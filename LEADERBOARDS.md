# PiBench leaderboards

Snapshot: **2026-08-28** · Protocols: **pi-agent-v5 current; pi-agent-v4 frozen** · Maximum score: **65**

These are profile rankings, not model-only rankings. Runtime, quantization, context, output allowance, reasoning control, sampler, speculation, and request history are part of a profile. Repeated equivalent runs use their arithmetic mean and observed range; no best-run or best-task splicing is used. Incomplete infrastructure runs are excluded. Protocol versions are ranked separately because their effective prompts differ.

The Antigravity rows use the frozen `antigravity-v1` prompt variant (canonical prompt plus an attested fixed injection), not the byte-identical pure-canonical input used by local and OpenAI profiles. They remain visible in the overall ordering with that boundary disclosed.

## Protocol-v5 Top 20 overall

Protocol v5 pins Pi 0.84.3 and attests effective-system-prompt SHA-256 `6b861f18cea399f742dc1a809914f8d6bf2ff30bb9f8c320ee50afb6f3bfebfc`. There is currently one eligible complete profile; the table grows as models receive a full v5 run.

| Rank | Model/profile | Class | Runs | Weighted score | Full-task pass | Raw grader points | Effective output t/s |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | **Peregrine — Qwen3.8 27B W4A16, vLLM 0.28, FP8-KV/131K, low/8K/MTP3** | Local production | 1 | **57.818/65** | 17/24 | 74/81 | **42.7** |

One run has no observed range and does not establish determinism. The score uses weighted partial credit; 74/81 is descriptive raw grader output, not the ranking denominator.

## Protocol-v5 Top 10 local

| Rank | Local profile | Runs | Weighted score | Effective output t/s | Deployment status |
|---:|---|---:|---:|---:|---|
| 1 | **Peregrine — Qwen3.8 27B W4A16, vLLM 0.28, FP8-KV/131K, low/8K/MTP3** | 1 | **57.818/65** | **42.7** | Production qualified; Doctor Strange rollback |

## Protocol-v4 Top 20 overall

There are **18 eligible complete protocol-v4 profiles**. This table is frozen for Pi 0.84.1 history and gradual v5 migration. The table intentionally stops at 18 rather than padding the Top 20 with historical, incomplete, or private qualification runs.

| Rank | Model/profile | Class | Runs | Mean score | Observed range | Effective output t/s |
|---:|---|---|---:|---:|---:|---:|
| 1 | Claude Opus 4.6 | Cloud antigravity-v1 | 198/199/204 | **61.506** | 60.810–62.604 | 40.5 |
| 2 | **Peregrine — Qwen3.8 27B W4A16, FP8-KV/131K, low/8K/MTP3** | Local production | 213/214/215 | **61.006** | 61.006–61.006 | 39.3 |
| 3 | GPT-5.5, high | Cloud native | 186/190 | **60.813** | 58.375–63.250 | 16.2 |
| 4 | GPT-5.5, medium | Cloud native | 185/189 | **59.625** | 57.208–62.042 | 19.7 |
| 5 | Gemini 3.7 Flash, medium | Cloud antigravity-v1 | 194/195 | **58.408** | 58.372–58.443 | 58.0 |
| 6 | Gemini 3.1 Pro, high | Cloud antigravity-v1 | 196/197 | **57.836** | 54.479–61.193 | 13.8 |
| 7 | GPT-5.6 Sol, medium | Cloud native | 187/192 | **57.516** | 57.443–57.589 | 18.8 |
| 8 | Doctor Strange — Qwen3.8 27B Q4_K_M, low/8K/MTP2 | Local fallback | 180/181/201 | **57.396** | 57.396–57.396 | 20.7 |
| 9 | GPT-5.6 Sol, high | Cloud native | 188/193 | **56.305** | 55.318–57.292 | 17.5 |
| 10 | Qwen3.8 + Sharp v22.3.1, low/8K/MTP2 | Local rejected candidate | 208 | **55.417** | not measured (n=1) | 20.2 |
| 11 | Cold Fusion, low/8K/MTP2 | Local rejected candidate | 200/203 | **55.006** | 55.006–55.006 | 19.8 |
| 12 | GPT-5.4, medium | Cloud native | 184/191 | **54.277** | 54.277–54.277 | 23.1 |
| 13 | Road Runner — Qwen3.6 35B-A3B, off/4K/MTP3 | Local bounded | 202 | **54.042** | not measured (n=1) | **148.2** |
| 14 | Spiderman — Tmax 27B, off/4K/MTP3 | Local retained | 206 | **52.729** | not measured (n=1) | 48.1 |
| 15 | Thor — DSV4Pro 27B, thinking/4K/no-spec | Local retained | 207 | **51.042** | not measured (n=1) | 10.0 |
| 16 | Road Runner practical — Qwen3.6 35B-A3B, low/8K/MTP3 | Local rejected practical | 183 | **49.542** | not measured (n=1) | 24.2 |
| 17 | Qwen3.8 27B Q4_K_M, off/4K/no-spec | Local comparison | 182 | **48.229** | not measured (n=1) | 28.1 |
| 18 | Ornith 1.5 35B-A3B AD-Q4, target-only off/4K | Local rejected candidate | 209 | **44.563** | not measured (n=1) | 92.7 |

