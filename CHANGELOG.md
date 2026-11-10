# Changelog

## Unreleased

- Fix Splash 1.4 discovery of installed 6-bit 27B MLX checkpoints, restore
  persistent OMP discovery, and remove the fixed 32 GiB streaming ceiling and
  duplicate memory reserves. Prefer the pinned BF16 embedding-row loader fix
  so Flash-Next's original 160-column n-gram rows load without changing weights.

- Prepare Flash-Next with unchanged Q4_K_M main tensors and the original BF16
  n-gram table. Verify source checksums and per-tensor byte parity, validate
  the combined GGUF with Splash, and show PLE precision separately in the
  model catalog. Retire the redundant sources only after native preparation.

- Support Splash 1.4.0 and Qwen3.8 Flash-Next GGUF, including split models.
  Use native local preparation and thinking limits, keep every shard in the
  source identity, and budget expert/PLE/KV SSD streaming against fresh memory
  headroom. Keep older runtimes available; current Splash requires original
  checkpoints rather than legacy packs.

- Separate complete Route Check, ANE tuning/FP16 clone and Session Set opening
  operations. Bind every temporary request and workspace action to the exact
  accepted run and cancellation event. Keep Stop available during response reads,
  reject stale-owner probes/admin calls and require clean unload before saving
  new readiness/tuning proof. Preserve cancellation during workspace preparation
  and release failed worker publications without stopping another route.
  Anchor clone writes to their created directory descriptor and publish only
  after exclusive destination, current parent/source and created-inode checks.
  Dispose unpublished attachment credentials while preserving accepted surfaces,
  unrelated files and symlink targets. Generated fixtures preserve full plans,
  results, settings and clone contents; these changes claim no inference TPS gain.

- Extract the complete Launch and resident-session workspace with private settings,
  explicit memory review, exact measured Apply and scoped model/session actions.
  Keep pending idle-unload choices visible, reject retired-owner replies and stale
  status reads, and preserve unchanged request/cache controls. Sessions now uses
  plain memory/model/request copy. Generated desktop/mobile checks preserve exact
  limits, reasoning, sampling, KV and acknowledgement; no UI timing is inference TPS.

- Separate complete model acquisition and setup previews, public metadata
  queries, pinned commands and current artifact verification. Preserve exact
  file/revision/license/destination consent and checksum checks. Bound CLI
  output while reading it, retain the existing character quota, and retire only
  the owned unreaped process session on limits, timeout or cancellation.

- Extract complete Benchmark Lab and Calibration controls into an independent
  workspace with private state and exact measured Apply references. Preserve
  focused saved results during unchanged updates, keep refresh/action failures
  visible with recovery, and fence stale status, plan, history and review replies.
  Generated desktop/mobile checks cover exact record/suite commits, Stop and
  typed profile-save recovery; UI DOM measurements are separate from inference TPS.

- Separate complete measured-route selection, engine ranking, Apply bindings and
  history presentation. Retain exact model/runtime/hardware/sampling/limits and
  fresh evidence checks through narrow callbacks. Reuse immutable configuration
  only while current policy inputs match. Index verified record identities to
  avoid repeated full-record comparisons; an equal record rejected by its own
  current check remains visible. Generated membership CPU work fell from about
  179 µs to 9 µs, without an inference TPS claim.

- Extract complete runtime inventory, installed pack contracts and update/adoption/
  promotion review plans into an independent catalog. Preserve exact audited
  releases, fresh trust/capacity checks, explicit approval and rollback; leave
  installation and selection separate. Restore Runtime Manager's missing Splash
  documentation link. Bind bounded raw kernel receipts to current executable,
  interpreter and package files, preventing stale readiness after replacements.
  Reuse immutable wiring with policy-change invalidation; measured setup overhead
  fell from about 137 to 2.6 microseconds, without an inference TPS claim.

- Extract complete model discovery, artifact records and Model Library readiness
  across all twelve engines. Preserve current SHA proof, source pairing, native
  precision, sampling/defaults and compatibility reasons through frozen policy
  and explicit ports. Keep persisted AtomicChat presentation data outside launch
  authority. Bind native inspection receipt reuse to current file/link identity
  and revalidate its fields each time, preventing a preserved modification time
  from hiding an executable or checkpoint replacement.
  Recover safely when the AtomicChat verifier thread cannot start: show a
  bounded failure, clear its publication and allow rescan to retry without
  accepting incomplete proof. Remove repeated catalog wiring from the pure
  memory-geometry facade while reading its current policy inputs each time;
  private helper CPU overhead fell from about 112 to 1 microsecond, without an
  inference TPS claim.

- Separate the complete Chat workspace and keep its draft, queue, history,
  recovery and stream state private. Preserve saved-route review and Console
  navigation through narrow callbacks. Reuse unchanged completed message DOM,
  preserving keyboard focus, edits and reasoning panels during streaming.
  Generated 160-message browser checks reduced repeated render work from about
  29 ms to about 1 ms; this measures UI rendering, not model inference speed.
- Separate the complete work-surface planner for Pi, oh-my-pi, OpenCode, Codex
  and Chat. Preserve exact private providers, limits, reasoning, model identity
  and local helper routing without writing global agent configuration.

- Extract complete Chat, benchmark and Route Check inference requests and
  streaming interpretation. Preserve exact wire limits, sampling, reasoning,
  native generation timing, tool-call proof and cancellation/EOF behavior;
  relay Chat bytes through explicit HTTP output callbacks and retain scoped
  cache observations. Verify all twelve engines against frozen requests and
  generated local HTTP/SSE fixtures without loading models.
  Close upstream connections on early browser disconnect and close bounded
  HTTP error responses. Decode complete non-stream JSON metadata within a
  fixed quota, preserving response bytes and correct usage across formatting;
  do not credit partial or oversized metadata or infer native TPS from delivery.
- Separate the full Runtime Manager interface, including update/comparison
  review, explicit promotion, app opening and runtime selection. Bind approval
  to the exact plan, fence stale replies and restore controls for retries.
  Keep focused cards, disclosures and cached inventory usable on errors;
  desktop/mobile flows pass with generated replies.

- Extract all twelve engine builders, current artifact checks and immediate
  Uzu/llama.cpp handoffs into one independent planning domain, preserving public
  call shapes and twenty frozen complete native/variant launch outputs. Dispose
  fixed engine/bridge credential files and plan-owned credential environment
  fields on previews, rejected starts and shutdown. Keep unrelated files and
  symlink targets intact, traverse nested oMLX cleanup through verified directory
  descriptors, and preserve preexisting key files on exclusive-create collisions.

- Separate complete benchmark, ANE and runtime-comparison storage. Read larger
  histories without silently treating them as empty; preserve unsupported or
  damaged files with visible errors. Serialize concurrent appends, reject
  external edits before commit and bound lock waits. Reuse unchanged decoded
  files while keeping route eligibility fresh; generated repeated-read CPU
  overhead improved about 3.8× without an inference-speed claim.

- Extract the complete owned session lifecycle, including engines, private
  proxies, attachments, idle/cache policy and Pi/oh-my-pi Console transport.
  Preserve exact launch contracts, executable handoff, live memory guards,
  cancellation epochs, once-only cleanup and scoped LM Studio model unload.
  Keep public controller call shapes compatible and verify them against frozen
  source and disposable process/RPC fixtures.
- Extract the full audited runtime-update job, preserving official-wheel and
  full-commit dependency checks, side-by-side paths, final-path smoke tests and
  explicit runtime selection. Drain command output while it runs to prevent
  pipe-buffer timeouts; keep output bounded and owned-process cleanup complete.
  Reject cancellation/publication and late-inspection races without recording
  trust for incomplete work. Recover from worker/output-reader start failures
  and preserve preexisting staging directories on a name collision. Release
  a failed launch worker's plan and bearer files so Stop and retry remain usable.
  Prepared route-check, tuning, clone and Session Set jobs also release failed
  worker publications; existing Session Set surfaces stay available.
- Centralize exact launch contracts and validate current runtime/model receipts
  before ports, credentials or launch files are allocated. Keep live/saved
  defaults, sampling, KV, reasoning and experimental consent unchanged, and
  retain fresh artifact checks in engine builders. Reject native Whallm's
  reserved port before allocation. Move late oMLX draft/adapter and MTPLX
  inverse-baseline/Hub-Python gates before catalog, key or template writes;
  invalid settings leave no launch artifacts.
- Separate saved launch/Session Set storage and their complete browser managers.
  Read all permitted saved system prompts instead of silently treating a file
  over 4 MiB as empty. Preserve corrupt or future-format files, retain cached
  visible entries on errors, and keep exact review/apply/launch contracts.
- Separate Setup Assistant and Model Acquisition jobs; fix cancellation races
  around process publication, verification and final status. Retain partial
  downloads for resume and retire owned downloader groups before verification.
- Separate the complete Model Library and acquisition interface. Preserve
  selected routes during filtering, keep exact file/license/revision review,
  and make inspection, download and retry errors readable on desktop and mobile.
- Extract exact benchmark evidence and tuning replay. Preserve local model,
  hardware, runtime, sampling, context, output and KV proof, including native
  generation metrics; cache only immutable wiring, never eligibility decisions.
- Extract complete Benchmark Lab, tuning, qualification and runtime comparison
  jobs into an execution service. Bind process, port and safety access to the
  exact accepted plan and cancellation epoch; preserve fresh loads and native
  workload contracts. Make evidence commit atomic with cancellation, retain
  rollback identity, and recover cleanly from worker or telemetry failure.
  Reject incomplete owned-unload proof before saving or loading another route;
  shared LM Studio uses explicit model-unload evidence while retaining its server.
- Extract complete Chat History/recovery and saved-chat resume review features.
  Bound incremental store I/O to the declared transcript/journal limits, retain
  corrupt or future-format files with visible errors, and preserve exact route
  review, apply and launch behavior. Extract executable identity verification
  into an independent module without changing retained-descriptor launch proof.
