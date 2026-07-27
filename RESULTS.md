# Reference results

These are historical PiBench runs from one system. They show what was observed with particular model files and settings; they are not hardware-independent rankings.

- Suite: 24 tasks, 65 weighted points
- Snapshot: 2026-07-24
- CPU: AMD Ryzen 9 7900, 12 cores / 24 threads
- RAM: 128 GB
- GPU: NVIDIA GeForce RTX 3090, 24 GB
- OS: Debian GNU/Linux 13, kernel 6.12.95+deb13-amd64
- NVIDIA driver: 550.163.01
- CUDA toolkit: 12.4.131

Most final local runs used a 131,072-token context, one parallel slot, quantized KV cache, full GPU offload, and flash attention. llama.cpp builds, quantizations, thinking modes, temperatures, and speculative settings varied and are treated as part of the profile.

## Local and cloud

| Rank | Model/configuration | Where | Score | Effective output t/s |
|---:|---|---|---:|---:|
| 1 | Thor — DSV4Pro 27B Q4, thinking on, no MTP | Local | **60.9/65** | 9.5 |
| 2 | Claude Opus 4.8, medium | Cloud | **60.2/65** | 41.8 |
| 3 | GPT-5.5, high | Cloud | **59.2/65** | 17.5 |
| 4 | GPT-5.6 Sol, high | Cloud | **58.9/65** | 17.5 |
| 5 | GPT-5.5, medium | Cloud | **58.0/65** | 21.7 |
| 6 | Qwen3.6 27B UD-Q5_K_XL, thinking on | Local | **58.0/65** | 5.7 |
| 7 | GPT-5.6 Sol, medium | Cloud | **57.8/65** | 19.8 |
| 8 | Claude Sonnet 4.6, medium | Cloud | **57.6/65** | 38.5 |
| 9 | Claude Opus 4.8, high | Cloud | **56.9/65** | 42.8 |
| 10 | Qwen3.6 35B Q3_K_M, thinking on | Local | **55.9/65** | 17.7 |
| 11 | Qwen3.6 27B NEO CODE Q5, thinking off | Local | **55.9/65** | 3.0 |
| 12 | Spiderman — Tmax 27B Q5, MTP n3 | Local | **55.8/65** | 46.3 |
| 13 | GPT-5.4, medium | Cloud | **54.3/65** | 22.9 |
| 14 | Qwen3.6 27B MTP Q4, thinking off | Local | **53.3/65** | 51.8 |
| 15 | DSV4Pro 27B Q4, thinking on, MTP | Local | **53.1/65** | 17.1 |
| 16 | ThinkingCap 27B Q5, thinking on | Local | **52.9/65** | 8.4 |
| 17 | Qwen3.6 35B APEX Compact, thinking on | Local | **52.8/65** | 13.5 |
| 18 | Tmax 27B IQ4_XS, thinking off | Local | **52.6/65** | 52.3 |
| 19 | OpenHands 27B Q4, thinking off | Local | **52.2/65** | 48.7 |
| 20 | Qwen3.6 35B APEX Quality, thinking off | Local | **51.7/65** | 137.8 |

## Local profiles

| Rank | Model/configuration | Score | Effective output t/s |
|---:|---|---:|---:|
| 1 | Thor — DSV4Pro 27B Q4 | **60.9/65** | 9.5 |
| 2 | Qwen3.6 27B UD-Q5_K_XL, thinking on | **58.0/65** | 5.7 |
| 3 | Qwen3.6 35B Q3_K_M, thinking on | **55.9/65** | 17.7 |
| 4 | Qwen3.6 27B NEO CODE Q5 | **55.9/65** | 3.0 |
| 5 | Spiderman — Tmax 27B Q5 MTP n3 | **55.8/65** | 46.3 |
| 6 | Qwen3.6 27B MTP Q4 | **53.3/65** | 51.8 |
| 7 | ThinkingCap 27B Q5 | **52.9/65** | 8.4 |
| 8 | Qwen3.6 35B APEX Compact | **52.8/65** | 13.5 |
| 9 | Tmax 27B IQ4_XS | **52.6/65** | 52.3 |
| 10 | OpenHands 27B Q4 | **52.2/65** | 48.7 |
| 11 | Qwen3.6 35B APEX Quality | **51.7/65** | 137.8 |
| 12 | Gemma 4 26B A4B UD-Q4_K_XL | **51.7/65** | 77.8 |
| 13 | Opus–DeepSeek distilled 27B Q4 | **51.1/65** | 31.9 |
| 14 | Road Runner — Qwen3.6 35B Q4 MTP n3 | **50.9/65** | **145.7** |
| 15 | Qwen3.6 27B Pi-Reasoning Q4 | **50.6/65** | 48.9 |
| 16 | Qwopus 27B v2 Q4 | **49.3/65** | 49.7 |
| 17 | Genesis 35B APEX Compact | **48.9/65** | 99.1 |
| 18 | KAT-Coder V2.5 Dev Q4 | **48.8/65** | 100.1 |
| 19 | SIQ-1 35B Q4 | **47.4/65** | 107.7 |
| 20 | Ornith 1.0 35B Q4 | **46.4/65** | 29.0 |

Thor, Spiderman, and Road Runner are local aliases. Effective output speed is estimated visible output divided by end-to-end task time, not pure backend decode speed. Cloud rows can combine the latest valid result per task from partial invocations; failed infrastructure, OOM, malformed, and incomplete runs are excluded.

To contribute a result from another system, follow the metadata checklist in [README.md](README.md).
