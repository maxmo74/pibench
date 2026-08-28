# Reference results

These runs were made on one reference workstation. They show observed model/profile behavior, not hardware-independent rankings.

- Suite: 24 tasks, 65 weighted points
- Snapshot: 2026-08-29
- Score protocol: pi-agent-24/65
- Current Pi: 0.84.3; effective system-prompt SHA-256: `6b861f18cea399f742dc1a809914f8d6bf2ff30bb9f8c320ee50afb6f3bfebfc`
- CPU: AMD Ryzen 9 7900, 12 cores / 24 threads
- RAM: 128 GB
- GPU: NVIDIA GeForce RTX 3090, 24 GB
- OS: Debian GNU/Linux 13, kernel 6.12.101+deb13-amd64
- NVIDIA driver: 595.91.07 for current Peregrine production; earlier local results used 550.163.01
- CUDA toolkit: 12.4.131

Pi 0.84.3 adds a trailing newline to the effective prompt used under Pi 0.84.1. Because tasks, prompts, graders, weights, sandbox, and clean invocation were unchanged, four complete bridge runs tested score compatibility. Both deterministic local profiles reproduced all task outcomes and private outputs byte-for-byte; both GPT-5.5 profiles stayed within ordinary cloud variation. PiBench therefore kept one `pi-agent-24/65` score protocol. Every result retains its exact Pi version and prompt hash. Runtime, parallelism, sampler, seed, output allowance, and request history remain named profile coordinates.

## Pi 0.84.1 to 0.84.3 compatibility bridge

| Profile | Pi 0.84.1 score evidence | Pi 0.84.3 score | Passed | Raw points | Interpretation |
|---|---:|---:|---:|---:|---|
| GPT-5.5, medium | 57.208, 62.042 | **62.375/65** | 21/24 | 78/81 | Managed-service variation; one task differs from closest earlier run |
| GPT-5.5, high | 58.375, 63.250 | **59.250/65** | 21/24 | 79/81 | Inside the earlier range; one task differs from each earlier run |
| Doctor Strange, low | 57.396 | **57.396/65** | 16/24 | 71/81 | 24/24 outcomes and outputs byte-identical |
| Road Runner, off | 54.042 | **54.042/65** | 16/24 | 72/81 | 24/24 outcomes and outputs byte-identical |

## Current production profile

| Model/profile | Class | Evidence | Pi | Weighted score | Passed | Raw grader points | Effective output t/s |
|---|---|---:|---|---:|---:|---:|---:|
| **Peregrine** — Qwen3.8 27B W4A16, vLLM 0.28, int8 KV, low reasoning, 8K output, DFlash2 k7, top-p 0.95 | Production | 232/233/234 | 0.84.3 | **57.970/65** | 18/24 | 74/81 | **58.1** |

Runs 232–234 were complete clean-start repetitions. All three produced byte-identical private outputs, each scoring 57.970238/65; effective output ranged from 58.03 to 58.17 t/s with a 58.11 mean. The production coordinate is patched vLLM 0.28.0 at project PR head `55a5a99b` plus the `#48375` Mamba cache-tail backport, a W4A16 DFlash2 k7 drafter, int8-per-token-head attention KV, FP16 recurrent state, aligned prefix caching, synchronous scheduling, max-seqs 2, GPU utilization 0.87, 131,072 context, temperature 0.60/top-p 0.95/top-k 20, and no request seed. The reliability gate passed 12/12 using repeated PiBench-owned fixtures; no external-project replay was run.

The original vLLM 0.27 MTP3 coordinate reproduced a cache-hot three-call cycle. The superseded top-p-0.90 DFlash2 runs 229–231 scored 56.021/65 at 57.08 t/s. Changing only top-p to 0.95 improved the deterministic score by 1.949 points and mean effective throughput by 1.03 t/s. The hash-bound production gate includes the DFlash2 artifact, complete startup patch verification, PiBench-owned reliability evidence, and the Peregrine loop guard.

## 2026-08-29 public-model challenger search

A Firefox Playwright survey covered Hugging Face, Hacker News, Reddit, and inference forums under a stricter replacement gate: three complete runs at least 58.47/65 and 35 effective t/s, or within 0.10 points of Peregrine with at least 10% higher throughput. [MODEL_CANDIDATE_RESEARCH.md](MODEL_CANDIDATE_RESEARCH.md) records the source-linked decision matrix and every pre-screen rejection.

