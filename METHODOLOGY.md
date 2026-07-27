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

`--allow-extensions` removes only the extension restriction for providers that require one. A fixed system prompt asks the model to follow formatting requirements precisely.

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

The local SQLite database records the exact Pi model argument, requested thinking mode, task result, score, timing, stdout/stderr, command, host information, and discoverable llama.cpp version and commit. The database and raw outputs remain under the gitignored `results/` directory.

For comparable contributed runs, record the model file or service, quantization, hardware, backend build, context, KV cache, reasoning mode, sampling, and speculative-decoding settings.

## Reading results

- Effective output t/s is estimated visible output divided by end-to-end wall time; it includes invocation and prompt-processing overhead.
- Local and cloud reasoning controls are not equivalent.
- Quantization and speculative decoding are part of the tested configuration.
- OOM, malformed-artifact, infrastructure, and incomplete runs are excluded rather than scored as model failures.
- Repeated equivalent runs are deduplicated in the summary tables.
- Some older cloud rows combine the latest valid task result across partial invocations.
- Static configuration checks verify requested content, not a live deployment.

The benchmark is intentionally small. Results should be reproduced on the hardware and software stack relevant to the intended deployment.
