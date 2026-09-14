# Qwen3.8 27B route investigation — 7 September 2026

> Development notes: referenced raw receipts and session captures stay local and are not included in the public release. Measurements below describe individual development runs.

## Failure and repair

The last Qwopus run repeated the same reasoning while the controller remained
responsive. It was stopped with its transcript preserved. This was a model
reasoning loop, not evidence of an out-of-memory crash. The investigation changes
the launcher, runtime and harness; game implementation remains Qwen's task.

The selected vendor MTPLX engine was upgraded from 2.11.1 to the official
[2.11.2 release](https://github.com/youssofal/MTPLX/releases/tag/v2.11.2), commit
`21be78b3f51820eecef020e5e4855c0715eaf9a5`. Its wheel SHA-256 matched the release
asset digest: `55482748c91fcd1992e16a58426642f5f0e0655a004785014cdd6c2822171597`.
The previous engine package and entry point were backed up before installation;
the desktop shell and other dependencies were not replaced. Native version
verification and dependency checks passed.

This machine is an Apple M5 Pro with 48 GB memory. The release's M1–M4
long-context Turbo regression does **not** explain this machine's failure.
Session-bank, restored speculative-history and verifier-allocation fixes are
relevant additional changes, but upgrading alone does not establish causality.

A separate launcher bug was reproduced: Pi runs global header extensions after
explicit launcher extensions, allowing an installed extension to overwrite
our repaired cache identity. The launcher now validates and applies that
identity at the authenticated relay boundary. The installed-Pi test reproduces
the late overwrite and verifies the old committed cache cannot be selected by
that overwrite. Normal thinking history remains intact. See
[reasoning recovery](QWOPUS_REASONING_FEEDBACK.md).

## Selected working setup

The everyday profile is **Qwen 27B · Fast thinking**: native Qwen3.8 MTPLX
Optimized Speed, medium thinking, MTP depth 3, Turbo, unquantized KV, 65,536
context and 16,384 maximum response tokens. The existing 40 GiB GPU ceiling
is unchanged. The smaller working window lets Pi's normal compaction start
earlier; 128K remains available as an explicit setting. No old Qwopus session
is silently reused. **Qwen 27B · 6-bit thinking** now uses the standard 6-bit
weights with oMLX DFlash2 at the same working limits. Actual Hub runs achieved
22.64 and 26.89 sustained decode tok/s with thinking enabled; the second also
passed native compaction and checkpoint recall. See the newer
[Hub reliability checkpoint](HUB_RELIABILITY_2026-09-07.md) for settings,
memory integration and limits of this evidence. The MTPLX-only measurements
below remain historical results, not the current 6-bit preset.

These are fixed launch profiles selected from this investigation. They are not
mislabelled as a completed cross-engine Calibration matrix or a full-capacity
qualification. Existing saved calibrations remain separate.

The final source was activated in run `d68bebe5-50fd-45e0-b33a-623674167bd3`.
The controller reports its source current, Pi reopened the saved conversation
without a new prompt, and the browser verified its retained transcript and
idle composer. The GPU wired limit was read back as 40,960 MiB.
Activation receipt (local-only evidence).

## Coding results

| Artifact / route | Trials passing all 8 unchanged tests | Task wall time | Decode on the long coding responses |
| --- | ---: | ---: | ---: |
| Optimized Speed / MTP | 2 / 2 | 87.28, 130.21 s | 32.19, 32.24 tok/s |
| Standard 6-bit / AR | 2 / 2 | 333.48, 270.09 s | 11.65, 11.76 tok/s |
| Optimized Quality / MTP | 1 / 1 | 136.40 s | 23.18 tok/s |

Speed finished this small task about 2.8 times faster on average than the
standard 6-bit route. Both reused approximately 80% of aggregate input tokens.
That task-time ratio includes different amounts of model-generated thinking;
it is not an isolated kernel speedup or a general intelligence ranking.

Quality was refused before loading at 128K because the estimate would consume
protected macOS reserve. No override was applied. Its coding trial used a 64K
engine limit; all coding agents still received the same 32K/8K fixture limits.
Quality was not subjected to the longer-context suite and is not selected as
the everyday route.

## Method

Only one model was loaded at a time. Comparisons used installed Pi 0.85.1 with
the launcher provider/workflow, fresh disposable sessions and projects,
medium thinking, model sampling (temperature 1.0, top-p .95, top-k 20),
unquantized KV, Smart cooling and the unchanged 40960 MiB GPU wired ceiling.
The optimized artifacts used native MTP depth 3 / Turbo. The installed
standard 6-bit artifact has no verified matching MTP head and used AR.

The coding task fixes a bounded TTL/LRU cache. Eight independently supplied
tests are hashed before and after; the model may modify only the source file.
Tests execute outside the model's verdict. The harness records usage and tool
calls and has a hard per-attempt deadline. This is print-mode Pi with the Hub's
provider/workflow, not a substitute for a live RPC Hub check.

Coding receipt directories: Speed (local-only evidence),
6-bit (local-only evidence),
Quality (local-only evidence).

## Longer context and cache reuse

`tools/verify_mtplx_session.py` generates a random-tagged ledger with exact
answer oracles. Each suite checks a cold prompt, retained-thinking follow-up,
a changed fact in the prefix, a separate session, and its cached follow-up.
The model must return exact JSON, retain actual reasoning and finish naturally.
The edited-prefix case must read the corrected value, not the old cached fact.

Both the 21.8K and 36.3K suites passed all five checks on Optimized Speed.

| Prompt size | Cold prefill | Decode across checks | Warm first output | Peak MLX memory during suite |
| --- | ---: | ---: | ---: | ---: |
| 21.8K | 437–442 tok/s | 34–38 tok/s | 1.05–1.08 s | 31.85 GiB |
| 36.3K | 414–416 tok/s | 30–33 tok/s | 1.27–1.47 s | 36.07 GiB |

Warm follow-ups reused over 98% of input tokens. The largest actual prompt was
36,613 tokens, with the engine configured for 131,072 context. These checks
are **not** a full 128K capacity qualification or a long-task intelligence
benchmark. Peak MLX memory is native engine telemetry, not whole-system RSS.

Receipts: 22K suite (local-only evidence),
36K suite (local-only evidence).

## Source verification

- Launcher controller regression: all cases passed after updating the manual's
  stale release-link assertion; 10 optional cases remain skipped.
- Installed Pi with an actual late header hook verifies recovery affinity,
  damaged-context removal, valid tool execution and bounded retry/stop handling.
- Installed MTPLX/Qwen tokenizer verifies legitimate reasoning preservation and
  unchanged prompt prefixes across a follow-up; no weights loaded by that check.
- Real-browser/installed-Pi fixture verifies streaming, scroll detachment,
  queueing, reload after journal overflow, stopping, resuming and retained history.

## Live harness findings

The bounded coding passes did not establish open-ended task quality. An initial
live Speed session accepted steering but exhausted its 4096-token medium
thinking allowance guessing constants. A later session spent time writing and
repairing browser setup code, then found its own measurements invalid. Both
transcripts were preserved; neither is counted as successful task verification.

Inspection accounting also had a concrete defect: `cd project && grep ... | head`
reset the inspection counter as if work had been executed. Common read-only
pipelines are now recognized; unknown shell syntax preserves confirmed
inspections, while edits and executable checks reset the streak. A regression
reproduces twelve distinct reads interleaved with unknown syntax and verifies
the bounded reminder. This is advisory accounting, not a shell permission rule.
Workflow guidance now asks for retrieved evidence for external specifications
and numerical constants.

Low thinking retained a 2048-token allowance. Both coding trials passed in
110.85 and 187.85 seconds; the second needed seven requests/tool calls, versus
four on each medium trial. It did not improve time to a correct result in this
screen, so medium remains the default.
Low-thinking receipts (local-only evidence).

The reusable-browser session (`864122e2-0648-4abd-aab9-90338153c463`) used the
same 64K/16K medium-thinking Speed profile. After a prompt at approximately
21:32 UTC, its first real browser open occurred at 21:32:46; it finished
naturally at 21:40:57 on 7 September 2026. It required no generated browser
setup script. Its final timing explanation was unsupported: it inferred
simulation behavior from `update(1)` and `requestAnimationFrame` while ignoring
the accumulator. Browser access reduced setup overhead, but this run does
**not** prove reliable open-ended reasoning or a successful game verification.

## Browser tooling and everyday UI

Pi now gets one `browser_check` tool when Playwright is already installed. It
owns a separate headless Chromium browser for page inspections, native input
and measurements. It installs nothing and leaves the user's browser alone.
Failures propagate as failed Pi results; partial initialization is cleaned up,
output is bounded, and cancellation, timeout and session shutdown close the
browser. Real-Chromium and installed-Pi protocol tests cover these contracts.

The implemented and tested `sequence` action runs up to six existing actions
without model delay between input and measurement. It stops on the first
failure and disallows nested sequences. This addresses timing interference
between separate tool calls; it does not establish that the model's experiment
or explanation is correct. Native `press`, `click` and `fill` use browser input;
synthetic `dispatchEvent` calls are not evidence of trusted gestures.

Home now exposes Sessions, Models and one Advanced menu. Fastest-engine selection
stays beside the model. Basic Settings opens limits/reasoning; engine tuning and
diagnostics stay collapsed. The Hub removes the global banner and single-session
tab, keeps useful metrics in one bar, and puts copy/compact/queue cleanup in the
overflow menu. Home and Return to Pi preserve the active session. A real browser
fixture verifies desktop/mobile layout, keyboard details/overflow focus, themes,
scrolling, queue/recovery and stop behavior.

## Scope of the evidence

Whole-response native decode measurements include reasoning and answer tokens.
Short-window bursts are not used to rank routes. Small coding and generated-fact
checks can reject broken configurations, but cannot establish reliable completion
of every long task or universally higher accuracy for one quantization. No game
implementation was written by the launcher agent, and no further game work is
part of this launcher investigation.
