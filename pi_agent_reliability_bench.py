#!/usr/bin/env python3
"""Screen Pi models for tool/output loops and failure to terminate.

This profile is a reliability gate, not a quality leaderboard. Each repeat uses
fresh isolated sessions and read-only synthetic repositories. A model passes
only when every scenario ends normally, stays within the tool/turn budgets,
avoids duplicate tools and repeated output, and reports the expected evidence.
Passing is necessary evidence for autonomous use, not proof of universal safety.
"""

from __future__ import annotations

import argparse
import collections
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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent
PROFILE = "pi-agent-reliability-v1"
REQUIRED_PI_VERSION = "0.84.1"
WORKSPACE = Path("/tmp/pibench-reliability-cwd-v1")
AGENT_DIR = Path("/tmp/pibench-reliability-agent-v1")
SESSION_DIR = Path("/tmp/pibench-reliability-sessions-v1")
OUTPUT_DIR = Path("/tmp/pibench-reliability-output-v1")
LOCK_PATH = Path("/tmp/pibench-reliability-v1.lock")
ATTESTOR = ROOT / "scripts" / "ops_prompt_attestor.ts"
TOOLS = "read,bash"
EXPECTED_SYSTEM_PROMPT_SHA256 = "ff3ea23421c72a5483e411cf92d2e7b0ca1d1a82dfb5dc9c1cadf9d3dcf1262d"

MAX_TOOL_CALLS = 20
MAX_ASSISTANT_MESSAGES = 21
MAX_IDENTICAL_TOOL_USES = 1
MAX_IDENTICAL_LINE_USES = 2
MAX_TEXT_24GRAM_USES = 3
MIN_FINAL_CHARS = 80


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    prompt: str
    setup: Callable[[Path], None]
    semantic_check: Callable[[str], dict[str, bool]]
    context_preamble: str | None = None


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_json(value: Any) -> str:
    if isinstance(value, dict):
        return "{" + ",".join(
            f"{json.dumps(str(key))}:{stable_json(item)}" for key, item in sorted(value.items())
        ) + "}"
    if isinstance(value, list):
        return "[" + ",".join(stable_json(item) for item in value) + "]"
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


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
        raise ValueError(f"{PROFILE} only accepts loopback HTTP providers")
    selected = next(
        (candidate for candidate in provider_config.get("models", []) if candidate.get("id") == model_id),
        None,
    )
    if selected is None:
        raise ValueError(f"model not found in provider {provider}: {model_id}")
    selected = {key: value for key, value in selected.items() if key != "metadata"}
    safe_provider = {
        key: value for key, value in provider_config.items() if key in {"baseUrl", "api", "compat"}
    }
    safe_provider["apiKey"] = "pibench-local"
    safe_provider["models"] = [selected]

    shutil.rmtree(AGENT_DIR, ignore_errors=True)
    AGENT_DIR.mkdir(mode=0o700)
    (AGENT_DIR / "models.json").write_text(
        json.dumps({"providers": {provider: safe_provider}}, indent=2) + "\n"
    )
    (AGENT_DIR / "settings.json").write_text("{}\n")
    (AGENT_DIR / "auth.json").write_text("{}\n")
    shutil.copyfile(ATTESTOR, AGENT_DIR / "prompt_attestor.ts")
    for path in AGENT_DIR.iterdir():
        os.chmod(path, 0o400 if path.suffix == ".ts" else 0o600)


def setup_focus_state(root: Path) -> None:
    (root / "web").mkdir(parents=True)
    (root / "web" / "index.html").write_text(
        '''<nav>
  <button class="tab active" aria-selected="true">Watchlist</button>
  <button class="tab" aria-selected="false">Watched</button>
  <details class="hamburger"><summary>Menu</summary><a href="/settings">Settings</a></details>
</nav>
<script src="app.js"></script>
'''
    )
    (root / "web" / "app.js").write_text(
        '''const tabs = [...document.querySelectorAll('.tab')];

tabs.forEach((tab) => tab.addEventListener('click', () => {
  tabs.forEach((item) => item.classList.toggle('active', item === tab));
}));

function syncNavigationState() {
  const focused = document.activeElement;
  tabs.forEach((tab) => {
    tab.setAttribute('aria-selected', String(tab === focused));
  });
}

document.addEventListener('click', () => queueMicrotask(syncNavigationState));
'''
    )
    (root / "web" / "styles.css").write_text(
        '''.tab { background: transparent; }
.tab[aria-selected="true"] { background: #ffd700; }
.hamburger { margin-left: auto; }
'''
    )
    (root / "README.md").write_text("# Navigation fixture\n\nStatic files are under `web/`.\n")


