#!/usr/bin/env python3
"""Generate integrated Markdown reports from the PiBench SQLite database."""

from __future__ import annotations

import argparse
import re
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "results" / "pibench.sqlite"
DEFAULT_OUT = ROOT / "results" / "INTEGRATED_REPORT.md"

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
    return conn


def generate(conn: sqlite3.Connection) -> str:
    lines: list[str] = [
        "# PiBench integrated report",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "This report is generated from `results/pibench.sqlite` and combines benchmark runs recorded by `pi_agent_bench.py`.",
        "",
        "## Overall by model",
        "",
        "| model | runs | pass | scored points | weighted score | avg wall s | approx output tok/s |",
        "|---|---:|---:|---:|---:|---:|---:|"
    ]

    for row in conn.execute(
        f"""
        SELECT m.model_arg,
               COUNT(DISTINCT r.id) AS runs,
               SUM(res.ok) AS passed,
               COUNT(*) AS total,
               SUM(COALESCE(res.score, 0)) AS score,
               SUM(COALESCE(res.total, 0)) AS points,
               {weighted_score_expr()} AS weighted_score,
               {weighted_total_expr()} AS weighted_total,
               AVG(res.wall_s) AS avg_wall_s,
               AVG(res.approx_output_tps) AS avg_tps
        FROM results res
        JOIN runs r ON r.id = res.run_id
        JOIN run_models rm ON rm.id = res.run_model_id
        JOIN models m ON m.id = rm.model_id
        JOIN tasks t ON t.id = res.task_id
        GROUP BY m.model_arg
        ORDER BY weighted_score * 1.0 / weighted_total DESC,
                 AVG(res.wall_s) ASC
        """
    ):
        points = f"{row['score']:.0f}/{row['points']:.0f}" if row["points"] else "n/a"
        weighted = f"{fmt_num(row['weighted_score'], 1)}/{fmt_num(row['weighted_total'], 1)}"
        lines.append(
            f"| `{row['model_arg']}` | {row['runs']} | {row['passed']}/{row['total']} | {points} | {weighted} | {fmt_num(row['avg_wall_s'])} | {fmt_num(row['avg_tps'], 1)} |"
        )

    lines += [
        "",
        "## Latest runs",
        "",
        "| run | started | notes | model | pass | scored points | weighted score | avg wall s |",
        "|---:|---|---|---|---:|---:|---:|---:|"
    ]
    for row in conn.execute(
        f"""
        SELECT r.id AS run_id, r.started_at, COALESCE(r.notes, '') AS notes, m.model_arg,
               SUM(res.ok) AS passed, COUNT(*) AS total,
               SUM(COALESCE(res.score, 0)) AS score,
               SUM(COALESCE(res.total, 0)) AS points,
               {weighted_score_expr()} AS weighted_score,
               {weighted_total_expr()} AS weighted_total,
               AVG(res.wall_s) AS avg_wall_s
        FROM results res
        JOIN runs r ON r.id = res.run_id
        JOIN run_models rm ON rm.id = res.run_model_id
        JOIN models m ON m.id = rm.model_id
        JOIN tasks t ON t.id = res.task_id
        GROUP BY r.id, m.model_arg
        ORDER BY r.id DESC, m.model_arg
        LIMIT 40
        """
    ):
        points = f"{row['score']:.0f}/{row['points']:.0f}" if row["points"] else "n/a"
        weighted = f"{fmt_num(row['weighted_score'], 1)}/{fmt_num(row['weighted_total'], 1)}"
        lines.append(
            f"| {row['run_id']} | {row['started_at']} | {row['notes']} | `{row['model_arg']}` | {row['passed']}/{row['total']} | {points} | {weighted} | {fmt_num(row['avg_wall_s'])} |"
        )

    lines += [
        "",
        "## Task matrix",
        "",
        "| task | weight | model | pass | scored points | weighted score | avg wall s | common failure notes |",
        "|---|---:|---|---:|---:|---:|---:|---|"
    ]
    for row in conn.execute(
        f"""
        SELECT t.name AS task, {weight_case('t')} AS weight, m.model_arg,
               SUM(res.ok) AS passed, COUNT(*) AS total,
               SUM(COALESCE(res.score, 0)) AS score,
               SUM(COALESCE(res.total, 0)) AS points,
               {weighted_score_expr()} AS weighted_score,
               {weighted_total_expr()} AS weighted_total,
               AVG(res.wall_s) AS avg_wall_s,
               GROUP_CONCAT(CASE WHEN res.ok = 0 THEN res.note ELSE NULL END, '; ') AS notes
        FROM results res
        JOIN tasks t ON t.id = res.task_id
        JOIN run_models rm ON rm.id = res.run_model_id
        JOIN models m ON m.id = rm.model_id
        GROUP BY t.name, m.model_arg
        ORDER BY t.name, m.model_arg
        """
    ):
        points = f"{row['score']:.0f}/{row['points']:.0f}" if row["points"] else "n/a"
        notes = sanitize_notes((row["notes"] or "").replace("\n", " "))[:160]
        weighted = f"{fmt_num(row['weighted_score'], 1)}/{fmt_num(row['weighted_total'], 1)}"
        lines.append(
            f"| `{row['task']}` | {fmt_num(row['weight'], 1)} | `{row['model_arg']}` | {row['passed']}/{row['total']} | {points} | {weighted} | {fmt_num(row['avg_wall_s'])} | {notes} |"
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate integrated PiBench Markdown report")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    conn = connect(Path(args.db))
    md = generate(conn)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
