# Pi implementation progress and shell deadlines

The September 11 archive incident exposed two gaps: native bash has no default deadline, and the existing inspection-cycle detector only sees unchanged cycles of native read/grep/find/ls calls. Changing shell commands and writes outside the project never met that detector's trigger.

The workflow now applies a 120-second default to native bash at Pi's pre-execution hook. It uses Pi's own process-tree cancellation and native timeout result; it does not restart the model or retry a command. Explicit finite timeouts are preserved for intentional long operations. Custom shell tools are not modified.

For implementation requests, the separate delivery observer compares bounded fingerprints of project source files, at most once per minute at completed-turn boundaries. Fifteen minutes and twelve completed tools without an observed source change produce one factual context note per input. Scratch files outside the project and downloaded binary assets do not count as source changes. Changes reset the observation window. Missing, oversized, or unreadable snapshots provide no evidence and reset it. Research-only requests and monitoring are excluded. A simple continuation retains the preceding task intent. Compaction does not itself count as implementation progress.

The note enters the next natural request after the confirmed tool results. It starts no evaluation call, aborts no reasoning, and does not demand arbitrary edits or declare a loop. Workflow guidance prioritises a runnable project milestone and bounded investigation of actual blockers. A source change is an observation, not proof of correctness or completion. The observer is deliberately limited: changes to source can still be unproductive, and assets/config-only work may need further research despite unchanged source.

The Hub no longer labels the agent idle solely because the model relay is idle while Pi is still streaming an agent turn.

Validation: delivery-observer and existing workflow/inspection tests; installed Pi with a simulated local provider confirms context-only notice delivery without an extra model turn; a real native shell running `sleep 180` stopped with the default 120-second timeout. No inference benchmark was used.
