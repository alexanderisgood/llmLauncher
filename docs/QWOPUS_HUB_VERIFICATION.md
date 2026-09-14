# Qwopus in the Pi Hub — 7 September 2026

## Integration

The downloaded `Shiftedx/qwopus3.8-27b-flash-mxfp4-vision-mtplx`
artifact uses the `Jackrong/Qwopus3.8-27B-Flash` source. Its MTP sidecar
was downloaded at the model root even though the manifest refers to
`mtp/weights.safetensors`. The local sidecar was relocated after checking
its SHA-256 against the published artifact. Native MTPLX inspection then
accepted all 15 MTP tensors. This establishes compatibility, not a speed
qualification for every context size.

MTPLX 2.11.1 does not identify this `qwopus3.8` alias as its `qwen3.8`
family. Its automatic template selection therefore used the older
`local_qwen36` profile and retained reasoning only in the current user
round. The publisher's bundled template has the same rolling checkpoint.

`mtplx_reasoning.py` recognizes the exact source and bundled template
hash and creates a session-local copy which retains earlier reasoning.
The launch command selects that copy and keeps `--preserve-thinking auto`.
In this runtime, that combination selects `preserve-echo`; explicitly
setting the flag to `on` selects a different legacy committed-history path.
The original model files are unchanged by this adapter. Unrecognized
publisher templates are not rewritten.

The installed native encoder regression reproduces loss of an earlier
reasoning sentinel, then verifies retention with the adapted template.
The installed Pi integration separately verifies that previous thinking
is emitted in the provider's `reasoning_content` field. These are
behavioral checks, not just assertions about launch flags.

## Workflow

The launcher-owned `pi-workflow.js` extension adds guidance for small
runnable milestones, focused verification, concise project handovers,
and checking the real entry point. It can send up to two visible native
steering reminders after repeated successful inspections without an
intervening edit or execution step. It does not replace Pi's tools,
compaction, or queue handling, and does not force read-only tasks to edit.
After the coding check below, the guidance was also tightened to prefer
executable checks over repeated arithmetic speculation and to make failed
checks fail the process rather than merely print a FAIL label. These final
wording changes passed extension tests; the coding run preceded them.

## Live xhigh coding check

An isolated cart project used the real Pi Hub, MTPLX 2.11.1, Qwopus,
128K context, a bounded 32K test response allowance, MTP depth 3, and
unchanged KV precision. The model edited the actual `cart.js` and
`index.html`, rather than a scratch alternative. A real browser displayed
the required £3.58 total before and after its correction.

Its first answer missed a floating-point half-penny rounding case. Native
Pi steering accepted independent feedback, and the model corrected it.
Seven independent assertion-based checks then passed, including clamping,
stock/quantity filtering, input immutability and rounding the combined
total once. This was a successful correction, not a perfect first pass.

The combined coding and correction turn took 5m 21s and used 13 model
requests, 14 tool calls and 7,388 output tokens. Its reported 112,739 input
tokens included 99,458 cache reads; 13,281 were uncached. Decode rates
varied with the request, so this is not a fixed throughput guarantee.
The verbosity and missed edge case remain limitations of this xhigh run.

A fresh prompt after completion reused **13,969 / 14,008 input tokens
(99.72%)**. Native telemetry reported **39 processed tokens in 0.282s**.
The complete follow-up took 8.537s with 162 output tokens and 22.76 decode
tok/s. It accurately recalled the changed files and rounding regression.
This directly verifies cache continuity across a new user message.

Local numeric receipts: `/tmp/qwopus-xhigh-hub-receipt.json` (the status
endpoint retains a bounded recent-request window; the complete turn
counts above come from the Pi summary). Test run:
`875d2408-48ea-43a4-91c5-1575ddd944bf`.

## Limits

Preserving reasoning and a reusable prompt prefix can reduce repeated
prefill and lost context. It does not prove a benchmark quality gain.
Accumulated input tokens still include cache hits, so that count alone
does not measure GPU prompt processing. Tool-call serialization can also
prevent MTPLX from directly saving its final generated cache; the runtime
then reprocesses a suffix rather than reusing the entire generated turn.

The system's existing 40 GiB GPU ceiling, 128K production context,
MTP depth 3, full-precision KV, and xhigh reasoning remain unchanged.
No claim is made that a short coding check qualifies a full 128K session
or proves the model cannot loop or make mistakes.

## Qwen3.8 27B MLX 6-bit follow-up verification

