# Benchmark planning and route qualification

`benchmark_planning.py` owns the complete generated workload, calibration,
bounded tuning/sweep and benchmark request planning feature: 47 functions.
`route_qualification.py` owns the complete exact route contract, correctness,
sample validation, metrics and current receipt proof feature: 14 functions.
They import no controller and start no work on import.

Static policy is detached and immutable, including nested suite/scenario lists.
The 14 helpers that need no policy or live authority are ordinary module
functions. Other methods receive explicit policy records and individually typed
validation, artifact, evidence, qualification and resource ports. Current binary
paths and descriptor availability are live lookups. Production wiring may be
reused only while its static policy inputs remain equal; eligibility, receipts,
artifacts, physical samples and results are never cached by either component.

Selection, benchmark evidence, resource admission, sampling, native telemetry and
inference/execution retain their existing authority. ANE request planning keeps
the existing normalizer callback and its materialization behavior. Ordinary
calibration previews, generated workloads and qualification contracts remain
read-only; they allocate no ports or engine processes. RouteCheck preview and
operation state belong to the separate RouteCheck domain.

## Verification

The test-only frozen sources retain every complete pre-extraction function body.
AST projection permits only the explicit dependency bindings and the approved
oh-my-pi label repair. A valid OMP calibration previously reached a missing label
entry and raised `KeyError('omp')`; it now returns the complete unchanged plan
with `clientLabel: 'oh-my-pi'`. The saved records retain the original failure and
the complete repaired plan.

Run the standalone checks with:

```sh
python3 -m unittest tests.test_benchmark_planning tests.test_route_qualification
```

The checks cover 528 complete generated route/calibration cases across all 12
engines and Pi/OMP; exact sampling, context/output/KV and bounded tuning settings;
generated prefixes and continuing conversations through 128K; and 15 complete
qualification records for Uzu, oMLX and llama.cpp. Additional cases reject invalid
counts/timings, wrong output/precision/runtime/correctness/unload receipts, missing
physical semantics/reserve, and inadequate authoritative high-context prompt
exercise. Live trust, receipt freshness, capability, model/runtime identity and
physical-size callback changes are rechecked on repeated calls.

Every fixture is generated local data. No test downloads, loads or serves a real
model, changes global agent settings, or stops an independent service. The CPU
report in `bench/results/20261007-benchmark-planning-cpu.json` measures computation
and policy construction only; it provides no inference TPS result.