Opus Distill v2 Q4_K_M was the sole pre-screen winner. Its pinned artifact matched the publisher LFS digest before isolated loading. Complete run 235 used llama.cpp b10566, 131,072 context, 8,192 output, q4_0 KV, embedded MTP draft2, and low reasoning.

| Candidate coordinate | Complete runs | Score | Effective output t/s | Decision |
|---|---:|---:|---:|---|
| Qwen3.8-27B Opus Distill v2 Q4_K_M, low/8K/MTP2 | 235 | **52.318/65** | **32.9** | Reject: 6.152 points below the quality gate and 2.1 t/s below the speed floor |

No challenger qualified. Opus Distill v2 also failed reliability qualification at 9/12: the three context-recovery setup phases used tools instead of returning the exact readiness final and made out-of-scope calls. Score repeats were not run after the complete screen missed both primary gates. Peregrine remains production unchanged with its existing reliability 12/12, hash-bound certificate, healthy loopback router, and Doctor Strange rollback.

## DFlash sampler qualification

DFlash2 temperature 0.60/top-p 0.95 met the **57/65** and **35 effective t/s** gates across three deterministic complete runs and passed the reliability gate. It uses the same Qwen3.8 W4A16 target on patched vLLM 0.28 with a W4A16 k7 drafter, int8-per-token-head KV, prefix caching, synchronous scheduling, and max-seqs 2.

| Candidate coordinate | Complete runs | Mean score | Mean effective output t/s | Reliability/replay result | Decision |
|---|---:|---:|---:|---|---|
| DFlash2, temperature 0.70 | 224/225/227 | **57.649/65** | **57.7** | reliability 12/12; cold and cache-hot each hit the 60-call guard without a final | Reject: retained-session gate |
| DFlash2, temperature 0.65 | none | not scored | not scored | cold finalized at 59 calls; cache-hot hit the guard | Reject before score run |
| DFlash2, temperature 0.625 | none | not scored | not scored | cold finalized at 41 calls; cache-hot hit the guard | Reject before score run |
| DFlash2, temperature 0.61 | none | not scored | not scored | cold finalized at 58 calls; cache-hot hit the guard | Reject before score run |
| DFlash2, temperature 0.60, top-p 0.95 | 232/233/234 | **57.970/65** | **58.1** | reliability 12/12 on PiBench-owned repeated fixtures | Promote: production winner |
| DFlash2, temperature 0.60, top-p 0.90 | 229/230/231 | **56.021/65** | **57.1** | reliability 12/12; historical private replay evidence retained | Superseded by top-p 0.95 |
| DFlash2, temperature 0.55 | none | not scored | not scored | cold finalized normally at 53 calls; hot replay was not run after the external-project fixture was withdrawn | Reject: required replay pair incomplete; score not run |

Runs 232–234 are the production aggregate. Runs 229–231 establish the superseded top-p-0.90 baseline; exploratory run 228 produced the same score but is excluded from that aggregate. Runs 224, 225, and 227 were complete temperature-0.70 repetitions; run 226 ended after 6/24 tasks and is excluded. Sampler coordinates rejected by, or unable to complete, the retained replay gate were not score-tested. Doctor Strange remains rollback.

## Historical and bridged local profiles

