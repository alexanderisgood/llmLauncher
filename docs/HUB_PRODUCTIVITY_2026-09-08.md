# Hub productivity repairs — 8 September 2026

> Development notes: referenced raw receipts and session captures stay local and are not included in the public release. Measurements below describe individual development runs.

The graphics task ran for roughly 45 minutes without a successful game edit.
The browser tool was present, but lacked screenshots. The model noticed that
missing action, built its own Playwright setup and tried external image services
after Pi correctly said the selected route could not read images. A later edit
used a palette anchor that did not exist; the atomic native edit changed nothing.
The task was stopped with its saved conversation and game files preserved.

## Browser work without setup detours

`browser_check` now captures viewport/element PNGs and resizes the actual browser
viewport, including inside bounded action sequences. Inspection reports controls,
canvas display/backing dimensions, failed images and runtime errors. Screenshots
stay in the owning run's browser folder and appear inside the Hub's existing
expandable tool result. Serving is restricted to bounded regular PNGs in that
folder; arbitrary paths, links, non-PNGs and cross-site embedding are rejected.

The selected DFlash route remains text-only. Tool guidance explicitly explains
that screenshots are for human review, supplies browser measurements as the
available verification method, and avoids browser-installation or remote-image
workarounds. These changes do not claim the model can judge screenshot pixels.

## Failed edits retain actual source evidence

Known native edit missing/ambiguous-anchor errors now include a bounded read of
the already-targeted file: exact candidate source lines, declaration locations,
line numbers and a content hash. The original failure and error status remain.
No proposed replacement is executed automatically. Custom tools are untouched.
The latest observation is retained beside native execution evidence across
compaction, clearly identified as an observation that can become stale.

An installed-Pi fixture reproduced an atomic batch whose first anchor was
invented. Nothing changed; Pi received the native error plus the actual source,
then succeeded using the observed anchor. This checks the real tool-event path,
not just a text-generation rule. It does not prove all model reasoning errors
or possible loops have been eliminated.

## Reuse the context already in memory

The launcher previously charged two extra complete cache copies before native
snapshot publication. The audited native generation path actually adopts the
resident KV/recurrent arrays and logits. This false allocation estimate skipped
valid snapshots and forced full prefills on later turns.

For native generation adoption with disk caching disabled, admission now reserves
twice the retained hidden-state spans plus 1 GiB. The installed native slicing
policy is evaluated on shape-only metadata to account for sink/window retention,
sidecar coverage and full-attention exceptions without allocating arrays.
Copied, disk-backed and unknown paths
retain the conservative full-copy allowance. The current native ceiling is
refreshed during generation; the 40 GiB ceiling, 90% admission margin and native
prefill admission remain unchanged. Native tests verify exact prefix restoration,
divergent-prefix rejection, consumption of the old cache entry, and unchanged
stored arrays after appends/recurrent-state updates.

The single retained snapshot's logical size limit now accounts for full-precision
KV plus 1 GiB of auxiliary state, with the previous 8 GiB minimum. The 128K Qwen
profile therefore uses a 9 GiB logical snapshot cap. This is neither a reservation
nor a higher physical memory ceiling. Full-128K memory capacity is still not
qualified by these smaller tests.

## Live evidence

The installed Qwen3.8-27B-MLX-6bit ran through Pi Hub with medium thinking,
DFlash2, Q8 draft weights, full-precision KV and 128K configured context.

- In an isolated browser task it delivered a redesigned dashboard and a correct
  one-step counter in 223 seconds, using nine tool calls. Independent Chromium
  checks passed at 390 and 1280 pixels: no horizontal overflow, correct button
  increments, preserved label, requested gradient/cards and no runtime errors.
  The initial model-side responsive check hit a file-iframe restriction and
  used a CSS approximation, explicitly disclosed in its final response. That
  exposed the missing resize action, which was then added.
- After reloading the extension, the same model verified both real viewports
  through native resize sequences in 61 seconds, reported zero overflow, saved
  the mobile screenshot and made no additional source edits. The live Hub loaded
  the actual local PNG through its new preview endpoint without browser errors.
- A separate synthetic native cache test processed 47,994 tokens cold in
  154.15 seconds. The two follow-ups restored 48,052 and 48,104 tokens, each
  processing only 22 new tokens in 0.55–0.56 seconds. First output arrived in
  0.86–0.87 seconds; both complete answers were correct. This demonstrates warm
  prefix reuse, not a 280-fold improvement in model decoding or all workloads.
