# Local verification checkpoint — 5 September 2026

This records observed results, not a claim that every runtime and agent surface
has completed end-to-end qualification. Recheck live state before starting work.

## MTPLX saving and application

Current real v5 result: `72fc9535-597f-43fe-9635-dfa24faf37c8`.
All three configurations completed with continuous telemetry, comparable
starting conditions, and matching fixed greedy probes. Median / slowest
generation speeds were AR **11.877 / 11.594**, default MTP D3
**22.463 / 20.386**, and long-context MTP D3 **22.772 / 21.032** tok/s.
Default MTP was selected: the candidate's median gain was only 1.37%, below
the 3% switching threshold (its worst-case gain was 3.17%). This verifies
bounded 256-token speed measurements, not long-generation or agent quality.
The actual browser Apply/reload/Apply check passed against this v5 result.

Restart recovery testing then found a second mismatch: standalone jobs dropped
the requested selection goal, so this fixed generation-TPS sweep was labelled
`fastest` in its saved record. New jobs preserve their goal; operator records
explicitly bind throughput. The known standalone v5 label error is interpreted
as throughput on read, without modifying the record, and the complete record
verifier still runs. The actual saved record now passes history lookup after
restart. The real isolated-browser test also passed with the controller's job
state idle: View results → Apply → reload → View results → Apply, followed by
the main-screen saved-settings shortcut. All actions used this same record ID;
new calibrations, model launches, external requests, and profile writes were
blocked by the harness, and none were attempted. Daylight and Frost checks
confirmed centred dialogs and three aligned, equal-height result cards.

### Historical v4 run (not eligible)

Real saved result: `7528492b-57cd-4840-aead-fe45bfd11e19`.
MTPLX 2.11.1, `Qwen3.8-27B-MTPLX-Optimized-Speed`, built-in Chat contract,
65,536 context, 16,384 configured response limit, model-default sampling and
reasoning, Turbo with system-controlled cooling and unchanged KV precision.

Three isolated configurations each completed four generated workload turns.
Actual prompt usage was 48,965 / 48,967 / 61,119 / 61,169 tokens; each request
allowed 256 output tokens. The launch response limit remained 16,384.
Version-4 measurement records distinguish those two limits.

| Configuration | Median generation tok/s | Slowest turn tok/s | Exact greedy parity with AR |
| --- | ---: | ---: | --- |
| AR | 10.689 | 10.353 | Reference |
| Default MTP D3 | 20.924 | 20.245 | Did not match |
| Long-context MTP D3 | 24.582 | 20.876 | Did not match |

AR was retained because of the exact-output gate, **not** because it was faster.
Different output hashes alone do not establish that an answer is semantically
incorrect. At that point the cause was unknown; the later fixed-probe diagnosis
and v5 run above resolved it. These short output measurements do not qualify
long generations.

Subsequent read-only request reconstruction identified a launcher bug: its
purported greedy probe requested temperature 0 / seed 17, but the emitted body
contained model defaults (temperature 1, top-p 0.95, top-k 20, no seed).
The builder now explicitly separates fixed probes from workload sampling.
The version-4 result above remains historical and is not eligible under the
new version-5 operator contract. The real version-5 comparison above now
confirms all three fixed probe outputs match on this tested model.

The isolated real-browser check in `tests/test_live_mtplx_apply.js` passed:

- Apply the exact saved result, reload, and apply the same result again.
- Preserve 65,536 context, instead of resetting to the 131,072 default.
- No replacement calibration, model load, or server-side profile write.
- Three aligned, equal-height result cards and a centred dialog in Daylight
  and Frost; matching explanations for the exact-output rejection.

After restarting the controller, `/api/optimal` still accepted this exact
saved record and retained its binding without loading a model. The controller
was left idle. This historical check required the completed job in controller
state; the newer v5 restart-and-history check above no longer does.

## Uzu tool/agent boundary

