# PiBench leaderboards

Snapshot: **2026-09-20** · Score protocol: **pi-agent-24/65** · Runner pin: **0.84.3**

These are selected protocol-compatible **configuration rankings**, not an exhaustive
ranking of every historical run or a deployment recommendation. The selection
retains the prior 22 profiles, adds the documented rejected DFlash temperature-0.70
coordinate, and includes today's complete candidate screens and Astra runs.
Failed infrastructure runs, incomplete runs and the misconfigured reasoning run
are excluded. Candidate and retired rows remain visibly unqualified.

Scores are arithmetic means of complete runs; no best-task or best-run splicing.
Effective speed is total approximate visible output tokens divided by total wall
time across the listed runs, including reasoning latency. It is not raw decode
speed or a mean of task rates. All speeds here were recomputed from RESULTS.csv;
older prose may use legacy per-task means. In particular, retired runs 213–215
have **37.81** aggregate t/s, not the previously labelled 39.3 effective t/s.

Pi 0.84.1 and 0.84.3 retain their qualified prompt-version boundary and exact
version labels. Antigravity uses a separate attested injected-prompt variant;
its rows are displayed together for navigation, not identical-input comparisons.
The Pi 0.86.1 bridge pilot remains limited to a no-tool subset; it does not change
the public runner pin. See [methodology](METHODOLOGY.md).

**Production remains Peregrine v0.28. Doctor Strange remains fallback.**
GPU-5 is labelled **Gandalf candidate**, not promoted. Higher score alone is
insufficient: cache-hot, retained-session and full-context qualification matter.

## Top 20 overall

| Rank | Profile | Class/status | Runs | Pi | Mean /65 | Score range | Effective t/s |
|---:|---|---|---|---|---:|---|---:|
| 1 | Claude Opus 4.6 | Cloud: Antigravity prompt variant | 198/199/204 | 0.84.1 | **61.506** | 60.810–62.604 | 47.45 |
| 2 | Peregrine v0.27 MTP3, historical | Local: Retired; termination failures | 213/214/215 | 0.84.1 | **61.006** | 61.006–61.006 | 37.81 |
| 3 | GPT-5.5 medium | Cloud: Native API | 185/189/216 | 0.84.1/0.84.3 | **60.542** | 57.208–62.375 | 20.91 |
| 4 | GPT-5.5 high | Cloud: Native API | 186/190/216 | 0.84.1/0.84.3 | **60.292** | 58.375–63.250 | 12.36 |
| 5 | v0.27 FP8 target-only, t0.70/p0.90 | Local: Near miss; preliminary reliability 4/4 | 253 | 0.84.3 | **59.214** | n=1 | 17.83 |
| 6 | Gemini 3.7 Flash medium | Cloud: Antigravity prompt variant | 194/195 | 0.84.1 | **58.408** | 58.372–58.443 | 65.50 |
| 7 | GPU-5 DFlash2 k7, t1.00 | Local: Candidate; unqualified | 241 | 0.84.3 | **58.399** | n=1 | 18.02 |
| 8 | GPU-5 DFlash2 k7, t0.60 (Gandalf candidate) | Local: Candidate; reliability 12/12 | 238/239/240 | 0.84.3 | **58.318** | 58.318–58.318 | 22.43 |
| 9 | Peregrine v0.28 DFlash2 k7, t0.60/p0.95 | Local: Production; reliability 12/12 | 232/233/234 | 0.84.3 | **57.970** | 57.970–57.970 | 58.11 |
| 10 | Gemini 3.1 Pro high | Cloud: Antigravity prompt variant | 196/197 | 0.84.1 | **57.836** | 54.479–61.193 | 12.93 |
| 11 | Patched v0.29 int8 DFlash2 k7, t0.60 | Local: Candidate; reliability 12/12 | 243/244 | 0.84.3 | **57.792** | 57.792–57.792 | 51.05 |
| 12 | Peregrine v0.28 DFlash2 k7, t0.70 | Local: Rejected; retained-session failures | 224/225/227 | 0.84.3 | **57.649** | 57.649–57.649 | 57.73 |
| 13 | GPT-5.6 Sol medium | Cloud: Native API | 187/192 | 0.84.1 | **57.516** | 57.443–57.589 | 21.28 |
| 14 | Doctor Strange, MTP2 | Local: Fallback | 180/181/201/217 | 0.84.1/0.84.3 | **57.396** | 57.396–57.396 | 21.65 |
| 15 | Patched v0.29 FP8 MTP3, t0.70 | Local: Below quality gate | 246 | 0.84.3 | **57.354** | n=1 | 40.98 |
| 16 | v0.27 FP8 MTP3 reconstruction, t0.70 | Local: Not historical reproduction | 248/249 | 0.84.1/0.84.3 | **56.568** | 56.568–56.568 | 36.15 |
| 17 | GPT-5.6 Sol high | Cloud: Native API | 188/193 | 0.84.1 | **56.305** | 55.318–57.292 | 18.53 |
| 18 | GPT-6 Astra medium | Cloud: Native API; two runs | 236/237 | 0.84.3 | **56.241** | 55.372–57.110 | 21.16 |
| 19 | Peregrine v0.28 DFlash2 k7, t0.60/p0.90 | Local: Superseded | 229/230/231 | 0.84.3 | **56.021** | 56.021–56.021 | 57.08 |
| 20 | GPT-6 Astra high | Cloud: Native API; two runs | 236/237 | 0.84.3 | **55.909** | 54.881–56.938 | 18.70 |

