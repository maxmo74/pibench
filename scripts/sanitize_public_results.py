#!/usr/bin/env python3
"""Redact machine-specific paths and optional literals from local raw artifacts.

This helper is only for reviewing ignored ``results/*.json`` and ``results/*.md``
files. It is not the public CSV exporter; use ``pibench_report.py --csv-out`` for
that fixed-schema export.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

DEFAULT_GLOBS = ("results/*.json", "results/*.md")
PATH_RULES = (
    (re.compile(r"/home/[A-Za-z0-9._-]+(?=/|\b)"), "<home>"),
    (re.compile(r"/root(?=/|\b)"), "<root>"),
)
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def sanitize(text: str, literals: list[str]) -> str:
    """Return a display-safe copy of local text without claiming publication safety."""

    for value in sorted((value for value in literals if value), key=len, reverse=True):
        text = text.replace(value, "<user>")
    for pattern, replacement in PATH_RULES:
        text = pattern.sub(replacement, text)
    return EMAIL.sub("<redacted-email>", text)


def selected_files(root: Path, globs: list[str]) -> list[Path]:
    return sorted({path for pattern in globs for path in root.glob(pattern) if path.is_file()})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--glob", action="append", dest="globs", help="file glob relative to root; repeatable")
    parser.add_argument("--literal", action="append", default=[], help="additional exact private string to redact; repeatable")
    parser.add_argument("--write", action="store_true", help="rewrite files; otherwise report files that need redaction")
    args = parser.parse_args()

    root = args.root.resolve()
    changed: list[Path] = []
    errors: list[str] = []
    for path in selected_files(root, args.globs or list(DEFAULT_GLOBS)):
        try:
            original = path.read_text()
            public = sanitize(original, args.literal)
            if public != original:
                changed.append(path)
                if args.write:
                    path.write_text(public)
        except (OSError, UnicodeError) as exc:
            errors.append(f"{path}: {exc}")

    for error in errors:
        print(error)
    verb = "rewrote" if args.write else "would rewrite"
    print(f"{verb} {len(changed)} file(s)")
    for path in changed:
        print(path.relative_to(root))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