## Protocol-v4 Top 10 local

This is strict score order, not a deployment recommendation. Critical reliability or retained-session failures can disqualify a high-scoring profile from unattended use.

| Rank | Local profile | Runs | Score used | Effective output t/s | Deployment status |
|---:|---|---:|---:|---:|---|
| 1 | **Peregrine — Qwen3.8 27B W4A16, FP8-KV/131K, low/8K/MTP3** | 213/214/215 | **61.006/65** | 39.3 | Production, supervised consequential edits |
| 2 | **Doctor Strange — Qwen3.8 27B Q4_K_M, low/8K/MTP2** | 180/181/201 | **57.396/65** | 20.7 | Automatic fallback and autonomous default |
| 3 | Qwen3.8 + Sharp v22.3.1, low/8K/MTP2 | 208 | **55.417/65** | 20.2 | Rejected candidate |
| 4 | Cold Fusion, low/8K/MTP2 | 200/203 | **55.006/65** | 19.8 | Rejected candidate |
| 5 | **Road Runner — Qwen3.6 35B-A3B, off/4K/MTP3** | 202 | **54.042/65** | **148.2** | Bounded no-tools throughput specialist |
| 6 | **Spiderman — Tmax 27B, off/4K/MTP3** | 206 | **52.729/65** | 48.1 | Retained local profile |
| 7 | **Thor — DSV4Pro 27B, thinking/4K/no-spec** | 207 | **51.042/65** | 10.0 | Retained local profile |
| 8 | Road Runner practical, low/8K/MTP3 | 183 | **49.542/65** | 24.2 | Rejected practical profile |
| 9 | Qwen3.8 27B Q4_K_M, off/4K/no-spec | 182 | **48.229/65** | 28.1 | Comparison profile |
| 10 | Ornith 1.5 35B-A3B AD-Q4, target-only off/4K | 209 | **44.563/65** | 92.7 | Rejected candidate |

The protocol-v4 Peregrine row describes the retired vLLM 0.27 benchmark coordinate. The current vLLM 0.28 production coordinate passed packaged reliability-v2 12/12 and completed cold plus cache-hot replays of the prior looping session without duplicate calls or cycles. Doctor Strange remains automatic fallback. Road Runner remains restricted to short, externally bounded no-tools work despite its throughput.

See [RESULTS.md](RESULTS.md) for qualification evidence and separate operations/reliability tables, [INFERENCE_PROFILES.md](INFERENCE_PROFILES.md) for tested local settings and portability limits, [METHODOLOGY.md](METHODOLOGY.md) for ranking rules, and [RESULTS.csv](RESULTS.csv) for the sanitized task-level records.
