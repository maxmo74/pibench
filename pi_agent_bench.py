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
]


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


def run_python_submission(code: str, tests: str, timeout: int = 8) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "submission.py"
        path.write_text(code + "\n\n" + tests)
        proc = subprocess.run(["python3", str(path)], text=True, capture_output=True, timeout=timeout)
        return proc.returncode == 0, (proc.stdout + proc.stderr)[-1200:]


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
    parser.add_argument("models", nargs="*", default=DEFAULT_MODELS, help="Pi model IDs, e.g. openai-codex/gpt-5.5:medium")
    parser.add_argument("--timeout", type=int, default=600, help="Per-task timeout in seconds")
    parser.add_argument("--offline", action="store_true", help="Set PI_OFFLINE=1 for local-only benchmarking")
    parser.add_argument("--keep-env-offline", action="store_true", help="Respect an existing PI_OFFLINE env var")
    parser.add_argument("--system-prompt", default="You are a precise benchmark participant. Follow the user's formatting requirements exactly.")
    parser.add_argument("--task", dest="tasks", action="append", choices=[t["name"] for t in TASKS], help="Task to run; repeat for multiple tasks. Defaults to all tasks.")
    parser.add_argument("--db", default=str(ROOT / "results" / "pibench.sqlite"), help="SQLite database path; use 'none' to disable DB recording")
    parser.add_argument("--notes", help="Optional notes for this benchmark run")
    args = parser.parse_args()

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
            task_ids[task["name"]] = upsert_task(conn, task["name"], task["prompt"], task["check"], category="pi_agent")
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
            print(f"{task['name']:<24} {status:<5} wall={result['wall_s']:7.2f}s approx_out={toks:5d} tok tps={row['approx_output_tps'] or 0:6.1f} {note}", flush=True)

    json_path = OUTDIR / f"pi_agent_{stamp}.json"
    md_path = OUTDIR / f"pi_agent_{stamp}.md"
    json_path.write_text(json.dumps(rows, indent=2))

    lines = [
        "# Pi agent benchmark",
        "",
        f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "| model | pass | avg wall s | approx output tok/s | notes |",
        "|---|---:|---:|---:|---|",
    ]
    for model in args.models:
        sub = [r for r in rows if r["model"] == model]
        if not sub:
            continue
        passed = sum(1 for r in sub if r["ok"])
        avg_wall = sum(r["wall_s"] for r in sub) / len(sub)
        avg_tps = sum((r.get("approx_output_tps") or 0) for r in sub) / len(sub)
        notes = "; ".join(f"{r['task']}={('pass' if r['ok'] else 'fail')}" for r in sub)
        lines.append(f"| `{model}` | {passed}/{len(sub)} | {avg_wall:.2f} | {avg_tps:.1f} | {notes} |")
    md_path.write_text("\n".join(lines) + "\n")

    if conn is not None and run_id is not None:
        finish_run(conn, run_id)
        print(f"Recorded SQLite run_id={run_id} in {args.db}")

    print(f"\nWrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