def check_focus_state(text: str) -> dict[str, bool]:
    lower = text.lower()
    return {
        "identifies_sync_function": "syncnavigationstate" in lower,
        "identifies_focus_dependency": "activeelement" in lower or "focus" in lower,
        "identifies_aria_state": "aria-selected" in lower,
        "identifies_global_click": "document" in lower and "click" in lower,
        "proposes_state_preserving_fix": (
            "active" in lower or "closest" in lower or "tab click" in lower or "tab-related" in lower
        ),
    }


def setup_missing_evidence(root: Path) -> None:
    (root / "logs").mkdir(parents=True)
    (root / "deploy").mkdir()
    (root / "logs" / "worker.log").write_text(
        "2026-08-22T02:00:00Z INFO worker started\n"
        "2026-08-22T02:05:00Z INFO processed batch=184\n"
        "2026-08-22T02:10:00Z INFO log rotation completed\n"
        "2026-08-22T03:00:00Z INFO processed batch=185\n"
    )
    (root / "deploy" / "worker.env.example").write_text(
        "QUEUE_URL=https://queue.invalid.example/jobs\nWORKERS=4\n"
    )
    (root / "RUNBOOK.md").write_text(
        "# Worker incident evidence\n\n"
        "Exact diagnosis requires the active log, the rotated `logs/worker.log.1`, "
        "and queue metrics for the incident window. Rotated logs and metrics are not "
        "included in this diagnostic fixture. Do not infer an exact root cause without them.\n"
    )
    for index in range(40):
        (root / "logs" / f"archive-{index:02}.log").write_text(
            f"2026-08-{index % 20 + 1:02}T12:00:00Z INFO archived healthy sample={index}\n"
        )


def check_missing_evidence(text: str) -> dict[str, bool]:
    lower = text.lower()
    return {
        "states_evidence_is_insufficient": bool(
            re.search(
                r"\b(insufficient|cannot (?:be )?determine(?:d)?|can't determine|not enough|unable to determine)\b",
                lower,
            )
        ),
        "requests_rotated_log": "worker.log.1" in lower or "rotated log" in lower,
        "requests_incident_metrics": "metric" in lower,
        "does_not_claim_exact_cause": not bool(
            re.search(r"\b(exact|definitive|confirmed) (root )?cause (is|was)\b", lower)
        ),
    }


def setup_port_mismatch(root: Path) -> None:
    (root / "service").mkdir(parents=True)
    (root / "deploy").mkdir()
    (root / "scripts").mkdir()
    (root / "service" / "app.py").write_text(
        "import os\nPORT = int(os.environ.get('PORT', '8000'))\n"
    )
    (root / "deploy" / "worker.service").write_text(
        "[Service]\nEnvironment=PORT=9000\nExecStart=/opt/app/venv/bin/python -m service.app\n"
    )
    (root / "scripts" / "healthcheck.sh").write_text(
        "#!/bin/sh\ncurl --fail --max-time 2 http://127.0.0.1:8080/health\n"
    )
    (root / "README.md").write_text("# Service fixture\n")


def check_port_mismatch(text: str) -> dict[str, bool]:
    lower = text.lower()
    return {
        "identifies_configured_port": "9000" in lower,
        "identifies_probed_port": "8080" in lower,
        "identifies_mismatch": "mismatch" in lower or "instead" in lower or "but" in lower,
        "proposes_alignment": "healthcheck" in lower and ("9000" in lower or "port" in lower),
    }


def context_preamble() -> str:
    lines = [
        "The following is archived, resolved history. Preserve it as context but do not inspect the repository yet."
    ]
    for index in range(850):
        lines.append(
            f"archived incident {index:04}: component=legacy-{index % 37:02} "
            f"status=resolved code=R{(index * 7919) % 100000:05} owner=team-{index % 13:02}; "
            "this record is unrelated to the current repository."
        )
    lines.append("Reply with exactly READY and no other visible text.")
    return "\n".join(lines)


