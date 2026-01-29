from __future__ import annotations
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

FLAG_RE = re.compile(r"(flag\{[^}\n]+\}|ctf\{[^}\n]+\}|picoCTF\{[^}\n]+\})", re.IGNORECASE)

# Whitelist minimale. Tu peux l’étendre.
DEFAULT_CMD_ALLOWLIST = {
    "file", "strings", "xxd", "hexdump",
    "unzip", "7z", "tar",
    "jq",
    "python3",
}

# Par défaut: refuser les commandes réseau. On peut activer via flag.
NETWORK_TOKENS = {"curl", "wget", "nc", "netcat", "ssh", "telnet", "nmap", "http", "https"}

@dataclass
class RunResult:
    ok: bool
    stdout: str
    stderr: str
    timeout: bool = False
    flag: Optional[str] = None

def find_flag(text: str) -> Optional[str]:
    m = FLAG_RE.search(text or "")
    return m.group(0) if m else None

def _check_cmd(cmd: List[str], allow_network: bool, allowlist: set[str]) -> Tuple[bool, str]:
    if not cmd:
        return False, "empty cmd"
    bin_name = Path(cmd[0]).name
    if bin_name not in allowlist:
        return False, f"cmd not allowed: {bin_name}"
    if not allow_network:
        s = " ".join(cmd).lower()
        for tok in NETWORK_TOKENS:
            if tok in s:
                return False, f"network token blocked: {tok}"
    return True, ""

class LocalRunner:
    def __init__(self, challenge_dir: Path, work_dir: Path, allow_network: bool = False, cmd_allowlist: Optional[set[str]] = None):
        self.challenge_dir = challenge_dir
        self.work_dir = work_dir
        self.allow_network = allow_network
        self.cmd_allowlist = cmd_allowlist or DEFAULT_CMD_ALLOWLIST
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def list_files(self) -> RunResult:
        files = [str(p.relative_to(self.challenge_dir)) for p in sorted(self.challenge_dir.rglob("*")) if p.is_file()]
        out = "\n".join(files) + ("\n" if files else "")
        return RunResult(True, out, "")

    def read_file_head(self, relpath: str, max_bytes: int = 200_000) -> RunResult:
        p = (self.challenge_dir / relpath).resolve()
        if not str(p).startswith(str(self.challenge_dir.resolve())):
            return RunResult(False, "", "path escape blocked")
        data = p.read_bytes()[:max_bytes]
        try:
            txt = data.decode("utf-8", errors="replace")
        except Exception:
            txt = data.decode(errors="replace")
        flag = find_flag(txt)
        return RunResult(True, txt, "", flag=flag)

    def run_cmd(self, cmd: List[str], timeout_s: int = 10, cwd_rel: Optional[str] = None, env: Optional[Dict[str,str]] = None) -> RunResult:
        ok, reason = _check_cmd(cmd, self.allow_network, self.cmd_allowlist)
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
        return self.run_cmd(["python3", "-c", code], timeout_s=timeout_s)

    def extract_archive(self, relpath: str, timeout_s: int = 20) -> RunResult:
        # Extraction dans work_dir/extracted/
        src = (self.challenge_dir / relpath).resolve()
        if not str(src).startswith(str(self.challenge_dir.resolve())):
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
