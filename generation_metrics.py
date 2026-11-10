"""Generation timing provenance shared by controller and read-only benchmarks.

Native request timing and delivery timing are different observations. Buffered
tool output and speculative batches cannot supply generation speed from the
interval between delivered chunks. Keep authoritative end-to-end/first-output
measurements separately; never estimate token counts from text or fragments.
"""
from __future__ import annotations

import math
import statistics
from typing import Any


BUFFERED_GENERATION_BACKENDS = frozenset({"kolibri", "splash"})
NATIVE_SOURCES = {
    "kolibri": "kolibri-native-stats", "splash": "splash-native-stats",
    "omlx": "omlx-native-stats", "slotstream": "slotstream-native-stats",
    "lmstudio": "lmstudio-response-stats",
}
PROOF_VERSION = 1


def _count(value: Any) -> int | None:
    return value if type(value) is int and 0 <= value <= 2_000_000_000 else None


def _number(value: Any, maximum: float = 1_000_000, *, positive=False) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= maximum:
        return None
    parsed = float(value)
    return parsed if math.isfinite(parsed) and (not positive or parsed > 0) else None


def native_generation_proof(
    backend: str, completion_tokens: int, stats: dict[str, Any],
) -> dict[str, Any] | None:
    """Project already-validated backend metadata into a durable numeric proof."""
    expected = NATIVE_SOURCES.get(backend)
    source = stats.get("runtimeStatsSource")
    # LM Studio's existing observer returns documented stats without adding
    # a source tag. Backend dispatch already bound these to that response.
    if backend == "lmstudio" and source is None:
        source = expected
    if not expected or source != expected or _count(completion_tokens) is None or completion_tokens < 1:
        return None
    rate = _number(stats.get("runtimeTokensPerSecond"), positive=True)
    seconds = _number(stats.get("runtimeGenerationSeconds"), 604800)
    generated = _count(stats.get("runtimeDecodeTokenCount"))
    first_batch = _count(stats.get("runtimeFirstBatchTokens"))
    basis = stats.get("runtimeThroughputBasis")
    if backend == "kolibri":
        generated = completion_tokens if generated is None else generated
        first_batch = 0
        basis = "request-native-generation"
        if generated != completion_tokens or seconds is None or seconds <= 0 or rate is None:
            return None
        if not math.isclose(generated / seconds, rate, rel_tol=1e-6, abs_tol=.0005):
            return None
    elif backend == "splash":
        if (
            generated is None or first_batch is None or generated + first_batch != completion_tokens
            or first_batch < 1 or generated >= completion_tokens or seconds is None
            or basis != "request-lifecycle-excluding-first-native-batch"
        ):
            return None
        if generated:
            if seconds <= 0 or rate is None or not math.isclose(generated / seconds, rate, rel_tol=1e-6, abs_tol=.0005):
                return None
        elif rate is not None:
            return None
    elif rate is None:
        return None
    else:
        generated = completion_tokens
        first_batch = 0
        basis = "runtime-reported-request-generation"
    return {
        "version": PROOF_VERSION, "backend": backend, "source": source,
        "completionTokens": completion_tokens, "decodeTokenCount": generated,
        "firstBatchTokens": first_batch, "generationSeconds": seconds,
        "tokensPerSecond": rate, "basis": basis,
    }


def sample_generation_tps(sample: dict[str, Any], backend: str) -> float | None:
    """Re-derive protected native rates; retain established other-engine metrics."""
    rate = _number(sample.get("decodeTokensPerSecond"), positive=True)
    if backend not in BUFFERED_GENERATION_BACKENDS:
        return None if sample.get("decodeTimingValid") is False else rate
    proof = sample.get("generationProof")
    if (
        not isinstance(proof, dict) or type(proof.get("version")) is not int
        or proof["version"] != PROOF_VERSION or proof.get("backend") != backend
        or proof.get("completionTokens") != sample.get("completionTokens")
        or proof.get("source") != NATIVE_SOURCES[backend]
        or sample.get("decodeTimingSource") != NATIVE_SOURCES[backend]
        or sample.get("decodeTimingBasis") != proof.get("basis")
        or sample.get("decodeTimingValid") is not True
    ):
        return None
    rebuilt = native_generation_proof(backend, sample.get("completionTokens"), {
        "runtimeStatsSource": proof.get("source"),
        "runtimeTokensPerSecond": proof.get("tokensPerSecond"),
        "runtimeGenerationSeconds": proof.get("generationSeconds"),
        "runtimeDecodeTokenCount": proof.get("decodeTokenCount"),
        "runtimeFirstBatchTokens": proof.get("firstBatchTokens"),
        "runtimeThroughputBasis": proof.get("basis"),
    })
    if (
        rebuilt is None or rate is None or rebuilt["tokensPerSecond"] is None
        or any(proof.get(key) != rebuilt[key] for key in rebuilt)
    ):
        return None
    count, seconds = rebuilt["decodeTokenCount"], rebuilt["generationSeconds"]
    if not count or seconds is None or seconds <= 0:
        return None
    actual = count / seconds
    if not math.isclose(rate, actual, rel_tol=1e-6, abs_tol=.0005):
        return None
    return actual


def median_generation_tps(samples: list[dict[str, Any]], backend: str) -> float | None:
    """A generation median requires valid timing for every measured sample."""
    values = [sample_generation_tps(sample, backend) for sample in samples]
    if not values or any(value is None for value in values):
        return None
    return round(statistics.median(values), 3)
