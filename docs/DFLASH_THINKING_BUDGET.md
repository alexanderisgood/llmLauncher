# DFlash thinking budget — 8 September 2026

> Development notes: referenced raw receipts and session captures stay local and are not included in the public release. Measurements below describe individual development runs.

The 7 September speed screen confirmed acceleration the user already had.
It was not a new speed optimization. This repair addresses a separate,
reproduced source defect: the selected thinking limit never reached DFlash's
sampler.

## Cause

oMLX 0.6.4 resolves `thinking_budget` from the request or model settings and
passes it to its engine. Its DFlash implementation ignored that parameter;
`dflash-mlx 0.1.10+omlx.7` exposed no matching processor hook. A configured
medium/4096 request could therefore continue thinking beyond 4096 tokens.
Checking model settings or the UI did not demonstrate enforcement.

The saved game investigation also contains a distinct causal reasoning error:
the model blamed a render callback rate without reading the enclosing fixed-step
loop or all code that writes the position. Its own recorded trace contradicted
that conclusion. The source was not truncated by the launcher. That failure
occurred on MTPLX and is not explained by this DFlash-specific budget bug.

## Repair

The audited native patch passes a request-local logits processor through oMLX
and DFlash. It reuses oMLX's existing thinking-budget processor, constraining the
**target distribution before sampling**. The first token, speculative batches
and internal autoregressive fallback all use the same policy. Rejected draft
branches restore their processor state; they cannot consume the committed
history's budget or falsely close thinking. Unchanged logits are returned
without a concatenate operation.

At the selected limit, the native processor emits the normal thinking close
sequence, allowing the answer or tool call to continue. Natural earlier
completion remains possible; thinking is still enabled. UTF-8 partial tokens
are completed before forcing the delimiter. Each request starts fresh, even
when its prompt comes from a prefix cache. Native cached logits remain raw.
Cancellation closes the underlying native generators.

This patch is specific to the audited oMLX 0.6.4 and dflash-mlx build. The
DFlash2 linear speculative path is covered; the DFlash1 tree path explicitly
rejects the budget. An oMLX model-eviction/image fallback also rejects it rather
than silently dropping the limit. These are not supported by the launcher's
selected guarded, text-only DFlash route.

Installation validates exact before/after SHA-256 hashes, stages and parses all
modified Python files, preserves original native sources, and rolls back file
replacement errors. Future managed 0.6.4 installs apply the patch before their
smoke checks; verification rejects an unpatched runtime. The official wheel's
provenance stays intact, with the local patch recorded separately.

## Completion and rendering repair

A bounded replay exposed two additional upstream defects. DFlash returned
`stop` when it exhausted `max_tokens`, and oMLX's recovery parser copied an
unterminated thinking block into the answer. This made an incomplete response
look complete and displayed the same reasoning twice.

The native engine now determines completion from committed generation IDs,
including a real EOS at the exact limit. A cutoff reports `length`. The
launcher opts this DFlash engine into strict native-thinking parsing in both
streaming and non-streaming Chat Completions. Unfinished thinking stays in its
original channel and cannot be recovered as an answer or a tool invocation.
Other engines retain their existing parser policy. Hub cancellation also
explicitly closes its owned native stream before clearing preview/status state.

## Evidence

- 27 budget, patch-installation and completion/parser tests passed. These run
  the actual native processor, sampler hooks and chat SSE logic with controlled
  token events; they do not load model weights.
- 22 related oMLX regressions passed, including immediate native stream cleanup
  before event-loop shutdown. One separate optional native GPU test was skipped;
  its existing SDPA path was not changed by this repair.
- Seven direct native checks passed on the installed standard 6-bit model:
  the same sum-of-squares question with 32 and 128 thinking limits (both answered
  42,925), a valid read-only tool call, its exact random-marker follow-up using
  cached input, a natural early finish, and both streaming and non-streaming
  output cutoffs. Each cutoff returned `length`, nonempty reasoning and no
  fabricated answer or tool call. These deliberately small limits test boundary
  handling; the saved medium setting remains 4096.
