# Hub source cleanup — 7 September 2026

This pass targets measured repeat work and the live reasoning-history defect. It does not claim that every part of the large controller has been refactored or that browser improvements increase model decode throughput.

## Changes

- `pi_timeline.js` reuses normalized immutable items and their cached UTF-8 sizes. Idle envelopes return the existing state. Streaming updates copy the item list and normalize only changed items, while retaining existing transcript limits and reset/stale-event behavior.
- `pi_timeline_view.js` owns transcript card creation and keyed updates. Appending to a live response changes its body in place, preserving the card, surrounding history, focus, disclosures and scroll anchors. The copy-button state no longer concatenates the entire transcript during rendering.
- `polling.js` owns status scheduling and coalesces manual/background requests. Visible active work still polls every 1.8 seconds. Closed inactive auxiliary tools poll every 30 seconds; opening their dialogs requests current status immediately. Work started in another window may therefore take up to approximately 30 seconds to appear in a closed auxiliary view. Hidden pages slow their status and transcript polling and refresh on returning to the foreground.
- `pi_context_recovery.js` separates reasoning-loop recognition and context repair from workflow orchestration. It removes synthetic repair-text echoes and prevents stale MTPLX reasoning-cache restoration. See [the investigation](QWOPUS_REASONING_FEEDBACK.md).

The raw Python console buffer was also profiled: 100,000 append/eviction operations with 512-byte chunks took approximately 21 ms on this machine. That result did not justify replacing it.

## Background engine polling

The health monitor previously collected the full Hub activity report every three seconds even when automatic unloading was off. For MTPLX this repeated three requests: relay status, native flight telemetry and native prefill snapshot. None of those values were used with the idle policy disabled.

The monitor now skips that collection when automatic unloading is off. When it is on, it reads the relay's request coverage and idle clock without asking the engine for token counters. Visible Hub status still collects fresh native telemetry; process checks and the model-health endpoint remain active in both modes.

A deterministic 20-cycle monitor test confirms zero background activity probes with the idle policy off, 20 relay-only probes with it on, and 20 model-health checks in both cases. This removes up to 60 redundant local requests per minute for MTPLX with automatic unloading off, or 40 with it on; real rates depend on response latency. Six focused lifecycle, idle-policy and status tests passed, including expired-idle shutdown, relay loss and delayed model-health responses. This reduces controller/runtime management work; it is not a measured decode-speed increase.

## Session status ownership

Activity collection now captures one plan/run ID, private relay endpoint/key and lifecycle phase. It uses that endpoint throughout the request, then checks ownership after relay/native I/O and again while assembling each public snapshot. If a session stops or is replaced, the response includes current session state and an empty, non-authoritative activity report until the next poll, rather than old TPS, context or idle evidence. Network reads remain outside the controller state lock; idle preferences are applied from current state without discarding valid telemetry for a preference-only change.

Six deterministic tests cover blocked relay and native reads, the final snapshot boundary, stale targets, relay replacement with the same plan, stopping, and stable-owner telemetry. They run without sockets or model weights. Fifteen existing status, idle/lifecycle and MTPLX/oMLX prefill tests also pass; all six Whallm telemetry tests remain passing.

## Compaction in smaller Hub windows

Pi's default 16,384-token reserve and 20,000-token recent-history target were inherited by the 16K Whallm route. The reserve left a zero-token admission threshold, while retention could exceed the entire selected window. The existing process-local settings adapter now bounds both values to one quarter of the selected context, while retaining smaller user preferences. At 16K, that gives a 4K reserve, 4K recent-history target and 12K compaction threshold. The original global/project settings files are untouched.

Large-window defaults remain intact where they fit, including oMLX's 8K recent-history cap. The separate model-name-based 64K trigger was removed on 8 September so the selected window controls normal compaction. An installed-Pi fixture using Whallm's 16K/4K medium-thinking contract accepts 8K reported usage without compaction, compacts once at 13K, and completes two further 3K turns without repeating it. All seven installed-Pi overflow/memory-recovery fixtures passed, along with the settings and loop-compaction checks. These use a local synthetic responder and load no model weights.

