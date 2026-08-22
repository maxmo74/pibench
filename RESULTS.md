# Reference results

These runs were made on one reference workstation. They show observed model/profile behavior, not hardware-independent rankings.

- Suite: 24 tasks, 65 weighted points
- Snapshot: 2026-08-22
- Current benchmark input: Pi-agent protocol v4
- Effective system-prompt SHA-256: `33367c8eccc8213267c551069af9e5c781122b08fe36b5f1f736d29e5269f711`
- CPU: AMD Ryzen 9 7900, 12 cores / 24 threads
- RAM: 128 GB
- GPU: NVIDIA GeForce RTX 3090, 24 GB
- OS: Debian GNU/Linux 13, kernel 6.12.101+deb13-amd64
- NVIDIA driver: 550.163.01
- CUDA toolkit: 12.4.131

Protocol v4 pins Pi 0.84.1, fixes Pi's working directory, verifies the complete effective system prompt before a run, records its hash, and aborts if Pi changes the prompt. Pi 0.84.2 is rejected because it adds a trailing newline. Current local results use 131,072-token context, one parallel slot, quantized KV cache, full GPU offload, and seed 42 unless stated otherwise. Cloud profiles use their request-visible provider settings, listed separately below.

## Current protocol-v4 local profiles

| Rank | Model/profile | Class | Run | Score | Passed | Effective output t/s |
|---:|---|---|---:|---:|---:|---:|
| 1 | **Doctor Strange** — Qwen3.8 27B Q4_K_M, low reasoning, 8K output, Q4 MTP draft2 | Practical/long-output | 201 | **57.396/65** | 16/24 | 20.7 |
| 2 | **Road Runner** — Qwen3.6 35B-A3B Q4, thinking off, 4K output, MTP draft3 | Canonical 4K | 202 | **54.042/65** | 16/24 | **148.2** |
| 3 | **Spiderman** — Tmax 27B Q5, thinking off, 4K output, MTP draft3 | Canonical 4K | 206 | **52.729/65** | 15/24 | 48.1 |
| 4 | **Thor** — DSV4Pro 27B Q4, thinking on, 4K output, no speculation | Canonical 4K | 207 | **51.042/65** | 18/24 | 10.0 |
| 5 | Road Runner practical — Qwen3.6 35B-A3B Q4, low, 8K output, MTP draft3 | Rejected practical | 183 | **49.542/65** | 17/24 | 24.2 |
| 6 | Qwen3.8 27B Q4_K_M, thinking off, 4K output, no speculation | Canonical 4K | 182 | **48.229/65** | 14/24 | 28.1 |

Doctor Strange is deliberately a separate practical profile: it doubles the canonical output allowance and uses a quantized MTP sidecar. Stable-v0.2.0 run 201 produced byte-identical outputs on all 24 tasks to b10434 runs 180/181 while improving mean effective throughput from 20.40 to 20.70 t/s. MTP draft2 remains the measured quality/speed point because draft3 changed task outcomes.

Road Runner remains the throughput leader. Run 202 is its current stable-runtime normalization. Its 0.750-point difference from old b301 run 177 was reproduced on the three changing tasks with b10434, proving that v0.2.0 did not introduce the trajectory change. Doctor Strange remains the daily quality profile.

### Stable-runtime normalization and rejected candidates

Production now uses stable llama.cpp v0.2.0/b10566, commit `bb4caa754`. Spiderman run 206 improved from b301 run 178 by 1.161 points and matched 6/24 outputs; Thor run 207 fell by 2.188 points and matched 3/24. These are current runtime-specific results rather than claims of intrinsic weight changes.

