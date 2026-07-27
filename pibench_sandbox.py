#!/usr/bin/env python3
"""Sandbox helpers for executing untrusted model-generated Python.

PiBench treats every generated submission as hostile. By default, executable
checks require Bubblewrap and run without network access or writable access to
the host filesystem. An explicitly requested unsafe fallback exists only for
controlled legacy environments.
"""

from __future__ import annotations

import os
import resource
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Sequence


class SandboxUnavailable(RuntimeError):
    """Raised when no safe generated-code sandbox is available."""


def _limits(timeout: int):
    def apply() -> None:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_CPU, (max(1, timeout), max(2, timeout + 1)))
        resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024 * 1024, 16 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        # Bubblewrap's PID namespace and --die-with-parent contain descendant
        # processes. RLIMIT_NPROC is intentionally omitted because Linux counts
        # the host user's existing processes, which can prevent namespace setup.
        # Enough for CPython and the benchmark tests, but not memory-exhaustion output.
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))

    return apply


def _bubblewrap_command(script: Path, args: Sequence[str]) -> list[str]:
    bwrap = shutil.which("bwrap")
    if not bwrap:
        raise SandboxUnavailable(
            "Bubblewrap is required for executable checks. Install 'bwrap', or set "
            "PIBENCH_ALLOW_UNSANDBOXED_EXEC=1 only in a disposable environment."
        )

    command = [
        bwrap,
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--ro-bind", "/usr", "/usr",
        "--ro-bind", "/bin", "/bin",
        "--ro-bind", "/lib", "/lib",
    ]
    if Path("/lib64").exists():
        command += ["--ro-bind", "/lib64", "/lib64"]
    command += [
        "--proc", "/proc",
        "--dev", "/dev",
        "--tmpfs", "/tmp",
        "--tmpfs", "/work",
        "--ro-bind", str(script), "/work/submission.py",
        "--chdir", "/work",
        "--clearenv",
        "--setenv", "HOME", "/nonexistent",
        "--setenv", "PATH", "/usr/bin:/bin",
        "--setenv", "PYTHONPATH", "",
        "--setenv", "LC_ALL", "C.UTF-8",
        "/usr/bin/python3", "-I", "-B", "/work/submission.py",
        *args,
    ]
    return command


def run_python_file(
    script: Path,
    *,
    args: Sequence[str] = (),
    input_text: str | None = None,
    timeout: int = 8,
) -> subprocess.CompletedProcess[str]:
    """Run a generated Python file safely and return its completed process."""

    script = script.resolve()
    if os.environ.get("PIBENCH_ALLOW_UNSANDBOXED_EXEC") == "1":
        command = ["/usr/bin/python3", "-I", "-B", str(script), *args]
        cwd = str(script.parent)
    else:
        command = _bubblewrap_command(script, args)
        cwd = None

    proc = subprocess.run(
        command,
        cwd=cwd,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        env={},
        start_new_session=True,
        preexec_fn=_limits(timeout),
    )
    if os.environ.get("PIBENCH_ALLOW_UNSANDBOXED_EXEC") != "1" and proc.returncode != 0:
        if proc.stderr.lstrip().startswith("bwrap:"):
            raise SandboxUnavailable(f"Bubblewrap could not start: {proc.stderr.strip()}")
    return proc


def run_python_source(
    source: str,
    *,
    args: Sequence[str] = (),
    input_text: str | None = None,
    timeout: int = 8,
) -> subprocess.CompletedProcess[str]:
    """Write generated source to a private temporary file and run it safely."""

    with tempfile.TemporaryDirectory(prefix="pibench-sandbox-") as tmp:
        script = Path(tmp) / "submission.py"
        script.write_text(source)
        return run_python_file(script, args=args, input_text=input_text, timeout=timeout)