## Whallm Hub telemetry

`whallm_telemetry.py` reads the owned runtime's bounded status response and publishes numeric measurements only. Active request counters, native completion count, token counts and elapsed time connect measurements to the relay. The server and runtime reset their counters at different points; the adapter handles that gap without showing the previous response's speed during a new prompt.

Prompt throughput excludes `prompt_cache_reused_tokens`. Whallm 1.1.4 supplies that measurement when the first token arrives, so the Hub shows its prefill stopwatch until then. Decode uses `decode_end_to_end_tokens_per_second`, including cache evaluation, rather than the faster model-step-only measurement. Polling occurs only for a running owned Whallm session's visible telemetry path; background idle checks still avoid native telemetry. Six focused adapter tests, 11 existing prefill/monitor tests and browser status tests passed without loading weights.

## Reproducible browser-state benchmark

`node tools/profile_hub.js [path-to-timeline-module]` uses 400 synthetic transcript items and 200 updates per scenario, with no model, browser, network, or user files. The encoder is instrumented to count allocated encoded bytes. Timings are one local run, not a full UI benchmark.

| Scenario | Before | After | Encoded bytes before | After |
| --- | ---: | ---: | ---: | ---: |
| 200 idle updates | 458.08 ms | 0.18 ms | 286,312,000 | 0 |
| 200 streaming updates | 444.11 ms | 6.57 ms | 286,955,800 | 679,400 |

A deterministic one-minute poll simulation drops status requests from 272 to 48 (about 82%) when the main run is visible and auxiliary tools are idle. It excludes transcript requests and user actions. Coalescing additionally prevents slow requests from accumulating overlapping copies.

## Verification

- 301 controller tests: passed, 10 existing skips.
- All 44 JavaScript test files: passed, with existing opt-in live tests skipped. Focused module and reasoning tests also rerun after final edits.
- Installed Pi in the real Hub browser, isolated local fixture: live and completed card identity, long streaming responses, scroll following/reading, queued input, reload after journal overflow, abort/recovery and saved transcript checks passed. No model weights loaded by this test.
- Installed Pi recovery integration: passes the actual captured provider request and repaired session header checks.
- Native MTPLX tokenizer/cache integration: two tests passed; no model weights loaded.
- Qwen3.8 6-bit native encoder test separately checks that prior reasoning and its prompt prefix survive a follow-up, with preservation disabled as a negative control.

The backend remains large. Future extractions should use component boundaries and measured work, with behavior checks at their interfaces, rather than moving large blocks behind compatibility aliases or adding speculative caches.

## 12 September: DFlash prompt preparation

The oMLX 0.6.4 session adapter now sends its already-counted token IDs to native
`stream_generate`, instead of re-rendering and re-encoding the messages through
`stream_chat`. The text-only/fallback guard runs first. Native generation still
owns context admission, thinking-budget processing, sampling and cancellation.
Server context validation and preflight token counting remain separate; this
removes one redundant pass, not all prompt preparation.

`tests/test_omlx_prompt_reuse.py` executes the installed native chat-dispatch and
tokenizer-dispatch methods without importing MLX or loading weights. It compares
the original path with the adapter for tools, Unicode, partial assistant messages,
thinking budgets and sampling settings. Token IDs and generation arguments match;
the adapter plus generation path renders and encodes once. The existing adapter
test also verifies output clamping and explicit native-stream cleanup on abort.

A CPU-only measurement using the installed uncensored 6-bit model's tokenizer,
with thinking enabled and a synthetic 48,651-token prompt, took median 72.6 ms for
two render/encode passes and 36.1 ms for one pass plus the native token-list copy
(five trials each). The saving is about 36 ms per reply at that prompt size, not
evidence of higher GPU prefill or decode TPS. Larger runtime costs still need
measurement before choosing the next optimization.