- Carry native Kolibri and Splash generation timing through live status and
  saved benchmarks. Validate rates against exact token counts and durations;
  preserve request latency separately and exclude buffered delivery rates from
  automatic generation-speed selection. Real Pi and oh-my-pi tool/history turns
  passed on both installed engines within the protected macOS reserve.
- Refactor stream framing, response metrics, controller reads, native resource
  telemetry and UI presentation into separate modules. Cache unchanged runtime
  probes, share catalog refreshes, scan fragmented events incrementally and
  accumulate tool arguments without repeatedly copying their entire prefix.
  Local synthetic tool-stream processing improved 4.84×; memory-read overhead
  fell from 1.94 ms to 0.015 ms. These measurements do not establish model TPS.
- Refresh the launch screen with model search, engine guidance, saved decode
  speed and first-token results, clearer readiness, responsive setup controls
  and fewer DOM writes during polling.
- Add oh-my-pi in Terminal and verified 18.6.3 Hub Console with a session-only provider and settings overlay.
  Keep helper roles on the selected local model, disable automatic fallback,
  preserve real reasoning across tool turns and pass exact context/response
  limits. Real oh-my-pi tools, reasoning history, native framing, queued turns,
  abort and local commands passed with generated data. Separate the complete
  semantic Console feature from controller process ownership and transport.
- Add visible **Quit** controls. Cancel launcher jobs and delayed Terminal
  launches, stop primary and attached agents plus recognised local engine
  servers, unload LM Studio, report remaining processes/errors, then close the
  controller. Ordinary Stop retains its session scope.
- Reduce Kolibri SSD reader planning overhead by making span merges linear and
  caching immutable tensor strides. Packed expert byte ranges remain identical;
  CPU planning measured about 1.4–1.5× faster. Tiny native MLX checks passed Q8/Q6/Q4
  cache execution and hybrid-prefix restoration; no inference TPS or full-256K
  claim follows from these checks.
- Reuse original resident Q6 experts during Kolibri prefill, preserving router
  order, exact outputs and final warm-cache order. Original-row native fixtures
  reduced a 64-token expert sweep from 11.69 to 8.55 ms; full-model measurements
  remain separate. Bound mini-pools to the configured batch size and retain the
  legacy comparison path.
- Extract model tensor inventories and Qwen PLE/expert storage contracts.
  Revalidate current files and headers while reusing immutable header decoding;
  enumerate PLE primes once instead of restarting for every head. Reject a
  corrupt present checkpoint index explicitly.
- Handle renamed, automatically restarted local engine services in Quit by
  verifying and unloading their exact user LaunchAgent before the process sweep.
  Preserve process-birth receipts for workers that become orphans; unrelated
  services and arbitrary shell jobs remain unaffected.
- Recognise manually started, retitled oMLX servers through native process and
  installed mapped-library proof. Recheck kernel birth and executable before
  signals; retain independent receipts for multiple Terminal agent instances.
- Correct Mac capacity accounting: use current native reclaimable page bytes
  for loading and OS reserves, while retaining memory pressure separately.
  Older pressure-only measurements remain historic speed evidence but cannot
  qualify physical capacity. Keep the existing limits and reserves unchanged.
- Verify the Kolibri prefill refactor on the full original checkpoint: the same
  8 GB/2K/128-output contract produced identical tokens and 24.8%/18.8% higher
  cold/warm prefill throughput in one process pair. Decode varied in both directions;
  these results do not establish a generation-TPS gain.

- Default Kolibri SSD prefill to 64 tokens, freeing 18 GiB of reserved attention
  workspace versus 256-token chunks at 256K context with quantized KV. Assign
  the remaining admissible memory to Q6 experts. Keep explicit saved chunk
  settings available. Catch short repeated reasoning paragraphs in Pi's
  fallback guard and omit aborted thinking-only loops from resumed context
  while preserving the saved transcript.

- Enable Pi for Kolibri SSD with native JSON function-tool responses, tool
  history and reasoning controls. Include tool schemas in the tokenizer context
  guard, expose recognisable context-overflow errors, and bound Pi summaries to
  4K output with reasoning off. Pi uses the selected Kolibri context, response,
  KV, prefill and memory settings. Tests and live Pi verification were skipped
  at the user's request.

- Raise Kolibri's context ceiling from 8K to its native 256K and maximum
  response to 64K. Add Q8/Q6/Q4 KV for its ten full-attention layers, preserving
  native BF16 sliding caches. Correct the installed mlx-lm Q6 packed cache
  allocation inside the owned worker. Add prefill and retained prompt-cache
  controls with memory reserves, saved settings and strict live route checks.
  Fix hybrid prefix snapshots so consecutive chat turns reuse the quantized
  cache. Three real turns passed with 256K configured and Q8 KV; full-window
  capacity was not exercised.

- Expand Splash discovery to every supported local GGUF variant, MLX affine
  Q4 checkpoint and existing Q4 pack. Use Splash 1.2.1's native header checks,
  matching DFlash2 drafts and model-directory server contract. Reuse target
  weights through verified links and preserve native thinking/tool constraints.
  Live checks passed for the installed 35B Q6_K and 27B Q4 pack.

- Add Kolibri Q6 SSD offloading to built-in Chat. Automatic sizing spends the
  available memory on expert weights after context, runtime and macOS reserves,
  with a 40 GB default ceiling and a final startup recheck. Keep the complete
  Q6 checkpoint in its existing folder and authenticate the owned native server.

- Fix release-review blockers: retain Python 3.10/3.11 parsing compatibility,
  pass Splash's private key to its native server, distinguish Splash packs in
  the catalog, and ignore stale acceleration controls on engine-managed routes.
  Standalone Splash hosting now validates its install and pack, uses the native
  thinking-budget adapter, and authenticates readiness checks. Both hosting
  helpers clean up their children on stop; Qwen handles SIGTERM as well as
  Ctrl-C. Exclude local benchmark runtimes, derived packs and run state from
  staging, and include JavaScript module tests in CI.

- Enforce a separate thinking budget in Splash decoding (low 1K, medium 4K,
  xhigh/default 32K, at most half the response allowance). The native decoder
  closes thinking and continues to answer/tools in the same request, including
  across DFlash speculative batches. Keep grammar validation and Unicode
  intact. Omit previous length-ended thinking-only attempts from Pi context
  without deleting saved history. This addresses 64K circular-thinking turns
  that changing-wording repetition guards cannot detect.

- Remove Splash's artificial 32K Max response ceiling. Larger allowances now
  follow the selected context with prompt room, propagate into the native
  server and Pi, and receive a proportional native request deadline. Detect
  the observed Pi failure that generated thousands of decimal digits in
  reasoning; stop the stream, retain the saved transcript, and omit damaged
  thinking from retry/compaction context. Splash checkpoints use thinking off
  and a 4K allowance; Pi exposes the engine's actual reasoning levels.
  Live Pi/Splash write/read/final-answer verification passed with a 65,536-token
  allowance. This contains numeric runaway; it does not claim to fix its
  underlying model/runtime cause.

- Fix **Pi on Splash**: the engine compiles tool schemas into a per-property
  grammar and rejects a top-level `anyOf`, which Pi's `browser_check` uses for
  its per-action requirements — every Pi turn failed with
  `400 unsupported top-level tool schema keyword(s): anyOf`. The relay now
  forwards a Splash-compatible schema (`splash_runtime.compatible_tool_schema`,
  applied by `relax_tool_schemas` in `session_proxy.transform_chat_request` for
  the `splash` backend only): unsupported *root* keywords are dropped, every
  nested keyword, enum, description and required name the engine can compile
  is preserved, and one notice is logged per relaxed request. The tool keeps
  validating its own arguments, so the contract still fails closed. Verified
  against the installed engine's own schema compiler (it rejects the original
  and compiles the relaxed schema) and end to end: the real captured Pi request
  with 9 tools returned `HTTP 200` through a live relay on the running engine.

- Measure the follow-up-turn comparison that decides agent workloads: on a
  112,881-token context Splash returns its first token in **390 ms** with
  112,864 tokens served from the prefix cache, while MTPLX's "warm" request
  reports `cachedPromptTokens: 0` and takes **439 s** — its session-bank entry
  is evicted at this context (`bank_entries_evicted: 1, bank_bytes_after: 0`),
  so every turn re-prefills the whole prompt (Q8 the same: 438 s). Roughly a
  thousand-fold difference per turn; the guidance is one Splash server with a
  stable prefix and at most four agent lanes, which is also the engine's
  concurrency cap (4 streams ≈ 79-81 tok/s aggregate, 8 streams no better).

- Make **Splash a first-class launcher engine**. New `splash_runtime.py`
  discovers the Homebrew install and verifies the release hashes from
  `libexec/release.json`, scans every pack under
  `~/Library/Application Support/Splash/models/<owner>/<repo>` (manifest plus
  `target/`, `draft/`, `tokenizer/` required), and exposes one model record per
  pack with fixed 16K/32K/64K/128K/256K context windows. `launcher.py` registers
  the adapter, the engine button and its control panel, a memory estimate
  (packed weights + ~32.5 KiB per context token of paged KV + a 2 GiB reserve),
  reasoning pinning (`off`/`low`/`medium`/`xhigh`), and a launch path that runs
  the engine's own `server.py` on a launcher-allocated loopback port — the
  Homebrew CLI's hardcoded 8000, which the oMLX route owns, is never touched.
  The launch re-verifies the engine release and pack manifest identity before
  loading and the health check validates `/v1/models`; a changed install or
  pack fails closed with a rescan request. Verified end to end on this Mac:
  the wrapper started the real pack at 128K, `/v1/models` returned
  `incoai/Qwen3.8-27B-Splash`, a chat completion answered, and the engine
  stopped with the run. Docs: `docs/SPLASH.md`; tests:
  `tests/test_splash_runtime.py`, `tests/test_splash_ui.js`.
  Live API check: `/api/launch` accepted the route, the launcher-managed
  engine reported Ready at 128K on its allocated port, `/api/chat` streamed a
  real answer (reasoning content included) through the private relay, and
  `/api/stop` released the run. Splash validates `top_k >= 1` even when
  decoding is greedy, so the launcher pins `top_k: 1` on that route when a
  locked contract carries `top_k: 0` (temperature 0 selects the engine's
  greedy cohort, so the value is unused and the measured contract is
  preserved).