- Actual Chromium and installed-Pi tests cover screenshots, real viewport/media
  query changes, trusted input, sequence failure handling, cancellation and PNG
  size boundaries. The live Hub preview is checked separately.

The isolated coding task and measurements used disposable projects. No game
source was written by the launcher work or its fixtures. Qwen's subsequent
edit to the user's project is assessed separately below.

Coding receipt (local-only evidence),
independent browser checks (local-only evidence),
native cache timings (local-only evidence),
model resize verification (local-only evidence),
live Hub preview (local-only evidence).

## First activation on the user's task

The updated controller was restarted while idle, then the original graphics
request was resumed in a fresh Pi session with a factual handover. The selected
6-bit model, 131,072-token context, medium thinking and 40 GiB native ceiling are
retained. The game source hash was unchanged by the launcher work at dispatch.
The resumed run is `c1e63fcf-55c4-415e-abe3-1f5b15828eeb`.

At 09:20 BST the Hub showed the model using the ready-made browser and reading
the relevant drawing functions. A live request reused 35,959 prompt tokens and
processed 1,018 new ones. The model was still planning its first graphics edit;
this early observation is not a claim that the game task has finished or that
all excessive planning is resolved.

Resume receipt (local-only evidence).

The longer run subsequently exposed a second overestimate at 09:24:51 BST:
the generation guard charged the full 442 MiB of hidden features when the native
sidecar policy retains only 57.7 MiB. The existing 35.619 GiB admission limit
rejected the old 36.048 GiB projection; the corrected projection is 35.298 GiB.
Before that rejection the run recorded 14 warm hits, one initial miss and no
evictions. The lost snapshot caused a 46,013-token cold prefill lasting 140.8
seconds. This is why the retained-span correction was added after the first
live test; warm reuse is not guaranteed under all memory conditions.

Ten native tests now cover actual hidden-state allocation peaks, dense/sparse
chunks, sidecars, full-attention exceptions, prefix trimming, admission at the
exact boundary and rejection one byte over it, plus unchanged restored cache
contents. The physical ceiling, 90% margin and fixed workspace reserve stay the
same. Native publication already clears unused allocator buffers immediately
before this guard, so no redundant allocator flush was added.

## Follow-up: a real edit, followed by excessive verification

The same saved Pi conversation was resumed after native compaction with the
retained-hidden correction, low thinking (2,048 tokens), and one-function scope.
This changed several variables together and is not an isolated comparison of
reasoning levels. Run `156a5cbb-8414-400a-b335-16f0248cb2a0` retained the 6-bit
model, DFlash2, 131,072-token context and 40 GiB native ceiling.

Qwen completed a native edit at 08:55:00 UTC, 4m11s after dispatch. Reversing
its recorded replacement in memory reproduces the previous file hash exactly:
only `drawBackground()` changed. Syntax and independent Chromium movement/jump
checks passed, with no runtime errors. The edit-generating request decoded at
29.8 tokens/s and processed its 652 new prompt tokens in 2.216 seconds. All
observed generation snapshots in that run were saved.

The checkpoint still took 20m27s to finish, with 19 tool calls and 18,694 output
tokens. Its 686,719 cumulative input tokens included 571,426 cached tokens;
115,293 were uncached. These are cumulative per-request counts, not the size
of the conversation. Most of the delay after editing was unnecessary browser
investigation, so this run does not establish satisfactory long-task efficiency.

The browser tool returned from a key press before the application processed
its next frame. An immediate sample still showed the title screen; the next
model round trip took 137 seconds, leaving gameplay running before it sampled
again. The model's later claim of 900 updates/second is unsupported: latency to
one animation-frame callback is not frame frequency, and the game uses a 60 Hz
accumulator. No game-loop changes were made by the launcher work.

`press`, `click` and `fill` now accept an optional `wait_for` expression. It
waits for an observed application condition within eight seconds and the
existing action deadline. Sequences allow 12 steps sharing a 120-second total
deadline, preserving the previous six-action worst-case duration. This lets
start, movement, jump, measurements and screenshots happen together without
model pauses. There are no fixed sleeps, guessed conditions or automatic
assertion retries. Hub previews also include screenshots in the later steps.

Real Chromium and installed-Pi fixtures pass with input transitions deliberately
delayed by animation frames. A condition that never becomes true fails within
the action deadline and prevents later steps. Existing workflow instructions
already require focused checks and completion when they pass; no additional
generic progress prompt was added.

Trial timeline (local-only evidence),
independent game verification (local-only evidence).

## Current activation