The installed `lmstudio-community/Qwen3.8-27B-MLX-6bit` artifact was also
checked. Its publisher template already supports preserving all historical
reasoning. It does not need the Qwopus compatibility adapter.

`tests/test_qwen38_reasoning_integration.py` checks the actual 6-bit
tokenizer through both installed engine paths without loading weights:

- oMLX 0.6.4: native model discovery, API message extraction, and the exact
  live launcher's generated model settings retain a reasoning sentinel
  after a new user message and keep the previous rendered prefix unchanged.
- MTPLX 2.11.1: native family resolution identifies `qwen3_8`, selects
  preserve-echo under `auto`, and the native encoder retains the same
  sentinel and prefix. No Qwopus template override is applied.
- A negative control explicitly disables preservation and must lose the
  sentinel, ensuring the check detects the behavior being protected.

A live two-turn Pi Hub check used the 6-bit model on its existing oMLX
DFlash route (depth 5, Q6 KV, Q8 draft, 128K context, xhigh; test response
allowance bounded to 4,096). The second turn correctly recalled the
fixture codename, reused **5,038 / 5,072 prompt tokens (99.33%)**, and
processed **34 tokens in 0.735s**. It completed in 3.885s with 55 output
tokens. This verifies short-turn cache reuse; it is not a long-context
memory or quality qualification. The 40 GiB GPU ceiling was retained.

Test run: `5443e7a0-8e0d-4744-b65f-f72ce9c14398`. Numeric-only receipt:
`/tmp/qwen6-preserved-thinking-receipt.json`. The original Qwopus Pi
conversation was backed up before switching and restored after the check.

## Malformed tool answer recovery

A subsequent real Qwopus turn printed a broken `{"name": "bash", ...`
wrapper as plain answer text. The request completed successfully at the
HTTP level and reused its cache, but Pi received no tool call, so the
approved game replacement did not happen. This is separate from cache
preservation and demonstrates why throughput alone is insufficient.

The Pi workflow extension now recognizes this narrow malformed final-answer
pattern for an active tool and asks the model to issue a native call. It
never parses that text into an executable command. Recovery is capped at
two retries per user input; valid JSON, quoted/fenced examples, explicit
format/example requests, failed/cancelled replies and actual tool calls
are excluded. The cap survives automatic continuation.

The Hub now renders Pi's explicitly visible custom extension messages as
plain notices, including recovery and terminal failure messages. Hidden
extension messages stay hidden, and history restoration does not duplicate
notices. The installed-Pi regression uses only a generated-value fixture
tool: it verifies recovery to a real native call, exactly one tool result,
and stopping after two repeated failures. No shell or filesystem tools are
available in that test.

## Repeated tool actions: observed failure and containment

The resumed Mario run produced real tool calls but repeated inspections and,
after direct steering, repeated the already successful replacement/check
command. The run was manually aborted. Its reported input was 1,636,420
tokens, including 1,595,912 cached tokens. Cache reuse therefore did not
establish useful progress or task quality. This run fails the autonomous
completion check; do not count subsequent operator intervention as a model
success.

Progress reminders now enter Pi's steering queue with `triggerTurn: true`.
Previously they were visible but used the non-triggering append path. A
separate guard pauses before a fourth consecutive identical tool call when
the preceding three successful calls returned identical content. Errors,
changed results and a new user input reset the repetition evidence. Explicit
poll/monitor/watch requests are exempt. This is bounded containment for the
observed pattern, not a general solution to model reasoning loops.

The installed-Pi fixture verifies that the fourth duplicate is blocked and
the turn aborts, in addition to malformed-call recovery and retry limits.
Unit checks cover changed results and explicit monitoring. No model-driven
long-task qualification has passed since this change. The user's game is
the local model's task; launcher development and verification must not
silently substitute operator-written game changes for model performance.


## Follow-up loop and pause reporting

The next user-driven run again repeated one reasoning passage and the same
read. The guard blocked the fourth identical read and Pi surfaced its abort
as an error. Hub classification now records a live guard notice and labels
that abort **Repetition paused** (including the stopped tool), while an
unrelated connection/provider error remains **Failed**. Historical notices
cannot mask a later error; the marker resets when a new agent turn starts.
The installed-Pi fixture verifies the resulting summary and tool labels.

The first diagnostic requests labelled “AR” were not valid AR controls:
MTPLX ignored their requested generation mode because they carried its managed
`pi` client hint. The short checkpoint fixture passed, but it did not establish
an AR/MTP comparison. Likewise, the first full-history replay did not establish
that comparison. Those earlier interpretations are withdrawn.

