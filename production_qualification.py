#!/usr/bin/env python3
"""Bind production approval to the tested runtime coordinate."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

REQUIRED_SUITE_RUNS = {
    "reliability": 12,
    "cache_hot": 2,
    "retained_replay": 1,
    "quality": 24,
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_fingerprint(inputs: Mapping[str, Path], pi_version: str) -> dict[str, str]:
    fingerprint = {name: file_sha256(path) for name, path in sorted(inputs.items())}
    fingerprint["pi_version"] = pi_version
    return fingerprint


def verify_artifact(
    artifact: Mapping[str, Any], inputs: Mapping[str, Path], pi_version: str
) -> list[str]:
    errors: list[str] = []
    if artifact.get("schema") != 1:
        errors.append("unsupported qualification schema")
    if artifact.get("backend") != "peregrine":
        errors.append("qualification backend mismatch")

    recorded = artifact.get("fingerprint")
    if not isinstance(recorded, dict):
        return errors + ["missing fingerprint"]

    current = build_fingerprint(inputs, pi_version)
    for name, digest in current.items():
        if name == "pi_version":
            if recorded.get(name) != digest:
                errors.append("Pi version mismatch")
            continue
        if recorded.get(name) != digest:
            errors.append(f"fingerprint mismatch: {name}")

    suites = artifact.get("suites")
    if not isinstance(suites, dict):
        return errors + ["missing suites"]
    for name, minimum_runs in REQUIRED_SUITE_RUNS.items():
        result = suites.get(name)
        if not isinstance(result, dict):
            errors.append(f"missing suite: {name}")
            continue
        if result.get("passed") is not True:
            errors.append(f"suite failed: {name}")
        runs = result.get("runs")
        if not isinstance(runs, int) or runs < minimum_runs:
            errors.append(f"insufficient suite runs: {name}")

    return errors