The preview observer was also measured with 1,000 synthetic updates at a simulated
20 updates/second. Plain thinking updates averaged 0.018 ms; a large active code
preview averaged 0.208 ms (99th percentile 1.215 ms), including local file writes.
These measurements do not justify adding a background writer or establish a GPU
throughput bottleneck. They did expose a rendering defect: discarding a long tool
call's opening marker stopped its preview. The bounded preview now retains the
call header plus the newest output, stays within 256,000 characters, displays at
most 60,000 characters, and clears when the call closes. Preview text is never
used for tool execution.

## 12 September: avoid full-prompt snapshot concatenation

The pinned DFlash feature store concatenated generated features and then the
entire dense prompt before handing the result to native snapshot trimming. The
launcher now supplies native `TargetHiddenChunks` containing the existing arrays.
Native construction still chooses sink, tail, sidecar and full-attention coverage;
it joins only the ranges it needs. Sampling, generated tokens, KV ownership and
memory ceilings are unchanged. The patch is limited to oMLX 0.6.4 with
dflash-mlx 0.1.10+omlx.7 and included in controller source freshness checks.

`tests/test_dflash_snapshot.py` compares the actual installed snapshot builder
and cache restoration for dense and sparse features, sink/tail windows, sidecar
coverage, full attention, zero-window retention and a truncated last block.
Saved feature values match exactly; missing full-context coverage still fails.
The existing memory estimator matches native retained bytes for these cases.

A native, model-free allocation check used 41,394 prompt rows plus 3,864 generated
rows, 128 feature columns and FP16 arrays. Extra peak allocation during feature
handoff plus native sidecar trimming was 12,599,296 bytes before and 1,523,712 bytes
after (about 88% lower). This small synthetic case verifies the allocation
reduction, not a whole-model peak or decode-TPS improvement. No heavy model
benchmark was run for this change.

## 12 September: distinguish engine readiness from loaded weights

The native protected activity endpoint returns an empty model list before oMLX
loads weights on demand. This was verified on the idle local server with zero
active and waiting native requests. The controller used to label it `unmatched`.
It now reports `unloaded` only when both native counters are valid zeroes and the
relay has no active or queued work. An exact model with `is_loading: true` reports
`loading`. Other missing/ambiguous identities retain the strict mismatch behavior;
no token speeds are inferred from these startup states. The launch estimate's
reuse label and cache-observatory text now describe a ready engine rather than
claiming its weights are loaded.

The startup-state, session-identity race and authenticated telemetry regressions
pass (10 tests), as does the launch-memory UI check.

## 12 September: shared workspace rendering

The Chat and Hub renderers both updated the shared launch form, dock and heading.
On each active-Hub status poll the Chat renderer exposed the form and selected
the home heading, then the Hub renderer undid those changes. `updateWorkspaceChrome`
now derives those shared elements from the visible workspaces and writes only
actual changes. A regression executes both production renderers for 200 stable
Hub refreshes and observes zero mutations to those shared elements. Home and Chat
transitions, retained postmortem output, Hub input and drafts pass their checks.
This is a DOM-work reduction; Safari RAM or model TPS improvements are unmeasured.

Safari's separate accessibility omission after Home → Return to Pi remains
unresolved. Full transcript rendering is restored: experiments changing focus,
ancestor `:has()` selectors, `display: contents`, the workspace's accessible name,
and rendering only 64 or eight recent events did not restore the live page's AX
subtree. All those experiments were reverted. A disposable fixture exposed 64
synthetic cards but omitted transcript children at 512; its other controls stayed
accessible, unlike the full app. That does not prove the live app's root cause.
The fixture tab and server were closed; the running model was not restarted.

## 12 September: collapsed transcript bodies

The Pi timeline now clears DOM body text when a thinking/tool disclosure closes
and restores it from the current journal item when reopened. Updates received
while closed stay in the journal without repopulating hidden text. Live thinking
and active tools retain their expanded defaults. This complements the existing
lazy screenshot loading and source release on collapse.

