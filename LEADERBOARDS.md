# PiBench leaderboards

Snapshot: **2026-08-28** · Score protocol: **pi-agent-24/65** · Execution revisions: **v4 and v5** · Maximum score: **65**

These are profile rankings, not model-only rankings. Runtime, quantization, context, output allowance, reasoning control, sampler, speculation, and request history are part of a profile. Repeated equivalent runs use their arithmetic mean and observed range; no best-run or best-task splicing is used. Incomplete infrastructure runs are excluded.

Protocols v4 and v5 have identical tasks, prompts, graders, weights, sandbox, fixed cwd, and clean invocation. V5 pins Pi 0.84.3 and attests one trailing newline absent from v4's Pi 0.84.1 effective prompt. A four-profile bridge found no material score effect: Doctor Strange and Road Runner reproduced all 24 task outcomes and outputs byte-for-byte; GPT-5.5 medium and high remained within ordinary managed-service variation. They are therefore treated as execution revisions of one score protocol. Every row retains the revision actually measured; historical v4 runs are never relabeled v5.

The Antigravity rows use the frozen `antigravity-v1` prompt variant—canonical prompt plus an attested fixed injection—not the pure-canonical input used by local and OpenAI profiles. They remain visible in the overall ordering with that boundary disclosed.

## Top 20 overall

There are **21 established complete profiles** in this frozen ranking. DFlash2 temperature 0.60/top-p 0.95 is production after meeting the score, throughput, and reliability gates.

| Rank | Model/profile | Class | Runs/evidence | Revision | Mean score | Observed range | Effective output t/s |
|---:|---|---|---:|---|---:|---:|---:|
| 1 | Claude Opus 4.6 | Cloud antigravity-v1 | 198/199/204 | v4 variant | **61.506** | 60.810–62.604 | 40.5 |
| 2 | Peregrine — Qwen3.8 27B W4A16, vLLM 0.27, FP8-KV/131K, low/8K/MTP3 | Local retired coordinate | 213/214/215 | v4 | **61.006** | 61.006–61.006 | 39.3 |
| 3 | GPT-5.5, medium | Cloud native | 185/189/216 | v4+v5 | **60.542** | 57.208–62.375 | 19.8 |
| 4 | GPT-5.5, high | Cloud native | 186/190/216 | v4+v5 | **60.292** | 58.375–63.250 | 15.9 |
| 5 | Gemini 3.7 Flash, medium | Cloud antigravity-v1 | 194/195 | v4 variant | **58.408** | 58.372–58.443 | 58.0 |
| 6 | **Peregrine — Qwen3.8 27B W4A16, vLLM 0.28, int8-KV/131K, low/8K/DFlash2 k7, top-p 0.95** | Local production | 232/233/234 | v5 | **57.970** | 57.970–57.970 | **58.1** |
| 7 | Gemini 3.1 Pro, high | Cloud antigravity-v1 | 196/197 | v4 variant | **57.836** | 54.479–61.193 | 13.8 |
| 8 | GPT-5.6 Sol, medium | Cloud native | 187/192 | v4 | **57.516** | 57.443–57.589 | 18.8 |
| 9 | Doctor Strange — Qwen3.8 27B Q4_K_M, low/8K/MTP2 | Local fallback | 180/181/201/217 | v4+v5 | **57.396** | 57.396–57.396 | 20.8 |
| 10 | GPT-5.6 Sol, high | Cloud native | 188/193 | v4 | **56.305** | 55.318–57.292 | 17.5 |
| 11 | Peregrine — Qwen3.8 27B W4A16, vLLM 0.28, int8-KV/131K, low/8K/DFlash2 k7, top-p 0.90 | Local predecessor | 229/230/231 | v5 | **56.021** | 56.021–56.021 | 57.1 |
| 12 | Qwen3.8 + Sharp v22.3.1, low/8K/MTP2 | Local rejected candidate | 208 | v4 | **55.417** | not measured (n=1) | 20.2 |
| 13 | Cold Fusion, low/8K/MTP2 | Local rejected candidate | 200/203 | v4 | **55.006** | 55.006–55.006 | 19.8 |
| 14 | Peregrine — Qwen3.8 27B W4A16, vLLM 0.28, FP8-KV/131K, low/8K/MTP3 | Local predecessor | 218/219/220 | v5 | **54.771** | 54.771–54.771 | 43.0 |
| 15 | GPT-5.4, medium | Cloud native | 184/191 | v4 | **54.277** | 54.277–54.277 | 23.1 |
| 16 | Road Runner — Qwen3.6 35B-A3B, off/4K/MTP3 | Local bounded | 202/217 | v4+v5 | **54.042** | 54.042–54.042 | **159.2** |
| 17 | Spiderman — Tmax 27B, off/4K/MTP3 | Local retained | 206 | v4 | **52.729** | not measured (n=1) | 48.1 |
| 18 | Thor — DSV4Pro 27B, thinking/4K/no-spec | Local retained | 207 | v4 | **51.042** | not measured (n=1) | 10.0 |
| 19 | Road Runner practical — Qwen3.6 35B-A3B, low/8K/MTP3 | Local rejected practical | 183 | v4 | **49.542** | not measured (n=1) | 24.2 |
| 20 | Qwen3.8 27B Q4_K_M, off/4K/no-spec | Local comparison | 182 | v4 | **48.229** | not measured (n=1) | 28.1 |

