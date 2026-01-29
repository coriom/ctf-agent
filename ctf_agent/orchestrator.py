# ctf_agent/orchestrator.py
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .agents.llm_manager import LLMManager
from .agents.llm_hacker import LLMHacker

FLAG_RE = re.compile(r"(flag\{[^}\n]+\}|ctf\{[^}\n]+\}|picoCTF\{[^}\n]+\})", re.IGNORECASE)
FLAG_PREFIXES = ("flag{", "ctf{", "picoCTF{")

DEFAULT_CMD_ALLOWLIST = {
    "file",
    "strings",
    "xxd",
    "hexdump",
    "unzip",
    "7z",
    "tar",
    "jq",
    "python3",
    "python",
}

DEFAULT_INSTALL_ALLOWLIST = {
    # keep minimal; extend as needed
    "binutils",
    "p7zip-full",
    "unzip",
    "jq",
    "exiftool",
    "tshark",
    "binwalk",
}

NETWORK_TOKENS = {
    "curl",
    "wget",
    "nc",
    "netcat",
    "ssh",
    "telnet",
    "nmap",
    "http",
    "https",
}


def _now_iso() -> str:
    import datetime as _dt

    return _dt.datetime.utcnow().isoformat() + "Z"


def find_flag(text: str) -> Optional[str]:
    m = FLAG_RE.search(text or "")
    return m.group(0) if m else None


def list_challenge_files(challenge_dir: Path) -> List[Path]:
    return [p for p in sorted(challenge_dir.rglob("*")) if p.is_file()]


def _safe_relpath(base: Path, p: Path) -> str:
    return str(p.resolve().relative_to(base.resolve()))


def _detect_host() -> Dict[str, Any]:
    sysname = platform.system().lower()
    is_wsl = False
    if sysname == "linux":
        try:
            txt = Path("/proc/version").read_text(errors="ignore").lower()
            is_wsl = ("microsoft" in txt) or ("wsl" in txt)
        except Exception:
            pass

    return {
        "os": sysname,  # "linux" | "darwin" | "windows"
        "is_wsl": is_wsl,
        "platform": platform.platform(),
        "python": platform.python_version(),
    }