Run `6064cb9f-fae9-4502-948a-2e3f21ef0b4c` loads the browser postconditions,
12-step sequences and cache corrections from the restarted controller. It
preserves Pi conversation `01a08014-ba04-7584-81ce-6f4d90c188ca`, low thinking,
128K configured context, the 6-bit model and 40 GiB ceiling. Full-128K capacity
and long-task reliability remain unqualified.

Activation receipt (local-only evidence).

The live Qwen verification finished at 09:19 UTC with one nine-step browser
call. Start, movement (x34 to 59.28), jump (y177.98 to 170.99, velocity -7),
screenshot and browser close completed in 1.16 seconds, with no reported
browser errors or source changes. Qwen waited for `play`, sampled rather than
waited for the initial grounded condition, and accurately disclosed the initial
`onGround:false`. It also retracted its unsupported frame-rate explanation.
Runtime results do not establish the visual quality of its graphics edit.

Including the restart's cold context load and model reasoning/report, this
verification took 4m31s, with 2,224 output tokens and one tool call. The native
follow-up reused 47,119 of 47,526 prompt tokens (99.1%), processing 407 new
tokens in 1.92 seconds. No snapshot rejection or crash occurred. Native memory
warnings briefly reported 38.3 GiB against its 38 GiB hard threshold, with zero
aborted requests, before pressure recovered to 26.8 GiB. The effective physical
ceiling remained 40 GiB. Decode on the cold request was 15.7 tokens/s excluding
prefill; successful cache reuse is not proof of sustained fast decoding.

Live browser postcondition result (local-only evidence).

The restarted Hub also loaded the actual step-eight PNG at 1280×800 through
the current run's artifact endpoint, with no browser errors.
Hub preview receipt (local-only evidence).

The [Reddit/X research review](HUB_RESEARCH_2026-09-08.md) distinguishes reports
matching the symptoms, upstream fixes already installed, and fixes for other
engines that do not apply to this MLX implementation.


## Progress-check false positive — 8 September, 11:53 BST

The saved Pi session recorded a progress check at 10:53:25 UTC after twelve
recognized inspection calls. It was reading different renderer functions and
source ranges, with new results; this was not evidence of a loop. The old rule
also treated four repeated call arguments as stalled work without comparing
their results, so changing logs and legitimate research could be interrupted.

Replaced the count-only steering rule with a conservative observed-cycle check.
It covers confirmed native read/grep/find/ls results: the same two to four
actions must return exactly the same complete text outputs for three cycles.
Each cycle must begin after the model received the preceding cycle's results;
a batch of duplicate calls alone is insufficient. Any unknown tool, error,
missing/large/non-text result interrupts the sequence. Changing arguments or
outputs cannot match an unchanged cycle. The detector retains at most twelve
bounded fingerprints, no full outputs and no evaluator.

A candidate waits until the tool batch ends and is cancelled if another tool
starts or completes. At most one note is committed per user input, surviving
automatic continuations and compaction. Explicit monitoring suppresses it. The
note lists the repeated actions and advises using observed evidence; it does
not demand edits or assert failure. Existing identical-result hard stops,
repeated-reasoning protection, invalid-tool recovery and edit evidence remain.

The note is saved/displayed without steering or triggering a new model turn.
An installed-Pi test exposed that Pi 0.85's active agent loop retains an older
context copy after saving a context-only notice. The existing context hook
therefore inserts the same note after its confirmed final tool result when
absent, preserving its position on later requests and avoiding duplicates.
Compaction clears the pending insertion; a missing anchor is never guessed.

An isolated installed-Pi fixture performs six real native reads against a
scripted local responder. The seventh natural request contains one correctly
placed note, with hashes matching the saved native results. It then completes:
seven requests, no extra turn, abort or file changes. No model is loaded.
The original thirteen tool completions before the false positive (twelve matched
the old classifier) replay without a notice or block under the new policy.

The source fix requires an idle Pi extension reload or a new Pi process. The
active response was left uninterrupted; bypassing Pi's idle reload requirement
would replace hooks during inference and could close its browser session.


## Long-generation memory reclaim — 8 September

Run `06d2642f-f0e3-4f04-94a9-56c8027acc45` produced a confirmed slow response:
4,636 output tokens at 5.8 decode tokens/second, excluding 19.31 seconds of
prefill. Native target verification consumed 763.4 seconds, drafting 5.76 seconds,
and acceptance was 61.5%. The following 303-token response decoded at 25.9
with a larger 55.5K prompt. Cache reuse remained healthy: sixteen hits and one
initial miss; a later request reused 55,801 of 55,840 prompt tokens.

