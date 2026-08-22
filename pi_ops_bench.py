#!/usr/bin/env python3
"""Run a versioned, tool-enabled, multi-turn daily-operations diagnostic.

Unlike the canonical no-tools suite, pi-ops-v1 gives Pi read/bash/edit/write in
an isolated disposable repository. It measures whether a model can fix code,
then follow up with a production service/documentation change, and finally
review its own work without touching the host filesystem outside that sandbox.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pibench_sandbox import run_python_source

ROOT = Path(__file__).resolve().parent
PROFILE = "pi-ops-v1"
REQUIRED_PI_VERSION = "0.84.1"
WORKSPACE = Path("/tmp/pibench-ops-cwd-v1")
AGENT_DIR = Path("/tmp/pibench-ops-agent-v1")
SESSION_DIR = Path("/tmp/pibench-ops-sessions-v1")
OUTPUT_DIR = Path("/tmp/pibench-ops-output-v1")
LOCK_PATH = Path("/tmp/pibench-ops-v1.lock")
ATTESTOR = ROOT / "scripts" / "ops_prompt_attestor.ts"
TOOLS = "read,bash,edit,write"
EXPECTED_TASK_FILES = {"retry.py", "README.md", ".gitignore", "deploy/pibench-worker.service"}
EXPECTED_SYSTEM_PROMPT_SHA256 = "c9f6885987f161b6c530b108b61e2d6b173e1b79dd1caeac2ddc0fb7f18b6cb9"

TURN_PROMPTS = (
    """Inspect this repository and fix the retry implementation so all tests pass. Requirements: retry_delays(attempts, base=1, cap=8) must return exactly `attempts` delays, use capped exponential backoff, reject booleans and non-positive/non-integer attempts with ValueError, reject boolean or non-positive base/cap with ValueError, and perform no sleeping or randomness. Do not modify tests. Run the tests before finishing.""",
    """Now productionize deploy/pibench-worker.service without undoing the retry fix. It must wait for network-online.target, run as User and Group pibench, use WorkingDirectory=/opt/pibench, EnvironmentFile=-/etc/pibench/worker.env, ExecStart=/opt/pibench/venv/bin/python -m worker, restart on failure after 5 seconds, and include NoNewPrivileges=true, PrivateTmp=true, ProtectSystem=strict, ProtectHome=true, and ReadWritePaths=/var/lib/pibench. Update README.md with the exact unittest and systemctl enable/start commands. Keep the change minimal and run tests again.""",
    """Review the repository changes for correctness, security, and scope. Fix any remaining issue you find, rerun the tests, and finish with a concise summary of files changed and validation performed.""",
)

BASE_RETRY = '''def retry_delays(attempts, base=1, cap=8):
    """Return retry delays."""
    return [min(cap, base * (2 ** i)) for i in range(attempts + 1)]
'''

VISIBLE_TESTS = '''import unittest

from retry import retry_delays


class RetryDelayTests(unittest.TestCase):
    def test_default_schedule(self):
        self.assertEqual(retry_delays(5), [1, 2, 4, 8, 8])

    def test_custom_cap(self):
        self.assertEqual(retry_delays(4, base=2, cap=5), [2, 4, 5, 5])

    def test_invalid_attempts(self):
        for value in (0, -1, 1.5, True):
            with self.assertRaises(ValueError):
                retry_delays(value)


if __name__ == "__main__":
    unittest.main()
'''

BASE_SERVICE = '''[Unit]
Description=PiBench worker
After=network.target

[Service]
ExecStart=python worker.py
Restart=always

[Install]
WantedBy=multi-user.target
'''

BASE_README = """# PiBench worker