def _write_outputs_local(out_dir: Path, state: Dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")

    report = []
    report.append("# CTF Agent Report (LLM planning + local execution)\n")
    report.append(f"- started_at: {state.get('started_at')}\n")
    report.append(f"- challenge_dir: {state.get('challenge_dir')}\n")
    report.append(f"- work_dir: {state.get('work_dir')}\n")
    report.append(f"- host: {state.get('host')}\n")
    report.append(f"- files: {len(state.get('files', []))}\n")
    report.append(f"- steps: {len(state.get('steps', []))}\n")
    report.append(f"- found_flag: {state.get('found_flag')}\n\n")

    report.append("## Steps\n")
    for i, s in enumerate(state.get("steps", []), start=1):
        report.append(f"### Step {i}\n")
        report.append("```json\n")
        report.append(json.dumps(s, indent=2))
        report.append("\n```\n\n")

    (out_dir / "report.md").write_text("".join(report), encoding="utf-8")

    if state.get("found_flag"):
        (out_dir / "flag.txt").write_text(state["found_flag"] + "\n", encoding="utf-8")


@dataclass
class RunResult:
    ok: bool
    stdout: str
    stderr: str
    timeout: bool = False
    flag: Optional[str] = None


class LocalRunner:
    def __init__(
        self,
        challenge_dir: Path,
        work_dir: Path,
        allow_network: bool,
        allow_install: bool,
        cmd_allowlist: set[str],
        install_allowlist: set[str],
    ):
        self.challenge_dir = challenge_dir.resolve()
        self.work_dir = work_dir.resolve()
        self.allow_network = allow_network
        self.allow_install = allow_install
        self.cmd_allowlist = cmd_allowlist
        self.install_allowlist = install_allowlist
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def list_files(self) -> RunResult:
        files = [str(p.relative_to(self.challenge_dir)) for p in sorted(self.challenge_dir.rglob("*")) if p.is_file()]
        out = "\n".join(files) + ("\n" if files else "")
        return RunResult(True, out, "")

    def read_file_head(self, relpath: str, max_bytes: int = 250_000) -> RunResult:
        p = (self.challenge_dir / relpath).resolve()
        if not str(p).startswith(str(self.challenge_dir)):
            return RunResult(False, "", "path escape blocked")
        data = p.read_bytes()[:max_bytes]
        txt = data.decode("utf-8", errors="replace")
        return RunResult(True, txt, "", flag=find_flag(txt))

    def _check_cmd(self, cmd: List[str]) -> Tuple[bool, str]:
        if not cmd:
            return False, "empty cmd"
        bin_name = Path(cmd[0]).name
        if bin_name not in self.cmd_allowlist:
            return False, f"cmd not allowed: {bin_name}"

        if not self.allow_network:
            s = " ".join(cmd).lower()
            for tok in NETWORK_TOKENS:
                if tok in s:
                    return False, f"network token blocked: {tok}"
        return True, ""

    def run_cmd(
        self,
        cmd: List[str],
        timeout_s: int = 10,
        cwd_rel: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> RunResult:
        ok, reason = self._check_cmd(cmd)
        if not ok:
            return RunResult(False, "", reason)

        cwd = self.work_dir if cwd_rel is None else (self.work_dir / cwd_rel)
        cwd.mkdir(parents=True, exist_ok=True)

        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        try:
            p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout_s, env=merged_env)
            flag = find_flag(p.stdout) or find_flag(p.stderr)
            return RunResult(p.returncode == 0, p.stdout, p.stderr, timeout=False, flag=flag)
        except subprocess.TimeoutExpired as e:
            out = e.stdout or ""
            err = e.stderr or ""
            flag = find_flag(out) or find_flag(err)
            return RunResult(False, out, err, timeout=True, flag=flag)

    def run_python(self, code: str, timeout_s: int = 10) -> RunResult:
        # prefer python3 if present in allowlist
        py = "python3" if "python3" in self.cmd_allowlist else "python"
        return self.run_cmd([py, "-c", code], timeout_s=timeout_s)

    def extract_archive(self, relpath: str, timeout_s: int = 20) -> RunResult:
        src = (self.challenge_dir / relpath).resolve()
        if not str(src).startswith(str(self.challenge_dir)):
            return RunResult(False, "", "path escape blocked")

        outdir = self.work_dir / "extracted"
        outdir.mkdir(parents=True, exist_ok=True)

        low = relpath.lower()
        if low.endswith(".zip"):
            return self.run_cmd(["unzip", "-o", str(src), "-d", str(outdir)], timeout_s=timeout_s)
        if low.endswith(".7z"):
            return self.run_cmd(["7z", "x", "-y", f"-o{outdir}", str(src)], timeout_s=timeout_s)
        if low.endswith((".tar", ".tar.gz", ".tgz")):
            return self.run_cmd(["tar", "-xf", str(src), "-C", str(outdir)], timeout_s=timeout_s)

        return RunResult(False, "", "unknown archive type")

    def install(self, packages: List[str], timeout_s: int = 120) -> RunResult:
        if not self.allow_install:
            return RunResult(False, "", "install blocked (enable --allow-install)")

        # enforce allowlist
        for p in packages:
            if p not in self.install_allowlist:
                return RunResult(False, "", f"package not allowed: {p}")

        host = _detect_host()
        osname = host["os"]

        if osname == "linux":
            if shutil.which("apt") is None:
                return RunResult(False, "", "apt not found on this linux host")
            cmd = ["sudo", "apt", "update"]
            r1 = subprocess.run(cmd, capture_output=True, text=True)
            if r1.returncode != 0:
                return RunResult(False, r1.stdout, r1.stderr)
            cmd2 = ["sudo", "apt", "install", "-y", *packages]
            return self.run_cmd(cmd2, timeout_s=timeout_s)

        if osname == "darwin":
            if shutil.which("brew") is None:
                return RunResult(False, "", "brew not found on macOS")
            cmd = ["brew", "install", *packages]
            return self.run_cmd(cmd, timeout_s=timeout_s)

        return RunResult(False, "", f"unsupported OS for install: {osname}")


def _read_objective(challenge_dir: Path) -> str:
    # Prefer OBJECTIVE.txt, else README.txt, else empty
    for name in ("OBJECTIVE.txt", "README.txt", "README.md"):
        p = challenge_dir / name
        if p.exists() and p.is_file():
            try:
                return p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                return p.read_text(errors="replace")
    return ""


def run_hybrid_llm_local_exec(
    challenge_dir: Path,
    out_dir: Path,
    work_dir: Path,
    manager_key: str,
    hacker_key: str,
    manager_model: str,
    hacker_model: str,
    max_steps: int,
    max_files: int,
    max_file_mb: int,
    allow_network: bool,
    allow_install: bool,
    cmd_allowlist: set[str],
    install_allowlist: set[str],
) -> Dict[str, Any]:
    challenge_dir = challenge_dir.resolve()
    out_dir = out_dir.resolve()
    work_dir = work_dir.resolve()

    # file inventory for the LLMs (no upload, just metadata + paths)
    all_paths = list_challenge_files(challenge_dir)
    limited: List[Path] = []
    for p in all_paths:
        if len(limited) >= max_files:
            break
        size_mb = p.stat().st_size / (1024 * 1024)
        if size_mb <= max_file_mb:
            limited.append(p)

    files_meta = []
    for p in limited:
        files_meta.append(
            {
                "path": str(p.relative_to(challenge_dir)),
                "size_bytes": p.stat().st_size,
                "suffix": p.suffix.lower(),
            }
        )

    objective_text = _read_objective(challenge_dir)

    state: Dict[str, Any] = {
        "started_at": _now_iso(),
        "challenge_dir": str(challenge_dir),
        "work_dir": str(work_dir),
        "host": _detect_host(),
        "policy": {
            "allow_network": allow_network,
            "allow_install": allow_install,
            "cmd_allowlist": sorted(list(cmd_allowlist)),
            "install_allowlist": sorted(list(install_allowlist)),
        },
        "objective_text": objective_text,
        "files": files_meta,
        "steps": [],
        "found_flag": None,
        "objective": None,
        "last_exec": None,
    }

    # LLM clients are created inside LLMManager/LLMHacker in your codebase.
    # Keep signature aligned with your existing constructors.
    manager = LLMManager(client=make_client(manager_key), model=manager_model)  # type: ignore[name-defined]
    hacker = LLMHacker(client=make_client(hacker_key), model=hacker_model, file_ids=[])  # type: ignore[name-defined]

    runner = LocalRunner(
        challenge_dir=challenge_dir,
        work_dir=work_dir,
        allow_network=allow_network,
        allow_install=allow_install,
        cmd_allowlist=cmd_allowlist,
        install_allowlist=install_allowlist,
    )

    for _ in range(max_steps):
        m = manager.decide(state)
        state["objective"] = m.get("objective")

        if m.get("stop") and m.get("final_flag"):
            state["found_flag"] = m["final_flag"]
            state["steps"].append({"type": "manager_stop", "flag": state["found_flag"]})
            break

        instruction = m.get("instruction_to_hacker", "")

        # Hacker should now return an action JSON:
        # { "action": { "type": "...", ... }, "note": "..." }
        # Backward compatibility: if it returns {status, flag,...} we still handle it.
        h = hacker.attempt(instruction, state)

        if isinstance(h.get("flag"), str) and h["flag"].startswith(FLAG_PREFIXES):
            state["found_flag"] = h["flag"]
            state["steps"].append(
                {
                    "type": "hacker_found_direct",
                    "objective": state.get("objective"),
                    "instruction_to_hacker": instruction,
                    "hacker": h,
                }
            )
            break

        action = (h.get("action") or {}) if isinstance(h, dict) else {}

        step_entry: Dict[str, Any] = {
            "objective": state.get("objective"),
            "instruction_to_hacker": instruction,
            "hacker_note": h.get("note"),
            "hacker_raw": {k: h.get(k) for k in ("status", "notes", "evidence", "suggestion_to_manager") if isinstance(h, dict)},
            "action": action,
        }

        # If hacker requests stop
        if action.get("type") == "stop":
            flag = action.get("flag")
            if isinstance(flag, str) and flag.startswith(FLAG_PREFIXES):
                state["found_flag"] = flag
            step_entry["exec"] = {"type": "stop"}
            state["steps"].append(step_entry)
            break

        # Execute locally
        exec_res: Optional[RunResult] = None
        atype = action.get("type")

        try:
            if atype == "list_files":
                exec_res = runner.list_files()

            elif atype == "read_file_head":
                exec_res = runner.read_file_head(
                    relpath=str(action.get("target", "")),
                    max_bytes=int(action.get("max_bytes", 250_000)),
                )

            elif atype == "run_cmd":
                exec_res = runner.run_cmd(
                    cmd=list(action.get("cmd", [])),
                    timeout_s=int(action.get("timeout_s", 10)),
                    cwd_rel=action.get("cwd"),
                    env=action.get("env"),
                )

            elif atype == "run_python":
                exec_res = runner.run_python(
                    code=str(action.get("code", "")),
                    timeout_s=int(action.get("timeout_s", 10)),
                )

            elif atype == "extract_archive":
                exec_res = runner.extract_archive(
                    relpath=str(action.get("target", "")),
                    timeout_s=int(action.get("timeout_s", 20)),
                )

            elif atype == "install":
                pkgs = action.get("packages", [])
                if not isinstance(pkgs, list):
                    pkgs = []
                exec_res = runner.install([str(x) for x in pkgs], timeout_s=int(action.get("timeout_s", 120)))

            else:
                exec_res = RunResult(False, "", f"unknown action.type: {atype}")

        except Exception as e:
            exec_res = RunResult(False, "", f"execution error: {type(e).__name__}: {e}")

        # Store output in separate files to avoid bloating state.json
        out_dir.mkdir(parents=True, exist_ok=True)
        step_idx = len(state["steps"]) + 1
        stdout_path = out_dir / f"step_{step_idx:03d}.stdout.txt"
        stderr_path = out_dir / f"step_{step_idx:03d}.stderr.txt"
        stdout_path.write_text(exec_res.stdout or "", encoding="utf-8", errors="replace")
        stderr_path.write_text(exec_res.stderr or "", encoding="utf-8", errors="replace")

        step_entry["exec"] = {
            "ok": exec_res.ok,
            "timeout": exec_res.timeout,
            "stdout_file": stdout_path.name,
            "stderr_file": stderr_path.name,
            "flag": exec_res.flag,
        }
        state["last_exec"] = {
            "ok": exec_res.ok,
            "timeout": exec_res.timeout,
            "stdout_preview": (exec_res.stdout or "")[:2000],
            "stderr_preview": (exec_res.stderr or "")[:2000],
            "flag": exec_res.flag,
        }

        state["steps"].append(step_entry)

        if exec_res.flag:
            state["found_flag"] = exec_res.flag
            break

    _write_outputs_local(out_dir, state)
    return state


# Backward-compatible alias (your CLI may still import run_api_only)
def run_api_only(*args, **kwargs):  # noqa: D401
    return run_hybrid_llm_local_exec(*args, **kwargs)


# NOTE:
# You must have make_client available in llm/openai_gateway.py.
# If your current gateway does not expose make_client, add:
#   from openai import OpenAI
#   def make_client(api_key: str) -> OpenAI: return OpenAI(api_key=api_key)
from .llm.openai_gateway import make_client  # keep at bottom to avoid circular issues
