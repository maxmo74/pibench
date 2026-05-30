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
        "local-llama-q4-32k/Qwen3.6-35B-A3B-MTP-UD-Q4_K_M-ctx32k:off",
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
        "local-llama-q4-32k/Qwen3.6-35B-A3B-MTP-UD-Q4_K_M-ctx32k:off",
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
}


def task_weight(name: str) -> float:
    return TASK_WEIGHTS.get(name, 1.0)


def approx_tokens(text: str) -> int:
    # Same rough heuristic Pi uses in compaction fallback; useful for cross-provider
    # latency comparison when provider token usage is not exposed by the CLI.
    return max(1, (len(text) + 3) // 4)


def clean_fenced(text: str) -> str:
    text = text.strip()
    match = re.search(r"```(?:python|html|nginx|conf)?\s*(.*?)```", text, flags=re.S | re.I)
    if match:
        return match.group(1).strip()
    return re.sub(r"^```(?:\w+)?\s*", "", text, flags=re.I).strip()


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
        "--no-extensions",
        "--no-skills",
        "--no-prompt-templates",
        "--no-themes",
        "-p", prompt,
    ]
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
            run_model_ids[model] = attach_model_to_run(conn, run_id, model_db_id)

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