The isolated Chromium fixture verified 100 long collapsed results had zero DOM
body characters, reopening retained exact text, closed updates reopened with the
latest result, screenshot lifecycle remained correct, and live thinking remained
visible. Timeline reconciliation and launch-memory checks also passed. Safari
could not be inspected because the Mac was locked; no measured Safari RAM saving
is claimed. Its open tab needs a refresh to load this frontend change. No model
restart or inference request was made.

## 12 September: incremental DFlash feature storage

`dflash_snapshot.install_chunked_prefill_features` keeps fresh and partial-hit
prompt features in native `TargetHiddenChunks` rather than allocating a dense
full-prompt buffer up front. Cached spans are clipped to the reused prefix, zero
gaps are scalar broadcast views, and new projected features replace only their
written spans. Exact-hit hydration retains the native path. Native full-context
coverage checks, sampling, thinking, KV policy, and memory ceilings are unchanged.
The adapter is fenced to oMLX 0.6.4 / dflash-mlx 0.1.10+omlx.7.

Seven prefill fixtures and three existing snapshot fixtures passed with the
installed MLX runtime, using small arrays only. They compare complete feature
values (including zero gaps), dtype/batch broadcasting, windowed/full draft
context selection, frozen snapshots, and combined generation-snapshot trimming.
Fresh-prefill checks compare FP16 and BF16 projections, intermediate prefix views,
draft context selection, and the transition into generation. The first cold chunk
(2,048 processed tokens out of 42,000, width 128) used 11,288,582 bytes of extra
peak allocation before versus 524,294 after. This avoids allocating unprocessed
feature rows early; it does not eliminate retained features for a completed prompt.
The 42,000-token / 128-feature-width partial-hit fixture measured 10,764,290 bytes
of extra peak allocation before versus 524,290 after. This measures the feature
buffer step, not whole-model peak memory or decode speed. All 18 memory-headroom
checks passed with the installed native runtime.

The adapter is wired into runtime startup. The controller update is active, but
there is no live model route: status showed the previous route had been explicitly
closed before activation. The next oMLX engine start will install the adapter.
No model request was submitted for these checks; full-model peak/TPS verification
remains pending.

## 12 September: conversation-bound Hub drafts

Pi status and console reads now expose an opaque `conversationId` derived from
the project and Pi's reported session file. Hub drafts use that identity once
available, so a new engine/run ID can reopen the same tab-local draft. Terminal
consoles retain per-run/per-surface keys. `/new` and `/resume` switch draft slots;
neither recovery nor migration submits a message. Late steering acknowledgements
must still belong to the original conversation before updating its UI or clearing
its draft.

Only newly typed, unbound text can migrate when this console first reports its
identity. Historical run-key drafts remain saved but cannot be assigned to a
conversation by guesswork. Existing legacy drafts stay under their original keys
and can be moved into an empty composer through Saved drafts; new identified
sessions recover their drafts automatically. Browser storage remains
tab-local and bounded, with no server-side draft text storage.

The production-function draft fixture passed refresh/restart recovery, distinct
conversation isolation, session switches within one console, legacy isolation,
and late steering acknowledgements with identical draft text. Console input/tab
fixtures and ten Python identity/queue/steering checks passed. The controller is
updated; the Safari tab needs a refresh to load the new frontend.

## 12 September: legacy draft recovery and idle activation

Saved drafts appears inside the existing console actions menu only when another
draft exists in this browser tab. Its picker renders bounded, literal previews;
explicit selection moves the complete stored message to an empty composer, never
to an agent input queue. Occupied composers are preserved. The isolated browser
fixture checked old run-key recovery, exact long-text restoration, HTML-like text,
refresh persistence, and occupied-composer refusal. Its dialog was also visually
reviewed. Conversation revision counters prevent delayed same-process status
responses from rewinding the conversation identity when terminal byte counts have
not changed.

The attempted same-session activation aborted before mutation because the live
route had changed to `idle` / `Stopped. The launcher-owned model route was closed.`
The controller alone was then restarted with fresh checks requiring no run,
consoles, active requests, or queued requests. Bootstrap confirmed
`controllerSourceCurrent: true`; status remained idle. No model was started and
no prompt was sent. Safari was subsequently found unlocked but in use on another
page, so its tabs were left alone. The old Hub draft remains in that tab's storage;
live recovery of it awaits the tab refresh and an appropriate open console.

