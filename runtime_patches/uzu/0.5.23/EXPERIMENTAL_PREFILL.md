# Bounded prefill — locally qualified at 64K/128K and adopted

The normal launcher now admits this exact locally qualified build. Its original
`prefill-experiment.1` identity is retained so existing 64K and 128K measurements
remain truthful; no receipt was relabelled for different bytes. It is still a
developer-host-only route, not a public runtime distribution. The old `.2`
executable remains installed untouched. The user-approved live ceiling is
38 GiB; the independent whole-Mac reserve monitor and 2 GiB admission margin
remain enabled. This document preserves the development and measurement record.

## Evidence and hypothesis

The previous 128K qualification (`abcffb9b-d74b-43e9-8bd8-3dcd92fad288`) was
stopped by the former 36 GiB process-group guard during its cold long-prompt
request. The completed 64K qualification remains separate and valid. No model
was loaded to develop this candidate, and the failed 128K test was not rerun.

At upstream commit `115609b6ef7ce5a94fc761bf395780f032b09f9b`:

- `stream/stream.rs` encodes every prefill chunk into one command buffer before
  submitting it. Each chunk remains 1,024 tokens for attention correctness.
- `allocator/allocator.rs` marks CPU constants as unable to alias earlier pooled
  ranges. Dropping their Rust allocations makes the ranges available to GPU
  scratch, but not to the next CPU constant. A pool retains backing ranges until
  it is released.
- Attention RoPE and trie preparation allocate constants per chunk. Completing
  GPU work and releasing a pool between bounded groups can reclaim those ranges.

The CPU probe uses the actual upstream range allocator, with synthetic ranges
instead of model weights or GPU buffers. It demonstrates bounded retained ranges
after pool turnover, rejects overlap with an in-flight pool, and checks that live
allocations prevent a pool from being released. **This is not a measurement of
physical memory savings, and does not establish the cause of the entire spike.**
KV growth and other persistent or driver allocations still exist.

The target's 16 full-attention layers share one equal RoPE configuration in
`Transformer::new`; their RoPE arrays must not be counted 16 times. The installed
configuration has a 64-element RoPE dimension despite a 256-element attention
head. This further limits what can be inferred from the simplified allocator
probe: a large physical-memory reduction is not established by counting layers.

## Candidate

`experimental-bounded-prefill.patch` applies only to the pinned commit above and
coexists with `llm-launcher-hardening.patch` without changing its server boundary.
Candidate patch SHA-256:
`e2218762985e121bd3fa7a305739666b3b22ae8f6a1b41651a978d9d27a41311`.

The separate `experimental-quiet-build.patch` serializes Metal kernel source
files and bounds their inner shard compilation/compression to two jobs. It does
not alter shard assignment or kernel contents. Its SHA-256 is
`73328dc97e4f6f0bf0f603212b4412f5f501d538cdb9332ccc0ac81c009bd614`.
The opt-in test applies both patches and checks that the sharding function stays
identical to upstream. The release candidate is built with both patches plus
the existing hardening patch, not the prefill patch alone.

`verify_candidate_source.py /absolute/path/to/uzu` reconstructs all three patches
on the pinned upstream archive in a temporary directory, checks 1,575 source
files against the actual checkout, and rejects changed or unexpected source
files. The verified source-content manifest SHA-256 is
`85ed840a55874324f63360bff43e22b0ec3f676b727bfa8f11759ca2adc2749c`.
An opt-in regression test checks that a modified build input is rejected. This
verifies source content, not compiler identity or binary reproducibility.

It submits and waits after each non-final 8,192-token group, drops chunk-local
allocations, and replaces the completed allocation pool. The target KV, draft
KV, accepted recurrent state, and repetition state are preserved. The final
sampling row and pending output remain on the existing decode path. Attention
chunk size, quantization, context, sampling, reasoning, and acceleration are not
changed. GPU errors propagate rather than continuing with a failed submission.

## Checks

