# Pi Hub commands

Type `/` in the Hub message box to browse commands discovered from the running Pi process. Click a command, or press Tab / Down to focus the list, then Enter to choose it. Add any arguments and press Enter to run it.

The Hub supplies `/help`, `/session`, `/name`, `/new`, `/compact`, `/reload`, `/resume`, `/fork`, `/tree`, `/thinking`, `/settings`, `/model`, `/hotkeys`, and `/quit`. Installed extension commands, prompt templates, and skills appear alongside these. `/model` explains how to change the launcher's local model route; `/settings` offers session controls. They do not change engine configuration behind the launcher.

Extension commands run immediately, including menus opened during generation. Prompt templates and skills retain normal message queuing. Session changes require an idle agent. Unknown commands produce a clear error instead of being sent to the model.

Select, confirm, input, and editor dialogs use browser controls. Text-based `ctx.ui.custom()` components, including the installed `pi-token-speed` `/tps` menu, render in a bounded panel with keyboard and button input. Escape or Cancel closes the menu. This bridge supports component rendering, input, render requests, disposal, and asynchronous completion; it does not provide full terminal emulation, images, or nested overlay APIs. Terminal-only built-ins absent from the picker are not implemented by Pi RPC and remain unavailable here.

Validation: opt-in `LLM_LAUNCHER_PI_INTEGRATION=1 python3 -m unittest tests.test_pi_slash_commands` exercises installed Pi and the installed token-speed extension with isolated settings, no tools, and no model server. It checks discovery, arguments, menus during generation, polling, cancellation, reload, and new-session history refresh. Browser verification covers command filtering, opening `/tps`, arrow navigation, and dismissal.

For oMLX Hub sessions, the in-process Pi settings adapter caps recent-message retention at 8,000 estimated tokens before native compaction preparation runs, preserving any smaller user setting. This applies to automatic and manual compaction; global/project settings and installed Pi files remain unchanged. Applying the cap only in `session_before_compact` was too late: Pi could return ‘nothing to compact’ under its default 20,000-token estimate even when actual prompt processing had exhausted GPU memory. Native summary generation, tool-pair boundaries and file tracking remain intact. DFlash Pi sessions keep one reusable in-memory snapshot, since loading a snapshot allocates another full working cache. The native memory guard remains enabled. `tests.test_pi_memory_compaction` checks that recovery completes the retry and two later requests with only one compaction, including a memory rejection below the default retention estimate. It also grows generated code until a second overflow and verifies another successful compact-and-retry.

The timeline keeps following through thinking updates, tool-card collapse, and layout changes. Only deliberate upward wheel, touch, keyboard, or scrollbar movement pauses following; scrolling to the bottom or pressing Latest resumes it. The Hub remains constrained to the window height on narrow screens. The browser fixture's `scroll` prompt exercises long thinking before and after a tall live tool card collapses.

Completed prompts show a compact summary beneath the answer: elapsed time,
Pi-reported total/input/output tokens, cached input when reported, and tool-call
count. Usage accumulates across model/tool steps and automatic retries until Pi
settles; stopped and failed prompts have distinct labels. Input includes cache
reads/writes and repeated conversation context, so this is total work across the
prompt, not occupied context. Missing usage is labelled unavailable or partial.
Browser refreshes retain the summary. Resumed history can rebuild token totals
for complete retained prompts, but does not invent an elapsed time.

The Hub uses one desktop toolbar for console tabs, route, speed, context and
controls. Less frequent controls are in the console actions menu; route details
open over the transcript. On narrow screens the toolbar wraps into two compact
rows. Thinking and code use the available transcript width.

The Prompt field shows a per-request stopwatch while preparing/prefilling and
removes it on decode, cancellation or completion. For guarded oMLX DFlash routes,
the adapter observes native `PrefillCompleteEvent` timing and computed/restored
token counts without changing the events or generation. It keeps at most 32
numeric receipts in the private run directory, matched by response ID (or one
unambiguous request start before the first SSE byte). Prompt throughput excludes
restored tokens and remains visible after generation. Until native prefill timing
arrives the UI says Waiting; it never treats total prompt tokens / TTFT as prefill
speed. This runtime observer takes effect when the engine starts with the updated
adapter. Other oMLX routes retain their existing native admin activity telemetry.

Context includes the percentage, used / total tokens, and remaining tokens.
Counts follow Pi's context estimate when available; compaction temporarily shows
Recalculating instead of stale counts, and remaining tokens never become negative.