A later control explicitly enabled client controls and checked the returned
`mtplx_stats.generation_mode`. With genuine AR, temperature 0 and context-copy
disabled, the 11,329-token current-round replay still returned the identical
321-token repeated read. MTP also repeated it with context-copy disabled, at
both effective temperature 0.6 and 1.0. All returned game calls were left
unexecuted. Disabling context-copy did not resolve this failure and the
experimental default override was removed. A clean checkpoint changed the
reasoning but exhausted its 2,048-token diagnostic limit; it is not a recovery
success and no automatic checkpoint replacement was shipped.

## Restart identity and actual sampling ownership

Pi compares provider, model ID and API before retaining an earlier thinking
block as reasoning. The launcher previously included the process run ID in
its Pi identity. Restarting the same model therefore looked like a model
switch and Pi converted previous thinking into ordinary answer text.

The Pi identity is now stable for the same backend and model artifact. A
provider request hook maps that stable ID to the current transport's served
model ID. Different artifacts/quantizations/backends remain distinct. The
installed Pi conversion test reproduces the old failure and verifies the fix
for both Qwopus/MTPLX and Qwen 6-bit/oMLX. Existing historical session records
are not rewritten; this fix protects future same-model restarts.

Separately, MTPLX treated the `pi` hint as an MTPLX-managed client and ignored
the authenticated launcher's validated sampling values. Qwopus's configured
model temperature was 1.0, but runtime telemetry showed 0.6. The session relay
now identifies itself as `llm-launcher` and explicitly enables request
controls after validation. It preserves the Pi session ID/cache affinity and
removes client generation-mode/draft-depth overrides, leaving acceleration
with the launched engine. Native MTPLX policy tests reproduce the ignored
controls and confirm the corrected ownership. Correct sampling alone did not
resolve the already-looping replay; this is a real contract fix, not evidence
of universal task recovery.

## Fresh coding comparison

The disposable TTLCache fixture restricts native Pi tools to the implementation
and fixed read-only tests. Returned game actions are never run. With Qwopus at
xhigh, 128K context and MTP depth 3, the first fresh run completed in 67.16s:
seven initially failing tests became eight passing tests, with five tool calls
and no intervention. Its 24,812 input tokens included 18,381 cache reads;
output was 1,643 tokens. This initial run preceded the sampler correction and
used the temporary context-copy-off diagnostic. It does not qualify the final
production route or the long failed session.

The 6-bit Qwen model completed the same fixture on oMLX DFlash depth 5,
Q6 KV and Q8 draft at xhigh/128K in 214.32s, also with all eight tests
passing and no intervention. It used 35,014 input tokens (28,975 cached),
5,478 output tokens and five tool calls. Neither fresh run repeated an
identical read. Their elapsed times are task results, not pure decode-speed
benchmarks; the generated reasoning lengths and initial sampling differed.

A read-only replay of the same stalled current-round history also caused the
6-bit model to propose the identical read (`offset=120, limit=30`), with 336
output tokens in 37.86s. Its native tokenizer counted 11,288 prompt tokens.
This is evidence that this history trap is not unique to Qwopus/MTP; it is
not a claim that independently running Qwen would always enter that trap.

## Additional failures under the corrected production sampler

The first fresh fixture at effective temperature 1.0 with MTP/context-copy
both active stopped after announcing its implementation, without editing.
It failed qualification (128.84s, 3,556 output tokens). A later run printed a
truncated `{"name": "run_tests>` tool wrapper; it also failed qualification.
These are retained as failures, not folded into the initial passing result.

The workflow now retries a narrow immediate-action preamble once, only after
native tool work has begun, with exclusions for planning/examples and conditional
offers. It also recognizes a truncated active tool name in a broken JSON
wrapper. Printed text is never executed. Native Pi fixtures verify real tool
execution after each recovery and the retry limits.

Manual compaction immediately after a repetition pause now recomputes Pi's
native cut point with no verbatim recent-message retention. Previously the
normal retention could keep the entire failed round outside the summary.
The native summarizer still owns the handover and file bookkeeping; the
original session entries remain saved. This special cut is skipped after a
new user message or a subsequent compaction. Native cut-point tests verify
that confirmed tool output and the user request enter the summary while the
repeated reasoning is removed from the retained tail.