## 12 September: idle Pi polling

The semantic Pi reader now backs off to 750 ms after four unchanged reads with
explicit idle stream/compaction flags and no local, queued, or abort work. Normal
terminal polling and unknown state keep their existing cadence. Active streams,
compaction, input, starting/stopping, and final output draining stay at 120 ms;
remaining semantic history is now drained at 0 ms even when terminal bytes have
already been skipped.

Immediate user-action reads replace a pending idle timer without overlapping an
in-flight request. Routine workspace status renders do not reset idle backoff.
The deterministic scheduler fixture measured 83 reads over the first settled
minute versus the previous 500. Production reader/scheduler checks verified
compaction wake, semantic backlog, timer replacement, and no overlapping reads;
existing input, draft, queue, tab, and postmortem fixtures passed. This is a
request-count reduction, not a measured Safari RAM or inference-TPS improvement.
The frontend change needs a page refresh; no controller/model restart is needed.

## 12 September: bounded diagnostic log reads

Log previews, download/update failure details, and ANE evidence extraction now
share `log_tail.read_log_tail`. Previously these paths decoded the entire log
before retaining only the final 2,000, 40,000, or 2,000,000 characters. Reads now
cap at four bytes per requested character plus a UTF-8 boundary margin, retaining
the existing replacement decoding, universal newline conversion, output limits,
and missing-file behavior. Full logs on disk are untouched. The existing bounded
Uzu and LM Studio readers keep their separate parsing behavior.

Four regression checks passed, covering Unicode and malformed bytes, CRLF/CR,
all consumers, missing/unreadable files, and a sparse 256 MiB log whose preview
used less than 3 MiB of temporary Python allocation. This bounds controller log
read overhead; it is not a measured Safari RAM or model throughput improvement.
The controller was restarted after fresh checks confirmed an idle route with no
consoles or requests. Bootstrap reports current source; the model remains stopped
and no prompts were sent.

## 12 September: hidden Hub screenshot lifecycle

Expanded screenshot results previously retained their image sources when the
whole Hub was hidden by Home navigation. The timeline view now suspends image
sources while hidden and restores only expanded results when it becomes visible.
Result text, card identity, disclosure state, and transcript state are retained.
Late results and queued disclosure events respect the hidden state. Resets also
release image sources before clearing the timeline, and detached cards cannot
reload images through delayed toggle events.

The isolated browser fixture passed hide/show, hidden updates, reset, detached
events, live thinking visibility, and existing screenshot rendering checks.
Production workspace, input, and postmortem checks passed. This is a verified
image-resource lifecycle improvement; Safari's actual process RAM saving remains
unmeasured. It is frontend-only and loads on page refresh.
The installed-Pi browser integration fixture also passed streaming/scroll,
queueing, reload after journal overflow, Stop/recovery, and retained stopped
transcripts using generated responses. No model was loaded.

## 12 September: streamed timeline text sanitization

Profiling 300 small thinking deltas after a 64,000-character block identified
`safe_agent_timeline_text` as the dominant controller timeline cost: it repeatedly
walked accumulated text with Python `ord`/list append calls. The sanitizer now
uses one compiled control-character pattern, invoking Python replacement only
for actual controls. Normal text keeps the same Unicode value; CRLF/CR handling,
visible ESC, replacement characters, and UTF-8 byte truncation are unchanged.

Three unprofiled paired runs of the production append path measured a median
1.232 seconds before and 0.105 seconds after (300 updates, identical 65,508 retained
text/title bytes). This is about 92% less CPU time for that synthetic long-output
workload, not a measured model decode speedup. New checks cover all C0/C1 controls,
multibyte boundaries, 600 streaming updates, journal overflow/replay, and retained
original requests. Nine existing live-feature/history/status unit checks also
passed; the installed-Pi history integration check was not enabled in this run.
The controller was activated after fresh idle/no-request checks and reports
current source. No model was started or prompt submitted.

