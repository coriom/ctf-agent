# ctf_agent/cli.py
import argparse
import os
import sys
from pathlib import Path

from .orchestrator import run_two_agents, run_two_agents_api


def main() -> None:
    ap = argparse.ArgumentParser(prog="ctf-agent")
    sub = ap.add_subparsers(dest="cmd", required=True)

    solve = sub.add_parser("solve")
    solve.add_argument("challenge_dir", type=str)
    solve.add_argument("--out", type=str, default="artifacts/latest")
    solve.add_argument("--work", type=str, default="artifacts/work")
    solve.add_argument("--max-steps", type=int, default=80)

    # API mode
    solve.add_argument("--api", action="store_true", help="Use OpenAI API (Manager+Hacker via prompts/)")
    solve.add_argument(
        "--model",
        type=str,
        default=os.getenv("CTF_AGENT_MODEL", "gpt-4.1-mini"),
        help="OpenAI model name (or set CTF_AGENT_MODEL)",
    )

    args = ap.parse_args()

    if args.cmd != "solve":
        raise SystemExit(2)

    challenge_dir = Path(args.challenge_dir).resolve()
    out_dir = Path(args.out).resolve()
    work_dir = Path(args.work).resolve()

    if not challenge_dir.exists() or not challenge_dir.is_dir():
        print("Invalid challenge_dir", file=sys.stderr)
        raise SystemExit(2)

    if args.api:
        state = run_two_agents_api(
            challenge_dir=challenge_dir,
            out_dir=out_dir,
            work_dir=work_dir,
            model=args.model,
            max_steps=args.max_steps,
        )
    else:
        state = run_two_agents(
            challenge_dir=challenge_dir,
            out_dir=out_dir,
            work_dir=work_dir,
            max_steps=args.max_steps,
        )

    if state.get("found_flag"):
        print(state["found_flag"])
        raise SystemExit(0)

    print("NO_FLAG_FOUND")
    raise SystemExit(1)
