#!/usr/bin/env python3
"""Benchmark models through the Pi CLI.

This benchmark exercises the same user-facing path as an interactive Pi session:
model resolution, provider integration, prompting, and response rendering. It is
intended for comparing local and cloud models configured in Pi.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from pibench_db import (
    attach_model_to_run,
    connect,
    create_run,
    finish_run,
    insert_result,
    upsert_model,
    upsert_task,
    utc_now,
)

ROOT = Path(__file__).resolve().parent
OUTDIR = ROOT / "results"
OUTDIR.mkdir(exist_ok=True)

DEFAULT_MODELS = [
    "local-llama/Qwen3.6-35B-A3B-APEX-MTP-Compact:off",
    "openai-codex/gpt-5.5:medium",
]

MODEL_PRESETS = {
    "baseline": DEFAULT_MODELS,
    "requested-cloud": [
        "openai-codex/gpt-5.4:medium",
        "openai-codex/gpt-5.5:medium",
        "openai-codex/gpt-5.5:high",
    ],
    "qwen-thinking": [
        "local-llama/Qwen3.6-35B-A3B-APEX-MTP-Compact:off",
        "local-llama/Qwen3.6-35B-A3B-APEX-MTP-Compact:medium",
    ],
    "article": [
        "local-llama-q4-64k/Qwen3.6-35B-A3B-MTP-UD-Q4_K_M-ctx64k:off",
        "local-llama-gemma-nomtp/gemma-4-26B-A4B-it-UD-Q4_K_XL-nomtp:off",
        "local-llama/Qwen3.6-35B-A3B-APEX-MTP-Quality:off",
        "local-llama/Qwen3.6-35B-A3B-APEX-MTP-Compact:off",
        "local-llama/Qwen3.6-35B-A3B-APEX-MTP-Compact:medium",
        "local-llama/Qwen3.6-35B-A3B-Uncensored-Genesis-MTP-APEX-Compact:off",
        "local-llama-nomtp/Qwen3.6-35B-A3B-Uncensored-Genesis-APEX-Compact:off",
        "openai-codex/gpt-5.4:medium",
        "openai-codex/gpt-5.5:medium",
        "openai-codex/gpt-5.5:high",
    ],
    # Enable this after the GGUF is downloaded and registered in Pi's local-llama provider.
    "genesis-local": [
        "local-llama/Qwen3.6-35B-A3B-Uncensored-Genesis-MTP-APEX-Compact:off",
        "local-llama/Qwen3.6-35B-A3B-Uncensored-Genesis-MTP-APEX-Compact:medium",
        "local-llama-nomtp/Qwen3.6-35B-A3B-Uncensored-Genesis-APEX-Compact:off",
    ],
    "genesis-mtp-comparison": [
        "local-llama/Qwen3.6-35B-A3B-Uncensored-Genesis-MTP-APEX-Compact:off",
        "local-llama-nomtp/Qwen3.6-35B-A3B-Uncensored-Genesis-APEX-Compact:off",
    ],
    "qwen35-quant-comparison": [
        "local-llama/Qwen3.6-35B-A3B-MTP-UD-Q3_K_M:off",
        "local-llama-q4-64k/Qwen3.6-35B-A3B-MTP-UD-Q4_K_M-ctx64k:off",
        "local-llama/Qwen3.6-35B-A3B-APEX-MTP-Quality:off",
        "local-llama/Qwen3.6-35B-A3B-APEX-MTP-Compact:off",
        "local-llama/Qwen3.6-35B-A3B-Uncensored-Genesis-MTP-APEX-Compact:off",
    ],
}

TASKS = [
    {
        "name": "json_exact",
        "prompt": 'Return only valid minified JSON with keys "name" and "nums". name must be "pi" and nums must be [3,1,4]. No markdown.',
        "check": "json_exact",
    },
    {
        "name": "dedupe_function",
        "prompt": "Return only Python code defining function dedupe_keep_order(xs) that removes duplicates while preserving order. No markdown.",
        "check": "dedupe_exec",
    },
    {
        "name": "parse_ints_function",
        "prompt": "Return only Python code defining function parse_ints(s) that returns all signed integers appearing in a string, e.g. 'a-2 b 10' -> [-2, 10]. No markdown.",
        "check": "parse_ints_exec",
    },
    {
        "name": "interval_merge_edgecases",
        "prompt": "Return only Python code defining merge_intervals(intervals). Input is a list of (start,end) pairs, possibly unsorted, overlapping, touching, negative, duplicated, or reversed. Return merged [start,end] lists sorted by start. Touching intervals merge. No markdown.",
        "check": "merge_intervals_exec",
    },
    {
        "name": "toposort_cycle",
        "prompt": "Return only Python code defining topo_sort(nodes, edges). nodes is an iterable of node names. edges is iterable of (before, after). Return a valid topological ordering list containing all nodes. If there is a cycle, raise ValueError. Include nodes that have no edges. No markdown.",
        "check": "toposort_exec",
    },
    {
        "name": "nginx_reverse_proxy",
        "prompt": "Return only an nginx server block, no markdown. Requirements: listen 443 ssl http2 for example.com; redirect HTTP to HTTPS; reverse proxy / to http://127.0.0.1:3000; set Host/X-Real-IP/X-Forwarded-For/X-Forwarded-Proto headers; websocket Upgrade support; gzip static assets; cache-control for /assets/; deny hidden files; include reasonable TLS directives.",
        "check": "nginx_static",
    },
    {
        "name": "webui_todo_static",
        "prompt": "Build a polished single-file web app. Return only complete HTML, no markdown. App: Todo manager. Requirements: responsive layout, CSS styling, add todo, delete todo, mark complete, filters All/Active/Completed, persist todos in localStorage, empty-state message, keyboard friendly form, no external dependencies.",
        "check": "todo_static",
    },
    {
        "name": "lru_cache_hard",
        "prompt": "Return only Python code defining class LRUCache. Constructor LRUCache(capacity). Methods get(key) returns value or -1; put(key,value) inserts/updates. Evict least-recently-used item when over capacity. get and put must both update recency. Capacity may be zero. Do not use external dependencies. No markdown.",
        "check": "lru_cache_exec",
    },
    {
        "name": "json_path_set_hard",
        "prompt": "Return only Python code defining function set_path(obj, path, value). path is a dotted/bracket path like 'a.b[0].c' or 'items[2]'. Mutate and return obj. Create missing dicts/lists as needed, extend lists with None, preserve existing containers, and raise ValueError on malformed paths. No markdown.",
        "check": "json_path_set_exec",
    },
    {
        "name": "rate_limiter_hard",
        "prompt": "Return only Python code defining class SlidingWindowRateLimiter. Constructor SlidingWindowRateLimiter(limit, window_seconds). Method allow(user_id, timestamp) returns True if the request is allowed, False otherwise. Allow at most limit requests per user in any sliding window of window_seconds. Timestamps are numeric and nondecreasing per user is not guaranteed. Keep independent state per user. No markdown.",
        "check": "rate_limiter_exec",
    },
    {
        "name": "unified_diff_hard",
        "prompt": "Return only Python code defining function apply_unified_diff(text, patch). text is a string. patch is a standard unified diff string with ---/+++ headers and @@ -a,b +c,d @@ hunks. Apply removals, additions, and context lines. Return the patched text. Raise ValueError if context/removal lines do not match. No markdown.",
        "check": "unified_diff_exec",
    },
    {
        "name": "csv_infer_hard",
        "prompt": "Return only Python code defining function infer_csv_schema(csv_text). Parse CSV with headers using Python standard library. Return a dict mapping column name to one of: int, float, bool, date, string. Empty cells are ignored for inference. bool accepts true/false/yes/no/1/0 case-insensitively. date accepts YYYY-MM-DD. int must not classify floats. No markdown.",
        "check": "csv_infer_exec",
    },
    {
        "name": "retry_schedule_hard",
        "prompt": "Return only Python code defining function retry_schedule(base_delay, factor, max_delay, attempts, jitter=None). Return a list of delays for retry attempts. Delay i is min(max_delay, base_delay * factor**i). attempts may be 0. If jitter is a number between 0 and 1, return (low, high) tuples where low=delay*(1-jitter), high=delay*(1+jitter), capped so high<=max_delay. Validate inputs and raise ValueError for invalid ones. No markdown.",
        "check": "retry_schedule_exec",
    },
    {
        "name": "semver_range_hard",
        "prompt": "Return only Python code defining function satisfies(version, constraint). version is semantic version MAJOR.MINOR.PATCH. constraint supports comma-separated AND clauses using operators ==, !=, >, >=, <, <= and compatible-release ~= such as '~=1.4' meaning >=1.4.0 and <2.0.0, or '~=1.4.5' meaning >=1.4.5 and <1.5.0. Ignore pre-release/build metadata. Raise ValueError for malformed input. No markdown.",
        "check": "semver_range_exec",
    },
    {
        "name": "markdown_table_hard",
        "prompt": "Return only Python code defining function parse_markdown_table(md). Parse the first GitHub-style markdown table in md and return a list of dicts keyed by header. Trim whitespace, support escaped pipe characters \\| inside cells, ignore alignment row, and raise ValueError if no valid table exists. No markdown.",
        "check": "markdown_table_exec",
    },
    {
        "name": "text_wrap_hard",
        "prompt": "Return only Python code defining function wrap_text(text, width, indent=0). Wrap paragraphs to at most width characters, preserving blank lines between paragraphs. Do not break words longer than width. Apply indent spaces to every output line, and account for indent in width. Raise ValueError for invalid width or indent. No markdown.",
        "check": "text_wrap_exec",
    },

    {
        "name": "systemd_service_hard",
        "prompt": "Return only a production-ready systemd service unit file, no markdown. Scenario: deploy a Python FastAPI app named inventory-api from /opt/inventory-api using virtualenv /opt/inventory-api/.venv, module inventory.main:app on 127.0.0.1:9000. Requirements: run as non-root user inventory, restart on failure, load EnvironmentFile /etc/inventory-api.env, set WorkingDirectory, use ExecStart, install for multi-user.target, include practical hardening without breaking network access.",
        "check": "systemd_service_static",
    },
    {
        "name": "nginx_tls_proxy_hard",
        "prompt": "Return only nginx configuration, no markdown. Scenario: example.com should redirect HTTP to HTTPS and proxy HTTPS traffic to http://127.0.0.1:9000. Requirements: listen 80 and 443 ssl http2, server_name example.com, WebSocket support, X-Forwarded-* and Host headers, TLS protocols/ciphers, HSTS, gzip for static responses, /assets/ cache headers, deny dotfiles, and safe client body size.",
        "check": "nginx_tls_proxy_static",
    },
    {
        "name": "log_triage_incident",
        "prompt": """Return only a concise incident triage report with sections: Summary, Evidence, Immediate Mitigation, Prevention. Logs:
2026-05-30T10:01:12Z api-1 inventory-api[2211]: accepted connection from 10.0.2.41
2026-05-30T10:01:19Z api-1 inventory-api[2211]: ERROR sqlite3.OperationalError: database is locked
2026-05-30T10:01:22Z api-1 inventory-api[2211]: request timeout POST /orders
2026-05-30T10:01:24Z api-1 kernel: Out of memory: Killed process 2211 (python) total-vm:2841020kB, anon-rss:1782040kB
2026-05-30T10:01:24Z api-1 systemd[1]: inventory-api.service: Main process exited, code=killed, status=9/KILL
2026-05-30T10:01:29Z api-1 systemd[1]: inventory-api.service: Scheduled restart job, restart counter is at 5
2026-05-30T10:01:29Z api-1 nginx[997]: connect() failed (111: Connection refused) while connecting to upstream, client: 203.0.113.7, request: POST /orders, upstream: http://127.0.0.1:9000/orders
Identify the primary root cause and do not invent services not shown.""",
        "check": "log_triage_static",
    },
    {
        "name": "readme_quickstart_rewrite",
        "prompt": "Return only a polished README Quickstart section in Markdown, no surrounding commentary. Project notes: name=PiBench; purpose=benchmark local and cloud LLMs through Pi CLI and llama.cpp; Python 3.11+; install with git clone then python -m venv .venv and pip install -r requirements.txt; run local benchmark with ./pi_agent_bench.py --model-preset baseline; generate report with ./pibench_report.py; SQLite database lives at results/pibench.sqlite and is gitignored; JSON/Markdown results are written to results/; config requires Pi models to be registered first. Include prerequisites, installation, running a benchmark, generating reports, outputs, and troubleshooting.",
        "check": "readme_quickstart_static",
    },
    {
        "name": "changelog_from_commits",
        "prompt": "Return only Keep a Changelog style release notes for version 0.3.0, no markdown fences. Commit messages: feat: add SQLite benchmark database; feat: add weighted normalized reporting; fix: count timeout rows as zero scored tasks; docs: add model preset guide; chore: reorder imports; feat: add Gemma non-MTP runtime comparison; fix: sanitize temporary traceback paths; perf: add Q4_K_M 64K context benchmark; breaking: rename project from pi-local-model-bench to PiBench. Group into Added, Changed, Fixed, and Breaking Changes. Omit noise.",
        "check": "changelog_static",
    },
    {
        "name": "github_issue_triage",
        "prompt": "Return only valid JSON. Triage these issues into an array under key issues. Each item must contain id, type, priority, and action. Types allowed: bug, feature, question, duplicate, invalid. Priorities allowed: P0, P1, P2, P3. Issues: #101 app crashes on startup after latest release, traceback shows missing config key; #102 please add dark mode; #103 how do I run with local models only?; #104 same as #101, startup crash missing config key; #105 benchmark result is wrong but no logs or reproduction; #106 security: report files include absolute local temp paths; #107 generated report should show context window; #108 production service down for all users after deploy. Mark #104 as duplicate of #101 in action.",
        "check": "github_issue_triage_static",
    },
    {
        "name": "architecture_decision_record",
        "prompt": "Return only an Architecture Decision Record in Markdown. Scenario: PiBench needs to store repeatable benchmark results, model metadata, task scores, raw stdout/stderr, and generate reports. Constraints: single-user local tool, no external service dependency, database file must remain gitignored, easy export to JSON/Markdown, should support joins for normalized reports. Alternatives to compare: SQLite, Postgres, flat JSON files. Choose the best option and explain consequences. Include Status, Context, Decision, Alternatives, Consequences.",
        "check": "adr_static",
    },
    {
        "name": "design_review_find_flaws",
        "prompt": "Return only a concise design review with sections: Critical Issues, Recommended Changes, Observability. Proposed design: A public web dashboard accepts benchmark uploads anonymously, stores raw stdout/stderr in S3, writes metadata directly from the browser to Postgres using an admin API key embedded in JavaScript, uses one VM with local disk for the database, has no rate limiting because uploads are small, and compares model scores without storing model context size or runtime configuration. Identify concrete flaws and fixes.",
        "check": "design_review_static",
    },
]


TASK_WEIGHTS = {
    # Smoke / instruction-following checks.
    "json_exact": 0.5,
    "dedupe_function": 1.0,
    "parse_ints_function": 1.0,
    # Medium algorithmic/static checks.
    "interval_merge_edgecases": 2.0,
    "toposort_cycle": 2.5,
    "nginx_reverse_proxy": 2.0,
    "webui_todo_static": 2.0,
    # Hard deterministic coding tasks.
    "lru_cache_hard": 3.0,
    "json_path_set_hard": 4.0,
    "rate_limiter_hard": 3.5,
    "unified_diff_hard": 4.5,
    "csv_infer_hard": 3.5,
    "retry_schedule_hard": 3.0,
    "semver_range_hard": 4.0,
    "markdown_table_hard": 3.5,
    "text_wrap_hard": 3.0,
    # Non-coding agent work: ops, documentation, planning, architecture.
    "systemd_service_hard": 3.0,
    "nginx_tls_proxy_hard": 3.0,
    "log_triage_incident": 2.5,
    "readme_quickstart_rewrite": 2.0,
    "changelog_from_commits": 2.0,
    "github_issue_triage": 2.5,
    "architecture_decision_record": 3.5,
    "design_review_find_flaws": 3.5,
}

TASK_DIFFICULTY = {
    name: ("easy" if weight <= 1.0 else "medium" if weight <= 2.5 else "hard" if weight <= 3.5 else "expert")
    for name, weight in TASK_WEIGHTS.items()
}

CHECK_TOTALS = {
    "unified_diff_exec": 3,
    "csv_infer_exec": 3,
    "retry_schedule_exec": 3,
    "semver_range_exec": 4,
    "markdown_table_exec": 4,
    "text_wrap_exec": 4,
    "systemd_service_static": 8,
    "nginx_tls_proxy_static": 9,
    "log_triage_static": 7,
    "readme_quickstart_static": 7,
    "changelog_static": 6,
    "github_issue_triage_static": 8,
    "adr_static": 7,
    "design_review_static": 8,
}


def task_weight(name: str) -> float:
    return TASK_WEIGHTS.get(name, 1.0)


def approx_tokens(text: str) -> int:
    # Same rough heuristic Pi uses in compaction fallback; useful for cross-provider
    # latency comparison when provider token usage is not exposed by the CLI.
    return max(1, (len(text) + 3) // 4)


def clean_fenced(text: str) -> str:
    text = text.strip()
    match = re.search(r"```(?:python|html|nginx|conf|json|markdown|md)?\s*(.*?)```", text, flags=re.S | re.I)
    if match:
        return match.group(1).strip()
    return re.sub(r"^```(?:\w+)?\s*", "", text, flags=re.I).strip()


def scored_static(checks: dict[str, bool]) -> tuple[bool, str, dict]:
    score = sum(1 for ok in checks.values() if ok)
    total = len(checks)
    failed = [name for name, ok in checks.items() if not ok]
    detail = f"score {score}/{total}" if not failed else f"score {score}/{total} failed: " + ", ".join(failed)
    return score == total, detail, {"score": score, "total": total, "failed": failed, **checks}


def has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def sanitize_tracebacks(text: str) -> str:
    return re.sub(r"/tmp/tmp[^/]+/submission\.py", "<tmp>/submission.py", text)


def run_python_submission(code: str, tests: str, timeout: int = 8) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "submission.py"
        path.write_text(code + "\n\n" + tests)
        proc = subprocess.run(["python3", str(path)], text=True, capture_output=True, timeout=timeout)
        return proc.returncode == 0, sanitize_tracebacks((proc.stdout + proc.stderr)[-1200:])


def run_python_scored(code: str, tests: str, timeout: int = 8) -> tuple[bool, str, dict]:
    harness = r'''
import json, traceback
passed = 0
failed = []
for name, fn in TESTS:
    try:
        fn()
        passed += 1
    except Exception:
        failed.append({"name": name, "traceback": traceback.format_exc(limit=4)})
print("PIBENCH_SCORE " + json.dumps({"score": passed, "total": len(TESTS), "failed": failed}, sort_keys=True))
raise SystemExit(0 if passed == len(TESTS) else 1)
'''
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "submission.py"
        path.write_text(code + "\n\n" + tests + "\n\n" + harness)
        proc = subprocess.run(["python3", str(path)], text=True, capture_output=True, timeout=timeout)
        output = sanitize_tracebacks(proc.stdout + proc.stderr)
        match = re.search(r"PIBENCH_SCORE (\{.*\})", output)
        checks = json.loads(match.group(1)) if match else {"score": 0, "total": 0, "failed": [{"name": "harness", "traceback": output[-1200:]}]}
        failed_names = [f["name"] for f in checks.get("failed", [])]
        detail = f"score {checks.get('score', 0)}/{checks.get('total', 0)}" if not failed_names else f"score {checks.get('score', 0)}/{checks.get('total', 0)} failed: " + ", ".join(failed_names)
        return proc.returncode == 0, detail, checks


def check_result(kind: str, text: str) -> tuple[bool, str, dict]:
    body = clean_fenced(text)
    if kind == "json_exact":
        try:
            ok = json.loads(body) == {"name": "pi", "nums": [3, 1, 4]}
            return ok, "json parsed" if ok else "json value mismatch", {}
        except Exception as exc:
            return False, f"json error: {exc}", {}

    if kind == "dedupe_exec":
        tests = """
