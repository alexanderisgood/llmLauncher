# Changelog

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