The opt-in real `test_uzu_candidate_live_boundary.py` test passed on the exact
qualified 64K bounded-prefill binary in 42.510 seconds, with normal 38 GiB
process guarding and clean unload. It checked authentication, output/context
limits, interrupted-stream recovery, separate reasoning, and generated tool
round trips through both the native server and the normal launcher relay.
The final answer had to use a nonce created only after the tool call.

A subsequent installed-Pi check exposed two test limitations, not evidence of
production readiness: the model returned the correct nonce wrapped in JSON
when the instruction only said "value", and Pi's `--no-tools` flag disabled
extension tools too. The test now explicitly requests the JSON value field,
uses `--tools fixture_lookup`, and verifies that exactly that tool is present
in the outgoing provider payload. It never exposes builtin file/shell tools,
user extensions, user context files, or cloud credentials. The installed-Pi
test remains opt-in and does not bypass production client admission.

The corrected real test passed in **35.979 seconds** with installed **Pi 0.84.2**.
It used the exact qualified 64K Uzu build, normal private session relay,
`pi-provider.js`, launcher-owned Pi RPC console, and actual `pi_timeline.js`
reconciliation. The outgoing request was required to contain exactly
`fixture_lookup`; the model called it and returned its generated value. Raw
RPC replacements are not counted as extra calls: all result events must have
one unique generated value, and the browser reducer must yield exactly one
tool-result item with a matching final answer. Separate thinking was present.
Both the agent process and model were stopped cleanly.

That first test attached Pi inside its isolated harness. A subsequent normal
primary-launch test (`tests/test_uzu_pi_primary_live.py`) passed in **14.505
seconds** using the production runtime and receipts, ordinary session capacity
admission, `normalized_request`, and `RunManager.start`. It started primary Pi
in Hub Console at 64K/16K output, executed one generated-data tool, returned its
new value, and remembered it on a follow-up without another tool call. Thinking,
tool output, and both answers passed the actual browser transcript reducer.
Both Pi and Uzu exited cleanly. No project files, builtin shell/file tools,
user Pi configuration, extensions, or cloud credentials were exposed.

Production Pi admission now requires the exact pinned Uzu/model identity and
Pi 0.84.2. It reuses only the matching Chat **capacity** receipt; context, output,
sampling, reasoning, freshness, and live memory checks remain intact. The
receipt remains Chat evidence, not a Pi speed benchmark. A separate real-browser
read-only check confirmed the Pi Hub route is launchable and survives reload.
OpenCode and Codex remain unavailable on this Uzu route.

That browser check also exposed an impossible calibration loop: Pi could run a
Chat-only qualification that could never qualify a Pi speed result. Pi benchmark
admission now explains the limitation rather than running it; the fixed route
can be kept without another test when matching capacity is already qualified.
The main-screen Pi badge links to capacity, not a fake performance result.

### Real coding task and replay-loss fix

The opt-in `tests/test_uzu_pi_coding_live.py` uses normal production Uzu/Pi
admission at 64K with the unchanged 38 GiB guard. Pi's builtin read/edit/write
tools are restricted to a disposable TTL/LRU cache fixture; only its source
file is editable. A fixed `run_tests` tool executes the eight read-only tests
in a verified macOS sandbox denying private file contents outside the fixture,
file writes, process forks, and network sockets. No normal user Pi setup or
credentials are inherited.

The first real run repaired the source and passed the tests, then failed the
Hub replay assertion: completed tool results were missing after the queued
follow-up. A deterministic regression reproduced the failure with a small
token-journal limit. The controller now maintains an independent bounded
materialised conversation (512 items / 512 KiB) and uses it when a reader
misses the delivery journal. Rebased snapshot revisions preserve original item
order even when older items receive late updates, while later deltas resume
at the normal journal cursor. UTF-8 and total-memory limits remain enforced.

One rerun needed a second code-repair attempt and reached the harness's old
three-minute deadline; it was safely unloaded and is not counted as a pass.
The subsequent complete run passed in **76.656 seconds** with a longer bounded
deadline and unchanged success criteria: original failing tests, changed source,
all eight tests passing without editing their file, a retained queued answer,
thinking and five tool results, Stop during actual generated output, paused
queued input, successful fresh response, and all prior answers retained.
Both agent and model stopped cleanly. Generated-only evidence is retained in
ignored `build/uzu-pi-coding/last-run.json`; it is not a benchmark receipt.

