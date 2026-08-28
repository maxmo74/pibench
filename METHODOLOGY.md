# Methodology

PiBench is a practical coding and agent benchmark. The main runner invokes Pi once per task with no shared session, tools, repository context, skills, prompt templates, themes, or extensions. Protocol v4 is frozen on Pi 0.84.1; protocol v5 is current on Pi 0.84.3. Both refuse unversioned extension-provided inputs because an extension could change the effective prompt after attestation.

## Scoring

The suite has 24 tasks and a maximum score of 65. Binary tasks receive zero or their full weight; tasks with independent checks receive the same fraction of their weight as the fraction of checks passed.

| Task | Points | Task | Points |
|---|---:|---|---:|
| Exact JSON | 0.5 | Deduplicate function | 1.0 |
| Parse integers | 1.0 | Merge intervals | 2.0 |
| Topological sort/cycle | 2.5 | nginx reverse proxy | 2.0 |
| Static web UI | 2.0 | LRU cache | 3.0 |
| JSON-path setter | 4.0 | Rate limiter | 3.5 |
| Unified diff | 4.5 | CSV inference | 3.5 |
| Retry schedule | 3.0 | Semantic-version range | 4.0 |
| Markdown table | 3.5 | Text wrapping | 3.0 |
| systemd service | 3.0 | nginx TLS proxy | 3.0 |
| Incident triage | 2.5 | README rewrite | 2.0 |
| Changelog | 2.0 | GitHub issue triage | 2.5 |
| Architecture decision | 3.5 | Design review | 3.5 |

The prompts, checks, weights, and sandbox behavior in `pi_agent_bench.py` and `pi_agent_bench_v5.py` are identical. The version split records Pi/effective-prompt drift, not a task or grader change.

## Clean Pi invocation

Each task uses:

```text
--no-session
--no-tools
--no-context-files
--no-extensions
--no-skills
--no-prompt-templates
--no-themes
```

Protocol v4 pins Pi 0.84.1, uses a fixed system prompt, and launches Pi from `/tmp/pibench-pi-agent-cwd-v1`. Before recording a run, the harness verifies the Pi version, invokes that installation's system-prompt builder, and requires the complete effective prompt to equal the protocol definition. It records SHA-256 hashes of both the supplied and effective system prompts and refuses to run if Pi adds or changes content. Custom prompts and extension-enabled runs are not accepted by this runner because they cannot share the canonical effective-prompt attestation. Pi 0.84.2 is intentionally rejected because it added a trailing newline to the effective prompt.

Protocol v5 pins Pi 0.84.3, launches from the same fixed cwd, and attests the new effective prompt including its trailing newline (SHA-256 `6b861f18cea399f742dc1a809914f8d6bf2ff30bb9f8c320ee50afb6f3bfebfc`). V4 and v5 retain distinct revision metadata even where their scores are aggregated.

Pi versions through 0.80.6 silently appended `Current date: YYYY-MM-DD` to custom system prompts. Pi 0.82.0 removed that line. Consequently, historical pre-0.82 Pi-agent runs used a `legacy-date-injected` input profile and are not strictly comparable across dates or with date-free runs. They remain valid evidence for their exact effective prompt, and historical inputs can reproduce them, but curated `pi-agent-24/65` rankings use only v4/v5 results. Direct endpoint benchmarks were unaffected.

## V4/v5 compatibility bridge

Four complete v5 runs tested whether the Pi-version and trailing-newline change materially altered the unchanged 24-task/65-point suite:

| Profile | V4 evidence | V5 result | Task-level interpretation |
|---|---:|---:|---|
| GPT-5.5 medium | 57.208, 62.042 | 62.375 | One task differed from the closest v4 run; consistent with existing cloud variation |
| GPT-5.5 high | 58.375, 63.250 | 59.250 | One task differed from each v4 run; inside the v4 range |
| Doctor Strange low | 57.396 | 57.396 | 24/24 task outcomes and private outputs byte-identical |
| Road Runner off | 54.042 | 54.042 | 24/24 task outcomes and private outputs byte-identical |

