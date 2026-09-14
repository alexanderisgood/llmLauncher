# MTPLX long-context memory policy

The `hub-prefill-1` adapter applies to ordinary dense Qwen 27B sessions on a
48 GiB Mac using exactly MTPLX 2.11.2. Model geometry, rather than the model
name or quantization label, admits Qwen 6-bit, Optimized Speed and the dense
Qwopus conversion. Other devices, architectures, versions and benchmark or
route-check jobs retain their existing configuration.

## Changes

- The native Metal allocation budget is explicitly 40 GiB. The native wired
  residency policy, pressure aborts, cancellation and overcommit prohibition
  remain enabled. An allocation budget is not a hard physical-memory fence.
- The session and total snapshot bank are both capped at 12 GiB. This avoids
  switching the observed 8.03 GiB snapshot into live-reference-only storage at
  the former 8 GiB threshold. Native eviction and dynamic ceilings still apply.
- Prefill admission accounts for full-precision KV, including a complete
  full-precision restored prefix when quantized cache conversion can overlap
  its source. Even a 113-token suffix must pass this check. The native
  reclamation order remains allocator cache, obsolete snapshots, then idle
  snapshots, protecting the prefix needed by the incoming request. Requests
  that still do not fit are refused before prefill.
- Prefill chunks are capped at 512 tokens, 256 with less than 10 GiB allocator
  headroom, or 128 with less than 6 GiB. Native recurrent-state boundaries are
  preserved. This is selected when each prefill span list is built; it is not
  an interruptible sub-operation or a token/context limit.
- Queued SSD writes, retries and snapshot-settle jobs use weak references.
  Evicting an entry therefore releases its buffers even if idle work is queued.
- Large snapshots get a periodic streaming SSD checkpoint opportunity between
  model turns, at most once per five minutes. Both normal and oversized live
  references are supported. A cooperative 30-second deadline and 1 GiB active
  memory reserve yield between tensor operations; a single tensor operation
  can outlast that deadline. The original idle persistence path remains active.
  Native checksums, atomic manifest publication, disk-space limits, storage cap,
  write budget and restore validation remain in use. Interrupted/failed writes
  are not reported as durable. SQLite transactions explicitly close connections.

This is checkpoint storage, **not live KV offload**. Active attention still
needs RAM. A checkpoint can avoid recomputing a compatible prefix after
restart or eviction; it cannot make an arbitrarily large prefill fit.

## Maintenance and validation

`mtplx_hub_runtime.py` is loaded by the selected runtime's Python, without
editing installed packages. Function source hashes in
`runtime_patches/mtplx/2.11.2/admission.json` reject changed patch targets.
The launcher source fingerprint includes both files.

`tests/test_mtplx_hub_memory_launch.py` verifies the launch settings and scope.
Run `tests/test_mtplx_hub_runtime.py` with the installed MTPLX Python and Metal
access for native, model-free cache tests. They cover the 8 GiB boundary using
tiny tensors with simulated byte accounting, exact cache restore, warm-prefix
admission, compaction reclamation, eviction while writes are pending, periodic
checkpointing, SSD reopening, cancellation between tensors and SQLite cleanup.
They do not establish overnight stability or measure 128K inference peaks.

The native `/health` response includes `startup.launcher_memory_policy` and its
latest checkpoint result. Verify `metal_memory_caps.memory_limit_bytes` is
42949672960 and both bank caps are 12884901888 after restart.

## Admission-refusal recovery

The September 9 follow-up reached 107,326 prompt tokens with 107,286 cached.
The guard refused a projected 40.7 GiB request before prefill; the server stayed
alive and SSD checkpoints had completed. This exposed a separate Hub integration
bug: the relay recognised oMLX memory admission errors but passed MTPLX's HTTP-200
SSE error through without Pi's compaction marker.

The relay now recognises the specific MTPLX `insufficient_memory` admission
message in both SSE and HTTP 507 responses. It preserves the original code and
memory diagnostics while adding the markers Pi needs to compact and retry.
Allocation failures during generation and sustained-pressure aborts are not
relabelled for automatic task replay. MTPLX uses the same bounded recent-history
retention policy as oMLX during recovery, and manual recovery also recognises
previously saved, unnormalised admission refusals.

Installed-Pi integration fixtures use the real relay and a fake model server:
HTTP and fragmented SSE regressions plus one compaction followed by successful
replay and two additional turns. No model weights are needed for these checks.
