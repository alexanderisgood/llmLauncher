# Hub reliability and 6-bit engine verification — 7 September 2026

> Development notes: referenced raw receipts and session captures stay local and are not included in the public release. Measurements below describe individual development runs.

This checkpoint separates launcher defects from model mistakes. A failed test
is useful feedback; silently losing a tool result, repeating a malformed call
without a bound, or reporting success without a final answer is not.

**Correction, 8 September:** these runs remeasured the existing DFlash2 speed;
they did not introduce that acceleration. They verified the selected medium
setting and retained reasoning, but not enforcement of its thinking budget.
Source inspection subsequently found that DFlash ignored `thinking_budget`.
The repair and separate validation are recorded in
[DFlash thinking budget](DFLASH_THINKING_BUDGET.md).

## Repairs

- Status captures one run, relay identity and lifecycle phase before doing I/O.
  Both public snapshots recheck that identity while reading current state.
  Stop/relaunch cannot attach a previous run's speed/context to the new run.
  Stale evidence is discarded, and the next poll fills in current evidence.
- Hub and Terminal Pi now share `pi-context-policy.js`. The 16K route uses a
  4K summary reserve and 4K recent-history allowance instead of Pi defaults
  larger than that window. Larger routes and lower user preferences retain
  their intended behavior. This changes only the owned Pi process; it does
  not write global preferences or modify the installed Pi package.
- Browser actions declare their required arguments. An entire sequence is
  checked before navigation/input begins, preventing a missing argument in
  a later step from causing avoidable partial browser actions. Runtime page
  failures still propagate as failed tools; they are not disguised as success.
- Identical native tool failures no longer reset the repetition counter. The
  existing three-identical-consecutive-results limit now includes errors:
  three real failures remain visible, and a fourth identical call is stopped
  before execution. Changed inputs/results, corrective edits and explicit
  monitoring retain their behavior. No automatic retry loop was added.