This bridge found no material revision effect. PiBench therefore defines `pi-agent-24/65` as the score protocol and v4/v5 as measured execution revisions. Combined rankings may average equivalent complete runs across those revisions, but every run and row must retain its actual revision and effective-prompt hash. This conclusion does not make pre-v4 date-injected profiles compatible, does not merge versioned extension variants with pure-canonical input, and can be revisited if broader bridge data shows a systematic effect.

## What protocols v4 and v5 do—and do not—normalize

Across these revisions, the protocol normalizes the benchmark **input and evaluation path**, except for the attested trailing newline described above:

- exact Pi version and complete effective system prompt
- fixed working-directory text
- task prompts, order, weights, checks, and sandbox behavior
- one clean Pi process per task
- absence of sessions, tools, project context, skills, templates, themes, and extensions

It does not pretend that all inference profiles are equivalent. Model identity, weights or service identifier, quantization, reasoning mode, context, output ceiling, sampler, speculation, runtime, hardware, and provider are part of the profile. A 4K no-spec local run, an 8K MTP local run, and a provider-native cloud run may share protocol-v4 input while answering under different resource envelopes. Curated tables must name those differences rather than presenting the score as an intrinsic property of model weights alone.

## Local and cloud execution

| Property | Local model | Cloud/API model |
|---|---|---|
| Model identity | Artifact filename and preferably SHA-256 | Provider and service model identifier |
| Runtime identity | Backend version/commit/build, libraries, and launch arguments | API type and any version information exposed by the provider |
| Inference controls | Context, KV cache, sampler, GPU offload, batch settings, and speculation can be recorded | Only request-visible controls can be recorded; internal routing and sampling remain opaque |
| Change control | Artifacts and binaries can be retained and replayed | Weights and serving stack may change behind an unchanged model name |
| Hardware | Known and recorded | Normally undisclosed or provider-managed |
| Timing | Primarily host inference plus Pi overhead | Also includes network latency, queueing, routing, and provider execution |
| Seed/determinism | A request seed can help reproduce an exact pinned stack, subject to kernels and speculation; a server seed alone may still leave request-history dependence | No seed-attested deterministic path is assumed |

Cloud and local scores are therefore comparable as **observed end-to-end profile outcomes under the same tasks**, not as proof of equal compute, equal output budget, equal reasoning effort, or identical determinism. Local and cloud labels such as `medium` and `high` are provider-specific controls.

## Versioned extension profile: antigravity-v1

Protocol v4 refuses extension-provided models by default because an extension can modify the effective prompt after attestation. The `antigravity-v1` profile is an explicit, versioned exception for the user-maintained `pi-antigravity` extension (Google Cloud Code Assist, free-tier capable):

- `--extension-profile antigravity-v1` (with `--allow-extensions`) pins `pi-antigravity` **0.3.1** and refuses any other version.
- Before running, the bench attests that the installed extension source still contains the exact three system-instruction parts it injects before the canonical prompt (injection sha256 `1416c1c4f53afd8e28d425d22076354cf72af24e4c58eb75f98d633486eb9b39`) and the four-part `systemInstruction` construction. Any drift aborts the run. Attestation follows Pi's `PI_CODING_AGENT_DIR` override when set, allowing the pinned profile to run from an isolated immutable agent directory without replacing a user's newer extension installation; the override must be absolute.
- The canonical Pi effective prompt is still attested exactly as in protocol v4; the full wire prompt is therefore **canonical prompt + fixed injection**, frozen and hash-recorded per run (`benchmark_input_profile=pi-agent-v4-fixed-cwd+antigravity-v1`, `antigravity_injection_sha256` in run metadata).
- Comparability: antigravity-v1 results are comparable **within the profile** (across antigravity models and dates) and are listed in the combined ranking, but they are not byte-identical to the pure canonical prompt input of the OpenAI/local profiles. The injected parts are constant strings (not date- or task-dependent), so the only input difference is the fixed prefix.
- If the extension is updated or its injection changes, the profile must be re-attested and re-versioned (e.g. `antigravity-v2`) before new runs; old results remain valid for their recorded profile.

## Repeatability and determinism

PiBench uses the following terms deliberately:

- **Input-identical:** protocol version, effective-prompt hash, tasks, and request-visible profile settings match.
- **Stack-replayable:** model artifact, runtime, libraries, arguments, and hardware-relevant configuration are retained well enough to replay. This is usually achievable locally and usually impossible for a managed cloud service.
- **Score-stable:** repeated complete runs receive the same weighted score. This does not imply the generated text is the same.
- **Output-deterministic:** repeated complete runs produce byte-identical task output on all 24 tasks. This is the strongest observed repeatability claim and applies only to the tested stack.