The installed-Pi synthetic protocol suite also passed in **15.122 seconds**
after this fix, including long UTF-8 output, queues, abort, error/limit handling,
and replay through the real browser reducer. The read-only real-browser Pi
admission/reload/keep-current check passed against the restored controller.

## Interruption safety

Core-engine calibration now applies the existing debounced whole-Mac reserve
guard to all oMLX, LM Studio and MTPLX modes, not just MTPLX's near-64K suite.
It follows the owned run rather than a child PID, so LM Studio's desktop-hosted
model and the load interval remain covered. The memory reserve is unchanged:
the greater of 4 GiB or 10% of physical RAM. Two low samples or three unreadable
samples fail the run through normal unload. Deferred Stop and final cleanup
are bound to the exact plan generation, not whichever run happens to be active.
Model-free worker tests cover AR/DFlash/MTP, loading/requests, absent/live/exited
children, transient recovery, and replacement-run safety. The full Python suite
passed 476 tests with 20 optional skips (456 passes).

The opt-in `tests/test_pi_hub_browser.js` uses installed Pi 0.84.2, the real
Hub DOM and console HTTP handlers, and a generated SSE responder on disposable
loopback ports. It has no model, agent tools, user configuration or credentials,
and leaves the normal controller untouched. It verifies scrolling up during
streaming, queued follow-ups, reload/replay after the bounded event journal
overflows, Stop response with a paused queue, clear/recovery, and retained
answers after stopping Pi. Frost at 1440px and Daylight at 960px preserve a
black timeline, distinct reasoning cards and aligned equal-height composer
buttons. This is UI/protocol evidence, not an inference-speed measurement.

Visual inspection of this test exposed a false thinking-only warning on user
abort. The provider now emits that guidance only for clean `stop` finishes,
not `aborted`, `error` or unknown termination. The Hub's paused-queue copy no
longer invents an incomplete-reasoning cause. The existing length-limit warning
and queue interruption safeguards remain tested.

The earlier run `ed6ad3b1-a754-434e-8d1f-31347d8b924a` was explicitly cancelled
after macOS power logs proved a low-battery hibernation from 02:08 to 08:06.
No partial result was saved. It must not be promoted or reconstructed from
partial status copies, which lack final telemetry/unload evidence.

Active measurement telemetry now compares wall time with monotonic time and
rejects sleep/clock discontinuities or prolonged monitoring gaps through the
owned-process unload path. Regression coverage includes clocks that exclude
suspend time and ordinary, non-qualification benchmark routes.

## Correctness sampling history

The local store contains 26 older general/tuning oMLX, LM Studio and ordinary
MTPLX records without proof of the corrected greedy request policy. New core
engine records carry `fixed-greedy-wire-v1`; old records remain saved but are
excluded from automatic candidates and trusted history recommendations. The
separately audited MTPLX operator-v5 run remains subject to its full verifier;
the v4 run remains invalid. Uzu capacity receipts use their independent policy.

Verification: 473 Python tests ran (453 passed, 20 optional skips); ordinary
JavaScript checks passed. After restarting the idle controller with this guard,
the real MTPLX v5 saved-history review, Apply/reload/Apply and main-screen
saved-settings shortcut passed without retesting. The real Uzu Pi browser
capacity/admission/reload/keep-current check also passed. Neither check launched
a model. The local benchmark store's SHA-256 stayed unchanged throughout.

## Remaining work

Active full three-engine run: `48d2c0a0-190a-4832-afe5-a166e0fd7d1c`, started
2026-09-05 on the normal port-18080 controller with the new memory guard.
Exact model: `Users-alexanderthomson-.lmstudio-models-Youssofal-Qw-f2ea0c4b`;
Chat contract, 65,536 context, 16,384 configured output, automatic reasoning,
model sampling, full-precision KV and system-controlled cooling. The generated
four-stage workload includes near-64K prompts and at most 256 output tokens
per timed request. Rotated order: LM Studio, MTPLX, oMLX; up to 33 loads / 198
requests including runtime and acceleration tuning. This is not complete
evidence until the worker saves and validates the entire comparison.
`tests/test_live_cross_engine_apply.js` is prepared for its saved result;
only syntax/opt-in gating has been checked so far, not the live Apply workflow.