| Candidate/profile | Runs | Score | Passed | Effective output t/s | Decision |
|---|---:|---:|---:|---:|---|
| Qwen3.8 + Sharp chat template v22.3.1, low/8K/MTP2 | 208 | **55.417/65** | 18/24 | 20.2 | Reject: below Doctor Strange and 19% slower end-to-end despite 21% less visible output |
| Cold Fusion GAIN V1.1, low/8K/MTP2 | 200/203 | **55.006/65** | 17/24 | 19.8 | Reject: exact score/runtime replay but below Doctor Strange and far slower than Road Runner |
| Ornith 1.5 35B-A3B AD-Q4 target-only, off/4K | 209 | **44.563/65** | 15/24 | 92.7 | Reject: lower quality and lower throughput than Road Runner; no MTP/thinking follow-up |

Road Runner low/8K on b10434 (run 183) scored **49.542/65 at 24.2 t/s**. Qwen3.6 maps low and medium to the same boolean thinking mode; the larger allowance mostly increased hidden reasoning, and JSON path plus semver produced effectively empty finals. That practical profile remains rejected.

## Current protocol-v4 OpenAI profiles

Each retained OpenAI profile received two complete runs through the OpenAI Codex Responses API. The table ranks the two-run mean and exposes the range because the service does not provide a seed-attested deterministic path.

| Rank | Model/profile | Runs | Mean score | Range | Mean effective output t/s |
|---:|---|---:|---:|---:|---:|
| 1 | GPT-5.5, high | 186/190 | **60.813/65** | 58.375–63.250 | 16.2 |
| 2 | GPT-5.5, medium | 185/189 | **59.625/65** | 57.208–62.042 | 19.7 |
| 3 | GPT-5.6 Sol, medium | 187/192 | **57.516/65** | 57.443–57.589 | 18.8 |
| 4 | GPT-5.6 Sol, high | 188/193 | **56.305/65** | 55.318–57.292 | 17.5 |
| 5 | GPT-5.4, medium | 184/191 | **54.277/65** | 54.277–54.277 | 23.1 |

All used protocol v4's pinned Pi 0.84.1, fixed cwd, effective-prompt hash, clean no-tools/no-context invocation, 272K registered context, and the provider-native 128K output ceiling. GPT-5.5 had unusually large 4.8-point ranges: JSON path and CSV inference changed outcomes between medium runs, while JSON path changed between high runs. GPT-5.4 repeated its score exactly but only 3/24 outputs were byte-identical, and GPT-5.6 Sol medium differed by only 0.146 point. Equal score is therefore described as score stability, not output determinism.

## Current protocol-v4 Antigravity profiles

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

## Current combined protocol-v4 ranking

This table uses the arithmetic mean of every equivalent complete run where repeats exist and a single complete run otherwise. Output allowances and reasoning controls remain part of each named profile; incomplete infrastructure runs are excluded.

| Rank | Model/profile | Class | Score used |
|---:|---|---|---:|
| 1 | Claude Opus 4.6 | Cloud antigravity-v1, three-run mean | **61.506** |
| 2 | GPT-5.5, high | Cloud native, two-run mean | **60.813** |
| 3 | GPT-5.5, medium | Cloud native, two-run mean | **59.625** |
| 4 | Gemini 3.7 Flash, medium | Cloud antigravity-v1, two-run mean | **58.408** |
| 5 | Gemini 3.1 Pro, high | Cloud antigravity-v1, two-run mean | **57.836** |
| 6 | GPT-5.6 Sol, medium | Cloud native, two-run mean | **57.516** |
| 7 | Doctor Strange — Qwen3.8 27B, low/8K/MTP2 | Local practical, exact runtime replay | **57.396** |
| 8 | GPT-5.6 Sol, high | Cloud native, two-run mean | **56.305** |
| 9 | Qwen3.8 + Sharp v22.3.1, low/8K/MTP2 | Local rejected template A/B | **55.417** |
| 10 | Cold Fusion, low/8K/MTP2 | Local rejected, exact two-run mean | **55.006** |
| 11 | GPT-5.4, medium | Cloud native, exact two-run mean | **54.277** |
| 12 | Road Runner — Qwen3.6 35B-A3B, off/4K/MTP3 | Local canonical | **54.042** |
| 13 | Spiderman — Tmax 27B, off/4K/MTP3 | Local canonical | **52.729** |
| 14 | Thor — DSV4Pro 27B, thinking/4K/no-spec | Local canonical | **51.042** |
| 15 | Road Runner practical — Qwen3.6 35B-A3B, low/8K/MTP3 | Local rejected practical | **49.542** |
| 16 | Qwen3.8 27B, off/4K/no-spec | Local canonical | **48.229** |
| 17 | Ornith 1.5 35B-A3B, target-only off/4K | Local rejected candidate | **44.563** |

