#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
from pathlib import Path

OUTDIR = Path(__file__).resolve().parent / "results"
OUTDIR.mkdir(exist_ok=True)

DEFAULT_MODELS = [
    "Qwen3.6-27B-MTP-Q4_K_M",
    "Qwen3.6-35B-A3B-MTP-UD-Q2_K_XL",
    "Qwen3.6-35B-A3B-MTP-UD-Q3_K_M",
    "Qwen3.6-35B-A3B-MTP-UD-Q4_K_M",
    "Qwen3.6-27B-NEO-CODE-2T-OT-Q5_K_M",
]

PROMPTS = [
    ("ok", "Reply with only OK"),
    ("json", 'Return only valid minified JSON: {"name":"pi","nums":[3,1,4]}. No markdown.'),
    ("dedupe", "Return only Python code defining dedupe_keep_order(xs), preserving order."),
]


def run(model, name, prompt):
    env = os.environ.copy()
    env["PI_OFFLINE"] = "1"
    cmd = ["pi", "--model", model, "-p", prompt]
    t0 = time.time()
    p = subprocess.run(cmd, text=True, capture_output=True, env=env, timeout=300)
    wall = time.time() - t0
    return {
        "model": model,
        "task": name,
        "wall_s": wall,
        "returncode": p.returncode,
        "stdout": p.stdout.strip(),
        "stderr": p.stderr.strip(),
    }


def main():
    models = sys.argv[1:] or DEFAULT_MODELS
    rows = []
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for model in models:
        print(f"\n=== {model} ===", flush=True)
        for name, prompt in PROMPTS:
            try:
                row = run(model, name, prompt)
            except Exception as e:
                row = {"model": model, "task": name, "returncode": -1, "error": str(e)}
            rows.append(row)
            ok = row.get("returncode") == 0
            print(f"{name:<10} {'OK' if ok else 'FAIL'} wall={row.get('wall_s', 0):.2f}s {row.get('stdout','')[:120].replace(chr(10),' ')}", flush=True)
    out = OUTDIR / f"pi_cli_{stamp}.json"
    out.write_text(json.dumps(rows, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
