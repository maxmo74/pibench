#!/usr/bin/env python3
"""Run PiBench's local compile, test, CSV, privacy, and Git consistency checks."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, help="private SQLite database used to verify deterministic RESULTS.csv")
    parser.add_argument("--history", action="store_true", help="include all reachable Git history and identities")
    args = parser.parse_args()

    run([sys.executable, "-m", "compileall", "-q", "."])
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    run(["git", "diff", "--check"])
    audit = [sys.executable, "scripts/public_release_audit.py"]
    if not args.history:
        audit.append("--current-only")
    if args.database:
        audit += ["--database", str(args.database.resolve())]
    run(audit)
    print("Repository audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