| Rank | Model/profile | Class | Runs | Mean score | Passed | Mean effective output t/s |
|---:|---|---|---:|---:|---:|---:|
| 1 | **Peregrine** — Qwen3.8 27B W4A16, FP8 KV, low reasoning, 8K output, MTP3, temp 0.7 | Production practical/long-output | 213/214/215 | **61.006/65** | 18/24 | **39.3** |
| 2 | **Peregrine** — Qwen3.8 27B W4A16, int8 KV, low reasoning, 8K output, DFlash2 k7, temp 0.60/top-p 0.95 | Production practical/long-output | 232/233/234 | **57.970/65** | 18/24 | **58.1** |
| 3 | **Doctor Strange** — Qwen3.8 27B Q4_K_M, low reasoning, 8K output, Q4 MTP draft2 | Fallback practical/long-output | 180/181/201/217 | **57.396/65** | 16/24 | 20.8 |
| 4 | **Peregrine** — Qwen3.8 27B W4A16, int8 KV, low reasoning, 8K output, DFlash2 k7, temp 0.60/top-p 0.90 | Superseded practical/long-output | 229/230/231 | **56.021/65** | 16/24 | 57.1 |
| 5 | **Road Runner** — Qwen3.6 35B-A3B Q4, thinking off, 4K output, MTP draft3 | Canonical 4K | 202/217 | **54.042/65** | 16/24 | **159.2** |
| 6 | **Spiderman** — Tmax 27B Q5, thinking off, 4K output, MTP draft3 | Canonical 4K | 206 | **52.729/65** | 15/24 | 48.1 |
| 7 | Qwen3.8-27B Opus Distill v2 Q4_K_M, low reasoning, 8K output, embedded MTP draft2 | Rejected practical | 235 | **52.318/65** | 16/24 | 32.9 |
| 8 | **Thor** — DSV4Pro 27B Q4, thinking on, 4K output, no speculation | Canonical 4K | 207 | **51.042/65** | 18/24 | 10.0 |
| 9 | Road Runner practical — Qwen3.6 35B-A3B Q4, low, 8K output, MTP draft3 | Rejected practical | 183 | **49.542/65** | 17/24 | 24.2 |
| 10 | Qwen3.8 27B Q4_K_M, thinking off, 4K output, no speculation | Canonical 4K | 182 | **48.229/65** | 14/24 | 28.1 |

This Peregrine row is the frozen predecessor to the current production coordinate. Runs 213–215 were clean-start, byte-identical 24/24, and each scored 61.005952; their effective-output means were 39.26–39.43 t/s. The historical runtime is vLLM 0.27.1 at revision `00210159`, Qwen3.8-27B W4A16 AutoRound with quantized LM head/MTP and int8 embeddings, FP8 attention KV, FP16 recurrent state, MTP3 probabilistic drafting, aligned prefix caching, GPU utilization 0.87, max-seqs 8, 131,072 context, 8,192 output, temperature 0.7/top-p 0.9/top-k 20, server seed 0, and no request seed. Copyable settings, alternative modes, the separate llama.cpp fallback, and hardware/runtime applicability limits are in [INFERENCE_PROFILES.md](INFERENCE_PROFILES.md).

The official NVIDIA 595.91.07 packaged DKMS stack produced the same 160,620-token KV pool on three clean starts. A production context gate passed at 121,879 prompt tokens with an 8K answer reservation, at 129,040 tokens near the limit, and on a true-low 121,902-token request; cached follow-up was 62.78× faster. Two simultaneous 50K prompts and four simultaneous 16K prompts also passed. Minimum observed free VRAM was 2,039 MiB in the near-limit gate and 1,979 MiB in the concurrency gate at the retained 280 W limit.

A request-history control found an important boundary: an inference-based startup probe advanced vLLM's unseeded RNG and changed the clean-start score to 58.256/65. One greedy no-thinking readiness request preserved the 61.006 trajectory, while periodic production health now uses vLLM's engine-health RPC and model metadata only—no inference request. The final DB runs record `startup-health=greedy-no-thinking`, `periodic-health=engine-rpc-no-inference`, `server-seed=0`, `request-seed=none`, and `nvidia-gsp=off`. No best-task selection was used.

Doctor Strange remains a separate fallback practical profile: it doubles the older canonical output allowance and uses a quantized MTP sidecar. Stable-v0.2.0 run 201 produced byte-identical outputs on all 24 tasks to b10434 runs 180/181. Road Runner remains the bounded no-tools throughput leader; Doctor Strange remains the automatic rollback backend for Peregrine.

A later interactive reliability audit confirmed that Road Runner can enter severe repeated-tool and repeated-output loops on ambiguous investigations. The retained incident repeated one paragraph 43 times; exact b10566 replay failed to terminate with both MTP3 and target-only execution. Repeat penalty 1.1 suppressed literal repetition but not endless investigation, medium thinking exhausted the output allowance, and a prompt-level tool budget was ignored. MTP amplified duplication but was not the root cause.

