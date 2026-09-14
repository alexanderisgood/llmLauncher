"""Numeric telemetry for one private, serial Whallm route; no model imports."""
from __future__ import annotations

import copy
import json
import math
import urllib.error
import urllib.request
from typing import Any

from whallm_runtime import ready_status

MAX_STATUS_BYTES = 256 * 1024


def _number(value: Any, maximum: float = 1_000_000) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if 0 <= value <= maximum and math.isfinite(value) else None


def _count(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 2_000_000_000 else None


def merge_activity(plan: Any, activity: dict[str, Any], snapshot: Any,
                   observations: dict[str, Any]) -> dict[str, Any]:
    """Correlate native counters with the relay, never copy the raw status body."""
    config = plan.options.get("_whallmConfig")
    if (not isinstance(config, dict) or not isinstance(snapshot, dict)
            or not isinstance(snapshot.get("runtime"), dict)
            or not isinstance(snapshot.get("launcher_contract"), dict)
            or not ready_status(snapshot, config)):
        return activity
    active, recent = activity.get("active"), activity.get("recent")
    if (activity.get("lanes") != 1 or activity.get("coverage", {}).get("allLauncherSurfaces") is not True
            or not isinstance(active, list) or len(active) > 1 or not isinstance(recent, list)):
        return activity
    metrics = snapshot.get("performance")
    if not isinstance(metrics, dict):
        return activity
    completed = _count(metrics.get("completed_request_count"))
    prompt = _count(metrics.get("runtime_prompt_tokens"))
    generated = _count(metrics.get("runtime_generation_tokens"))
    cached = _count(metrics.get("prompt_cache_reused_tokens"))
    elapsed = _number(metrics.get("request_seconds"), 604800)
    if None in (completed, prompt, generated, cached, elapsed) or cached > prompt:
        return activity
    if observations.get("runId") != plan.run_id or completed < observations.get("completed", 0):
        observations.clear()
        observations.update(runId=plan.run_id, requests={})
    previous_completed = observations.get("completed")
    records = observations["requests"]
    result = copy.deepcopy(activity)
    ttft = _number(metrics.get("time_to_first_token_seconds"), 604800)
    prefill_rate = _number(metrics.get("prefill_tokens_per_second"))
    decode_rate = _number(metrics.get("decode_end_to_end_tokens_per_second"))
    prefill = None
    if (ttft and ttft <= elapsed + .05 and prefill_rate is not None and generated > 0
            and math.isclose(prefill_rate, (prompt - cached) / ttft, rel_tol=.001, abs_tol=.01)):
        prefill = {"source": "whallm-prefill", "tokensPerSecond": round(prefill_rate, 2),
                   "processedTokens": prompt - cached, "cachedTokens": cached,
                   "elapsedSeconds": ttft, "partial": False}

    def timing_matches(request: dict[str, Any]) -> bool:
        duration = _number(request.get("runSeconds"), 604800)
        return duration is not None and elapsed <= duration + 0.5 and duration - elapsed <= 15

    if (len(active) == 1 and isinstance(active[0], dict) and active[0].get("state") == "running"
            and metrics.get("generating") is True and _count(metrics.get("generation_tokens")) == 0):
        # The server has started a fresh request, but runtime.start may not
        # have reset the preceding request yet. Publish no old token numbers.
        result["active"][0]["liveTelemetry"] = {"source": "whallm-native-stats", "phase": "prefill"}

    # Server generation counters reset before tokenization; runtime counters
    # reset later. Their agreement rejects the previous request during that gap.
    if (len(active) == 1 and isinstance(active[0], dict) and active[0].get("state") == "running"
            and metrics.get("generating") is True
            and _count(metrics.get("generation_tokens")) == generated and timing_matches(active[0])):
        request = result["active"][0]
        identifier = request.get("id")
        if isinstance(identifier, str) and identifier:
            record = records.setdefault(identifier, {})
            record.update(counter=completed, promptTokens=prompt)
            phase = "decode" if generated > 0 else "prefill"
            request["liveTelemetry"] = {
                "source": "whallm-native-stats", "phase": phase,
                "promptTokens": prompt, "generatedTokens": generated,
                "contextTokens": prompt + generated, "elapsedSeconds": elapsed,
                "tokensPerSecond": decode_rate if generated > 1 else None,
            }
            if prefill is not None:
                record["promptProcessing"] = prefill
                request["promptProcessing"] = copy.deepcopy(prefill)
            if generated > 1 and decode_rate is not None and decode_rate > 0:
                request.update(runtimeStatsSource="whallm-native-stats", runtimeTokensPerSecond=decode_rate)

    for index, request in enumerate(result["recent"][:32]):
        if not isinstance(request, dict) or not isinstance(request.get("id"), str):
            continue
        identifier = request["id"]
        record = records.get(identifier, {})
        counts_match = (request.get("usageReported") is True
                        and _count(request.get("promptTokens")) == prompt
                        and _count(request.get("completionTokens")) == generated)
        # A final receipt belongs only to an observed request's next native
        # completion, or the sole newest completion since the preceding poll.
        final_match = (not active and index == 0 and metrics.get("generating") is False
                       and request.get("state") == "completed" and counts_match and timing_matches(request)
                       and (record.get("counter") == completed - 1
                            or (not record and previous_completed is not None and completed == previous_completed + 1)))
        if final_match:
            record = records.setdefault(identifier, {})
            record["promptTokens"] = prompt
            if prefill is not None:
                record["promptProcessing"] = prefill
            if generated > 1 and decode_rate is not None and decode_rate > 0:
                record["runtimeTokensPerSecond"] = decode_rate
        if request.get("usageReported") is True and request.get("promptTokens") == record.get("promptTokens"):
            if "promptProcessing" in record:
                request["promptProcessing"] = copy.deepcopy(record["promptProcessing"])
            if "runtimeTokensPerSecond" in record:
                request.update(runtimeStatsSource="whallm-native-stats",
                               runtimeTokensPerSecond=record["runtimeTokensPerSecond"])
    observations["completed"] = completed
    while len(records) > 32:
        records.pop(next(iter(records)))
    return result


def request_activity(plan: Any, activity: dict[str, Any], observations: dict[str, Any]) -> dict[str, Any]:
    if (plan.backend != "whallm" or not plan.model.get("nativeWhallm")
            or not plan.secrets.get("apiKey")):
        return activity
    request = urllib.request.Request(f"http://127.0.0.1:{plan.port}/api/status",
        headers={"Authorization": f"Bearer {plan.secrets['apiKey']}"})
    try:
        with urllib.request.urlopen(request, timeout=0.6) as response:
            raw = response.read(MAX_STATUS_BYTES + 1)
        if len(raw) > MAX_STATUS_BYTES:
            return activity
        return merge_activity(plan, activity, json.loads(raw), observations)
    except (OSError, ValueError, urllib.error.URLError):
        return activity
