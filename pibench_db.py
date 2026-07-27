#!/usr/bin/env python3
"""SQLite storage helpers for PiBench results."""

from __future__ import annotations

import json
import os
import platform
import re
import sqlite3
import subprocess
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "results" / "pibench.sqlite"
SCHEMA_VERSION = 3


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def merge_dicts(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge JSON-like dictionaries without modifying either input."""
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def run_cmd(cmd: list[str], timeout: int = 10) -> str | None:
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
        if proc.returncode != 0:
            return None
        out = (proc.stdout + proc.stderr).strip()
        return out or None
    except Exception:
        return None


def collect_host_metadata() -> dict[str, Any]:
    """Collect portable host facts without recording the machine's hostname."""
    meta: dict[str, Any] = {
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
    }
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                meta["mem_total_kb"] = int(line.split()[1])
                break
    except Exception:
        pass

    lscpu = run_cmd(["lscpu"])
    if lscpu:
        for line in lscpu.splitlines():
            key, separator, value = line.partition(":")
            if not separator:
                continue
            value = value.strip()
            if key == "Model name":
                meta["cpu_model"] = value
            elif key == "CPU(s)":
                try:
                    meta["logical_cpus"] = int(value)
                except ValueError:
                    pass
            elif key == "Core(s) per socket":
                try:
                    meta["cores_per_socket"] = int(value)
                except ValueError:
                    pass
            elif key == "Socket(s)":
                try:
                    meta["cpu_sockets"] = int(value)
                except ValueError:
                    pass

    gpu = run_cmd(
        [
            "nvidia-smi",
            "--query-gpu=index,name,memory.total,driver_version,compute_cap",
            "--format=csv,noheader,nounits",
        ]
    )
    include_compute_capability = True
    if not gpu:
        gpu = run_cmd(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ]
        )
        include_compute_capability = False
    if gpu:
        accelerators = []
        for line in gpu.splitlines():
            parts = [part.strip() for part in line.split(",")]
            expected = 5 if include_compute_capability else 4
            if len(parts) == expected:
                item = {
                    "index": parts[0],
                    "vendor": "NVIDIA",
                    "name": parts[1],
                    "memory_mib": parts[2],
                    "driver_version": parts[3],
                }
                if include_compute_capability:
                    item["compute_capability"] = parts[4]
                accelerators.append(item)
        if accelerators:
            meta["accelerators_detected"] = accelerators
            # Retained for compatibility with schema-v2 databases and reports.
            meta["nvidia_gpus"] = [
                f"{item['name']}, {item['memory_mib']} MiB, driver {item['driver_version']}"
                for item in accelerators
            ]

    if nvcc := run_cmd(["nvcc", "--version"]):
        match = re.search(r"release\s+([^,\s]+)", nvcc)
        if match:
            meta["cuda_toolkit_version"] = match.group(1)
    try:
        rocm_version = Path("/opt/rocm/.info/version").read_text().strip()
        if rocm_version:
            meta["rocm_version"] = rocm_version
    except Exception:
        pass
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
    # Model IDs may contain spaces. The provider is the first field and the
    # four capability fields are always at the right edge of the table.
    return {
        "provider": parts[0],
        "model_id": " ".join(parts[1:-4]),
        "context": parts[-4],
        "max_out": parts[-3],
        "thinking": parts[-2],
        "images": parts[-1],
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


def router_model_status(base_url: str | None, model_id: str | None) -> dict[str, Any]:
    """Return a matching loopback router model entry, including launch arguments."""
    if not base_url or not model_id:
        return {}
    parsed = urllib.parse.urlparse(base_url)
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        return {}
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/models", timeout=5) as response:
            data = json.load(response).get("data", [])
    except Exception:
        return {}
    for item in data:
        if not isinstance(item, dict):
            continue
        aliases = item.get("aliases") or []
        if item.get("id") == model_id or model_id in aliases:
            return item if isinstance(item, dict) else {}
    return {}


def router_llama_server_path(base_url: str | None, model_id: str | None) -> str | None:
    """Discover the backing llama-server binary from a loopback router."""
    status = router_model_status(base_url, model_id)
    args = (status.get("status") or {}).get("args") or []
    if not args:
        return None
    candidate = Path(str(args[0]))
    return str(candidate) if candidate.name == "llama-server" and candidate.is_file() else None


def infer_llama_server_path(
    provider: str | None,
    provider_cfg: dict[str, Any],
    model_cfg: dict[str, Any],
    model_id: str | None,
    router_status: dict[str, Any] | None = None,
) -> str | None:
    if override := os.environ.get("PIBENCH_LLAMA_SERVER_PATH"):
        return override
    if not provider or not provider.startswith("local-llama"):
        return None
    metadata = model_cfg.get("metadata", {}) if isinstance(model_cfg, dict) else {}
    for key in ("llamaServerPath", "llama_server_path", "serverPath"):
        if value := metadata.get(key):
            candidate = Path(str(value))
            if candidate.name == "llama-server" and candidate.is_file():
                return str(candidate)
    args = ((router_status or {}).get("status") or {}).get("args") or []
    if args:
        candidate = Path(str(args[0]))
        if candidate.name == "llama-server" and candidate.is_file():
            return str(candidate)
    return router_llama_server_path(provider_cfg.get("baseUrl"), model_id)


def parse_llama_version_output(output: str | None) -> dict[str, str | None]:
    if not output:
        return {"version": None, "commit": None, "build": None, "compiler": None, "target": None}
    first = output.splitlines()[0] if output.splitlines() else output
    match = re.search(r"version:\s*([0-9]+)\s*\(([0-9a-fA-F]+)\)", output)
    compiler_match = re.search(r"built with\s+(.+?)\s+for\s+(.+?)(?:\n|$)", output)
    result: dict[str, str | None] = {
        "version": None,
        "commit": None,
        "build": first.strip() or None,
        "compiler": compiler_match.group(1).strip() if compiler_match else None,
        "target": compiler_match.group(2).strip() if compiler_match else None,
    }
    if match:
        version, commit = match.groups()
        result.update({"version": version, "commit": commit, "build": f"llama.cpp b{version} ({commit})"})
    return result


def llama_build_config(path: str | None) -> dict[str, str]:
    """Read reproducibility-relevant, non-path CMake settings near llama-server."""
    if not path:
        return {}
    try:
        cache = Path(path).parents[1] / "CMakeCache.txt"
        lines = cache.read_text().splitlines()
    except Exception:
        return {}
    exact = {
        "CMAKE_BUILD_TYPE",
        "CMAKE_CUDA_ARCHITECTURES",
        "GGML_CUDA",
        "GGML_CUDA_COMPRESSION_MODE",
        "GGML_CUDA_FA",
        "GGML_CUDA_FA_ALL_QUANTS",
        "GGML_CUDA_FORCE_CUBLAS",
        "GGML_CUDA_FORCE_MMQ",
        "GGML_CUDA_GRAPHS",
        "GGML_CUDA_NCCL",
        "GGML_CUDA_NO_PEER_COPY",
        "GGML_CUDA_NO_VMM",
        "GGML_NATIVE",
    }
    result: dict[str, str] = {}
    for line in lines:
        if line.startswith(("//", "#")) or "=" not in line or ":" not in line.split("=", 1)[0]:
            continue
        name_type, value = line.split("=", 1)
        name = name_type.split(":", 1)[0]
        if name in exact:
            result[name] = value
    return result


def git_commit_date_for_server(path: str | None, commit: str | None) -> str | None:
    if not path or not commit:
        return None
    server = Path(path)
    # <checkout>/build/bin/llama-server -> repository root
    try:
        repo = server.parents[2]
    except Exception:
        return None
    return run_cmd(["git", "-C", str(repo), "show", "-s", "--format=%cI", commit], timeout=10)


def command_option(args: list[str], *names: str) -> str | None:
    for index, arg in enumerate(args):
        for name in names:
            if arg == name and index + 1 < len(args):
                return args[index + 1]
            if arg.startswith(name + "="):
                return arg.split("=", 1)[1]
    return None


def redact_command_args(args: list[str]) -> list[str]:
    sensitive = {"--api-key", "--api-key-file", "--hf-token", "--token"}
    redacted: list[str] = []
    hide_next = False
    for arg in args:
        if hide_next:
            redacted.append("<redacted>")
            hide_next = False
            continue
        name = arg.split("=", 1)[0]
        if name in sensitive:
            if "=" in arg:
                redacted.append(name + "=<redacted>")
            else:
                redacted.append(arg)
                hide_next = True
        else:
            redacted.append(arg)
    return redacted


def infer_quantization(text: str) -> str | None:
    patterns = [
        r"(?:UD-)?IQ\d(?:_[A-Z0-9]+)+",
        r"(?:UD-)?Q\d(?:_[A-Z0-9]+)+",
        r"(?:NV|MX)?FP\d+",
        r"BF16",
        r"F16",
    ]
    for pattern in patterns:
        if match := re.search(pattern, text.upper()):
            return match.group(0)
    return None


def collect_runtime_metadata(model_arg: str, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = profile or {}
    runtime_profile = profile.get("runtime", {}) if isinstance(profile.get("runtime", {}), dict) else {}
    artifact_profile = profile.get("model", {}) if isinstance(profile.get("model", {}), dict) else {}
    inference_profile = profile.get("inference", {}) if isinstance(profile.get("inference", {}), dict) else {}

    parsed = split_model_arg(model_arg)
    provider = parsed.get("provider")
    model_id = parsed.get("model_id")
    cfg = read_models_config(provider, model_id)
    provider_cfg = cfg.get("provider_config", {})
    model_cfg = cfg.get("model_config", {})
    metadata = model_cfg.get("metadata", {}) if isinstance(model_cfg, dict) else {}
    base_url = provider_cfg.get("baseUrl") if isinstance(provider_cfg, dict) else None
    router_status = router_model_status(base_url, model_id)
    server_args = [str(arg) for arg in ((router_status.get("status") or {}).get("args") or [])]
    server_path = infer_llama_server_path(provider, provider_cfg, model_cfg, model_id, router_status)
    version_output = run_cmd([server_path, "--version"], timeout=10) if server_path else None
    version_info = parse_llama_version_output(version_output)
    commit_date = git_commit_date_for_server(server_path, version_info.get("commit"))

    model_path = command_option(server_args, "-m", "--model")
    artifact = artifact_profile.get("artifact") or (Path(model_path).name if model_path else None)
    quantization_text = " ".join(str(value) for value in (model_id, artifact) if value)
    quantization = artifact_profile.get("quantization") or infer_quantization(quantization_text)
    model_format = artifact_profile.get("format") or ("GGUF" if model_path and model_path.lower().endswith(".gguf") else None)

    inferred_inference: dict[str, Any] = {}
    option_map = {
        "context_size": ("-c", "--ctx-size"),
        "gpu_layers": ("-ngl", "--gpu-layers", "--n-gpu-layers"),
        "parallel": ("-np", "--parallel"),
        "flash_attention": ("-fa", "--flash-attn"),
        "temperature": ("--temp", "--temperature"),
        "top_p": ("--top-p",),
        "top_k": ("--top-k",),
        "min_p": ("--min-p",),
        "seed": ("-s", "--seed"),
        "batch_size": ("-b", "--batch-size"),
        "ubatch_size": ("-ub", "--ubatch-size"),
        "threads": ("-t", "--threads"),
        "fit": ("-fit", "--fit"),
        "fit_context_min": ("-fitc", "--fit-ctx"),
        "split_mode": ("-sm", "--split-mode"),
        "tensor_split": ("-ts", "--tensor-split"),
        "reasoning": ("-rea", "--reasoning"),
        "reasoning_format": ("--reasoning-format",),
        "reasoning_budget": ("--reasoning-budget",),
        "speculation_method": ("--spec-type",),
        "speculative_tokens": ("--spec-draft-n-max",),
    }
    for key, names in option_map.items():
        if value := command_option(server_args, *names):
            inferred_inference[key] = value
    cache_k = command_option(server_args, "-ctk", "--cache-type-k")
    cache_v = command_option(server_args, "-ctv", "--cache-type-v")
    if cache_k or cache_v:
        inferred_inference["kv_cache"] = f"k={cache_k or 'default'},v={cache_v or 'default'}"
    inference = merge_dicts(inferred_inference, inference_profile)

    runtime_label = (
        runtime_profile.get("name")
        or runtime_profile.get("backend")
        or ("llama.cpp" if server_path else None)
        or metadata.get("runtime")
    )
    runtime_version = runtime_profile.get("version") or metadata.get("runtimeVersion") or version_info.get("version")
    runtime_commit = runtime_profile.get("commit") or metadata.get("runtimeCommit") or version_info.get("commit")
    runtime_build = runtime_profile.get("build") or metadata.get("runtimeBuild") or version_info.get("build")
    runtime_compiler = runtime_profile.get("compiler") or version_info.get("compiler")
    if not runtime_build and runtime_label:
        runtime_build = " ".join(str(value) for value in (runtime_label, runtime_version, runtime_commit) if value)

    result: dict[str, Any] = {
        "provider": provider,
        "model_id": model_id,
        "base_url": base_url,
        "runtime_label": runtime_label,
        "runtime_version": runtime_version,
        "runtime_commit": runtime_commit,
        "runtime_build": runtime_build,
        "runtime_compiler": runtime_compiler,
        "runtime_target": version_info.get("target"),
        "runtime_metadata": runtime_profile or None,
        "llama_server_path": server_path,
        "llama_cpp_version": version_info.get("version"),
        "llama_cpp_commit": version_info.get("commit"),
        "llama_cpp_build": version_info.get("build"),
        "llama_cpp_commit_date": commit_date,
        "llama_cpp_version_output": version_output,
        "llama_cpp_build_config": llama_build_config(server_path),
        "server_args": redact_command_args(server_args) if server_args else None,
        "model_format": model_format,
        "quantization": quantization,
        "model_artifact": artifact,
        "model_sha256": artifact_profile.get("sha256"),
        "model_artifact_metadata": artifact_profile or None,
        "context_size": inference.get("context_size"),
        "kv_cache": inference.get("kv_cache"),
        "inference": inference or None,
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
            contributor TEXT,
            source_url TEXT,
            compute_mode TEXT,
            accelerators_json TEXT,
            environment_json TEXT,
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
            runtime_version TEXT,
            runtime_commit TEXT,
            runtime_build TEXT,
            runtime_compiler TEXT,
            llama_cpp_version TEXT,
            llama_cpp_build TEXT,
            llama_cpp_commit TEXT,
            llama_cpp_commit_date TEXT,
            llama_server_path TEXT,
            model_format TEXT,
            quantization TEXT,
            model_artifact TEXT,
            model_sha256 TEXT,
            context_size INTEGER,
            kv_cache TEXT,
            inference_json TEXT,
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
        ("contributor", "TEXT"),
        ("source_url", "TEXT"),
        ("compute_mode", "TEXT"),
        ("accelerators_json", "TEXT"),
        ("environment_json", "TEXT"),
    ]:
        add_column_if_missing(conn, "runs", column, decl)
    for column, decl in [
        ("runtime_label", "TEXT"),
        ("runtime_version", "TEXT"),
        ("runtime_commit", "TEXT"),
        ("runtime_build", "TEXT"),
        ("runtime_compiler", "TEXT"),
        ("llama_cpp_version", "TEXT"),
        ("llama_cpp_build", "TEXT"),
        ("llama_cpp_commit", "TEXT"),
        ("llama_cpp_commit_date", "TEXT"),
        ("llama_server_path", "TEXT"),
        ("model_format", "TEXT"),
        ("quantization", "TEXT"),
        ("model_artifact", "TEXT"),
        ("model_sha256", "TEXT"),
        ("context_size", "INTEGER"),
        ("kv_cache", "TEXT"),
        ("inference_json", "TEXT"),
        ("runtime_json", "TEXT"),
    ]:
        add_column_if_missing(conn, "run_models", column, decl)
    conn.execute(
        "INSERT OR IGNORE INTO schema_info(version, applied_at) VALUES (?, ?)",
        (SCHEMA_VERSION, utc_now()),
    )
    conn.commit()


def create_run(
    conn: sqlite3.Connection,
    benchmark_name: str,
    command: list[str],
    config: dict[str, Any],
    notes: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> int:
    metadata = metadata or {}
    provenance = metadata.get("provenance", {}) if isinstance(metadata.get("provenance", {}), dict) else {}
    host_overrides = metadata.get("host", {}) if isinstance(metadata.get("host", {}), dict) else {}
    host = merge_dicts(collect_host_metadata(), host_overrides)
    accelerators = host_overrides.get("accelerators_used")
    cur = conn.execute(
        """
        INSERT INTO runs(
            run_uuid, benchmark_name, benchmark_version, started_at, pi_version,
            pibench_commit, command_json, config_json, host_json, contributor,
            source_url, compute_mode, accelerators_json, environment_json, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            json_dumps(host),
            provenance.get("contributor"),
            provenance.get("source_url"),
            host_overrides.get("compute_mode"),
            json_dumps(accelerators) if accelerators is not None else None,
            json_dumps(metadata) if metadata else None,
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


def attach_model_to_run(
    conn: sqlite3.Connection,
    run_id: int,
    model_db_id: int,
    model_arg: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> int:
    runtime = collect_runtime_metadata(model_arg, metadata) if model_arg else {}
    values = (
        runtime.get("runtime_label"),
        runtime.get("runtime_version"),
        runtime.get("runtime_commit"),
        runtime.get("runtime_build"),
        runtime.get("runtime_compiler"),
        runtime.get("llama_cpp_version"),
        runtime.get("llama_cpp_build"),
        runtime.get("llama_cpp_commit"),
        runtime.get("llama_cpp_commit_date"),
        runtime.get("llama_server_path"),
        runtime.get("model_format"),
        runtime.get("quantization"),
        runtime.get("model_artifact"),
        runtime.get("model_sha256"),
        runtime.get("context_size"),
        runtime.get("kv_cache"),
        json_dumps(runtime.get("inference", {})),
        json_dumps(runtime),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO run_models(
            run_id, model_id, runtime_label, runtime_version, runtime_commit,
            runtime_build, runtime_compiler, llama_cpp_version, llama_cpp_build,
            llama_cpp_commit, llama_cpp_commit_date, llama_server_path,
            model_format, quantization, model_artifact, model_sha256,
            context_size, kv_cache, inference_json, runtime_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, model_db_id, *values),
    )
    columns = (
        "runtime_label", "runtime_version", "runtime_commit", "runtime_build",
        "runtime_compiler", "llama_cpp_version", "llama_cpp_build",
        "llama_cpp_commit", "llama_cpp_commit_date", "llama_server_path",
        "model_format", "quantization", "model_artifact", "model_sha256",
        "context_size", "kv_cache", "inference_json", "runtime_json",
    )
    assignments = ", ".join(f"{column} = COALESCE(?, {column})" for column in columns)
    conn.execute(
        f"UPDATE run_models SET {assignments} WHERE run_id = ? AND model_id = ?",
        (*values, run_id, model_db_id),
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