A [Level1Techs inference-fidelity report](https://forum.level1techs.com/t/why-your-local-llm-feels-dumber-than-it-is/253917) motivated a long-context follow-up testing two additional hypotheses. Qwen's official non-thinking sampler (temperature 0.7, top-p 0.8, top-k 20, min-p 0, presence penalty 1.5) eventually stopped, but only after 73 tool calls and 13 repetitions of one read; its diagnosis remained incorrect/incomplete. Matched target-only Q8 and F16 KV controls each received the same 48,091-token initial prompt at 64K context and both timed out. Q8 made 28 calls with one read repeated seven times; F16 made 135 calls with one read repeated 126 times. KV precision materially changed the trajectory, but higher precision was not a monotonic correctness fix and Q4 KV is not the sole cause. This does not invalidate run 202's bounded score or throughput, but it demotes Road Runner from general autonomous use to a short, externally bounded throughput specialist.

### Qualification controls, fallback runtime, and rejected candidates

Peregrine's promotion was not based on its highest exploratory score. BF16-KV/80K scored 53.652/65 and passed 22/24 reliability scenario-runs. FP8-KV/131K at the original sampler scored 57.610/65 and passed 21/24. KVarN K4V2/240K appeared to score 62.854/65 with prefix caching, but combined perplexity regressed from about 8.09 to 9.30; disabling the cache restored perplexity and reduced PiBench to 49.313/65 with reliability 18/24. Historical vLLM 0.27 temperature-0.7 scored 61.006 but retained semantic failures; DFlash2 temperature-0.70 met the score floor but failed termination gates. Production therefore uses temperature 0.60/top-p 0.95, which met the score, throughput, and PiBench-owned reliability gates.

Stable llama.cpp v0.2.0/b10566, commit `bb4caa754`, remains installed as the rollback runtime. Spiderman run 206 improved from b301 run 178 by 1.161 points and matched 6/24 outputs; Thor run 207 fell by 2.188 points and matched 3/24. These are current runtime-specific results rather than claims of intrinsic weight changes.

| Candidate/profile | Runs | Score | Passed | Effective output t/s | Decision |
|---|---:|---:|---:|---:|---|
| Qwen3.8 + Sharp chat template v22.3.1, low/8K/MTP2 | 208 | **55.417/65** | 18/24 | 20.2 | Reject: below Doctor Strange and 19% slower end-to-end despite 21% less visible output |
| Cold Fusion GAIN V1.1, low/8K/MTP2 | 200/203 | **55.006/65** | 17/24 | 19.8 | Reject: exact score/runtime replay but below Doctor Strange and far slower than Road Runner |
| Qwen3.8-27B Opus Distill v2 Q4_K_M, low/8K/MTP2 | 235 | **52.318/65** | 16/24 | 32.9 | Reject: misses both primary gates; reliability not qualified at 9/12 |
| Ornith 1.5 35B-A3B AD-Q4 target-only, off/4K | 209 | **44.563/65** | 15/24 | 92.7 | Reject: lower quality and lower throughput than Road Runner; no MTP/thinking follow-up |

Road Runner low/8K on b10434 (run 183) scored **49.542/65 at 24.2 t/s**. Qwen3.6 maps low and medium to the same boolean thinking mode; the larger allowance mostly increased hidden reasoning, and JSON path plus semver produced effectively empty finals. That practical profile remains rejected.

## OpenAI profiles

Each retained OpenAI profile received complete runs through the OpenAI Codex Responses API. GPT-5.5 includes one Pi 0.84.3 bridge run in addition to two Pi 0.84.1 runs. The table ranks the complete-run mean and exposes the range because the service does not provide a seed-attested deterministic path.

| Rank | Model/profile | Runs | Mean score | Range | Mean effective output t/s |
|---:|---|---:|---:|---:|---:|
| 1 | GPT-5.5, medium | 185/189/216 | **60.542/65** | 57.208–62.375 | 19.8 |
| 2 | GPT-5.5, high | 186/190/216 | **60.292/65** | 58.375–63.250 | 15.9 |
| 3 | GPT-5.6 Sol, medium | 187/192 | **57.516/65** | 57.443–57.589 | 18.8 |
| 4 | GPT-5.6 Sol, high | 188/193 | **56.305/65** | 55.318–57.292 | 17.5 |
| 5 | GPT-5.4, medium | 184/191 | **54.277/65** | 54.277–54.277 | 23.1 |

The original runs used Pi 0.84.1; run 216 used Pi 0.84.3. All used the fixed cwd, attested effective-prompt revision, clean no-tools/no-context invocation, 272K registered context, and provider-native 128K output ceiling. GPT-5.5 had unusually large 4.8-point ranges: JSON path and CSV inference changed outcomes between medium runs, while JSON path changed between high runs. GPT-5.4 repeated its score exactly but only 3/24 outputs were byte-identical, and GPT-5.6 Sol medium differed by only 0.146 point. Equal score is therefore described as score stability, not output determinism.

## Frozen Antigravity prompt profiles

Antigravity (Google Cloud Code Assist) results run under the **antigravity-v1** versioned extension profile: the `pi-antigravity` 0.3.1 extension is pinned, and its fixed three-part system-instruction injection (sha256 `1416c1c4…eb9b39`) is attested against the installed source before every run. The full effective prompt sent to the model is therefore frozen as canonical prompt + fixed injection, but it is **not byte-identical to the pure canonical prompt** used by the OpenAI profiles; antigravity-v1 scores are comparable within the profile and across antigravity models, but sit on a different prompt variant.

| Model/profile | Runtime | Runs | Mean score | Range | Mean effective output t/s |
|---|---|---:|---:|---:|---:|
| Claude Opus 4.6 | claude-opus-4-6-thinking (thinking always on, no effort tiers) | 198/199/204 | **61.506/65** | 60.810–62.604 | 40.5 |
| Gemini 3.7 Flash, medium | gemini-3.7-flash-tiered, thinkingConfig MEDIUM | 194/195 | **58.408/65** | 58.372–58.443 | 58.0 |
| Gemini 3.1 Pro, high | gemini-pro-agent (high) | 196/197 | **57.836/65** | 54.479–61.193 | 13.8 |

Earlier prose incorrectly summarized Antigravity with the sum of weights for fully passing tasks, while `RESULTS.csv`, local profiles, OpenAI profiles, and the documented methodology all award proportional credit on independently scored checks. The corrected values above use the authoritative CSV formula. The task rows, pass counts, and raw grader values are unchanged.

Flash medium passed 18/24 in both runs and has the tightest Antigravity score range. Its recurring full-task failures still include JSON path, retry schedule, changelog, ADR, and design review, but partial checks preserve the credit it earned. Its ~58 t/s mean is the fastest cloud profile measured here.

The third Opus repeat, run 204, scored 61.104/65 with 19/24 full passes at 41.5 t/s. Across all three equivalent complete runs, Opus averages 61.506 with a 1.795-point range, replacing the misleading 9-point binary-pass range. It is the strongest Antigravity profile, though its fixed injected prompt keeps it on a distinct input variant from pure-canonical profiles.

Pro high remains slower and more variable than Flash: its 6.714-point range is driven mainly by unified diff and JSON-path behavior. Flash medium is the stronger Gemini profile on mean, stability, and throughput. A Sonnet 4.6 attempt (run 205) exhausted the shared Claude quota after 7/24 tasks; it is explicitly `incomplete-infrastructure`, excluded from every aggregate, and may be completed only after the provider reset.

## Combined pi-agent-24/65 ranking (22 eligible)

This table uses the arithmetic mean of every equivalent complete run, including bridge-qualified Pi versions, and a single complete run otherwise. Every run retains its measured Pi version in [RESULTS.csv](RESULTS.csv).

| Rank | Model/profile | Class | Score used |
|---:|---|---|---:|
| 1 | Claude Opus 4.6 | Cloud antigravity-v1 | **61.506** |
| 2 | Peregrine, vLLM 0.27, low/8K/MTP3 | Local retired | **61.006** |
| 3 | GPT-5.5, medium | Cloud native, Pi 0.84.1/0.84.3 mean | **60.542** |
| 4 | GPT-5.5, high | Cloud native, Pi 0.84.1/0.84.3 mean | **60.292** |
| 5 | Gemini 3.7 Flash, medium | Cloud antigravity-v1 | **58.408** |
| 6 | **Peregrine, vLLM 0.28, low/8K/DFlash2 k7, top-p 0.95** | Local production, exact three-run mean | **57.970** |
| 7 | Gemini 3.1 Pro, high | Cloud antigravity-v1 | **57.836** |
| 8 | GPT-5.6 Sol, medium | Cloud native | **57.516** |
| 9 | Doctor Strange, low/8K/MTP2 | Local fallback, Pi-version exact replay | **57.396** |
| 10 | GPT-5.6 Sol, high | Cloud native | **56.305** |
| 11 | Peregrine, vLLM 0.28, low/8K/DFlash2 k7, top-p 0.90 | Local predecessor | **56.021** |
| 12 | Qwen3.8 + Sharp v22.3.1, low/8K/MTP2 | Local rejected | **55.417** |
| 13 | Cold Fusion, low/8K/MTP2 | Local rejected | **55.006** |
| 14 | Peregrine, vLLM 0.28, low/8K/MTP3 | Local predecessor | **54.771** |
| 15 | GPT-5.4, medium | Cloud native | **54.277** |
| 16 | Road Runner, off/4K/MTP3 | Local bounded, Pi-version exact replay | **54.042** |
| 17 | Spiderman, off/4K/MTP3 | Local retained | **52.729** |
| 18 | Qwen3.8-27B Opus Distill v2, low/8K/MTP2 | Local rejected | **52.318** |
| 19 | Thor, thinking/4K/no-spec | Local retained | **51.042** |
| 20 | Road Runner practical, low/8K/MTP3 | Local rejected | **49.542** |
| 21 | Qwen3.8 27B, off/4K/no-spec | Local comparison | **48.229** |
| 22 | Ornith 1.5, target-only off/4K | Local rejected | **44.563** |

The Antigravity prompt variant remains explicitly labeled because its fixed extension injection is not byte-identical to pure-canonical input.

## Tool-enabled multi-turn daily operations

`pi-ops-v1` is a separate 100-point profile and is not part of the 65-point ranking. Each model received the same three-turn persisted session, writable disposable repository, four Pi tools, hidden retry checks, systemd/README static checks, and scope/test-preservation checks.

| Model | Score | Tool calls | Wall time | Main deduction |
|---|---:|---:|---:|---|
| **Peregrine** | **100/100** | **19** | **59.3 s** | none |
| Doctor Strange | **100/100** | 27 | 225.7 s | none |
| Road Runner | **95/100** | 18 | **20.5 s** | omitted exact unittest command |
| Thor | **95/100** | 15 | 74.0 s | omitted exact unittest command |
| Spiderman | **85/100** | 18 | 53.6 s | omitted all three exact README commands |

All profiles passed every hidden retry check, every service/hardening check, preserved supplied tests, stayed within the allowed file scope, and completed all turns. Peregrine and Doctor Strange both maximized instruction compliance; Peregrine used eight fewer tools and completed about 3.8× faster. Peregrine attestation used PiBench tip `0b0dbf6`; the older four used commit `b124523`. All used Pi 0.84.1, attestor SHA-256 `0480e4d9c6e8b2b7905a10c78206b37ac45cd9203068140123e7f08e8c51d013`, effective system prompt SHA-256 `c9f6885987f161b6c530b108b61e2d6b173e1b79dd1caeac2ddc0fb7f18b6cb9`.

These three structured, convergent turns do not test open-ended exploration or guaranteed termination. The Road Runner loop audit demonstrates that its 95/100 result must not be generalized to unattended ambiguous work. The separate experimental reliability gate below begins testing that missing dimension without changing this historical profile.

## Agent reliability gate

The merged `pi_agent_reliability_bench.py` runner pins Pi 0.84.3, retains the four scenario classes, loads the production loop guard, and is mandatory for current Peregrine promotion. Packaged vLLM 0.28 Peregrine passed 12/12. Earlier Pi 0.84.1 evidence below remains historical qualification evidence. Four read-only scenarios run twice: evidence-backed diagnosis, missing-evidence termination, recovery after a large irrelevant preamble, and a deterministic polling trap with repository-scope enforcement.

| Model | Screen result | Scenario-runs | Tools | Wall time including context setup | Failure |
|---|---|---:|---:|---:|---|
| **Peregrine, low, temp 0.7** | **qualified** | **24/24** | 149 | 490.2 s | none; separate retained-session semantic warning |
| Doctor Strange, low | **qualified** | **8/8** | 53 | 404.9 s | none |
| Spiderman, off | **qualified** | **8/8** | 50 | 179.2 s | none |
| **GPT-5.6 Sol, medium** | **qualified** | **8/8** | 52 | **154.8 s** | none |
| GPT-5.6 Sol, high | **not qualified** | 7/8 | 53 | 178.2 s | one polling-trap run attempted environment enumeration outside the fixture |
| GPT-5.6 Sol, xhigh | **not qualified** | 7/8 | 57 | 197.0 s | one polling-trap run attempted environment and neighboring-temporary-file enumeration |
| Road Runner, off | **not qualified** | 6/8 | 68 | **79.0 s** | both polling-trap runs searched outside the fixture; one also exceeded its 10-tool budget |
| Thor, medium | **not qualified** | 6/8 | 50 | 224.6 s | ran the unchanged polling diagnostic twice in both repeats |

Peregrine also passed an additional 8/8 suite after installation on the packaged production stack. Its 24/24 row is the three-suite final qualification coordinate and is kept separate from the three retained real-session replays that all selected the wrong CSS fix. All profiles completed their other scenario-runs with normal semantic answers and no timeouts. Road Runner's failures are consistent with its broader tendency to continue searching after repository evidence is exhausted: the two failed runs made seven out-of-scope calls in total, while the first also used 14 tools. Thor's duplicate was the exact same `./scripts/diagnose.sh` command each time even though the fixture states that its read-only output cannot change. Sol high and xhigh showed no looping, duplicate, budget, timeout, or answer failure; each missed strict qualification only because one polling-trap repeat tried to inspect process/temporary context beyond the repository. The attested scope guard blocked those calls and Sol still stopped with a correct answer. Sol medium, Doctor Strange, and Spiderman had no gate failures.

Peregrine attestation: PiBench tip `0b0dbf6`. Earlier local attestation: commit `041ebad`. Credential-isolated Sol attestation: commit `3e6638a`, scope-guard SHA-256 `414af68b47ac74f90f147a5dbe9c22b0fadf44958081dca4030656270920b8b8`. All use Pi 0.84.1, attestor SHA-256 `0480e4d9c6e8b2b7905a10c78206b37ac45cd9203068140123e7f08e8c51d013`, and effective system-prompt SHA-256 `ff3ea23421c72a5483e411cf92d2e7b0ca1d1a82dfb5dc9c1cadf9d3dcf1262d`. Raw text and credentials remain private; retained results contain checks, metrics, timings, and hashes only. This initial screen is intentionally conservative and remains experimental: passing is useful qualification evidence, not proof against every future loop.

## Historical prompt-profile boundary

Pi versions through 0.80.6 silently appended `Current date: YYYY-MM-DD` to caller-supplied system prompts. Pi 0.82.0 removed that line. The benchmark previously recorded only the supplied prompt, not Pi's augmented effective prompt.

Restoring the exact historical dates reproduced the retained outputs byte-for-byte on all 24 tasks:

| Historical profile | Original score | Date-free replay | Exact historical-input replay |
|---|---:|---:|---:|
| Thor | 60.875 | 53.792 | 60.875 |
| Spiderman | 55.818 | 51.193 | 55.818 |
| Road Runner | 50.854 | 50.854 | 50.854 |
| Qwen3.6 27B Q4 MTP2 | 53.313 | 50.527 | 53.313 |

The old scores are authentic and reproducible for their exact inputs, but date-injected runs are not directly comparable across dates or with the current score protocol. They remain in `RESULTS.csv` as historical evidence and are excluded from the current ranking. Direct endpoint benchmarks were unaffected.

## Historical cloud reference

Earlier cloud scores—including Claude Opus 4.8 at 60.2, GPT-5.5 high at 59.2, and GPT-5.6 Sol high at 58.9—belong to historical prompt profiles and remain historical evidence only. The OpenAI profiles and Claude Opus 4.6 now have date-free replacements above (Opus 4.6 via the antigravity-v1 profile); the historical Opus 4.8 and other date-injected Claude scores must not be mixed into the current ranking.

Effective output speed is visible output divided by end-to-end task time, not pure backend decode speed. The complete sanitized task-level history and reproducibility metadata are in [RESULTS.csv](RESULTS.csv). To contribute a result from another system, follow [README.md](README.md) and [METHODOLOGY.md](METHODOLOGY.md).
