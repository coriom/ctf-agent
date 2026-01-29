from pathlib import Path

def repo_root() -> Path:
    # ctf_agent/llm/prompts.py -> repo root
    return Path(__file__).resolve().parents[2]

def load_prompt(name: str) -> str:
    p = repo_root() / "prompts" / name
    return p.read_text(encoding="utf-8")