No-model CPU engine compilation passed with Homebrew Rust 1.97.1 (upstream
declares 1.98.0, so the explicit version override is required):

```sh
cargo check -p uzu-engine --no-default-features --features cpu \
  --locked --offline --ignore-rust-version -j2
```

The combined hardened CLI check with CPU, Metal, and grammar features also
passed. The installed Metal toolchain needed access outside the build sandbox;
no toolchain was downloaded. The resumed check completed in 1m 56s:

```sh
TOOLCHAINS=com.apple.dt.toolchain.Metal.32023.883 \
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  nice -n 10 cargo check -p cli --locked --offline --ignore-rust-version -j2
```

`-j2` limits Cargo jobs, not Uzu's internal Metal compilation fan-out; the build
script independently uses available CPU parallelism. The process was low
priority, no model was resident, and a whole-Mac check reported 93% free memory.
The subsequent release candidate uses the separate quiet-build patch above to
bound that internal fan-out as well. A successful `cargo check` is not a
linked release executable or a model-output test. `cargo fmt --all -- --check`
also passed (stable rustfmt warns about upstream's nightly-only import options).

From the launcher repository, point the opt-in regression test at a local clone
of the pinned source. The test reads original files from Git into a temporary
fixture, applies the experimental patch only there, and runs four Rust tests.
It does not modify the supplied clone, access model files, or load a model.

```sh
LLM_LAUNCHER_UZU_SOURCE=/absolute/path/to/uzu \
  python3 -m unittest discover -s tests -p 'test_uzu_prefill_candidate.py' -v
```

All four checks passed: constant lifetime, in-flight isolation, live-allocation
rejection, and preservation of token order/exactly one final sampling row across
chunk/group boundaries through 128K, with and without the final logits-row split.
These are allocator and scheduling checks, **not model-output equivalence**.

The first release attempt's helper spent several minutes evaluating Rhai kernel
variant constraints. A one-second process sample confirmed active evaluation,
not a deadlock (5.0 GiB current physical footprint, 13.2 GiB peak). Uzu optimizes
dev build helpers but has no corresponding release override; Cargo's default
for build dependencies is opt-level 0. That owned build group was interrupted
and confirmed stopped before resuming with the following build-only override,
retaining cached artifacts and the same three source patches:

```sh
CARGO_PROFILE_RELEASE_BUILD_OVERRIDE_OPT_LEVEL=2 \
TOOLCHAINS=com.apple.dt.toolchain.Metal.32023.883 \
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  nice -n 10 cargo build --release -p cli --locked --offline --ignore-rust-version -j2
```

The override is documented in [Cargo's build dependency profiles](https://doc.rust-lang.org/cargo/reference/profiles.html#build-dependencies).
This build command does not install or run the candidate.

The combined release build completed successfully in 10m 03s on 2026-09-04.
The output is `target/release/cli` (the upstream package names the executable
`cli`; it has not been copied over the installed `mirai`):

- Architecture: `arm64` Mach-O executable
- Size: `65,079,520` bytes
- SHA-256: `efe7fc98a8e063c30103a27badb4f308b8cb782708134a7805178f9e16caa0ce`
- Signature: ad-hoc linker signature, no Developer ID or notarization
- Compiler: Homebrew Rust 1.97.1, commit
  `8bab26f4f68e0e26f0bb7960be334d5b520ea452`, LLVM 22.1.8
- Post-build source verification: all 1,575 files matched the three-patch
  manifest above. The separate allocator/scheduling and modified-source
  rejection tests passed again.

This build record alone identifies a local artifact, not a reproducible release
or an inference qualification. The later measurements below qualified its exact
bytes. Normal admission now uses that identity; the working `.2` executable
itself remains unchanged.

`tests/test_uzu_candidate_executable.py` adds an opt-in executable smoke test.
It requires an exact expected binary hash, uses only a nonexistent model path,
denies outbound networking and reads of the model cache, and kills its owned
process group if startup does not reject promptly. It checks the mandatory CLI
flags, rejection of non-loopback binding and unsafe/short credential files, and
consumption of a valid one-use credential before the missing model is resolved.
The harness passed against both the installed `.2` baseline and the exact
candidate hash above. Candidate startup rejected unsafe binding, unsafe key
permissions, and short credentials before model discovery; the valid one-use
key was consumed before the nonexistent model failed resolution. Additional
candidate checks rejected zero/over-range context, zero output, and output
larger than context without consuming credentials. It is not an
authenticated HTTP inference or long-context test.

The candidate source also passed all eight native Nagare tests in the release
profile with the same build-helper override (`cargo test --release -p nagare
--locked --offline --ignore-rust-version -j2 -- --test-threads=1`). These include
live context reservation at the boundary, preservation of token/cache state
after rejection, and a successful replacement turn after outer-history
preflight rejection. The test backend is synthetic, not a loaded model. The
separate CPU-only CLI/server suite also passed all 74 tests after a 6m 02s test
build. Coverage includes bearer authentication, mandatory output/context
limits, reasoning round-trip and validation, cancellation finish reasons, and
tool-call serialization. Neither native suite loaded model weights.

## Isolated qualification runner

`candidate_qualification.py` admits only the candidate SHA-256 and size above
from the owner-only workspace directory
`build/uzu-prefill-candidate/runtimes/uzu-0.5.23-llm-launcher.prefill-experiment.1/`.
The executable was first staged there as `mirai`, mode `0500`, before its later
normal-app installation. This directory is Git-ignored. The runner verifies the complete
source tree first and uses a distinct experimental version and patch-chain hash
(`680e2d72f0ba7a63fc822543022c6a1fc9b2895276fb7252a8049219de58692f`,
the three patch files concatenated in the verifier's order).

All launcher-owned state paths are redirected inside that private workspace
directory. Model files remain shared read-only inputs; production settings,
runtime bytes and qualification receipts are not copied or changed. The actual
launcher calibration planner and benchmark worker are reused, including output,
reasoning, near-tier prompt, memory, performance and unload gates. The runner
does not start an app server or expose an experimental toggle to normal users.

Without `--run`, it prints a no-load plan:

```sh
python3 runtime_patches/uzu/0.5.23/candidate_qualification.py \
  --source /absolute/path/to/uzu --context 65536
```

The real staged candidate's 64K plan was ready to measure, with its own binary
identity and no trusted result. Its 128K plan was blocked by the expected
`missing-64k-receipt` condition: the working binary's receipt did not authorize
this candidate. No model was loaded for either check.

After native tests pass, `--run` must acquire the **normal controller's exclusive
instance lock** before starting the benchmark. It refuses while that controller
is running; it never stops it automatically. It holds the lock through cleanup,
so the normal app cannot start a competing model session. Signal cancellation,
a one-hour run bound, and final unload checking are additional runner controls;
they do not replace the launcher's continuous memory guard. The five no-model
runner tests cover isolated paths/identities, preservation of the 38 GiB ceiling
and 2 GiB margin, patch-chain identity, exclusive locking without modifying lock
metadata, unsafe lock rejection, and unchanged 64K/128K request settings.

An additional opt-in harness, `tests/test_uzu_candidate_live_boundary.py`, is
prepared for real-model rejection/cancellation recovery. It requires this
candidate's own reusable 64K receipt and the same exclusive controller lock,
then uses normal session admission and the native authenticated listener. It
checks missing authentication, zero output limits and stricter-alias clamping,
an over-context prompt, a complete
reasoning answer after rejection, and another complete answer after closing an
active stream. It is skipped unless both `LLM_LAUNCHER_UZU_LIVE_CANDIDATE=1` and
`LLM_LAUNCHER_UZU_SOURCE` are explicitly set. Its final live run passed in
15.502s on 2026-09-05 local time. The normal relay correctly rejected the first
attempt's workspace-local config; the harness now creates only a fresh UUID
run beneath the normal private `runs` directory, with the ordinary `077` umask,
instead of weakening or changing the relay's trusted-root check. All benchmark
receipts and runtime settings remain isolated.

The successful recovery log is normal run
`d7a80612-6019-4035-a642-d82ef7a5cadb/engine.log`. It records:

- Zero limits rejected; conflicting positive aliases clamped to exactly eight
  generated tokens with a `length` finish.
- A canonical 70,010-token prompt plus 4,096 response reservation rejected by
  the native 65,536-token limit before prefill.
- A subsequent complete reasoning answer (`stop`, 181 generated tokens).
- An active stream interrupted by closing its client; the server recorded
  `client disconnected` after 0.32s.
- Another complete answer immediately afterward (`stop`, 174 tokens).
- A complete reasoning answer through the unchanged normal app relay (`stop`,
  179 tokens), followed by idle manager and closed native/relay listeners.

Early harness attempts also assumed rejection rather than the documented clamp
policy, and required an optional space after SSE `data:`. Those harness
assumptions were corrected; no native limit, parser, memory guard or relay
security check was weakened. A no-model test independently confirms that the
harness's termination handlers unwind cleanup and restore prior handlers.

## Measured candidate 64K result

The isolated run completed on 2026-09-04 at 22:46:10 UTC, record
`7cd4a040-9ab7-433d-b301-ac44bf4dd8b3`. Original evidence is stored in
`build/uzu-prefill-candidate/benchmarks.json`; the native run log is under
`runs/5ae03fdb-07f6-48f0-8a5a-fcb6ba1c052c/engine.log` in that state directory.

- Four complete reasoning-and-answer turns; authoritative usage on all four.
- Prompt tokens: 49,099 cold; 49,844 shared-prefix; 60,333 tool-result ingestion;
  60,823 warm follow-up. The last two exceed the required 90% of 65,536.
- Median generation: 38.027 tok/s; slowest turn: 33.786 tok/s.
- Measured process-group peak: 22,379,589,848 bytes (20.84 GiB).
- Minimum recorded system headroom: 26,800,595,927 bytes; required OS reserve:
  5,153,960,755 bytes. The process ceiling remained 38 GiB throughout.
- Arithmetic correctness passed. Clean unload verified process/group exit,
  closed listener, and idle manager. The normal controller was then restored
  at port 18080, with no model resident.

The earlier `.2` 64K run (`3d49f11e-8e42-4be4-ad8d-4068a761e45d`) recorded a
27.85 GiB peak and 37.109 tok/s median. The candidate's recorded peak was about
7.01 GiB lower. These are separate model-default-sampling runs with different
generated lengths, not a repeated controlled A/B study or a claim of a speed
improvement. Nor do four generated turns prove general model-output equivalence.

Reopening the candidate planner with the same hardware access used during the
run recognized its receipt. The 128K preflight then used that exact new record:
the projected peak plus the unchanged 2 GiB margin was 30,164,218,072 bytes
(28.09 GiB), below 38 GiB, and the plan became ready to measure. A sandboxed
planner without the same hardware identity access
did not match the receipt; no identity or admission guard was relaxed.

## Measured candidate 128K result

The next isolated run completed at 2026-09-04 23:01:09 UTC (September 5 local
time), record `8811a1ac-230b-4208-9b35-0b8ec202b3f2`, native run
`1865ffac-8421-4efc-86de-6270fac8000b`. All four turns completed with separate
reasoning, final answers, authoritative usage, and the existing correctness and
clean-unload checks. The context, output contract, BF16 KV, model weights,
sampling and 38 GiB ceiling were not lowered to obtain a pass.

| Turn | Authoritative prompt tokens | Native time to first output | Native generation tok/s |
| --- | ---: | ---: | ---: |
| Cold | 98,251 | 344.03s | 55.1 |
| Shared prefix | 102,579 | 0.68s | 57.1 |
| Tool-result ingestion | 122,797 | 90.57s | 56.9 |
| Warm follow-up | 124,165 | 0.87s | 44.6 |

Launcher-observed median generation was 56.075 tok/s; minimum was 44.716 tok/s.
Its measured process-group peak was 26,955,575,560 bytes (25.10 GiB), below both
the 38 GiB live ceiling and the earlier 28.09 GiB projection including margin.
Minimum system headroom was 22,162,031,247 bytes, above the unchanged
5,153,960,755-byte system reserve. Both near-tier turns exceeded 90% of 131,072.

The higher generation rates versus the 64K run are workload-dependent, not
proof that longer context is intrinsically faster. Cold prefill still took
about 5m 44s; cached reuse was essential to the roughly one-second follow-ups.
Reopening with the same hardware access returned `ready: true`,
`action: apply-existing`, and `qualified: true`, without another test. The
normal controller was restored at port 18080, idle with no resident model.

## Adoption and remaining verification

The combined build, native boundary suites, real reasoning/answer recovery,
64K qualification, and subsequent 128K qualification passed as recorded above.
These checks are not a controlled baseline/candidate output-equivalence study;
that remains unproven and no general quality-equivalence claim is made.

On the qualification host, the exact executable was installed separately at
`~/Library/Application Support/LLM Launcher/runtimes/uzu-0.5.23-llm-launcher.prefill-experiment.1/mirai`
with an owner-only directory and mode `0500` executable. Normal backend and
frontend pins match its size, binary hash and ordered patch-chain hash.

`adopt_qualification.py` defaults to read-only validation. With `--apply`, it
requires the controller's exclusive lock, validates exact runtime/model/hardware
and context eligibility, backs up existing benchmark history, and merges only
the two fixed record IDs above. Their contents stay unchanged and all prior
history is retained. Receipts for the old `.2` bytes do not authorize this build,
nor do these receipts authorize `.2`. No profile or model settings were changed.

The normal controller has been restarted. A no-load check through its actual
HTTP endpoints passed for both contexts: `/api/calibration/plan` returned
`apply-existing`, `/api/optimal` accepted the returned immutable evidence binding,
and reopening the plan with the applied options returned the same saved binding
without requesting a retest. The controller stayed idle. Seven no-model adoption
tests also cover exact identities, missing/duplicated receipts, hardware/context
mismatch, planner rejection, and unchanged evidence contents.

An isolated headless Chromium browser subsequently exercised the real UI while
the desktop was locked: the 128K saved result displayed, Apply called the real
optimizer, reopening offered Requalify rather than demanding a new test, and
Launch became enabled. A full page reload also retained the ready 128K route.
Frost at 1920px and Daylight at 960px remained centered without horizontal
dialog overflow; the desktop action buttons had equal top edges and heights.
This exposed and fixed a misleading 0% bar on reopened saved results. The harness
blocks model-start and other mutation endpoints in its default no-inference mode;
it substitutes only the empty journal-recovery response for its new isolated tab.
No public installer, automatic download or distributable executable is offered.

The separately opted-in real Chat test subsequently passed through the normal
launcher with run `47e0af41-bce6-4c77-9075-27be9bcb3c51`. It launched the qualified
128K-window route, displayed runtime thinking separately, queued a second prompt,
preserved the reader's scroll position while output grew, and completed both
final answers. The usage dashboard displayed 77.4 tok/s after its asynchronous
update. Native logs recorded 106.3 tok/s for 1,646 output tokens and 77.1 tok/s for
1,226 output tokens, with 0.36/0.33-second time to first token. These were a
repetitive rendering prompt and short arithmetic follow-up with only 62/1,752
input tokens, **not** a long-context or representative coding speed measurement.
The earlier qualification receipts remain the long-context evidence.

Clicking End chat stopped the actual model and returned the controller to idle
before test cleanup, while leaving both replies readable. Screenshots were
visually inspected. Apply/reopen/reload and both theme-layout checks also passed
in this run, with no uncaught browser errors or unexpected requests. The harness
only permits its exact model/context launch, protects existing chat IDs from
writes, and stops only its own run on failure. Generated test conversations may
remain in local history; no existing conversations are deleted.
