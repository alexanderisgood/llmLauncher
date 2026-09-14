# Local harness work — 7 September 2026

> Development notes: referenced raw receipts and session captures stay local and are not included in the public release. Measurements below describe individual development runs.

## Implemented

- Pi updated from 0.84.2 to 0.85.1. Hub imports now support Pi's bundled executable and share its SettingsManager prototype. The older tested Pi remains a separate private Uzu runtime.
- Native compaction, overflow recovery, queue, abort, saved-history and bounded tool-recovery integration checks run against the installed Pi executable.
- Pi's deferred extension notices now reconcile aborted tool results and final repetition status. Unrelated errors remain failures.
- Compaction carries up to eight recent execution observations beside the generated summary. The record retains exact truncated outputs, including failed attempts and changed outcomes. It does not claim tests passed merely because a tool returned successfully. It is saved in the Pi session and adds no new user prompt or automatic continuation.
- MTPLX's reasoning choices show their actual thinking-token ceilings, bounded by half the response allowance. Medium/high/xhigh request 4,096/8,192/16,384 thinking tokens. Thinking remains enabled. Native effort markers additionally apply only where a template supports them; Qwopus's installed template has no effort markers.
- OpenCode now explicitly advertises local function tools and thinking, including interleaved `reasoning_content` replay; session-specific model IDs cannot rely on a hosted model catalogue.
- The existing local Codex Responses bridge was verified with Codex CLI 0.153.4: shell-tool execution, returned tool output, thinking replay and final completion. It now retains cached-input and reasoning-token counts. A stable local tool-use instruction supplements the existing host prompt, without fabricated tool calls or automatic retry loops. A temporary provider keeps the normal Codex configuration intact. This is local model inference through the Codex CLI, not access to an OpenAI model's weights.

## Reproducible screening

`tools/compare_local_harnesses.py` runs plain Pi, Pi with Hub workflow guidance, Codex and OpenCode against an idle, already-loaded MTPLX server. Each attempt uses a fresh disposable TTL/LRU-cache or inclusive-range project and session. Pi/OpenCode writes are confined by an outer macOS sandbox; Codex uses its native workspace sandbox; the same untouched tests independently grade the result. Harnesses run serially with a time and request limit. The relay keeps sampling consistent and gives each attempt separate cache affinity.

The Pi Hub arm tests its provider/workflow integration in print mode, not browser rendering; real RPC behavior is covered separately by installed-Pi integration tests. This small screen cannot establish general intelligence or a stable ranking. It has no game-project changes. A timeout is a failed timed completion even if an eventual longer attempt might succeed. Token totals are partial when an aborted request never returned usage; check `requestsWithUsage` and `usageComplete` before comparing costs.

## Research basis

- [Pi changelog](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/CHANGELOG.md): post-0.84.2 fixes include tool-result compaction admission and extension-message ordering.
- [Pi lifecycle tracking](https://github.com/earendil-works/pi/issues/5886): low-level agent end does not necessarily mean the session has settled.
- [Qwopus model card](https://huggingface.co/Jackrong/Qwopus3.8-27B-Flash): acknowledges loops; its reported coding battery used a different engine, quantization and thinking-off configuration.
- [Codex custom/local providers](https://learn.chatgpt.com/docs/config-file/config-advanced): custom Responses providers and local OSS routes.
- [OpenCode providers](https://opencode.ai/docs/providers/): custom OpenAI-compatible servers.

Thinking stayed enabled in every comparison.

## Results on this machine

Small inclusive-range repair, independently checked against six unchanged assertions:

| Harness | Qwopus MXFP4, xhigh, MTP depth 2 | Qwen 3.8 27B 6-bit, medium, AR |
| --- | --- | --- |
| Plain Pi | Passed, 31.54 s | Passed, 65.23 s |
| Pi with Hub workflow | Passed, 41.54 s | Passed, 64.73 s |
| OpenCode with capability fix | Passed, 44.10 s | Passed, 71.37 s |
| Codex with local tool guidance | One pass, 70.55 s; one timeout, 120.09 s | Passed, 146.16 s |

These are one attempt per cell except the two Qwopus Codex repeats. They are not equivalent model-speed comparisons: quantization, reasoning settings and acceleration differ. The 6-bit artifact has no verified matching MTP weights, so its test explicitly used AR. Advertised context was 32,768 and response allowance 8,192; the engine itself was loaded with 131,072 context. Different harness prompts/tool definitions also change the work and cache reuse. Qwopus Codex initially returned only a promise to act; that pre-fix result is retained separately in the receipts.

The harder TTL/LRU-cache repair did **not** complete within 180 seconds through plain Pi, Pi Hub workflow, or OpenCode on Qwopus/xhigh. Those interrupted runs have incomplete token usage. Switching harnesses has therefore not demonstrated a fix for long-task overthinking or looping. No controlled medium-versus-xhigh comparison on the same model/task was completed here.

For the successful Qwopus range attempts, Pi Hub reported 17,094 total input tokens, of which 14,034 were cached (3,060 fresh), versus 946 output tokens. The successful Codex repeat reported 46,275 input, 41,478 cached (4,797 fresh), and 1,611 output. Repeated input totals should not be treated as entirely fresh prompt processing. The Qwen 6-bit Codex attempt reported no cache hits; this remains an observation from one attempt, not a conclusion that Codex caching is broken.

Machine-readable, credential-free receipts: harness-results/2026-09-07 (local-only evidence). Setup failures before inference are excluded from the comparison.

## Verification and remaining limits

The launcher regression suite passed 301 tests (10 skipped). Six opt-in installed-Pi integration checks passed; the installed-Codex tool/result/thinking/cache integration check passed; 67 Uzu backend tests passed with the preserved Pi runtime. The evidence extension has focused lifecycle and restoration checks, but its effect on a long real coding task has not yet been measured. Actual model-template checks passed for both installed model artifacts.

The original Qwopus Pi launch was restored after screening with its saved Mario session, xhigh thinking, MTP depth 2, 128K context and the existing 40 GiB memory ceiling. Safari was refreshed and the saved thinking/tool transcript was visible. The comparison runner did not edit that game project. The conversation remains paused: automatic approval review rejected sending a continuation because it could cause the local model to modify the Mario project, citing the user's restriction that Qwen should build it. No continuation was sent.

## Follow-up: repeated thinking

The subsequent fresh session reproduced a reasoning loop. The investigation found and fixed missed short-paragraph cycles in the Hub cleanup and an incorrect preserve-all template override. See [Qwopus reasoning feedback](QWOPUS_REASONING_FEEDBACK.md) for controlled AR/MTP receipts, the corrected scoped contract and remaining limits. The benchmark settings above describe the earlier runs; current Qwopus launches use the reviewed publisher checkpoint.