- The complete Pi Hub route read a random marker from its disposable project
  and returned that exact marker with a native Complete event. No game file was
  read or changed by that check. The verifier initially selected the wrong
  transcript kind; correcting it to `answer` verified the preserved response
  without rerunning the model.

Native checks (local-only evidence),
actual Pi Hub check (local-only evidence).

- A live cancellation check closed a response after real reasoning began.
  The next request returned the correct answer in 1.45 seconds, demonstrating
  that the cancelled generation did not hold the executor. The native close
  path is also tested synchronously before garbage collection can mask leaks.

Cancellation check (local-only evidence).

These checks validate the real boundary and transport fixes, not a new decode
speed improvement. DFlash2 acceleration was already present.

## Reasoning diagnosis remains open

The reduced replay preserves historical assistant claims and selected tool
results. Its missing code can only be retrieved through a read-only fixture
tool; historical shell/browser commands are never executed. It is not a full
reconstruction of the original request or a live game task.

The initial baseline repeated the incorrect refresh-rate explanation, then
read the frame loop but used its 4096-total-output diagnostic allowance while
still reasoning. The engine's false `stop` and duplicate answer exposed the
completion defect above. A short instruction to inspect control flow and
reconcile measurements still produced an incorrect no-fault conclusion; that
experimental instruction was **not** added to the production workflow.

Providing the missing source let the model identify the double position update,
but it continued discussing secondary details. The original diagnostic's total
4096-token allowance left no space after a full medium-thinking budget. A final
replay allowed 8192 total output tokens and 300 seconds. Its first response used
the selected 4096 thinking budget, exited thinking and described the real bug,
then requested a historical tool that this read-only fixture does not expose.
The second response reached the diagnostic deadline. This is incomplete, not a
quality pass; an unavailable historical tool in this deliberately restricted
replay is not proof that the production Pi tool is unavailable.

The first final replay response re-tokenized to 4097 rendered reasoning tokens,
including parser whitespace, before its answer/tool-call transition. Exact
internal boundary behavior is verified by the native transaction tests rather
than inferred solely from rendered text. The 40 GiB ceiling and all production
sampling parameters remained unchanged.

Baseline (local-only evidence),
rejected instruction (local-only evidence),
source-supplied final replay (local-only evidence).

The controller and model were restarted for final native validation. Browser
visual inspection was unavailable because the Mac was locked; the actual Hub
RPC path was validated through its controller and native Pi events.

This limits excessive reasoning per response. It does not establish that the
model reasons about the right subject or that open-ended tasks cannot loop.
No game files, model weights, sampling parameters or 40 GiB ceiling are changed.

## Selected context correction

On 8 September the saved **Qwen 27B · 6-bit thinking** profile was changed from
65,536 to 131,072 context for its next launch. The selected 16,384 output limit,
medium thinking, full-precision KV, Q8 draft weights and other profiles were
preserved. The user's active graphics run remains at its original 65,536
context; neither that run nor its controller was restarted for this change.
The controller's source-freshness check therefore requires a launcher restart
after the user ends that session, before launching the updated profile.

`pi-context-policy.js` no longer installs the blanket 65,536-token compaction
trigger for oMLX model names containing 27B. Pi retains its normal 16,384-token
reserve, so a 131,072 window normally compacts at 114,688 tokens. Native memory
admission, the 8K recovery retention cap and memory-overflow compaction remain.

The installed-Pi fixture `tests.test_pi_128k_compaction` passed with the actual
27B provider naming and 128K contract: 70K and 114K reported usage do not compact,
115K triggers one compaction, and the following turn completes at 3K. It verifies
the reserve and retention settings directly and leaves persisted settings alone.
All three installed-Pi memory-recovery regressions also passed. These checks use
a local synthetic responder and load no model weights.

The capacity planner estimates a 37.5 GiB working set at the full selected
window; this is not a native admission pass or a measured capacity result.
Full-128K capacity has not been qualified, and actual native memory pressure can
require earlier compaction under the unchanged 40 GiB ceiling. No concurrent
model or memory stress test was started while the user's graphics task ran.

Saved-profile receipt (local-only evidence).
