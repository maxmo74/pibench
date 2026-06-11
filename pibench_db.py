#!/usr/bin/env python3
"""SQLite storage helpers for PiBench results."""

from __future__ import annotations

import json
import os
import platform
import re
import socket
import sqlite3
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "results" / "pibench.sqlite"
SCHEMA_VERSION = 2


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def run_cmd(cmd: list[str], timeout: int = 10) -> str | None:
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
        out = (proc.stdout + proc.stderr).strip()
        return out or None
    except Exception:
        return None


def collect_host_metadata() -> dict[str, Any]:
    meta: dict[str, Any] = {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
    }
    if meminfo := Path("/proc/meminfo"):
        try:
            for line in meminfo.read_text().splitlines():
                if line.startswith("MemTotal:"):
                    meta["mem_total_kb"] = int(line.split()[1])
                    break
        except Exception:
            pass
    lscpu = run_cmd(["lscpu"])
    if lscpu:
        for line in lscpu.splitlines():
            if line.startswith("Model name:"):
                meta["cpu_model"] = line.split(":", 1)[1].strip()
            elif line.startswith("CPU(s):"):
                try:
                    meta["logical_cpus"] = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
    gpu = run_cmd(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"])
    if gpu:
        meta["nvidia_gpus"] = [line.strip() for line in gpu.splitlines() if line.strip()]
    return meta


def get_pi_version() -> str | None:
    return run_cmd(["pi", "--version"])


def get_git_commit() -> str | None:
    return run_cmd(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"])


def split_model_arg(model_arg: str) -> dict[str, Any]:
    # Pi accepts provider/model:thinking. Model IDs themselves can contain ':' in
    # theory, but current Pi model shorthand uses the final suffix for thinking.
    thinking = None
    base = model_arg
    if ":" in model_arg:
        maybe_base, maybe_thinking = model_arg.rsplit(":", 1)
        if maybe_thinking in {"off", "minimal", "low", "medium", "high", "xhigh"}:
            base = maybe_base
            thinking = maybe_thinking
    if "/" in base:
        provider, model_id = base.split("/", 1)
    else:
        provider, model_id = None, base
    return {"provider": provider, "model_id": model_id, "thinking_requested": thinking}


def parse_pi_list_models(model_id: str) -> dict[str, Any]:
    out = run_cmd(["pi", "--list-models", model_id], timeout=30)
    if not out:
        return {}
    lines = [line for line in out.splitlines() if line.strip()]
    if len(lines) < 2:
        return {"raw": out}
    # pi --list-models emits whitespace-aligned columns:
    # provider model context max-out thinking images
    parts = lines[1].split()
    if len(parts) < 6:
        return {"raw": out}
    return {
        "provider": parts[0],
        "model_id": parts[1],
        "context": parts[2],
        "max_out": parts[3],
        "thinking": parts[4],
        "images": parts[5],
        "raw": out,
    }


def infer_effective_thinking(model_arg: str, metadata: dict[str, Any]) -> str | None:
    parsed = split_model_arg(model_arg)
    requested = parsed.get("thinking_requested")
    provider = parsed.get("provider") or metadata.get("provider")
    model_id = parsed.get("model_id") or metadata.get("model_id")
    if requested is None:
        return None
    if provider and provider.startswith("local-llama"):
        if requested == "off":
            return "qwen-chat-template:enable_thinking=false"
        # Current local Qwen config uses qwen-chat-template, where Pi/llama.cpp
        # receives a boolean, not a graded effort. medium/high/xhigh are therefore
        # best interpreted as thinking enabled unless model-specific handling changes.
        return "qwen-chat-template:enable_thinking=true"
    if provider == "openai-codex":
        mapping = {"minimal": "low", "xhigh": "xhigh"}
        return f"openai-responses:reasoning.effort={mapping.get(requested, requested)}"
    return requested


def read_models_config(provider: str | None, model_id: str | None) -> dict[str, Any]:
    if not provider or not model_id:
        return {}
    for path in [Path.home() / ".pi/agent/models.json"]:
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        provider_cfg = data.get("providers", {}).get(provider)
        if not provider_cfg:
            continue
        for model_cfg in provider_cfg.get("models", []):
            if model_cfg.get("id") == model_id:
                return {"provider_config": provider_cfg, "model_config": model_cfg, "config_path": str(path)}
    return {}


def infer_llama_server_path(provider: str | None, provider_cfg: dict[str, Any], model_cfg: dict[str, Any]) -> str | None:
    if override := os.environ.get("PIBENCH_LLAMA_SERVER_PATH"):
        return override
    if not provider or not provider.startswith("local-llama"):
        return None
    metadata = model_cfg.get("metadata", {}) if isinstance(model_cfg, dict) else {}
    build_hint = str(metadata.get("llamaCppBuild") or metadata.get("runtime") or provider)
    if "llama.cpp-latest" in build_hint or "latest llama.cpp" in build_hint or provider.startswith("local-llama-latest"):
        return "/opt/llama.cpp-latest/build/bin/llama-server"
    return "/opt/llama.cpp/build/bin/llama-server"


def parse_llama_version_output(output: str | None) -> dict[str, str | None]:
    if not output:
        return {"version": None, "commit": None, "build": None}
    first = output.splitlines()[0] if output.splitlines() else output
    match = re.search(r"version:\s*([0-9]+)\s*\(([0-9a-fA-F]+)\)", output)
    if match:
        version, commit = match.groups()
        return {"version": version, "commit": commit, "build": f"llama.cpp b{version} ({commit})"}
    return {"version": None, "commit": None, "build": first.strip() or None}


def git_commit_date_for_server(path: str | None, commit: str | None) -> str | None:
    if not path or not commit:
        return None
    server = Path(path)
    # /opt/llama.cpp[-latest]/build/bin/llama-server -> repo root
    try:
        repo = server.parents[2]
    except Exception:
        return None
    return run_cmd(["git", "-C", str(repo), "show", "-s", "--format=%cI", commit], timeout=10)


def collect_runtime_metadata(model_arg: str) -> dict[str, Any]:
    parsed = split_model_arg(model_arg)
    provider = parsed.get("provider")
    model_id = parsed.get("model_id")
    cfg = read_models_config(provider, model_id)
    provider_cfg = cfg.get("provider_config", {})
    model_cfg = cfg.get("model_config", {})
    metadata = model_cfg.get("metadata", {}) if isinstance(model_cfg, dict) else {}
    server_path = infer_llama_server_path(provider, provider_cfg, model_cfg)
    version_info = parse_llama_version_output(run_cmd([server_path, "--version"], timeout=10) if server_path else None)
    commit_date = git_commit_date_for_server(server_path, version_info.get("commit"))
    runtime_label = metadata.get("runtime") or ("llama.cpp" if server_path else None)
    result: dict[str, Any] = {
        "provider": provider,
        "model_id": model_id,
        "base_url": provider_cfg.get("baseUrl") if isinstance(provider_cfg, dict) else None,
        "runtime_label": runtime_label,
        "llama_server_path": server_path,
        "llama_cpp_version": version_info.get("version"),
        "llama_cpp_commit": version_info.get("commit"),
        "llama_cpp_build": version_info.get("build"),
        "llama_cpp_commit_date": commit_date,
        "model_metadata": metadata,
        "config_path": cfg.get("config_path"),
    }
    return {k: v for k, v in result.items() if v is not None}


def connect(path: Path | str = DEFAULT_DB) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)
    return conn


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}


