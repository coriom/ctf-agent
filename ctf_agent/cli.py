import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .orchestrator import run_api_only


def main() -> None:
    load_dotenv()

    ap = argparse.ArgumentParser(prog="ctf-agent")
    sub = ap.add_subparsers(dest="cmd", required=True)

    solve = sub.add_parser("solve")
    solve.add_argument("challenge_dir", type=str)
    solve.add_argument("--out", type=str, default="artifacts/latest")

    args = ap.parse_args()
    if args.cmd != "solve":
        raise SystemExit(2)

    manager_key = os.getenv("OPENAI_API_KEY_MANAGER", "")
    hacker_key = os.getenv("OPENAI_API_KEY_HACKER", "")
    if not manager_key or not hacker_key:
        print("Missing OPENAI_API_KEY_MANAGER or OPENAI_API_KEY_HACKER in .env", file=sys.stderr)
        raise SystemExit(2)

    manager_model = os.getenv("CTF_AGENT_MODEL_MANAGER", "gpt-4.1-mini")
    hacker_model = os.getenv("CTF_AGENT_MODEL_HACKER", "gpt-4.1-mini")
    max_steps = int(os.getenv("CTF_AGENT_MAX_STEPS", "12"))
    max_files = int(os.getenv("CTF_AGENT_MAX_FILES", "50"))
    max_file_mb = int(os.getenv("CTF_AGENT_MAX_FILE_MB", "20"))

    challenge_dir = Path(args.challenge_dir).resolve()
    out_dir = Path(args.out).resolve()

    if not challenge_dir.exists() or not challenge_dir.is_dir():
        print("Invalid challenge_dir", file=sys.stderr)
        raise SystemExit(2)

    state = run_api_only(
        challenge_dir=challenge_dir,
        out_dir=out_dir,
        manager_key=manager_key,
        hacker_key=hacker_key,
        manager_model=manager_model,
        hacker_model=hacker_model,
        max_steps=max_steps,
        max_files=max_files,
        max_file_mb=max_file_mb,
    )

    if state.get("found_flag"):
        print(state["found_flag"])
        raise SystemExit(0)

    print("NO_FLAG_FOUND")
    raise SystemExit(1)
