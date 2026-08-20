# Reference results

These runs were made on one reference workstation. They show observed model/profile behavior, not hardware-independent rankings.

- Suite: 24 tasks, 65 weighted points
- Snapshot: 2026-08-19
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
| 1 | **Doctor Strange** — Qwen3.8 27B Q4_K_M, low reasoning, 8K output, Q4 MTP draft2 | Practical/long-output | 180/181 | **57.396/65** | 16/24 | 20.4 |
| 2 | **Road Runner** — Qwen3.6 35B-A3B Q4, thinking off, 4K output, MTP draft3 | Canonical 4K | 177 | **54.792/65** | 17/24 | **144.9** |
| 3 | **Thor** — DSV4Pro 27B Q4, thinking on, 4K output, no speculation | Canonical 4K | 179 | **53.229/65** | 17/24 | 9.3 |
| 4 | **Spiderman** — Tmax 27B Q5, thinking off, 4K output, MTP draft3 | Canonical 4K | 178 | **51.568/65** | 13/24 | 47.8 |
| 5 | Road Runner practical — Qwen3.6 35B-A3B Q4, low, 8K output, MTP draft3 | Rejected practical | 183 | **49.542/65** | 17/24 | 24.2 |
| 6 | Qwen3.8 27B Q4_K_M, thinking off, 4K output, no speculation | Canonical 4K | 182 | **48.229/65** | 14/24 | 28.1 |

Doctor Strange is deliberately a separate practical profile: it doubles the canonical output allowance and uses a quantized MTP sidecar. Runs 180 and 181 were exact repeats and produced byte-identical outputs on all 24 tasks. MTP draft2 was retained because draft3 was faster but changed task outcomes in paired testing.

Road Runner remains the throughput leader. Doctor Strange is the current daily quality profile; its low reasoning setting and 8K allowance avoid the output-exhaustion failures observed with Qwen3.8's medium/xhigh behavior.

### Rejected Road Runner practical profile

Road Runner low/8K on current llama.cpp b10434 (run 183) scored **49.542/65 at 24.2 effective visible tok/s**, versus its off/4K run at **54.792/65 and 144.9 tok/s**. Qwen3.6 maps low and medium to the same boolean thinking mode rather than Qwen3.8's graduated effort. The larger allowance mostly increased hidden reasoning; JSON path and semver produced effectively empty finals. The low/8K profile is rejected, and Road Runner remains configured off/4K.

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
| Claude Opus 4.6 | claude-opus-4-6-thinking (thinking always on, no effort tiers) | 198/199 | **52.500/65** | 48.000–57.000 | 40.0 |
| Gemini 3.7 Flash, medium | gemini-3.7-flash-tiered, thinkingConfig MEDIUM | 194/195 | **46.750/65** | 46.500–47.000 | 58.0 |
| Gemini 3.1 Pro, high | gemini-pro-agent (high) | 196/197 | **44.250/65** | 41.000–47.500 | 13.8 |

Flash medium passed 18/24 in both runs; its recurring failures are JSON path (invalid-input rejection), retry schedule (2/3), changelog (5/6), ADR (6/7), and design review (7/8). Its effective throughput (~58 tok/s) makes it the fastest cloud profile measured so far.

Claude Opus 4.6 is the strongest antigravity profile so far (52.500 mean, ~40 tok/s) and the first cloud model on this profile to pass 20+ tasks in a single run (run 198: 21/24). Its 9-point range is the largest measured on any profile: the runs passed 21/24 and 18/24, with `retry_schedule_hard` (3/3 → 2/3), `log_triage_incident` (7/7 → 6/7), and `design_review_find_flaws` (8/8 → 7/8) flipping, while `markdown_table_hard` (2/4) and `changelog_from_commits` (5/6) failed both runs. A further repeat would tighten the mean.

Pro high is slower (~14 tok/s) and more variable: the two runs passed 18/24 and 17/24 with a 6.5-point range, driven by `unified_diff_hard` moving 3/3 → 1/3 and `json_path_set_hard` flipping between runs. Under this profile, the cheaper flash model at medium reasoning outscored pro at high reasoning on both mean and range, so flash medium is the stronger antigravity profile for Gemini workloads; Claude Opus 4.6 is the strongest overall antigravity profile.

## Current combined protocol-v4 ranking

This table combines two-run means where repeats exist and single complete runs otherwise. Output allowances and reasoning controls remain part of each named profile.

| Rank | Model/profile | Class | Score used |
|---:|---|---|---:|
| 1 | GPT-5.5, high | Cloud native, two-run mean | **60.813** |
| 2 | GPT-5.5, medium | Cloud native, two-run mean | **59.625** |
| 3 | GPT-5.6 Sol, medium | Cloud native, two-run mean | **57.516** |
| 4 | Doctor Strange — Qwen3.8 27B, low/8K/MTP2 | Local practical, exact two-run mean | **57.396** |
| 5 | GPT-5.6 Sol, high | Cloud native, two-run mean | **56.305** |
| 6 | Road Runner — Qwen3.6 35B-A3B, off/4K/MTP3 | Local canonical | **54.792** |
| 7 | GPT-5.4, medium | Cloud native, exact two-run mean | **54.277** |
| 8 | Thor — DSV4Pro 27B, thinking/4K/no-spec | Local canonical | **53.229** |
| 9 | Claude Opus 4.6 | Cloud antigravity-v1 profile, two-run mean | **52.500** |
| 10 | Spiderman — Tmax 27B, off/4K/MTP3 | Local canonical | **51.568** |
| 11 | Road Runner practical — Qwen3.6 35B-A3B, low/8K/MTP3 | Local rejected practical | **49.542** |
| 12 | Qwen3.8 27B, off/4K/no-spec | Local canonical | **48.229** |
| 13 | Gemini 3.7 Flash, medium | Cloud antigravity-v1 profile, two-run mean | **46.750** |
| 14 | Gemini 3.1 Pro, high | Cloud antigravity-v1 profile, two-run mean | **44.250** |

The antigravity-v1 profiles' prompt variant (canonical + fixed extension injection) differs from the pure canonical input of the other profiles, so their ranks are reported within the combined ordering but on a distinct input variant.

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