## 12 September: complete response buffer ownership

The Chat Completions relay previously accumulated a non-stream response, copied
it to immutable bytes, copied those bytes into the output-limit guard, then copied
the guard buffer again before parsing. `finish_completion` now applies the same
correction directly to the already bounded response buffer. Unchanged payloads
reuse that buffer; corrected payloads are serialized once, and the handler drops
its obsolete input reference. Chunked/streamed guard behavior, the 128 MiB body
limit, error normalization, and response-header rules remain unchanged.

An 8 MiB synthetic completion reduced extra traced allocation from about 24 to
16 MiB when unchanged, and 34 to 26 MiB when corrected. These measurements exclude
the original response buffer and are not whole-process RSS or model TPS results.
Two new checks cover body identity, malformed JSON/Unicode, usage and finish-reason
variants, multiple choices, chunked equivalence, and allocation reduction. Existing
output-limit and four memory-error checks passed. A real local HTTP relay fixture
also delivered both corrected and unchanged responses with their expected text,
usage, and headers. No model was loaded.
The idle controller was restarted and reports current source. There is no live
model route; the next route start will use the updated proxy.

## 12 September: bounded streaming metrics lines

Reproduced a telemetry failure: an SSE content line larger than the 1 MiB metrics
allowance followed by a usage event in the same upstream read lost both events,
leaving prompt/completion counts unknown. The parser previously discarded through
the last newline of an oversized accumulated buffer. It now bounds each line,
skips the remainder of an oversized line through its own newline, and resumes on
the next line. A suffix of rejected content cannot masquerade as a new event.
Normal batches use an offset into the incoming chunk instead of repeatedly
copying the unprocessed remainder. The payload relay itself is unchanged.

Five framing checks passed, covering the reproduced failure with 16 KiB reads,
fragmented UTF-8 and CRLF, final unterminated lines, request IDs, large batches of
valid events, and non-stream limits. Six MTPLX telemetry checks, runtime-usage and
LM Studio stats checks, and the real local HTTP delivery fixture also passed.
In three synthetic runs of 500 batches of 330 small SSE events (16,830 bytes per
batch), median parser time fell from 0.396 to 0.258 seconds, about 35%. This is
parser CPU time, not model decode speed. No inference was run.
The controller is current after an idle-only restart. The next model route will
start the updated proxy; no active session was interrupted.

## 12 September: Chat Completions guard recovery after oversized events

A tool event exceeding the 256 KiB guard allowance across multiple reads
previously disabled the guard for the entire remaining stream. A reproduced
event of roughly 288 KiB then hid correction of a later false `stop` at the
output ceiling. The guard now passes the oversized event through unchanged and
resumes inspection after its SSE separator. Only three boundary bytes remain
buffered while passing through; split LF/CRLF separators are recognized without
mistaking a JSON-looking suffix for a fresh event. Subsequent memory-refusal
events remain eligible for the existing narrowly scoped compaction marker.

Four new regression checks passed, covering real-sized events, repeated events,
fragmentation down to single bytes, both newline forms, unchanged below-limit
results, subsequent memory errors, and unfinished streams. Existing memory-error,
non-stream allocation, and output-limit checks passed. The local HTTP fixture now
also sends a large synthetic tool event and verifies unchanged tool bytes followed
by the corrected limit signal. No model request was made. This fixes oversized
nonterminal events; the separate bounded terminal-tail overflow policy remains
unchanged.
The controller reports current source after an idle-only restart. The next
model route will use the updated guard; no existing session was interrupted.

## 12 September: Responses guard recovery and shared SSE framing

The Responses guard had the same permanent-disable behavior after an oversized
event. It now forwards that event with a three-byte separator tail and resumes
inspection on subsequent events. Explicit usage still determines output-limit
correction. If oversized output could not be inspected, the guard no longer
infers a reasoning-only failure from incomplete evidence. Ordinary fully inspected
reasoning-only detection stays enabled. Terminal-tail and non-stream limits remain
unchanged.

