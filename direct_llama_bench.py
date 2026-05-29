#!/usr/bin/env python3
import ast
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = os.environ.get("LLAMA_BASE", "http://127.0.0.1:8080/v1")
OUTDIR = Path(__file__).resolve().parent / "results"
OUTDIR.mkdir(exist_ok=True)

DEFAULT_MODELS = [
    "Qwen3.6-27B-MTP-Q4_K_M",
    "Qwen3.6-35B-A3B-MTP-UD-Q2_K_XL",
    "Qwen3.6-35B-A3B-MTP-UD-Q3_K_M",
    "Qwen3.6-35B-A3B-MTP-UD-Q4_K_M",
    "Qwen3.6-27B-NEO-CODE-2T-OT-Q5_K_M",
]

TASKS = [
    {
        "name": "json_exact",
        "prompt": 'Return only valid minified JSON with keys "name" and "nums". name must be "pi" and nums must be [3,1,4]. No markdown.',
        "max_tokens": 80,
        "check": "json_exact",
    },
    {
        "name": "dedupe_function",
        "prompt": "Return only Python code defining function dedupe_keep_order(xs) that removes duplicates while preserving order.",
        "max_tokens": 256,
        "check": "dedupe_exec",
    },
    {
        "name": "parse_ints_function",
        "prompt": "Return only Python code defining function parse_ints(s) that returns all signed integers appearing in a string, e.g. 'a-2 b 10' -> [-2, 10].",
        "max_tokens": 320,
        "check": "parse_ints_exec",
    },
    {
        "name": "bugfix_explain",
        "prompt": "In one sentence plus code, fix this memory-inefficient Python expression: sum([x*x for x in range(n)]).",
        "max_tokens": 180,
        "check": "contains_generator_sum",
    },
    {
        "name": "reasoning_calendar",
        "prompt": "If tomorrow is Friday, what day of the week was yesterday? Answer with one word only.",
        "max_tokens": 20,
        "check": "contains_wednesday",
    },
    {
        "name": "long_coding_advice",
        "prompt": "Write a concise 8-point checklist for reviewing a Python pull request. Keep each point one sentence.",
        "max_tokens": 384,
        "check": "manual",
    },
]


def api(path, payload=None, timeout=400):
    if payload is None:
        req = urllib.request.Request(BASE + path)
    else:
        req = urllib.request.Request(
            BASE + path,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "Authorization": "Bearer llama.cpp"},
        )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def available_models():
    try:
        return {m["id"] for m in api("/models").get("data", [])}
    except Exception:
        return set()


def clean_code(text):
    m = re.search(r"```(?:python)?\s*(.*?)```", text, flags=re.S | re.I)
    return (m.group(1) if m else text).strip()


def check(kind, text):
    if kind == "manual":
        return None, "manual"
    if kind == "json_exact":
        try:
            return json.loads(text) == {"name": "pi", "nums": [3, 1, 4]}, "json parsed"
        except Exception as e:
            return False, f"json error: {e}"
    if kind == "contains_generator_sum":
        norm = text.replace(" ", "")
        return "sum(x*xforxinrange(n))" in norm, "contains generator sum"
    if kind == "contains_wednesday":
        return "wednesday" in text.lower(), "contains Wednesday"
    if kind in {"dedupe_exec", "parse_ints_exec"}:
        code = clean_code(text)
        try:
            ns = {}
            exec(code, ns)
            if kind == "dedupe_exec":
                f = ns["dedupe_keep_order"]
                ok = f([1, 2, 1, 3, 2, 4]) == [1, 2, 3, 4] and f(["a", "a", "b"]) == ["a", "b"]
            else:
                f = ns["parse_ints"]
                ok = f("a-2 b 10 +7 x0") == [-2, 10, 7, 0] and f("none") == []
            return ok, "exec check"
        except Exception as e:
            return False, f"exec error: {type(e).__name__}: {e}"
    return False, "unknown check"


def call(model, prompt, max_tokens):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False, "preserve_thinking": True},
    }
    t0 = time.time()
    j = api("/chat/completions", payload)
    wall = time.time() - t0
    return wall, j


def gpu_mem():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader,nounits"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return out
    except Exception:
        return ""


def main():
    models = sys.argv[1:] or DEFAULT_MODELS
    avail = available_models()
    rows = []
    stamp = time.strftime("%Y%m%d-%H%M%S")
    print(f"Base: {BASE}")
    print(f"Available models: {len(avail)}")

    for model in models:
        if avail and model not in avail:
            print(f"\n=== {model} SKIP not in llama /v1/models ===")
            continue
        print(f"\n=== {model} ===", flush=True)
        try:
            call(model, "Reply with only READY", 8)
            time.sleep(0.5)
            print("GPU:", gpu_mem().replace("\n", " | "))
        except Exception as e:
            print("LOAD/READY FAILED", e)
            rows.append({"model": model, "task": "load", "ok": False, "error": str(e)})
            continue

        for task in TASKS:
            try:
                wall, j = call(model, task["prompt"], task["max_tokens"])
                text = j["choices"][0]["message"]["content"].strip()
                ok, note = check(task["check"], text)
                tim = j.get("timings", {})
                usage = j.get("usage", {})
                row = {
                    "model": model,
                    "task": task["name"],
                    "ok": ok,
                    "note": note,
                    "wall_s": wall,
                    "prompt_tps": tim.get("prompt_per_second"),
                    "gen_tps": tim.get("predicted_per_second"),
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "text": text,
                }
                rows.append(row)
                status = "MANUAL" if ok is None else ("PASS" if ok else "FAIL")
                print(f"{task['name']:<20} {status:<6} wall={wall:6.2f}s gen={row['gen_tps'] or 0:7.1f} tok/s {note}")
            except Exception as e:
                rows.append({"model": model, "task": task["name"], "ok": False, "error": str(e)})
                print(f"{task['name']:<20} ERROR {e}")

    json_path = OUTDIR / f"direct_llama_{stamp}.json"
    md_path = OUTDIR / f"direct_llama_{stamp}.md"
    json_path.write_text(json.dumps(rows, indent=2))

    lines = ["# Direct llama.cpp benchmark", "", f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}", "", "| model | graded pass | avg gen tok/s | notes |", "|---|---:|---:|---|"]
    for model in models:
        sub = [r for r in rows if r.get("model") == model and "task" in r]
        graded = [r for r in sub if r.get("ok") is not None]
        passed = sum(1 for r in graded if r.get("ok") is True)
        speeds = [r.get("gen_tps") for r in sub if isinstance(r.get("gen_tps"), (int, float))]
        avg = sum(speeds) / len(speeds) if speeds else 0
        lines.append(f"| `{model}` | {passed}/{len(graded)} | {avg:.1f} | |")
    md_path.write_text("\n".join(lines) + "\n")
    print(f"\nWrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
