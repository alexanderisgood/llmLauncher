# Changelog

All notable public changes are recorded here.

## Unreleased

- Reversible local actions no longer ask for a redundant checkbox: Route Check, Calibration, ANE measurement, runtime comparison, and ordinary Session Set opening now start from their clearly labelled action button. Extra confirmation remains for downloads, installs, large-file creation, destructive deletion, experimental routes, and memory-risk overrides.
- Cooling is now a user-owned safety setting. Apply fastest preserves it, Calibration defaults to Automatic, and maximum fans requires an explicit loud-mode selection.
- Calibration evidence includes the selected cooling policy, preventing maximum-fan results from being applied to normal-cooling routes.
- LM Studio MLX models now load through the canonical identifier in its local model index, including quantised aliases such as `model@6bit`; stale catalog failures now give an actionable Rescan message.

## 1.66.0-alpha.2 - 2026-08-24

First public alpha.

### Included

- Unified model routing across oMLX, LM Studio, and MTPLX.
- Pi, OpenCode, Codex, and built-in streaming Chat work surfaces.
- Capability-aware model library, route validation, local profiles, Session Sets, and warm-route attachment.
- Chat thinking separation, TPS, message queuing, history, search, branching, drafts, and interrupted-turn recovery.
- Calibration, benchmark evidence, fastest-safe settings, engine shootouts, DFlash 2 setup, and guarded ANE tuning.
- Graphite, Daylight, Ember, and Midnight appearances with Focused and Detailed information levels.
- Authenticated loopback bridges and launcher-owned process cleanup.

### Alpha limitations

- macOS-focused and not yet packaged, signed, or notarized.
- FreeToken support is retained behind an off-by-default UI feature flag.
- Runtime compatibility and saved-data formats may change before a stable release.