- Extend the successful MTPLX saved-route restart/review proof to full
  cross-engine shootout history and the other runtime-specific tuning panels.
- Extend the successful bounded Uzu Pi coding/queue/Stop test to larger
  multi-file coding tasks and browser-driven live agent controls.
- Add honest Pi agent-performance calibration, separate from Chat capacity.
- Uzu OpenCode support remains gated pending actual tool/agent verification.
- This run compared three MTPLX settings, not three different engines. It is
  not evidence of a completed oMLX/LM Studio/MTPLX cross-engine comparison.

At the replay-fix checkpoint, the full Python suite passed 450 tests with 20 explicit
optional skips; all ordinary JavaScript checks passed. The separate live
browser check above also passed. Uzu's 38 GiB process ceiling remains separate
from MTPLX's own memory planning and the whole-Mac reserve.

## Simplified launch home

The main Launch button now orchestrates a fresh capacity plan and required
route qualification before handing off to the existing production launch
preflight. The preparation module never turns an engine comparison into a
qualification, edits visible settings, or fabricates a saved receipt. Uzu Pi
uses the existing verified Chat capacity relationship; missing 64K prerequisites
for a selected 128K capacity test run in order. Cancellation is bound to the
job started by that launch, including cancellation during the start request.

The real browser opened Uzu + Pi at 128K / 16,384 output with one click and
reused its saved capacity result. A temporary 32,768 output selection started
the required 64K prerequisite automatically; Cancel stopped that preparation
without launching Pi. That new qualification was deliberately cancelled, not
claimed as completed. Unit tests cover completion, failed-result rejection,
review, changed settings, and cancellation races. The browser was restored to
the existing 128K / 16,384 configuration after verification.

### Pi status noise and thinking visibility — 5 September 2026

Inspected the user's active Uzu/Pi session in Safari. Its single greeting
produced thinking and an answer, but the old controller recorded `setStatus`
presentation updates between nearly every token. The browser now filters
those legacy cards before materializing its bounded timeline and keeps
Thinking expanded by default. Reloaded Safari and observed the existing
thinking and answer with no status noise; Pi remained running and the unsent
draft was restored. The controller was not restarted, preserving its live
conversation. The server-side suppression takes effect on its next restart.
Regression tests exercise 1,000 status events, retained thinking, notification
and confirmation delivery, cursor advancement, and manual collapse behavior.

### Uzu response-ceiling capacity reuse — 5 September 2026

The user's 128K / 64,000 output launch had unnecessarily started a new 64K
prerequisite despite successful 64K and 128K receipts at 50,000 output. Both
configurations share the same 8,192-token bounded probe ceiling. The repeat
failed at the tool-ingestion probe's remaining-context 2,432-token allowance;
it was not recorded as a successful qualification.

After the capacity-only reuse change, the current saved 128K receipt
`8a224132-f7a4-49cd-bfc7-47a2888b0d0d` validated without modification for the
user's unchanged 128K / 64,000 settings. Restarted the idle controller and
launched Pi in test1 from Safari. The normal launcher reached running with
context 131072 and output 64000; benchmark status remained idle with no job.
The Hub showed Pi ready. No new model qualification or speed claim was made.
Validation: 67 Uzu backend tests passed; the 300-test controller suite passed
with 10 optional skips; launch-flow and session-admission UI tests passed.


## Pi Hub recovery and live output