- DFlash now installs oMLX 0.6.4's existing SDPA256 attention patch and supplies
  live, engine-owned memory headroom. Upstream left this integration out of the
  DFlash engine ([issue #3241](https://github.com/jundot/omlx/issues/3241)).
  Long prefill uses tiled attention only when the unfused allocation would
  exceed the existing 90% headroom budget. The provider detaches on shutdown,
  fallback, failed startup or cancellation without clearing a replacement
  engine's provider. No attention kernel or 40 GiB ceiling was changed.
- Reasoning options now have explicit canonical values. Previously MTPLX's
  descriptive budget labels also became option values, so subsequent refreshes
  disabled them and reset reasoning to `auto`. The bug also rejected a ready
  oMLX saved profile requesting `medium`. This was observed in the live page;
  API-launched model trials above retained their explicitly verified medium
  settings and were not affected by this menu bug.

## Regression evidence

- Core launcher: 302 tests passed, one expected skip.
- Status ownership: six deterministic blocked-I/O tests, plus 21 related
  telemetry, lifecycle and idle-policy regressions passed.
- Shared compaction: nine installed-Pi integrations passed, including real
  Terminal PTY and Hub RPC, saved-history resume, overflow/memory recovery,
  slash commands and reload. Six build/identity tests and JS policy tests pass.
- Installed Pi tool recovery: generated malformed calls, bounded recovery,
  duplicate execution prevention, interrupted reasoning loops and clean
  subsequent context all passed against a local simulated model.
- Real Chromium and installed-Pi browser tests passed, including rejection of
  a malformed later sequence step before its first action. The native failed
  tool replay also passed with unchanged error text and no fourth execution.
- All 22 oMLX regressions passed with loopback access. The subsequently added
  opt-in native test and seven SDPA lifecycle/routing tests also passed in the
  installed 0.6.4 runtime. Real FP16 operators agreed within 0.000184 maximum
  absolute error. Both ordinary and GQA-folded block-4 verification retained
  the fast path when their allocations fit; provider teardown was verified.
  These checks use small tensors, not model weights or artificial RAM pressure.
- Saved-profile reasoning regression passed across Whallm, MTPLX and oMLX,
  including repeated budget-label refreshes and rejection of unsupported
  engine/client levels. Related benchmark-route and calibration-lifecycle
  regressions passed.

## Live screen

`tools/verify_pi_hub.py` uses normal launch admission and the actual Hub HTTP
and Pi RPC path. Each attempt has a fresh disposable coding project, unchanged
external tests, retained thinking, a repair turn and a warm verification turn.
Only the fixture's own model route may be unloaded by cleanup. No game project
or previous user conversation is reused.

The model must observe failing tests, repair the implementation and finish
cleanly. A separate Node process checks the result and original test hash.
Passing this small fixture is not a general intelligence or long-task guarantee.

## Actual Hub results and saved route

The installed **Qwen3.8-27B-MLX-6bit** weights ran through real Pi Hub RPC with
medium thinking, 65,536 context, 16,384 response limit, model-default sampling
and full-precision KV. The saved **Qwen 27B · 6-bit thinking** profile now uses
oMLX 0.6.4 / DFlash2, block 4, DDTree verification and Q8 draft weights.
DDTree is the saved selector; this DFlash2 runtime actually follows its linear
speculative sampler at the configured temperature, not its DFlash1 tree path.
Its project and other controls, and every other saved profile, were preserved.
The controller was restarted with current source. The real browser applied
this profile successfully after the reasoning-menu fix and returned to Home
showing oMLX, the 6-bit model, medium thinking and 64K/16K limits with Launch
enabled. DFlash is selected; no model or user task was started by that action.

Update, 8 September: the saved **Qwen 27B · 6-bit thinking** profile now selects
131,072 context, with its other settings unchanged. The former blanket 64K Pi
compaction trigger was removed; the standard 16K reserve now gives a 112K
threshold. The user's already-running 64K graphics session was left untouched.
The measurements below remain historical 64K-profile results, not evidence of
full-128K capacity. The 40 GiB native ceiling remains enforced.

| Route | Sustained decode | Repair wall time | Peak engine physical footprint |
| --- | ---: | ---: | ---: |
| MTPLX 2.11.2 AR | 10.87 tok/s | 356.36 s | 30.67 GiB |
| oMLX 0.6.4 AR | 10.76 tok/s | 341.06 s | 30.08 GiB |
| oMLX DFlash2 | 22.64 tok/s | 147.47 s | 27.06 GiB |
| DFlash2 repeat, including compaction exercise | 26.89 tok/s | 125.35 s | 35.45 GiB |

Every repair passed all eight independent, unchanged tests and reached a clean
final answer. Both DFlash runs also preserved the repaired source during the
verification follow-up. The repeat added a random checkpoint among synthetic
tool output, performed native Pi compaction, deleted that generated note, then
verified the code again and correctly recalled the marker. Its largest actual
prompt was 38,486 tokens. It unloaded cleanly; this is not a 64K capacity test.

Decode is `sum(completionTokens - 1) / sum(generationSeconds)` across completed
requests, excluding prompt processing. The repeat includes checkpoint and
compaction requests; its higher average is not a controlled extra speed gain.
These are stochastic task screens, not a general quality ranking. DFlash2 was
the expected source of acceleration; switching the ordinary engine alone was
not an optimization. The memory integration above was completed afterwards
and verified separately with native operators, not credited for these speeds.

Receipts: first DFlash Hub run (local-only evidence),
compaction repeat (local-only evidence),
native attention check (local-only evidence),
saved profile (local-only evidence).

The upstream attention wrapper still falls back to its original operator if
the tiled kernel itself errors; that upstream behavior was not replaced here.
The native kernel check passed on this device. Known launcher failure paths
are covered, but semantic model loops and incorrect reasoning remain possible.