Run `python retry.py` while developing.
"""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_model_arg(model_arg: str) -> tuple[str, str, str | None]:
    base = model_arg
    thinking = None
    if ":" in model_arg:
        candidate, level = model_arg.rsplit(":", 1)
        if level in {"off", "minimal", "low", "medium", "high", "xhigh", "max"}:
            base, thinking = candidate, level
    if "/" not in base:
        raise ValueError(f"model must include provider/model: {model_arg}")
    provider, model_id = base.split("/", 1)
    return provider, model_id, thinking


def source_agent_dir() -> Path:
    configured = os.environ.get("PI_CODING_AGENT_DIR")
    return Path(configured).expanduser() if configured else Path.home() / ".pi" / "agent"


def write_isolated_agent(model_arg: str) -> None:
    provider, model_id, _ = parse_model_arg(model_arg)
    source = json.loads((source_agent_dir() / "models.json").read_text())
    provider_config = source.get("providers", {}).get(provider)
    if not isinstance(provider_config, dict):
        raise ValueError(f"provider not found in models.json: {provider}")
    parsed = urllib.parse.urlsplit(str(provider_config.get("baseUrl", "")))
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("pi-ops-v1 only copies loopback HTTP providers into its sandbox")
    selected = None
    for candidate in provider_config.get("models", []):
        if candidate.get("id") == model_id:
            selected = {key: value for key, value in candidate.items() if key != "metadata"}
            break
    if selected is None:
        raise ValueError(f"model not found in provider {provider}: {model_id}")

    safe_provider = {
        key: value
        for key, value in provider_config.items()
        if key in {"baseUrl", "api", "compat"}
    }
    safe_provider["apiKey"] = "pibench-local"
    safe_provider["models"] = [selected]
    shutil.rmtree(AGENT_DIR, ignore_errors=True)
    AGENT_DIR.mkdir(mode=0o700)
    (AGENT_DIR / "models.json").write_text(json.dumps({"providers": {provider: safe_provider}}, indent=2) + "\n")
    (AGENT_DIR / "settings.json").write_text("{}\n")
    (AGENT_DIR / "auth.json").write_text("{}\n")
    shutil.copyfile(ATTESTOR, AGENT_DIR / "ops_prompt_attestor.ts")
    os.chmod(AGENT_DIR / "models.json", 0o600)
    os.chmod(AGENT_DIR / "settings.json", 0o600)
    os.chmod(AGENT_DIR / "auth.json", 0o600)
    os.chmod(AGENT_DIR / "ops_prompt_attestor.ts", 0o400)


def reset_workspace() -> str:
    for path in (WORKSPACE, SESSION_DIR, OUTPUT_DIR):
        shutil.rmtree(path, ignore_errors=True)
        path.mkdir(mode=0o700, parents=True)
    (WORKSPACE / "deploy").mkdir()
    (WORKSPACE / "tests").mkdir()
    (WORKSPACE / "retry.py").write_text(BASE_RETRY)
    (WORKSPACE / "tests" / "test_retry.py").write_text(VISIBLE_TESTS)
    (WORKSPACE / "deploy" / "pibench-worker.service").write_text(BASE_SERVICE)
    (WORKSPACE / "README.md").write_text(BASE_README)
    subprocess.run(["git", "init", "-q"], cwd=WORKSPACE, check=True)
    subprocess.run(["git", "config", "user.name", "PiBench fixture"], cwd=WORKSPACE, check=True)
    subprocess.run(["git", "config", "user.email", "fixture@invalid.example"], cwd=WORKSPACE, check=True)
    subprocess.run(["git", "add", "."], cwd=WORKSPACE, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=WORKSPACE, check=True)
    return sha256_bytes((WORKSPACE / "tests" / "test_retry.py").read_bytes())


def bwrap_command(pi_executable: Path, model_arg: str, session_id: str, prompt: str) -> list[str]:
    command = [
        "bwrap", "--unshare-all", "--share-net", "--die-with-parent", "--new-session",
        "--ro-bind", "/usr", "/usr", "--ro-bind", "/bin", "/bin",
        "--ro-bind", "/lib", "/lib", "--ro-bind", "/etc", "/etc",
    ]
    if Path("/lib64").exists():
        command += ["--ro-bind", "/lib64", "/lib64"]
    if not pi_executable.is_relative_to("/usr"):
        if not pi_executable.is_relative_to("/opt"):
            raise RuntimeError(f"pi-ops-v1 sandbox supports Pi under /usr or /opt, got {pi_executable}")
        command += ["--ro-bind", "/opt", "/opt"]
    command += [
        "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
        "--bind", str(WORKSPACE), str(WORKSPACE),
        "--bind", str(AGENT_DIR), "/agent",
        "--bind", str(SESSION_DIR), "/sessions",
        "--bind", str(OUTPUT_DIR), "/output",
        "--chdir", str(WORKSPACE), "--clearenv",
        "--setenv", "HOME", str(WORKSPACE),
        "--setenv", "PATH", "/usr/bin:/bin",
        "--setenv", "PI_CODING_AGENT_DIR", "/agent",
        "--setenv", "PI_OFFLINE", "1",
        "--setenv", "PI_TELEMETRY", "0",
        "--setenv", "PIBENCH_OPS_PROMPT_ATTESTATION", "/output/system-prompt-sha256.txt",
        str(pi_executable),
        "--model", model_arg,
        "--session-id", session_id,
        "--session-dir", "/sessions",
        "--tools", TOOLS,
        "--no-context-files", "--no-skills", "--no-prompt-templates", "--no-themes",
        "--no-extensions", "--extension", "/agent/ops_prompt_attestor.ts",
        "--offline", "--mode", "json", "--print", prompt,
    ]
    return command


def run_turn(pi_executable: Path, model_arg: str, session_id: str, prompt: str, timeout: int) -> dict[str, Any]:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            bwrap_command(pi_executable, model_arg, session_id, prompt),
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        returncode, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        returncode = -1
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        stderr = f"timeout after {timeout}s\n{stderr}"
    wall = time.monotonic() - started
    if sha256_bytes((AGENT_DIR / "ops_prompt_attestor.ts").read_bytes()) != sha256_bytes(ATTESTOR.read_bytes()):
        raise RuntimeError("tool-enabled session modified its prompt attestor")
    events = []
    for line in stdout.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    tool_calls = sum(1 for event in events if event.get("type") == "tool_execution_start")
    return {
        "returncode": returncode,
        "wall_s": wall,
        "tool_calls": tool_calls,
        "stdout_sha256": sha256_bytes(stdout.encode()),
        "stderr": stderr[-2000:],
    }


def retry_checks() -> dict[str, bool]:
    source = (WORKSPACE / "retry.py").read_text()
    assertions = {
        "default_schedule": "assert retry_delays(5) == [1, 2, 4, 8, 8]",
        "custom_schedule": "assert retry_delays(4, base=2, cap=5) == [2, 4, 5, 5]",
        "single_attempt": "assert retry_delays(1) == [1]",
        "attempt_validation": "\nfor value in (0, -1, 1.5, True, '2'):\n    try: retry_delays(value)\n    except ValueError: pass\n    else: raise AssertionError(value)",
        "base_validation": "\nfor value in (0, -1, True):\n    try: retry_delays(2, base=value)\n    except ValueError: pass\n    else: raise AssertionError(value)",
        "cap_validation": "\nfor value in (0, -1, True):\n    try: retry_delays(2, cap=value)\n    except ValueError: pass\n    else: raise AssertionError(value)",
        "large_cap": "assert retry_delays(6, base=3, cap=10) == [3, 6, 10, 10, 10, 10]",
    }
    checks: dict[str, bool] = {}
    for name, assertion in assertions.items():
        proc = run_python_source(source + "\n" + assertion + "\n", timeout=5)
        checks[name] = proc.returncode == 0
    checks["no_sleep_or_random"] = not re.search(r"\b(?:sleep|random)\b", source)
    return checks


def service_checks() -> dict[str, bool]:
    path = WORKSPACE / "deploy" / "pibench-worker.service"
    text = path.read_text() if path.is_file() else ""
    compact = {line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")}
    return {
        "network_online": "Wants=network-online.target" in compact and "After=network-online.target" in compact,
        "identity": "User=pibench" in compact and "Group=pibench" in compact,
        "working_directory": "WorkingDirectory=/opt/pibench" in compact,
        "environment_file": "EnvironmentFile=-/etc/pibench/worker.env" in compact,
        "exec_start": "ExecStart=/opt/pibench/venv/bin/python -m worker" in compact,
        "restart": "Restart=on-failure" in compact and bool({"RestartSec=5", "RestartSec=5s"} & compact),
        "no_new_privileges": "NoNewPrivileges=true" in compact,
        "private_tmp": "PrivateTmp=true" in compact,
        "filesystem_hardening": "ProtectSystem=strict" in compact and "ProtectHome=true" in compact,
        "write_path": "ReadWritePaths=/var/lib/pibench" in compact,
    }


def score_workspace(test_hash: str, turns: list[dict[str, Any]]) -> tuple[float, dict[str, Any]]:
    retry = retry_checks()
    service = service_checks()
    readme = (WORKSPACE / "README.md").read_text() if (WORKSPACE / "README.md").is_file() else ""
    readme_checks = {
        "test_command": "python3 -m unittest discover -s tests -v" in readme,
        "enable_command": "systemctl enable pibench-worker.service" in readme,
        "start_command": "systemctl start pibench-worker.service" in readme,
    }
    tests_unchanged = (WORKSPACE / "tests" / "test_retry.py").is_file() and sha256_bytes(
        (WORKSPACE / "tests" / "test_retry.py").read_bytes()
    ) == test_hash
    status_lines = subprocess.run(
        ["git", "status", "--porcelain"], cwd=WORKSPACE, text=True, capture_output=True, check=True
    ).stdout.splitlines()
    changed = {line[3:] for line in status_lines if len(line) > 3}
    generated = {
        path for path in changed
        if "__pycache__" in Path(path).parts or Path(path).suffix in {".pyc", ".pyo"}
    }
    reviewed_changes = changed - generated
    scope_clean = bool(reviewed_changes) and reviewed_changes.issubset(EXPECTED_TASK_FILES)
    turns_complete = all(turn["returncode"] == 0 for turn in turns) and len(turns) == len(TURN_PROMPTS)

    score = 0.0
    score += sum(retry.values()) / len(retry) * 35
    score += sum(service.values()) / len(service) * 30
    score += sum(readme_checks.values()) / len(readme_checks) * 15
    score += 10 if tests_unchanged else 0
    score += 5 if scope_clean else 0
    score += 5 if turns_complete else 0
    details = {
        "retry": retry,
        "service": service,
        "readme": readme_checks,
        "tests_unchanged": tests_unchanged,
        "scope_clean": scope_clean,
        "changed_files": sorted(reviewed_changes),
        "ignored_generated_files": sorted(generated),
        "turns_complete": turns_complete,
    }
    return score, details


def git_commit() -> str | None:
    proc = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True, capture_output=True)
    return proc.stdout.strip() if proc.returncode == 0 else None


def run_model(pi_executable: Path, model_arg: str, timeout: int) -> dict[str, Any]:
    write_isolated_agent(model_arg)
    test_hash = reset_workspace()
    session_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"pibench:{PROFILE}:{model_arg}"))
    turns = [run_turn(pi_executable, model_arg, session_id, prompt, timeout) for prompt in TURN_PROMPTS]
    hashes_path = OUTPUT_DIR / "system-prompt-sha256.txt"
    hashes = hashes_path.read_text().splitlines() if hashes_path.is_file() else []
    if len(hashes) != len(TURN_PROMPTS) or len(set(hashes)) != 1:
        raise RuntimeError(f"effective system prompt was not stable for {model_arg}: {hashes}")
    if hashes[0] != EXPECTED_SYSTEM_PROMPT_SHA256:
        raise RuntimeError(f"effective system prompt drifted for {model_arg}: {hashes[0]}")
    score, checks = score_workspace(test_hash, turns)
    return {
        "model": model_arg,
        "score": score,
        "system_prompt_sha256": hashes[0],
        "turns": turns,
        "total_wall_s": sum(turn["wall_s"] for turn in turns),
        "tool_calls": sum(turn["tool_calls"] for turn in turns),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("models", nargs="+", help="configured loopback Pi model arguments")
    parser.add_argument("--timeout", type=int, default=900, help="per-turn timeout")
    parser.add_argument("--output", type=Path, help="private JSON output path")
    args = parser.parse_args()

    if not shutil.which("bwrap"):
        parser.error("Bubblewrap is required")
    pi_path = shutil.which("pi")
    if not pi_path:
        parser.error("Pi is not on PATH")
    pi_executable = Path(pi_path).resolve()
    version = subprocess.run([str(pi_executable), "--version"], text=True, capture_output=True, check=True).stdout.strip()
    if version != REQUIRED_PI_VERSION:
        parser.error(f"{PROFILE} requires Pi {REQUIRED_PI_VERSION}, got {version}")
    if not ATTESTOR.is_file():
        parser.error(f"missing prompt attestor: {ATTESTOR}")

    LOCK_PATH.touch(mode=0o600, exist_ok=True)
    with LOCK_PATH.open("r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        results = [run_model(pi_executable, model, args.timeout) for model in args.models]

    prompt_hashes = {result["system_prompt_sha256"] for result in results}
    if len(prompt_hashes) != 1:
        raise RuntimeError(f"models did not share one effective system prompt: {prompt_hashes}")
    payload = {
        "profile": PROFILE,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pi_version": version,
        "pibench_commit": git_commit(),
        "attestor_sha256": sha256_bytes(ATTESTOR.read_bytes()),
        "system_prompt_sha256": next(iter(prompt_hashes)),
        "turn_prompt_sha256": [sha256_bytes(prompt.encode()) for prompt in TURN_PROMPTS],
        "results": results,
    }
    output = args.output or ROOT / "results" / f"pi_ops_{time.strftime('%Y%m%d-%H%M%S')}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=output.parent, prefix=output.name + ".", delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    os.chmod(temporary, 0o600)
    temporary.replace(output)

    print(f"profile={PROFILE} system_prompt_sha256={payload['system_prompt_sha256']}")
    for result in sorted(results, key=lambda item: item["score"], reverse=True):
        print(
            f"{result['model']}: {result['score']:.1f}/100, "
            f"tools={result['tool_calls']}, wall={result['total_wall_s']:.1f}s"
        )
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