During a response, Steer sends the composer text through Pi's native steering
queue. Pi reads it before its next model step, after the current response/tool
step reaches a safe boundary. Queue still waits until the current task finishes.
Steering acknowledgements and failures appear in the transcript, and the original
prompt remains visible alongside later steering instructions. Slash commands use
Send/Queue. The button requires a controller advertising steering support; an
older running controller shows a restart explanation rather than accepting an
unsupported action. A failed HTTP send leaves the draft in the composer.

Pi RPC uses a raw terminal stream so long JSON messages are not truncated by
terminal line buffering. Input limits count JSON-escaped UTF-8 bytes. Steer uses
native `prompt` with `streamingBehavior: "steer"`, so an instruction arriving just
after completion starts the next turn. Normal and queued prompts use `followUp`
behavior to tolerate a turn still settling. Installed-Pi integration coverage
checks long multiline Unicode messages, delivery order, and the completion race.

MTPLX packs with a declared `mlx_lm_extra_tensors.mtp_file` or nested
`mtp/weights.safetensors` are recognised using the installed runtime's native
artifact inspection. This permits MTP when the local tensor gate passes without
promoting publisher speed claims to local calibration evidence. Nested MTP
weights participate in the model fingerprint, so replacing a head invalidates
old measurements. Downloaded heads must retain the publisher's directory layout.

### DFlash allocation headroom

The launcher-owned oMLX runtime admits prefill against 90% of the current native memory limit so a request can become a compactable overflow before the native 95% eviction threshold. It copies the guard for admission, preserving the enforcer’s live settings and the kernel ceiling. Optional DFlash snapshot publication checks current active/process memory plus allocation workspace. Native generation snapshots with disk caching disabled adopt the resident arrays, so only hidden-state joining and 1 GiB workspace are added; copied or disk-backed snapshots retain twice the source array sizes plus 1 GiB. Insufficient headroom or unknown layouts still skip publication. The single retained snapshot's logical capacity accounts for the selected full-precision KV window without increasing the physical memory guard. `tests.test_omlx_memory_headroom` covers native adoption/restoration, unchanged ceilings, lower dynamic limits and allocation-free refusal. See the [8 September repair and live cache measurements](HUB_PRODUCTIVITY_2026-09-08.md).

MTPLX prompt throughput comes from its authenticated dashboard prefill progress and completed native receipts, not the flight recorder’s generation TPS. Live samples subtract cached tokens; the last observed sample remains during decode until a completed receipt supplies final compute timing. Samples are matched to exact response IDs, or one model/time-matched live lane before SSE supplies an ID. Only bounded numeric measurements are retained; dashboard prompt previews and session metadata are discarded.

Pi honours the selected context window. The former model-name-based 65,536-token
oMLX 27B trigger was removed on 8 September: at 131,072 context, the normal
16,384-token reserve gives a 114,688-token automatic-compaction threshold.
128K includes room for output; it is not 128K of input plus a response. The
8K recent-history cap, native file/tool tracking and memory-error recovery remain
in place. Actual native memory pressure may still require earlier compaction;
selecting 128K does not establish that every full-window workload fits 40 GiB.

The oMLX relay recognises Pi's exact native summarization system prompt on an
owned Pi surface, caps that housekeeping request at 4096 output tokens (or a
smaller caller limit), and disables thinking through the chat template for the
summary only. Normal coding requests retain the selected reasoning policy.

Launcher Pi sessions load `pi-workflow.js`. It appends stable coding guidance
for runnable milestones, durable handover notes, real entry-point verification
and honest completion. A bounded progress reminder is queued through native Pi
steering after 12 consecutive successful inspections or four identical reads.
Edits, test execution and ambiguous shell scripts reset the inspection streak;
there are at most two reminders per user prompt, and reminders never start a
new turn. Tool permissions and native compaction remain unchanged.

Qwopus MXFP4 Hub smoke check (2026-09-07): MTPLX 2.11.1, native MTP depth 3,
sustained profile, unquantized KV, 128K context, thinking off for the fixture.
Installed Pi read, edited and executed a small Python repair successfully in
18 seconds. The three requests after cold prefill reported cache reuse of
5220/5284, 5279/5360 and 5355/5399 prompt tokens. This is a short functional
check, not a long-context speed or model-quality benchmark. The user session
was restored separately with its original xhigh/100000-output settings.