Installed Pi 0.84.2 with generated loopback responses passed context-overflow
compaction and one automatic retry, the installed pi-token-speed 0.7.1 status
bridge, saved-session resume, follow-up queue ordering, abort and truncated
response recovery. Tests isolate user tools/configuration and make no model
requests. Browser inspection confirmed readable partial code during a real Pi
RPC tool stream, collapsed finished details, and retained code for reopening.
The fixture deliberately registers no tools, so its write ends with Pi's safe
“Tool write not found” result and cannot alter project files.
67 Uzu backend checks and 300 controller checks passed (10 controller skips),
plus focused Python/JavaScript streaming, status, recovery and resume checks.
Pi custom terminal extension screens remain a limitation of Pi's RPC API;
these checks do not claim complete terminal/browser feature parity.

Live application check: restarted the controller, reused the existing Uzu
capacity receipt, and resumed the original test1 Pi session at 131,072 context /
64,000 response. Native compaction completed at 13:20:53 UTC, with 27,858 tokens
before compaction, and Pi retained its session history. The live browser showed
compaction progress, then cleared it and enabled Compact again with no browser
console errors. The interrupted project task was left ready for the user.


Hub context/prompt status: installed Pi integration verified context counts
before and after automatic compaction. Live browser inspection showed Pi's
68,978 / 131,072 token estimate (52.6%) and the latest request's estimated
prompt throughput, with separate Generate, Prompt, Context and Lane fields
in one desktop row and no browser console errors. The idle Pi process was
restarted with its existing session file; the loaded model was preserved.


## MTPLX 2.11.1 local diagnosis — 6 September 2026

On the M5 Pro with 48 GiB RAM, the installed Qwen3.8-27B MTPLX Optimized
Speed artifact has 20.68 GB of mixed 4/8-bit weights. Its replaced MTP
sidecar contains 31 tensors; the installed runtime's payload audit passed
(8 nonzero payload tensors, 8 scale tensors). The stale 15-tensor audit in
model metadata was backed up and replaced with that native audit, restoring
verified MTP and the 2.11.1 long-context operator contract.

A completed four-stage 49–61K synthetic comparison at a 128K configured
context, Q4 KV, Turbo, depth 3 and model sampling measured median generation
rates of 11.409 tok/s AR, 7.423 default MTP, and 6.692 long-context MTP.
The local benchmark receipt is 73f15076-f076-4dbe-8cb7-7098068a193d. These
are long-context measurements, not a general speed ceiling for this model.

After explicitly approved Pi suspension, single 78-token / 256-output-token
short probes measured native decode rates of 13.147 AR/Q4, 18.109 MTP/Q4,
and 27.234 MTP/unquantized KV. These are diagnostic samples, not a repeated
controlled qualification or an automatic-selection receipt. Temperature was
1.0, top-p 0.95 and top-k 20; stochastic output trajectories can differ.
The GPU wired limit remained 40960 MiB throughout.

A subsequent single generated 61,157-token prompt with MTP D3 and unquantized
KV measured 22.509 native decode tok/s over 256 output tokens. Peak MLX
memory was 34,871,264,900 bytes (32.48 GiB); prompt processing was 358.527
tok/s. This supports Q4/layout overhead as an additional cause of the slow
long-context route: the 32K compiled-verifier cutoff alone does not explain
it. This remains a diagnostic sample with stochastic output, not a new
full calibration receipt. The active Pi session was restored with MTP D3,
Turbo, unquantized KV, 131072 configured context and the existing 40960 MiB
GPU limit, and its interrupted task was resumed from the saved JSONL.

## oMLX compaction recovery — 6 September 2026, 13:38 UTC

The 27B DFlash session rejected a 90,751-token prompt, then rejected its
54,681-token compaction request under dynamic memory pressure. A cold retry
with the original summary allowance reached hard memory pressure and was
stopped. Baseline recovery was rejected by the relay's conservative context
estimate before inference. The bounded, thinking-disabled native DFlash
recovery succeeded: Pi saved a compaction at 13:38:19 UTC with 90,392 tokens
before compaction and an 11,928-character summary. The original DFlash/xhigh,
128K context, 100000 output settings were restored, the saved task resumed,
and the kernel wired limit was verified at 40960 MiB. Earlier compaction and
the summary-only 4096-token limit are now active. Focused proxy/settings tests
and all three installed-Pi mock-server memory-recovery cases passed.
