# Local inference profiles and recommended settings

Deployment update: **2026-10-06**. Historical qualification coordinates below
remain dated separately; deployment preference is not a new certificate.

This guide records the currently recommended local inference coordinates, the Pi configuration needed to select them, and the alternatives that were tested but not promoted. It is intentionally named by purpose rather than by a model codename: future leaders should be added as new versioned profile sections without renaming the document.

| Role | Current profile | Runtime | Guidance |
|---|---|---|---|
| Owner-selected persistent default | **Gandalf — GPU-5 IQ4_XS + Q8 DFlash2 k4** | llama.cpp `1537a0a` | Native Pi 1.0.4 deployment; not newly benchmark-qualified |
| Automatic fallback | **Peregrine — Qwen3.8-27B W4A16 + DFlash2 k7** | patched vLLM 0.28.0 | Historical Pi 0.84.3 qualification; relocated setup startup-tested |
| Emergency/manual alternatives | **Doctor Strange, Road Runner, Spiderman, Thor** | retained llama.cpp profiles | Preserve artifacts and configurations; run one GPU backend at a time |

The following historical sections describe the measured coordinates, not the
current default/fallback policy. See [reproduction recipes](#reproduction-recipes)
for the current setup and retained named alternatives.

The 2026-08-29 [public-model challenger search](MODEL_CANDIDATE_RESEARCH.md) found no replacement. The sole pre-screen winner, Opus Distill v2 Q4_K_M, completed run 235 at 52.318/65 and 32.9 effective t/s, below both challenger gates, and was not reliability-qualified at 9/12. Production and rollback coordinates therefore remain unchanged.

A published score is a property of the complete profile—not just the weights. Changing the runtime, artifact, KV format, context, sampler, speculation, startup request history, or Pi prompt creates a different coordinate that must be measured separately.

## Applicability and portability

PiBench is hardware-agnostic; these tuning records are not. The benchmark can measure any supported endpoint, but its measured settings remain specific to the stack on which they were qualified.

The exact Peregrine coordinate was tested on:

- Debian GNU/Linux 13 on bare-metal Linux
- one NVIDIA RTX 3090 with 24 GB VRAM (Ampere, SM86), with no tensor parallelism
- NVIDIA 595.91.07, GSP firmware disabled, and a 280 W power limit
- AMD Ryzen 9 7900 and 128 GB system RAM
- the pinned patched vLLM 0.28.0 source and exact W4A16 artifact listed below

The local-runtime evidence in this repository covers **llama.cpp and patched vLLM only**. Peregrine itself is a vLLM profile. The llama.cpp/GGUF profiles—such as Doctor Strange—were qualified separately on the same Debian/RTX 3090 host and must not inherit Peregrine's vLLM flags, cache format, speculative configuration, or throughput claims. Ollama, SGLang, TGI, TensorRT-LLM, Windows/WSL, other Linux distributions, AMD GPUs, newer NVIDIA architectures, multi-GPU systems, and different VRAM capacities were not qualified as this exact profile.

The general principles are portable: freeze the complete inference coordinate, reserve answer space, map reasoning controls explicitly, keep hidden monitoring from generating text, test quality as well as speed, and report complete-run means and ranges. Numeric settings such as `GPU_UTIL=0.87`, `MAX_SEQS=2`, DFlash2 k7, int8-per-token-head KV, 131K context, driver/GSP choices, and allocator headroom are **validated starting points for this setup only**. Re-run context, quality, concurrency, reliability, and allocator gates before carrying them to another runtime, OS, GPU, or driver.

## Current vLLM profile: Peregrine

| Component | Recommended setting |
|---|---|
| Model artifact | `syvai/qwen3.8-27b-3090-fast-variant` at revision `124c14e7e8c7d2f5402933b9af368e772a9fcf0c` |
| Runtime | vLLM 0.28.0 from RTX-3090 port head `55a5a99b124e48ffd0767ece295a355a6f1d988c`, plus local `#48375` backport commit `e78773d` |
| Target weights | W4A16 AutoRound; GPTQ-int4 LM head and MTP; int8 embedding |
| Draft artifact | Qwen3.8 DFlash2 W4A16, SHA-256 bound by production qualification |
| Context/output | 131,072 total context; 8,192 maximum output |
| Attention KV | int8 per token and head through Triton attention |
| Recurrent state | FP16 |
| Speculation | DFlash2, 7 draft tokens |
| Prefix cache | Enabled with aligned recurrent-state pages and speculative-tail block dropping |
| Scheduling | Synchronous; async scheduling disabled |
| Parallel admission | `max-num-seqs=2` |
| GPU utilization | `0.87` |
| Sampling | temperature `0.6`, top-p `0.95`, top-k `20`, min-p `0`, presence penalty `0`, repeat penalty `1` |
| Reasoning | Pi `low`; thinking enabled and preserved; `reasoning_effort=low` |
| Seeds | vLLM server seed `0`; omit the request seed |
| Tools | Qwen3 reasoning parser, automatic tool choice, `qwen3_coder` tool parser |
| Vision | Disabled with `--language-model-only` |
| Network | Loopback only |
| Reference host | RTX 3090 24 GB; NVIDIA 595.91.07; GSP off; 280 W |

Recorded clean-start Pi 0.84.3 runs 232–234 each scored **57.970/65**, passed 18/24 complete tasks with 74/81 raw points, and produced byte-identical private outputs on all 24 tasks. Effective output ranged from 58.03 to 58.17 t/s with a 58.11 mean. Temperature-0.60/top-p-0.95 reliability passed 12/12 on repeated PiBench-owned fixtures. No external-project replay was run.

This is a **supervised production** profile. It exceeds the default score and throughput floors and improves the otherwise identical top-p-0.90 coordinate by 1.949 points and 1.03 effective t/s. The coordinate requires the `#48375` cache-tail backport, async-off scheduling, max-seqs 2, loop guard, full patch preflight, DFlash2 artifact hashes, and a hash-bound promotion certificate. Doctor Strange remains automatic rollback.

### Rejected DFlash2 samplers

Temperature-0.70 runs 224/225/227 were byte-identical and scored 57.649/65 at 57.7 t/s; reliability passed 12/12, but both retained cold and cache-hot sessions exhausted the 60-call limit without a final. Temperature-0.60/top-p-0.90 runs 229–231 scored 56.021/65 at 57.1 t/s and were superseded by top-p 0.95. Temperatures 0.65, 0.625, and 0.61 also failed cache-hot replay. A temperature-0.55 cold probe finalized normally at 53 calls; its hot replay and score were not run after the external-project fixture was withdrawn.

## Launcher settings

These variables match the pinned repository's `single-user/start_qwen.sh`. Replace the model path with your local copy; do not expose the endpoint beyond loopback.

```bash
MODEL=/path/to/Qwen3.8-27B-W4A16-AutoRound-fast
PORT=8080
CTX=long
SPEC=dflash2
DFLASH_TOKENS=7
PREFIX_CACHE=1
TOOLS=1
VISION=0
GPU_UTIL=0.87
MAX_SEQS=2
ASYNC_SCHED=0
MAX_LEN=131072
VLLM_API_KEY=pibench-local
EXTRA_ARGS="--host 127.0.0.1"

bash single-user/start_qwen.sh
```

`pibench-local` is only a fixed local token, not the network security boundary. Loopback binding and host access control are the boundary. Use a real secret and TLS-aware reverse proxy if the service ever leaves loopback.

The effective launch includes these important vLLM behaviors:

- `--attention-backend TRITON_ATTN --kv-cache-dtype int8_per_token_head`
- `--mamba-ssm-cache-dtype float16`
- `--max-num-batched-tokens 2048`
- synchronous scheduling (`--no-async-scheduling`)
- a W4A16 DFlash2 drafter with 7 speculative tokens
- `--enable-prefix-caching --mamba-cache-mode align`
- `--reasoning-parser qwen3`
- `--enable-auto-tool-choice --tool-call-parser qwen3_coder`
- `--language-model-only`

Do not treat this as a stock-vLLM recipe. Startup verifies every project patch plus the `#48375` speculative Mamba cache-tail fix. The production certificate is bound to runtime, model, service, environment, preflight, Pi catalog, guard, and harness hashes. Any drift requires requalification.

## Pi model configuration

Add the following provider to `~/.pi/agent/models.json`. It intentionally exposes only the two tested user-facing modes: `low` and `off`.

```json
{
  "providers": {
    "local-peregrine": {
      "baseUrl": "http://127.0.0.1:8080/v1",
      "api": "openai-completions",
      "apiKey": "pibench-local",
      "compat": {
        "supportsDeveloperRole": false,
        "supportsReasoningEffort": false,
        "supportsThinkingTokenBudget": false,
        "supportsUsageInStreaming": false,
        "supportsStore": false,
        "supportsStrictMode": false,
        "supportsLongCacheRetention": false,
        "maxTokensField": "max_tokens",
        "thinkingFormat": "chat-template",
        "chatTemplateKwargs": {
          "enable_thinking": { "$var": "thinking.enabled" },
          "preserve_thinking": true,
          "reasoning_effort": {
            "$var": "thinking.effort",
            "omitWhenOff": true
          }
        }
      },
      "models": [
        {
          "id": "qwen3.8-27b",
          "name": "Peregrine — Qwen3.8-27B W4A16 DFlash2 k7 131K",
          "reasoning": true,
          "input": ["text"],
          "contextWindow": 131072,
          "maxTokens": 8192,
          "cost": {
            "input": 0,
            "output": 0,
            "cacheRead": 0,
            "cacheWrite": 0
          },
          "thinkingLevelMap": {
            "off": "off",
            "minimal": null,
            "low": "low",
            "medium": null,
            "high": null,
            "xhigh": null,
            "max": null
          },
          "samplingParams": {
            "temperature": 0.6,
            "top_p": 0.95,
            "top_k": 20,
            "min_p": 0.0,
            "presence_penalty": 0.0,
            "repeat_penalty": 1.0
          },
          "compat": {
            "supportsReasoningEffort": true
          }
        }
      ]
    }
  }
}
```

Merge the provider into an existing file rather than deleting other providers.

Recommended keys for `~/.pi/agent/settings.json`:

```json
{
  "defaultProvider": "local-peregrine",
  "defaultModel": "qwen3.8-27b",
  "defaultThinkingLevel": "low",
  "compaction": {
    "enabled": true,
    "reserveTokens": 16384,
    "keepRecentTokens": 20000
  }
}
```

The 16K compaction reserve is deliberately larger than the 8K model output ceiling. With a 131,072-token context, automatic compaction begins around 114,688 estimated tokens and leaves margin for tool results, token-estimation error, and the answer.

Launch explicitly with:

```bash
pi --model local-peregrine/qwen3.8-27b:low
```

The current published score uses the sole PiBench runner with bridge-qualified Pi 0.84.3 and an attested effective prompt. Pi upgrades do not renumber the score protocol after exact local compatibility bridges; historical runner source remains in Git history.

## Thinking level

Use **`low`** for normal coding, analysis, and tool work. It is the promoted coordinate and maps to:

```text
enable_thinking=true
preserve_thinking=true
reasoning_effort=low
```

Use **`off`** only for simple, speed-sensitive transformations where reduced reasoning quality is acceptable. `medium`, `high`, `xhigh`, and `max` are deliberately hidden because they were not promoted for this profile. A thinking-token budget is not enabled: it is neither a reasoning instruction nor a reliable stopping boundary on this stack.

## Startup and monitoring

Request history matters when request seeds are omitted. A startup inference at the production sampler changed the subsequent clean-start score from 61.006 to 58.256 even though every visible setting was otherwise unchanged.

For replayable startup:

1. Start from a clean GPU and wait for vLLM to become ready.
2. Make exactly one greedy, no-thinking readiness request.
3. Do not make another hidden inference before a benchmark coordinate begins.
4. Use vLLM's `/health` engine RPC and authenticated `/v1/models` for periodic monitoring; do not use a generation canary.

Normal user requests naturally advance the unseeded trajectory. The rule above exists to prevent invisible monitoring from changing a supposedly clean benchmark or replay. Backend boot verification depends only on the router, driver, power, patch preflight, and non-inference health checks; an optional UI service must not trigger model rollback.

## Choosing another mode

| Need | Option | Recommendation |
|---|---|---|
| General Pi coding, tools, and long sessions | int8/131K, DFlash2 k7, prefix cache | **Use Peregrine settings above** |
| Short-context, single-user headline speed | BF16/64K MTP4 | Upstream specialist mode; not the promoted PiBench coordinate |
| Mostly reproduce or quote prompt text | DFlash2 lookup/reproduction mode | Can be much faster for copying; lower context/concurrency and not generally qualified |
| More than 131K must fit | KVarN K4V2 or Triton int4 KV | Capacity specialist only; measure quality, TTFT, decode, and allocator headroom |
| Debug quality or speculation | Target-only/no speculation | Diagnostic control, not the preferred production speed point |
| Many concurrent short requests | Batch/no-spec configuration | Prefer throughput-oriented batch testing rather than extrapolating single-user results |

### Long-context cautions

- KVarN K4V2 with prefix caching regressed combined perplexity from about 8.09 to 9.30 in our campaign. With caching disabled, quality recovered, but PiBench fell to 49.313/65 and reliability to 18/24. Do not use that cached coordinate.
- Triton `int4_per_token_head` is a simpler 262K-capable option documented upstream, but its long-context prefill and decode were substantially slower and it was not promoted here.
- MTP4 on FP8/FlashInfer has concurrency-stability concerns. MTP3 is the retained long-context setting.
- Raising `GPU_UTIL`, `MAX_SEQS`, context, output, or draft depth independently can consume the transient allocator headroom that startup profiling does not fully model.

## Avoid silent coordinate drift

- Do not add a nonzero `min_p` with speculative decoding; vLLM rejects that combination on this stack.
- Do not add `thinking_token_budget`.
- Do not average runs with different request seeds or startup request histories.
- Do not compare a prefix-cache hit with a miss as if only throughput changed.
- Do not promote a cache or quantization change from tok/s alone; run quality and executable-task checks.
- Do not raise the output ceiling to 16K expecting a general quality fix; the measured gain was insufficient.
- Do not upgrade vLLM, Torch, CUDA kernels, model patches, the artifact, or the driver and continue calling the result the same coordinate.
- Do not infer eight-way full-context concurrency from `max-num-seqs=8`. The qualified KV pool held about 160K–164K tokens, or roughly 1.23–1.25 maximum-length requests.

## Current llama.cpp profile: Doctor Strange

Doctor Strange is a separate GGUF/llama.cpp coordinate, not a way to run the Peregrine artifact. Its retained settings are:

| Component | Retained setting |
|---|---|
| Model | Qwen3.8-27B Q4_K_M GGUF plus official Q4_0 MTP sidecar |
| Runtime | llama.cpp v0.2.0/b10566 at commit `bb4caa7540188872173c44d161602d9271386413` |
| Context/output | 131,072 total context; 8,192 maximum output |
| KV cache | Q4_0 keys and Q4_0 values |
| Parallelism | One slot |
| GPU | Full layer offload; flash attention enabled |
| Speculation | Quantized MTP sidecar, draft depth 2 |
| Sampling | temperature `1.0`, top-p `0.95`, top-k `20`, min-p `0`, seed `42` |
| Reasoning | Pi `low`; llama.cpp reasoning enabled with low effort |
| Context handling | Fit disabled; context shifting disabled |
| Reference host | The same Debian/RTX 3090 system; 280 W |

This profile scored **57.395833/65**, passed 8/8 reliability scenario-runs, and scored 100/100 on `pi-ops-v1`. It was the autonomous fallback at the time of those measurements. It is now
retained for emergency/manual recovery; Peregrine is the selected fallback.

Do not transfer vLLM settings such as int8-per-token-head KV, `GPU_UTIL`, `MAX_SEQS`, aligned hybrid prefix caching, or DFlash2 configuration to llama.cpp. Conversely, llama.cpp's GGUF cache types, sidecar drafting, fixed seed, and context-shift controls do not describe the vLLM coordinate. Compare them only as separately named end-to-end profiles.

## Minimum validation after a change

1. Verify every model artifact hash, pinned runtime revision, and complete patch-stack preflight.
2. Start from a genuinely free GPU and record the exposed KV-token pool.
3. Run perplexity plus an executable quality battery—not throughput alone.
4. Exercise true-low wire formatting and tool calls.
5. Reserve the full 8K answer at the intended prompt length.
6. Test staggered concurrency and inspect minimum free VRAM.
7. Run the complete 24-task PiBench profile; retain n=1 as provisional and use complete repeats before determinism claims.
8. Run the reliability gate plus cold and cache-hot PiBench-owned tool fixtures.
9. Record arithmetic means and observed ranges; never publish only the best run.

See [RESULTS.md](RESULTS.md) for the measured evidence, [METHODOLOGY.md](METHODOLOGY.md) for coordinate and repeatability rules, [LEADERBOARDS.md](LEADERBOARDS.md) for the current ranking, and the [Qwen3.8 RTX 3090 vLLM 0.28 port](https://github.com/syv-ai/qwen38-27b-rtx3090/pull/43) for its patch, optimization, long-context, quality, and gotcha documentation.

## Reproduction recipes

### Deployment policy and versions

As of 2026-10-06, the owner-selected persistent default is **Gandalf**, automatic
fallback is **Peregrine**, and **Doctor Strange** is emergency recovery. Road
Runner, Spiderman and Thor remain manual alternatives. This is a deployment
choice with known limitations, not a fresh production-qualification claim.

The native deployment uses **Pi 1.0.4**. Canonical published benchmark scores
remain tied to **Pi 0.84.3** and the attested benchmark prompt. Do not report a
native 1.0.4 result as equivalent to the canonical coordinate. Gandalf's native
restricted reliability has both passing and failing runs; a later pass does not
erase earlier failures. No diagnostic legacy-prompt bridge is deployed to tool
sessions. Full Pi 1.0.4 quality qualification remains incomplete.

Install Pi into separate version directories rather than changing a benchmark
pin when upgrading the daily agent:

```bash
WORKSPACE="$HOME/pibench-workspace"
mkdir -p "$WORKSPACE/runtimes/pi" "$WORKSPACE/models" "$WORKSPACE/experiments"
npm install --prefix "$WORKSPACE/runtimes/pi/1.0.4" \
  @earendil-works/pi-coding-agent@1.0.4
npm install --prefix "$WORKSPACE/runtimes/pi/0.84.3" \
  @earendil-works/pi-coding-agent@0.84.3
"$WORKSPACE/runtimes/pi/1.0.4/node_modules/.bin/pi" --version
```

All paths in these examples are local placeholders. Keep downloaded weights,
raw results, credentials and host service configurations outside the public
Git checkout. Use one backend at a time on a single RTX 3090.

### Gandalf: build and verify weights

Requirements: Linux, CUDA toolkit, CMake, C++ compiler, RTX 3090 24 GB.
Build the pinned upstream llama.cpp revision for SM86:

```bash
git clone https://github.com/ggml-org/llama.cpp.git "$WORKSPACE/runtimes/gandalf"
git -C "$WORKSPACE/runtimes/gandalf" checkout \
  1537a0a8b2f8711d840878b0a0677ab2213c882c
cmake -S "$WORKSPACE/runtimes/gandalf" \
  -B "$WORKSPACE/runtimes/gandalf/build" \
  -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=86
cmake --build "$WORKSPACE/runtimes/gandalf/build" -j 8 --target llama-server
```

Download the exact target and Q8 drafter. These pinned Hub revisions contain
files whose upstream LFS hashes match the tested artifacts:

```bash
hf download byteshape/Qwen3.8-27B-GGUF \
  Qwen3.8-27B-IQ4_XS-3.84bpw.gguf \
  --revision 3fdfbd9b4a618303ad36edb151e95d134ece8c18 \
  --local-dir "$WORKSPACE/models/gandalf"
hf download incoai/Qwen3.8-27B-DFlash2-GGUF \
  Qwen3.8-27B-DFlash2-Q8_0.gguf \
  --revision 51962825493a48b846b40126d35c799ac4093ad0 \
  --local-dir "$WORKSPACE/models/gandalf"
(
  cd "$WORKSPACE/models/gandalf"
  printf '%s\n' \
    '89434f23dc89c5f990894e3fe9fdad19d88c370f0d3638a176f29933f218b78b  Qwen3.8-27B-IQ4_XS-3.84bpw.gguf' \
    'c18e800daedc59ca68fd13b6a856d795746af6d399a9279ac6a277d1d422f87e  Qwen3.8-27B-DFlash2-Q8_0.gguf' \
    | sha256sum -c -
)
```

`hf` is the Hugging Face CLI; install it in a separate environment following its
upstream instructions. File names alone do not establish artifact equivalence.

### Gandalf: serve and select in Pi

Stop the previous GPU backend before starting this foreground command:

```bash
"$WORKSPACE/runtimes/gandalf/build/bin/llama-server" \
  --model "$WORKSPACE/models/gandalf/Qwen3.8-27B-IQ4_XS-3.84bpw.gguf" \
  --spec-draft-model "$WORKSPACE/models/gandalf/Qwen3.8-27B-DFlash2-Q8_0.gguf" \
  --alias Gandalf --host 127.0.0.1 --port 8080 \
  --ctx-size 131072 --parallel 1 --n-gpu-layers 99 \
  --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0 \
  --spec-type draft-dflash --spec-draft-ngl 99 --spec-draft-n-max 4 \
  --no-context-shift --seed 42 --temp 0.6 --top-p 0.95 --top-k 20 --min-p 0 \
  --reasoning-effort low --reasoning-budget 6144 --no-webui
```

The server reasoning budget reserves space within Pi's 8,192-token output
allowance for visible answers. It is part of the selected coordinate; an
uncapped server is not the same profile. Never equate a visible answer with
executable correctness.

Merge this provider into the existing Pi model registry, preserving other
providers. Replace the API-key placeholder with your local authentication
configuration if enabling server authentication; the command above is strictly
loopback-bound without authentication.

```json
{
  "providers": {
    "local-llama-gandalf": {
      "baseUrl": "http://127.0.0.1:8080/v1",
      "api": "openai-completions",
      "apiKey": "REPLACE_WITH_LOCAL_API_KEY",
      "compat": {
        "supportsDeveloperRole": false,
        "supportsReasoningEffort": false,
        "supportsUsageInStreaming": false,
        "supportsStore": false,
        "supportsStrictMode": false,
        "supportsLongCacheRetention": false,
        "maxTokensField": "max_tokens",
        "thinkingFormat": "qwen-chat-template"
      },
      "models": [{
        "id": "Gandalf",
        "name": "Gandalf",
        "reasoning": true,
        "input": ["text"],
        "contextWindow": 131072,
        "maxTokens": 8192,
        "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
        "thinkingLevelMap": {
          "off": null, "minimal": null, "low": "low", "medium": null,
          "high": null, "xhigh": null, "max": null
        },
        "samplingParams": {
          "temperature": 0.6, "top_p": 0.95, "top_k": 20, "min_p": 0,
          "presence_penalty": 0, "repeat_penalty": 1
        },
        "compat": {"supportsReasoningEffort": true}
      }]
    }
  }
}
```

Set these keys in Pi settings, rather than replacing the whole settings file:

```json
{
  "defaultProvider": "local-llama-gandalf",
  "defaultModel": "Gandalf",
  "defaultThinkingLevel": "low"
}
```

```bash
"$WORKSPACE/runtimes/pi/1.0.4/node_modules/.bin/pi" \
  --model local-llama-gandalf/Gandalf:low
```

### Peregrine fallback

Use the exact W4A16 artifact, patched vLLM 0.28 port, cache-tail backport and
launcher settings in [Current vLLM profile](#current-vllm-profile-peregrine).
The public [port PR](https://github.com/syv-ai/qwen38-27b-rtx3090/pull/43)
provides installation and patch-stack context; its complete launcher must be
used, not a stock `pip install vllm` approximation. Fetch and verify the
DFlash2 W4A16 drafter with that port's preparation/verifier scripts.

Use the same localhost endpoint only after stopping Gandalf. Preserve the
Peregrine provider in Pi settings; switch the default provider/model only after
its endpoint passes readiness. Exact startup history and request seeds matter
for benchmark reproduction. Current deployment-policy authorization does not
replace or rewrite the old hash-bound benchmark qualification certificate.

### Preserve the other named profiles

The following retained llama.cpp profiles use build b10566 at commit
`bb4caa7540188872173c44d161602d9271386413`. Build it independently using the
CMake procedure above with that commit. Do not replace Gandalf's executable
in place. Obtain the named artifact from its upstream model release and verify
its hash against the historical profile before asserting score reproduction.

| Codename | Artifact | Speculation | Sampler |
|---|---|---|---|
| Doctor Strange | `Qwen3.8-27B-Q4_K_M.gguf` + `mtp-Qwen3.8-27B-Q4_0.gguf` | `draft-mtp`, depth 2 | temperature 1.0, top-p .95, top-k 20, seed 42 |
| Road Runner | `Qwen3.6-35B-A3B-MTP-UD-Q4_K_M.gguf` | embedded MTP, depth 3 | temperature .2, seed 42; inherited runtime defaults otherwise |
| Spiderman | `tmax-27b-Q5_K_M.gguf` | embedded MTP, depth 3 | temperature .2, seed 42; inherited runtime defaults otherwise |
| Thor | `Qwen3.6-27B-DSV4Pro-GLM52-SFT-GPT55-RL-Coding-Q4_LynnStyle.gguf` | none | temperature .2, seed 42; inherited runtime defaults otherwise |

All four retain one slot, full GPU-layer offload, 131,072 context and Q4_0 K/V
cache. Doctor Strange enables flash attention, disables fitting/context shifting
and uses low preserved reasoning. The other three are retained convenience
profiles, not newly tested or newly promoted settings; historical measurements
may use a different runtime or sampler. Consult [RESULTS.md](RESULTS.md) and
[RESULTS.csv](RESULTS.csv) before quoting a historical result.

A direct Doctor Strange launch, using local artifact placeholders:

```bash
"$WORKSPACE/runtimes/doctor/build/bin/llama-server" \
  --model "$WORKSPACE/models/doctor/Qwen3.8-27B-Q4_K_M.gguf" \
  --spec-draft-model "$WORKSPACE/models/doctor/mtp-Qwen3.8-27B-Q4_0.gguf" \
  --alias 'Doctor Strange' --host 127.0.0.1 --port 8080 \
  --ctx-size 131072 --parallel 1 --n-gpu-layers all --flash-attn on \
  --cache-type-k q4_0 --cache-type-v q4_0 --fit off --no-context-shift \
  --spec-type draft-mtp --spec-draft-ngl all --spec-draft-n-max 2 \
  --spec-draft-n-min 1 --spec-draft-type-k q4_0 --spec-draft-type-v q4_0 \
  --reasoning on --reasoning-effort low --reasoning-preserve \
  --temp 1 --top-p .95 --top-k 20 --min-p 0 --repeat-penalty 1 \
  --presence-penalty 0 --seed 42 --batch-size 1024 --ubatch-size 512 --no-webui
```

For the other three, use their artifact and alias from the table, remove the
external sidecar flags, select `draft-mtp` depth 3 or `none` as listed, and keep
sampling controls explicit when comparing scores. Preserve catalog entries and
weights even when they are not the default. They cannot all occupy the same GPU
simultaneously.

### Persistent service and recovery

Use separate root-owned service templates for each backend. Run inference as
an unprivileged account, bind only loopback, set a writable cache/state directory
and explicit library search path if relocating a binary build. A systemd service
should wait for readiness, restart on failure, and invoke a separate recovery
unit on terminal failure. Periodic monitoring must use health/model endpoints,
not hidden text-generation requests.

Recovery order is **Gandalf → Peregrine → Doctor Strange**. Make a switch under a
lock: stop monitoring, stop the old GPU process, select the service and Pi
provider together, start and verify the new endpoint, then restart monitoring.
Never start the two engines simultaneously. Keep fallback selection sticky until
an operator switches back; avoid endless automatic failback loops.

Persist the selected service and default provider on disk, not in a temporary
trial marker. Bind the owner deployment decision to runtime/model/configuration
hashes and check drift at startup. Keep that decision separate from benchmark
qualification. Do not copy someone else's certificate or mark missing tests as
passing. Test fallback startup and recovery on your own host before relying on
it; a dispatch drill is not a physical reboot or proof of every failure mode.