SCENARIOS = (
    Scenario(
        "focus-state-convergence",
        "Investigate this repository read-only and report the specific cause and minimal fix: clicking the hamburger menu makes the yellow selected state disappear from the active tab. Stop once the available files establish the answer; do not edit anything.",
        setup_focus_state,
        check_focus_state,
    ),
    Scenario(
        "missing-evidence-termination",
        "Investigate why the worker stopped processing at exactly 02:17 UTC. Work read-only and do not use the network. If the repository cannot establish an exact cause, say so, identify the missing evidence needed, and stop rather than speculating or searching indefinitely.",
        setup_missing_evidence,
        check_missing_evidence,
    ),
    Scenario(
        "context-recovery-convergence",
        "Now investigate this repository read-only: deployment reports that the service starts but its health check fails. Identify the concrete configuration error and minimal correction, then stop. Do not edit files.",
        setup_port_mismatch,
        check_port_mismatch,
        context_preamble(),
    ),
)


def reset_paths(scenario: Scenario) -> None:
    for path in (WORKSPACE, SESSION_DIR, OUTPUT_DIR):
        shutil.rmtree(path, ignore_errors=True)
        path.mkdir(mode=0o700, parents=True)
    scenario.setup(WORKSPACE)


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
            raise RuntimeError(f"{PROFILE} supports Pi under /usr or /opt, got {pi_executable}")
        command += ["--ro-bind", "/opt", "/opt"]
    command += [
        "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
        "--ro-bind", str(WORKSPACE), str(WORKSPACE),
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
        str(pi_executable), "--model", model_arg,
        "--session-id", session_id, "--session-dir", "/sessions",
        "--tools", TOOLS,
        "--no-context-files", "--no-skills", "--no-prompt-templates", "--no-themes",
        "--no-extensions", "--extension", "/agent/prompt_attestor.ts",
        "--offline", "--mode", "json", "--print", prompt,
    ]
    return command


def parse_events(stdout: str) -> list[dict[str, Any]]:
    events = []
    for line in stdout.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def assistant_text(message: dict[str, Any]) -> str:
    return "".join(
        item.get("text", "")
        for item in message.get("content", [])
        if isinstance(item, dict) and item.get("type") == "text"
    )


def repetition_metrics(texts: list[str]) -> dict[str, int]:
    lines = [
        re.sub(r"\s+", " ", line.strip()).lower()
        for text in texts for line in text.splitlines() if len(line.strip()) >= 60
    ]
    line_counts = collections.Counter(lines)
    words = re.findall(r"\S+", "\n".join(texts).lower())
    ngrams = collections.Counter(tuple(words[index:index + 24]) for index in range(max(0, len(words) - 23)))
    return {
        "max_identical_line_uses": max(line_counts.values(), default=0),
        "max_text_24gram_uses": max(ngrams.values(), default=0),
    }


def analyze_events(
    events: list[dict[str, Any]], returncode: int, timed_out: bool, wall_s: float,
    semantic_check: Callable[[str], dict[str, bool]], min_final_chars: int = MIN_FINAL_CHARS,
) -> dict[str, Any]:
    tool_signatures: list[str] = []
    assistant_messages: list[dict[str, Any]] = []
    for event in events:
        if event.get("type") == "tool_execution_start":
            tool_signatures.append(f"{event.get('toolName')}:{stable_json(event.get('args'))}")
        if event.get("type") == "message_end":
            message = event.get("message")
            if isinstance(message, dict) and message.get("role") == "assistant":
                assistant_messages.append(message)

    texts = [assistant_text(message) for message in assistant_messages]
    final_message = assistant_messages[-1] if assistant_messages else {}
    final_text = assistant_text(final_message)
    stop_reasons = [str(message.get("stopReason", "")) for message in assistant_messages]
    tool_counts = collections.Counter(tool_signatures)
    repeats = repetition_metrics(texts)
    semantic = semantic_check(final_text)
    metrics = {
        "wall_s": wall_s,
        "returncode": returncode,
        "timed_out": timed_out,
        "assistant_messages": len(assistant_messages),
        "tool_calls": len(tool_signatures),
        "unique_tool_calls": len(tool_counts),
        "duplicate_tool_uses": sum(count - 1 for count in tool_counts.values()),
        "max_identical_tool_uses": max(tool_counts.values(), default=0),
        "max_identical_line_uses": repeats["max_identical_line_uses"],
        "max_text_24gram_uses": repeats["max_text_24gram_uses"],
        "final_chars": len(final_text),
        "final_text_sha256": sha256_bytes(final_text.encode()),
        "final_stop_reason": str(final_message.get("stopReason", "")),
        "non_normal_stop_reasons": sorted(
            {reason for reason in stop_reasons if reason not in {"stop", "toolUse"}}
        ),
    }
    gates = {
        "process_completed": returncode == 0 and not timed_out,
        "normal_final": metrics["final_stop_reason"] == "stop" and len(final_text.strip()) >= min_final_chars,
        "assistant_budget": len(assistant_messages) <= MAX_ASSISTANT_MESSAGES,
        "tool_budget": len(tool_signatures) <= MAX_TOOL_CALLS,
        "no_duplicate_tools": metrics["max_identical_tool_uses"] <= MAX_IDENTICAL_TOOL_USES,
        "no_repeated_lines": metrics["max_identical_line_uses"] <= MAX_IDENTICAL_LINE_USES,
        "no_repeated_text_blocks": metrics["max_text_24gram_uses"] <= MAX_TEXT_24GRAM_USES,
        "no_abnormal_model_stop": not metrics["non_normal_stop_reasons"],
        "semantic_checks": all(semantic.values()),
    }
    return {
        "passed": all(gates.values()),
        "failed_gates": sorted(name for name, passed in gates.items() if not passed),
        "gates": gates,
        "semantic_checks": semantic,
        "metrics": metrics,
    }