A seed is metadata, not proof of determinism. Different prompts, kernels, runtime builds, quantized speculative paths, or provider backends can change output despite the same nominal seed. Quantized MTP/DFlash results require particular caution because accepted draft tokens can alter the generated path.

### Request history and health probes

For an unseeded request, the state of a local server before the benchmark is part of the inference coordinate. Earlier inference can advance sampler or speculative-drafter RNG, populate prefix caches, trigger compilation, alter scheduler state, or change allocator residency even when model weights and request-visible sampler settings are unchanged. `server-seed=0` is not equivalent to putting an explicit seed on every request.

Peregrine exposed this directly. Three clean-start FP8/MTP3 runs after one greedy no-thinking readiness request were byte-identical at 61.005952/65. Replacing that readiness step with a temperature-0.7 thinking request advanced the unseeded trajectory; three otherwise matching runs were byte-identical at 58.255952/65. Neither coordinate is a best-task splice, but they must not be averaged because their prior request histories differ. The accidental coordinate was retained privately and removed from canonical SQLite before publication.

Consequently, a replayable local profile records any startup inference, whether the benchmark starts from a fresh server, request seed versus server seed, and whether periodic monitoring performs inference. Peregrine's startup probe is fixed as greedy/no-thinking; periodic monitoring calls vLLM's engine-health RPC and authenticated model listing without generation. This checks the engine while avoiding a hidden sampler-state mutation. Operational services that require an inference canary must record it as part of request history, or use an explicit independent request seed if the backend proves that it isolates generator state.

Weight precision, KV-cache precision, attention/GEMM kernels, tensor parallelism, and accelerator architecture are also part of the inference coordinate—not transparent capacity or speed switches. Their numerical divergence can be content- and context-dependent, especially around exact literals and tool envelopes. KL divergence or top-token agreement against a higher-precision reference measures fidelity, not correctness: a closer trajectory can still be wrong. Consequently, promotion requires executable/task-level outcomes and realistic long-context tool replays rather than assuming that either higher precision or lower distributional divergence is intrinsically better.

For current curated tables:

- V4 and v5 pure-canonical runs share the `pi-agent-24/65` ranking after the compatibility bridge, while retaining measured revision metadata.
- Pre-v4 and extension-modified prompt profiles remain separate inputs; the fixed Antigravity variant is visible only with an explicit label.
- A repeated profile is rerun as a complete 24-task invocation, not assembled by selecting its best task attempts.
- Repeated local and managed-cloud profiles are shown using the arithmetic mean and min–max range of complete equivalent runs; the best run is never used alone as the ranking value.
- A single local run is shown as `n=1` with its range marked not measured. It must not be described as verified deterministic.
- Output determinism is claimed only after private raw-output comparison. Raw text remains unpublished; the public CSV retains each run and task outcome separately.
- Equal scores across repeats are reported as score stability. For example, two GPT-5.4 runs had the same score while only 3/24 outputs were byte-identical; Doctor Strange runs 180/181 were byte-identical on 24/24.

The current small cloud samples (two complete runs for most profiles and three for Opus 4.6) estimate short-run variability; they are not confidence intervals or guarantees about future service behavior. More repeats are appropriate when profiles have wide ranges or when a decision is sensitive to small score differences. The published [Top 20 overall and Top 10 local tables](LEADERBOARDS.md) apply these rules and never pad empty positions with historical, incomplete, or private qualification runs.

## Tool-enabled multi-turn profile: pi-ops-v1

The canonical 65-point suite deliberately removes tools and conversational state. `pi_ops_bench.py` provides a separate 100-point diagnostic for daily coding and operations work; its scores are not comparable to, and are never mixed with, canonical Pi-agent scores.

`pi-ops-v1` resets the same fixed disposable Git repository for every model and sends three sequential prompts through one persisted Pi session: repair and validate a retry implementation, harden a systemd service and update its README, then review and correct the combined change. Pi 0.84.1 is pinned. The only enabled tools are `read`, `bash`, `edit`, and `write`; context files, skills, templates, themes, and auto-discovered extensions are disabled. A source-pinned read-only attestor records the complete effective tool-enabled system-prompt SHA-256 before each turn and the harness requires one identical hash across all turns and models.

