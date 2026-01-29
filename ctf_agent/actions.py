from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

# Actions autorisées (MVP). Tu en ajoutes ensuite (binwalk, exiftool, tshark, etc.)
ALLOWED_ACTIONS = {
    "list_files",
    "read_file_head",
    "run_cmd",
    "run_python",
    "extract_archive",
    "stop",
}

@dataclass
class Action:
    type: str
    target: Optional[str] = None          # path ou string
    cmd: Optional[List[str]] = None       # pour run_cmd
    code: Optional[str] = None            # pour run_python
    timeout_s: int = 10
    cwd: Optional[str] = None             # relatif au workdir
    env: Optional[Dict[str, str]] = None  # env additionnel

def validate_action(a: Dict[str, Any]) -> None:
    t = a.get("type")
    if t not in ALLOWED_ACTIONS:
        raise ValueError(f"Action not allowed: {t}")
    if t == "run_cmd" and not isinstance(a.get("cmd"), list):
        raise ValueError("run_cmd requires cmd: [..]")
    if t == "run_python" and not isinstance(a.get("code"), str):
        raise ValueError("run_python requires code: str")
