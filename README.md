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

Hard deterministic tasks carry more weight than smoke tests. See [METHODOLOGY.md](METHODOLOGY.md) for the scoring and clean-run controls.

## Run it

### Requirements

- Linux or WSL
- Python 3.11+
- [Pi](https://github.com/earendil-works/pi-coding-agent) 0.84.1 with at least one configured model (protocol v4 pins this exact version)
- [Bubblewrap](https://github.com/containers/bubblewrap) for safely checking generated Python

No particular GPU is required. PiBench itself has no Python package dependencies.

On Debian or Ubuntu:

```bash
sudo apt install bubblewrap
npm install -g @earendil-works/pi-coding-agent@0.84.1
git clone https://github.com/maxmo74/pibench.git
cd pibench
```

Pi 0.84.2 changed the effective custom system prompt by adding a trailing newline. PiBench rejects it rather than silently mixing benchmark inputs. An immutable local 0.84.1 installation can be placed first on `PATH` if the system-wide Pi must remain current.

List the models available to Pi:

```bash
pi --list-models
```

Run all 24 tasks against one model:

```bash
./pi_agent_bench.py 'provider/model:off'
```

For a fully local provider:

```bash
./pi_agent_bench.py --offline 'local-llama/your-model:off'
```

Pass several model IDs to compare them in one run, and use `--task TASK_NAME` for a shorter test. Protocol v4 deliberately refuses extension-enabled runs because an extension can modify the effective system prompt after attestation; use a separately versioned runner for those providers.

PiBench records CPU, memory, detected accelerators, Pi version, and model configuration automatically. For a CPU-only run or a backend that cannot be discovered through Pi, add explicit metadata:

```bash
./pi_agent_bench.py 'ollama/model:off' \
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

## Reference results

Current rankings use the fixed, attested protocol-v4 input. The table is a strict score ordering of the ten highest completed v4 profiles currently available. Repeated cloud profiles use the two-run mean; a one-run local profile uses that run's score.

| Rank | Scope | Alias / real model and profile | Runs | Score used | Observed range | Effective output t/s |
|---:|---|---|---:|---:|---:|---:|
| 1 | Cloud | OpenAI **GPT-5.5**, high | 186/190 | **60.813/65** | 58.375–63.250 | 16.2 |
| 2 | Cloud | OpenAI **GPT-5.5**, medium | 185/189 | **59.625/65** | 57.208–62.042 | 19.7 |
| 3 | Cloud | OpenAI **GPT-5.6 Sol**, medium | 187/192 | **57.516/65** | 57.443–57.589 | 18.8 |
| 4 | Local | **Doctor Strange** — Qwen3.8-27B Q4_K_M, low/8K/MTP2 | 180/181 | **57.396/65** | 57.396–57.396 | 20.4 |
| 5 | Cloud | OpenAI **GPT-5.6 Sol**, high | 188/193 | **56.305/65** | 55.318–57.292 | 17.5 |
| 6 | Local | **Road Runner** — Qwen3.6-35B-A3B-MTP UD-Q4_K_M, off/4K/MTP3 | 177 | **54.792/65** | not measured (n=1) | **144.9** |
| 7 | Cloud | OpenAI **GPT-5.4**, medium | 184/191 | **54.277/65** | 54.277–54.277 | 23.1 |
| 8 | Local | **Thor** — Qwen3.6-27B DSV4Pro Q4_LynnStyle, thinking/4K/no-spec | 179 | **53.229/65** | not measured (n=1) | 9.3 |
| 9 | Cloud | **Claude Opus 4.6** (antigravity-v1 profile) | 198/199 | **52.500/65** | 48.000–57.000 | 40.0 |
| 10 | Local | **Spiderman** — Tmax-27B Q5_K_M, off/4K/MTP3 | 178 | **51.568/65** | not measured (n=1) | 47.8 |

Road Runner practical (Qwen3.6 35B-A3B, low/8K/MTP3) is published at 49.542/65 (run 183) but rejected for deployment; Qwen3.6's boolean thinking mode made it slower and less accurate. The other antigravity-v1 cloud profiles are below it: Gemini 3.7 Flash medium at 46.750/65 (runs 194/195) and Gemini 3.1 Pro high at 44.250/65 (runs 196/197); Qwen3.8 off/4K/no-spec sits between Spiderman and Road Runner practical at 48.229/65. Doctor Strange, Road Runner, Thor, and Spiderman are local deployment aliases.

### Cloud versus local results

Protocol v4 makes the **benchmark input** identical: pinned Pi 0.84.1, the same effective-system-prompt hash, fixed cwd, task prompts and graders, and no tools, context files, skills, themes, templates, or extensions. The one documented exception is the **antigravity-v1** profile (Google Cloud Code Assist via the pinned `pi-antigravity` 0.3.1 extension), whose fixed three-part system-instruction injection is version-pinned and attested; those runs sit on canonical prompt + fixed injection rather than the pure canonical prompt. It does not make the execution environments equivalent:

- Local runs can attest the GGUF hash, quantization, llama.cpp commit, server arguments, KV cache, sampler, speculation, and hardware. Seeded local generation can be reproducible, but quantized speculative decoding and runtime changes can still alter output.
- Cloud runs attest the provider/model identifier and request profile, but not weights, backend build, routing, sampler implementation, or service updates. The API does not provide a seed-attested deterministic path, so repeated cloud runs are summarized by mean and range rather than their best score.
- Doctor Strange is currently **output-deterministic on its tested stack**: runs 180/181 were byte-identical on all 24 tasks. GPT-5.4 repeated the same score but only 3/24 outputs were byte-identical, illustrating that score stability is not output determinism. GPT-5.5 varied by about 4.8 points between identical invocations.
- Effective output t/s is end-to-end visible-output speed. Local figures primarily reflect the reference machine; cloud figures also include network, queueing, and opaque provider execution.
- Output ceilings and reasoning controls are profile properties: local canonical runs use 4K, Doctor Strange uses 8K, and these OpenAI catalog entries expose a provider-native 128K ceiling. Local and cloud reasoning levels are not assumed equivalent.

Pre-v4 results remain in `RESULTS.csv` as historical evidence but are not mixed into this ranking. See [RESULTS.md](RESULTS.md) and [METHODOLOGY.md](METHODOLOGY.md) for detailed interpretation rules.

### Reference system

The reference local runs were made on this machine:

| Component | Specification |
|---|---|
| OS | Debian GNU/Linux 13 (trixie), kernel 6.12.101+deb13-amd64 |
| CPU | AMD Ryzen 9 7900, 12 cores / 24 threads |
| RAM | 128 GB |
| GPU | NVIDIA GeForce RTX 3090, 24 GB (24,576 MiB) |
| NVIDIA driver | 550.163.01 |
| CUDA toolkit | 12.4.131 |

Most final local comparisons used a 131,072-token context, one parallel slot, quantized KV cache, full GPU offload, and flash attention. Exact model settings are part of each result profile.

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
