#!/usr/bin/env python3
"""Sandbox helpers for executing untrusted model-generated Python.

PiBench treats every generated submission as hostile. Executable checks run
without network access or writable access to the host filesystem. An explicitly
requested unsafe fallback exists only for controlled legacy environments.

Two isolation backends are supported, and the choice is recorded because the two
are NOT equally strong:

* ``bubblewrap`` (Linux) -- kernel namespaces, read-only bind mounts, tmpfs
  ``/work`` and ``/tmp``, cleared environment. The strong reference backend.
* ``seatbelt`` (macOS) -- ``sandbox-exec`` deny-only profile plus the shared
  ``setrlimit`` budget. It denies network egress, host writes and host reads of
  user data, but macOS exposes no mount or PID namespaces, Apple deprecates
  sandbox profiles, and Apple documents them as best-effort rather than a
  security boundary. It is a containment lane, not an equivalent one.

Callers must stamp the backend onto every run so results are never silently
ranked across different isolation guarantees.
"""

from __future__ import annotations

import os
import platform
import resource
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Sequence

BUBBLEWRAP = "bubblewrap"
SEATBELT = "seatbelt"
UNSANDBOXED = "unsandboxed"

SEATBELT_EXECUTABLE = "/usr/bin/sandbox-exec"

# Denied to generated code. Allow-listing is added back only for the sandbox work
# directory and the submission itself. Seatbelt profiles must stay deny-only for
# these subpath rules -- blanket ``(deny file-read*)`` followed by an allow-list, or
# ``require-not`` inside a read deny, aborts sandboxd (SIGABRT); denying a subpath
# and re-allowing a path nested inside it is the verified-working pattern.
#
# Scratch roots are denied alongside user data because submissions run concurrently
# under the same scratch parent: leaving it readable lets one submission read another
# attempt's files, which contaminates scoring. Bubblewrap does not have this hole --
# only explicitly bind-mounted paths exist inside its namespace -- so a seatbelt lane
# is strictly weaker and must never be ranked against a bubblewrap lane.
SEATBELT_DENIED_READ_ROOTS = (
    "/Users",
    "/Volumes",
    "/Network",
    "/tmp",        # canonical /private/tmp
    "/var/tmp",    # canonical /private/var/tmp
    "/var/folders",  # canonical /private/var/folders: per-user TMPDIR lives here
    "/private/tmp",
    "/private/var/tmp",
    "/private/var/folders",
)


class SandboxUnavailable(RuntimeError):
    """Raised when no safe generated-code sandbox is available."""


# Resource limits this platform refuses to install; probed once in the parent so
# the verdict is reportable. preexec_fn runs in a forked child, so recording the
# gap there would never reach the caller.
_UNSUPPORTED_LIMITS: dict[str, str] | None = None


def _probe_limits() -> dict[str, str]:
    global _UNSUPPORTED_LIMITS
    if _UNSUPPORTED_LIMITS is None:
        found: dict[str, str] = {}
        for label, value in (
            ("RLIMIT_AS", (512 * 1024 * 1024, 512 * 1024 * 1024)),
            ("RLIMIT_DATA", (512 * 1024 * 1024, 512 * 1024 * 1024)),
        ):
            which = getattr(resource, label, None)
            if which is None:
                continue
            try:
                resource.setrlimit(which, value)
            except (ValueError, OSError) as exc:
                found[label] = str(exc)
        _UNSUPPORTED_LIMITS = found
    return _UNSUPPORTED_LIMITS


def limit_gaps() -> list[str]:
    """Resource limits the platform refused, for honest run provenance."""

    return sorted(_probe_limits())