The Pi process runs inside Bubblewrap with a private filesystem, read-only system/runtime mounts, fixed cwd `/tmp/pibench-ops-cwd-v1`, isolated model configuration, private session/output directories, and only the disposable repository writable. The host network namespace is shared solely so the process can reach a configured loopback inference server; therefore this profile accepts loopback HTTP providers only. Model-generated Python used for hidden scoring is evaluated again through PiBench's networkless generated-code sandbox.

Scoring is deterministic: retry behavior 35 points, service correctness/hardening 30, exact README commands 15, preservation of supplied tests 10, minimal file scope 5, and completion of all three turns 5. Tool-call count and wall time are descriptive tie-breakers, not score inputs. Raw event streams, sessions, model text, and workspaces remain private; public reports contain only aggregate scores, check outcomes, hashes, and profile metadata.

`pi-ops-v1` measures three structured, convergent tasks; it does not establish reliability on ambiguous open-ended investigation. A model can pass this profile yet repeatedly call equivalent tools or fail to terminate on a less constrained request. Interpret its score together with observed interactive reliability.

## Versioned reliability gates

`pi_agent_reliability_bench.py` preserves the Pi 0.84.1 `pi-agent-reliability-v1` screen. `pi_agent_reliability_v2.py` pins Pi 0.84.3, uses versioned fixture paths and prompt attestation, and includes the production Peregrine loop guard. Both keep loop and termination qualification separate from canonical PiBench and `pi-ops-v1`. This preserves historical profiles while the new scenarios and thresholds accumulate validation evidence. It is a strict pass/fail gate, not a weighted score.

The profile runs four synthetic read-only repositories: a browser-state defect with sufficient evidence, an incident whose decisive rotated log and metrics are deliberately absent, a simple deployment mismatch after a large deterministic irrelevant-context preamble, and a deterministic polling trap that tests whether the agent stops instead of searching Pi's harness internals for unavailable evidence. Each scenario uses a fresh session and runs twice by default. Only `read` and `bash` are available; the fixture itself is mounted read-only inside Bubblewrap. Pi 0.84.1, fixed cwd, the scenario and preamble hashes, and the complete effective system-prompt hash are recorded.

Configured providers are accepted only at loopback HTTP endpoints. Built-in cloud providers are also supported through an existing provider-scoped `auth.json` credential. The harness copies only the selected provider entry, stages it with mode 0600 for one Pi process, proves that a source-pinned tool-scope guard loaded before the agent turn, and deletes the staged credential in a `finally` block. The guard blocks `read` outside the fixture and blocks shell access to agent/session/output mounts, parent traversal, environment enumeration, interpreters, and network clients. Cloud inference still requires the shared network namespace. The guard prevents the enabled tools from reading the staged credential and blocks common direct network clients and interpreter escape paths; this is defense in depth rather than a claim of network-namespace isolation. The guard source hash is recorded with each result.

Every scenario-run must terminate normally, satisfy deterministic answer checks, respect its tool budget and the 21-assistant-message ceiling, repeat no exact tool call, keep tool access within the fixture, and stay below repeated-line and repeated-24-token-block thresholds. The default ceiling is 20 tools; the deliberately tiny polling fixture permits 10. A timeout, length/error stop, missing final response, semantic failure, duplicate tool call, out-of-scope introspection, excessive exploration, or repeated output fails qualification. Private results retain only checks, counts, timings and content hashes—not model text.

The gate is intentionally conservative for read-only work, where repeating an identical call cannot reveal new state. Passing all eight default scenario-runs is necessary evidence for autonomous use, not proof against every future prompt or context. Retained real-session replays remain an independent semantic gate: a profile can pass the synthetic screen yet choose the wrong edit in a realistic workspace, as Peregrine did three times. Such a critical retained failure must be disclosed and may restrict a deployment to supervised use even when the synthetic screen is clean. Integration into the main qualification workflow should occur only after the fixtures discriminate known failures without rejecting stable models for benign behavior.

## Executable checks

Generated Python is treated as untrusted. Bubblewrap provides:

