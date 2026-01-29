import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional

from ..tools import find_flag, load_text

B64_RE = re.compile(r"^[A-Za-z0-9+/=]{16,}$")

TEXT_EXT = {".txt", ".md", ".log", ".json", ".csv"}

@dataclass
class ManagerDecision:
    action: Dict[str, Any]
    note: str = ""

class Manager:
    def __init__(self, challenge_dir: Path, files: List[str]):
        self.challenge_dir = challenge_dir
        self.files = files

    def decide_next(self, state: Dict[str, Any]) -> ManagerDecision:
        # stop si flag déjà trouvée
        if state.get("found_flag"):
            return ManagerDecision({"type": "stop", "flag": state["found_flag"]}, "already have flag")

        done = state.get("done", {})
        done_reads = set(done.get("read_text", []))
        done_strings = set(done.get("strings", []))
        done_b64 = set(done.get("try_base64_line", []))

        # 1) lire fichiers texte
        for rel in self.files:
            p = self.challenge_dir / rel
            if p.suffix.lower() in TEXT_EXT and rel not in done_reads:
                return ManagerDecision({"type": "read_text", "target": rel, "timeout_s": 2}, "scan text")

        # 2) après lectures, tenter base64 sur lignes candidates
        for rel in self.files:
            p = self.challenge_dir / rel
            if p.suffix.lower() in TEXT_EXT:
                txt = load_text(p)
                for line in txt.splitlines():
                    s = line.strip()
                    if s in done_b64:
                        continue
                    if B64_RE.fullmatch(s) and (len(s) % 4 == 0):
                        return ManagerDecision({"type": "try_base64_line", "target": s, "timeout_s": 5}, "try base64")

        # 3) strings sur gros/binaires
        for rel in self.files:
            p = self.challenge_dir / rel
            if rel in done_strings:
                continue
            if p.stat().st_size > 200_000 or p.suffix.lower() in {".exe", ".elf", ".bin", ".out"}:
                return ManagerDecision({"type": "strings", "target": rel, "timeout_s": 10}, "strings scan")

        return ManagerDecision({"type": "stop"}, "no more actions")
