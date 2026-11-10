"""Request-bound native mlx-lm metrics, including buffered function-tool output.

The generator's counters/timers are observed before each yielded token. A
producer queue associates its GenerationContext with that request; the HTTP
thread retains the same context until final usage. Queued or concurrent HTTP
requests never share a global last-response record. Only primitive numbers
are retained: no logprob tensors, model arrays, messages or output text.

These hooks target the qualified sequential mlx-lm0.31.3 server. They observe
the existing generator and queue; math, sampling, tokenization and KV remain
unchanged. Native fields are emitted only when HTTP/native token counts agree.
"""
from __future__ import annotations

from functools import wraps
import math
import threading
from typing import Any

VERSION = 1
MAX_TOKENS = 2_000_000_000
MAX_SECONDS = 86_400
MAX_TPS = 10_000_000


def _integer(value):
    return value if isinstance(value,int) and not isinstance(value,bool) and 0 <= value <= MAX_TOKENS else None


def _positive(value, maximum):
    if isinstance(value,bool) or not isinstance(value,(int,float)):
        return None
    try:
        value = float(value)
    except (ValueError,OverflowError):
        return None
    return value if math.isfinite(value) and 0 < value <= maximum else None


class NativeMetrics:
    def __init__(self):
        self._lock = threading.Lock()
        self._last = None

    def observe(self, response):
        processed = _integer(getattr(response,"prompt_tokens",None))
        generated = _integer(getattr(response,"generation_tokens",None))
        prompt_tps = _positive(getattr(response,"prompt_tps",None),MAX_TPS)
        generation_tps = _positive(getattr(response,"generation_tps",None),1_000_000)
        valid = None not in (processed,generated,prompt_tps,generation_tps) and generated > 0
        with self._lock:
            self._last = (processed,generated,prompt_tps,generation_tps) if valid else None

    def usage(self, context, usage):
        if not isinstance(usage,dict) or getattr(context,"_should_stop",False):
            return None
        with self._lock:
            last = self._last
        if last is None:
            return None
        processed,generated,prompt_tps,generation_tps = last
        prompt = _integer(usage.get("prompt_tokens"))
        completion = _integer(usage.get("completion_tokens"))
        details = usage.get("prompt_tokens_details")
        cached = _integer(details.get("cached_tokens")) if isinstance(details,dict) else None
        context_cached = _integer(getattr(context,"prompt_cache_count",None))
        if (None in (prompt,completion,cached,context_cached) or generated != completion
                or processed+cached != prompt or cached != context_cached
                or prompt != len(context.prompt) or _integer(usage.get("total_tokens")) != prompt+completion):
            return None
        generation_seconds = _positive(generated/generation_tps,MAX_SECONDS)
        prompt_seconds = _positive(processed/prompt_tps,MAX_SECONDS) if processed else None
        if generation_seconds is None or (processed and prompt_seconds is None):
            return None
        result = {
            "kolibri_native_stats":{"version":VERSION,"prompt_tokens":prompt,
                "processed_prompt_tokens":processed,"cached_prompt_tokens":cached,
                "generation_tokens":generated},
            "generation_duration":generation_seconds,
            "generation_tokens_per_second":generation_tps,
        }
        if prompt_seconds is not None:
            result["prompt_eval_duration"] = prompt_seconds
        return result


class _QueueObserver:
    def __init__(self, queue, context_type, producer):
        self._queue,self._context_type,self._producer = queue,context_type,producer

    def put(self, value, *args, **kwargs):
        if isinstance(value,self._context_type):
            value._kolibri_native_metrics = NativeMetrics()
            self._producer.context = value
        return self._queue.put(value,*args,**kwargs)

    def __getattr__(self, name):
        return getattr(self._queue,name)


def install(server: Any) -> None:
    """Attach numeric observations to the existing sequential server path."""
    if getattr(server,"_kolibri_native_metrics_installed",False):
        return
    generator = server.ResponseGenerator
    handler = server.APIHandler
    if not all(callable(value) for value in (generator._serve_single,generator.generate,
                                            handler.completion_usage_response,server.stream_generate)):
        raise ValueError("The qualified Kolibri native metrics boundary is unavailable")
    producer,consumer = threading.local(),threading.local()
    serve_single,generate = generator._serve_single,generator.generate
    stream_generate,usage_response = server.stream_generate,handler.completion_usage_response

    @wraps(serve_single)
    def observed_single(self, request):
        previous = getattr(producer,"context",None)
        producer.context = None
        queue,completion,args = request
        try:
            return serve_single(self,(_QueueObserver(queue,server.GenerationContext,producer),completion,args))
        finally:
            producer.context = previous

    @wraps(stream_generate)
    def observed_stream(*args, **kwargs):
        context = getattr(producer,"context",None)
        metrics = getattr(context,"_kolibri_native_metrics",None)
        iterator = stream_generate(*args,**kwargs)
        try:
            for response in iterator:
                if metrics is not None:
                    metrics.observe(response)
                # Update before the native producer queues this response.
                # The HTTP handler may consume a terminal frame immediately.
                yield response
        finally:
            close = getattr(iterator,"close",None)
            if close is not None:
                close()

    @wraps(generate)
    def observed_generate(self, *args, **kwargs):
        consumer.context = None
        context,response = generate(self,*args,**kwargs)
        consumer.context = context
        return context,response

    @wraps(usage_response)
    def observed_usage(self, *args, **kwargs):
        response = usage_response(self,*args,**kwargs)
        context = getattr(consumer,"context",None)
        consumer.context = None
        metrics = getattr(context,"_kolibri_native_metrics",None)
        if metrics is not None and isinstance(response,dict):
            usage = response.get("usage")
            native = metrics.usage(context,usage)
            if native is not None:
                usage.update(native)
        return response

    generator._serve_single = observed_single
    generator.generate = observed_generate
    server.stream_generate = observed_stream
    handler.completion_usage_response = observed_usage
    server._kolibri_native_metrics_installed = True
