# Reference results

These runs were made on one reference workstation. They show observed model/profile behavior, not hardware-independent rankings.

- Suite: 24 tasks, 65 weighted points
- Snapshot: 2026-08-17
- Current benchmark input: Pi-agent protocol v4
- Effective system-prompt SHA-256: `33367c8eccc8213267c551069af9e5c781122b08fe36b5f1f736d29e5269f711`
- CPU: AMD Ryzen 9 7900, 12 cores / 24 threads
- RAM: 128 GB
- GPU: NVIDIA GeForce RTX 3090, 24 GB
- OS: Debian GNU/Linux 13, kernel 6.12.101+deb13-amd64
- NVIDIA driver: 550.163.01
- CUDA toolkit: 12.4.131

Protocol v4 pins Pi 0.84.1, fixes Pi's working directory, verifies the complete effective system prompt before a run, records its hash, and aborts if Pi changes the prompt. Pi 0.84.2 is rejected because it adds a trailing newline. Current results use 131,072-token context, one parallel slot, quantized KV cache, full GPU offload, and seed 42 unless stated otherwise.

## Current protocol-v4 local profiles

| Rank | Model/profile | Class | Run | Score | Passed | Effective output t/s |
|---:|---|---|---:|---:|---:|---:|
| 1 | **Doctor Strange** — Qwen3.8 27B Q4_K_M, low reasoning, 8K output, Q4 MTP draft2 | Practical/long-output | 180/181 | **57.396/65** | 16/24 | 20.4 |
| 2 | **Road Runner** — Qwen3.6 35B-A3B Q4, thinking off, 4K output, MTP draft3 | Canonical 4K | 177 | **54.792/65** | 17/24 | **144.9** |
| 3 | **Thor** — DSV4Pro 27B Q4, thinking on, 4K output, no speculation | Canonical 4K | 179 | **53.229/65** | 17/24 | 9.3 |
| 4 | **Spiderman** — Tmax 27B Q5, thinking off, 4K output, MTP draft3 | Canonical 4K | 178 | **51.568/65** | 13/24 | 47.8 |
| 5 | Qwen3.8 27B Q4_K_M, thinking off, 4K output, no speculation | Canonical 4K | 182 | **48.229/65** | 14/24 | 28.1 |

Doctor Strange is deliberately a separate practical profile: it doubles the canonical output allowance and uses a quantized MTP sidecar. Runs 180 and 181 were exact repeats and produced byte-identical outputs on all 24 tasks. MTP draft2 was retained because draft3 was faster but changed task outcomes in paired testing.

Road Runner remains the throughput leader. Doctor Strange is the current daily quality profile; its low reasoning setting and 8K allowance avoid the output-exhaustion failures observed with Qwen3.8's medium/xhigh behavior.

### Rejected Road Runner practical profile

Road Runner low/8K on current llama.cpp b10434 (run 183) scored **49.542/65 at 24.2 effective visible tok/s**, versus its off/4K run at **54.792/65 and 144.9 tok/s**. Qwen3.6 maps low and medium to the same boolean thinking mode rather than Qwen3.8's graduated effort. The larger allowance mostly increased hidden reasoning; JSON path and semver produced effectively empty finals. The low/8K profile is rejected, and Road Runner remains configured off/4K.

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

No cloud model has yet been rerun under protocol v4. Earlier cloud scores—including Claude Opus 4.8 at 60.2, GPT-5.5 high at 59.2, and GPT-5.6 Sol high at 58.9—belong to historical prompt profiles and must not be mixed into the table above.

Effective output speed is visible output divided by end-to-end task time, not pure backend decode speed. The complete sanitized task-level history and reproducibility metadata are in [RESULTS.csv](RESULTS.csv). To contribute a result from another system, follow [README.md](README.md) and [METHODOLOGY.md](METHODOLOGY.md).