## Top 20 cloud

Ten cloud profiles are currently included in the selected ranking. This table
lists up to 20 using the same complete-run means and aggregate throughput as
above. Antigravity's distinct prompt variant remains labelled; incomplete
infrastructure runs are excluded.

| Rank | Profile | Class/status | Runs | Pi | Mean /65 | Score range | Effective t/s |
|---:|---|---|---|---|---:|---|---:|
| 1 | Claude Opus 4.6 | Cloud: Antigravity prompt variant | 198/199/204 | 0.84.1 | **61.506** | 60.810–62.604 | 47.45 |
| 2 | GPT-5.5 medium | Cloud: Native API | 185/189/216 | 0.84.1/0.84.3 | **60.542** | 57.208–62.375 | 20.91 |
| 3 | GPT-5.5 high | Cloud: Native API | 186/190/216 | 0.84.1/0.84.3 | **60.292** | 58.375–63.250 | 12.36 |
| 4 | Gemini 3.7 Flash medium | Cloud: Antigravity prompt variant | 194/195 | 0.84.1 | **58.408** | 58.372–58.443 | 65.50 |
| 5 | Gemini 3.1 Pro high | Cloud: Antigravity prompt variant | 196/197 | 0.84.1 | **57.836** | 54.479–61.193 | 12.93 |
| 6 | GPT-5.6 Sol medium | Cloud: Native API | 187/192 | 0.84.1 | **57.516** | 57.443–57.589 | 21.28 |
| 7 | GPT-5.6 Sol high | Cloud: Native API | 188/193 | 0.84.1 | **56.305** | 55.318–57.292 | 18.53 |
| 8 | GPT-6 Astra medium | Cloud: Native API; two runs | 236/237 | 0.84.3 | **56.241** | 55.372–57.110 | 21.16 |
| 9 | GPT-6 Astra high | Cloud: Native API; two runs | 236/237 | 0.84.3 | **55.909** | 54.881–56.938 | 18.70 |
| 10 | GPT-5.4 medium | Cloud: Native API | 184/191 | 0.84.1 | **54.277** | 54.277–54.277 | 27.97 |

## Top 10 local

| Rank | Profile | Class/status | Runs | Pi | Mean /65 | Score range | Effective t/s |
|---:|---|---|---|---|---:|---|---:|
| 1 | Peregrine v0.27 MTP3, historical | Local: Retired; termination failures | 213/214/215 | 0.84.1 | **61.006** | 61.006–61.006 | 37.81 |
| 2 | v0.27 FP8 target-only, t0.70/p0.90 | Local: Near miss; preliminary reliability 4/4 | 253 | 0.84.3 | **59.214** | n=1 | 17.83 |
| 3 | GPU-5 DFlash2 k7, t1.00 | Local: Candidate; unqualified | 241 | 0.84.3 | **58.399** | n=1 | 18.02 |
| 4 | GPU-5 DFlash2 k7, t0.60 (Gandalf candidate) | Local: Candidate; reliability 12/12 | 238/239/240 | 0.84.3 | **58.318** | 58.318–58.318 | 22.43 |
| 5 | Peregrine v0.28 DFlash2 k7, t0.60/p0.95 | Local: Production; reliability 12/12 | 232/233/234 | 0.84.3 | **57.970** | 57.970–57.970 | 58.11 |
| 6 | Patched v0.29 int8 DFlash2 k7, t0.60 | Local: Candidate; reliability 12/12 | 243/244 | 0.84.3 | **57.792** | 57.792–57.792 | 51.05 |
| 7 | Peregrine v0.28 DFlash2 k7, t0.70 | Local: Rejected; retained-session failures | 224/225/227 | 0.84.3 | **57.649** | 57.649–57.649 | 57.73 |
| 8 | Doctor Strange, MTP2 | Local: Fallback | 180/181/201/217 | 0.84.1/0.84.3 | **57.396** | 57.396–57.396 | 21.65 |
| 9 | Patched v0.29 FP8 MTP3, t0.70 | Local: Below quality gate | 246 | 0.84.3 | **57.354** | n=1 | 40.98 |
| 10 | v0.27 FP8 MTP3 reconstruction, t0.70 | Local: Not historical reproduction | 248/249 | 0.84.1/0.84.3 | **56.568** | 56.568–56.568 | 36.15 |

