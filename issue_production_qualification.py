#!/usr/bin/env python3
"""Issue or verify a hash-bound Peregrine production qualification."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from production_qualification import build_fingerprint, file_sha256, verify_artifact

DEFAULT_ARTIFACT = Path("/var/lib/pibench/qualifications/peregrine.json")
DEFAULT_CONFIG = Path("/etc/pibench-production-qualification.json")
RELIABILITY_PROFILES = frozenset({
    "pi-agent-reliability",
    "pi-agent-reliability-v1",
    "pi-agent-reliability-v2",
})


def load_inputs(config_path: Path) -> dict[str, Path]:
    payload = json.loads(config_path.read_text())
    inputs = payload.get("inputs")
    if not isinstance(inputs, dict) or not inputs:
        raise ValueError(f"qualification config has no inputs: {config_path}")
    return {str(name): Path(str(path)) for name, path in inputs.items()}


def pi_version() -> str:
    return subprocess.run(["pi", "--version"], text=True, capture_output=True, check=True).stdout.strip()


def evidence(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text())
    passed = payload.get("passed") is True
    runs = payload.get("runs", 0)
    if payload.get("profile") in RELIABILITY_PROFILES:
        results = payload.get("results", [])
        passed = bool(results) and all(item.get("passed") is True for item in results)
        runs = sum(int(item.get("scenarios_total", 0)) for item in results)
    if not passed:
        raise ValueError(f"evidence is not passing: {path}")
    if not isinstance(runs, int):
        raise ValueError(f"evidence has invalid run count: {path}")
    return {"passed": True, "runs": runs, "path": str(path), "sha256": file_sha256(path)}


def issue(args: argparse.Namespace) -> int:
    inputs = load_inputs(args.config)
    suites = {}
    for item in args.evidence:
        name, separator, raw_path = item.partition("=")
        if not separator:
            raise ValueError(f"invalid evidence argument: {item}")
        suites[name] = evidence(Path(raw_path).resolve())
    artifact = {
        "schema": 1,
        "backend": "peregrine",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "fingerprint": build_fingerprint(inputs, pi_version()),
        "suites": suites,
    }
    errors = verify_artifact(artifact, inputs, pi_version())
    if errors:
        raise ValueError("; ".join(errors))
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=args.artifact.parent, delete=False) as handle:
        json.dump(artifact, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    os.chmod(temporary, 0o600)
    temporary.replace(args.artifact)
    print(f"issued {args.artifact}")
    return 0


def check(args: argparse.Namespace) -> int:
    inputs = load_inputs(args.config)
    if not args.artifact.is_file():
        print(f"missing qualification: {args.artifact}")
        return 1
    errors = verify_artifact(json.loads(args.artifact.read_text()), inputs, pi_version())
    if errors:
        print("qualification rejected: " + "; ".join(errors))
        return 1
    print("qualification accepted")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("issue", "check"))
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument(
        "--config", type=Path,
        default=Path(os.environ.get("PIBENCH_QUALIFICATION_CONFIG", DEFAULT_CONFIG)),
    )
    parser.add_argument("--evidence", action="append", default=[])
    args = parser.parse_args()
    return issue(args) if args.command == "issue" else check(args)


if __name__ == "__main__":
    raise SystemExit(main())
