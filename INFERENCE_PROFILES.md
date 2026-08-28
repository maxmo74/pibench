# Local inference profiles and recommended settings

Snapshot: **2026-08-28**

This guide records the currently recommended local inference coordinates, the Pi configuration needed to select them, and the alternatives that were tested but not promoted. It is intentionally named by purpose rather than by a model codename: future leaders should be added as new versioned profile sections without renaming the document.

| Role | Current profile | Runtime | Guidance |
|---|---|---|---|
| Supervised production daily driver | **Peregrine — Qwen3.8-27B W4A16** | patched vLLM 0.28.0 | Reliability-qualified; reproducible v5 runs 218–220 |
| Autonomous fallback | **Doctor Strange — Qwen3.8-27B Q4_K_M** | llama.cpp v0.2.0/b10566 | Lower throughput and score, but retained as the reliability-qualified fallback |

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

The general principles are portable: freeze the complete inference coordinate, reserve answer space, map reasoning controls explicitly, keep hidden monitoring from generating text, test quality as well as speed, and report complete-run means and ranges. Numeric settings such as `GPU_UTIL=0.87`, `MAX_SEQS=2`, MTP3, FP8 KV, 131K context, driver/GSP choices, and allocator headroom are **validated starting points for this setup only**. Re-run context, quality, concurrency, reliability, and allocator gates before carrying them to another runtime, OS, GPU, or driver.

## Current vLLM profile: Peregrine

| Component | Recommended setting |
|---|---|
| Model artifact | `syvai/qwen3.8-27b-3090-fast-variant` at revision `124c14e7e8c7d2f5402933b9af368e772a9fcf0c` |
| Runtime | vLLM 0.28.0 from RTX-3090 port head `55a5a99b124e48ffd0767ece295a355a6f1d988c`, plus local `#48375` backport commit `e78773d` |
| Target weights | W4A16 AutoRound; GPTQ-int4 LM head and MTP; int8 embedding |
| Context/output | 131,072 total context; 8,192 maximum output |
| Attention KV | FP8 through FlashInfer |
| Recurrent state | FP16 |
| Speculation | MTP, 3 probabilistic draft tokens |
| Prefix cache | Enabled with aligned recurrent-state pages and speculative-tail block dropping |
| Scheduling | Synchronous; async scheduling disabled |
| Parallel admission | `max-num-seqs=2` |
| GPU utilization | `0.87` |
| Sampling | temperature `0.7`, top-p `0.9`, top-k `20`, min-p `0`, presence penalty `0`, repeat penalty `1` |
| Reasoning | Pi `low`; thinking enabled and preserved; `reasoning_effort=low` |
| Seeds | vLLM server seed `0`; omit the request seed |
| Tools | Qwen3 reasoning parser, automatic tool choice, `qwen3_coder` tool parser |
| Vision | Disabled with `--language-model-only` |
| Network | Loopback only |
| Reference host | RTX 3090 24 GB; NVIDIA 595.91.07; GSP off; 280 W |

Recorded clean-start protocol-v5 runs 218–220 each scored **54.771/65**, passed 17/24 complete tasks with 72/81 raw points, and produced byte-identical outputs on 24/24 tasks. Mean effective output was 43.0 t/s at about 12.02 seconds mean wall time. The earlier 57.818 qualification artifact followed a different request history and is not used as the leaderboard aggregate. Packaged reliability-v2 passed 12/12. Cold and cache-hot replays of the exact prior looping session completed with 97/97 unique calls, two normal finals, and no guard trigger.

This remains a **supervised production** profile. The original vLLM 0.27 MTP3 coordinate reproduced a cache-hot loop; the current coordinate requires the `#48375` cache-tail backport, async-off scheduling, max-seqs 2, loop guard, full patch preflight, and hash-bound promotion certificate. Doctor Strange remains automatic rollback.

## Launcher settings

These variables match the pinned repository's `single-user/start_qwen.sh`. Replace the model path with your local copy; do not expose the endpoint beyond loopback.

```bash
MODEL=/path/to/Qwen3.8-27B-W4A16-AutoRound-fast
PORT=8080
CTX=long
SPEC=mtp
DRAFT_TOKENS=3
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

- `--kv-cache-dtype fp8`
- `--mamba-ssm-cache-dtype float16`
- `--max-num-batched-tokens 2048`
- synchronous scheduling (`--async-scheduling` absent)
- probabilistic MTP3
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
          "name": "Peregrine — Qwen3.8-27B W4A16 FP8-KV MTP3 131K",
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
            "temperature": 0.7,
            "top_p": 0.9,
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

The current published score uses protocol v5's immutable Pi 0.84.3 runner and attested prompt. Use the separate Pi 0.84.1 runner only to reproduce protocol-v4 history.

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
| General Pi coding, tools, and long sessions | FP8/131K, MTP3, prefix cache | **Use Peregrine settings above** |
| Short-context, single-user headline speed | BF16/64K MTP4 or DFlash2 | Upstream specialist mode; not the promoted PiBench coordinate |
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

This profile scored **57.395833/65**, passed 8/8 reliability scenario-runs, and scored 100/100 on `pi-ops-v1`. It remains the autonomous fallback because Peregrine's higher score and synthetic reliability did not eliminate its retained-session semantic failure.

Do not transfer vLLM settings such as FP8 KV, `GPU_UTIL`, `MAX_SEQS`, aligned hybrid prefix caching, or probabilistic MTP configuration to llama.cpp. Conversely, llama.cpp's GGUF cache types, sidecar drafting, fixed seed, and context-shift controls do not describe the vLLM coordinate. Compare them only as separately named end-to-end profiles.

## Minimum validation after a change

1. Verify every model artifact hash, pinned runtime revision, and complete patch-stack preflight.
2. Start from a genuinely free GPU and record the exposed KV-token pool.
3. Run perplexity plus an executable quality battery—not throughput alone.
4. Exercise true-low wire formatting and tool calls.
5. Reserve the full 8K answer at the intended prompt length.
6. Test staggered concurrency and inspect minimum free VRAM.
7. Run the complete versioned 24-task PiBench profile; retain n=1 as provisional and use complete repeats before determinism claims.
8. Run reliability-v2 plus cold and cache-hot retained realistic tool sessions.
9. Record arithmetic means and observed ranges; never publish only the best run.

See [RESULTS.md](RESULTS.md) for the measured evidence, [METHODOLOGY.md](METHODOLOGY.md) for coordinate and repeatability rules, [LEADERBOARDS.md](LEADERBOARDS.md) for the current ranking, and the [Qwen3.8 RTX 3090 vLLM 0.28 port](https://github.com/syv-ai/qwen38-27b-rtx3090/pull/43) for its patch, optimization, long-context, quality, and gotcha documentation.