MTPLX Pi housekeeping summaries now use a 4,096-token maximum without extra
thinking, matching the existing oMLX summary policy. Ordinary task reasoning
and output allowances are unchanged. This is a bounded recovery operation,
not an automatic promise of long-task completion.

Pi's native summary generation bypasses its normal provider request hook.
The first live compaction check exposed that the new stable identity was
therefore rejected by the relay. The relay now also resolves the one verified
stable alias to the loaded model, including attached Pi surfaces; arbitrary
model IDs remain rejected. Native overflow/summary/retry tests assert that
the summary arrives with the stable ID and reaches the upstream served ID.
The failed initial compaction created no checkpoint and left the transcript
unchanged. Relay source changes now also mark the controller as needing a
reload, preventing an old relay from being mistaken for the edited version.

## Final live checks

The corrected native loop compaction completed on the user's saved session
in 237.27s. It summarized a context reported as 53,524 tokens, retained only
one old suffix entry, and saved an 8,938-character handover containing the
movement/audio request, `game.js`, completed work and next steps. Pure native
Pi context reconstruction now produces three wire messages for a continuation,
with no verbatim reasoning messages. Original session entries and a separate
pre-compaction backup remain available; no game tools were executed by this
recovery operation.

A subsequent fresh Qwopus coding check passed all eight fixed tests without
intervention in **130.13s**, with five tool calls. It used **30,125 input tokens
(23,800 cached)** and **4,226 output tokens**. The real relay/native runtime
reported **MTP, temperature 1.0, client controls honored, context-copy active,
reasoning on**. The session used xhigh/128K, depth 3 and full-precision KV.
A narrow planning-exclusion correction followed this run: protecting tests
must not be misclassified as a request to avoid implementation. That correction
passed native Pi recovery tests, not a repeated full model benchmark.

The final pass does not erase the preceding premature-stop and malformed-tool
failures. These single task results support bounded local verification, not
“perfect” reliability or an intrinsic intelligence/speed ranking. Numeric/task
receipts are in `build/qwopus-coding-receipt.json` and
`build/qwen6-coding-receipt.json`; the two failed diagnostic receipts are also
retained in `build/`. The GPU ceiling was directly checked as 40,960 MiB.

A read-only continuation from that native handover used **3,956 prompt tokens**
and proposed a fresh file read rather than the repeated `offset=120, limit=30`
call. It completed the proposal in 36.89s with 903 output tokens. The proposal
was not executed. This confirms a changed next step and smaller active context;
it does not establish completion of the movement/audio game task.

## 2026-09-07: decode tuning and Hub overhead

On the M5 Pro / 48 GiB host, the installed Qwopus artifact is MXFP4 (4-bit,
32-element groups), running MTPLX 2.11.1 / MLX 0.32.2. These comparisons kept
128K context, xhigh, temperature 1.0, full-precision KV and the existing memory
limits. They used the same 28,346-token synthetic scheduling prompt, seed 731,
and 384 generated tokens per arm. No model tool calls were executed by the
benchmark.

Sustained/Turbo/Turbo/Sustained yielded native `decode_tok_s` of 23.68, 22.83,
22.92 and 20.55 respectively. Cache warmth and run-to-run drift differed; this
is not convincing evidence for promoting Turbo. The runtime also reported a
failed packed-GQA self-check and safe stock-kernel fallback. Sustained stays
selected.

Depths 3/2/1/1/2/3 yielded native `decode_tok_s` of 20.91, 22.85, 20.29, 20.44,
22.91 and 18.67. Native `tok_s` (a different timing window) was 20.93, 22.90,
20.34, 20.48, 22.96 and 20.75. Depth 2 therefore showed a repeatable gain of
roughly 10% on the latter metric, with only one context-copy token in each
384-token sample. It becomes the saved Qwopus tuned preset; this is a narrow
throughput comparison, not a general quality evaluation or a guarantee of
this rate at the user's longer current context. Numeric receipts are in
`build/qwopus-depth-tuning-results.json` and
`build/qwopus-profile-tuning-results.json`.

The Hub now prefers native decode telemetry to Pi-token-speed's estimate.
When only Pi's estimate is available it is explicitly labelled as such;
prefill speed remains separate. Completed timeline cards are retained during
streaming instead of rebuilding every message. Status unit tests, timeline
and console-tab tests, and the real installed-Pi browser fixture passed.
The browser fixture additionally checks completed-message DOM identity during
streaming, preserving scrolling, queue, stop/recovery and saved transcript
coverage. Its menu/visible-button checks were updated to match the current UI.