The antigravity-v1 profiles' prompt variant (canonical + fixed extension injection) differs from the pure canonical input of the other profiles. Their corrected scores are shown in the combined ordering, but that boundary prevents a claim of byte-identical input equivalence.

## Tool-enabled multi-turn daily operations

`pi-ops-v1` is a separate 100-point profile and is not part of the 65-point ranking. Each model received the same three-turn persisted session, writable disposable repository, four Pi tools, hidden retry checks, systemd/README static checks, and scope/test-preservation checks.

| Model | Score | Tool calls | Wall time | Main deduction |
|---|---:|---:|---:|---|
| Doctor Strange | **100/100** | 27 | 225.7 s | none |
| Road Runner | **95/100** | 18 | **20.5 s** | omitted exact unittest command |
| Thor | **95/100** | 15 | 74.0 s | omitted exact unittest command |
| Spiderman | **85/100** | 18 | 53.6 s | omitted all three exact README commands |

All four passed every hidden retry check, every service/hardening check, preserved supplied tests, stayed within the allowed file scope, and completed all turns. Doctor Strange maximized instruction compliance; Road Runner delivered nearly the same score with the best operational latency. Attestation: PiBench commit `b124523`, Pi 0.84.1, attestor SHA-256 `0480e4d9c6e8b2b7905a10c78206b37ac45cd9203068140123e7f08e8c51d013`, effective system prompt SHA-256 `c9f6885987f161b6c530b108b61e2d6b173e1b79dd1caeac2ddc0fb7f18b6cb9`.

## Historical prompt-profile boundary

Pi versions through 0.80.6 silently appended `Current date: YYYY-MM-DD` to caller-supplied system prompts. Pi 0.82.0 removed that line. The benchmark previously recorded only the supplied prompt, not Pi's augmented effective prompt.

Restoring the exact historical dates reproduced the retained outputs byte-for-byte on all 24 tasks:

| Historical profile | Original score | Date-free replay | Exact historical-input replay |
|---|---:|---:|---:|
| Thor | 60.875 | 53.792 | 60.875 |
| Spiderman | 55.818 | 51.193 | 55.818 |
| Road Runner | 50.854 | 50.854 | 50.854 |
| Qwen3.6 27B Q4 MTP2 | 53.313 | 50.527 | 53.313 |

The old scores are authentic and reproducible for their exact inputs, but date-injected runs are not directly comparable across dates or with protocol v4. They remain in `RESULTS.csv` as historical evidence and are excluded from the current ranking. Direct endpoint benchmarks were unaffected.

## Historical cloud reference

Earlier cloud scores—including Claude Opus 4.8 at 60.2, GPT-5.5 high at 59.2, and GPT-5.6 Sol high at 58.9—belong to historical prompt profiles and remain historical evidence only. The OpenAI profiles and Claude Opus 4.6 now have protocol-v4 replacements above (Opus 4.6 via the antigravity-v1 profile); the historical Opus 4.8 and other pre-v4 Claude scores must not be mixed into the current ranking.

Effective output speed is visible output divided by end-to-end task time, not pure backend decode speed. The complete sanitized task-level history and reproducibility metadata are in [RESULTS.csv](RESULTS.csv). To contribute a result from another system, follow [README.md](README.md) and [METHODOLOGY.md](METHODOLOGY.md).