- separate namespaces and no network
- no host home-directory access
- read-only runtime libraries
- private temporary work directories
- CPU, memory, file-size, descriptor, and wall-time limits
- Python isolated mode

If the sandbox cannot start, executable checks fail closed. The unsafe environment-variable override is intended only for disposable systems.

## Recorded metadata

The schema separates metadata that applies to the whole run from metadata for each tested model:

- **Provenance:** optional contributor handle and source URL.
- **Host:** OS, CPU, memory, detected accelerators, compute mode (`cpu`, `gpu`, `hybrid`, `remote`, `cloud`, or `other`), and the devices actually used.
- **Runtime:** backend name, version, commit, build, compiler, and backend-specific JSON.
- **Model artifact:** format, quantization or precision, stable filename/service identifier, and optional SHA-256.
- **Inference:** context size, KV-cache representation, sampler, request/server seeds, startup request history, monitoring behavior, speculation, driver/kernel coordinates, and arbitrary backend-specific settings.
- **Result:** exact Pi model argument, requested/effective thinking mode, benchmark protocol version, effective-system-prompt hash, task score, timing, stdout/stderr, and command.

For loopback llama.cpp routers, PiBench also discovers the backing `llama-server`, records its build number, Git commit and date, compiler/target from `--version`, selected CMake options, model filename, launch arguments, context, KV types, sampling, GPU offload, flash attention, parallelism, and speculation settings when available. The dedicated `llama_cpp_*` database columns are retained alongside generic runtime columns.

Metadata that cannot be discovered can be supplied on the command line or through `--metadata-file`. A profile is a JSON object with optional `provenance`, `host`, `runtime`, `model`, and `inference` objects. For example:

```json
{
  "provenance": {"contributor": "@example", "source_url": "https://example.org/run"},
  "host": {"compute_mode": "hybrid", "accelerators_used": ["GPU 0", "GPU 1"]},
  "runtime": {"name": "vLLM", "version": "0.19.0", "commit": "abcdef0"},
  "model": {"format": "safetensors", "quantization": "FP8"},
  "inference": {"context_size": 131072, "tensor_parallel": 2, "temperature": 0.2}
}
```

Command-line values override their corresponding profile values. Run one model per contributed profile when different models use different runtimes or inference settings. Do not place credentials or private paths in a profile.

The database, metadata profiles, and raw outputs remain local under gitignored paths. The tracked `RESULTS.csv` is a deterministic allowlisted export of every recorded task result. It includes outcomes, partial-credit scores, weights, timings, model/runtime identifiers, selected hardware and inference metadata, and an explicit run-status field. It excludes prompts, output, stderr, checks, notes, commands, arbitrary JSON, credentials, and private paths. The SQLite database is never published. `orphaned-metadata` means task rows survived an old parent-run cleanup; those rows remain visible for completeness but are not used in curated rankings.

Regenerate the public export after adding reviewed runs:

```bash
./pibench_report.py --csv-out RESULTS.csv
```

## Reading results

- Effective output t/s is visible output divided by end-to-end wall time; it includes Pi startup, prompt processing, hidden reasoning latency, network and queueing where applicable. It is not pure backend decode speed.
- Local and cloud reasoning controls are not equivalent, and output ceilings must be read as part of the profile.
- Quantization and speculative decoding are part of the tested configuration, not transparent acceleration layers.
- OOM, malformed-artifact, infrastructure, authentication, quota, and incomplete runs are excluded rather than scored as model failures.
- Results are compared within the `pi-agent-24/65` score protocol and compatible effective-prompt family. V5 is the current execution revision; v4 remains measured historical evidence, while older date-injected profiles remain separate.
- Current cloud aggregates use complete-run means and ranges. Some explicitly historical cloud rows combined the latest valid task result across partial invocations; those rows are not protocol-v4 ranking inputs.
- The public CSV contains individual run/task observations. Curated aggregate means, ranges, repeatability labels, and deployment decisions are documented in `README.md` and `RESULTS.md` rather than replacing raw observations.
- Static configuration checks verify requested content, not a live deployment.

The benchmark is intentionally small. A two-run range is descriptive, not statistically conclusive. Results should be reproduced on the hardware, software stack, service date, and request profile relevant to the intended deployment.