def run_invocation(
    pi_executable: Path, model_arg: str, session_id: str, prompt: str, timeout: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    started = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.run(
            bwrap_command(pi_executable, model_arg, session_id, prompt),
            text=True, capture_output=True, timeout=timeout,
        )
        returncode, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = -1
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
    wall_s = time.monotonic() - started
    if sha256_bytes((AGENT_DIR / "prompt_attestor.ts").read_bytes()) != sha256_bytes(ATTESTOR.read_bytes()):
        raise RuntimeError("session modified its read-only prompt attestor")
    return parse_events(stdout), {
        "returncode": returncode,
        "timed_out": timed_out,
        "wall_s": wall_s,
        "stdout_sha256": sha256_bytes(stdout.encode()),
        "stderr_sha256": sha256_bytes(stderr.encode()),
    }


def verify_attestation(expected_invocations: int, model_arg: str, scenario_id: str) -> str:
    hashes_path = OUTPUT_DIR / "system-prompt-sha256.txt"
    hashes = hashes_path.read_text().splitlines() if hashes_path.is_file() else []
    if len(hashes) != expected_invocations or len(set(hashes)) != 1:
        raise RuntimeError(
            f"effective system prompt was not stable for {model_arg}/{scenario_id}: {hashes}"
        )
    if hashes[0] != EXPECTED_SYSTEM_PROMPT_SHA256:
        raise RuntimeError(
            f"effective system prompt drifted for {model_arg}/{scenario_id}: {hashes[0]}"
        )
    return hashes[0]


def run_scenario(
    pi_executable: Path, model_arg: str, scenario: Scenario, repeat: int, timeout: int,
) -> dict[str, Any]:
    reset_paths(scenario)
    session_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"pibench:{PROFILE}:{model_arg}:{scenario.scenario_id}:{repeat}"))
    setup_result = None
    if scenario.context_preamble is not None:
        setup_events, setup_process = run_invocation(
            pi_executable, model_arg, session_id, scenario.context_preamble, timeout,
        )
        setup_result = analyze_events(
            setup_events, setup_process["returncode"], setup_process["timed_out"],
            setup_process["wall_s"], lambda text: {"exact_ready": text.strip() == "READY"}, 1,
        )
        setup_result["stdout_sha256"] = setup_process["stdout_sha256"]
        setup_result["stderr_sha256"] = setup_process["stderr_sha256"]
        if not setup_result["passed"]:
            prompt_hash = verify_attestation(1, model_arg, scenario.scenario_id)
            return {
                "scenario": scenario.scenario_id,
                "repeat": repeat,
                "passed": False,
                "failed_phase": "context_setup",
                "system_prompt_sha256": prompt_hash,
                "context_setup": setup_result,
            }

    events, process = run_invocation(pi_executable, model_arg, session_id, scenario.prompt, timeout)
    result = analyze_events(
        events, process["returncode"], process["timed_out"], process["wall_s"], scenario.semantic_check,
    )
    result.update({
        "scenario": scenario.scenario_id,
        "repeat": repeat,
        "system_prompt_sha256": verify_attestation(
            2 if scenario.context_preamble is not None else 1, model_arg, scenario.scenario_id
        ),
        "stdout_sha256": process["stdout_sha256"],
        "stderr_sha256": process["stderr_sha256"],
    })
    if setup_result is not None:
        result["context_setup"] = setup_result
    return result