def _limits(timeout: int):
    """Build a preexec_fn applying every rlimit the platform will accept.

    macOS rejects finite RLIMIT_AS/RLIMIT_DATA with
    ``ValueError: current limit exceeds maximum limit``. Raising there would abort
    every executable check on Darwin, so unsupported limits are skipped and
    reported through ``limit_gaps()``; wall-clock timeout remains the bound on
    runaway work.
    """

    unsupported = _probe_limits()
    requested = [
        ("RLIMIT_CORE", resource.RLIMIT_CORE, (0, 0)),
        ("RLIMIT_CPU", resource.RLIMIT_CPU, (max(1, timeout), max(2, timeout + 1))),
        ("RLIMIT_FSIZE", resource.RLIMIT_FSIZE, (16 * 1024 * 1024, 16 * 1024 * 1024)),
        ("RLIMIT_NOFILE", resource.RLIMIT_NOFILE, (64, 64)),
        # Bubblewrap's PID namespace and --die-with-parent contain descendant
        # processes. RLIMIT_NPROC is intentionally omitted because Linux counts
        # the host user's existing processes, which can prevent namespace setup.
        ("RLIMIT_AS", resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024)),
    ]

    def apply() -> None:
        for label, which, value in requested:
            if label in unsupported:
                continue
            try:
                resource.setrlimit(which, value)
            except (ValueError, OSError):
                pass

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


def seatbelt_available() -> bool:
    """True only when a real seatbelt profile is enforced on this machine.

    Existence of ``sandbox-exec`` is not enough: profiles can abort (SIGABRT) on
    some macOS builds, so a trivial profile is executed and verified to actually
    deny. The verdict is cached for the process lifetime.
    """

    global _SEATBELT_PROBE
    if _SEATBELT_PROBE is not None:
        return _SEATBELT_PROBE
    _SEATBELT_PROBE = _probe_seatbelt()
    return _SEATBELT_PROBE


_SEATBELT_PROBE: bool | None = None

_SEATBELT_PROBE_PROFILE = '(version 1)(allow default)(deny network*)'


def _probe_seatbelt() -> bool:
    if sys.platform != "darwin" or not Path(SEATBELT_EXECUTABLE).exists():
        return False
    try:
        with tempfile.TemporaryDirectory(prefix="pibench-seatbelt-probe-") as tmp:
            script = Path(tmp) / "probe.py"
            script.write_text(
                "import socket\n"
                "try:\n"
                "    socket.create_connection(('127.0.0.1',9),timeout=2)\n"
                "    print('NETWORK_OPEN')\n"
                "except Exception:\n"
                "    print('NETWORK_BLOCKED')\n"
            )
            proc = subprocess.run(
                [SEATBELT_EXECUTABLE, "-p", _SEATBELT_PROBE_PROFILE,
                 "/usr/bin/python3", "-I", "-B", str(script)],
                capture_output=True, text=True, timeout=30, env={},
            )
    except (OSError, subprocess.SubprocessError):
        return False
    # A sandbox that fails to start, aborts, or leaves the network open is unusable.
    return proc.returncode == 0 and "NETWORK_BLOCKED" in proc.stdout


def resolve_backend() -> str:
    """Pick the strongest available backend, deterministically.

    Bubblewrap is always preferred: it is the stronger boundary and the reference
    platform for published scores.
    """

    if os.environ.get("PIBENCH_ALLOW_UNSANDBOXED_EXEC") == "1":
        return UNSANDBOXED
    if shutil.which("bwrap"):
        return BUBBLEWRAP
    if seatbelt_available():
        return SEATBELT
    raise SandboxUnavailable(
        "No sandbox backend is available for executable checks. Install 'bwrap' "
        "(Linux) or run on macOS with a working 'sandbox-exec'. Setting "
        "PIBENCH_ALLOW_UNSANDBOXED_EXEC=1 is only acceptable in a disposable "
        "environment."
    )


def backend_details() -> dict[str, object]:
    """Provenance for the selected backend, for stamping onto runs.

    ``isolation_strength`` is deliberately part of the record so a weaker lane can
    never be mistaken for the reference lane in a ranking.
    """

    backend = resolve_backend()
    if backend == BUBBLEWRAP:
        return {"sandbox_backend": backend, "isolation_strength": "namespaces",
                "sandbox_version": _bubblewrap_version()}
    if backend == SEATBELT:
        return {"sandbox_backend": backend, "isolation_strength": "best-effort",
                "sandbox_mechanism": "sandbox-exec deny-only profile",
                "sandbox_limitations": [
                    "no mount namespace", "no pid namespace",
                    "apple-deprecated profile format",
                    "not a security boundary per apple documentation",
                    "no per-process memory cap: platform refuses RLIMIT_AS/RLIMIT_DATA",
                ],
                "resource_limit_gaps": sorted(set(limit_gaps())),
                "macos_version": platform.mac_ver()[0]}
    return {"sandbox_backend": backend, "isolation_strength": "none"}


