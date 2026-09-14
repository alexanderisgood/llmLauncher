# Recorded browser timing causal leap

This fixture isolates a real reasoning failure from the saved Pi session
`2026-09-07T21-31-35-093Z_01a07dc8-9f35-71d7-ac82-2bf5e1daa184.jsonl`.
It is a reduced, noncontiguous replay, not a reconstruction of the entire
original provider request.

The original objective was to verify current start, movement timing and audio
behavior, fix only reproduced faults, and report limitations. The model saw
search hits mentioning `update(1)` and `requestAnimationFrame(frame)`, then
assumed one physics step occurred per render callback without reading the
enclosing loop. Later it attributed an unexpected displacement to 121 render
callbacks per second. Its own trace contradicted that explanation: velocity
increased by nine increments over 151.1 ms, approximately 60 physics steps
per second. The old final answer nonetheless declared movement correct.

`browser-timing-causal-leap.json` contains the sanitized original objective
and complete selected assistant/tool messages. The final incorrect answer is
excluded. Genuine earlier assistant speculation remains, including its tool
arguments and actual measured counterexample. Project paths become `/fixture`
and tool IDs are renamed consistently; no expected answer is added to the
model messages. Native thinking is retained as `reasoning_content`.

The missing `frame` and `moveAndCollide` implementations are separately
available in `available_source`. These exact excerpts came from earlier
same-day recorded reads in
`2026-09-07T20-39-36-239Z_01a07d99-082f-77a8-9e7b-473c84bbf17d.jsonl`,
lines 19 and 21. The newest session's caller excerpt matches that earlier
source verbatim. The source and trace are historical evidence, not a claim
about the current game's files. Each contributing raw transcript record has
a SHA-256 digest and one-based source line in the provenance metadata.

The newest session had no compaction or custom-message injection, and its
saved user message matches the saved handover. The model's own narrow search
omitted the enclosing loop; the recorded result was not truncated by the
launcher. This does not prove every original native request byte: that full
wire capture is unavailable here.

For a bounded comparison, use identical current harness instructions, model,
medium thinking and sampling in both arms. Start after the final recorded tool
result. In the first arm, serve the missing source only when requested. In the
second, supply those same two source excerpts as attributed evidence, without
their diagnosis. This separates a failure to retrieve needed code from a
failure to reason over code already supplied.

Use read-only fixture tools to return `available_source`. Do not execute the
recorded shell/browser calls or point any replay at the real game. A maximum
of four new tool calls, 8,192 generated tokens and 300 seconds bounds each
future diagnostic; this leaves answer space beyond medium thinking's 4,096-token
allowance. The initial 4,096-total-token replays were too short for a full
thinking budget plus an answer;
truncation or interruption counts as incomplete. Record source reads before
the verdict, unsupported conclusions, thinking tokens and natural completion.
A paired result is diagnostic evidence, not a general reliability rate.

`browser-timing-causal-leap.expected.json` holds evaluator-only criteria and
arithmetic. **Do not include that file or this README in the model input.**
