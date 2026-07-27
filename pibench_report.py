#!/usr/bin/env python3
"""Generate integrated Markdown reports from the PiBench SQLite database."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sqlite3
import time
import urllib.parse
from pathlib import Path

from pibench_db import init_db

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "results" / "pibench.sqlite"
DEFAULT_OUT = ROOT / "results" / "INTEGRATED_REPORT.md"

NORMALIZED_HARD_5 = [
    "csv_infer_hard",
    "retry_schedule_hard",
    "semver_range_hard",
    "markdown_table_hard",
    "text_wrap_hard",
]

NORMALIZED_NONCODING_8 = [
    "systemd_service_hard",
    "nginx_tls_proxy_hard",
    "log_triage_incident",
    "readme_quickstart_rewrite",
    "changelog_from_commits",
    "github_issue_triage",
    "architecture_decision_record",
    "design_review_find_flaws",
]

NORMALIZED_FULL_16 = [
    "json_exact",
    "dedupe_function",
    "parse_ints_function",
    "interval_merge_edgecases",
    "toposort_cycle",
    "nginx_reverse_proxy",
    "webui_todo_static",
    "lru_cache_hard",
    "json_path_set_hard",
    "rate_limiter_hard",
    "unified_diff_hard",
    "csv_infer_hard",
    "retry_schedule_hard",
    "semver_range_hard",
    "markdown_table_hard",
    "text_wrap_hard",
]

NORMALIZED_EXPANDED_24 = NORMALIZED_FULL_16 + NORMALIZED_NONCODING_8

CSV_SCHEMA_VERSION = 1
CSV_INFERENCE_FIELDS = [
    "gpu_layers",
    "parallel",
    "flash_attention",
    "temperature",
    "top_p",
    "top_k",
    "min_p",
    "seed",
    "batch_size",
    "ubatch_size",
    "threads",
    "fit",
    "fit_context_min",
    "split_mode",
    "tensor_split",
    "reasoning",
    "reasoning_format",
    "reasoning_budget",
    "speculation_method",
    "speculative_tokens",
]
CSV_FIELDS = [
    "csv_schema_version",
    "result_id",
    "run_id",
    "run_model_id",
    "run_started_at",
    "run_ended_at",
    "run_status",
    "benchmark_name",
    "benchmark_version",
    "pibench_commit",
    "pi_version",
    "suite",
    "run_task_count",
    "run_passed",
    "run_weighted_score",
    "run_weighted_total",
    "contributor",
    "source_url",
    "compute_mode",
    "accelerators_used",
    "host_platform",
    "cpu_model",
    "logical_cpus",
    "memory_gib",
    "accelerators_detected",
    "cuda_toolkit_version",
    "provider",
    "model_id",
    "model_arg",
    "thinking_requested",
    "thinking_effective",
    "context_window",
    "max_output",
    "runtime_label",
    "runtime_version",
    "runtime_commit",
    "runtime_build",
    "runtime_compiler",
    "llama_cpp_version",
    "llama_cpp_build",
    "llama_cpp_commit",
    "llama_cpp_commit_date",
    "model_format",
    "quantization",
    "model_artifact",
    "model_sha256",
    "context_size",
    "kv_cache",
    *CSV_INFERENCE_FIELDS,
    "task",
    "task_category",
    "check_kind",
    "task_weight",
    "passed",
    "score",
    "total",
    "weighted_score",
    "wall_s",
    "approx_output_tokens",
    "approx_output_tps",
]
CSV_FORBIDDEN = re.compile(
    r"(?i)(/(?:home|root|tmp)/|[A-Z]:\\Users\\|BEGIN [A-Z ]*PRIVATE KEY|"
    r"(?:api[_-]?key|authorization|bearer)\s*[:=]|"
    r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})"
)

TASK_WEIGHTS = {
    "json_exact": 0.5,
    "dedupe_function": 1.0,
    "parse_ints_function": 1.0,
    "interval_merge_edgecases": 2.0,
    "toposort_cycle": 2.5,
    "nginx_reverse_proxy": 2.0,
    "webui_todo_static": 2.0,
    "lru_cache_hard": 3.0,
    "json_path_set_hard": 4.0,
    "rate_limiter_hard": 3.5,
    "unified_diff_hard": 4.5,
    "csv_infer_hard": 3.5,
    "retry_schedule_hard": 3.0,
    "semver_range_hard": 4.0,
    "markdown_table_hard": 3.5,
    "text_wrap_hard": 3.0,
    "systemd_service_hard": 3.0,
    "nginx_tls_proxy_hard": 3.0,
    "log_triage_incident": 2.5,
    "readme_quickstart_rewrite": 2.0,
    "changelog_from_commits": 2.0,
    "github_issue_triage": 2.5,
    "architecture_decision_record": 3.5,
    "design_review_find_flaws": 3.5,
}


def weight_case(alias: str = "t") -> str:
    clauses = " ".join(f"WHEN {alias}.name = '{name}' THEN {weight}" for name, weight in TASK_WEIGHTS.items())
    return f"CASE {clauses} ELSE 1.0 END"


def weighted_score_expr() -> str:
    w = weight_case("t")
    return f"SUM(CASE WHEN COALESCE(res.total, 0) > 0 THEN (COALESCE(res.score, 0) * 1.0 / res.total) * ({w}) ELSE res.ok * ({w}) END)"


def weighted_total_expr() -> str:
    return f"SUM({weight_case('t')})"


def sanitize_notes(text: str) -> str:
    return re.sub(r"/tmp/tmp[^/]+/submission\.py", "<tmp>/submission.py", text)


def parse_json_dict(value: object) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def parse_json_list(value: object) -> list:
    if not value:
        return []
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def public_url(value: object) -> str:
    """Strip credentials, queries, and fragments from a public provenance URL."""
    if not value:
        return ""
    try:
        parsed = urllib.parse.urlsplit(str(value))
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return ""
        host = parsed.hostname
        if ":" in host:
            host = f"[{host}]"
        netloc = f"{host}:{parsed.port}" if parsed.port is not None else host
        return urllib.parse.urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))
    except (TypeError, ValueError):
        return ""


def public_text(value: object) -> str:
    """Normalize an allowlisted CSV value and reject private or active content."""
    if value is None:
        return ""
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, (dict, list)):
        text = json.dumps(value, sort_keys=True, separators=(",", ":"))
    else:
        text = " ".join(str(value).split())
    if CSV_FORBIDDEN.search(text):
        raise ValueError(f"unsafe value refused by public CSV exporter: {text[:80]!r}")
    # Prevent spreadsheet applications from interpreting contributor-controlled
    # strings as formulas. Numeric fields are formatted before reaching here.
    if text.startswith(("=", "+", "-", "@")):
        text = "'" + text
    return text


def public_git_commit(value: object) -> str:
    text = str(value or "").strip()
    return text if re.fullmatch(r"[0-9a-fA-F]{7,40}", text) else ""


def public_iso_timestamp(value: object) -> str:
    text = str(value or "").strip()
    return public_text(text) if re.fullmatch(r"\d{4}-\d{2}-\d{2}T[^\s]+", text) else ""


def csv_number(value: object, digits: int = 6) -> str:
    if value is None:
        return ""
    number = float(value)
    if not math.isfinite(number):
        return ""
    return f"{number:.{digits}f}".rstrip("0").rstrip(".")


def suite_name(task_names: set[str]) -> str:
    known = [
        ("expanded-24", NORMALIZED_EXPANDED_24),
        ("full-16", NORMALIZED_FULL_16),
        ("non-coding-8", NORMALIZED_NONCODING_8),
        ("hard-5", NORMALIZED_HARD_5),
    ]
    for name, tasks in known:
        if task_names == set(tasks):
            return name
    return f"custom-{len(task_names)}"


def detected_accelerators(host: dict) -> list[str]:
    values = []
    for item in host.get("accelerators_detected", []):
        if not isinstance(item, dict) or not item.get("name"):
            continue
        details = [str(item["name"])]
        if item.get("memory_mib"):
            details.append(f"{item['memory_mib']} MiB")
        if item.get("driver_version"):
            details.append(f"driver {item['driver_version']}")
        values.append("; ".join(details))
    if not values:
        values.extend(str(value) for value in host.get("nvidia_gpus", []) if value)
    return values


def export_public_csv(conn: sqlite3.Connection, out: Path) -> int:
    """Write an allowlisted task-level export without prompts or raw model output."""
    rows = conn.execute(
        """
        SELECT res.id AS result_id, res.run_id, res.run_model_id,
               r.id AS metadata_run_id, r.started_at, r.ended_at,
               res.started_at AS result_started_at,
               res.ended_at AS result_ended_at,
               r.notes, r.benchmark_name, r.benchmark_version,
               r.pibench_commit, r.pi_version, r.contributor, r.source_url,
               r.compute_mode, r.accelerators_json, r.host_json,
               m.provider, m.model_id, m.model_arg, m.thinking_requested,
               m.thinking_effective, m.context_window_label,
               m.max_output_label,
               rm.runtime_label, rm.runtime_version, rm.runtime_commit,
               rm.runtime_build, rm.runtime_compiler,
               rm.llama_cpp_version, rm.llama_cpp_build,
               rm.llama_cpp_commit, rm.llama_cpp_commit_date,
               rm.model_format, rm.quantization, rm.model_artifact,
               rm.model_sha256, rm.context_size, rm.kv_cache,
               rm.inference_json,
               t.name AS task, t.category AS task_category,
               t.check_kind,
               res.ok, res.score, res.total, res.wall_s,
               res.approx_output_tokens, res.approx_output_tps
        FROM results res
        LEFT JOIN runs r ON r.id = res.run_id
        JOIN run_models rm ON rm.id = res.run_model_id
        JOIN models m ON m.id = rm.model_id
        JOIN tasks t ON t.id = res.task_id
        ORDER BY res.run_id, res.run_model_id, res.id
        """
    ).fetchall()

    grouped: dict[tuple[int, int], list[sqlite3.Row]] = {}
    for row in rows:
        grouped.setdefault((int(row["run_id"]), int(row["run_model_id"])), []).append(row)

    summaries = {}
    for key, group in grouped.items():
        names = {str(row["task"]) for row in group}
        weighted_score = 0.0
        weighted_total = 0.0
        for row in group:
            weight = TASK_WEIGHTS.get(str(row["task"]), 1.0)
            weighted_total += weight
            if row["total"] is not None and float(row["total"]) > 0:
                weighted_score += (float(row["score"] or 0) / float(row["total"])) * weight
            else:
                weighted_score += (1.0 if row["ok"] else 0.0) * weight
        notes = str(group[0]["notes"] or "").lower()
        if group[0]["metadata_run_id"] is None:
            status = "orphaned-metadata"
        elif notes.startswith("incomplete infrastructure"):
            status = "incomplete-infrastructure"
        elif not group[0]["ended_at"]:
            status = "incomplete"
        else:
            status = "completed"
        summaries[key] = {
            "started_at": group[0]["started_at"] or min((row["result_started_at"] for row in group if row["result_started_at"]), default=None),
            "ended_at": group[0]["ended_at"] or max((row["result_ended_at"] for row in group if row["result_ended_at"]), default=None),
            "suite": suite_name(names),
            "task_count": len(group),
            "passed": sum(1 for row in group if row["ok"]),
            "weighted_score": weighted_score,
            "weighted_total": weighted_total,
            "status": status,
        }

    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_name(out.name + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            summary = summaries[(int(row["run_id"]), int(row["run_model_id"]))]
            host = parse_json_dict(row["host_json"])
            inference = parse_json_dict(row["inference_json"])
            used = parse_json_list(row["accelerators_json"])
            memory_gib = None
            if host.get("mem_total_kb") is not None:
                try:
                    memory_gib = float(host["mem_total_kb"]) / 1024 / 1024
                except (TypeError, ValueError):
                    pass
            weight = TASK_WEIGHTS.get(str(row["task"]), 1.0)
            if row["total"] is not None and float(row["total"]) > 0:
                credit = float(row["score"] or 0) / float(row["total"])
            else:
                credit = 1.0 if row["ok"] else 0.0
            record = {
                "csv_schema_version": str(CSV_SCHEMA_VERSION),
                "result_id": str(row["result_id"]),
                "run_id": str(row["run_id"]),
                "run_model_id": str(row["run_model_id"]),
                "run_started_at": public_text(summary["started_at"]),
                "run_ended_at": public_text(summary["ended_at"]),
                "run_status": summary["status"],
                "benchmark_name": public_text(row["benchmark_name"] or row["task_category"]),
                "benchmark_version": public_text(row["benchmark_version"]),
                "pibench_commit": public_git_commit(row["pibench_commit"]),
                "pi_version": public_text(row["pi_version"]),
                "suite": summary["suite"],
                "run_task_count": str(summary["task_count"]),
                "run_passed": str(summary["passed"]),
                "run_weighted_score": csv_number(summary["weighted_score"]),
                "run_weighted_total": csv_number(summary["weighted_total"]),
                "contributor": public_text(row["contributor"]),
                "source_url": public_text(public_url(row["source_url"])),
                "compute_mode": public_text(row["compute_mode"]),
                "accelerators_used": public_text(used),
                "host_platform": public_text(host.get("platform")),
                "cpu_model": public_text(host.get("cpu_model")),
                "logical_cpus": public_text(host.get("logical_cpus") or host.get("cpu_count")),
                "memory_gib": csv_number(memory_gib, 3),
                "accelerators_detected": public_text(detected_accelerators(host)),
                "cuda_toolkit_version": public_text(host.get("cuda_toolkit_version")),
                "provider": public_text(row["provider"]),
                "model_id": public_text(row["model_id"]),
                "model_arg": public_text(row["model_arg"]),
                "thinking_requested": public_text(row["thinking_requested"]),
                "thinking_effective": public_text(row["thinking_effective"]),
                "context_window": public_text(row["context_size"] or row["context_window_label"]),
                "max_output": public_text(row["max_output_label"]),
                "runtime_label": public_text(row["runtime_label"]),
                "runtime_version": public_text(row["runtime_version"]),
                "runtime_commit": public_git_commit(row["runtime_commit"]),
                "runtime_build": public_text(row["runtime_build"]),
                "runtime_compiler": public_text(row["runtime_compiler"]),
                "llama_cpp_version": public_text(row["llama_cpp_version"]),
                "llama_cpp_build": public_text(row["llama_cpp_build"]),
                "llama_cpp_commit": public_git_commit(row["llama_cpp_commit"]),
                "llama_cpp_commit_date": public_iso_timestamp(row["llama_cpp_commit_date"]),
                "model_format": public_text(row["model_format"]),
                "quantization": public_text(row["quantization"]),
                "model_artifact": public_text(row["model_artifact"]),
                "model_sha256": public_text(row["model_sha256"]),
                "context_size": public_text(row["context_size"]),
                "kv_cache": public_text(row["kv_cache"]),
                "task": public_text(row["task"]),
                "task_category": public_text(row["task_category"]),
                "check_kind": public_text(row["check_kind"]),
                "task_weight": csv_number(weight),
                "passed": "1" if row["ok"] else "0",
                "score": csv_number(row["score"]),
                "total": csv_number(row["total"]),
                "weighted_score": csv_number(credit * weight),
                "wall_s": csv_number(row["wall_s"]),
                "approx_output_tokens": public_text(row["approx_output_tokens"]),
                "approx_output_tps": csv_number(row["approx_output_tps"]),
            }
            for field in CSV_INFERENCE_FIELDS:
                record[field] = public_text(inference.get(field))
            writer.writerow(record)
    temporary.replace(out)
    return len(rows)


def model_label(model_arg: str) -> str:
    labels = {
        "claude-bridge/claude-opus-4-8:high": "Claude Bridge Opus 4.8 — high reasoning",
        "claude-bridge/claude-opus-4-8:medium": "Claude Bridge Opus 4.8 — medium reasoning",
        "claude-bridge/claude-sonnet-4-6:medium": "Claude Bridge Sonnet 4.6 — medium reasoning",
        "local-llama-neo-code-nomtp/Qwen3.6-27B-NEO-CODE-2T-OT-Q5_K_M-nomtp:off": "Qwen3.6 27B NEO CODE 2T OT Q5_K_M — non-MTP runtime, thinking off",
        "local-llama-latest-neo-code-64k-nomtp-temp02/Qwen3.6-27B-NEO-CODE-2T-OT-Q5_K_M-ctx64k-latest-nomtp-temp02:off": "Qwen3.6 27B NEO CODE 2T OT Q5_K_M — latest llama.cpp 64K ctx, no-MTP, temp0.2, thinking off",
        "local-llama-stable-neo-code-64k-nomtp-temp02/Qwen3.6-27B-NEO-CODE-2T-OT-Q5_K_M-ctx64k-stable-nomtp-temp02:off": "Qwen3.6 27B NEO CODE 2T OT Q5_K_M — stable llama.cpp 64K ctx, no-MTP, temp0.2, thinking off",
        "local-llama-qwen3-coder-nomtp/Qwen3-Coder-30B-A3B-Instruct-1M-UD-Q4_K_XL-nomtp:off": "Qwen3-Coder 30B A3B Instruct 1M UD Q4_K_XL — non-MTP runtime, thinking off",
        "local-llama-qwen25-coder-nomtp/qwen2.5-coder-32b-instruct-q4_k_m-nomtp:off": "Qwen2.5-Coder 32B Instruct Q4_K_M — non-MTP runtime, thinking off",
        "local-llama-qwen25-coder-64k-nomtp/qwen2.5-coder-32b-instruct-q4_k_m-ctx64k-nomtp:off": "Qwen2.5-Coder 32B Instruct Q4_K_M — 64K ctx non-MTP runtime, thinking off",
        "local-llama-devstral-nomtp/Devstral-Small-2507-UD-Q4_K_XL-nomtp:off": "Devstral Small 2507 UD Q4_K_XL — non-MTP runtime, thinking off",
        "local-llama-mistral-small-nomtp/Mistral-Small-3.2-24B-Instruct-2506-UD-Q4_K_XL-nomtp:off": "Mistral Small 3.2 24B Instruct 2506 UD Q4_K_XL — non-MTP runtime, thinking off",
        "local-llama-deepseek-coder-v2-lite-nomtp/DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M-nomtp:off": "DeepSeek Coder V2 Lite Instruct Q4_K_M — non-MTP runtime, thinking off",
        "local-llama-nemotron-nano-64k-nomtp/Nemotron-3-Nano-30B-A3B-UD-Q3_K_XL-ctx64k-nomtp:off": "Nemotron 3 Nano 30B A3B UD Q3_K_XL — 64K ctx non-MTP runtime, thinking off",
        "local-llama-test/Nex-N2-mini-Q4_K_M:medium": "Nex-N2-mini Q4_K_M — thinking enabled",
        "local-llama-test/Nex-N2-mini-Q4_K_M:off": "Nex-N2-mini Q4_K_M — thinking off",
        "local-llama-test/SIQ-1-35B-Q4_K_M:medium": "SIQ-1-35B Q4_K_M — thinking enabled",
        "local-llama-test/SIQ-1-35B-Q4_K_M:off": "SIQ-1-35B Q4_K_M — thinking off",
        "local-llama-test/KAT-Coder-V2.5-Dev-Q4_K_M:medium": "KAT-Coder-V2.5-Dev Q4_K_M — thinking enabled",
        "local-llama-test/KAT-Coder-V2.5-Dev-Q4_K_M:off": "KAT-Coder-V2.5-Dev Q4_K_M — thinking off",
        "local-llama/Road Runner:off": "Road Runner — Qwen3.6 35B Q4, MTP n3, thinking off",
        "local-llama/Qwen3.6-35B-A3B-MTP-UD-Q2_K_XL:off": "Qwen3.6 35B A3B MTP UD Q2_K_XL — thinking off",
        "local-llama/Qwen3.6-35B-A3B-MTP-UD-Q3_K_M:off": "Qwen3.6 35B A3B MTP UD Q3_K_M — thinking off",
        "local-llama/Qwen3.6-35B-A3B-MTP-UD-Q3_K_M:medium": "Qwen3.6 35B A3B MTP UD Q3_K_M — thinking on",
        "local-llama-q3-262k/Qwen3.6-35B-A3B-MTP-UD-Q3_K_M-ctx262k:medium": "Qwen3.6 35B A3B MTP UD Q3_K_M — 262K ctx MTP runtime, thinking on",
        "local-llama-latest-q3-131k/Qwen3.6-35B-A3B-MTP-UD-Q3_K_M-ctx131k-latest:off": "Qwen3.6 35B A3B MTP UD Q3_K_M — latest llama.cpp 131K ctx, thinking off",
        "local-llama-latest-q3-131k/Qwen3.6-35B-A3B-MTP-UD-Q3_K_M-ctx131k-latest:medium": "Qwen3.6 35B A3B MTP UD Q3_K_M — latest llama.cpp 131K ctx, thinking on",
        "local-llama-latest-q3-131k-nomtp/Qwen3.6-35B-A3B-MTP-UD-Q3_K_M-ctx131k-latest-nomtp:off": "Qwen3.6 35B A3B MTP UD Q3_K_M — latest llama.cpp 131K ctx, no-MTP, thinking off",
        "local-llama-stable-q3-131k/Qwen3.6-35B-A3B-MTP-UD-Q3_K_M-ctx131k-stable:off": "Qwen3.6 35B A3B MTP UD Q3_K_M — stable llama.cpp 131K ctx, thinking off",
        "local-llama-stable-q3-131k-temp02/Qwen3.6-35B-A3B-MTP-UD-Q3_K_M-ctx131k-stable-temp02:off": "Qwen3.6 35B A3B MTP UD Q3_K_M — stable llama.cpp 131K ctx, temp0.2, thinking off",
        "local-llama-stable-q3-131k-nomtp-temp02/Qwen3.6-35B-A3B-MTP-UD-Q3_K_M-ctx131k-stable-nomtp-temp02:off": "Qwen3.6 35B A3B MTP UD Q3_K_M — stable llama.cpp 131K ctx, no-MTP, temp0.2, thinking off",
        "local-llama-latest-q3-131k-nomtp-temp02/Qwen3.6-35B-A3B-MTP-UD-Q3_K_M-ctx131k-latest-nomtp-temp02:off": "Qwen3.6 35B A3B MTP UD Q3_K_M — latest llama.cpp 131K ctx, no-MTP, temp0.2, thinking off",
        "local-llama-latest-q3-131k-greedy/Qwen3.6-35B-A3B-MTP-UD-Q3_K_M-ctx131k-latest-greedy:off": "Qwen3.6 35B A3B MTP UD Q3_K_M — latest llama.cpp 131K ctx, temp0, thinking off",
        "local-llama-latest-q3-131k-temp02/Qwen3.6-35B-A3B-MTP-UD-Q3_K_M-ctx131k-latest-temp02:off": "Qwen3.6 35B A3B MTP UD Q3_K_M — latest llama.cpp 131K ctx, temp0.2, thinking off",
        "local-llama-latest-q3-131k-mtp4/Qwen3.6-35B-A3B-MTP-UD-Q3_K_M-ctx131k-latest-mtp4:medium": "Qwen3.6 35B A3B MTP UD Q3_K_M — latest llama.cpp 131K ctx, MTP draft4, thinking on",
        "local-llama-latest-q3-262k/Qwen3.6-35B-A3B-MTP-UD-Q3_K_M-ctx262k-latest:off": "Qwen3.6 35B A3B MTP UD Q3_K_M — latest llama.cpp 262K ctx, thinking off",
        "local-llama-diag-stable-q3-131k/Qwen3.6-35B-A3B-MTP-UD-Q3_K_M-ctx131k-diag-stable:medium": "Qwen3.6 35B A3B MTP UD Q3_K_M — diagnostic stable llama.cpp 131K ctx, thinking on",
        "local-llama-diag-latest-q3-131k/Qwen3.6-35B-A3B-MTP-UD-Q3_K_M-ctx131k-diag-latest:medium": "Qwen3.6 35B A3B MTP UD Q3_K_M — diagnostic latest llama.cpp 131K ctx, thinking on",
        "local-llama/Qwen3.6-35B-A3B-MTP-UD-Q4_K_M:off": "Qwen3.6 35B A3B MTP UD Q4_K_M — full-context attempt, thinking off",
        "local-llama-q4-32k/Qwen3.6-35B-A3B-MTP-UD-Q4_K_M-ctx32k:off": "Qwen3.6 35B A3B MTP UD Q4_K_M — 32K ctx MTP runtime, thinking off",
        "local-llama-q4-64k/Qwen3.6-35B-A3B-MTP-UD-Q4_K_M-ctx64k:off": "Qwen3.6 35B A3B MTP UD Q4_K_M — 64K ctx MTP runtime, thinking off",
        "local-llama-q4-64k/Qwen3.6-35B-A3B-MTP-UD-Q4_K_M-ctx64k:medium": "Qwen3.6 35B A3B MTP UD Q4_K_M — 64K ctx MTP runtime, thinking on",
        "local-llama-latest-q4-64k/Qwen3.6-35B-A3B-MTP-UD-Q4_K_M-ctx64k-latest:off": "Qwen3.6 35B A3B MTP UD Q4_K_M — latest llama.cpp 64K ctx, thinking off",
        "local-llama-stable-q4-64k-temp02/Qwen3.6-35B-A3B-MTP-UD-Q4_K_M-ctx64k-stable-temp02:off": "Qwen3.6 35B A3B MTP UD Q4_K_M — stable llama.cpp 64K ctx, temp0.2, thinking off",
        "local-llama-stable-q4-131k-nomtp-temp02/Qwen3.6-35B-A3B-MTP-UD-Q4_K_M-ctx131k-stable-nomtp-temp02:off": "Qwen3.6 35B A3B MTP UD Q4_K_M — stable llama.cpp 131K ctx, no-MTP, temp0.2, thinking off",
        "local-llama-latest-q4-64k-temp02/Qwen3.6-35B-A3B-MTP-UD-Q4_K_M-ctx64k-latest-temp02:off": "Qwen3.6 35B A3B MTP UD Q4_K_M — latest llama.cpp 64K ctx, temp0.2, thinking off",
        "local-llama-latest-q4-131k/Qwen3.6-35B-A3B-MTP-UD-Q4_K_M-ctx131k-latest:off": "Qwen3.6 35B A3B MTP UD Q4_K_M — latest llama.cpp 131K ctx, thinking off",
        "local-llama-latest-q4-131k-temp02/Qwen3.6-35B-A3B-MTP-UD-Q4_K_M-ctx131k-latest-temp02:off": "Qwen3.6 35B A3B MTP UD Q4_K_M — latest llama.cpp 131K ctx, temp0.2, thinking off",
        "local-llama-q4kxl-32k/Qwen3.6-35B-A3B-MTP-UD-Q4_K_XL-ctx32k:off": "Qwen3.6 35B A3B MTP UD Q4_K_XL — 32K ctx MTP runtime, thinking off",
        "local-llama-q4kxl-32k/Qwen3.6-35B-A3B-MTP-UD-Q4_K_XL-ctx32k:medium": "Qwen3.6 35B A3B MTP UD Q4_K_XL — 32K ctx MTP runtime, thinking on",
        "local-llama-q4kxl-48k/Qwen3.6-35B-A3B-MTP-UD-Q4_K_XL-ctx48k:off": "Qwen3.6 35B A3B MTP UD Q4_K_XL — 48K ctx MTP runtime, thinking off",
        "local-llama-q4kxl-48k/Qwen3.6-35B-A3B-MTP-UD-Q4_K_XL-ctx48k:medium": "Qwen3.6 35B A3B MTP UD Q4_K_XL — 48K ctx MTP runtime, thinking on",
        "local-llama-q4kxl-64k/Qwen3.6-35B-A3B-MTP-UD-Q4_K_XL-ctx64k:off": "Qwen3.6 35B A3B MTP UD Q4_K_XL — 64K ctx MTP runtime, thinking off",
        "local-llama-q4kxl-64k/Qwen3.6-35B-A3B-MTP-UD-Q4_K_XL-ctx64k:medium": "Qwen3.6 35B A3B MTP UD Q4_K_XL — 64K ctx MTP runtime, thinking on",
        "local-llama-latest-q4kxl-64k/Qwen3.6-35B-A3B-MTP-UD-Q4_K_XL-ctx64k-latest:off": "Qwen3.6 35B A3B MTP UD Q4_K_XL — latest llama.cpp 64K ctx, thinking off",
        "local-llama/gemma-4-26B-A4B-it-UD-Q4_K_XL:off": "Gemma 4 26B A4B IT UD Q4_K_XL — MTP-router attempt, thinking off",
        "local-llama-gemma-nomtp/gemma-4-26B-A4B-it-UD-Q4_K_XL-nomtp:off": "Gemma 4 26B A4B IT UD Q4_K_XL — non-MTP runtime, thinking off",
        "local-llama/Qwen3.6-35B-A3B-APEX-MTP-Quality:off": "Qwen3.6 35B A3B APEX MTP Quality — thinking off",
        "local-llama/Qwen3.6-35B-A3B-APEX-MTP-Compact:off": "Qwen3.6 35B A3B APEX MTP Compact — thinking off",
        "local-llama-apex-quality-64k/Qwen3.6-35B-A3B-APEX-MTP-Quality-ctx64k:off": "Qwen3.6 35B A3B APEX MTP Quality — 64K ctx MTP runtime, thinking off",
        "local-llama-claude-distilled-quality-64k/Qwen3.6-35B-A3B-Claude-4.7-Opus-Reasoning-Distilled-APEX-MTP-Quality-ctx64k:off": "Qwen3.6 35B Claude 4.7 Opus Reasoning Distilled APEX MTP Quality — 64K ctx MTP runtime, thinking off",
        "local-llama-carnice-quality-64k/Carnice-Qwen3.6-MoE-35B-A3B-APEX-MTP-Quality-ctx64k:off": "Carnice Qwen3.6 MoE 35B A3B APEX MTP Quality — 64K ctx MTP runtime, thinking off",
        "local-llama/Qwen3.6-27B-MTP-Q4_K_M:off": "Qwen3.6 27B MTP Q4_K_M — thinking off",
        "local-llama-latest-27b-q4-131k/Qwen3.6-27B-MTP-Q4_K_M-ctx131k-latest:off": "Qwen3.6 27B MTP Q4_K_M — latest llama.cpp 131K ctx, thinking off",
        "local-llama-latest-27b-q4-131k-temp02/Qwen3.6-27B-MTP-Q4_K_M-ctx131k-latest-temp02:off": "Qwen3.6 27B MTP Q4_K_M — latest llama.cpp 131K ctx, temp0.2, thinking off",
        "local-llama-latest-27b-q4-64k-q8kv-temp02/Qwen3.6-27B-MTP-Q4_K_M-ctx64k-latest-q8kv-temp02:off": "Qwen3.6 27B MTP Q4_K_M — latest llama.cpp 64K ctx, q8 KV, temp0.2, thinking off",
        "local-llama-latest-27b-q4-131k-q8kv-temp02/Qwen3.6-27B-MTP-Q4_K_M-ctx131k-latest-q8kv-temp02:off": "Qwen3.6 27B MTP Q4_K_M — latest llama.cpp 131K ctx, q8 KV, temp0.2, thinking off",
        "local-llama-latest-27b-q4-131k-mtp4-temp02/Qwen3.6-27B-MTP-Q4_K_M-ctx131k-latest-mtp4-temp02:off": "Qwen3.6 27B MTP Q4_K_M — latest llama.cpp 131K ctx, MTP draft4, temp0.2, thinking off",
        "local-llama-stable-27b-q4-131k-temp02/Qwen3.6-27B-MTP-Q4_K_M-ctx131k-stable-temp02:off": "Qwen3.6 27B MTP Q4_K_M — stable llama.cpp 131K ctx, temp0.2, thinking off",
        "local-llama/qwen3.6-27B-openhands-v1-MTP-Q4_K_M:off": "Qwen3.6 27B OpenHands v1 MTP Q4_K_M — thinking off",
        "local-llama-latest-openhands-27b-q4-131k-temp02/qwen3.6-27B-openhands-v1-MTP-Q4_K_M-ctx131k-latest-temp02:off": "Qwen3.6 27B OpenHands v1 MTP Q4_K_M — latest llama.cpp 131K ctx, temp0.2, thinking off",
        "local-llama/Qwen3.6-35B-A3B-APEX-MTP-Compact:medium": "Qwen3.6 35B A3B APEX MTP Compact — thinking on",
        "local-llama/Qwen3.6-35B-A3B-Uncensored-Genesis-MTP-APEX-Compact:off": "Qwen3.6 35B A3B Uncensored Genesis MTP APEX Compact — thinking off",
        "local-llama/Qwen3.6-35B-A3B-Uncensored-Genesis-MTP-APEX-Compact:medium": "Qwen3.6 35B A3B Uncensored Genesis MTP APEX Compact — thinking on",
        "local-llama-nomtp/Qwen3.6-35B-A3B-Uncensored-Genesis-APEX-Compact:off": "Qwen3.6 35B A3B Uncensored Genesis APEX Compact — non-MTP runtime, thinking off",
        "openai-codex/gpt-5.4:medium": "OpenAI Codex GPT-5.4 — medium reasoning",
        "openai-codex/gpt-5.5:medium": "OpenAI Codex GPT-5.5 — medium reasoning",
        "openai-codex/gpt-5.5:high": "OpenAI Codex GPT-5.5 — high reasoning",
    }
    return labels.get(model_arg, model_arg)


def fmt_num(value: object, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return str(value)


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def runtime_build_label(value: object) -> str:
    return str(value) if value else "n/a"


def latest_normalized_rows(conn: sqlite3.Connection, tasks: list[str]) -> list[sqlite3.Row]:
    placeholders = ",".join("?" for _ in tasks)
    return conn.execute(
        f"""
        WITH latest AS (
            SELECT m.model_arg,
                   COALESCE(rm.runtime_build, rm.llama_cpp_build, rm.runtime_label, 'n/a') AS runtime_build,
                   t.name AS task, MAX(res.id) AS result_id
            FROM results res
            JOIN run_models rm ON rm.id = res.run_model_id
            JOIN models m ON m.id = rm.model_id
            JOIN tasks t ON t.id = res.task_id
            WHERE t.name IN ({placeholders})
            GROUP BY m.model_arg, COALESCE(rm.runtime_build, rm.llama_cpp_build, rm.runtime_label, 'n/a'), t.name
        )
        SELECT latest.model_arg, latest.runtime_build, latest.task, res.ok, res.score, res.total,
               res.wall_s, res.approx_output_tps,
               COALESCE(CAST(rm.context_size AS TEXT), m.context_window_label) AS context_window_label,
               m.max_output_label
        FROM latest
        JOIN results res ON res.id = latest.result_id
        JOIN run_models rm ON rm.id = res.run_model_id
        JOIN models m ON m.id = rm.model_id
        ORDER BY latest.model_arg, latest.runtime_build, latest.task
        """,
        tasks,
    ).fetchall()


def append_normalized_section(lines: list[str], conn: sqlite3.Connection, title: str, tasks: list[str], description: str) -> None:
    rows = latest_normalized_rows(conn, tasks)
    by_model: dict[tuple[str, str], list[sqlite3.Row]] = {}
    for row in rows:
        by_model.setdefault((row["model_arg"], row["runtime_build"] or "n/a"), []).append(row)

    summary = []
    for (model_arg, runtime_build), model_rows in by_model.items():
        covered = {r["task"] for r in model_rows}
        if not all(task in covered for task in tasks):
            continue
        passed = sum(1 for r in model_rows if r["ok"])
        score = sum(r["score"] or 0 for r in model_rows)
        points = sum(r["total"] or 0 for r in model_rows)
        weighted_score = 0.0
        weighted_total = 0.0
        for r in model_rows:
            weight = TASK_WEIGHTS.get(r["task"], 1.0)
            weighted_total += weight
            if r["total"]:
                weighted_score += ((r["score"] or 0) / r["total"]) * weight
            else:
                weighted_score += (1.0 if r["ok"] else 0.0) * weight
        avg_wall = sum(r["wall_s"] for r in model_rows) / len(model_rows)
        avg_tps = sum((r["approx_output_tps"] or 0) for r in model_rows) / len(model_rows)
        context = model_rows[0]["context_window_label"] or "n/a"
        max_out = model_rows[0]["max_output_label"] or "n/a"
        summary.append((weighted_score / weighted_total, weighted_score, weighted_total, model_arg, runtime_build, context, max_out, passed, len(model_rows), score, points, avg_wall, avg_tps))

    summary.sort(key=lambda x: (-x[0], x[11]))
    lines += [
        f"## {title}",
        "",
        description + " It uses the latest result for each model on the same tasks: "
        + ", ".join(f"`{task}`" for task in tasks)
        + "."
        "",
        "| rank | model | exact Pi model argument | runtime build | context | max out | pass | raw points | weighted score | avg wall s | approx output tok/s |",
        "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for i, (_, weighted_score, weighted_total, model_arg, runtime_build, context, max_out, passed, total, score, points, avg_wall, avg_tps) in enumerate(summary, 1):
        lines.append(
            f"| {i} | {model_label(model_arg)} | `{model_arg}` | {runtime_build_label(runtime_build)} | {context} | {max_out} | {passed}/{total} | {score:.0f}/{points:.0f} | {fmt_num(weighted_score, 1)}/{fmt_num(weighted_total, 1)} | {fmt_num(avg_wall)} | {fmt_num(avg_tps, 1)} |"
        )
    lines += [
        "",
        "Note: local Qwen `:medium` means Qwen chat-template thinking is enabled; it is not directly equivalent to OpenAI `reasoning.effort=medium`.",
        "",
    ]


def generate(conn: sqlite3.Connection) -> str:
    lines: list[str] = [
        "# PiBench integrated report",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "This report is generated from `results/pibench.sqlite` and combines benchmark runs recorded by `pi_agent_bench.py`.",
        "",
    ]
    append_normalized_section(
        lines,
        conn,
        "Normalized full-16 comparison",
        NORMALIZED_FULL_16,
        "This is the main apples-to-apples leaderboard for the full current PiBench suite.",
    )
    append_normalized_section(
        lines,
        conn,
        "Normalized expanded-24 comparison",
        NORMALIZED_EXPANDED_24,
        "This is the expanded apples-to-apples leaderboard including coding, sysadmin, documentation, project-management, and architecture tasks.",
    )
    append_normalized_section(
        lines,
        conn,
        "Normalized non-coding-8 comparison",
        NORMALIZED_NONCODING_8,
        "This is the focused apples-to-apples table for the new non-coding agent tasks: sysadmin, documentation, project management, and architecture/design review.",
    )
    append_normalized_section(
        lines,
        conn,
        "Normalized hard-5 comparison",
        NORMALIZED_HARD_5,
        "This is the focused apples-to-apples table for the hardest shared subset.",
    )
    lines += [
        "## Historical aggregate by model",
        "",
        "| model | exact Pi model argument | runtime build | context | max out | runs | pass | scored points | weighted score | avg wall s | approx output tok/s |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"
    ]

    for row in conn.execute(
        f"""
        SELECT m.model_arg,
               COALESCE(rm.runtime_build, rm.llama_cpp_build, rm.runtime_label, 'n/a') AS runtime_build,
               COUNT(DISTINCT r.id) AS runs,
               SUM(res.ok) AS passed,
               COUNT(*) AS total,
               SUM(COALESCE(res.score, 0)) AS score,
               SUM(COALESCE(res.total, 0)) AS points,
               {weighted_score_expr()} AS weighted_score,
               {weighted_total_expr()} AS weighted_total,
               AVG(res.wall_s) AS avg_wall_s,
               AVG(res.approx_output_tps) AS avg_tps,
               COALESCE(CAST(rm.context_size AS TEXT), m.context_window_label) AS context_window_label,
               m.max_output_label
        FROM results res
        JOIN runs r ON r.id = res.run_id
        JOIN run_models rm ON rm.id = res.run_model_id
        JOIN models m ON m.id = rm.model_id
        JOIN tasks t ON t.id = res.task_id
        GROUP BY m.model_arg, COALESCE(rm.runtime_build, rm.llama_cpp_build, rm.runtime_label, 'n/a')
        ORDER BY weighted_score * 1.0 / weighted_total DESC,
                 AVG(res.wall_s) ASC
        """
    ):
        points = f"{row['score']:.0f}/{row['points']:.0f}" if row["points"] else "n/a"
        weighted = f"{fmt_num(row['weighted_score'], 1)}/{fmt_num(row['weighted_total'], 1)}"
        lines.append(
            f"| {model_label(row['model_arg'])} | `{row['model_arg']}` | {runtime_build_label(row['runtime_build'])} | {row['context_window_label'] or 'n/a'} | {row['max_output_label'] or 'n/a'} | {row['runs']} | {row['passed']}/{row['total']} | {points} | {weighted} | {fmt_num(row['avg_wall_s'])} | {fmt_num(row['avg_tps'], 1)} |"
        )

    lines += [
        "",
        "## Latest runs",
        "",
        "| run | started | notes | model | exact Pi model argument | runtime build | context | pass | scored points | weighted score | avg wall s |",
        "|---:|---|---|---|---|---|---:|---:|---:|---:|---:|"
    ]
    for row in conn.execute(
        f"""
        SELECT r.id AS run_id, r.started_at, COALESCE(r.notes, '') AS notes, m.model_arg,
               COALESCE(rm.runtime_build, rm.llama_cpp_build, rm.runtime_label, 'n/a') AS runtime_build,
               SUM(res.ok) AS passed, COUNT(*) AS total,
               SUM(COALESCE(res.score, 0)) AS score,
               SUM(COALESCE(res.total, 0)) AS points,
               {weighted_score_expr()} AS weighted_score,
               {weighted_total_expr()} AS weighted_total,
               AVG(res.wall_s) AS avg_wall_s,
               COALESCE(CAST(rm.context_size AS TEXT), m.context_window_label) AS context_window_label
        FROM results res
        JOIN runs r ON r.id = res.run_id
        JOIN run_models rm ON rm.id = res.run_model_id
        JOIN models m ON m.id = rm.model_id
        JOIN tasks t ON t.id = res.task_id
        GROUP BY r.id, m.model_arg, COALESCE(rm.runtime_build, rm.llama_cpp_build, rm.runtime_label, 'n/a')
        ORDER BY r.id DESC, m.model_arg
        LIMIT 40
        """
    ):
        points = f"{row['score']:.0f}/{row['points']:.0f}" if row["points"] else "n/a"
        weighted = f"{fmt_num(row['weighted_score'], 1)}/{fmt_num(row['weighted_total'], 1)}"
        lines.append(
            f"| {row['run_id']} | {row['started_at']} | {row['notes']} | {model_label(row['model_arg'])} | `{row['model_arg']}` | {runtime_build_label(row['runtime_build'])} | {row['context_window_label'] or 'n/a'} | {row['passed']}/{row['total']} | {points} | {weighted} | {fmt_num(row['avg_wall_s'])} |"
        )

    lines += [
        "",
        "## Task matrix",
        "",
        "| task | weight | model | exact Pi model argument | runtime build | context | pass | scored points | weighted score | avg wall s | common failure notes |",
        "|---|---:|---|---|---|---:|---:|---:|---:|---:|---|"
    ]
    for row in conn.execute(
        f"""
        SELECT t.name AS task, {weight_case('t')} AS weight, m.model_arg,
               COALESCE(rm.runtime_build, rm.llama_cpp_build, rm.runtime_label, 'n/a') AS runtime_build,
               SUM(res.ok) AS passed, COUNT(*) AS total,
               SUM(COALESCE(res.score, 0)) AS score,
               SUM(COALESCE(res.total, 0)) AS points,
               {weighted_score_expr()} AS weighted_score,
               {weighted_total_expr()} AS weighted_total,
               AVG(res.wall_s) AS avg_wall_s,
               GROUP_CONCAT(CASE WHEN res.ok = 0 THEN res.note ELSE NULL END, '; ') AS notes,
               COALESCE(CAST(rm.context_size AS TEXT), m.context_window_label) AS context_window_label
        FROM results res
        JOIN tasks t ON t.id = res.task_id
        JOIN run_models rm ON rm.id = res.run_model_id
        JOIN models m ON m.id = rm.model_id
        GROUP BY t.name, m.model_arg, COALESCE(rm.runtime_build, rm.llama_cpp_build, rm.runtime_label, 'n/a')
        ORDER BY t.name, m.model_arg, COALESCE(rm.runtime_build, rm.llama_cpp_build, rm.runtime_label, 'n/a')
        """
    ):
        points = f"{row['score']:.0f}/{row['points']:.0f}" if row["points"] else "n/a"
        notes = sanitize_notes((row["notes"] or "").replace("\n", " "))[:160]
        weighted = f"{fmt_num(row['weighted_score'], 1)}/{fmt_num(row['weighted_total'], 1)}"
        lines.append(
            f"| `{row['task']}` | {fmt_num(row['weight'], 1)} | {model_label(row['model_arg'])} | `{row['model_arg']}` | {runtime_build_label(row['runtime_build'])} | {row['context_window_label'] or 'n/a'} | {row['passed']}/{row['total']} | {points} | {weighted} | {fmt_num(row['avg_wall_s'])} | {notes} |"
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate integrated PiBench reports")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Markdown report path")
    parser.add_argument("--csv-out", help="optional sanitized task-level CSV path")
    args = parser.parse_args()

    conn = connect(Path(args.db))
    md = generate(conn)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md)
    print(f"Wrote {out}")
    if args.csv_out:
        csv_out = Path(args.csv_out)
        count = export_public_csv(conn, csv_out)
        print(f"Wrote {csv_out} ({count} task results)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