Applied depth 2, saved `Qwopus · tuned D2`, and resumed the original saved Pi
session. The first resumed request processed 43,146 prompt tokens; native
MTPLX reported 391 generated tokens at 20.99 decode tokens/s. Safari then
showed **20.7 tok/s · engine**, **379.5 prompt tok/s**, and the retained
43K-token context. This is a live sample, not a completed-task average.
The user's unsent `15` draft was preserved. The game project was not edited
by this tuning work; its original Pi task owns subsequent game changes.

## 2026-09-07: malformed command retry recovery

The subsequent live task failed after Qwopus returned the same malformed,
deeply escaped command as text on the initial attempt and both retries.
This was a tool-format stop, not a process or RAM crash. The retries previously
replayed the invalid assistant answer and reasoning alongside generic feedback.

The Pi context hook now replaces only malformed assistant entries adjacent to
launcher format-recovery/error notices with a short non-execution notice in
model-facing context. Persisted messages and the visible transcript remain
unchanged, as do native tool calls and confirmed results. Unflagged examples
are untouched; cleanup does not cross user messages. Both notice/assistant
persistence orders are handled. This also works after a session restart.
Recovery guidance now asks for a smaller action and correct escaping; for the
Qwopus model it repeats the tool delimiters from its installed publisher
template. Invalid command text is never executed or repaired into executable
code. Retry limits remain two.

Unit checks passed, including saved-history immutability and example exclusions.
The installed-Pi integration fixture passed native retry execution, outgoing
context cleanup, visible history retention, and bounded failure/repetition
checks. A read-only check of the user's saved entries identified five historical
flagged attempts eligible for cleanup. Live task continuation is checked
separately below; fixture success alone does not establish model reliability.

Live continuation after activating the fix produced a native `bash` tool call
and a corresponding tool result with `isError: false`. The command generated
the intended collision diagnostic instead of being printed as malformed JSON.
The diagnostic still reports a failing game test; tool execution recovery does
not establish completion of the game task. Pi continues that existing task.
The launcher was restarted as required by its source-version guard, restoring
depth 2, 128K context, full-precision KV and the same saved session. No game
files were edited by the launcher repair work.

## 2026-09-07: interrupt repeated reasoning while streaming

The user observed large blocks of verbatim reasoning repeated during decode.
The previous guard covered identical tool calls, leaving this failure mode
unchecked. The response was stopped through the Hub before applying repairs.

Pi now checks a bounded 16K-character reasoning tail every 512 new characters.
It interrupts only when long, varied prose paragraphs occur at least three
times, total at least 2,400 characters, and dominate at least 65% of the tail.
Fenced code, short token runs, changing diagnostic values, and ordinary answer
text are excluded. This conservative exact-repetition guard is not a general
semantic-loop detector. It emits the existing repetition-pause notice, cancels
native generation, and never automatically retries the same stream.

Model-facing context omits detected repetitive thinking blocks while retaining
real tool calls, results, and the original saved history. A restored unfinished
turn containing a detected loop receives a compaction marker; existing native
Pi compaction can then produce a handover without verbatim recent-turn
retention. Existing user/compaction boundaries prevent marking unrelated work.

Unit tests and an installed-Pi SSE fixture passed: upstream generation was
cancelled before completing the repeated stream, the Hub reported Repetition
paused, no automatic retry occurred, and the next request omitted the loop.
Native compaction cut-point tests also passed. Replaying the user's latest
61,745-character reasoning block through the detector triggered at 4,608
characters. An earlier 58,207-character block triggered at 39,424 characters;
its earlier non-identical analysis is outside this guard's exact-match scope.

The root-cause audit found 168,989 characters of historical reasoning in a
reconstruction of the failed request (87,581 before the latest user message,
81,408 after it). This is not evidence that preserving healthy reasoning is
wrong: Qwen3.8's publisher explicitly recommends preserved thinking, whereas
the packaged Qwopus template contains an older rolling checkpoint. The current
compatibility template remains in place pending quality evidence; it is not
blindly rolled back to save tokens.

A second feedback path was confirmed: native Pi summaries bypass the ordinary
context hook and serialize assistant thinking. The Hub now applies the same
selective repetitive-thinking cleanup to native compaction preparation, after
Pi selects the cut. File bookkeeping, healthy reasoning, messages, tool results
and the saved transcript stay intact. Installed-Pi and unit checks passed.
An installed-MTPLX canonicalization test additionally verifies that the visible
recovery marker prevents cached reasoning from being substituted back into the
cleaned turn. Merely omitting the reasoning field would not provide that
protection on a matching warm native session.

