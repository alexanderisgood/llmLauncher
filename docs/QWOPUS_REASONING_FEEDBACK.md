# Qwopus reasoning feedback investigation — 7 September 2026

> Development notes: referenced raw receipts and session captures stay local and are not included in the public release. Measurements below describe individual development runs.

The new Mario session still entered sustained verbatim reasoning loops. This was real model output, not a browser rendering duplication: saved assistant messages contained the same paragraph 86–92 times, consumed roughly 16,400 thinking tokens apiece, and returned to the same failed check. The last native request reported 369,512 characters of assistant reasoning history. The live 116.59 tok/s reading was a short-window rate; that response's whole decode average was around 57 tok/s. Speed was not evidence of useful progress.

## Reproduced source defects

1. The Hub's reasoning cleanup ignored prose paragraphs shorter than 180 characters/35 words. The observed repeating cycle mixed short and long paragraphs, so almost entirely repetitive text failed its 65% coverage test. All six sampled long reasoning messages returned `false`. As a result neither streaming containment nor the existing next-request/compaction cleanup recognized them. The corrected detector includes substantial short prose with a stricter repeat count. The recorded motif is now caught at 3,072 characters. Fenced code remains excluded, including fences beginning outside the tail window. Saved reasoning, genuine tool calls and results are not edited.
2. The launcher's Qwopus template override removed the publisher's rolling checkpoint. That incorrectly forced MTPLX into preserve-all reasoning history instead of its scoped mode. The override now pins the reviewed publisher template byte-for-byte. Native tokenizer/encoder checks establish that active assistant/tool thinking remains, completed user rounds' thinking is omitted, and answers/tool results survive. Thinking stays enabled. This corrects cross-round amplification; it cannot alone prevent a loop within one active round.

## Bounded inference isolation

One fixed seed, temperature 1.0, top-p .95, top-k 20; same installed model/engine. A reduced fixture used one recorded audio reasoning block and its actual tool result, with no executing tools. Limit: 1,536 output tokens. Each request had independent session affinity and zero reported cached tokens. These are diagnostic requests, not a full task benchmark or an exact replay of the entire 93K prompt.

| History | Decode | Output tokens | Reasoning tokens | Largest paragraph repeat | Wall time |
| --- | --- | ---: | ---: | ---: | ---: |
| Recorded repetitive thinking | MTP depth 2 | 395 | 356 | 1 | 53.72 s |
| Recorded repetitive thinking | AR | 1,536 (limit) | 1,534 | 6 | 144.40 s |
| Repetitive thinking omitted | MTP depth 2 | 60 | 19 | 1 | 4.16 s |
| Repetitive thinking omitted | AR | 60 | 19 | 1 | 5.86 s |

The clean requests returned the same next tool call. No proposed tool executed. The result shows that MTP is not necessary for this failure and that repeated context can reproduce it. It does not establish the cause of the first loop, prove all model loops are fixed, or measure a speedup on equivalent input lengths. Input shrank from 17,307 to 842 tokens when the defective history was omitted. Sampling was verified in native telemetry and was not changed in production.

Receipts: qwopus-reasoning-feedback.json (local-only evidence).

## Verification

- Recorded alternating-paragraph regression covers streaming detection, next-provider context cleanup, native-summary input cleanup, saved-transcript preservation, actual tool IDs/results and nonrepetitive/fenced exclusions.
- Installed Pi integration streams the recorded motif, verifies one pause without automatic retries, and captures the subsequent provider request to check both text and structured thinking omit the loop.
- Installed MTPLX/Qwopus tokenizer integration verifies scoped reasoning. The subsequent recovery-namespace test described below checks prevention of native warm-cache substitution without changing visible answers.
- Full launcher regression: 301 tests, 10 skipped, no failures. All six sampled long reasoning loops from the real session are now recognized.

The route was restarted and native settings confirmed `reasoning_history_mode=scoped`. The same saved task was resumed with xhigh thinking and MTP depth 2 unchanged. Its first resumed prompt measured 13,033 tokens, versus 92,903 on the stopped request; this is the actual new prompt size, not a cache-hit estimate. Long-task success has not yet been established.

The first-loop propensity remains a model/runtime question. These fixes address demonstrated amplification defects in our integration; another uncontrolled continuation is not proof of reliable long-task completion.

Upstream contract: [MTPLX changelog, scoped reasoning history](https://github.com/youssofal/MTPLX/blob/main/CHANGELOG.md), release 2.0.2. The earlier launcher assumption that the rolling checkpoint was obsolete was incorrect.

## Follow-up: synthetic repair text caused another feedback loop

Later on 7 September, the fresh Mario session remained responsive but repeatedly read the same source sections. Its prompt grew from 31,219 to more than 81,000 tokens. Short assistant messages copied the launcher's injected repair sentence, `[Repetitive reasoning omitted. Use the confirmed tool results and test the unresolved question directly.]`, into both reasoning and final text. Normal Pi abort completed in about one second. This was distinct from the earlier PTY deadlock.

The repair sentence itself was a source defect: inserting it as an assistant answer taught the model an unproductive response pattern. `pi_context_recovery.js` now removes detected repetitive thinking and exact assistant echoes of that legacy sentence without inserting replacement prose. Valid reasoning, visible answers, native tool calls and tool results remain. Original saved entries remain unchanged; quoted user text is not removed. Empty assistant messages produced solely by this cleanup are omitted from provider context.

MTPLX preserve mode can otherwise restore omitted reasoning from its committed session cache. Repaired history now uses a stable session-header namespace derived from the damaged entries. Healthy continuations keep that namespace; further damage changes it. This leaves visible answers untouched and avoids turning off reasoning preservation globally. Qwopus scoped mode already skips that native substitution, but the protection also covers preserve-mode routes such as Qwen3.8 6-bit.

On opening a saved unfinished turn, exact synthetic echoes now enable the existing native full-turn compaction recovery. Compaction uses Pi's own bookkeeping and the same context cleaner. A regression checks that older damage before a completed compaction does not trigger a new pause.

Verification includes real installed Pi requests (no synthetic repair sentence; changed session header), the installed MTPLX cache resolver and canonicalization path, and the actual Qwen3.8 6-bit tokenizer/encoder with preserved reasoning. This fixes the demonstrated feedback mechanism; it does not prove Qwopus cannot develop a different loop.

## Follow-up: installed extensions could undo cache recovery

Pi 0.85.1 loads explicit launcher extensions before global extensions. The
installed global MTPLX policy rewrites `x-mtplx-session-id` on every request,
which could undo the repaired cache namespace above. Earlier tests disabled
global extensions and missed this interaction.

The workflow now supplies the repaired identity in a private launcher header.
The authenticated relay validates and consumes it, then applies the native
session ID after client extensions have finished. Normal sessions preserve
their original affinity, and new sessions clear the recovery identity.
No private recovery header reaches MTPLX. This applies to every MTPLX model,
including the standard 6-bit and optimized Qwen3.8 artifacts.

The installed Pi integration now includes a late header extension reproducing
the overwrite. It verifies that Pi's outgoing native ID was reset, while the
actual relay transformation selects a different repaired cache namespace and
the model-facing history omits the recorded loop. This is a reproduced
integration defect; it does not explain Qwopus's latest first-loop failure
under scoped reasoning, which does not restore committed thinking this way.
