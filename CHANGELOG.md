# Changelog

All notable public changes are recorded here.

## Unreleased

- Hub Console now preserves its newest transcript rows when the window or status area changes size, consumes a final Pi JSON event even if the process exits before its trailing newline, and periodically reconciles Pi's authoritative streaming state so a missed settle event cannot leave the composer stuck on Queue. Pi extension confirmations, choices, inputs, and editor requests now appear as answerable inline cards instead of silently blocking the agent.
- Harden Mference admission to its real `.gturbo` contract: bounded regular metadata, pinned production architecture signatures, exact manifest/receipt binding, safe paths, matching file sets/sizes/hashes, and complete non-empty expert-layer payloads are now required before the route is advertised. Mference launches now send the served model ID and one of its six supported fixed context windows; SSD Calibration visibly uses and applies the largest common window instead of failing later on the generic 131,072-token default. SwiftLM admission now includes its released Qwen3-Next family, while the distinct Qwen3.8-Flash-Next architecture remains blocked.
- Add an optional **Huge models on SSD** lane with registered SwiftLM and Mference adapters, model-family admission, native expert-routing controls, and Pi/OpenCode/Chat compatibility. Oversized-MoE Calibration now compares only those two SSD runtimes, uses fresh cold-to-warm stages, reports generation TPS/TTFT/memory/thermal evidence, and reuses the applied result across MLX and `.gturbo` artifacts only when both carry proof of the same immutable source revision. Qwen3.8-Flash-Next is detected but fails closed until an upstream engine explicitly supports its new architecture.
- Calibration no longer preserves a slower third-place current engine merely because the first two engines are inside the 3% noise threshold. It now forms an explicit leading group, keeps the current route only when that route belongs to the group, otherwise recommends the raw leader without claiming a unique winner, and labels the completed action clearly as **Apply result**. Applying the matching result is covered as a reusable handoff, so the fastest-settings action does not request the same calibration again.
- Pi now uses its supported structured RPC protocol inside Hub Console instead of a redraw-based terminal screen. The Hub restores the current Pi session transcript, keeps thinking, responses, tool calls/results, and launcher-owned queued follow-ups in distinct append-only lanes, changes Send to Queue while Pi is responding, and provides explicit Clear queue and Stop response controls even on installed Pi builds that predate its own clear-queue RPC command. Model-supplied control bytes are made printable rather than allowed to erase the transcript; Terminal mode remains available for Pi's full native TUI.
- Correct ANSI `CSI 3J` handling so a terminal request to clear scrollback no longer erases the visible screen.
- The audited oMLX installer now rebases every generated virtual-environment launcher before atomic promotion, repeats the full smoke suite from the final installed path, and records final-path verification in its manifest. A failed promoted copy is removed without touching the selected rollback, non-zero `--version` output can no longer masquerade as a valid runtime, and official provenance is trusted only when the final command reports the exact audited version.
- Frost now keeps its capped desktop workspace centred on wide displays, and Focused mode no longer pushes the second card in a sibling grid down by its generic section spacing. Header, dock, and dialog control-height regression checks remain in place.
- Add **Frost**, an optional polished light appearance with restrained translucent bars, Mac-style grouped surfaces, native blue controls, softer dialogs, clearer Chat reasoning/answer lanes, and consistent light treatment across launcher and management flows. Hub Console now keeps its entire workspace—not only the terminal viewport—black in every appearance.
- Cross-engine Calibration now performs the bounded engine-specific search instead of timing one arbitrary accelerated preset: LM Studio evaluates up to ten MTP depth/minimum/cutoff candidates, oMLX evaluates up to ten DFlash block/verifier/draft-precision candidates, and MTPLX still checks every verified draft depth. Plans disclose worst-case reload/request counts as **up to**, live progress names the exact candidate and TPS, and only a complete correctness/resource-gated sweep can be saved or applied.
- Engine Calibration now reloads MTPLX at every verified MTP draft depth (D1 through the artifact maximum), correctness-gates each depth against AR, and compares the fastest valid depth with the other engines. The read-only plan includes those extra reloads/requests, live status names the active depth, completed results show the exact winning depth, and Apply fastest restores that measured depth instead of reverting to the artifact default.
- Calibration now shows every engine's measured result and generation TPS, keeps live generation TPS visible while testing, and preserves the chosen cooling mode when reopened. Saved evidence is grouped by one completed shootout instead of mixing newer routes from another run, and a route that starts with more free memory than the shared reference remains usable. Apply no longer reopens Calibration in those cases; worse memory, thermal drift, power-mode changes, and cooldown timeouts still fail closed.
- Keep an explicit **Retest engines** action after Calibration finds a saved result, while making **Use result** the primary action.
- Calibration now turns completed engine measurements into a usable result even when backends differ by one terminal token or choose different valid greedy wording. Exact parity remains required inside each engine before an accelerator can win; cross-engine results instead require the same model/input contract and tightly bounded token-count drift.
- The final ranking now honours the resource-settling gate that every route already passed, instead of rejecting the matrix again with a stricter pairwise memory check. Existing matching measurements become usable without rerunning them.
- Calibration has one clear Result area in Focused mode, never presents “completed” and “measurement needed” together, and disables the test button while a completed result is being reloaded. Its performance drop-up is reduced to fastest engine, test/review, and checked launch choices; the other ranking goals remain in Calibration.
- A controller that is still running older Python source now blocks new launches, measurements, downloads, runtime changes, and Session Set opens immediately with a restart message instead of executing stale routing code.
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
- Frost, Graphite, Daylight, Ember, and Midnight appearances with Focused and Detailed information levels.
- Authenticated loopback bridges and launcher-owned process cleanup.

### Alpha limitations

- macOS-focused and not yet packaged, signed, or notarized.
- FreeToken support is retained behind an off-by-default UI feature flag.
- Runtime compatibility and saved-data formats may change before a stable release.
