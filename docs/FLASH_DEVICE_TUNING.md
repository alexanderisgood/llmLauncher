# Qwen3.8 Flash on this Mac — 7 September 2026

> Development notes: referenced raw receipts and session captures stay local and are not included in the public release. Measurements below describe individual development runs.

The retained large MoE is Whallm's full 512-expert Qwen3.8 Flash-Next install.
The 288-expert REAP MLX copy was removed, releasing 73,515,222,264 bytes of
model files (about 73.5 GB / 68.5 GiB). The separate 27B models were not changed.
See the removal receipt (local-only evidence).

This is a memory-fit and expert-coverage decision. REAP's non-PLE weights
require about 38.64 GiB resident before KV state and workspaces; the earlier
8,224-token prefill reached 41.25 GiB plus a transient allocation. That does
not fit the user's 40 GiB ceiling. Whallm streams the full model's experts
and n-gram table from storage. These are different variants, not two identical
copies, and the small checks below do not prove a universal quality ranking.

## Installed runtime and defaults

Whallm was updated from 1.1.2 to the official signed and notarized
[1.1.4 release](https://github.com/yanun0323/Whallm/releases/tag/v1.1.4).
The downloaded archive matched the release's SHA-256, and the old temporary
app backup was removed after the new runtime passed the model checks.

The launcher-owned route uses 4,096 expert-cache slots, four read workers,
two prefetch workers, a 2 GiB prompt cache, 25% supported ANE prefill, and a
40 GiB native memory limit. It retains every expert and uses medium thinking.
MTP is disabled because this installed artifact has no MTP sidecar.

The initial Hub route is bounded to 16,384 context tokens and up to 4,096
response tokens. This is a conservative operating configuration, not a claim
that a 16K capacity test has passed. Whallm's published support floor is 64 GiB;
this 48 GiB Mac remains outside that published configuration.

## Device measurements

The Apple M5 Pro with 48 GiB unified memory ran one three-request trial per
cache size, sequentially. Both trials used thinking, identical generated
records, isolated prompt-cache directories and an external process-memory
watcher. Both passed exact JSON extraction, a corrected fact using cached
history, and a structured tool call, with natural completion and native
usage counts matching the response.

| Measurement | 4,096 slots — retained | 8,192 slots |
| --- | ---: | ---: |
| Uncached ledger prompt | 4,471 tokens | 4,471 tokens |
| Uncached prompt throughput | 100.8 tok/s | 103.1 tok/s |
| Ledger decode throughput | 8.0 tok/s | 8.4 tok/s |
| Cached correction decode | 8.3 tok/s | 9.5 tok/s |
| Prompt tokens reused on correction | 4,670 / 4,716 | 4,637 / 4,683 |
| Peak process footprint, including lifetime peak | 23.89 GiB | 33.06 GiB |
| Lowest reported free-memory percentage | 37% | 10% |

Doubling the cache added over 9 GiB of process memory for a modest improvement
in these requests. The smaller cache preserves room for context, the Hub and
other apps. The native memory limit stays at 40 GiB for both.

These are short device probes, not an intelligence benchmark or a sustained
agent run. Sampling is stochastic and generated lengths differ. Cold means
zero native prompt-cache reuse; the macOS file cache was not purged. Native
prompt throughput divides newly processed tokens by time to first token,
including request overhead. Decode includes native cache-evaluation time.
The tool check validates call generation, not execution of a tool result.
Full settings and count-matched measurements are in the
device receipt (local-only evidence).

## Launcher fixes

- Discover the installed full model and start an owned Whallm process from
  Launch. Verify actual model loading before reporting Ready and unload the
  owned process when the session ends.
- Bound Pi's process-local compaction settings to the selected context.
  At 16K, use at most 4K reserve and 4K recent history instead of Pi's
  inherited 16K reserve and 20K retention. Preserve smaller saved preferences
  and keep saved settings unchanged.
- Fill cached-input usage from matching native prompt and completion counts.
  Do not interpret an absent cache field as proof that all input was processed.
- Keep idle health monitoring independent of expensive Hub telemetry reads.
  Native model health checks and user-visible telemetry remain available.

The installed-Pi compaction regression checks that 8K fits, 13K triggers one
compaction, and two subsequent 3K turns complete without immediate compaction.

## Real Pi Hub check

The launcher-owned runtime also completed an isolated real Pi task: read a
60-record input file, compute the open-record count and units, write the result,
read it back and verify it independently. The result was exactly 40 open records
and 21,171 units. Two Bash tool calls and three model requests finished naturally
with thinking visible. No game project was used.

The Hub reported 22,243 cumulative input tokens, including 14,214 cached tokens,
and 505 output tokens including thinking. Actual newly processed input was
8,029 tokens. Native prompt rates appeared after prefill, with cached tokens
excluded, and the stopwatch appeared while the measurement was pending.
Peak process footprint was 24.30 GiB. This was an 8,409-token final prompt,
still not a full 16K capacity qualification.

Stopping Pi returned to Home. End session then unloaded the owned engine and
left the controller idle; Home now keeps that control visible beside Return
to Pi. The Hub receipt (local-only evidence) records
the results. The 302-test launcher suite passed with one skip, alongside the
focused native-route, telemetry and installed-Pi regressions.

The new native route enables Pi, OpenCode and Chat. Codex is withheld on this
route pending a separate Responses qualification because Whallm's current
Responses implementation buffers tool output and can mislabel output-limit
completion. Existing external Whallm and other Codex routes are unchanged.