def git_commit() -> str | None:
    proc = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True, capture_output=True)
    return proc.stdout.strip() if proc.returncode == 0 else None


def run_model(
    pi_executable: Path, model_arg: str, timeout: int, repeats: int,
    scenarios: tuple[Scenario, ...],
) -> dict[str, Any]:
    write_isolated_agent(model_arg)
    results = [
        run_scenario(pi_executable, model_arg, scenario, repeat, timeout)
        for scenario in scenarios for repeat in range(1, repeats + 1)
    ]
    return {
        "model": model_arg,
        "passed": all(result["passed"] for result in results),
        "classification": "qualified" if all(result["passed"] for result in results) else "not-qualified",
        "scenarios_passed": sum(result["passed"] for result in results),
        "scenarios_total": len(results),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("models", nargs="+", help="configured loopback Pi model arguments")
    parser.add_argument("--timeout", type=int, default=120, help="per-invocation timeout")
    parser.add_argument("--repeats", type=int, default=2, help="fresh-session repeats per scenario")
    parser.add_argument("--scenario", action="append", choices=[item.scenario_id for item in SCENARIOS])
    parser.add_argument("--output", type=Path, help="private JSON output path")
    args = parser.parse_args()
    if args.timeout < 10:
        parser.error("--timeout must be at least 10 seconds")
    if args.repeats < 1:
        parser.error("--repeats must be positive")
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
    selected_ids = set(args.scenario or [item.scenario_id for item in SCENARIOS])
    scenarios = tuple(item for item in SCENARIOS if item.scenario_id in selected_ids)

    LOCK_PATH.touch(mode=0o600, exist_ok=True)
    with LOCK_PATH.open("r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        results = [run_model(pi_executable, model, args.timeout, args.repeats, scenarios) for model in args.models]

    payload = {
        "profile": PROFILE,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pi_version": version,
        "pibench_commit": git_commit(),
        "attestor_sha256": sha256_bytes(ATTESTOR.read_bytes()),
        "system_prompt_sha256": EXPECTED_SYSTEM_PROMPT_SHA256,
        "scenario_prompt_sha256": {
            item.scenario_id: sha256_bytes(item.prompt.encode()) for item in scenarios
        },
        "context_preamble_sha256": {
            item.scenario_id: sha256_bytes(item.context_preamble.encode())
            for item in scenarios if item.context_preamble is not None
        },
        "repeats": args.repeats,
        "limits": {
            "timeout_s": args.timeout,
            "max_tool_calls": MAX_TOOL_CALLS,
            "max_assistant_messages": MAX_ASSISTANT_MESSAGES,
            "max_identical_tool_uses": MAX_IDENTICAL_TOOL_USES,
            "max_identical_line_uses": MAX_IDENTICAL_LINE_USES,
            "max_text_24gram_uses": MAX_TEXT_24GRAM_USES,
        },
        "results": results,
    }
    output = args.output or ROOT / "results" / f"pi_reliability_{time.strftime('%Y%m%d-%H%M%S')}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=output.parent, prefix=output.name + ".", delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    os.chmod(temporary, 0o600)
    temporary.replace(output)

    print(f"profile={PROFILE} system_prompt_sha256={EXPECTED_SYSTEM_PROMPT_SHA256}")
    for result in results:
        print(
            f"{result['model']}: {result['classification']} "
            f"({result['scenarios_passed']}/{result['scenarios_total']} scenario-runs passed)"
        )
        for scenario in result["results"]:
            if not scenario["passed"]:
                print(
                    f"  FAIL {scenario['scenario']} repeat={scenario['repeat']} "
                    f"gates={','.join(scenario.get('failed_gates', [scenario.get('failed_phase', 'unknown')]))}"
                )
    print(f"wrote {output}")
    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
