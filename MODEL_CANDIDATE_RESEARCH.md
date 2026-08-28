# Production local-LLM candidate research

Research snapshot: **2026-08-28** · Qualification: **2026-08-29** · Reference hardware: **RTX 3090 24 GB** · Current production: **Peregrine Qwen3.8-27B W4A16 + DFlash2 k7**

This survey uses Firefox through Playwright. Search results and model cards are discovery evidence, not promotion evidence. Local PiBench runs, reliability gates, artifact hashes, context tests, and production health checks remain authoritative.

## Promotion boundary

A replacement must fit one RTX 3090, serve at least 131,072 context with an 8,192-token output allowance, support Pi tool calls and low reasoning, remain loopback-only, and preserve Doctor Strange rollback. Promotion requires three clean complete runs satisfying either:

- at least **58.47/65** and **35 effective output t/s**, or
- within **0.10 points** of 57.970238/65 and at least **63.918 effective output t/s**.

The winning coordinate must also pass reliability 12/12 and hash-bound production qualification. Qualification throughput is total visible output tokens divided by total task-wall time. Different weights, quantization, runtime, sampler, context, speculation, or request history are never averaged.

## Source sweep

### Hugging Face

- [Qwen3.8 model search](https://huggingface.co/models?search=Qwen3.8) established the current release and derivative landscape.
- [Qwen3.8-27B Opus Distill v2](https://huggingface.co/barozp/Qwen3.8-27B-Opus-Distill-v2) is Apache-2.0, derives from Qwen3.8-27B, documents 11,716 verified-genuine Opus traces, and fixes a deterministic self-verification loop in its predecessor. Its same-protocol quick evaluation reports a large GPQA gain over base. The inherited template exposes thinking controls and tool calls; native context is 262,144.
- [Opus Distill v2 GGUF](https://huggingface.co/barozp/Qwen3.8-27B-Opus-Distill-v2-GGUF) provides a 16.81 GB Q4_K_M artifact and retained MTP support. Repository revision screened: `64d56b13ea8d6aa770eeaf8a6ca1358299c6f44c`.
- [Qwen3.8-27B Fable Distill](https://huggingface.co/TeichAI/Qwen3.8-27B-Fable-Distill) reports ARC/BoolQ gains, but its card discloses a large private training corpus with no auditable provenance or licensing.
- [Ornith 1.5 35B-A3B](https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B) publishes strong coding/tool benchmarks, MIT licensing, 262K context, and Qwen tool parsers. The [single-node vLLM W4A16 conversion](https://huggingface.co/MIRALABS/Ornith-1.5-35B-A3B-W4A16-SYM) reports about 20 GB **per GPU on two RTX 3090s**, outside this one-GPU contract.
- [Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) has 262K context and strong agentic results, but contains 125B core parameters, 51B n-gram embeddings, and a 4B MTP head. Even aggressive useful quantizations exceed 24 GB.
- [Qwen3.8-9B Distill](https://huggingface.co/empero-ai/Qwen3.8-9B-Distill) supports 262K context and function calling, but reports no coding benchmark and only 0.751 MMLU flexible accuracy; the training traces are described as internal datasets.
- [Qwen3.8 Distill 35B-A3B Coder](https://huggingface.co/Lord-H4D3ZS/Qwen3.8-Distill-35B-A3B-Coder-Abliterated) labels itself a 2-bit proof of concept, reports no gain over base, and explicitly reports weak tool use.
- [Cold Fusion W4A16](https://huggingface.co/JC1DA/Qwen3.8-27B-Cold-Fusion-GAIN-V1.1-INT4-Autoround) is a reproducible 17.4 GiB AutoRound conversion, but the same target weights already scored 55.006/65 twice in PiBench.

### Hacker News

- [Qwen3.8 search](https://hn.algolia.com/?q=Qwen3.8) surfaced the official 27B and Flash-Next releases, local quantization reports, and 24 GB deployment claims.
- [Qwen3.8-27B at 256K on a 24 GB GPU](https://news.ycombinator.com/item?id=49331607) reinforces that capacity and headline speed require workload-level validation rather than configuration splicing.
- [Qwen3.8 quantization discussion](https://news.ycombinator.com/item?id=49452656) points toward 4-bit as the useful quality/capacity region; lower-bit headline fit is not production evidence.
- [Qwen3.8-Flash-Next discussion](https://news.ycombinator.com/item?id=49448210) reports roughly 90 GB even for a 3-bit quant, confirming rejection on 24 GB.
- A focused [Opus Distill v2 search](https://hn.algolia.com/?q=%22Opus%20Distill%20v2%22) returned no independent reports; its publisher claims therefore require direct local validation.

### Reddit

- [Actual local programming discussion](https://www.reddit.com/r/LocalLLaMA/comments/1vw8vuh/qwen_38_27b_for_actual_local_programming/) describes Qwen3.8-27B as useful but below frontier models and stresses supervised, verifiable work.
- [16 GB coding setup](https://www.reddit.com/r/LocalLLM/comments/1vwhkw6/my_best_local_coding_setup_qwen_38_27b_on_16_gb/) reports 50–60 decode t/s at 130K using a low-bit GGUF; this is throughput evidence only, not score or reliability evidence.
- [W4A16 versus GGUF on a 3090](https://www.reddit.com/r/LocalLLaMA/comments/1w062t7/qwen38_27b_ud_q_k_xl_vs_w4a16autoround/) reports 55–65 t/s and larger context on the same vLLM RTX-3090 port used by Peregrine, supporting the retained runtime rather than a new model.
- [Dual-3090 DFlash2 report](https://www.reddit.com/r/LocalLLaMA/comments/1w0vrrx/qwen38_27b_int4_with_dflash2_at_165ts_and_18m_kv/) requires two GPUs and unmerged LMCache correctness patches; it is outside the hardware contract.
- [Ornith versus Qwen coding discussion](https://www.reddit.com/r/LocalLLaMA/comments/1vxuzr4/ornith1535ba3b_on_a_strix_halo_igpu_lands_4/) reports strong LiveCodeBench results but also template sensitivity and broad capability regression after fine-tuning.
- A focused Reddit search found no independent Opus Distill v2 report, so no community claim substitutes for local testing.

### Inference forums and upstreams

- [Why your local LLM feels dumber than it is](https://forum.level1techs.com/t/why-your-local-llm-feels-dumber-than-it-is/253917) argues for workload-level, long-context, tool-aware tests instead of zero-temperature prompt anecdotes.
- [Qwen3.8 quant selection guide](https://forum.level1techs.com/t/qwen-3-8-quant-selection-guide-for-rtx-5090/254095) finds 4-bit candidates viable but emphasizes full-distribution and workload-specific validation.
- [llama.cpp issue #25618](https://github.com/ggml-org/llama.cpp/issues/25618) remains open for greedy divergence with quantized targets and model-based speculative decoding. This prevents treating MTP/DFlash speed as automatically lossless.
- [vLLM PR #54165](https://github.com/vllm-project/vllm/pull/54165) addresses DFlash/DSpark corruption with hybrid Mamba plus KV connectors; it is open and LMCache-specific.
- [vLLM PR #50885](https://github.com/vllm-project/vllm/pull/50885) is a draft FlashInfer speculative CUDA-graph optimization with an unresolved correctness dependency.
- [RTX-3090 vLLM 0.28 port PR #43](https://github.com/syv-ai/qwen38-27b-rtx3090/pull/43) remains the relevant single-GPU runtime base; its published long-context DFlash result aligns with current Peregrine rather than introducing stronger weights.

## Candidate decision matrix

| Candidate | Screened artifact revision | Provenance/license | Runtime and 24 GB fit | Context/output | Pi tools/low reasoning | Evidence and outcome |
|---|---|---|---|---|---|---|
| Qwen3.8-27B Opus Distill v2 Q4_K_M | GGUF `64d56b13ea8d6aa770eeaf8a6ca1358299c6f44c` | Apache-2.0; Qwen base and 11,716 verified-trace sources named | llama.cpp b10566; 16.81 GB file; **19,845 MiB loaded** | 262K native; tested 131,072/8,192 | Inherited Qwen tool/thinking template; tested low | **Reject after run 235 and reliability:** 52.318/65, 32.860 effective t/s, and not qualified at 9/12 |
| Qwen3.8-27B Fable Distill | Model `ac2b133895580be05ee90a6a7cdcc23cdf998bd0` | Apache-2.0 artifact; material private training corpus has no auditable license/provenance | A GGUF could fit llama.cpp; no artifact accepted for loading | 262K base; 8K possible | Inherited Qwen template | Reject before loading: production provenance boundary fails |
| Ornith 1.5 35B-A3B | Official `10fbf86fed7ecee4a061f8b499a618f46001cac1`; tested AtomicChat GGUF `7aa8fc1d9b861d797880f4a341166d4bb3439f74` | MIT; official model and conversion named | Tested GGUF loaded with llama.cpp b10566; published W4A16 needs two 3090s | 262K native; 131K loaded; 8K supported | Native reasoning and Qwen tool parser | Reject: PiBench run 209 scored 44.563/65, 13.907 below the gate |
| Qwen3.8-27B Cold Fusion GAIN V1.1 | Tested GGUF `0405b00cc604b41fb82a30cfee1ccf5ff9a395bb`; W4A16 `bd2639c792ea562fcb8d58c1b2035102ca737725` | Apache-2.0; merge and conversion methods disclosed | llama.cpp b10566 tested; published W4A16 is 17.4 GiB | 262K base; 131,072/8,192 tested | Inherited Qwen tool/thinking template; low tested | Reject: same target runs 200/203 scored 55.006/65 and 19.8 effective t/s |
| Qwen3.8-9B Distill | `0934f3d2327ff2df2197495278c4c46ae5a56bd9` | Apache-2.0 artifact; internal trace corpus not independently auditable | vLLM or llama.cpp quant fits easily | 262K native; 8K possible | Function calling and reasoning advertised | Reject before loading: MMLU 0.751, no coding result, and insufficient provenance/quality evidence |
| Qwen3.8 Distill 35B-A3B Coder PoC | `75914ba5f4bbb059d2d54f22eceb626b5481cca9` | Apache-2.0; method disclosed | 2-bit llama.cpp proof of concept is about 16 GB | Card recommends 32K, below 131K requirement | Card reports weak tools | Reject before loading: context, tool, and quality pre-screen fails |
| Qwen3.8-Flash-Next | `de4b8e4d43b917e7706784d8bb445c9af86a3540` | Official Qwen Community 1.0 release | No useful one-GPU runtime coordinate; reported 3-bit footprint is about 90 GB | 262K native; 8K possible | Native agent/tool support | Reject before loading: cannot fit 24 GB |
| Opus Distill v1 | Model `517d63f33f9b5d4b3b72b29ef4a33c71365d5732`; GGUF `67cb62729922db64263bffb5f40e82bebe0ad2c9` | Apache-2.0; trace sources named | Q4 llama.cpp artifact fits | 262K base; 8K possible | Inherited Qwen template | Reject before loading: publisher reproduces a non-terminating stacked-constraint loop fixed only in v2 |

The broad uncensored, abliterated, and heretic search results did not become credible candidates: they lacked auditable task-corpus provenance, comparable quality evidence, or both.

## Isolated test result

The sole pre-screen winner, Opus Distill v2 Q4_K_M, was downloaded from its pinned revision and matched the repository LFS SHA-256 `424b98a8f5add2fb66b92902d98ee9288badc82f4b986e70ade5f8d5ca615991` before loading. The isolated coordinate used stable llama.cpp b10566 (`bb4caa7540188872173c44d161602d9271386413`), 131,072 context, 8,192 output, q4_0 K/V, embedded MTP draft2, low reasoning, temperature 1.0, top-p 0.95, top-k 20, min-p 0, seed 42, one slot, and loopback serving.

Complete PiBench run **235** scored **52.318452/65**, passed 16/24 tasks, and produced 12,898 visible tokens in 392.519 task-wall seconds: **32.859587 effective output t/s**. The runner's separate unweighted mean of the 24 per-task rates was 30.475684 t/s. Native decode commonly reached 48–64 t/s, but promotion uses aggregate task-visible throughput. The coordinate is 6.151548 points below the quality gate and 2.140413 effective t/s below the speed floor. Its reliability gate also returned **not qualified at 9/12**. All focus-state, missing-evidence, and polling-trap repeats passed. All three context-recovery setup phases failed because the model used tools instead of returning the exact readiness final and made out-of-scope calls. Score repeats were not run after the complete screen missed both primary gates.

## Final decision

No researched candidate qualifies. **Peregrine remains production**, unchanged at 57.970238/65 and 58.107729 effective t/s with reliability 12/12. The isolated window restored the qualified loopback router with zero restarts, its health timer active, 280 W power, and Doctor Strange rollback preserved.
