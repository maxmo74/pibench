# Methodology

PiBench is a practical coding and agent benchmark. The main runner invokes Pi once per task with no shared session, tools, repository context, skills, prompt templates, themes, or extensions. Extensions can be enabled only when needed to provide the selected model.

## Scoring

The suite has 24 tasks and a maximum score of 65. Binary tasks receive zero or their full weight; tasks with independent checks receive the same fraction of their weight as the fraction of checks passed.

| Task | Points | Task | Points |
|---|---:|---|---:|
| Exact JSON | 0.5 | Deduplicate function | 1.0 |
| Parse integers | 1.0 | Merge intervals | 2.0 |
| Topological sort/cycle | 2.5 | nginx reverse proxy | 2.0 |
| Static web UI | 2.0 | LRU cache | 3.0 |
| JSON-path setter | 4.0 | Rate limiter | 3.5 |
| Unified diff | 4.5 | CSV inference | 3.5 |
| Retry schedule | 3.0 | Semantic-version range | 4.0 |
| Markdown table | 3.5 | Text wrapping | 3.0 |
| systemd service | 3.0 | nginx TLS proxy | 3.0 |
| Incident triage | 2.5 | README rewrite | 2.0 |
| Changelog | 2.0 | GitHub issue triage | 2.5 |
| Architecture decision | 3.5 | Design review | 3.5 |

The prompts and checks in `pi_agent_bench.py` are the canonical task definitions.

## Clean Pi invocation

Each task uses:

```text
--no-session
--no-tools
--no-context-files
--no-extensions
--no-skills
--no-prompt-templates
--no-themes
```

Protocol v4 pins Pi 0.84.1, uses a fixed system prompt, and launches Pi from `/tmp/pibench-pi-agent-cwd-v1`. Before recording a run, the harness verifies the Pi version, invokes that installation's system-prompt builder, and requires the complete effective prompt to equal the protocol definition. It records SHA-256 hashes of both the supplied and effective system prompts and refuses to run if Pi adds or changes content. Custom prompts and extension-enabled runs are not accepted by this runner because they cannot share the canonical effective-prompt attestation. Pi 0.84.2 is intentionally rejected because it added a trailing newline to the effective prompt.

Pi versions through 0.80.6 silently appended `Current date: YYYY-MM-DD` to custom system prompts. Pi 0.82.0 removed that line. Consequently, historical pre-0.82 Pi-agent runs used a `legacy-date-injected` input profile and are not strictly comparable across dates or with date-free runs. They remain valid evidence for their exact effective prompt, and historical inputs can reproduce them, but curated current rankings use protocol-v4 results only. Direct endpoint benchmarks were unaffected.

## Executable checks

Generated Python is treated as untrusted. Bubblewrap provides:

- separate namespaces and no network
- no host home-directory access
- read-only runtime libraries
- private temporary work directories
- CPU, memory, file-size, descriptor, and wall-time limits
- Python isolated mode

If the sandbox cannot start, executable checks fail closed. The unsafe environment-variable override is intended only for disposable systems.

## Recorded metadata

The schema separates metadata that applies to the whole run from metadata for each tested model:

- **Provenance:** optional contributor handle and source URL.
- **Host:** OS, CPU, memory, detected accelerators, compute mode (`cpu`, `gpu`, `hybrid`, `remote`, `cloud`, or `other`), and the devices actually used.
- **Runtime:** backend name, version, commit, build, compiler, and backend-specific JSON.
- **Model artifact:** format, quantization or precision, stable filename/service identifier, and optional SHA-256.
- **Inference:** context size, KV-cache representation, and arbitrary backend-specific settings.
- **Result:** exact Pi model argument, requested/effective thinking mode, benchmark protocol version, effective-system-prompt hash, task score, timing, stdout/stderr, and command.

For loopback llama.cpp routers, PiBench also discovers the backing `llama-server`, records its build number, Git commit and date, compiler/target from `--version`, selected CMake options, model filename, launch arguments, context, KV types, sampling, GPU offload, flash attention, parallelism, and speculation settings when available. The dedicated `llama_cpp_*` database columns are retained alongside generic runtime columns.

Metadata that cannot be discovered can be supplied on the command line or through `--metadata-file`. A profile is a JSON object with optional `provenance`, `host`, `runtime`, `model`, and `inference` objects. For example:

```json
{
  "provenance": {"contributor": "@example", "source_url": "https://example.org/run"},
  "host": {"compute_mode": "hybrid", "accelerators_used": ["GPU 0", "GPU 1"]},
  "runtime": {"name": "vLLM", "version": "0.19.0", "commit": "abcdef0"},
  "model": {"format": "safetensors", "quantization": "FP8"},
  "inference": {"context_size": 131072, "tensor_parallel": 2, "temperature": 0.2}
}
```

Command-line values override their corresponding profile values. Run one model per contributed profile when different models use different runtimes or inference settings. Do not place credentials or private paths in a profile.

The database, metadata profiles, and raw outputs remain local under gitignored paths. The tracked `RESULTS.csv` is a deterministic allowlisted export of every recorded task result. It includes outcomes, partial-credit scores, weights, timings, model/runtime identifiers, selected hardware and inference metadata, and an explicit run-status field. It excludes prompts, output, stderr, checks, notes, commands, arbitrary JSON, credentials, and private paths. The SQLite database is never published. `orphaned-metadata` means task rows survived an old parent-run cleanup; those rows remain visible for completeness but are not used in curated rankings.

Regenerate the public export after adding reviewed runs:

```bash
./pibench_report.py --csv-out RESULTS.csv
```

## Reading results

- Effective output t/s is estimated visible output divided by end-to-end wall time; it includes invocation and prompt-processing overhead.
- Local and cloud reasoning controls are not equivalent.
- Quantization and speculative decoding are part of the tested configuration.
- OOM, malformed-artifact, infrastructure, and incomplete runs are excluded rather than scored as model failures.
- Results are compared only within the same benchmark protocol and effective-prompt profile. Protocol v4 is the current canonical Pi-agent profile; older date-injected and date-free working-directory profiles are historical evidence.
- Repeated equivalent runs are deduplicated in the summary tables.
- Some older cloud rows combine the latest valid task result across partial invocations.
- Static configuration checks verify requested content, not a live deployment.

The benchmark is intentionally small. Results should be reproduced on the hardware and software stack relevant to the intended deployment.