The strongest identified pressure gap is DFlash's missing
`request_pressure_reclaim` hook. Its periodic allocator cleanup waits for 1,024
generated tokens; oMLX's process enforcer could request earlier cleanup from an
ordinary scheduler but not the DFlash guard. The slow run repeatedly reached
38–38.5 GiB pressure before dropping to 27–31 GiB. Swap use alone is not proof
of active thrashing: sampled swap-outs were unchanged. These observations
identify a concrete integration defect, not a measured post-fix speed gain.

The session adapter now implements the guard's flag-only request and consumes
it at a committed DFlash token boundary on the existing inference thread.
Native pressure thresholds decide when to request it. Synchronization settles
the audited draft's default-stream work, then `clear_cache` releases unused
allocator buffers; live KV, recurrent state, draft tensors and snapshot arrays
remain referenced. No pressure means no extra synchronization or cache clear.
The 40 GiB ceiling and native admission checks are unchanged.

Installation checks the audited oMLX 0.6.4 / dflash-mlx 0.1.10+omlx.7 interfaces.
Tests cover the real enforcer contract, thread ownership, coalesced requests,
shutdown/fallback/disabled guards, events, wrapper composition and cancellation.
A separate small native-MLX fixture confirms live cache/snapshot arrays and an
asynchronous draft survive reclaim, without loading model weights. Existing
adapter, attention, memory-admission and prefill tests also pass; unrelated
native operator opt-ins were not repeated.

Only launcher source changed. Installed runtime files and the active engine
were untouched. Activation needs an engine restart at a safe checkpoint;
sustained speed and pressure reduction require a long-response comparison after
activation and are not yet established.


The user subsequently requested a restart. Both fixes are now active in run
`60c589c2-d5a9-412e-b7b9-7b1e0cf68dd0`, with the exact Pi conversation
`01a08090-6a4f-7270-9e0e-8fb140fc6927` restored. Controller, engine and Pi were
restarted; the old session engine exited. The 6-bit model, 128K context, 80K
output, medium thinking, Q8 DFlash block 4 and 40 GiB ceiling were preserved.
Startup passed and Safari's Hub loaded the saved transcript. The session is
idle; post-restart long-generation speed has not yet been measured.

Activation receipt (local-only evidence).

## Recovery and Qwopus preparation after the stopped run

The scheduled task `review-qwen-s-completed-mario-run` is paused. The next
observed failure was incomplete compaction: the summary exhausted its 4,096
token allowance. The original Pi conversation remains saved and the old
controller remains idle with two paused follow-ups. Its API returns only the
count; their text was never persisted. Do not stop that controller without
resolving whether those two messages may be discarded.

Implemented, but awaiting activation in the user's session:

- Pi summary recovery keeps native checkpoint creation and the 4,096 token
  ceiling, requests a concise complete checkpoint, and retries truncation or
  empty text once. Partial summaries and tool-call responses cannot become
  checkpoints. Task thinking stays enabled. The adapter is limited to oMLX and
  MTPLX; preserved Uzu Pi retains native compaction.
- The Hub exposes queued follow-up text in a compact expandable list. It saves
  changes to private, atomic files under `pi-queues`, keyed by project and Pi
  session. Resuming that conversation restores the queue paused. Accepted or
  cleared messages are removed from the saved queue. Disk failures are visible.
  This cannot recover messages held only by the already-running old controller.
- The installed MTPLX 2.11.2 Qwopus artifact has a vision tower. Its Pi model
  contract now advertises image input; browser screenshots reach the model as
  bounded image blocks while original PNGs remain available in the Hub.
  Text-only routes explicitly describe that limitation. Incomplete browser
  scripts and HTML downloaded as an image produce useful tool feedback.
- oMLX single-entry DFlash cache replacement releases an obsolete generation
  entry before allocating its replacement when headroom admission fails, then
  remeasures actual memory. The 40 GiB ceiling and 90% reserve are unchanged;
  no speculative credit is taken for cache arrays that remain resident.

Validation includes real installed-Pi/Chromium queue visibility and reload,
native compaction continuation/failure, outgoing screenshot image parts,
Qwopus template/cache-history/tool-recovery regression tests, and native MLX
array-release/restoration tests. These are bounded regression checks, not a
claim that a new long-running Qwopus task has passed.

