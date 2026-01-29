# ctf_agent/orchestrator.py
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List, Optional

from .solver import list_files, write_outputs

# Local (rule-based) manager + local tool-runner hacker
from .agents.manager import Manager
from .agents.hacker import Hacker as ToolRunnerHacker

# LLM agents (API mode)
# These modules must exist if you enable --api
from .agents.llm_manager import LLMManager
from .agents.llm_hacker import LLMHacker


def init_state(challenge_dir: Path, files: List[str]) -> Dict[str, Any]:
    return {
        "challenge_dir": str(challenge_dir),
        "files": files,
        "actions": [],
        "done": {"read_text": [], "try_base64_line": [], "strings": []},
        "found_flag": None,
        "objective": None,
    }


def _mark_done(state: Dict[str, Any], action: Dict[str, Any]) -> None:
    t = action.get("type")
    if t not in state.get("done", {}):
        return
    target = action.get("target")
    if target is None:
        return
    state["done"][t].append(target)


def run_two_agents(
    challenge_dir: Path,
    out_dir: Path,
    work_dir: Path,
    max_steps: int = 80,
) -> Dict[str, Any]:
    """
    Local mode:
    - Manager: rule-based strategy + memory
    - Hacker: executes whitelisted local tools
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    files = list_files(challenge_dir)
    state = init_state(challenge_dir, files)

    manager = Manager(challenge_dir, files)
    tool_runner = ToolRunnerHacker(challenge_dir, work_dir)

    last_tool_output: Optional[str] = None

    for _ in range(max_steps):
        decision = manager.decide_next(state)
        action = decision.action

        # STOP from manager
        if action.get("type") == "stop":
            if action.get("flag"):
                state["found_flag"] = action["flag"]
            state["actions"].append({"type": "stop", "note": decision.note})
            break

        # Execute one action
        res = tool_runner.execute(action)
        last_tool_output = res.stdout if res.stdout else res.stderr

        _mark_done(state, action)

        entry = {
            "manager_note": decision.note,
            "action": action,
            "ok": res.ok,
            "stderr": (res.stderr or "")[:2000],
        }

        if res.flag:
            state["found_flag"] = res.flag
            entry["found_flag"] = res.flag
            state["actions"].append(entry)
            break

        state["actions"].append(entry)

    write_outputs(out_dir, state)
    return state


def run_two_agents_api(
    challenge_dir: Path,
    out_dir: Path,
    work_dir: Path,
    model: str,
    max_steps: int = 80,
) -> Dict[str, Any]:
    """
    API mode:
    - LLMManager: decides objective + message_to_hacker
    - LLMHacker: picks exactly one next tool action (JSON)
    - ToolRunnerHacker: executes the tool action locally (whitelist enforced)
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    files = list_files(challenge_dir)
    state = init_state(challenge_dir, files)

    manager = LLMManager(model=model)
    hacker_llm = LLMHacker(model=model)
    tool_runner = ToolRunnerHacker(challenge_dir, work_dir)

    last_tool_output: Optional[str] = None

    for _ in range(max_steps):
        # Manager step
        m = manager.decide(state=state, last_tool_output=last_tool_output)
        state["objective"] = m.get("objective")

        if m.get("stop") and m.get("final_flag"):
            state["found_flag"] = m["final_flag"]
            state["actions"].append(
                {"type": "manager_stop", "objective": state["objective"], "flag": state["found_flag"]}
            )
            break

        manager_msg = m.get("message_to_hacker", "")

        # Hacker (LLM) chooses one action
        h = hacker_llm.pick_action(
            manager_msg=manager_msg,
            state=state,
            last_tool_output=last_tool_output,
        )
        action = h.get("action") or {}

        # Validate basic shape early
        if "type" not in action:
            state["actions"].append(
                {
                    "type": "invalid_action",
                    "manager_msg": manager_msg,
                    "hacker_note": h.get("note"),
                    "error": "Missing action.type",
                }
            )
            break

        # Hacker stop
        if action.get("type") == "stop":
            if action.get("flag"):
                state["found_flag"] = action["flag"]
            state["actions"].append(
                {"type": "hacker_stop", "manager_msg": manager_msg, "hacker_note": h.get("note")}
            )
            break

        # Execute locally (whitelist enforced in ToolRunnerHacker/tools.py)
        res = tool_runner.execute(action)
        last_tool_output = res.stdout if res.stdout else res.stderr

        _mark_done(state, action)

        entry = {
            "objective": state.get("objective"),
            "manager_msg": manager_msg,
            "hacker_note": h.get("note"),
            "action": action,
            "ok": res.ok,
            "stderr": (res.stderr or "")[:2000],
        }

        if res.flag:
            state["found_flag"] = res.flag
            entry["found_flag"] = res.flag
            state["actions"].append(entry)
            break

        state["actions"].append(entry)

    write_outputs(out_dir, state)
    return state
