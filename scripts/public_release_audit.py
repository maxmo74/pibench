#!/usr/bin/env python3
"""Fail when reachable public Git history contains secrets or private artifacts."""

from __future__ import annotations

import argparse
import csv
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF_RELATIVE = Path(__file__).resolve().relative_to(ROOT).as_posix()

SECRET_PATTERNS = (
    ("private key", re.compile(rb"-----BEGIN (?:OPENSSH |RSA |EC |DSA |PGP )?PRIVATE KEY-----")),
    ("GitHub token", re.compile(rb"\b(?:github_pat_[A-Za-z0-9_]{20,}|gh[opusr]_[A-Za-z0-9]{30,})\b")),
    ("OpenAI token", re.compile(rb"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}\b")),
    ("Anthropic token", re.compile(rb"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("Hugging Face token", re.compile(rb"\bhf_[A-Za-z0-9]{20,}\b")),
    ("AWS access ID", re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("Google API key", re.compile(rb"\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("Slack token", re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("JWT", re.compile(rb"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("credential URL", re.compile(rb"(?i)https?://[^\s/:@]+:[^\s/@]+@[^\s]+")),
)
PRIVATE_PATH = re.compile(rb"/(?:home/[A-Za-z0-9._-]+|root)/")
DANGEROUS_EXEC = re.compile(rb"\bexec\s*\(\s*(?:code|text|source|stdout)\b")
PYTHON_SUBPROCESS = re.compile(rb"subprocess\.(?:run|call|Popen|check_output)\s*\([^\n]*(?:python3|python)")
FORBIDDEN_SUFFIXES = {
    ".key", ".p12", ".pem", ".pfx", ".gguf", ".aria2", ".sqlite", ".sqlite3", ".safetensors",
}
FORBIDDEN_NAMES = {"auth.json", "credentials.json", ".env"}
MAX_BLOB_BYTES = 1_000_000
LARGE_PUBLIC_FILES = {"RESULTS.csv"}
EXPECTED_NAME = "maxmo74"
EXPECTED_EMAIL = "8917299+maxmo74@users.noreply.github.com"


def git_bytes(*args: str, input_data: bytes | None = None) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], input=input_data)


def check_public_path(path: str, *, historical: bool = False) -> list[str]:
    errors: list[str] = []
    relative = Path(path)
    parts = {part.lower() for part in relative.parts}
    prefix = "historical " if historical else ""
    if relative.name.lower() in FORBIDDEN_NAMES or relative.suffix.lower() in FORBIDDEN_SUFFIXES:
        errors.append(f"{prefix}forbidden result artifact: {path}")
    if "results" in parts and path != "RESULTS.csv":
        errors.append(f"{prefix}private results path: {path}")
    if "__pycache__" in parts or relative.suffix.lower() in {".pyc", ".pyo"}:
        errors.append(f"{prefix}compiled artifact: {path}")
    return errors


def check_blob(path: str, data: bytes, *, historical: bool = False) -> list[str]:
    errors: list[str] = []
    prefix = "history: " if historical else ""
    if path != SELF_RELATIVE:
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(data):
                errors.append(f"{prefix}{path}: possible {label}")
        if PRIVATE_PATH.search(data):
            errors.append(f"{prefix}{path}: machine-specific absolute path")
    if b"\0" in data[:8192]:
        errors.append(f"{prefix}binary Git blob: {path}")
        return errors
    if len(data) > MAX_BLOB_BYTES and path not in LARGE_PUBLIC_FILES:
        errors.append(f"{prefix}Git blob exceeds 1 MB: {path} ({len(data)} bytes)")
    # Current executable code must use the sandbox helper. Historical source is
    # retained for auditability; old unsafe implementations are not credentials
    # or private artifacts and cannot execute from the current tree.
    if not historical and path.endswith(".py") and path != "pibench_sandbox.py":
        if DANGEROUS_EXEC.search(data):
            errors.append(f"{prefix}{path}: direct execution of generated text")
        if PYTHON_SUBPROCESS.search(data):
            errors.append(f"{prefix}{path}: Python subprocess outside sandbox helper")
    return errors


def audit_csv(path: Path, database: Path | None) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return ["RESULTS.csv is missing"]
    sys.path.insert(0, str(ROOT))
    import pibench_report  # noqa: PLC0415

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != pibench_report.CSV_FIELDS:
            errors.append("RESULTS.csv header does not match the fixed schema")
            return errors
        previous: tuple[int, int, int] | None = None
        rows = 0
        numeric = {
            "run_task_count", "run_passed", "run_weighted_score", "run_weighted_total",
            "logical_cpus", "memory_gib", "context_size", "task_weight", "passed",
            "score", "total", "weighted_score", "wall_s", "approx_output_tokens", "approx_output_tps",
        }
        for line_number, row in enumerate(reader, 2):
            rows += 1
            for field, value in row.items():
                if value is None:
                    errors.append(f"RESULTS.csv:{line_number}: malformed row")
                    break
                if pibench_report.CSV_FORBIDDEN.search(value):
                    errors.append(f"RESULTS.csv:{line_number}:{field}: forbidden private marker")
                if value.startswith(("=", "+", "-", "@")):
                    errors.append(f"RESULTS.csv:{line_number}:{field}: active spreadsheet cell")
                if field in numeric and value:
                    try:
                        if not math.isfinite(float(value)):
                            raise ValueError
                    except ValueError:
                        errors.append(f"RESULTS.csv:{line_number}:{field}: non-finite/non-numeric value")
            try:
                key = (int(row["run_id"]), int(row["run_model_id"]), int(row["result_id"]))
                if previous is not None and key < previous:
                    errors.append(f"RESULTS.csv:{line_number}: non-deterministic ordering")
                previous = key
            except ValueError:
                errors.append(f"RESULTS.csv:{line_number}: invalid identifier")
        if rows == 0:
            errors.append("RESULTS.csv contains no rows")

    if database is not None:
        if not database.is_file():
            errors.append(f"database not found: {database}")
        else:
            with tempfile.TemporaryDirectory(prefix="pibench-public-audit-") as tmp:
                regenerated = Path(tmp) / "RESULTS.csv"
                pibench_report.export_public_csv(database, regenerated)
                if regenerated.read_bytes() != path.read_bytes():
                    errors.append("RESULTS.csv is stale or non-deterministic relative to the supplied database")
    return errors


def audit_current() -> tuple[list[str], int]:
    errors: list[str] = []
    tracked = [item.decode() for item in git_bytes("ls-files", "-z").split(b"\0") if item]
    for path in tracked:
        errors.extend(check_public_path(path))
        errors.extend(check_blob(path, (ROOT / path).read_bytes()))
    return errors, len(tracked)


def audit_history() -> tuple[list[str], int, int]:
    errors: list[str] = []
    records = git_bytes("rev-list", "--objects", "--all").decode().splitlines()
    seen_blobs: set[str] = set()
    history_paths = 0
    for record in records:
        object_id, _, object_path = record.partition(" ")
        if not object_path:
            continue
        history_paths += 1
        errors.extend(check_public_path(object_path, historical=True))
        if object_id in seen_blobs or git_bytes("cat-file", "-t", object_id).strip() != b"blob":
            continue
        seen_blobs.add(object_id)
        errors.extend(check_blob(object_path, git_bytes("cat-file", "blob", object_id), historical=True))

    identities = git_bytes("log", "--all", "--format=%an%x00%ae%x00%cn%x00%ce").decode().splitlines()
    for identity in identities:
        parts = identity.split("\0")
        if len(parts) != 4:
            continue
        for role, name, email in (("author", parts[0], parts[1]), ("committer", parts[2], parts[3])):
            if name != EXPECTED_NAME:
                errors.append(f"commit history contains an unexpected {role} name: {name}")
            if email != EXPECTED_EMAIL:
                errors.append(f"commit history contains a non-noreply {role} email: {email}")
    for message in git_bytes("log", "--all", "--format=%B").splitlines():
        if PRIVATE_PATH.search(message):
            errors.append("machine-specific absolute path in commit message")
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(message):
                errors.append(f"possible {label} in commit message")
    commits = int(git_bytes("rev-list", "--all", "--count").strip() or b"0")
    return errors, commits, len(seen_blobs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current-only", action="store_true", help="skip reachable-history and identity checks")
    parser.add_argument("--database", type=Path, help="also require RESULTS.csv to equal a fresh export from this private database")
    args = parser.parse_args()

    errors, tracked = audit_current()
    commits = blobs = 0
    if not args.current_only:
        history_errors, commits, blobs = audit_history()
        errors.extend(history_errors)
    errors.extend(audit_csv(ROOT / "RESULTS.csv", args.database))

    if errors:
        print("PUBLIC RELEASE AUDIT FAILED", file=sys.stderr)
        for error in sorted(set(errors)):
            print(f"- {error}", file=sys.stderr)
        return 1
    suffix = f", {commits} commits, {blobs} reachable blobs" if not args.current_only else ""
    print(f"Public release audit passed: {tracked} tracked files{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
