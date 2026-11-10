"""Bounded, metadata-only throughput observation shared by launcher relays.

Counters always come from engine usage. Text and socket read counts are never
used as token estimates. Decode reuse lives for one upstream read only.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any

from sse_framing import ResponseOutcome
from stream_observer import ChunkJSONDecoder


class ResponseMetrics:
    """Extract only bounded timing and runtime usage metadata from a relayed response."""

    def __init__(self, protocol: str, content_type: str, backend: str = "", *, maximum: int = 1024 * 1024) -> None:
        self.protocol = protocol
        self.maximum = maximum
        self._decoder = ChunkJSONDecoder()
        self.outcome = ResponseOutcome(protocol, content_type.lower().startswith("text/event-stream"), decoder=self._decoder.loads)
        self.backend = backend
        self.streaming = content_type.lower().startswith("text/event-stream")
        self.buffer = bytearray()
        self.complete = bytearray()
        self.overflowed = False
        self.discarding_line = False
        self.output_seen = False
        self.prompt_tokens: int | None = None
        self.completion_tokens: int | None = None
        self.runtime_stats: dict[str, Any] = {}

    @staticmethod
    def _token(value: Any) -> int | None:
        return ResponseMetrics._integer(value)

    def _usage(self, value: Any) -> None:
        if not isinstance(value, dict):
            return
        usage = value.get("usage")
        response = value.get("response")
        if not isinstance(usage, dict) and isinstance(response, dict):
            usage = response.get("usage")
        if not isinstance(usage, dict):
            return
        prompt = self._token(usage.get("prompt_tokens"))
        if prompt is None:
            prompt = self._token(usage.get("input_tokens"))
        completion = self._token(usage.get("completion_tokens"))
        if completion is None:
            completion = self._token(usage.get("output_tokens"))
        if prompt is not None and completion is not None:
            self.prompt_tokens = prompt
            self.completion_tokens = completion

    @staticmethod
    def _number(value: Any, maximum: float, *, positive: bool = False) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        # Reject huge integers before converting to float (which can overflow).
        if value < 0 or value > maximum:
            return None
        parsed = float(value)
        if not math.isfinite(parsed):
            return None
        if positive and parsed <= 0:
            return None
        return parsed

    @staticmethod
    def _integer(value: Any, maximum: int = 2_000_000_000) -> int | None:
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
            return None
        return value

    def _performance(self, value: Any) -> None:
        """Read documented LM Studio numeric stats without retaining response data."""
        if self.backend != "lmstudio" or not isinstance(value, dict):
            return
        containers = [value]
        for key in ("response", "result"):
            nested = value.get(key)
            if isinstance(nested, dict):
                containers.append(nested)
        stats = next(
            (container.get("stats") for container in containers
             if isinstance(container.get("stats"), dict)),
            None,
        )
        if not isinstance(stats, dict):
            return
        tps = self._number(stats.get("tokens_per_second"), 1_000_000, positive=True)
        ttft = self._number(
            stats.get("time_to_first_token_seconds", stats.get("time_to_first_token")),
            86_400,
        )
        generation = self._number(
            stats.get("generation_time_seconds", stats.get("generation_time")),
            86_400,
        )
        total_draft = self._integer(stats.get("total_draft_tokens_count"))
        accepted_draft = self._integer(stats.get("accepted_draft_tokens_count"))
        if tps is not None:
            self.runtime_stats["runtimeTokensPerSecond"] = round(tps, 4)
        if ttft is not None:
            self.runtime_stats["runtimeTimeToFirstTokenSeconds"] = round(ttft, 6)
        if generation is not None:
            self.runtime_stats["runtimeGenerationSeconds"] = round(generation, 6)
        if (
            total_draft is not None and accepted_draft is not None
            and total_draft > 0 and accepted_draft <= total_draft
        ):
            self.runtime_stats["totalDraftTokens"] = total_draft
            self.runtime_stats["acceptedDraftTokens"] = accepted_draft
            self.runtime_stats["speculativeAcceptancePercent"] = round(
                accepted_draft / total_draft * 100, 1,
            )

    def _omlx_performance(self, value: dict[str, Any]) -> None:
        if self.backend != "omlx" or not isinstance(value.get("usage"), dict):
            return
        usage = value["usage"]
        prompt = self._integer(usage.get("prompt_tokens"))
        completion = self._integer(usage.get("completion_tokens"))
        if prompt != self.prompt_tokens or completion != self.completion_tokens or None in (prompt, completion):
            return
        seconds = self._number(usage.get("generation_duration"), 86400, positive=True)
        tps = self._number(usage.get("generation_tokens_per_second"), 1_000_000, positive=True)
        if seconds is not None and tps is not None and completion > 0:
            self.runtime_stats.update(runtimeStatsSource="omlx-native-stats",
                                      runtimeTokensPerSecond=tps, runtimeGenerationSeconds=seconds)
        ttft = self._number(usage.get("time_to_first_token"), 86400)
        if ttft is not None:
            self.runtime_stats["runtimeStatsSource"] = "omlx-native-stats"
            self.runtime_stats["runtimeTimeToFirstTokenSeconds"] = ttft
        details = usage.get("prompt_tokens_details")
        cached = self._integer(details.get("cached_tokens")) if isinstance(details, dict) else None
        prefill = self._number(usage.get("prompt_eval_duration"), 86400, positive=True)
        # Upstream derives some cached-turn durations from total prompt count.
        # Only uncached turns have an unambiguous processed-token denominator.
        if cached == 0 and prefill is not None and prompt > 0 and prompt / prefill <= 10_000_000:
            self.runtime_stats["promptProcessing"] = {
                "source": "omlx-native-stats", "processedTokens": prompt,
                "cachedTokens": 0, "elapsedSeconds": prefill,
                "tokensPerSecond": round(prompt / prefill, 2),
            }

    def _kolibri_performance(self, value: dict[str, Any]) -> None:
        """Trust only request-bound native counters matching final HTTP usage."""
        if self.backend != "kolibri" or not isinstance(value.get("usage"),dict):
            return
        usage = value["usage"]
        # A later usage frame supersedes earlier counts. Never retain an
        # earlier native rate when final counters no longer prove its scope.
        if self.runtime_stats.get("runtimeStatsSource") == "kolibri-native-stats":
            for key in ("runtimeStatsSource","runtimeTokensPerSecond","runtimeGenerationSeconds",
                        "runtimeDecodeTokenCount","runtimeThroughputBasis"):
                self.runtime_stats.pop(key,None)
            if (self.runtime_stats.get("promptProcessing") or {}).get("source") == "kolibri-native-stats":
                self.runtime_stats.pop("promptProcessing",None)
        stats = usage.get("kolibri_native_stats")
        if not isinstance(stats,dict) or type(stats.get("version")) is not int or stats["version"] != 1:
            return
        prompt,completion = self._integer(usage.get("prompt_tokens")),self._integer(usage.get("completion_tokens"))
        processed,cached = self._integer(stats.get("processed_prompt_tokens")),self._integer(stats.get("cached_prompt_tokens"))
        generated = self._integer(stats.get("generation_tokens"))
        native_prompt = self._integer(stats.get("prompt_tokens"))
        details = usage.get("prompt_tokens_details")
        reported_cached = self._integer(details.get("cached_tokens")) if isinstance(details,dict) else None
        if (None in (prompt,completion,processed,cached,generated,reported_cached,native_prompt)
                or prompt != self.prompt_tokens or completion != self.completion_tokens
                or native_prompt != prompt or generated != completion or generated < 1
                or processed+cached != prompt or reported_cached != cached
                or self._integer(usage.get("total_tokens")) != prompt+completion):
            return
        seconds = self._number(usage.get("generation_duration"),86400,positive=True)
        tps = self._number(usage.get("generation_tokens_per_second"),1_000_000,positive=True)
        if (seconds is None or tps is None
                or not math.isclose(generated/seconds,tps,rel_tol=1e-6,abs_tol=1e-6)):
            return
        self.runtime_stats.update(runtimeStatsSource="kolibri-native-stats",runtimeTokensPerSecond=tps,
                                  runtimeGenerationSeconds=seconds,runtimeDecodeTokenCount=generated,
                                  runtimeThroughputBasis="request-native-generation")
        prefill = self._number(usage.get("prompt_eval_duration"),86400,positive=True)
        if processed > 0 and prefill is not None and processed/prefill <= 10_000_000:
            self.runtime_stats["promptProcessing"] = {
                "source":"kolibri-native-stats","processedTokens":processed,"cachedTokens":cached,
                "elapsedSeconds":prefill,"tokensPerSecond":round(processed/prefill,2),
            }

    def _splash_performance(self, value: dict[str, Any]) -> None:
        """Validate request-bound native lifecycle timing, excluding its first batch.

        Splash1.2.1 server/metrics.py emits this on the final usage SSE frame.
        Its first native emission can contain several speculative tokens. The
        decode count excludes that entire batch and uses the native interval
        from first emission to Done. It is not GPU command/kernel throughput,
        and native first emission need not equal the first visible tool delta.
        """
        if self.backend != "splash" or self.protocol != "chat-completions" or not self.streaming:
            return
        if "timings" in value:
            # The terminal native frame independently reports raw totals.
            # Keep only bounded metadata until its matching usage frame, so
            # changed usage cannot reinterpret an older decode counter as a
            # different first-batch size.
            self._splash_final_timing = None
            timings = value.get("timings")
            choices = value.get("choices")
            identifier, model = value.get("id"), value.get("model")
            if (value.get("object") == "chat.completion.chunk" and isinstance(timings, dict)
                    and isinstance(choices, list) and len(choices) == 1 and isinstance(choices[0], dict)
                    and type(choices[0].get("index")) is int and choices[0]["index"] == 0
                    and choices[0].get("delta") == {} and choices[0].get("finish_reason") in {"stop", "length", "tool_calls"}
                    and all(isinstance(item, str) and 0 < len(item) <= 256 for item in (identifier, model))):
                raw_prompt = self._integer(timings.get("prompt_n"))
                raw_completion = self._integer(timings.get("predicted_n"))
                raw_cached = self._integer(timings.get("cache_n"))
                raw_start_ms = self._number(timings.get("prompt_ms"), 86_400_000)
                raw_decode_ms = self._number(timings.get("predicted_ms"), 86_400_000)
                raw_rate = self._number(timings.get("predicted_per_second"), 1_000_000)
                raw_prompt_rate = self._number(timings.get("prompt_per_second"), 10_000_000)
                if (None not in (raw_prompt, raw_completion, raw_cached, raw_start_ms, raw_decode_ms, raw_rate, raw_prompt_rate)
                        and raw_completion > 0 and raw_cached <= raw_prompt):
                    expected_prompt_rate = (raw_prompt - raw_cached) * 1000 / raw_start_ms if raw_start_ms else 0
                    if math.isclose(raw_prompt_rate, expected_prompt_rate, rel_tol=1e-6, abs_tol=1e-6):
                        self._splash_final_timing = {
                            "id": identifier, "model": model, "prompt": raw_prompt, "completion": raw_completion,
                            "cached": raw_cached, "start_ms": raw_start_ms, "decode_ms": raw_decode_ms, "rate": raw_rate,
                        }
        if "usage" not in value:
            return
        terminal = getattr(self, "_splash_final_timing", None)
        self._splash_final_timing = None
        # A later final usage observation supersedes the old proof, including
        # malformed/missing native metadata or changed final token counters.
        if self.runtime_stats.get("runtimeStatsSource") == "splash-native-stats":
            for key in ("runtimeStatsSource", "runtimeTokensPerSecond", "runtimeGenerationSeconds",
                        "runtimeTimeToFirstTokenSeconds", "runtimeDecodeTokenCount", "runtimeFirstBatchTokens",
                        "runtimeThroughputBasis"):
                self.runtime_stats.pop(key, None)
        if (self.runtime_stats.get("promptProcessing") or {}).get("source") == "splash-native-stats":
            self.runtime_stats.pop("promptProcessing", None)
        usage, stats = value.get("usage"), value.get("metrics")
        if (value.get("object") != "chat.completion.chunk" or not isinstance(usage, dict)
                or not isinstance(stats, dict) or not terminal
                or terminal["id"] != value.get("id") or terminal["model"] != value.get("model")):
            return
        containers = [stats.get(key) for key in ("prefill", "decode", "cache", "request_latency")]
        if any(not isinstance(item, dict) for item in containers):
            return
        prefill, decode, cache, latency = containers
        prompt = self._integer(usage.get("prompt_tokens"))
        completion = self._integer(usage.get("completion_tokens"))
        processed = self._integer(prefill.get("tokens"))
        decoded = self._integer(decode.get("tokens"))
        cached = self._integer(cache.get("matched_tokens"))
        details = usage.get("prompt_tokens_details")
        reported_cached = self._integer(details.get("cached_tokens")) if isinstance(details, dict) else None
        if (None in (prompt, completion, processed, decoded, cached, reported_cached)
                or prompt != self.prompt_tokens or completion != self.completion_tokens
                or completion < 1 or decoded >= completion or processed + cached != prompt
                or cached != reported_cached or self._integer(usage.get("total_tokens")) != prompt + completion
                or terminal["prompt"] != prompt or terminal["completion"] != completion or terminal["cached"] != cached):
            return
        first_batch = completion - decoded
        start_ms = self._number(latency.get("start_to_first_token_ms"), 86_400_000)
        decode_ms = self._number(latency.get("first_token_to_done_ms"), 86_400_000)
        wall_ms = self._number(latency.get("wall_ms"), 86_400_000)
        ttft_ms = self._number(latency.get("ttft_ms"), 86_400_000)
        if (None in (start_ms, decode_ms, wall_ms, ttft_ms)
                or wall_ms < decode_ms or ttft_ms + .001 < start_ms
                or not math.isclose(wall_ms - decode_ms, ttft_ms, rel_tol=1e-8, abs_tol=.001)
                or not math.isclose(terminal["start_ms"], start_ms, rel_tol=1e-8, abs_tol=.001)
                or not math.isclose(terminal["decode_ms"], decode_ms, rel_tol=1e-8, abs_tol=.001)):
            return
        if "queue_to_start_ms" in latency:
            queue_ms = self._number(latency["queue_to_start_ms"], 86_400_000)
            if queue_ms is None or not math.isclose(ttft_ms - start_ms, queue_ms, rel_tol=1e-8, abs_tol=.001):
                return
        tps = self._number(latency.get("stream_tokens_per_second"), 1_000_000, positive=True)
        if decoded:
            if (decode_ms <= 0 or tps is None
                    or not math.isclose(decoded * 1000 / decode_ms, tps, rel_tol=1e-6, abs_tol=1e-6)
                    or not math.isclose(terminal["rate"], tps, rel_tol=1e-6, abs_tol=1e-6)):
                return
        elif "stream_tokens_per_second" in latency or terminal["rate"] != 0:
            # Native metrics omit the rate when the entire response belongs
            # to its first batch; a fabricated rate must not be retained.
            return
        self.runtime_stats.update(
            runtimeStatsSource="splash-native-stats", runtimeGenerationSeconds=decode_ms / 1000,
            runtimeTimeToFirstTokenSeconds=ttft_ms / 1000, runtimeDecodeTokenCount=decoded,
            runtimeFirstBatchTokens=first_batch,
            runtimeThroughputBasis="request-lifecycle-excluding-first-native-batch",
        )
        if tps is not None:
            self.runtime_stats["runtimeTokensPerSecond"] = tps
        if processed > 0 and start_ms > 0 and processed * 1000 / start_ms <= 10_000_000:
            self.runtime_stats["promptProcessing"] = {
                "source": "splash-native-stats", "processedTokens": processed, "cachedTokens": cached,
                "elapsedSeconds": start_ms / 1000, "tokensPerSecond": round(processed * 1000 / start_ms, 2),
                "basis": "request-start-to-first-native-token",
            }

    def _slotstream_performance(self, value: dict[str, Any]) -> None:
        if self.backend != "slotstream":
            return
        stats = value.get("slotstream_metrics")
        if not isinstance(stats, dict) or type(stats.get("version")) is not int or stats["version"] != 1:
            return
        if stats.get("phase") not in {"prefilled", "completed"}:
            return
        prompt = self._integer(stats.get("prompt_tokens"))
        processed = self._integer(stats.get("processed_tokens"))
        cached = self._integer(stats.get("cached_tokens"))
        seconds = self._number(stats.get("prefill_seconds"), 604800, positive=True)
        if (None in (prompt, processed, cached, seconds) or processed + cached != prompt
                or (self.prompt_tokens is not None and self.prompt_tokens != prompt)):
            return
        speed = processed / seconds
        if not math.isfinite(speed) or speed > 10_000_000:
            return
        self.runtime_stats["promptProcessing"] = {
            "source": "slotstream-native-stats", "tokensPerSecond": round(speed, 2),
            "processedTokens": processed, "cachedTokens": cached, "elapsedSeconds": seconds,
        }
        if stats["phase"] != "completed":
            return
        # Completion counters must agree with ordinary OpenAI usage before
        # publishing native decode or speculation facts.
        tokens = self._integer(stats.get("decode_tokens"))
        elapsed = self._number(stats.get("decode_seconds"), 604800, positive=True)
        if tokens is None or tokens != self.completion_tokens or elapsed is None:
            return
        rate = tokens / elapsed
        if rate <= 1_000_000:
            self.runtime_stats.update(runtimeStatsSource="slotstream-native-stats",
                runtimeTokensPerSecond=round(rate, 4), runtimeGenerationSeconds=elapsed)
        drafted = self._integer(stats.get("drafted_tokens"))
        accepted = self._integer(stats.get("accepted_drafts"))
        if drafted is not None and accepted is not None and 0 <= accepted <= drafted and drafted > 0:
            self.runtime_stats.update(totalDraftTokens=drafted, acceptedDraftTokens=accepted,
                speculativeAcceptancePercent=round(accepted / drafted * 100, 1))
        pool = self._integer(stats.get("expert_pool_bytes"), 1_000_000_000_000)
        slots = self._integer(stats.get("expert_pool_slots"), 24_576)
        hit = self._number(stats.get("expert_hit_rate"), 1)
        if pool is not None and slots is not None and hit is not None:
            self.runtime_stats["expertCache"] = {"allocatedBytes": pool, "slots": slots,
                "hitRatePercent": round(hit * 100, 1)}

    @staticmethod
    def _nonempty(value: Any) -> bool:
        if isinstance(value, str):
            return bool(value)
        if isinstance(value, list):
            return bool(value)
        if isinstance(value, dict):
            return bool(value)
        return value is not None

    def _inspect(self, value: Any) -> bool:
        if not isinstance(value, dict):
            return False
        if self.backend in {"omlx", "mtplx"}:
            identifier = value.get("id")
            if isinstance(identifier, str) and re.fullmatch(r"chatcmpl-[0-9a-f]{8,32}", identifier):
                self.runtime_stats["runtimeResponseId"] = identifier
        if self.backend == "uzu":
            identifier = value.get("id")
            if isinstance(identifier, str) and re.fullmatch(r"chatcmpl-[0-9a-f]{32}", identifier):
                self.runtime_stats["uzuRequestTag"] = identifier[9:17]
        self._usage(value)
        self._performance(value)
        self._slotstream_performance(value)
        self._omlx_performance(value)
        self._kolibri_performance(value)
        self._splash_performance(value)
        emitted = False
        if self.protocol == "chat-completions":
            for choice in value.get("choices") or []:
                if not isinstance(choice, dict):
                    continue
                delta = choice.get("delta")
                message = choice.get("message")
                for container in (delta, message, choice):
                    if not isinstance(container, dict):
                        continue
                    if any(self._nonempty(container.get(key)) for key in (
                        "content", "reasoning", "reasoning_content", "thinking", "tool_calls", "text",
                    )):
                        emitted = True
                        break
                if emitted:
                    break
        else:
            event_type = str(value.get("type") or "")
            emitted = bool(
                event_type.endswith(".delta")
                and any(self._nonempty(value.get(key)) for key in (
                    "delta", "text", "arguments", "content",
                ))
            )
        if emitted:
            self.output_seen = True
        return emitted

    def _line(self, line: bytes) -> bool:
        stripped = line.strip()
        if not stripped.startswith(b"data:"):
            return False
        payload = stripped[5:].strip()
        if not payload or payload == b"[DONE]" or len(payload) > self.maximum:
            return False
        try:
            return self._inspect(self._decoder.loads(payload))
        except (ValueError, UnicodeError, TypeError):
            return False

    def _feed(self, chunk: bytes) -> bool:
        self.outcome.feed(chunk)
        emitted = False
        if self.streaming:
            start = 0
            while start < len(chunk):
                newline = chunk.find(b"\n", start)
                end = len(chunk) if newline < 0 else newline
                if self.discarding_line:
                    # An oversized line may span many reads. Its suffix is
                    # still part of that line, never a new metrics event.
                    self.discarding_line = newline < 0
                elif len(self.buffer) + end - start > self.maximum:
                    self.buffer.clear()
                    self.overflowed = True
                    self.discarding_line = newline < 0
                elif newline < 0:
                    self.buffer.extend(chunk[start:end])
                elif self.buffer:
                    self.buffer.extend(chunk[start:end])
                    emitted = self._line(self.buffer) or emitted
                    self.buffer.clear()
                else:
                    emitted = self._line(chunk[start:end]) or emitted
                start = end + 1
        elif not self.overflowed:
            if len(self.complete) + len(chunk) <= self.maximum:
                self.complete.extend(chunk)
            else:
                self.complete.clear()
                self.overflowed = True
        return emitted

    def feed(self, chunk: bytes) -> bool:
        # Semantic validation and metadata inspection see the same payloads.
        # Reuse decoded objects only during this read, then release all data.
        try:
            return self._feed(chunk)
        finally:
            self._decoder.clear()

    def _finish(self) -> bool:
        self.outcome.finish()
        emitted = False
        if self.streaming and self.buffer:
            emitted = self._line(bytes(self.buffer))
            self.buffer.clear()
        elif not self.streaming and not self.overflowed and self.complete:
            try:
                emitted = self._inspect(self._decoder.loads(self.complete))
            except (ValueError, UnicodeError, TypeError):
                pass
            self.complete.clear()
        return emitted

    def finish(self) -> bool:
        try:
            return self._finish()
        finally:
            self._decoder.clear()

    def public_usage(self) -> tuple[int | None, int | None]:
        return self.prompt_tokens, self.completion_tokens

    def observe_payload(self, value: Any) -> bool:
        """Observe already-decoded metadata; the caller owns framing/result validation."""
        return self._inspect(value)

    def public_runtime_stats(self) -> dict[str, int | float | str]:
        return dict(self.runtime_stats)