The launch request in `/tmp/qwopus-switch-launch.json` validates against the
installed MTPLX 2.11.2 and Qwopus MXFP4 vision artifact: 131,072 context,
32,768 output, medium thinking, sustained profile, native MTP depth 2, full
precision KV and publisher-scoped thinking history. It resumes Pi conversation
`01a08090-6a4f-7270-9e0e-8fb140fc6927`. No model was loaded, no game files were
edited, and the old controller was not restarted for these checks. Live vision
inference and sustained task performance remain to be checked after switching.

## Qwopus screenshot configuration compatibility

The user subsequently launched Qwopus with MTPLX 2.11.2 in run
`920cb7d6-941a-4b71-8e25-7a8aa81757c3`, Pi conversation
`01a08204-f5e9-7665-9330-500d6ef2bca0`. Its first screenshot input failed
before generation: `_materialize_vision_splice` opens
`preprocessor_config.json`, while the downloaded publisher artifact supplies
those settings as `processor_config.json.image_processor`. The earlier gate
checked the tower weights but missed this runtime requirement. This was not a
memory-admission failure.

Client preparation now supplies the legacy filename from that exact local
publisher object after validating pixel bounds, normalization and patch
geometry against the installed tower. It preserves existing files and never
substitutes another model's settings. Capability reads remain read-only and
advertise images only when the standalone configuration is usable. An
unsupported runtime, invalid configuration or unwritable model stays text-only.

Eight focused regressions cover preparation, no mutation during capability
reads, invalid/mismatched settings, existing-file preservation, write failure,
unsupported engines, and the actual Pi launch contract. Five adjacent Pi
identity/preserved-runtime checks also pass.

The compatibility file was installed on the active artifact and the saved Pi
task resumed without restarting MTPLX or changing the user's thinking, context,
KV or memory settings. The resumed image-bearing request completed successfully,
followed by successful browser work and another screenshot. Thinking events
were visible in the Hub transcript. Image prefill was slower than the earlier
text-only requests; this repair establishes recovery from the configuration
failure, not optimal vision speed or completion of the game task. The preparation
and stricter gate are in launcher source for its next controller startup; the
active engine already uses the repaired artifact.

Live recovery receipt (local-only evidence).

## Printed edit incorrectly marked complete

At 18:06:12 UTC the same task ended with a bare `{"name":"edit","arguments":...}`
object in assistant text. The engine log and exact final text establish that
the outer JSON object was missing its closing brace. The edit did not execute.
Several overlapping source reads preceded it; two
earlier edits had succeeded, so the task cannot be described as making no
progress throughout the run. The Hub nevertheless labelled the final response
Complete because the recovery exemption treated a mention of
`processor_config.json` in the resume instruction as a request for literal
JSON, disabling recovery. A separate inspection found that the detector also
excluded complete JSON envelopes printed as answers; that gap was repaired too.

The request also used MTPLX's default hybrid tool contract. The installed
encoder reproduces conflicting examples: the publisher template asks for JSON
inside `tool_call`, while the runtime adds `function`/`parameter` XML. Qwopus
launches now select native tool prompting. Its Pi provider also sends the
supported request override, allowing the correction after extension reload
without restarting the engine. Other model routes retain their existing mode.

Recovery now recognizes exact bare envelopes for an active tool even when the
JSON parses. It never executes assistant text: the existing bounded Pi recovery
asks the model to issue a real tool call, preserves native validation, and stops
with a visible error when the retry allowance is exhausted. Explicit requests
for literal examples remain exempt. Merely mentioning a filename such as
`config.json` no longer disables recovery for the whole task.

The installed-Pi fixture returns an unexecuted valid JSON envelope first, then a
native tool call after recovery. Exactly one fixture tool executes; its result
reaches the model. The same check covers exhausted recovery, visible failure
status, paused queue advancement and existing repeated-call limits. Native
MTPLX/tokenizer checks establish one tool format and retained active reasoning.
Provider, workflow and unchanged inspection-trigger regressions pass. These
checks do not establish that arbitrary model planning loops are eliminated.

The idle Pi extensions were reloaded and the original saved task resumed with
a factual correction that the last printed edit never ran. Launcher work did
not edit the game source. The first resumed request records native tool mode
from the request header, the hybrid contract disabled, and reasoning on. Its
59,012-token cold prefill ran at 365 tokens/s; that is not an isolated speed
comparison. At 18:18:38 UTC Qwopus executed a native three-block edit; subsequent
`node --check` tool results returned without errors. Inspection continues, so
this establishes working tool transport rather than elimination of all loops.

Tool recovery receipt (local-only evidence).