Reference checks: Qwen3.8's model card documents preserved thinking and warns
that lower effort can increase retries; Qwopus's own card acknowledges residual
reasoning loops. These statements do not prove the cause of this specific
sample:
- https://huggingface.co/Qwen/Qwen3.8-27B
- https://huggingface.co/Jackrong/Qwopus3.8-27B-Flash

Controlled replay results (standard Pi prompt/tools reconstructed at the saved
failure boundary; fixed seed 731; output cap 1,536; no proposed tools executed):

| History | Decode | Input tokens | Output tokens | Result |
| --- | --- | ---: | ---: | --- |
| Full reasoning | MTP D2 | 82,236 | 241 | Native edit proposal, valid arguments |
| No historical reasoning | MTP D2 | 30,494 | 51 | Native bash proposal, valid arguments |
| No historical reasoning | AR | 30,494 | 51 | Same bash proposal, valid arguments |
| Full reasoning | AR | 82,236 | 69 | Native tool proposal |

None reproduced the original reasoning loop. This is not a bit-exact replay
of the unknown original random seed, nor a completed-task quality evaluation.
It does not establish the initiating model/runtime cause, prove all historical
reasoning harmful, or justify disabling MTP. The implemented policy removes
only detected repetitive reasoning, retaining healthy reasoning. The numeric
receipt is `build/qwopus-repetition-replay-receipt.json`.

The first attempt at the second arm hit MTPLX's memory-pressure guard (HTTP
507); the engine stayed up. Later arms used cleanup limited to this diagnostic's
four named sessions. Broad shared-cache clearing was rejected by automatic
approval review and was not performed. The successful outputs are too short
for throughput qualification, and prefill cache warmth differed.

The real clean-handover compaction completed from 99,361 reported tokens with a
4,246-character summary. Its assertion that seven tests passed after the latest
edits was not supported by the recent recorded results, so continuation includes
an explicit correction requiring current verification. The task is not marked
complete based on that summary. Future compactions now receive targeted loop
cleanup too; this does not guarantee factual perfection of model summaries.

Final activation restored the original Pi session with the corrected handover
instruction, MTP D2, 128K context and the existing memory limits. Safari showed
11,619 / 131,072 context tokens while the resumed task performed five distinct
native reads with successful results. This confirms restored tool progression,
not game completion or elimination of every possible model loop. The original
loop's initiating cause remains unproven by the four bounded replays.

## September 7: independent tool-format failures

The 14:41 Safari failure was a stopped Pi task, not an engine crash. The
received edit wrapper was missing its outer closing JSON brace; the installed
Pi edit tool does support the `edits` array used in this request. A native edit
executed successfully between the two latest malformed answers. The launcher
incorrectly counted format retries across the entire user prompt instead of
ending a failure episode after a confirmed successful native tool result.

Recovery now permits two retries per unsuccessful episode, plus a six-retry
ceiling across the user prompt. Only a real successful tool result resets the
episode counter; errors, missing results, automatic continuations and compaction
cannot reset the overall ceiling. Printed malformed commands remain unexecuted.
The recovery instruction also explicitly calls out closing the outer JSON object.

Exhausted recovery now settles as `Tool call failed`, retaining token totals and
pausing queued work, instead of treating the malformed final text as `Complete`.
Saved-history rendering recognizes the terminal notice on either side of the
failed assistant entry. Historical notices cannot change a live turn's state.

Regression coverage includes three malformed-answer/successful-tool episodes
within a single real installed-Pi prompt, consecutive failure bounds, the overall
retry ceiling, and both live/persisted notice orders. This fixes recovery and
status handling; it does not establish why the model originally generated
malformed JSON or solve its broader unproductive debugging trajectory.

Validation passed: workflow unit checks; 16 passing prompt-summary, notice,
steering and saved-history checks (one separate opt-in check skipped); and the
installed-Pi integration fixture. Activation restored the same original session
under run `ca364dfc-2852-40f7-90e7-5b982623f817`, with xhigh thinking, MTP D2,
128K context and unchanged memory settings. The resumed task executed a native
bash call, again confirming six passing checks and the unresolved tile-83.4
bot failure. Safari was refreshed to the restored route and its unsent draft
preserved. This is verified recovery, not verification that the game is complete.