- Close the Splash **execution-geometry** TPS lane with engine-native
  evidence. A pack's `manifest.json` carries `execution_geometry`, and the
  native binary parses those keys — but it does not honour edits to them:
  `maximum_batch_width: 8` and even `: 1` still produced
  `memory_plan.budget.maximum_batch_width = 4`, and
  `draft_proposal_tokens: 12` still produced 7 drafts per step with
  bit-identical acceptance (693 drafted / 156 accepted / 0.2251 in both arms).
  The derived-pack machinery built for the test stays in the bench tools
  (`bench/derived/`, `bench/run.py --splash-pack`, native `/status` capture in
  every Splash result), and the apparent 14% `prefill_token_budget` gain turned
  out to be session drift. `--max-memory 44G` also leaves the geometry at 4.
  What remains is the serving shape: 4 concurrent streams reach 79.2 tok/s
  aggregate (engine metric 81.0) and 8 streams only 80.3, because the engine
  caps decode batches at width 4 — so one Splash server and up to four agent
  lanes per Mac is the correct topology, with the prefix cache doing the rest.
  Full detail: `bench/notes/splash-tps.md`.

- Make the Splash route runnable on this Mac: `tools/run_splash_128k.py` starts
  Inco's engine on a free loopback port (8010 by default) instead of the CLI's
  hardcoded 8000, which the launcher's oMLX server owns, with `--check` to
  validate the install and package without launching. Verified live: serves
  alongside oMLX, `/v1/models` and chat completions answer correctly, Ctrl-C
  stops the engine. `docs/SPLASH.md` documents the install, the measured
  numbers and the concurrency guidance; `tests/test_splash_route.py` pins the
  argv construction and the fail-closed package checks.