## Top 10 local

This is strict score order, not a deployment recommendation. Critical reliability or retained-session failures can disqualify a high-scoring profile from unattended use.

| Rank | Local profile | Runs/evidence | Revision | Score used | Effective output t/s | Deployment status |
|---:|---|---:|---|---:|---:|---|
| 1 | Peregrine — Qwen3.8 27B W4A16, **vLLM 0.27**, FP8-KV/131K, low/8K/MTP3 | 213/214/215 | v4 | **61.006/65** | 39.3 | Retired runtime coordinate |
| 2 | **Peregrine — Qwen3.8 27B W4A16, vLLM 0.28, int8-KV/131K, low/8K/DFlash2 k7, top-p 0.95** | 232/233/234 | v5 | **57.970/65** | **58.1** | Production qualified |
| 3 | **Doctor Strange — Qwen3.8 27B Q4_K_M, low/8K/MTP2** | 180/181/201/217 | v4+v5 | **57.396/65** | 20.8 | Automatic fallback |
| 4 | Peregrine — Qwen3.8 27B W4A16, vLLM 0.28, int8-KV/131K, low/8K/DFlash2 k7, top-p 0.90 | 229/230/231 | v5 | **56.021/65** | 57.1 | Superseded production coordinate |
| 5 | Qwen3.8 + Sharp v22.3.1, low/8K/MTP2 | 208 | v4 | **55.417/65** | 20.2 | Rejected candidate |
| 6 | Cold Fusion, low/8K/MTP2 | 200/203 | v4 | **55.006/65** | 19.8 | Rejected candidate |
| 7 | Peregrine — Qwen3.8 27B W4A16, vLLM 0.28, FP8-KV/131K, low/8K/MTP3 | 218/219/220 | v5 | **54.771/65** | 43.0 | Superseded production coordinate |
| 8 | **Road Runner — Qwen3.6 35B-A3B, off/4K/MTP3** | 202/217 | v4+v5 | **54.042/65** | **159.2** | Bounded no-tools throughput specialist |
| 9 | **Spiderman — Tmax 27B, off/4K/MTP3** | 206 | v4 | **52.729/65** | 48.1 | Retained local profile |
| 10 | **Thor — DSV4Pro 27B, thinking/4K/no-spec** | 207 | v4 | **51.042/65** | 10.0 | Retained local profile |

The retired vLLM 0.27 Peregrine profile remains first by bounded-suite score but is not deployable. Production top-p-0.95 DFlash2 runs 232–234 were byte-identical at 57.970/65 and averaged 58.1 effective t/s; reliability-v2 passed 12/12 on PiBench-owned fixtures. Doctor Strange remains automatic fallback. Road Runner remains restricted to short, externally bounded no-tools work despite its throughput.

## RTX 3090 candidate decisions

| Profile | Runs | Revision | Score | Effective output t/s | Gate result |
|---|---:|---|---:|---:|---|
| Qwen3.8 W4A16 + DFlash2 k7, temperature 0.70 | 224/225/227 | v5 | **57.649/65** | **57.7** | Reject: both retained replays reached the mandatory guard without a final |
| Qwen3.8 W4A16 + DFlash2 k7, temperature 0.60, top-p 0.95 | 232/233/234 | v5 | **57.970/65** | **58.1** | Production: reliability-v2 12/12; hash-qualified |
| Qwen3.8 W4A16 + DFlash2 k7, temperature 0.60, top-p 0.90 | 229/230/231 | v5 | **56.021/65** | **57.1** | Superseded by top-p 0.95 |
| Qwen3.8 W4A16 + DFlash2 k7, temperature 0.55 | none | v5 | not scored | not scored | Cold replay finalized at 53 calls; hot replay and score not run after the external-project fixture was withdrawn |

DFlash2 temperatures 0.65, 0.625, and 0.61 were rejected by cache-hot retained replay before score testing. Run 226 ended after 6/24 tasks at a 9/9 weighted subset score and 91.5 effective t/s; it is excluded from the temperature-0.70 complete-run mean. Production uses temperature 0.60/top-p 0.95; Doctor Strange remains rollback.

See [RESULTS.md](RESULTS.md) for bridge and qualification evidence, [INFERENCE_PROFILES.md](INFERENCE_PROFILES.md) for tested local settings and portability limits, [METHODOLOGY.md](METHODOLOGY.md) for ranking rules, and [RESULTS.csv](RESULTS.csv) for sanitized task-level records.