Both guards now share byte-boundary parsing and oversized-prefix forwarding in
`sse_framing.py`. The controller source fingerprint covers this helper and
`codex_proxy.py`, which was previously missing from that dependency list.
Nine Responses reliability checks, four Chat oversized-event checks, four memory
error checks, streamed/JSON completion correction, and controller freshness checks
passed. The local Responses HTTP fixture also preserved usage and terminal
correction. A separate run using the real 16 MiB Responses allowance forwarded
16,810,040 content bytes intact and corrected the subsequent terminal event in
2.716 seconds; no model was loaded. The incremental scanning change below
addresses that parse cost.
The idle controller was restarted and reports current source. No model route was
opened; the next launch will use these proxy changes.

## 12 September: incremental SSE separator scanning

The guards previously searched every accumulated byte for a separator on each
upstream read. A fragmented 16 MiB event therefore caused quadratic search work.
The shared `EventScanner` remembers the already searched prefix, rechecking only
the final three bytes plus new input. Popping an event, forwarding an oversized
prefix, and finishing reset its search position appropriately. Byte limits and
protocol interpretation are unchanged.

Three paired runs through the production Responses guard, with 16,810,040 content
bytes supplied in 16 KiB reads, measured a median 2.499 seconds with full rescans
and 0.01277 seconds with incremental scans. Output hashes matched, all content
bytes were forwarded, and terminal limit correction remained intact. This is a
large-event parser measurement, not a model decode benchmark.

The scanner regression measures searched bytes directly to enforce linear work,
and checks fragmented opaque streams against the original full scanner. Twenty-four
checks passed across framing, Responses reliability, Chat oversized events,
memory errors, complete-response allocation, and both local HTTP protocol fixtures.
No model was loaded or prompt submitted.
The idle controller is current after restart; the next route launch will use the
incremental scanner.

## Live recovery

Controller source freshness was verified after restart. Pi reopened the same saved Mario conversation and detected the synthetic echoes in its unfinished turn. Native compaction finished at 19:31:20 UTC, with 56,009 input tokens and 1,219 output tokens. The first resumed task request contained 9,015 prompt tokens, versus 81,299 in the last pre-pause request. It emitted fresh reasoning, with an observed native decode sample of 27.48 tok/s (whole-decode average 24.79 tok/s at that point). A subsequent real bash invocation completed and no new saved assistant message contained the synthetic repair sentence. These are live observations, not a matched speed benchmark or proof of long-task success. The route remained xhigh, 128K, MTP depth 2, and the GPU ceiling read back as 40,960 MiB.

The live Hub was also checked in a background browser: the compact header, prefill stopwatch/speed, compaction state and conversation loaded without browser errors. Safari was in active use on another page, so its existing Hub tab may need a refresh to load the new JavaScript.

## Reasoning preservation

