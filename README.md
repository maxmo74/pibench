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
- [Pi](https://github.com/earendil-works/pi-coding-agent) with at least one configured model
- [Bubblewrap](https://github.com/containers/bubblewrap) for safely checking generated Python

No particular GPU is required. PiBench itself has no Python package dependencies.

On Debian or Ubuntu:

```bash
sudo apt install bubblewrap
git clone https://github.com/maxmo74/pibench.git
cd pibench
```

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

Pass several model IDs to compare them in one run. Use `--allow-extensions` when the provider is supplied by a Pi extension, and `--task TASK_NAME` for a shorter test.

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

An OpenAI-compatible endpoint can also be tested directly without Pi:

```bash
./openai_endpoint_bench.py \
  --base-url http://127.0.0.1:8080/v1 \
  --model your-model
```

This diagnostic reuses current PiBench checks and records both effective output speed and native server timing fields when available. Pass `--task TASK_NAME` repeatedly to select specific tasks.

## Reference results

These are selected historical runs, not universal model rankings. Quantization, context, reasoning mode, backend build, and sampling all affect the result.

| Model/configuration | Where | Score | Effective output t/s |
|---|---|---:|---:|
| Thor — DSV4Pro 27B Q4, thinking on | Local | **60.9/65** | 9.5 |
| Claude Opus 4.8, medium | Cloud | **60.2/65** | 41.8 |
| GPT-5.5, high | Cloud | **59.2/65** | 17.5 |
| GPT-5.6 Sol, high | Cloud | **58.9/65** | 17.5 |
| Qwen3.6 27B UD-Q5_K_XL, thinking on | Local | **58.0/65** | 5.7 |
| Spiderman — Tmax 27B Q5, MTP n3 | Local | **55.8/65** | 46.3 |
| Road Runner — Qwen3.6 35B Q4, MTP n3 | Local | **50.9/65** | **145.7** |

Thor, Spiderman, and Road Runner are local deployment aliases, not upstream model names. The complete tables and configuration notes are in [RESULTS.md](RESULTS.md).

### Reference system

The reference local runs were made on this machine:

| Component | Specification |
|---|---|
| OS | Debian GNU/Linux 13 (trixie), kernel 6.12.95+deb13-amd64 |
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