f = dedupe_keep_order
assert f([1, 2, 1, 3, 2, 4]) == [1, 2, 3, 4]
assert f([\"a\", \"a\", \"b\"]) == [\"a\", \"b\"]
assert f([]) == []
print('ok')
"""
        ok, detail = run_python_submission(body, tests)
        return ok, "exec check" if ok else detail, {}

    if kind == "parse_ints_exec":
        tests = """
f = parse_ints
assert f('a-2 b 10 +7 x0') == [-2, 10, 7, 0]
assert f('none') == []
assert f('--5') in ([-5], [5])
print('ok')
"""
        ok, detail = run_python_submission(body, tests)
        return ok, "exec check" if ok else detail, {}

    if kind == "merge_intervals_exec":
        tests = """
assert merge_intervals([]) == []
assert merge_intervals([(1,3),(2,4),(10,11),(4,5)]) == [[1,5],[10,11]]
assert merge_intervals([(5,5),(1,2),(2,2),(-3,-1),(-2,0)]) == [[-3,0],[1,2],[5,5]]
assert merge_intervals([(3,1),(2,4)]) == [[1,4]]
print('ok')
"""
        ok, detail = run_python_submission(body, tests)
        return ok, "exec check" if ok else detail, {}

    if kind == "toposort_exec":
        tests = """
def valid(order, nodes, edges):
    assert set(order) == set(nodes) and len(order) == len(nodes)
    pos = {x: i for i, x in enumerate(order)}
    assert all(pos[a] < pos[b] for a, b in edges)
valid(topo_sort(['a','b','c','d'], [('a','c'),('b','c')]), ['a','b','c','d'], [('a','c'),('b','c')])
valid(topo_sort(['x'], []), ['x'], [])
try:
    topo_sort(['a','b'], [('a','b'),('b','a')])
    raise AssertionError('cycle not detected')
except ValueError:
    pass
print('ok')
"""
        ok, detail = run_python_submission(body, tests)
        return ok, "exec check" if ok else detail, {}

    if kind == "lru_cache_exec":
        tests = """
c = LRUCache(2)
c.put('a', 1); c.put('b', 2)
assert c.get('a') == 1
c.put('c', 3)
assert c.get('b') == -1 and c.get('a') == 1 and c.get('c') == 3
c.put('a', 10)
c.put('d', 4)
assert c.get('c') == -1 and c.get('a') == 10 and c.get('d') == 4
z = LRUCache(0)
z.put('x', 1)
assert z.get('x') == -1
one = LRUCache(1)
one.put('x', 1); one.put('x', 2)
assert one.get('x') == 2
print('ok')
"""
        ok, detail = run_python_submission(body, tests)
        return ok, "exec check" if ok else detail, {}

    if kind == "json_path_set_exec":
        tests = r'''
o = {}
assert set_path(o, 'a.b[0].c', 7) is o
assert o == {'a': {'b': [{'c': 7}]}}
set_path(o, 'a.b[2]', 'x')
assert o['a']['b'] == [{'c': 7}, None, 'x']
o2 = {'items': [{'name': 'old'}]}
set_path(o2, 'items[0].name', 'new')
assert o2 == {'items': [{'name': 'new'}]}
set_path(o2, 'items[1].tags[0]', 'pi')
assert o2['items'][1]['tags'] == ['pi']
for bad in ['', 'a..b', 'a[', 'a[-1]', '[0]']:
    try:
        set_path({}, bad, 1)
        raise AssertionError('did not reject ' + repr(bad))
    except ValueError:
        pass
print('ok')
'''
        ok, detail = run_python_submission(body, tests)
        return ok, "exec check" if ok else detail, {}

    if kind == "rate_limiter_exec":
        tests = """
rl = SlidingWindowRateLimiter(2, 10)
assert rl.allow('u', 100.0) is True
assert rl.allow('u', 101.0) is True
assert rl.allow('u', 102.0) is False
assert rl.allow('v', 102.0) is True
assert rl.allow('u', 110.0) is True  # 100.0 has expired for [100,110]
assert rl.allow('u', 109.0) is False # out-of-order timestamp still sees 101 and 110 in window
rl2 = SlidingWindowRateLimiter(1, 5)
assert rl2.allow('a', 0) is True
assert rl2.allow('a', 4.999) is False
assert rl2.allow('a', 5) is True
print('ok')
"""
        ok, detail = run_python_submission(body, tests)
        return ok, "exec check" if ok else detail, {}

    if kind == "unified_diff_exec":
        tests = r'''
def t_basic():
    text = "a\nb\nc\n"
    patch = "--- old\n+++ new\n@@ -1,3 +1,4 @@\n a\n-b\n+B\n c\n+d\n"
    assert apply_unified_diff(text, patch) == "a\nB\nc\nd\n"

def t_multiple_hunks():
    text = "one\ntwo\nthree\nfour\nfive\n"
    patch = "--- a\n+++ b\n@@ -1,2 +1,2 @@\n one\n-two\n+TWO\n@@ -4,2 +4,3 @@\n four\n five\n+six\n"
    assert apply_unified_diff(text, patch) == "one\nTWO\nthree\nfour\nfive\nsix\n"

def t_bad_context():
    try:
        apply_unified_diff("x\ny\n", "--- a\n+++ b\n@@ -1,2 +1,2 @@\n z\n-y\n+Y\n")
        raise AssertionError("accepted wrong context")
    except ValueError:
        pass

TESTS = [("basic", t_basic), ("multiple_hunks", t_multiple_hunks), ("bad_context", t_bad_context)]
'''
        return run_python_scored(body, tests)

    if kind == "csv_infer_exec":
        tests = r'''
def t_mixed_schema():
    csv_text = "id,price,active,joined,name\n1,3.50,true,2024-01-02,Ada\n2,,NO,2024-12-31,Bob\n3,7,1,,Carol\n"
    assert infer_csv_schema(csv_text) == {"id": "int", "price": "float", "active": "bool", "joined": "date", "name": "string"}

def t_int_not_float_and_empty():
    csv_text = "a,b,c\n001,,hello\n-2,,world\n"
    assert infer_csv_schema(csv_text) == {"a": "int", "b": "string", "c": "string"}

def t_quoted_commas():
    csv_text = 'name,ok,amount\n"Smith, Ann",yes,10\n"Jones",false,11.25\n'
    assert infer_csv_schema(csv_text) == {"name": "string", "ok": "bool", "amount": "float"}

TESTS = [("mixed_schema", t_mixed_schema), ("int_empty", t_int_not_float_and_empty), ("quoted_commas", t_quoted_commas)]
'''
        return run_python_scored(body, tests)

    if kind == "retry_schedule_exec":
        tests = r'''
def t_plain():
    assert retry_schedule(1, 2, 10, 5) == [1, 2, 4, 8, 10]
    assert retry_schedule(0.5, 3, 4, 4) == [0.5, 1.5, 4, 4]
    assert retry_schedule(1, 2, 10, 0) == []

def t_jitter():
    got = retry_schedule(10, 2, 25, 3, jitter=0.1)
    assert got == [(9.0, 11.0), (18.0, 22.0), (22.5, 25)]

def t_invalid():
    bad_args = [(0,2,10,1), (1,0,10,1), (1,2,0,1), (1,2,10,-1), (1,2,10,1,-0.1), (1,2,10,1,1.1)]
    for args in bad_args:
        try:
            retry_schedule(*args)
            raise AssertionError("accepted " + repr(args))
        except ValueError:
            pass

TESTS = [("plain", t_plain), ("jitter", t_jitter), ("invalid", t_invalid)]
'''
        return run_python_scored(body, tests)

    if kind == "semver_range_exec":
        tests = r'''
def t_basic_ops():
    assert satisfies("1.2.3", ">=1.0.0, <2.0.0") is True
    assert satisfies("2.0.0", ">=1.0.0, <2.0.0") is False
    assert satisfies("1.2.3+build.7", "==1.2.3") is True
    assert satisfies("1.2.3-alpha", "==1.2.3") is True

def t_not_equal_and_edges():
    assert satisfies("1.2.3", "!=1.2.4") is True
    assert satisfies("1.2.3", "!=1.2.3") is False
    assert satisfies("1.2.3", ">1.2.2, <=1.2.3") is True

def t_compatible_release():
    assert satisfies("1.4.0", "~=1.4") is True
    assert satisfies("1.9.9", "~=1.4") is True
    assert satisfies("2.0.0", "~=1.4") is False
    assert satisfies("1.4.5", "~=1.4.5") is True
    assert satisfies("1.5.0", "~=1.4.5") is False

def t_invalid():
    for version, constraint in [("1.2", ">=1.0.0"), ("1.2.3", ">>1.0.0"), ("1.2.3", "~=1"), ("x", "==1.0.0")]:
        try:
            satisfies(version, constraint)
            raise AssertionError("accepted invalid input")
        except ValueError:
            pass

TESTS = [("basic_ops", t_basic_ops), ("not_equal_edges", t_not_equal_and_edges), ("compatible", t_compatible_release), ("invalid", t_invalid)]
'''
        return run_python_scored(body, tests)

    if kind == "markdown_table_exec":
        tests = r'''
def t_basic():
    md = "intro\n\n| name | age |\n| --- | ---: |\n| Ada | 36 |\n| Bob | 40 |\n"
    assert parse_markdown_table(md) == [{"name": "Ada", "age": "36"}, {"name": "Bob", "age": "40"}]

def t_escaped_pipes():
    md = "| key | value |\n|---|---|\n| a | one \\| two |\n| b | x |\n"
    assert parse_markdown_table(md)[0] == {"key": "a", "value": "one | two"}

def t_first_valid_table():
    md = "|not|table|\nplain\n\n| h |\n| - |\n| c |\n"
    assert parse_markdown_table(md) == [{"h": "c"}]

def t_invalid():
    for md in ["", "| a | b |\n| c | d |\n", "no table"]:
        try:
            parse_markdown_table(md)
            raise AssertionError("accepted invalid table")
        except ValueError:
            pass

TESTS = [("basic", t_basic), ("escaped_pipes", t_escaped_pipes), ("first_valid", t_first_valid_table), ("invalid", t_invalid)]
'''
        return run_python_scored(body, tests)

    if kind == "text_wrap_exec":
        tests = r'''
def assert_width(s, width):
    for line in s.splitlines():
        assert len(line) <= width or len(line.strip()) > width

def t_basic():
    out = wrap_text("alpha beta gamma delta", 12)
    assert out == "alpha beta\ngamma delta"
    assert_width(out, 12)

def t_paragraphs_indent():
    out = wrap_text("one two three\n\nfour five six", 10, indent=2)
    assert out == "  one two\n  three\n\n  four\n  five six"
    assert_width(out, 10)

def t_long_word():
    out = wrap_text("short supercalifragilistic tiny", 10)
    assert "supercalifragilistic" in out
    assert_width(out, 10)

def t_invalid():
    for args in [("x", 0), ("x", 4, -1), ("x", 4, 4)]:
        try:
            wrap_text(*args)
            raise AssertionError("accepted invalid args")
        except ValueError:
            pass

TESTS = [("basic", t_basic), ("paragraphs_indent", t_paragraphs_indent), ("long_word", t_long_word), ("invalid", t_invalid)]
'''
        return run_python_scored(body, tests)

    static_kinds = {
        "nginx_static",
        "todo_static",
        "systemd_service_static",
        "nginx_tls_proxy_static",
        "log_triage_static",
        "readme_quickstart_static",
        "changelog_static",
        "github_issue_triage_static",
        "adr_static",
        "design_review_static",
    }
    if kind in static_kinds:
        body = text.strip()
    lowered = body.lower()
    if kind == "nginx_static":
        checks = {
            "listen_443": "listen 443" in lowered and "ssl" in lowered,
            "listen_80_redirect": "listen 80" in lowered and "return 301" in lowered,
            "server_name": "server_name example.com" in lowered,
            "proxy_pass": "proxy_pass http://127.0.0.1:3000" in lowered,
            "headers": all(x in lowered for x in ["x-real-ip", "x-forwarded-for", "x-forwarded-proto"]),
            "websocket": "upgrade" in lowered and "connection" in lowered,
            "gzip": "gzip on" in lowered,
            "assets_cache": "/assets/" in lowered and ("cache-control" in lowered or "expires" in lowered),
            "deny_hidden": "deny all" in lowered and ("/\\." in lowered or "hidden" in lowered),
            "tls": "ssl_protocols" in lowered or "ssl_ciphers" in lowered,
        }
        ok = all(checks.values())
        missing = [k for k, v in checks.items() if not v]
        return ok, "static check" if ok else "missing: " + ", ".join(missing), checks

    if kind == "todo_static":
        checks = {
            "html": "<html" in lowered and "</html>" in lowered,
            "style": "<style" in lowered and "</style>" in lowered,
            "script": "<script" in lowered and "</script>" in lowered,
            "localStorage": "localstorage" in lowered,
            "add": "add" in lowered,
            "delete": "delete" in lowered or "remove" in lowered,
            "completed": "completed" in lowered or "complete" in lowered,
            "filter": "filter" in lowered and "active" in lowered,
            "responsive": "@media" in lowered or "grid" in lowered or "flex" in lowered,
            "accessible_form": "<label" in lowered or "aria-" in lowered,
        }
        ok = all(checks.values())
        missing = [k for k, v in checks.items() if not v]
        return ok, "static check" if ok else "missing: " + ", ".join(missing), checks

    if kind == "systemd_service_static":
        checks = {
            "unit_sections": all(x in lowered for x in ["[unit]", "[service]", "[install]"]),
            "non_root_user": "user=inventory" in lowered and "user=root" not in lowered,
            "working_directory": "workingdirectory=/opt/inventory-api" in lowered.replace(" ", ""),
            "execstart_uvicorn": "execstart=" in lowered and "uvicorn" in lowered and "inventory.main:app" in lowered,
            "restart": "restart=on-failure" in lowered.replace(" ", ""),
            "environment_file": "environmentfile=/etc/inventory-api.env" in lowered.replace(" ", ""),
            "install_target": "wantedby=multi-user.target" in lowered.replace(" ", ""),
            "hardening": sum(1 for x in ["nonewprivileges", "privatetmp", "protectsystem", "protecthome", "readwritepaths"] if x in lowered.replace(" ", "")) >= 3,
        }
        return scored_static(checks)

    if kind == "nginx_tls_proxy_static":
        checks = {
            "http_redirect": "listen 80" in lowered and "return 301" in lowered and "https://" in lowered,
            "https_listener": "listen 443" in lowered and "ssl" in lowered and "http2" in lowered,
            "server_name": "server_name example.com" in lowered,
            "proxy_pass": "proxy_pass http://127.0.0.1:9000" in lowered,
            "proxy_headers": all(x in lowered for x in ["host", "x-real-ip", "x-forwarded-for", "x-forwarded-proto"]),
            "websocket": "upgrade" in lowered and "connection" in lowered,
            "tls_hsts": "ssl_protocols" in lowered and "strict-transport-security" in lowered,
            "assets_gzip_cache": "gzip" in lowered and "/assets/" in lowered and ("cache-control" in lowered or "expires" in lowered),
            "dotfiles_body_size": ("deny all" in lowered and ("/\\." in lowered or "dot" in lowered or "hidden" in lowered)) and "client_max_body_size" in lowered,
        }
        return scored_static(checks)

    if kind == "log_triage_static":
        checks = {
            "sections": all(x in lowered for x in ["summary", "evidence", "immediate", "prevention"]),
            "oom_root_cause": has_any(lowered, ["out of memory", "oom", "memory"]),
            "killed_python": "killed" in lowered and ("python" in lowered or "inventory-api" in lowered),
            "secondary_db_locked": "database is locked" in lowered or "sqlite" in lowered,
            "upstream_refused": "connection refused" in lowered or "upstream" in lowered,
            "mitigation": has_any(lowered, ["restart", "rollback", "scale", "memory limit", "reduce memory", "add memory"]),
            "prevention": has_any(lowered, ["monitor", "alert", "postgres", "connection pool", "memory profiling", "resource limits"]),
        }
        return scored_static(checks)

    if kind == "readme_quickstart_static":
        checks = {
            "title": "quickstart" in lowered,
            "prerequisites": "prerequisites" in lowered and "python 3.11" in lowered,
            "install": "git clone" in lowered and "venv" in lowered and "pip install" in lowered,
            "run_benchmark": "pi_agent_bench.py" in lowered and "--model-preset baseline" in lowered,
            "generate_report": "pibench_report.py" in lowered,
            "outputs": "results/" in lowered and "pibench.sqlite" in lowered and "gitignored" in lowered,
            "troubleshooting": "troubleshooting" in lowered and "model" in lowered,
        }
        return scored_static(checks)

    if kind == "changelog_static":
        checks = {
            "version": "0.3.0" in lowered,
            "added": "added" in lowered and "sqlite" in lowered and "weighted" in lowered,
            "changed": "changed" in lowered and "pibench" in lowered,
            "fixed": "fixed" in lowered and "timeout" in lowered and "traceback" in lowered,
            "breaking": "breaking" in lowered and "rename" in lowered,
            "omit_chore": "reorder imports" not in lowered,
        }
        return scored_static(checks)

    if kind == "github_issue_triage_static":
        compact = lowered.replace(" ", "")
        checks = {
            "json_object": body.strip().startswith("{") and "issues" in lowered,
            "all_ids": all(f"101" in lowered and f"{i}" in lowered for i in range(102, 109)),
            "p0_outage": "108" in lowered and "p0" in lowered,
            "duplicate": "104" in lowered and "duplicate" in lowered and "101" in lowered,
            "question": "103" in lowered and "question" in lowered,
            "invalid_missing_repro": "105" in lowered and "invalid" in lowered,
            "security_bug": "106" in lowered and ("bug" in lowered or "p1" in lowered or "security" in lowered),
            "feature_requests": all(x in lowered for x in ["102", "107", "feature"]),
        }
        return scored_static(checks)

    if kind == "adr_static":
        checks = {
            "sections": all(x in lowered for x in ["status", "context", "decision", "alternatives", "consequences"]),
            "chooses_sqlite": "sqlite" in lowered and has_any(lowered, ["choose", "chosen", "decision"]),
            "compares_postgres": "postgres" in lowered,
            "compares_json": "json" in lowered,
            "constraints": "single-user" in lowered and "no external" in lowered,
            "gitignored_export": "gitignored" in lowered and "export" in lowered,
            "tradeoffs": has_any(lowered, ["tradeoff", "trade-off", "limitation", "consequence"]),
        }
        return scored_static(checks)

    if kind == "design_review_static":
        checks = {
            "sections": all(x in lowered for x in ["critical", "recommended", "observability"]),
            "auth": has_any(lowered, ["anonymous", "authentication", "auth"]),
            "secret_exposure": "admin api key" in lowered or ("api key" in lowered and "javascript" in lowered),
            "raw_output_privacy": "stdout" in lowered and has_any(lowered, ["secret", "privacy", "redact", "sensitive"]),
            "rate_limiting": "rate limit" in lowered or "rate limiting" in lowered,
            "single_point_failure": "single" in lowered and has_any(lowered, ["failure", "vm", "disk"]),
            "runtime_metadata": "context" in lowered and has_any(lowered, ["runtime", "configuration", "metadata"]),
            "concrete_fixes": has_any(lowered, ["presigned", "least privilege", "server-side", "queue", "backup", "replica", "monitor"]),
        }
        return scored_static(checks)

    return False, "unknown check", {}


def run_pi(model: str, prompt: str, args: argparse.Namespace) -> dict:
    env = os.environ.copy()
    if args.offline:
        env["PI_OFFLINE"] = "1"
    elif "PI_OFFLINE" in env and not args.keep_env_offline:
        env.pop("PI_OFFLINE")

    cmd = [
        "pi",
        "--model", model,
        "--no-session",
        "--no-tools",
        "--no-context-files",
        "--no-skills",
        "--no-prompt-templates",
        "--no-themes",
        "-p", prompt,
    ]
    if not args.allow_extensions:
        cmd.insert(7, "--no-extensions")
    if args.system_prompt:
        cmd[1:1] = ["--system-prompt", args.system_prompt]

    start = time.time()
    proc = subprocess.run(cmd, text=True, capture_output=True, env=env, timeout=args.timeout)
    wall = time.time() - start
    return {
        "cmd": cmd,
        "wall_s": wall,
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark models through the Pi CLI")
    parser.add_argument("models", nargs="*", help="Pi model IDs, e.g. openai-codex/gpt-5.5:medium")
    parser.add_argument("--model-preset", choices=sorted(MODEL_PRESETS), help="Use a built-in model list instead of positional models")
    parser.add_argument("--list-model-presets", action="store_true", help="Print built-in model presets and exit")
    parser.add_argument("--timeout", type=int, default=600, help="Per-task timeout in seconds")
    parser.add_argument("--offline", action="store_true", help="Set PI_OFFLINE=1 for local-only benchmarking")
    parser.add_argument("--keep-env-offline", action="store_true", help="Respect an existing PI_OFFLINE env var")
    parser.add_argument("--allow-extensions", action="store_true", help="Do not pass --no-extensions; required for extension-provided providers such as claude-bridge")
    parser.add_argument("--system-prompt", default="You are a precise benchmark participant. Follow the user's formatting requirements exactly.")
    parser.add_argument("--task", dest="tasks", action="append", choices=[t["name"] for t in TASKS], help="Task to run; repeat for multiple tasks. Defaults to all tasks.")
    parser.add_argument("--db", default=str(ROOT / "results" / "pibench.sqlite"), help="SQLite database path; use 'none' to disable DB recording")
    parser.add_argument("--notes", help="Optional notes for this benchmark run")
    args = parser.parse_args()

    if args.list_model_presets:
        for name, models in MODEL_PRESETS.items():
            print(f"{name}:")
            for model in models:
                print(f"  {model}")
        return 0

    if args.models and args.model_preset:
        parser.error("use either positional models or --model-preset, not both")
    args.models = args.models or MODEL_PRESETS.get(args.model_preset or "baseline", DEFAULT_MODELS)

    selected_tasks = [t for t in TASKS if not args.tasks or t["name"] in set(args.tasks)]
    stamp = time.strftime("%Y%m%d-%H%M%S")
    rows = []

    conn = None if args.db == "none" else connect(Path(args.db))
    run_id = None
    run_model_ids = {}
    task_ids = {}
    if conn is not None:
        run_id = create_run(
            conn,
            "pi_agent",
            sys.argv,
            {
                "models": args.models,
                "tasks": [t["name"] for t in selected_tasks],
                "timeout": args.timeout,
                "offline": args.offline,
                "keep_env_offline": args.keep_env_offline,
                "allow_extensions": args.allow_extensions,
                "system_prompt": args.system_prompt,
            },
            args.notes,
        )
        for task in selected_tasks:
            task_ids[task["name"]] = upsert_task(
                conn,
                task["name"],
                task["prompt"],
                task["check"],
                category="pi_agent",
                metadata={"weight": task_weight(task["name"]), "difficulty": TASK_DIFFICULTY.get(task["name"], "unknown")},
            )
        for model in args.models:
            model_db_id = upsert_model(conn, model)
            run_model_ids[model] = attach_model_to_run(conn, run_id, model_db_id, model)

    for model in args.models:
        print(f"\n=== {model} ===", flush=True)
        for task in selected_tasks:
            task_started_at = utc_now()
            try:
                result = run_pi(model, task["prompt"], args)
            except subprocess.TimeoutExpired as exc:
                row = {
                    "model": model,
                    "task": task["name"],
                    "ok": False,
                    "note": f"timeout after {args.timeout}s",
                    "wall_s": args.timeout,
                    "returncode": -1,
                    "score": 0,
                    "total": CHECK_TOTALS.get(task["check"]),
                    "task_weight": task_weight(task["name"]),
                    "task_difficulty": TASK_DIFFICULTY.get(task["name"], "unknown"),
                    "stdout": exc.stdout or "",
                    "stderr": exc.stderr or "",
                    "started_at": task_started_at,
                    "ended_at": utc_now(),
                }
                rows.append(row)
                if conn is not None and run_id is not None:
                    insert_result(conn, run_id, run_model_ids[model], task_ids[task["name"]], row)
                print(f"{task['name']:<24} TIMEOUT", flush=True)
                continue

            stdout = result["stdout"]
            if result["returncode"] == 0:
                ok, note, checks = check_result(task["check"], stdout)
            else:
                ok, note, checks = False, "pi failed", {}
            if CHECK_TOTALS.get(task["check"]) and not checks.get("total"):
                checks = {**checks, "score": 0, "total": CHECK_TOTALS[task["check"]]}
            toks = approx_tokens(stdout)
            row = {
                "model": model,
                "task": task["name"],
                "ok": ok,
                "note": note,
                "wall_s": result["wall_s"],
                "approx_output_tokens": toks,
                "approx_output_tps": toks / result["wall_s"] if result["wall_s"] > 0 else None,
                "returncode": result["returncode"],
                "score": checks.get("score"),
                "total": checks.get("total"),
                "task_weight": task_weight(task["name"]),
                "task_difficulty": TASK_DIFFICULTY.get(task["name"], "unknown"),
                "checks": checks,
                "stdout": stdout,
                "stderr": result["stderr"],
                "started_at": task_started_at,
                "ended_at": utc_now(),
            }
            rows.append(row)
            if conn is not None and run_id is not None:
                insert_result(conn, run_id, run_model_ids[model], task_ids[task["name"]], row)
            status = "PASS" if ok else "FAIL"
            score_text = f" score={row['score']}/{row['total']}" if row.get("total") else ""
            print(f"{task['name']:<24} {status:<5} wall={result['wall_s']:7.2f}s approx_out={toks:5d} tok tps={row['approx_output_tps'] or 0:6.1f}{score_text} {note}", flush=True)

    json_path = OUTDIR / f"pi_agent_{stamp}.json"
    md_path = OUTDIR / f"pi_agent_{stamp}.md"
    json_path.write_text(json.dumps(rows, indent=2))

    lines = [
        "# Pi agent benchmark",
        "",
        f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "| model | pass | scored points | avg wall s | approx output tok/s | notes |",
        "|---|---:|---:|---:|---:|---|"
    ]
    for model in args.models:
        sub = [r for r in rows if r["model"] == model]
        if not sub:
            continue
        passed = sum(1 for r in sub if r["ok"])
        avg_wall = sum(r["wall_s"] for r in sub) / len(sub)
        avg_tps = sum((r.get("approx_output_tps") or 0) for r in sub) / len(sub)
        score_total = sum(r.get("score") or 0 for r in sub)
        points_total = sum(r.get("total") or 0 for r in sub)
        score_label = f"{score_total}/{points_total}" if points_total else "n/a"
        notes = "; ".join(f"{r['task']}={('pass' if r['ok'] else 'fail')}" for r in sub)
        lines.append(f"| `{model}` | {passed}/{len(sub)} | {score_label} | {avg_wall:.2f} | {avg_tps:.1f} | {notes} |")
    md_path.write_text("\n".join(lines) + "\n")

    if conn is not None and run_id is not None:
        finish_run(conn, run_id)
        print(f"Recorded SQLite run_id={run_id} in {args.db}")

    print(f"\nWrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