def _bubblewrap_version() -> str | None:
    try:
        out = subprocess.run(["bwrap", "--version"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return (out.stdout or out.stderr).strip() or None


def _seatbelt_profile(workdir: Path, script: Path) -> str:
    """Build a deny-only seatbelt profile for one submission.

    Paths are canonicalised because macOS exposes /tmp and /var as symlinks into
    /private; an un-canonicalised subpath silently matches nothing, which is worse
    than failing because the submission runs unrestricted.
    """

    writable = os.path.realpath(str(workdir))
    reads_allowed = [writable, os.path.realpath(str(script))]
    lines = [
        "(version 1)",
        "(allow default)",
        # No outbound connections, including to loopback model endpoints.
        "(deny network*)",
        # Nothing outside the work directory may be written.
        "(deny file-write*)",
        f'(allow file-write* (subpath "{writable}"))',
    ]
    for root in dict.fromkeys(os.path.realpath(r) for r in SEATBELT_DENIED_READ_ROOTS):
        if root and Path(root).exists():
            lines.append(f'(deny file-read* (subpath "{root}"))')
    home = os.path.realpath(str(Path.home()))
    if home and not any(home.startswith(os.path.realpath(r)) for r in SEATBELT_DENIED_READ_ROOTS):
        lines.append(f'(deny file-read* (subpath "{home}"))')
    for target in reads_allowed:
        if target:
            lines.append(f'(allow file-read* (subpath "{target}") (literal "{target}"))')
    return "\n".join(lines) + "\n"


def _seatbelt_command(script: Path, args: Sequence[str], profile_path: Path) -> list[str]:
    return [
        SEATBELT_EXECUTABLE, "-f", str(profile_path),
        "/usr/bin/python3", "-I", "-B", str(script), *args,
    ]


def run_python_file(
    script: Path,
    *,
    args: Sequence[str] = (),
    input_text: str | None = None,
    timeout: int = 8,
) -> subprocess.CompletedProcess[str]:
    """Run a generated Python file safely and return its completed process."""

    script = script.resolve()
    backend = resolve_backend()
    profile_path: Path | None = None
    # Seatbelt cannot mount a tmpfs, so TMPDIR is redirected into the work
    # directory: this keeps writes contained and matches bubblewrap's tmpfs /tmp,
    # otherwise tempfile.TemporaryDirectory() behaves differently per lane.
    env: dict[str, str] = {}

    if backend == UNSANDBOXED:
        command = ["/usr/bin/python3", "-I", "-B", str(script), *args]
        cwd = str(script.parent)
    elif backend == SEATBELT:
        workdir = script.parent
        workdir.mkdir(parents=True, exist_ok=True)
        (workdir / "tmp").mkdir(exist_ok=True)
        profile_path = workdir / "submission.sb"
        profile_path.write_text(_seatbelt_profile(workdir, script))
        command = _seatbelt_command(script, args, profile_path)
        cwd = str(workdir)
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": "/nonexistent",
            "PYTHONPATH": "",
            "LC_ALL": "C.UTF-8",
            "TMPDIR": str(Path(os.path.realpath(str(workdir))) / "tmp"),
        }
    else:
        command = _bubblewrap_command(script, args)
        cwd = None

    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            input=input_text,
            text=True,
            capture_output=True,
            timeout=timeout,
            env=env,
            start_new_session=True,
            preexec_fn=_limits(timeout),
        )
    finally:
        if profile_path is not None:
            profile_path.unlink(missing_ok=True)

    if backend == BUBBLEWRAP and proc.returncode != 0:
        if proc.stderr.lstrip().startswith("bwrap:"):
            raise SandboxUnavailable(f"Bubblewrap could not start: {proc.stderr.strip()}")
    if backend == SEATBELT:
        # A signal-death here means the profile aborted (SIGABRT) rather than the
        # submission doing something forbidden; report it as unavailable instead of
        # silently scoring the submission as a failure.
        if proc.returncode < 0 and "Fatal Python error" not in proc.stderr:
            raise SandboxUnavailable(
                f"Seatbelt could not start (signal {-proc.returncode}): "
                f"{proc.stderr.strip()[:200]}"
            )
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
