# PiBench

PiBench is a small, reproducible benchmark for comparing **local and cloud LLMs** on coding and agent-oriented tasks through the [Pi coding agent](https://github.com/earendil-works/pi-coding-agent).

PiBench is hardware-agnostic. It can test models running on CPUs, one or more GPUs in a workstation or server, another machine on the network, or a cloud provider. The results included here are simply the runs made on the reference system described below.

## What it tests

The main suite contains 24 tasks with a weighted maximum of 65 points. It covers:

- exact instruction following and JSON output
- executable Python and edge cases
- parsers, diffs, rate limiting, retries, and caching
- nginx and systemd configuration
- incident analysis and issue triage
- documentation, architecture decisions, and design review

Hard deterministic tasks carry more weight than smoke tests. See [METHODOLOGY.md](METHODOLOGY.md) for the scoring and clean-run controls, [LEADERBOARDS.md](LEADERBOARDS.md) for the explicit overall and local rankings, [INFERENCE_PROFILES.md](INFERENCE_PROFILES.md) for tested local settings and portability limits, and [RESULTS.md](RESULTS.md) for qualification details.

## Run it

### Requirements

- Linux or WSL
- Python 3.11+
- [Pi](https://github.com/earendil-works/pi-coding-agent) 0.84.1 for protocol v4 or 0.84.3 for protocol v5, with at least one configured model
- [Bubblewrap](https://github.com/containers/bubblewrap) for safely checking generated Python

No particular GPU is required. PiBench itself has no Python package dependencies.

On Debian or Ubuntu:

```bash
sudo apt install bubblewrap
npm install -g @earendil-works/pi-coding-agent@0.84.3
git clone https://github.com/maxmo74/pibench.git
cd pibench
```

Protocol v4 remains frozen on Pi 0.84.1. Pi 0.84.2 added a trailing newline to the effective custom prompt, so protocol v5 explicitly pins Pi 0.84.3 and attests that new prompt instead of silently mixing inputs. Keep an immutable 0.84.1 installation on `PATH` for v4 replays; use the current `pi_agent_bench_v5.py` runner for new v5 results.

List the models available to Pi:

```bash
pi --list-models
```

Run all 24 tasks against one model:

```bash
./pi_agent_bench_v5.py 'provider/model:off'
```

For a fully local provider:

```bash
./pi_agent_bench_v5.py --offline 'local-llama/your-model:off'
```

Pass several model IDs to compare them in one run, and use `--task TASK_NAME` for a shorter test. `pi_agent_bench.py` is the immutable Pi 0.84.1/protocol-v4 runner; `pi_agent_bench_v5.py` is the Pi 0.84.3/protocol-v5 runner. Never combine their scores into one rank. Both refuse unversioned extension-modified inputs.

PiBench records CPU, memory, detected accelerators, Pi version, and model configuration automatically. For a CPU-only run or a backend that cannot be discovered through Pi, add explicit metadata:

```bash
./pi_agent_bench_v5.py 'ollama/model:off' \
  --compute-mode cpu \
  --backend Ollama --backend-version 0.12.3 \
  --model-format GGUF --quantization Q5_K_M \
  --context-size 32768 --kv-cache f16
```

Repeat `--accelerator` for the devices actually used in a multi-GPU run. `--metadata-file` accepts a reusable JSON profile, and `--inference-option KEY=VALUE` records backend-specific settings. See `--help` and [METHODOLOGY.md](METHODOLOGY.md#recorded-metadata).

Results are written locally to `results/`, including `results/pibench.sqlite`. Generate a Markdown summary with:

```bash
./pibench_report.py
```

The tracked [RESULTS.csv](RESULTS.csv) contains the complete sanitized task-level result history. Regenerate it from the local database with:

```bash
./pibench_report.py --csv-out RESULTS.csv
```

The exporter uses a strict field allowlist: scores, timings, model/runtime identifiers, and reproducibility metadata are included; prompts, output, errors, notes, command lines, private paths, and arbitrary JSON are excluded. Incomplete infrastructure runs are explicitly marked.

Before any push, `python3 scripts/repository_audit.py --history` must pass. It scans the current tree and all reachable Git history; deleting a sensitive file in a later commit is not sufficient. See [SECURITY.md](SECURITY.md).

An OpenAI-compatible endpoint can also be tested directly without Pi:

```bash
./openai_endpoint_bench.py \
  --base-url http://127.0.0.1:8080/v1 \
  --model your-model
```

This diagnostic reuses current PiBench checks and records both effective output speed and native server timing fields when available. Pass `--task TASK_NAME` repeatedly to select specific tasks.

For a separate tool-enabled, multi-turn operations diagnostic, run configured loopback models through the versioned `pi-ops-v1` profile:

```bash
PATH=/opt/pibench-pi-0.84.1/node_modules/.bin:$PATH \
  ./pi_ops_bench.py \
  'local-llama/Doctor Strange:low' \
  'local-llama/Road Runner:off'
```

That profile gives Pi only `read`, `bash`, `edit`, and `write` inside a disposable Bubblewrap filesystem, uses three sequential turns in one session, hashes its effective tool-enabled system prompt, and scores the resulting code, service unit, documentation, test preservation, and change scope. Its 100-point score is a separate daily-operations diagnostic and is never mixed into the canonical 65-point no-tools ranking. Raw sessions and output remain under ignored local paths.

For current loop/termination qualification, use the Pi 0.84.3 `pi-agent-reliability-v2` gate:

```bash
./pi_agent_reliability_v2.py --repeats 3 \
  'local-peregrine/qwen3.8-27b:low'
```

The immutable Pi 0.84.1 `pi_agent_reliability_bench.py` runner remains available for protocol-v1 reliability history.

It runs four read-only synthetic investigations twice in fresh isolated sessions: evidence-backed diagnosis, graceful termination when decisive evidence is absent, recovery after a large irrelevant context preamble, and resistance to a deterministic polling trap without searching outside the fixture. A model passes the screen only if every run finishes normally, answers the fixture correctly, respects scenario tool budgets and the 21-message ceiling, makes no exact duplicate tool call, stays inside the repository, and avoids repeated text blocks. This is deliberately a pass/fail screen rather than another score. It remains separate while its scenarios and thresholds are validated; passing is necessary evidence for autonomous use, not a guarantee of universal reliability. Private output records metrics, checks and hashes but not model text. Configured endpoints must remain loopback-only, while built-in cloud providers may use an existing provider-scoped `auth.json` entry. For cloud runs, only the selected credential is staged in the isolated agent directory, an attested extension blocks tool access outside the fixture, and the parent removes the staged credential after every Pi process—even on timeout.

Protocol-v4 reliability-v1 results remain historical qualification evidence. The current vLLM 0.28 Peregrine coordinate uses the persistent Pi 0.84.3 `pi-agent-reliability-v2` gate and passed **12/12** after packaging. It also completed cold and cache-hot replays of the exact prior looping session with 97/97 unique calls, normal finals, and no guard trigger. Passing is still necessary evidence rather than proof of universal autonomy; the Peregrine-only loop guard remains mandatory and Doctor Strange remains automatic rollback.

## Reference results

### Protocol-v5 Top 20 overall (1 eligible profile)

Protocol v5 pins Pi 0.84.3 and its trailing-newline effective prompt. It starts a new ranking rather than rewriting protocol-v4 history. New profiles will be added gradually when a complete 24-task v5 run exists.

| Rank | Scope | Alias / real model and profile | Runs | Score used | Effective output t/s |
|---:|---|---|---:|---:|---:|
| 1 | Local production | **Peregrine** — Qwen3.8-27B W4A16, vLLM 0.28, FP8 KV, low/8K/MTP3 | 1 | **57.818/65** | **42.7** |

Raw grader points were 74/81 with 17/24 full-task passes; the leaderboard uses the documented weighted partial-credit score. One run establishes a current result, not a range or determinism claim.

### Protocol-v5 Top 10 local

| Rank | Local profile | Score used | Deployment status |
|---:|---|---:|---|
| 1 | **Peregrine** — Qwen3.8-27B W4A16, vLLM 0.28, FP8-KV/131K, low/8K/MTP3 | **57.818/65** | Production qualified; Doctor Strange rollback |

### Protocol-v4 Top 20 overall (18 frozen profiles)

The following ranking remains frozen on Pi 0.84.1. It is retained for history and gradual v5 migration, not combined with the v5 table. Eighteen complete profiles are eligible, so the table stops at 18. See [LEADERBOARDS.md](LEADERBOARDS.md) for protocol-separated overall and local rankings.

| Rank | Scope | Alias / real model and profile | Runs | Score used | Observed range | Effective output t/s |
|---:|---|---|---:|---:|---:|---:|
| 1 | Cloud variant | **Claude Opus 4.6** (antigravity-v1) | 198/199/204 | **61.506/65** | 60.810–62.604 | 40.5 |
| 2 | Local production | **Peregrine** — Qwen3.8-27B W4A16, FP8 KV, low/8K/MTP3, temp 0.7 | 213/214/215 | **61.006/65** | 61.006–61.006 | 39.3 |
| 3 | Cloud | OpenAI **GPT-5.5**, high | 186/190 | **60.813/65** | 58.375–63.250 | 16.2 |
| 4 | Cloud | OpenAI **GPT-5.5**, medium | 185/189 | **59.625/65** | 57.208–62.042 | 19.7 |
| 5 | Cloud variant | **Gemini 3.7 Flash**, medium (antigravity-v1) | 194/195 | **58.408/65** | 58.372–58.443 | 58.0 |
| 6 | Cloud variant | **Gemini 3.1 Pro**, high (antigravity-v1) | 196/197 | **57.836/65** | 54.479–61.193 | 13.8 |
| 7 | Cloud | OpenAI **GPT-5.6 Sol**, medium | 187/192 | **57.516/65** | 57.443–57.589 | 18.8 |
| 8 | Local fallback | **Doctor Strange** — Qwen3.8-27B Q4_K_M, low/8K/MTP2 | 180/181/201 | **57.396/65** | 57.396–57.396 | 20.7 |
| 9 | Cloud | OpenAI **GPT-5.6 Sol**, high | 188/193 | **56.305/65** | 55.318–57.292 | 17.5 |
| 10 | Local candidate | Qwen3.8-27B + **Sharp v22.3.1**, low/8K/MTP2 | 208 | **55.417/65** | not measured (n=1) | 20.2 |
| 11 | Local candidate | **Cold Fusion** Qwen3.8-27B, low/8K/MTP2 | 200/203 | **55.006/65** | 55.006–55.006 | 19.8 |
| 12 | Cloud | OpenAI **GPT-5.4**, medium | 184/191 | **54.277/65** | 54.277–54.277 | 23.1 |
| 13 | Local bounded | **Road Runner** — Qwen3.6-35B-A3B UD-Q4_K_M, off/4K/MTP3 | 202 | **54.042/65** | not measured (n=1) | **148.2** |
| 14 | Local retained | **Spiderman** — Tmax 27B Q5, off/4K/MTP3 | 206 | **52.729/65** | not measured (n=1) | 48.1 |
| 15 | Local retained | **Thor** — DSV4Pro 27B Q4, thinking/4K/no-spec | 207 | **51.042/65** | not measured (n=1) | 10.0 |
| 16 | Local rejected practical | Road Runner, low/8K/MTP3 | 183 | **49.542/65** | not measured (n=1) | 24.2 |
| 17 | Local comparison | Qwen3.8-27B Q4_K_M, off/4K/no-spec | 182 | **48.229/65** | not measured (n=1) | 28.1 |
| 18 | Local rejected candidate | Ornith 1.5 35B-A3B AD-Q4, target-only off/4K | 209 | **44.563/65** | not measured (n=1) | 92.7 |

### Protocol-v4 Top 10 local

| Rank | Local profile | Score used | Deployment status |
|---:|---|---:|---|
| 1 | **Peregrine** — Qwen3.8-27B W4A16, FP8-KV/131K, low/8K/MTP3 | **61.006/65** | Production; supervise consequential edits |
| 2 | **Doctor Strange** — Qwen3.8-27B Q4_K_M, low/8K/MTP2 | **57.396/65** | Automatic fallback and autonomous default |
| 3 | Qwen3.8 + Sharp v22.3.1, low/8K/MTP2 | **55.417/65** | Rejected candidate |
| 4 | Cold Fusion, low/8K/MTP2 | **55.006/65** | Rejected candidate |
| 5 | **Road Runner** — Qwen3.6-35B-A3B, off/4K/MTP3 | **54.042/65** | Bounded no-tools throughput specialist |
| 6 | **Spiderman** — Tmax 27B, off/4K/MTP3 | **52.729/65** | Retained local profile |
| 7 | **Thor** — DSV4Pro 27B, thinking/4K/no-spec | **51.042/65** | Retained local profile |
| 8 | Road Runner practical, low/8K/MTP3 | **49.542/65** | Rejected practical profile |
| 9 | Qwen3.8-27B Q4_K_M, off/4K/no-spec | **48.229/65** | Comparison profile |
| 10 | Ornith 1.5 35B-A3B AD-Q4, target-only off/4K | **44.563/65** | Rejected candidate |

The antigravity rows were previously summarized with binary pass-weight totals rather than PiBench's documented partial-credit formula. The table now uses the same canonical weighted calculation as `RESULTS.csv` and every other profile; no raw result was changed. Antigravity-v1 still has a distinct canonical-plus-fixed-injection input, so its combined position must be read with that boundary in mind.

Peregrine is the production daily driver on patched **vLLM 0.28.0**: Qwen3.8-27B W4A16, FP8 attention KV, FP16 recurrent state, probabilistic MTP3, aligned prefix caching, synchronous scheduling, two admitted sequences, 131,072 context, and an 8K output ceiling. Its protocol-v5 run scored **57.818/65** at **42.7 effective t/s**, up from the safe v0.27 MTP1 coordinate's 56.568/65 at 28.0 t/s. The `#48375` cache-tail backport, complete startup patch verification, loop guard, retained cache-hot replay, and hash-bound production certificate are mandatory parts of the coordinate. [INFERENCE_PROFILES.md](INFERENCE_PROFILES.md) records the exact settings.

Stable llama.cpp v0.2.0/b10566 and all GGUF profiles remain installed as the controlled fallback runtime; Doctor Strange is the automatic rollback backend. The original vLLM 0.27 MTP3 coordinate later reproduced a cache-hot three-call cycle. The packaged vLLM 0.28 coordinate completed cold and cache-hot copies of that exact retained session without duplicates or cycles, but consequential edits remain supervised.

### Tool-enabled daily-operations result

The separate `pi-ops-v1` three-turn profile produced:

| Alias | Score | Tool calls | Total wall time |
|---|---:|---:|---:|
| **Peregrine** | **100/100** | **19** | **59.3 s** |
| **Doctor Strange** | **100/100** | 27 | 225.7 s |
| **Road Runner** | **95/100** | 18 | **20.5 s** |
| **Thor** | **95/100** | 15 | 74.0 s |
| **Spiderman** | **85/100** | 18 | 53.6 s |

All profiles fixed the retry implementation, preserved tests, produced the fully hardened service, stayed in scope, and completed all turns. Peregrine and Doctor Strange both earned 100/100; Peregrine used 19 tools and completed in 59.3 seconds. Road Runner and Thor omitted the exact requested unittest command; Spiderman missed all three exact README commands. Road Runner remained the fastest older bounded profile. Peregrine used Pi 0.84.1 at PiBench tip `0b0dbf6`; the older four used commit `b124523`. Both used attestor SHA-256 `0480e4d9c6e8b2b7905a10c78206b37ac45cd9203068140123e7f08e8c51d013`, and effective tool-enabled system-prompt SHA-256 `c9f6885987f161b6c530b108b61e2d6b173e1b79dd1caeac2ddc0fb7f18b6cb9`.

A subsequent adversarial replay exposed a limitation that `pi-ops-v1` does not measure: termination under ambiguous, open-ended investigation. A retained Road Runner session duplicated planning and searches, then repeated one paragraph 43 times until aborted. Replaying the exact branch on b10566 timed out with repeated tools under both MTP3 and target-only execution; repetition penalties reduced verbatim duplication but did not restore termination, and an explicit tool budget was ignored. MTP amplified the failure but was not its root cause. Road Runner should therefore not be used unattended for autonomous tool work; prefer Doctor Strange. Its 148.2 t/s result remains valid for the bounded no-tools profile.

### Cloud versus local results

Protocol v4 makes the **benchmark input** identical: pinned Pi 0.84.1, the same effective-system-prompt hash, fixed cwd, task prompts and graders, and no tools, context files, skills, themes, templates, or extensions. The one documented exception is the **antigravity-v1** profile (Google Cloud Code Assist via the pinned `pi-antigravity` 0.3.1 extension), whose fixed three-part system-instruction injection is version-pinned and attested; those runs sit on canonical prompt + fixed injection rather than the pure canonical prompt. It does not make the execution environments equivalent:

- Local runs can attest the GGUF hash, quantization, llama.cpp commit, server arguments, KV cache, sampler, speculation, and hardware. Seeded local generation can be reproducible, but quantized speculative decoding and runtime changes can still alter output.
- Cloud runs attest the provider/model identifier and request profile, but not weights, backend build, routing, sampler implementation, or service updates. The API does not provide a seed-attested deterministic path, so repeated cloud runs are summarized by mean and range rather than their best score.
- Peregrine's clean-start production runs 213–215 were byte-identical on all 24 tasks. This claim includes server seed 0, omitted request seed, and one greedy startup readiness request; periodic checks are non-inference engine-RPC probes. An extra inference request changes the subsequent unseeded trajectory and is therefore a different request-history coordinate. Doctor Strange remains output-deterministic across its tested b10434/b10566 replay. GPT-5.4 repeated the same score but only 3/24 outputs were byte-identical.
- Effective output t/s is end-to-end visible-output speed. Local figures primarily reflect the reference machine; cloud figures also include network, queueing, and opaque provider execution.
- Output ceilings and reasoning controls are profile properties: local canonical runs use 4K, Peregrine and Doctor Strange use 8K, and these OpenAI catalog entries expose a provider-native 128K ceiling. Local and cloud reasoning levels are not assumed equivalent.

Pre-v4 results remain in `RESULTS.csv` as historical evidence but are not mixed into this ranking. See [RESULTS.md](RESULTS.md) and [METHODOLOGY.md](METHODOLOGY.md) for detailed interpretation rules.

### Reference system

The reference local runs were made on this machine:

| Component | Specification |
|---|---|
| OS | Debian GNU/Linux 13 (trixie), kernel 6.12.101+deb13-amd64 |
| CPU | AMD Ryzen 9 7900, 12 cores / 24 threads |
| RAM | 128 GB |
| GPU | NVIDIA GeForce RTX 3090, 24 GB (24,576 MiB) |
| NVIDIA driver | 595.91.07 (current Peregrine production); earlier local runs used 550.163.01 |
| CUDA toolkit | 12.4.131 |

Most final local comparisons used a 131,072-token context, quantized KV cache, full GPU offload, and flash attention. Current Peregrine admits two sequences to reduce recurrent-state and scheduler exposure; the llama.cpp fallback uses one parallel slot. Exact settings are part of each result profile.

## Contributing results

Runs from other hardware and providers are welcome. To make a result useful, include:

- model and provider, including quantization
- compute mode (CPU, GPU, hybrid, remote, or cloud), hardware, OS, and backend version or commit
- context size, KV-cache type, reasoning mode, temperature, and speculation settings
- exact PiBench command
- weighted score and timing summary from a complete 24-task run

Use `--contributor` and `--source-url` to preserve provenance in your local database. Open a pull request that adds a concise row or section to `RESULTS.md`. Contributions are accepted under AGPL-3.0-or-later. Do not commit `results/`, metadata profiles, raw transcripts, model weights, credentials, or machine-specific paths. Some historical experiment commits have no file diff because generated result files are intentionally excluded from Git.

## Safety and limitations

Generated Python is untrusted. PiBench runs executable checks through Bubblewrap with no network or host-home access and with resource limits. It fails closed when the sandbox is unavailable. Do not set `PIBENCH_ALLOW_UNSANDBOXED_EXEC=1` outside a disposable environment.

PiBench is a focused engineering suite, not a complete measure of model quality. Static configuration checks are not deployment tests, models can be stochastic, and local and cloud reasoning controls are not equivalent.

The project was developed with LLM coding assistance; benchmark choices, runs, and summaries were reviewed by the maintainer.

## License

[GNU Affero General Public License v3.0 or later](LICENSE) (`AGPL-3.0-or-later`)