def add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, decl: str) -> None:
    if column not in table_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_info (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_uuid TEXT NOT NULL UNIQUE,
            benchmark_name TEXT NOT NULL,
            benchmark_version INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            pi_version TEXT,
            pibench_commit TEXT,
            command_json TEXT,
            config_json TEXT,
            host_json TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT,
            model_id TEXT NOT NULL,
            model_arg TEXT NOT NULL,
            thinking_requested TEXT,
            thinking_effective TEXT,
            context_window_label TEXT,
            max_output_label TEXT,
            supports_thinking TEXT,
            supports_images TEXT,
            metadata_json TEXT,
            UNIQUE(model_arg, thinking_effective)
        );

        CREATE TABLE IF NOT EXISTS run_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
            model_id INTEGER NOT NULL REFERENCES models(id),
            runtime_label TEXT,
            llama_cpp_version TEXT,
            llama_cpp_build TEXT,
            llama_cpp_commit TEXT,
            llama_cpp_commit_date TEXT,
            llama_server_path TEXT,
            runtime_json TEXT,
            UNIQUE(run_id, model_id)
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            category TEXT,
            check_kind TEXT,
            prompt TEXT NOT NULL,
            metadata_json TEXT
        );

        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
            run_model_id INTEGER NOT NULL REFERENCES run_models(id) ON DELETE CASCADE,
            task_id INTEGER NOT NULL REFERENCES tasks(id),
            started_at TEXT,
            ended_at TEXT,
            ok INTEGER NOT NULL,
            score REAL,
            total REAL,
            wall_s REAL NOT NULL,
            returncode INTEGER,
            approx_output_tokens INTEGER,
            approx_output_tps REAL,
            note TEXT,
            checks_json TEXT,
            stdout TEXT,
            stderr TEXT,
            raw_json TEXT,
            UNIQUE(run_id, run_model_id, task_id)
        );

        CREATE INDEX IF NOT EXISTS idx_results_task ON results(task_id);
        CREATE INDEX IF NOT EXISTS idx_results_run_model ON results(run_model_id);
        CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at);
        """
    )
    for column, decl in [
        ("runtime_label", "TEXT"),
        ("llama_cpp_version", "TEXT"),
        ("llama_cpp_build", "TEXT"),
        ("llama_cpp_commit", "TEXT"),
        ("llama_cpp_commit_date", "TEXT"),
        ("llama_server_path", "TEXT"),
        ("runtime_json", "TEXT"),
    ]:
        add_column_if_missing(conn, "run_models", column, decl)
    conn.execute(
        "INSERT OR IGNORE INTO schema_info(version, applied_at) VALUES (?, ?)",
        (SCHEMA_VERSION, utc_now()),
    )
    conn.commit()


def create_run(conn: sqlite3.Connection, benchmark_name: str, command: list[str], config: dict[str, Any], notes: str | None = None) -> int:
    cur = conn.execute(
        """
        INSERT INTO runs(run_uuid, benchmark_name, benchmark_version, started_at, pi_version, pibench_commit, command_json, config_json, host_json, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            benchmark_name,
            SCHEMA_VERSION,
            utc_now(),
            get_pi_version(),
            get_git_commit(),
            json_dumps(command),
            json_dumps(config),
            json_dumps(collect_host_metadata()),
            notes,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def finish_run(conn: sqlite3.Connection, run_id: int) -> None:
    conn.execute("UPDATE runs SET ended_at = ? WHERE id = ?", (utc_now(), run_id))
    conn.commit()


def upsert_task(conn: sqlite3.Connection, name: str, prompt: str, check_kind: str, category: str | None = None, metadata: dict[str, Any] | None = None) -> int:
    conn.execute(
        """
        INSERT INTO tasks(name, category, check_kind, prompt, metadata_json)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            category=excluded.category,
            check_kind=excluded.check_kind,
            prompt=excluded.prompt,
            metadata_json=excluded.metadata_json
        """,
        (name, category, check_kind, prompt, json_dumps(metadata or {})),
    )
    row = conn.execute("SELECT id FROM tasks WHERE name = ?", (name,)).fetchone()
    assert row is not None
    return int(row["id"])


def upsert_model(conn: sqlite3.Connection, model_arg: str) -> int:
    parsed = split_model_arg(model_arg)
    metadata = parse_pi_list_models(parsed["model_id"])
    provider = parsed.get("provider") or metadata.get("provider")
    model_id = parsed.get("model_id") or metadata.get("model_id") or model_arg
    thinking_requested = parsed.get("thinking_requested")
    thinking_effective = infer_effective_thinking(model_arg, metadata)
    conn.execute(
        """
        INSERT INTO models(provider, model_id, model_arg, thinking_requested, thinking_effective, context_window_label, max_output_label, supports_thinking, supports_images, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(model_arg, thinking_effective) DO UPDATE SET
            provider=excluded.provider,
            model_id=excluded.model_id,
            thinking_requested=excluded.thinking_requested,
            context_window_label=excluded.context_window_label,
            max_output_label=excluded.max_output_label,
            supports_thinking=excluded.supports_thinking,
            supports_images=excluded.supports_images,
            metadata_json=excluded.metadata_json
        """,
        (
            provider,
            model_id,
            model_arg,
            thinking_requested,
            thinking_effective,
            metadata.get("context"),
            metadata.get("max_out"),
            metadata.get("thinking"),
            metadata.get("images"),
            json_dumps(metadata),
        ),
    )
    row = conn.execute(
        "SELECT id FROM models WHERE model_arg = ? AND COALESCE(thinking_effective, '') = COALESCE(?, '')",
        (model_arg, thinking_effective),
    ).fetchone()
    assert row is not None
    return int(row["id"])


def attach_model_to_run(conn: sqlite3.Connection, run_id: int, model_db_id: int, model_arg: str | None = None) -> int:
    runtime = collect_runtime_metadata(model_arg) if model_arg else {}
    conn.execute(
        """
        INSERT OR IGNORE INTO run_models(run_id, model_id, runtime_label, llama_cpp_version, llama_cpp_build, llama_cpp_commit, llama_cpp_commit_date, llama_server_path, runtime_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            model_db_id,
            runtime.get("runtime_label"),
            runtime.get("llama_cpp_version"),
            runtime.get("llama_cpp_build"),
            runtime.get("llama_cpp_commit"),
            runtime.get("llama_cpp_commit_date"),
            runtime.get("llama_server_path"),
            json_dumps(runtime),
        ),
    )
    conn.execute(
        """
        UPDATE run_models
        SET runtime_label = COALESCE(?, runtime_label),
            llama_cpp_version = COALESCE(?, llama_cpp_version),
            llama_cpp_build = COALESCE(?, llama_cpp_build),
            llama_cpp_commit = COALESCE(?, llama_cpp_commit),
            llama_cpp_commit_date = COALESCE(?, llama_cpp_commit_date),
            llama_server_path = COALESCE(?, llama_server_path),
            runtime_json = COALESCE(?, runtime_json)
        WHERE run_id = ? AND model_id = ?
        """,
        (
            runtime.get("runtime_label"),
            runtime.get("llama_cpp_version"),
            runtime.get("llama_cpp_build"),
            runtime.get("llama_cpp_commit"),
            runtime.get("llama_cpp_commit_date"),
            runtime.get("llama_server_path"),
            json_dumps(runtime) if runtime else None,
            run_id,
            model_db_id,
        ),
    )
    row = conn.execute("SELECT id FROM run_models WHERE run_id = ? AND model_id = ?", (run_id, model_db_id)).fetchone()
    assert row is not None
    return int(row["id"])


def insert_result(conn: sqlite3.Connection, run_id: int, run_model_id: int, task_id: int, row: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO results(
            run_id, run_model_id, task_id, started_at, ended_at, ok, score, total,
            wall_s, returncode, approx_output_tokens, approx_output_tps, note,
            checks_json, stdout, stderr, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            run_model_id,
            task_id,
            row.get("started_at"),
            row.get("ended_at"),
            1 if row.get("ok") else 0,
            row.get("score"),
            row.get("total"),
            row.get("wall_s"),
            row.get("returncode"),
            row.get("approx_output_tokens"),
            row.get("approx_output_tps"),
            row.get("note"),
            json_dumps(row.get("checks", {})),
            row.get("stdout"),
            row.get("stderr"),
            json_dumps(row),
        ),
    )
    conn.commit()


def summarize_latest(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT r.id AS run_id, r.started_at, m.model_arg,
               SUM(res.ok) AS passed, COUNT(*) AS total,
               AVG(res.wall_s) AS avg_wall_s,
               AVG(res.approx_output_tps) AS avg_approx_output_tps
        FROM runs r
        JOIN run_models rm ON rm.run_id = r.id
        JOIN models m ON m.id = rm.model_id
        JOIN results res ON res.run_model_id = rm.id
        GROUP BY r.id, m.id
        ORDER BY r.id DESC, m.model_arg
        LIMIT 20
        """
    ).fetchall()


def main() -> int:
    conn = connect()
    print(f"database: {DEFAULT_DB}")
    for row in summarize_latest(conn):
        print(
            f"run={row['run_id']} {row['started_at']} model={row['model_arg']} "
            f"pass={row['passed']}/{row['total']} avg_wall={row['avg_wall_s']:.2f}s "
            f"approx_tps={row['avg_approx_output_tps']:.1f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