- Measure Inco's new **Splash 1.0** engine (`incoai/splash`) on the standing
  128K prompt and add it to the benchmark harness (`bench/run.py --engine splash`,
  which drives `server.py --port` so the user's oMLX service keeps port 8000).
  Cold prefill **324.5 / 337.9 tok/s** and decode **25.30 / 25.33 tok/s** over
  two runs, with a cached-prefix TTFT of **390 ms** on a 112,881-token prompt —
  the fastest 27B prefill and decode measured on this machine, +7% prefill and
  +31% decode over the MTPLX route, 5.5× decode the original launcher baseline
  but 1.38× prefill (still short of the 1.5× bar). The pack is a repacked
  `mlx-community/Qwen3.8-27B-4bit` target plus Inco's DFlash 2 draft, so the
  win comes from shape-specialised kernels and speculative decode, not from a
  lower-precision model. Details, caveats and the (not yet done) launcher
  integration: `bench/notes/splash-engine.md`.

- Probe the last structural lever for 27B prefill speed — ANE offload — and
  record exactly where it stands (`bench/notes/ane-prefill-probe.md`). The
  launcher's own scan reports the locally installed
  `lmstudio-community/Qwen3.8-27B-MLX-6bit` and `-8bit` checkpoints as
  **ANE-ready** (the 4-bit Speed pack is not: group size 32 vs the required
  64/128), so no download is needed. Two blockers were measured: (1) with the
  managed `omlx-0.7.0.dev2` selected, the launcher's ANE tuner dies on
  `HTTP 401: Admin authentication required` because 0.7.x gates
  `/admin/api/bench/ane-tune/*` behind an admin session cookie, while the
  managed 0.6.4 runtime accepts the same bearer key (minimum supported ANE
  runtime is 0.6.3rc2); (2) driven directly against 0.6.4 the tuner calibrates
  a real split — GPU-only 140.5 tok/s at a 2,048-token prefill, MLP **ANE
  53.0%**, GDN **ANE 37.5% / GPU 62.5%** — then fails to verify it under
  Apple's default Metal cap (`PrefillMemoryExceededError: ~44.74 GB peak vs
  35.57 GB ceiling`), which oMLX says to fix with
  `sudo sysctl iogpu_wired_limit_mb=43008`. That is a user-level action, so
  the route is parked pending approval rather than silently changed.

- Fix the launcher side of that probe: **ANE Tuner now works with the modern
  oMLX runtimes.** oMLX 0.7.x gates `/admin/api/*` behind an admin session
  cookie, so the tuner's bearer-only requests died with
  `401 Admin authentication required`; `ANETunerManager` now logs in once
  (`POST /admin/api/login` with the private engine's own key), caches the
  `omlx_admin_session` cookie per port and retries, and the cookie is reused
  for every later call. Verified live against the managed `omlx-0.7.0.dev2`:
  a 6-bit 27B ANE run now reaches the measurement phases (GPU-only baseline
  141.6 tok/s) instead of failing at the first request, and a unit test locks
  the retry/caching behaviour in. The remaining ANE blocker is Apple's Metal
  wired cap, which needs the user's sudo.

- Keep the benchmark harness on the runtime we ship: `bench/harness.py` was
  still pinning the obsolete `0.2.17-q8.2` Slotstream binary and applying no
  Q8 switches, so any arm that did not pass `--binary`/`--extra-env` explicitly
  measured a superseded engine. It now defaults to the pinned `0.2.20-q8.1`
  runtime and merges `slotstream_runtime.Q8_OPTIMIZATION_ENV` (4,096-token
  prefill passes, the twelve read-path switches and the 4,096-token workspace
  tile) into every Q8 launch.

- Close the 27B's remaining prefill-attention lane with evidence rather than a
  flag. A kernel workstream reproduced MLX's own NAX attention kernel
  (`attention_nax_dsplit`) through `mx.fast.metal_kernel` at several tilings:
  the replicas are **bit-exact** against the stock kernel (max|d| = 0, which is
  the hard part) but slower — `dsplit128` 0.80x/0.87x, `dsplit64` (the stock
  tiling, re-hosted) 0.84x/0.84x at kv = 32,768/113,000, and the no-head-split
  variants collapse to 0.26-0.31x. With the flag campaign already closed
  (`bench/notes/27b-prefill-hunt.md`: async rungs = no-op, chunk 1024 = −1%,
  4096 = −12%, 8192 = −3.6%, blocked GDN = +1.2% but not byte-identical, max
  fans = −2.5%), the 27B prefill is at the achievable ceiling of the current
  stack: 27.9-28.3 TFLOP/s GEMM against a 29.5-30.2 bf16 GEMM ceiling, and an
  18-21 TFLOP/s attention kernel we cannot beat from Python. Details and the
  remaining non-flag options (ANE prefill via oMLX ≥ 0.6.3rc2, a
  research-grade kernel, or quality-trading sparse prefill) are recorded in
  `bench/notes/RESULTS.md`.

- Raise Slotstream's MoE workspace tile to 4,096 for Q8 launches
  (`SLOTSTREAM_OPT_WORKSPACE_TILE=4096`, added to the launcher's Q8 switch
  set, applied to both the serve and the doctor ledger). The engine's default
  of 256 tokens of workspace per tile serialises 32 tiles per layer per read
  scope at a 4,096-token prefill pass, each tile ending in its own `eval`.
  Paired same-session arms at a 112,881-token prompt on the pinned
  `0.2.20-q8.1` binary: prefill **133.7 → 167.4 tok/s** (+25.2%) and a repeat
  with the full 256-token probe **168.9 tok/s**, decode 11.07 → 11.16/11.34
  tok/s (flat), greedy continuation byte-identical to the recorded reference
  `dcb56fb102e8…`, drafting unchanged at 130 of 250 drafts accepted. Flash-Next
  long-context prefill therefore goes from 1.58x to **2.0x** the original
  83.8 tok/s baseline. Evidence: `bench/results/20260918-234936-flash-tile-4096.json`,
  `bench/results/20260919-000134-flash-tile-4096-rep2.json`.

- Measure the MTPLX 2.11.2 runtime's own kernels on this Mac to explain the
  27B's 128K prefill ceiling: 4-bit qmm 27.9-28.3 TFLOP/s, bf16 GEMM
  29.5-30.2, fused causal attention at head_dim 256 / 24 q-heads / 4 kv-heads /
  q=2048 / kv=113,000 only 15.5-16.9 TFLOP/s. Those three numbers reproduce the
  whole 358 s prefill (~184 s GEMM + ~164 s attention + ~10 s GatedDeltaNet),
  so the route is at the stack's measured ceiling and the remaining prefill
  knobs are percent-level. Recorded with the microbenchmark harness
  `bench/microbench_mlx.py` and the arm log `bench/notes/27b-prefill-hunt.md`;
  the kernel project that could move the ceiling (`runtime-patches/mtplx-nax-prefill/`)
  and the two rejected "obvious" levers (maximum fans: 282.3 against 289.5
  tok/s same-session; session-to-session comparisons: the same config measured
  315.0 and 289.5 tok/s six hours apart) are documented there too.

- Keep acceptance honest at 128K: the shipped 27B route (MTPLX, full-precision
  KV, turbo, MTP depth 3) accepts 78%/65%/35% by depth at a 112,881-token
  prompt (2.78 tokens per verify round) and Flash-Next's Slotstream Q8 route
  accepts 130/250 drafts (52%). Bonsai-2's published Bonsai-1 dspark drafter is
  byte-exact but collapses from 64.3% acceptance at 4K to 1.8% at 128K, so
  speculation there is rejected rather than shipped.

- Document Bonsai-2-27B's two 128K routes and close the speculation question:
  MLX/MLX runtime at full-precision KV is 177.4 prefill / 9.0 decode, llama.cpp
  with `-ctk f16 -ctv f16 -fa on -ub 512 --load-mode mlock` is 128.2 / 11.8
  (against 122.8 / 9.5 on Q8 KV), and the dspark drafter experiment (1.42x at
  4K) is dead at 128K for economics rather than correctness. `docs/LONG_CONTEXT_128K.md`
  carries the table. The same llama.cpp route measured at the pack's native
  256K window on a 234,952-token prompt: **77.4 prefill / 7.56 decode**, no
  memory cliff (ttft 3,036 s; `bench/results/20260919-005828-bonsai2-gguf-256k-f16kv.json`),
  which completes the capacity sweep: 32K 266/21, 128K 128.2/11.8, 256K 77.4/7.6.

- Document the measured 128K long-context optima and the settings that produce
  them in `docs/LONG_CONTEXT_128K.md`: Qwen3.8-27B on MTPLX with full-precision
  KV (315.7 prefill / 19.3 decode tok/s at a 112,881-token prompt),
  Qwen3.8 Flash-Next on the Q8 Slotstream runtime (132.3 / 11.9), and the
  local 35B MoE through `tools/run_qwen35_moe_128k.py` (392.1 / 32.5). The
  document also records the alternatives that measured worse, so the
  trade-offs are not re-litigated.

- Record a measured kernel experiment that is **not adopted**: staging the Q8
  reduce kernel's row maximum and per-part softmax weights in threadgroup
  memory removes ~195M redundant `exp` calls per speculative round, builds
  cleanly, passes all 45 q8-cache assertions and reproduces the greedy output
  byte-for-byte — but two runs (12.14 and 11.71 decode tok/s) are
  indistinguishable from the five runs of the shipped kernel (11.84-11.96).
  The pinned runtime therefore stays `0.2.20-q8.1`; the patch is kept at
  `runtime-patches/slotstream-q8/q8-kernel-reduce-staged.patch` as evidence.

- Import the user's Qwen3.8-35B-A3B Q6_K GGUF into the scanned LM Studio
  model root (hard-linked, no duplicate 27 GB) and add
  `tools/run_qwen35_moe_128k.py`, which serves it through the launcher-managed
  llama.cpp at 128K with Q8 KV and the measured-fastest flags. At a
  112,881-token prompt: **392.1 prefill / 32.5 decode tok/s** with
  `--load-mode mlock` (358.5 / 31.5 with mmap), byte-identical greedy output.
  The launcher's LM Studio route cannot express `mlock`, so the helper is the
  documented way to run the maxed configuration.

- Rebase the local Slotstream Q8 KV fork onto upstream v0.2.20 as
  `0.2.20-q8.1` (same Q8 cache arithmetic, upstream's decode-lookahead,
  prefix-state and correctness work included) and enable the engine's
  validated read-path switches for Q8 launches. Paired measurement at a
  112,881-token prompt with the corrected tap sidecar present in both arms:
  cold prefill 90.4 → 124.7 tok/s and decode 8.62 → 10.74 tok/s, with
  byte-identical greedy probes. The maintainer's Metal toolchain component
  must be installed for rebuilds; the recipe and hashes are pinned in
  `runtime-patches/slotstream-q8/`.

- Use 4,096-token Slotstream prefill passes for Q8 launches. At the same
  112,881-token prompt the larger pass measured 128.6 prefill / 11.26 decode
  tok/s against 124.7 / 10.74 at the planner's 2,048 default, even though it
  costs ~2.6 GB of the process budget; the engine accepts 256-4,096.

- Add the engine's launch-reduction switches to Q8 Slotstream launches
  (compiled final norm, fused GDN recording, slot-word writes, workspace
  pieces). Measured at 112,881 tokens: prefill 127.7 → 132.3 tok/s with an
  unchanged 11.84 decode and byte-identical greedy output. The individual
  contribution of each switch is not yet bisected.

- Raise Slotstream's default whole-process ceiling from 30 GB to 36 GB so the
  native auto planner may keep a larger expert pool. At a 112,881-token prompt
  with Q8 KV and MTP depth 2 this took the expert cache from 12.9 GB to
  19.0 GB, the hit rate from 75.9% to 90.1% and decode from 7.03 to
  9.68 tok/s (+38%); prefill was unchanged. The engine still sizes down to
  live reclaimable memory and the capacity check still fails closed.

- Lift MTPLX's compiled-verify fence to the selected window above 32,768
  tokens. The turbo profile pinned `MTPLX_COMPILED_VERIFY_MAX_CONTEXT` at
  32,768, so every speculative verify at a larger context ran the eager path.
  A local A/B at a 112,881-token prompt with paged KV Q8 and MTP depth 3
  measured decode 4.56 -> 10.05 tok/s with a byte-identical greedy
  continuation; the fence is now launcher-owned and stripped from any
  inherited shell environment. Prefill was unchanged within run-to-run spread.

- Add checksum-pinned oMLX 0.7.0.dev2 as a selectable preview with isolated
  installation, exact development-version identity and preserved rollback provenance.
  Make the verified full Flash Q4 pack selectable with expert and PLE SSD offload,
  adjustable expert RAM share and a user RAM ceiling. Preserve upstream MTP/DFlash
  incompatibility with expert offload; show native oMLX prompt/decode timing.

- Report Slotstream Q8 native prompt processing as soon as prefill completes,
  excluding reused tokens; show native decode speed, MTP acceptance and expert-cache
  allocation/hits on completed requests.

- Add a separately pinned Slotstream Q8 KV runtime with main/MTP cache
  quantization, fused sparse attention, prefix-safe rollback, and memory
  accounting. The launcher preserves the explicit Q8/full-precision choice.

- Remove the Slotstream-specific 36 GB input cap; native available-memory and
  Metal checks still determine what can actually be allocated.
- Stop Pi from sending the unsupported OpenAI response-storage field to local engines.

- Fix Slotstream startup on busy Macs with automatic expert-cache sizing inside
  the selected memory ceiling, preserving context and MTP; retain fixed sizing.
- Remove the launcher-only 32K response cap for Slotstream. Responses may use
  the chosen context minus at least 1,024 tokens for instructions and history.

- Stop every guarded native engine on watchdog exceptions or loss of the guard.
- Bound concurrent relay uploads and retained request bodies before parsing,
  enforce upload deadlines, and reap disconnected queued requests.
- Classify incomplete/error streams separately from successful completion;
  exclude buffered or insufficiently timed responses from decode-speed rankings.
- Preserve an explicit acceleration selection when a model rescan makes it
  unavailable, and block launch until the request is valid or changed explicitly.
- Add the pinned Slotstream 0.2.17 Qwen3.8 Flash-Next adapter with full-expert
  SSD streaming, explicit native MTP, 16K–256K context choices and checked memory budgets.
- Verify the complete model before every load, preserve authenticated session
  controls, and show incomplete model downloads without allowing an early launch.
- Support Chat, Pi and OpenCode; keep Responses, vision and custom sampling
  unavailable on this initial route. No local speed claim is inferred from availability.

## 1.67.0-alpha.1 — 14 September 2026

- Simplify everyday launch controls and consolidate the Pi Hub toolbar to make
  more room for the conversation. Keep measured fastest-engine selection nearby.
- Add editable/deletable queued messages, steering, slash commands, timestamps,
  streaming tool previews, prompt summaries and saved-conversation recovery.
- Separate prompt-processing speed from decode speed and show context tokens
  used, capacity and remaining space. Bound transcript rendering and idle polling.
- Repair Pi transport backpressure, relay cancellation and recoverable context
  admission failures. Long-running sessions can compact and continue, but
  repeated memory-driven compaction and model/tool failures remain possible.
- Add version-gated DFlash Q4/Q6/Q8 target KV support with prefix-cache handling
  for the audited oMLX runtime. Adaptive and Fixed DFlash support this path;
  DDTree does not. Bound quantized prefill batches and reclaim unused Metal
  buffers at committed prefill/decode boundaries.
- Add estimated launch memory, optional Hub fan controls and updated runtime
  adapters. Availability and speed depend on the model, engine and Mac.

This remains an alpha. Cached-input reuse has been observed in extended local
sessions; it is not a guarantee of task quality, freedom from loops, or any
particular decode speed. Raw local session captures are not distributed.

## Full-expert Flash on this Mac — 7 September 2026

- Add a launcher-owned route for the installed Whallm 1.1.4 full-expert
  Qwen3.8 Flash model, including actual model-load readiness, bounded memory,
  thinking and native cached-input accounting.
- Fix Pi's inherited compaction reserve for small context windows. A 16K
  session now has room for messages and a summary instead of immediately
  attempting compaction.
- Remove redundant telemetry calls from idle health monitoring. Keep engine
  health checks and the Hub's live measurements.
- Compare expert-cache sizes on the M5 Pro and retain 4,096 slots for memory
  headroom. Remove the incompatible REAP copy, keeping all 27B models.
  See [device measurements and limits](docs/FLASH_DEVICE_TUNING.md).

## A smaller everyday interface — 7 September 2026

- Keep Sessions, Models and one Advanced menu in the home navigation. Put
  appearance and management tools there, and collapse engine tuning inside
  Settings. Keep Choose fastest engine beside the model.
- Give the Hub one compact toolbar and more conversation space. Remove the
  duplicate single-session tab and idle instructions; show message actions
  when relevant. Move copy, compaction and queue cleanup into the overflow menu.
- Add a direct Return to Pi action on Home without stopping or recreating the
  running session. Verify navigation, queue, stop, themes and mobile layout in
  the real browser with installed Pi.

## Qwen route reliability — 7 September 2026

- Update the audited MTPLX release to 2.11.2, including its hardware-gating,
  session-cache and verifier-memory fixes. Keep 2.11.1 calibration receipts
  tied to their exact runtime; do not reuse them for the new engine.
- Apply repaired Pi cache identity at the relay boundary so a later global
  extension cannot restore damaged reasoning from the old native cache.
  Verify with installed Pi and a reproduced late extension overwrite.
- Add a bounded generated-data session check covering longer prompts,
  preserved thinking, cache reuse, changed facts and independent sessions.
- Supply Pi with a private browser tool when Playwright is already installed.
  Small browser checks no longer need a generated setup script. Serialize page
  actions, bound output, and close the owned browser on cancellation, timeout
  and session shutdown. Keep the user's browser separate.

## Pi Hub transport recovery — 7 September 2026

- Fix a PTY deadlock that froze Hub status and output after the engine finished. Extract bounded nonblocking duplex I/O, preserve command order, and coalesce pending state probes.
- Interrupt both sides of a cancelled relay request, including detached HTTP response sockets. Bound writes to unresponsive clients so they cannot occupy the engine lane indefinitely.
- Add real PTY/socket backpressure regressions; verify installed Pi streaming, queued messages, abort and saved transcript recovery. See [diagnosis and verification](docs/PI_HUB_TRANSPORT_DEADLOCK.md).

- Treat oMLX's native `prefill_memory_exceeded` admission rejection as recoverable through Pi compaction. Preserve its memory diagnostics and limits, leave unrelated memory failures unchanged, and mark rejected HTTP requests as failed rather than completed in Hub activity.

- Fix oMLX 0.6.4 DFlash Hub sessions stopping on a false context overflow: count the actual rendered prompt with the engine tokenizer, bound the remaining response, and expose genuine overflow in the format Pi recognises for automatic compaction.
- Show a temporary live code preview while oMLX buffers a Qwen tool call. Match it to the active response and surface, keep it private and bounded, and remove it on completion/cancellation. The upstream final tool parser and Pi execution remain unchanged.

## Hub prompt speed and context usage — 5 September 2026

- Add Prompt and Context fields to the existing horizontal Hub status bar. Use live engine prefill telemetry where available and matched native Uzu completion measurements; never divide cached prompt totals by time to first output.
- Publish Pi’s own context estimate through its status bridge, including generated output and unknown usage after compaction. Never substitute a pre-compaction percentage when Pi reports that the count is unknown.

## Pi live code, extension speed and context recovery — 5 September 2026

- Reassemble Pi RPC tool-argument fragments, show readable write/edit code while it streams, and collapse tool details when finished. Preserve live execution output and manually reopened completed details.
- Read `pi-token-speed` from Pi's actual `setStatus` events. Strip terminal colours and retain bounded latest statuses outside the transcript; label live versus last Pi speed without treating estimates as calibration evidence.
- Remove the obsolete Uzu JSON-byte context check. The pinned runtime still enforces exact rendered prompt tokens plus the full response allowance. Preserve its overflow code in the error message so Pi can compact and retry automatically.
- Show transient compaction progress, distinguish failure/cancellation from success, and add a Compact action. Explicit Pi session-file launch recovery validates the project and retains Pi-owned history.

## Reuse Uzu capacity after response-limit changes — 5 September 2026

- Session admission reuses a valid Uzu capacity receipt across response
  ceilings with the same bounded test budget, within the same context window.
  This avoids repeating 64K and 128K tests for a 50,000 → 64,000 Max response
  change. Stored receipts stay unchanged; speed comparisons remain exact.
- Show “Saved capacity check reused” on the launch home. Changed models,
  runtimes, context tiers, reasoning, sampling, or expired/invalid proof still
  cannot reuse that result. Live memory admission and runtime guards remain.

## Hub speed and request progress — 5 September 2026

- Keep the selected surface's previous measured speed visible during requests
  without live token counts, explicitly labelled “last”. Prefill throughput is
  labelled separately from generation speed, and Pi tool requests are no
  longer described as Chat turns.
- Show a temporary Hub activity line for prompt preparation, reported prefill,
  generation, and queuing. It clears when the request finishes. First-output
  timing resets for each new request instead of falling back to an older one.

## Activity Monitor name — 5 September 2026

- The macOS controller registers as **LLM Launcher** in Activity Monitor on
  startup, without modifying Python or adding a Dock icon. Naming is optional
  on systems where the macOS display-name APIs are unavailable.

## Pi Hub thinking visibility — 5 September 2026

- Keep Pi's per-token status and other presentation commands out of the
  transcript journal. Genuine notifications and input requests remain visible.
- Remove legacy `setStatus` cards when reconnecting to an existing controller,
  without stopping Pi. Thinking stays expanded unless the reader collapses it.
- Verified the repaired transcript in Safari against the active Uzu/Pi session.

## Simplified launch home — 5 September 2026

- Rebuilt the home around model selection, Chat or an agent, a working folder,
  and one Launch button. Context, sampling, runtime tuning, saved routes, and
  diagnostics are grouped under Settings. Only compatible models appear in
  the launch picker; the full inventory remains in Models.
- Launch now handles fresh capacity checks and required first-use route
  qualifications, reuses matching saved results, and continues automatically
  after success. Uzu's missing 64K prerequisite for a 128K test is staged
  automatically; Pi retains the existing Chat-capacity-only evidence boundary.
- Added inline progress, cancellation, and memory review. Failed or cancelled
  preparation never launches; cancellation cannot stop a replacement job.
- Verified a real one-click Uzu/Pi launch, automatic prerequisite start and
  cancellation, and desktop/mobile presentation. Python: 480 tests passed
  with 20 optional skips. JavaScript: all 42 test scripts passed, including
  14 preparation workflow tests.


All notable public changes are recorded here.

## Unreleased

- Extend continuous whole-Mac memory protection to every oMLX, LM Studio and MTPLX benchmark mode, during loading and requests. LM Studio remains monitored even without a live CLI child. Two consecutive reserve breaches or three unreadable samples stop the owned route and prevent a result from being saved. Generation-bound Stop prevents delayed benchmark cleanup from stopping a replacement run; runtime-specific Uzu/llama.cpp ceilings are unchanged.

- Pi's cancelled/error turns no longer raise the misleading “finished reasoning without a final response” provider warning. That warning is now restricted to an actual clean thinking-only finish; response-limit guidance is unchanged. Paused Hub queues describe their state without guessing why the previous response stopped.
- Add an opt-in real-browser/installed-Pi regression using generated streaming responses and no model or tools. It exercises scroll detachment, queuing, reload after event-journal overflow, Stop response and recovery, and stopping the agent while retaining its transcript. Frost/Daylight checks cover black Hub background, distinct thinking cards and equal-height aligned composer buttons.

- Version the corrected greedy correctness-probe contract for oMLX, LM Studio and MTPLX. Older unmarked runs remain saved but cannot choose settings automatically; history explains that their correctness sampling needs a re-test. The already verified MTPLX operator-v5 contract remains eligible subject to its full verifier, and Uzu's separate packaged-sampler capacity receipts are unchanged.

- Fix Pi Hub transcript loss after long thinking or queued turns. Token-journal turnover previously discarded completed tool results from fresh-tab/missed-poll replay even when the conversation itself was small. A separately bounded in-memory conversation snapshot now preserves item order and resumes incremental updates without duplicated text. Regression coverage includes journal overflow, late updates, UTF-8, memory bounds and the actual browser reducer.
- Verify a real Uzu–Pi cache-repair task using restricted builtin file tools and a sandboxed fixed test runner: eight tests passed, the queued reply and tool results survived replay, Stop paused the next queued message, and a fresh request recovered without losing prior answers. Both processes unloaded. This is one controlled coding/interaction test, not a sustained agent benchmark or proof of general coding quality.
- Enable Uzu Pi for the exact locally verified runtime/model and Pi 0.84.2. Normal primary Hub startup, one real generated-data tool call, a retained follow-up, thinking/answer reconciliation, and clean agent/model shutdown passed at qualified 64K. Pi reuses the exact Chat capacity receipt without relabelling its TPS as agent performance. Unsupported Pi speed calibration is blocked with an explanation instead of offering an unusable repeated test; keeping the already capacity-qualified fixed route does not require another calibration. OpenCode remains gated.
- Add opt-in real Uzu/Pi integration checks with no builtin file/shell tools, user extensions, context files, or cloud credentials. Separate native/private-relay tool round trips and interrupted-response recovery passed. The real browser also verified normal Pi capacity admission and settings persistence after reload without loading a model.

- Preserve the selected goal in standalone benchmark jobs. A real restart test found the fixed MTPLX generation-TPS sweep saved as `fastest` because the job builder dropped the preference; its valid measurements were then invisible to TPS history lookup. New operator records explicitly bind throughput, and the known standalone v5 label error is interpreted without rewriting evidence or relaxing record verification. Practical-tie results explain the measured percentage and switching threshold.

- Measurement history now offers **View results** for verified saved current-engine runs, including after a controller restart. Review uses the saved record rather than fabricating a completed job, survives idle polling, and clears when settings or live work change. MTPLX's specialised 64K settings suite is also included in history and performance-receipt lookup without confusing it with the cross-engine Agentic workload.

- Fix a false greedy-parity failure: the benchmark request builder let the launch sampling contract overwrite the fixed correctness probe (temperature 0 became the model's temperature 1, with no seed). Warm-up and correctness requests now explicitly select the fixed probe contract; timed workload requests and user launch settings retain their original sampling. Uzu's packaged sampler is not falsely labelled greedy. MTPLX operator receipts advance to version 5 so sampled-probe results cannot be reused as verified greedy comparisons.

- Fix Apply/reload losing the measured context and runtime controls: the real browser check exposed 65,536 context reverting to the 131,072 default. The visible route now retains bounded, non-secret controls and revalidates their availability on restore; prompts, paths, credentials, approvals and qualification claims are not stored. Apply/reload/Apply passed against a real saved MTPLX result without retesting or loading a model.
- MTPLX result copy now distinguishes an exact-output mismatch from a speed failure, including when displaying already saved results. A faster but mismatching MTP route is shown honestly instead of claiming it was slower than AR.

- Stop and discard a running benchmark after a sleep/clock discontinuity or a prolonged telemetry gap. The check compares wall time with monotonic time so macOS hibernation cannot silently span a supposedly continuous speed comparison. It uses the existing owned-process unload path and does not prevent the Mac from sleeping.

- Benchmark Lab now keeps the last completed turn's generation TPS visible beside progress, with the measured route/stage identified in its tooltip. A new route starts at Measuring rather than inheriting the previous route's speed. This is explicitly a completed-turn measurement, not a fabricated live-token estimate.

- Fix final MTPLX calibration validation adding the configured 16K reply ceiling to a near-64K prompt even though the measured request allowed only 256 output tokens. Version-4 operator receipts now bind and validate each actual request allowance, including completion limits, without changing the user's launch settings or accepting older unbound evidence.

- Completed current-engine Benchmark Lab results now offer **Use measured settings** directly. The action carries the exact saved-result reference, checks that the visible route still matches, and closes the result dialog only after successful application. It never starts a replacement calibration automatically; incomplete or mismatched results have no Apply action.

- Fix a circular MTPLX Calibration admission check that demanded a completed result before allowing the candidate measurement that would produce it. Only the trusted benchmark path can measure the candidate without a saved result; static runtime/model revalidation and memory admission remain required. Normal launches, saved profiles, Session Sets, and Route Check still require completed evidence, and caller-supplied flags grant no bypass.

- Fix MTPLX long-context calibration's synthetic corpus sizing: the installed Qwen tokenizer split some words into two tokens, turning the intended 61K prompt into roughly 74K and overflowing a 64K session. The fixed vocabulary now uses verified token costs, with CPU-only real-tokenizer regression coverage. Operator-sweep receipts advance to version 3 so earlier workload results cannot be reused silently; native usage must still prove near-64K coverage.

- The isolated MTPLX 2.11.1 long-context comparison now stops on two consecutive readings below the protected whole-Mac memory reserve, or three unreadable readings, including while a model loads. This supplements per-load admission and recorded telemetry; it does not alter macOS memory limits or fan settings. AR and MTP failure-path tests verify unload and rejection of incomplete evidence.

- The opt-in real Uzu browser test now verifies separate thinking, queued replies, scroll preservation during streaming, asynchronously reported TPS, and End chat unloading the model while retaining the conversation. It passed on the qualified local 128K-window route; its short rendering prompts are not a coding-throughput benchmark. Cleanup is restricted to the test-owned run.

- Reopened saved Calibration results now show 100% alongside Ready to use instead of a misleading empty progress bar. A lone qualified-route card uses the full result row. An opt-in isolated browser check exercises real saved-result Apply/reopen/reload without loading a model or changing server-side profiles.

- Current-engine MTPLX benchmarks now run the same three-route 2.11.1 operator comparison as Calibration when an eligible 27B model, Turbo, Agentic workload and at least 64K context are selected. The UI discloses all three setups and 18 generated requests before starting. Other engines are not loaded, Sustained is not silently changed, and the existing correctness/resource/TPS promotion gates still apply.

- Adopt the exact locally qualified Uzu bounded-prefill build (`0.5.23-llm-launcher.prefill-experiment.1`) on the developer host. Its unchanged 64K/128K receipts are now available to normal calibration planning; existing history and the old `.2` executable are preserved. The 128K run completed four reasoning-and-answer turns at 56.075 median generation tok/s and 25.10 GiB measured process-group peak, but cold 98K-token prefill still took 344 seconds. This is local workload evidence, not a public runtime distribution or general output-equivalence claim. The live ceiling is 38 GiB with the independent system reserve and admission margin retained.

- Raise Uzu's live process-group ceiling from 36 to 38 GiB at the user's request. Keep the independent whole-Mac reserve monitor and 2 GiB admission margin. Existing valid 36 GiB receipts remain usable only for their measured context and below their original recorded peak limit; this does not qualify 128K or rerun a model automatically.
- Replace Uzu's fixed 2,048-token qualification output cap with a context-aware allowance of up to 8,192 tokens, capped by the selected response limit. Preserve a prompt-framing margin and the final follow-up's reserve. Version-5 receipts bind the budget policy, each request's exact allowance, and the measured range; Apply reconstructs these from numeric evidence. Old receipts cannot authorize the new qualification, and truncated answers still fail.
- Make Uzu qualification use one real conversation, echoing exact reasoning and answer channels in memory instead of canned replies that force the native server to reset its cache. Size added synthetic tool padding from prior authoritative usage and reserve space for follow-ups. Saved receipts bind the new conversation policy and reconstruct its adaptive targets from numeric evidence only; no generated text is persisted and near-tier/completion gates remain mandatory.
- Report output-token and reasoning/answer character counts when Uzu qualification stops, distinguishing reasoning-only output from a started answer and an unconfirmed terminal state. Generated text is not saved in these diagnostics, and failed samples remain ineligible for qualification.
- Replace Uzu qualification's open-ended assessment of random filler with a concrete Python cache-key defect, regression tests, a partial fix, and a model-revision follow-up. The same long corpus, prefix-reuse structure, near-tier usage requirement, model-default reasoning, and completion gates remain; padding is explicitly inert rather than fictional architecture evidence. The workload policy is bound into saved receipts.
- Give Uzu's native reasoning up to 2,048 tokens per qualification response instead of inheriting the SSD-PLE route's 512-token test cap. Preserve the user's configured response limit and all context/memory guards. Version-4 Uzu receipts bind the new measured allowance; frontend and controller share a regression-checked version, prompt-sizing policy, and token budget so Apply cannot reject a result due to contract drift. llama.cpp's explicit 384+128 split is unchanged.
- Correct Uzu qualification corpus sizing against its pinned tokenizer: several synthetic words consume two tokens, so the old word-count approximation overshot the intended long-context prompts. Keep the near-tier authoritative-usage gate, invalidate older corpus-policy receipts, and stop immediately if a turn is truncated, lacks reasoning/final output, or misses its target size. A CPU-only installed-tokenizer test covers all four context tiers without loading weights.
- Show the active agentic calibration workload and target prompt size before sending each request, rather than leaving the previous completed step onscreen during a long prefill. Retain the clearly labelled last-completed TPS instead of estimating token speed from stream chunks. Uzu's packaged-sampling correctness probe is no longer labelled greedy.
- Preserve valid Darwin memory samples when the kernel's peak counter briefly lags its current footprint during allocation. Use the higher current/peak value for ceiling enforcement; failed reads and zero counters still fail closed. Reproduced the lag in a 64 MiB CPU-only process before changing the monitor.
- Fix hardened Uzu 0.5.23 startup with an older installed Mirai catalog: create missing v2 offline metadata during explicit launch, pointing only to the already receipt/SHA-256-verified model directory. Preserve the model's encoding and bundled acceleration, bypass native downloads, keep outbound networking denied, and revalidate the exact catalog at process launch. Existing different catalogs are never overwritten. Verified native catalog listing offline; long-context inference qualification remains separate.
- Align the bottom action row across all themes, not just Frost: the performance card now matches adjacent action heights and helper copy no longer shifts their vertical positions. Launch keeps a stable width when warnings change, with its full explanation still available. A container-width breakpoint moves detailed-mode actions onto a second row before the inspector can crush the optimiser label; focused narrow layouts stack cleanly.
- Keep long Pi thinking and answers live after the 64 KiB per-block display limit: retain the newest UTF-8 text instead of silently ignoring further output. Final snapshots and history replay preserve the ending and label omitted earlier text; the existing memory caps remain in place. The installed-Pi fixture also checks response limits, interrupted-stream retries, paused follow-ups, and a long answer replayed by the actual browser timeline code.
- Add an opt-in installed-Pi integration check using the real launcher provider and Hub RPC/PTY connection against generated loopback responses. It verifies separate thinking and answers, queued follow-ups, abort without draining the queue, subsequent prompts, and retained history. The test isolates agent configuration, disables tools and discovery, and loads no model; it is not a model-speed or long-context qualification.
- Keep the launcher on its requested local port after a clean restart: bind the actual reusable HTTP listener instead of treating lingering closed connections as an occupied port. A genuinely occupied address still falls back; permission and other binding failures remain explicit.
- Keep saved Calibration results reusable through disk reload, Apply, browser refresh, and measured Quick Launch profiles, including a non-default winning runtime preset. Bound results now reject changed ANE-prefill or memory-guard settings instead of restoring them silently. Measured profiles retain those comparison controls without adding them to ordinary resident-route identities; loading a new calibration plan also clears the previous model's warning tooltip.
- Calibration now measures runtime presets as well as accelerator controls: oMLX burst, LM Studio GPU offload, MTPLX profiles, SwiftLM prefill sizes, and Mference prompt caching on the agentic workload. It measures AR at every preset, tunes acceleration on the provisional winner, then checks the retained acceleration settings at every other preset. Results disclose actual and maximum setup counts and preserve the exact winning configuration through save, reload, and Apply. This is a bounded staged search, not a guarantee of the global optimum; sampling, model fidelity, context, KV precision, memory guards, and the selected cooling policy remain fixed.
- Make Pi Hub **Stop response** bypass the ordinary prompt queue, so it reaches Pi even while a prompt POST is stalled. The button now shows one guarded **Stopping…** state, ignores duplicate clicks and stale process generations, keeps every queued follow-up in place, and always resumes transcript polling after the abort attempt.
- Harden the private inference relays around exact request contracts. oMLX Responses now rejects hidden or server-expanded history, media, retrieval, and versioned hosted-tool references that cannot be included in its conservative context bound; model-default reasoning strips client attempts to weaken or replace it; and non-contract sampler fields and aliases such as `logit_bias`, `dynatemp_range`, `repetition_context_size`, and camel-case variants fail closed. Non-stream Chat Completions are now held before headers up to the existing 128 MiB body ceiling, receive the same exact-limit `stop`-to-`length` correction as SSE, and return 502 rather than silently bypassing correction if oversized.
- Prevent Calibration from advertising or starting an impossible oMLX DFlash 2 load while a measured ANE-prefill setting is locked. That comparison keeps the user's ANE setting, measures only compatible AR/MTP routes, and explicitly says DFlash was not tested; turning ANE prefill off retains the full bounded DFlash search. Direct DFlash tuning now rejects the conflict during planning instead of failing after model load.
- Make capacity admission consistent across the whole hub. The main Launch action now stays disabled until a fresh, exact visible-route check succeeds and discards stale browser responses when model, context, reasoning, sampling, or work surface changes. Preview and settings remain available, while Route Check execution, Calibration measurements, generic benchmarks, runtime promotion, ANE tuning, and Session Set model loads all re-sample live Mac headroom immediately before `RunManager.start`; automated loads require an unqualified ready result and cannot reuse a memory-review acknowledgement. Runtime promotion also reports a blocked capacity check in its read-only plan instead of advertising two model loads that will fail later.
- Refresh the audited MTPLX entry to [2.11.1](https://github.com/youssofal/MTPLX/releases/tag/v2.11.1) at official release commit [`dd4031a8f9ed9d0a532b6e16bcc147dc40399c1d`](https://github.com/youssofal/MTPLX/commit/dd4031a8f9ed9d0a532b6e16bcc147dc40399c1d), while retaining the upstream warning that 2.11.0 was a retracted, mis-stamped upload containing 2.10.2. Add a fail-closed dense-27B long-context route for the release's operator recipe: only exact 2.11.1, verified MTP, Turbo, and at least 65,536 context can enter a user-triggered three-load AR/default-MTP/candidate-MTP comparison. Generated near-64K prompts must report authoritative usage, preserve exact output, start under comparable Mac conditions, and clear a 3% median and worst-case generation-TPS gate before the candidate can be saved, applied, or reused. Normal routes still pin `MTPLX_ALLOW_SWAP=0`; inherited operator and compiled-growth-reserve overrides are stripped, and no release setting is enabled globally.
- Refresh the audited optional Whallm route to 1.1.4, including its Qwen/Codex reply and prompt-cache reliability fixes, ANE prefill path, current 9.7–10.4 generation tok/s M5 Pro reference range, and 22.75 GiB peak MLX active memory through 16K input. These remain upstream reference figures rather than local evidence. Whallm's optional MTP prototype stays outside automatic selection because its own formal total-time and tail-latency gates did not accept it.
- Add a developer-machine-only experimental resident Mirai/Uzu runtime card and dedicated cache scanner for the exact [`trymirai/Qwen3.6-27B-M`](https://huggingface.co/trymirai/Qwen3.6-27B-M) package—not Qwen3.8 Flash. Its exact hardened executable is installed on the qualification host but is not bundled or published, so a fresh public clone leaves this route unavailable. Its Mirai-M 4-bit target, bundled DFlash draft, and Weaver proposal tree are one fixed runtime-managed speculative route rather than an AR/DFlash tuning sweep. Weights remain a separate Mirai-cache download and are not bundled; every payload must match its pinned SHA-256 rather than merely carrying a completion receipt. Uzu's approximately 105 output tok/s vendor result came from an M5 Max with 128 GB unified memory, is labelled upstream evidence, and cannot select a route on this Mac.
- Replace the previous discovery-only Uzu route with source-pinned hardened build `0.5.23-llm-launcher.2`: upstream commit `115609b6ef7ce5a94fc761bf395780f032b09f9b`, patch SHA-256 `6caceb71adad8a609dec32e2c6eaf5bd72f0b7240564eeb9ead5c67bc53ab124`, and binary SHA-256 `d90089131806aeb7a388058bb3f5f5e386aa40847ad24910a574ebf82a8c438e`. The build includes the decode-memory hotfix, transactional rollback for rejected context overflows, and truthful cancellation reporting, and is ad-hoc signed only, not Developer ID signed or notarized. Its loopback server consumes an owner-only one-use API key before model load, authenticates the raw listener, and remains inside the launcher's outbound-denied sandbox and 36 GiB process ceiling. Initial compatibility is built-in Chat with **Model default** reasoning; Pi/OpenCode await streamed tool qualification, and Codex remains unavailable without a Responses API.
- Enforce mandatory native context and output ceilings in Uzu, including an authoritative final reservation against the live cached-prefix sequence immediately before generation. Bind admission to separate exact-context version-3 16K, 32K, 64K, and 128K receipts covering the source, patch, binary, authentication, sandbox, native limits, model, and measured settings; deliberately invalidate older version-1 and version-2 Uzu receipts. Qualification must actually exercise the tier's long prompt schedule rather than accepting a short prompt under a large declared limit: at 64K and 128K the tool-ingest and steady-turn probes require authoritative usage at or above 90% of the selected context. The 64K/128K admission estimate includes full BF16 target/draft KV plus an extra long-context prefill reserve and must retain a 2 GiB margin below the independent 36 GiB live process ceiling. Before 128K can even qualify, a fresh matching 64K receipt must show that its measured process-group peak plus the estimated 64K-to-128K growth and the 2 GiB margin remain strictly below that ceiling. Qualification uses only packaged sampling and verifies reasoning, final-answer completion, authoritative usage, arithmetic correctness, at least 15 generation tok/s, whole-system headroom, owned-process footprint, and clean unload. Uzu's current BF16 sparse KV state is reported separately from its 4-bit weights; unsupported Q8/Q4 cache controls are not invented.
- Add an experimental receipt-bound llama.cpp b10740 SSD-PLE route for the exact pinned AtomicChat Qwen3.8 Flash-Next AD-3.84 28-shard GGUF. The route is fixed to 8K, one lane, f16 KV, Jinja, runtime-controlled reasoning, and no speculation; only its isolated PLE table is described as SSD-mapped. It supports Pi, OpenCode, and Chat, not Codex, and remains **Not measured on this Mac** until its local qualification succeeds.
- Gate that route on exact runtime and current-process model SHA verification, the exact 44 GiB (`45056` MiB) Metal limit, at least 4 GiB of macOS headroom, and Whallm isolation. Its single-route qualification saves nothing unless all four generated agentic reasoning-and-answer probes clear 15 generation tok/s plus minimum-token, correctness, Jinja-tool, memory, continuous-isolation, and clean-unload checks. Ordinary launches revalidate the receipt and require current headroom for the measured process-group peak plus the 4 GiB macOS reserve; Whallm is checked before process creation and throughout every route. The private llama.cpp bearer is passed through an owner-only per-run key file rather than process arguments and is removed on cleanup. Probes measure at most 512 output tokens, so longer configured responses remain explicitly unmeasured and are bound separately in the receipt; qualification is not a cross-engine or fastest-engine claim.
- Model Library, Calibration, and benchmark receipts now report host support separately from performance evidence: **Supported on this host**, **Experimental on this host**, or **Unavailable on this host** versus **Verified on this Mac**, **Upstream measured**, or **Not measured on this Mac**. Only an exact matching local benchmark is eligible for automatic selection; upstream oMLX DFlash 2 and Whallm figures remain reference-only.
- Flash-Next Calibration can now show one installed Qwen3.8-27B DFlash 2 route as an explicit different-model alternative after fresh target/draft, runtime, visible-contract, and memory validation; it never changes the selected model automatically. A real 8,224-token qualification showed that a 44 GiB Metal limit fails oMLX's 95% prefill guard, so the estimator now reserves 1 GiB of transient workspace and requires 45 GiB for that long-context contract.
- Whallm now works through the ordinary built-in Chat and Codex private relays instead of failing after launch; SwiftLM and Mference receive the same complete relay admission. Selecting a model with a smaller context window reconciles Max response automatically while reserving room for instructions and history, and every optional runtime route is restored across refreshes. Chat no longer presents unstable TPS from tiny replies, labels those samples as too short, and stopping a Whallm session makes clear that its shared server and loaded model remain untouched.
- Runtime Manager can now open an installed LM Studio, MTPLX, or Whallm app from the hub with one explicit button press and no confirmation checkbox. The controller revalidates the exact supported app bundle identifier and executable immediately before asking macOS to open it; inspection still starts nothing, missing or substituted bundles fail closed, and the launcher never claims that merely opening an app loaded a model. Whallm's handoff tells the user to start its pinned Qwen server and then Rescan. Optional runtime cards also use distinct engine marks instead of rendering every SSD runtime as MTPLX.
- Add an experimental Whallm route for the pinned full-512-expert Qwen3.8 Flash-Next model. The launcher discovers it only from Whallm's live fixed loopback API, caps the visible context to its published 1K/2K/8K/16K benchmark matrix, opens an authenticated private bridge for Pi/OpenCode/Codex/Chat, and leaves Whallm's shared model process alone on Stop. The UI discloses Whallm's 64 GiB support floor, treats 48 GiB as experimental, and never cross-compares this full model with the public pruned REAP-288 artifact or the unreleased pMLX tweet route.
- Make **Highest generation TPS** the actual fallback everywhere—not only the visible UI—including older saved profiles, direct API calls, Calibration, Engine Shootout, and measurement history. Runtime Manager's static audit is refreshed to oMLX 0.6.4, LM Studio 0.4.23 Build 1, MTPLX 2.11.1, and optional SwiftLM b709; oMLX 0.6.4 is pinned to its official wheel digest and complete source dependency revisions, while every update still requires a matching local measurement before it can become the fastest route.
- Correct local servers that report normal completion after emitting exactly the configured response ceiling. Chat Completions `stop` becomes `length`, while native Responses `response.completed` becomes `response.incomplete` with `max_output_tokens`; the latter now covers Codex in both Hub Console and external Terminal, plus non-streamed Responses callers. The MTPLX Responses bridge applies the same authoritative-usage rule. Pi shows one recoverable warning to send `continue` or raise Max response instead of silently ending a reasoning-only turn. Hub Console also reconciles Pi's authoritative final `message_end` against streamed deltas, restores a missing suffix or final block, and explicitly identifies a settled reasoning-only turn. These guards stream earlier output normally and add no prompt, reasoning, or response text to persistent state.

- Hub Console now preserves its newest transcript rows when the window or status area changes size, consumes a final Pi JSON event even if the process exits before its trailing newline, and periodically reconciles Pi's authoritative streaming state so a missed settle event cannot leave the composer stuck on Queue. Pi extension confirmations, choices, inputs, and editor requests now appear as answerable inline cards instead of silently blocking the agent.
- Chat now saves before replacing or ending its launcher surface, keeps unfinished drafts and paused queues attached to the conversation rather than a temporary surface ID, and serializes history reads, saves, updates, and deletes. Failed storage keeps the current transcript and focus in place; concurrent first saves reuse one ID; transcript switches and revision actions are locked while history is changing, preventing duplicate chats, deleted-thread resurrection, and cross-wired replies.
- Chat's Stop response now asks the authenticated private relay to cancel the exact Chat surface before aborting the browser stream, so queued work is removed and the active relay connection is closed instead of silently leaving the local request running. The queue remains paused after an interrupted turn.
- Starting the next queued Chat turn now preserves an intentional scroll-up position and leaves **Latest** visible; only a reader already following the transcript is moved to the new live answer.
- Harden Mference admission to its real `.gturbo` contract: bounded regular metadata, pinned production architecture signatures, exact manifest/receipt binding, safe paths, matching file sets/sizes/hashes, and complete non-empty expert-layer payloads are now required before the route is advertised. Mference launches now send the served model ID and one of its six supported fixed context windows; SSD Calibration visibly uses and applies the largest common window instead of failing later on the generic 131,072-token default. SwiftLM admission now includes its released Qwen3-Next family; both artifact-based routes still reject Qwen3.8 Flash-Next, which now has separate Whallm-owned and exact pinned llama.cpp paths.
- Add an optional **Huge models on SSD** lane with registered SwiftLM and Mference adapters, model-family admission, native expert-routing controls, and Pi/OpenCode/Chat compatibility. Oversized-MoE Calibration compares only those two artifact-based runtimes, uses fresh cold-to-warm stages, reports generation TPS/TTFT/memory/thermal evidence, and reuses the applied result across MLX and `.gturbo` artifacts only when both carry proof of the same immutable source revision.
- Calibration no longer preserves a slower third-place current engine merely because the first two engines are inside the 3% noise threshold. It now forms an explicit leading group, keeps the current route only when that route belongs to the group, otherwise recommends the raw leader without claiming a unique winner, and labels the completed action clearly as **Apply result**. Applying the matching result is covered as a reusable handoff, so the fastest-settings action does not request the same calibration again.
- Pi now uses its supported structured RPC protocol inside Hub Console instead of a redraw-based terminal screen. The Hub restores the current Pi session transcript and renders thinking, responses, tool calls/results, queue changes, notices, and errors as distinct semantic cards; the first upward wheel, key, or scroll movement detaches live follow even inside the old near-tail threshold, redraws preserve the first visible card as an anchor, and **New output** returns to the live tail without moving the reader early. Inactive tabs show unread events from a content-free revision. The 512-event/512-KiB journal emits periodic complete live snapshots plus an authoritative final snapshot, while the browser independently enforces 512 items, 512 KiB total, and 64 KiB per item, so refresh replay cannot lose an evicted delta prefix or grow one card without bound. Send changes to Queue while Pi is responding, with explicit Clear queue and Stop response controls even on Pi builds that predate its own clear-queue RPC command. Locally waiting and in-flight prompts now appear in that queue count, Clear queue drops messages that have not reached Pi, every accepted input restarts reading immediately, and two bounded final-drain reads preserve late settlement output. Model text is rendered only through text nodes; Terminal mode remains available for Pi's full native TUI.
- Correct ANSI `CSI 3J` handling so a terminal request to clear scrollback no longer erases the visible screen.
- The audited oMLX installer now rebases every generated virtual-environment launcher before atomic promotion, repeats the full smoke suite from the final installed path, and records final-path verification in its manifest. A failed promoted copy is removed without touching the selected rollback, non-zero `--version` output can no longer masquerade as a valid runtime, and official provenance is trusted only when the final command reports the exact audited version.
- Frost now keeps its capped desktop workspace centred on wide displays, and Focused mode no longer pushes the second card in a sibling grid down by its generic section spacing. Header, dock, and dialog control-height regression checks remain in place.
- Runtime and Work surface selectors now share the same 42-pixel outer height in the focused desktop layout, removing the adjacent four-pixel baseline mismatch while keeping runtime icons and labels legible.
- Chat and Hub Console action clusters now keep their adjacent Stop/Escape/Send controls on one 34-pixel baseline in every appearance, including Frost.
- Add **Frost**, an optional polished light appearance with restrained translucent bars, Mac-style grouped surfaces, native blue controls, softer dialogs, clearer Chat reasoning/answer lanes, and consistent light treatment across launcher and management flows. Hub Console now keeps its entire workspace—not only the terminal viewport—black in every appearance.
- Cross-engine Calibration now performs the bounded engine-specific search instead of timing one arbitrary accelerated preset: LM Studio evaluates up to ten MTP depth/minimum/cutoff candidates, oMLX evaluates up to ten DFlash block/verifier/draft-precision candidates, and MTPLX still checks every verified draft depth. Plans disclose worst-case reload/request counts as **up to**, live progress names the exact candidate and TPS, and only a complete correctness/resource-gated sweep can be saved or applied.
- Applying a measured result now isolates each engine's acceleration route, so MTPLX MTP controls cannot invalidate oMLX or LM Studio history while every backend-owned setting remains validated. The exact measured ANE choice and tie-band record are replayed, the complete result is validated before atomic persistence, and result cards explain when a faster speculative candidate was rejected for failing AR output parity without presenting its TPS as trusted evidence.
- Calibration preserves completed mandatory evidence if optional LM Studio or oMLX refinement later reaches the cancellable resource-settling limit. Route starts use a disclosed 2 GiB tolerance against one fixed free-memory reference plus two stable samples, while winner/regression decisions retain the stricter 512 MiB threshold; thermal and Low Power Mode checks remain unchanged.
- Structurally complete v1 tuner receipts remain reusable after the stricter v2 evidence upgrade, while malformed or incomplete records still fail closed. Complete and cooldown-stopped sweeps replay their exact deterministic candidate sequence, and the selected row must match the stored measured mode. The performance strip now falls back to another complete exact-contract benchmark suite when the preferred suite has no result, then binds Apply to that suite's exact shootout and record IDs; damaged or legacy-unbound evidence remains reviewable but cannot present a misleading Apply action.
- Engine Calibration now reloads MTPLX at every verified MTP draft depth (D1 through the artifact maximum), correctness-gates each depth against AR, and compares the fastest valid depth with the other engines. The read-only plan includes those extra reloads/requests, live status names the active depth, completed results show the exact winning depth, and Apply fastest restores that measured depth instead of reverting to the artifact default.
- Calibration now shows every engine's measured result and generation TPS, keeps live generation TPS visible while testing, and preserves the chosen cooling mode when reopened. Saved evidence is grouped by one completed shootout instead of mixing newer routes from another run, and a route that starts with more free memory than the shared reference remains usable. Apply no longer reopens Calibration in those cases; worse memory, thermal drift, power-mode changes, and cooldown timeouts still fail closed.
- Keep an explicit **Retest engines** action after Calibration finds a saved result, while making **Use result** the primary action.
- Calibration now turns completed engine measurements into a usable result even when backends differ by one terminal token or choose different valid greedy wording. Exact parity remains required inside each engine before an accelerator can win; cross-engine results instead require the same model/input contract and tightly bounded token-count drift.
- The final ranking now honours the resource-settling gate that every route already passed, instead of rejecting the matrix again with a stricter pairwise memory check. Existing matching measurements become usable without rerunning them.
- Calibration has one clear Result area in Focused mode, never presents “completed” and “measurement needed” together, and disables the test button while a completed result is being reloaded. Its performance drop-up is reduced to fastest engine, test/review, and checked launch choices; the other ranking goals remain in Calibration.
- A controller that is still running older Python source now blocks new launches, measurements, downloads, runtime changes, and Session Set opens immediately with a restart message instead of executing stale routing code.
- Reversible local actions no longer ask for a redundant checkbox: Route Check, Calibration, ANE measurement, runtime comparison, and ordinary Session Set opening now start from their clearly labelled action button. Extra confirmation remains for downloads, installs, large-file creation, destructive deletion, experimental routes, and memory-risk overrides.
- Cooling is now a user-owned safety setting. Apply fastest preserves it, Calibration defaults to Automatic, and maximum fans requires an explicit loud-mode selection.
- Calibration evidence includes the selected cooling policy, preventing maximum-fan results from being applied to normal-cooling routes.
- LM Studio MLX models now load through the canonical identifier in its local model index, including quantised aliases such as `model@6bit`; stale catalog failures now give an actionable Rescan message.

## 1.66.0-alpha.2 - 2026-08-24

First public alpha.

### Included

- Unified model routing across oMLX, LM Studio, and MTPLX.
- Pi, OpenCode, Codex, and built-in streaming Chat work surfaces.
- Capability-aware model library, route validation, local profiles, Session Sets, and warm-route attachment.
- Chat thinking separation, TPS, message queuing, history, search, branching, drafts, and interrupted-turn recovery.
- Calibration, benchmark evidence, fastest-safe settings, engine shootouts, DFlash 2 setup, and guarded ANE tuning.
- Frost, Graphite, Daylight, Ember, and Midnight appearances with Focused and Detailed information levels.
- Authenticated loopback bridges and launcher-owned process cleanup.

### Alpha limitations

- macOS-focused and not yet packaged, signed, or notarized.
- FreeToken support is retained behind an off-by-default UI feature flag.
- Runtime compatibility and saved-data formats may change before a stable release.