## All selected profiles

| Rank | Profile | Class/status | Runs | Pi | Mean /65 | Score range | Effective t/s |
|---:|---|---|---|---|---:|---|---:|
| 1 | Claude Opus 4.6 | Cloud: Antigravity prompt variant | 198/199/204 | 0.84.1 | **61.506** | 60.810–62.604 | 47.45 |
| 2 | Peregrine v0.27 MTP3, historical | Local: Retired; termination failures | 213/214/215 | 0.84.1 | **61.006** | 61.006–61.006 | 37.81 |
| 3 | GPT-5.5 medium | Cloud: Native API | 185/189/216 | 0.84.1/0.84.3 | **60.542** | 57.208–62.375 | 20.91 |
| 4 | GPT-5.5 high | Cloud: Native API | 186/190/216 | 0.84.1/0.84.3 | **60.292** | 58.375–63.250 | 12.36 |
| 5 | v0.27 FP8 target-only, t0.70/p0.90 | Local: Near miss; preliminary reliability 4/4 | 253 | 0.84.3 | **59.214** | n=1 | 17.83 |
| 6 | Gemini 3.7 Flash medium | Cloud: Antigravity prompt variant | 194/195 | 0.84.1 | **58.408** | 58.372–58.443 | 65.50 |
| 7 | GPU-5 DFlash2 k7, t1.00 | Local: Candidate; unqualified | 241 | 0.84.3 | **58.399** | n=1 | 18.02 |
| 8 | GPU-5 DFlash2 k7, t0.60 (Gandalf candidate) | Local: Candidate; reliability 12/12 | 238/239/240 | 0.84.3 | **58.318** | 58.318–58.318 | 22.43 |
| 9 | Peregrine v0.28 DFlash2 k7, t0.60/p0.95 | Local: Production; reliability 12/12 | 232/233/234 | 0.84.3 | **57.970** | 57.970–57.970 | 58.11 |
| 10 | Gemini 3.1 Pro high | Cloud: Antigravity prompt variant | 196/197 | 0.84.1 | **57.836** | 54.479–61.193 | 12.93 |
| 11 | Patched v0.29 int8 DFlash2 k7, t0.60 | Local: Candidate; reliability 12/12 | 243/244 | 0.84.3 | **57.792** | 57.792–57.792 | 51.05 |
| 12 | Peregrine v0.28 DFlash2 k7, t0.70 | Local: Rejected; retained-session failures | 224/225/227 | 0.84.3 | **57.649** | 57.649–57.649 | 57.73 |
| 13 | GPT-5.6 Sol medium | Cloud: Native API | 187/192 | 0.84.1 | **57.516** | 57.443–57.589 | 21.28 |
| 14 | Doctor Strange, MTP2 | Local: Fallback | 180/181/201/217 | 0.84.1/0.84.3 | **57.396** | 57.396–57.396 | 21.65 |
| 15 | Patched v0.29 FP8 MTP3, t0.70 | Local: Below quality gate | 246 | 0.84.3 | **57.354** | n=1 | 40.98 |
| 16 | v0.27 FP8 MTP3 reconstruction, t0.70 | Local: Not historical reproduction | 248/249 | 0.84.1/0.84.3 | **56.568** | 56.568–56.568 | 36.15 |
| 17 | GPT-5.6 Sol high | Cloud: Native API | 188/193 | 0.84.1 | **56.305** | 55.318–57.292 | 18.53 |
| 18 | GPT-6 Astra medium | Cloud: Native API; two runs | 236/237 | 0.84.3 | **56.241** | 55.372–57.110 | 21.16 |
| 19 | Peregrine v0.28 DFlash2 k7, t0.60/p0.90 | Local: Superseded | 229/230/231 | 0.84.3 | **56.021** | 56.021–56.021 | 57.08 |
| 20 | GPT-6 Astra high | Cloud: Native API; two runs | 236/237 | 0.84.3 | **55.909** | 54.881–56.938 | 18.70 |
| 21 | v0.29 FP8 target-only, t0.70 | Local: Below quality/speed gates | 247 | 0.84.3 | **55.479** | n=1 | 16.96 |
| 22 | Qwen3.8 + Sharp v22.3.1 | Local: Rejected | 208 | 0.84.1 | **55.417** | n=1 | 14.46 |
| 23 | v0.27 FP8 MTP3, synchronous | Local: One empty answer | 251 | 0.84.3 | **55.131** | n=1 | 32.52 |
| 24 | v0.27 FP8 MTP3, seed42 | Local: Below quality gate | 250 | 0.84.3 | **55.068** | n=1 | 41.79 |
| 25 | Cold Fusion | Local: Rejected | 200/203 | 0.84.1 | **55.006** | 55.006–55.006 | 21.46 |
| 26 | Peregrine v0.28 FP8 MTP3 | Local: Superseded | 218/219/220 | 0.84.3 | **54.771** | 54.771–54.771 | 45.10 |
| 27 | GPU-5 MTP3, t1.00 | Local: Below quality gate | 242 | 0.84.3 | **54.443** | n=1 | 24.58 |
| 28 | Patched v0.29 int8 DFlash2 k7, t1.00 | Local: Below quality gate | 245 | 0.84.3 | **54.318** | n=1 | 55.43 |
| 29 | GPT-5.4 medium | Cloud: Native API | 184/191 | 0.84.1 | **54.277** | 54.277–54.277 | 27.97 |
| 30 | Road Runner, off/4K/MTP3 | Local: Bounded only | 202/217 | 0.84.1/0.84.3 | **54.042** | 54.042–54.042 | 182.05 |
| 31 | Spiderman, off/4K/MTP3 | Local: Retained | 206 | 0.84.1 | **52.729** | n=1 | 54.76 |
| 32 | Opus Distill v2 | Local: Rejected; reliability 9/12 | 235 | 0.84.3 | **52.318** | n=1 | 32.86 |
| 33 | Thor, thinking/4K/no-spec | Local: Retained | 207 | 0.84.1 | **51.042** | n=1 | 8.20 |
| 34 | v0.27 FP8 target-only, t0.60/p0.95 | Local: Below quality/speed gates | 252 | 0.84.3 | **50.354** | n=1 | 15.79 |
| 35 | Road Runner practical, low/8K | Local: Rejected | 183 | 0.84.1 | **49.542** | n=1 | 21.18 |
| 36 | Qwen3.8 Q4_K_M, off/4K/no-spec | Local: Comparison | 182 | 0.84.1 | **48.229** | n=1 | 22.78 |
| 37 | Ornith 1.5, off/4K/no-spec | Local: Rejected | 209 | 0.84.1 | **44.562** | n=1 | 80.59 |

## Today's evidence and limits

- Astra: runs **236–237**, two complete runs each at medium and high. These are
  cloud results, not local GPU performance. Do not interpret two samples as a
  stable intrinsic ranking; medium and high overlap in observed score range.
- Preserved candidate outputs were backfilled as **238–253**, with source hashes,
  original timestamps, Pi versions and explicit runtime coordinates. Historical
  IDs and rows are unchanged. Missing historical benchmark commit provenance is
  left unknown rather than guessed. Raw evidence remains private.
- The retired-coordinate recovery completed **nine valid full screens**. None
  reached 60/65 with at least 18 effective t/s. Target-only run 253 came closest
  at 59.214/65 and 17.83 t/s; its 4/4 reliability check is preliminary, not 12/12.
- TypeSafe/Jev is parked: useful decision-workflow ideas, but no demonstrated
  improvement to this local, single-pass benchmark. It was not run or ranked.

See [RESULTS.md](RESULTS.md) for investigations, [INFERENCE_PROFILES.md](INFERENCE_PROFILES.md)
for deployment profiles, and [RESULTS.csv](RESULTS.csv) for sanitized task records.
