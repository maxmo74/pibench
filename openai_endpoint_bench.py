#!/usr/bin/env python3
"""Benchmark an OpenAI-compatible chat endpoint without invoking the Pi CLI.

The benchmark reuses current PiBench checks and preserves native server timing
fields when the endpoint provides them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from pi_agent_bench import TASKS as PIBENCH_TASKS, check_result, approx_tokens  # noqa: E402

PB = {t["name"]: t for t in PIBENCH_TASKS}

DEFAULT_TASKS = [
    "lru_cache_hard",
    "json_path_set_hard",
    "rate_limiter_hard",
    "semver_range_hard",
    "log_triage_incident",
    "design_review_find_flaws",
    "architecture_decision_record",
]
ENDPOINT_TASKS = [task["name"] for task in PIBENCH_TASKS] + ["long_promessi_qa"]


def long_promessi_task(text_path: Path) -> dict:
    text = text_path.read_text(errors="ignore")[:60000]
    return {
        "name": "long_promessi_qa",
        "prompt": (
            "Read the following excerpt from I Promessi Sposi and answer in Italian, "
            "in exactly two concise sentences: who are Renzo and Lucia, and what obstacle "
            "prevents their marriage? Do not mention that this is an excerpt.\n\n" + text
        ),
        "check": "long_promessi_static",
    }


def get_task(name: str, long_text_path: Path | None) -> dict:
    if name == "long_promessi_qa":
        if long_text_path is None:
            raise ValueError("long_promessi_qa requires --long-text PATH or PIBENCH_LONG_TEXT")
        return long_promessi_task(long_text_path)
    if name not in PB:
        raise KeyError(name)
    return PB[name]


def check_extra(kind: str, stdout: str):
    low = stdout.lower()
    if kind == "long_promessi_static":
        checks = {
            "renzo": "renzo" in low,
            "lucia": "lucia" in low,
            "marriage": any(w in low for w in ["matrimonio", "spos", "nozze"]),
            "obstacle": any(w in low for w in ["don rodrigo", "imped", "ostacol", "minacc"]),
            "italian": any(w in low for w in ["sono", "il", "la", "che", "perché", "perche"]),
        }
        score = sum(checks.values())
        return score >= 4, f"score {score}/5", {"score": score, "total": 5, **checks}
    return check_result(kind, stdout)


def sanitized_endpoint(base_url: str) -> str:
    """Retain a reproducible endpoint address without credentials or query data."""
    parsed = urllib.parse.urlsplit(base_url)
    host = parsed.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    netloc = f"{host}:{parsed.port}" if parsed.port is not None else host
    return urllib.parse.urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def call_chat(base_url: str, model: str, prompt: str, max_tokens: int, timeout: int, no_think_template: bool) -> dict:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a precise benchmark participant. Follow formatting requirements exactly."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if no_think_template:
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, body, {"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.load(r)
    wall = time.time() - t0
    msg = data["choices"][0]["message"]
    return {"wall_s": wall, "stdout": (msg.get("content") or "").strip(), "raw": data}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    ap.add_argument("--model", required=True, help="exact model ID accepted by the endpoint")
    ap.add_argument("--label", default="", help="result label; defaults to the model ID")
    ap.add_argument("--task", action="append", choices=ENDPOINT_TASKS, help="task to run; repeat as needed; defaults to a representative seven-task subset")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--max-tokens", type=int, default=2048)
    ap.add_argument("--no-think-template", action="store_true", help="send chat_template_kwargs.enable_thinking=false for Qwen-style llama-server")
    ap.add_argument("--long-text", default=os.environ.get("PIBENCH_LONG_TEXT", ""), help="path to I Promessi Sposi text for long_promessi_qa; may also use PIBENCH_LONG_TEXT")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    tasks = args.task or DEFAULT_TASKS
    label = args.label or args.model
    long_text_path = Path(args.long_text).expanduser().resolve() if args.long_text else None
    if "long_promessi_qa" in tasks and (long_text_path is None or not long_text_path.is_file()):
        ap.error("long_promessi_qa requires an existing --long-text PATH or PIBENCH_LONG_TEXT")
    input_metadata = None
    if long_text_path is not None:
        content = long_text_path.read_bytes()
        input_metadata = {"long_text_sha256": hashlib.sha256(content).hexdigest(), "long_text_bytes": len(content)}
    rows = []
    for name in tasks:
        task = get_task(name, long_text_path)
        print(f"=== {label} :: {name} ===", flush=True)
        try:
            result = call_chat(args.base_url, args.model, task["prompt"], args.max_tokens, args.timeout, args.no_think_template)
            ok, note, checks = check_extra(task["check"], result["stdout"])
            toks = approx_tokens(result["stdout"])
            timings = result["raw"].get("timings")
            if not isinstance(timings, dict):
                timings = {}
            row = {
                "label": label,
                "model": args.model,
                "task": name,
                "ok": bool(ok),
                "note": note,
                "checks": checks,
                "wall_s": result["wall_s"],
                "approx_output_tokens": toks,
                "approx_output_tps": toks / result["wall_s"] if result["wall_s"] > 0 else None,
                "server_prompt_tps": timings.get("prompt_per_second"),
                "server_output_tps": timings.get("predicted_per_second"),
                "server_timings": timings or None,
                "stdout": result["stdout"],
                "usage": result["raw"].get("usage"),
            }
        except Exception as e:
            row = {"label": label, "model": args.model, "task": name, "ok": False, "note": f"error: {e}", "wall_s": args.timeout, "stdout": ""}
        rows.append(row)
        score = row.get("checks", {}).get("score")
        total = row.get("checks", {}).get("total")
        score_txt = f" score={score}/{total}" if total is not None else ""
        native_tps = row.get("server_output_tps")
        native_txt = f" server_tps={native_tps:.1f}" if isinstance(native_tps, (int, float)) else ""
        print(f"{'PASS' if row['ok'] else 'FAIL'} wall={row['wall_s']:.2f}s effective_tps={(row.get('approx_output_tps') or 0):.1f}{native_txt}{score_txt} {row['note']}", flush=True)
        print((row.get("stdout") or "").replace("\n", " ")[:180], flush=True)

    passed = sum(1 for r in rows if r["ok"])
    score = sum((r.get("checks", {}).get("score") or (1 if r["ok"] else 0)) for r in rows)
    total = sum((r.get("checks", {}).get("total") or 1) for r in rows)
    avg_wall = sum(r["wall_s"] for r in rows) / len(rows)
    avg_tps = sum((r.get("approx_output_tps") or 0) for r in rows) / len(rows)
    server_speeds = [r["server_output_tps"] for r in rows if isinstance(r.get("server_output_tps"), (int, float))]
    summary = {
        "label": label,
        "model": args.model,
        "base_url": sanitized_endpoint(args.base_url),
        "pass": f"{passed}/{len(rows)}",
        "score": score,
        "total": total,
        "avg_wall_s": avg_wall,
        "avg_effective_output_tps": avg_tps,
        "avg_server_output_tps": sum(server_speeds) / len(server_speeds) if server_speeds else None,
    }
    print("=== SUMMARY ===")
    print(json.dumps(summary, indent=2))

    if args.out:
        out = Path(args.out)
    else:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        safe_label = re.sub(r"[^A-Za-z0-9._-]+", "-", label).strip(".-") or "model"
        out = ROOT / "results" / f"endpoint_bench_{safe_label}_{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "input_metadata": input_metadata, "rows": rows}, indent=2))
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