The cleanup is not a global removal of thinking. Qwen3.8 6-bit uses native preserve mode; its installed encoder regression confirms earlier thinking and its prompt prefix survive subsequent user messages. [Qwen's model card](https://huggingface.co/Qwen/Qwen3.8-27B#disable-preserved-thinking) recommends this behavior, and [Benjamin Marie reports](https://x.com/bnjmn_marie/status/2096638179277488191) worse accuracy and 2.9 times as many output tokens without it in his coding evaluation. That ratio is not a universal task saving.

Qwopus uses its publisher's different, scoped template: current-round assistant/tool thinking survives, while earlier completed rounds' thinking is dropped. Format verification does not establish that this policy is optimal for coding quality. A controlled Qwopus comparison with valid reasoning retained is needed before claiming it is better than full preservation. This latest failure specifically involved synthetic repair-text echoes and repetitive source reads within one user turn, which scoped mode did not prevent.


## 12 September: editable DFlash fallback cache

Restored the cache selector under every DFlash verifier, labelled explicitly as
fallback KV, with the actual DFlash precision displayed separately. The message
now distinguishes DDTree's quantized-cache rejection from Adaptive/Fixed DFlash's
integration limitation. The installed dflash-mlx `SpeculativeSession.open` resets
`snap_prefix_len` to zero whenever `quantize_kv_cache` is enabled; exposing Q8 as
an effective DFlash setting would therefore sacrifice conversation-prefix reuse.
The installed oMLX `_build_runtime_context` also does not pass that option.
Supporting effective DFlash Q8 with prefix reuse remains unfinished backend work.

Verified the editable selection and preserved value across all three verifier
strategies in a background browser, plus the KV UI regression and JS syntax check.
No model was launched, stopped, or reconfigured for this verification.


## 12 September: actual DFlash Q4/Q6/Q8 KV and prefix reuse

The preceding fallback-only limitation is now replaced for the pinned oMLX
0.6.4 / dflash-mlx 0.1.10+omlx.7 session adapter. Adaptive and Fixed DFlash pass
the selected KV precision to native Qwen cache creation and generation. DDTree
plus quantized KV is rejected explicitly in the UI and launch builder.

The process-local adapter preserves packed weights, scales, biases, bit width
and group size through RAM snapshots, sidecar slicing, and native SSD storage.
Snapshot identities include the quantization format, preventing reuse across
precisions. Native token-prefix and hidden-feature coverage checks remain.
Q6 allocation also needed fixing: a 256D head packs into 48 uint32 words,
whereas the installed allocation incorrectly used 256 // (32 // 6) = 51.
Installed package files are unchanged; the adapter refuses other runtime versions.

Native checks passed at Q4, Q6 and Q8: snapshot immutability across append,
trim and growth; exact packed-state restoration; native quantized attention;
SSD round trips and sidecar restoration; mismatched prefix/precision rejection;
small randomly initialized native Qwen forward passes after restore; runtime
configuration, generation flag propagation, and precision-specific cache keys.
These use tiny arrays/models, not the user's 27B weights. They do not establish
long-task quality or decode speed. Fifteen native checks, ten cache-policy checks,
the launch-builder regression, UI checks and memory-headroom regressions passed.

Full 128K attention-KV estimates for the 27B geometry are 8 GiB at full precision,
4.25 GiB Q8, 3.25 GiB Q6 and 2.25 GiB Q4, including scale/bias metadata. Model,
draft, recurrent state, hidden features and temporary workspace remain separate.
Calibration still excludes comparisons that equate DFlash affine KV with ordinary
oMLX TurboQuant: identical bit width does not make them numerically equivalent.

## 12 September: quantized prefill memory pressure

The resumed 6-bit model with Q8 KV was successfully reusing prefixes until large
prefill temporaries pushed process memory over the hard limit. oMLX then unloaded
the model after the request drained, losing the RAM prefix and forcing the next
turn to process roughly 125K tokens again. The observed unused Metal pool reached
8–10 GiB; increasing the memory ceiling would not fix this repeated allocation.

Quantized DFlash prefill now caps each query chunk at 128 tokens instead of the
native 2,048-token fused-attention default. Its attention path materializes scores,
so smaller chunks bound temporary memory at long context. Pressure-reclaim tickets
are also consumed at committed PrefillProgressEvent boundaries, alongside existing
token boundaries, on the same MLX executor. Live cache state remains referenced.

The pressure-reclaim suite passed (12 checks, one optional skip), including a
prefill-only stream; five native Q8 checks passed, including the runtime chunk cap.
The user's exact Pi session and four queued follow-ups were preserved across the
controller restart. Q8 KV, 180K context and xhigh reasoning were retained.

The resumed request completed its cold prefill: 137,596 tokens in 907.7 seconds
(151.6 tokens/s), then streamed generation to the Hub. During generation, live
pressure tickets reclaimed approximately 5 GiB of unused Metal buffers and
returned process memory from hard pressure to approximately 31.1 GiB without
unloading. This validates recovery and reclamation on the user's actual workload;
the first post-restart turn was still generating at the time of this observation,
so next-turn prefix reuse was not yet measured.
