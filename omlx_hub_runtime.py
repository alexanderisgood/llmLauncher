"""Session-only oMLX adapter: exact DFlash admission and non-executable previews.

The upstream parser and final tool calls are unchanged. A bounded, owner-only
preview file is replaced during generation and removed on completion/cancel.
No prompts or previews are added to the relay's persistent logs.
"""
import json
import copy
from contextlib import aclosing
from functools import wraps
import logging
import math
import os
from pathlib import Path
import re
import inspect
import threading
import time
import uuid
import weakref


DFLASH_HEADROOM_RATIO = .90


class _DFlashPressureEvents:
    """Return unused Metal buffers on the executor, never the monitor thread."""
    def __init__(self, iterator, engine, guard, token_type, mx, prefill_type=None):
        self.iterator = iterator
        self.engine = weakref.ref(engine)
        self.guard = guard
        self.token_type = token_type
        self.prefill_type = prefill_type
        self.mx = mx
        # Native builds and consumes this iterator inside _run_generate_streaming
        # (or generate's _run), on the same dedicated MLX executor thread.
        self.thread_id = threading.get_ident()

    def __iter__(self):
        return self

    def __next__(self):
        if self.iterator is None:
            raise StopIteration
        try:
            event = next(self.iterator)
            if ((type(event) is self.token_type and not event.fallback_ar)
                    or (self.prefill_type is not None and type(event) is self.prefill_type)):
                self.reclaim()
            return event
        except BaseException:
            try:
                self.close()
            except Exception:
                logging.getLogger(__name__).debug(
                    "DFlash pressure observer cleanup failed", exc_info=True)
            raise

    def reclaim(self):
        engine, guard = self.engine(), self.guard
        runtime = getattr(getattr(engine, "_runtime_context", None), "runtime", None)
        if (threading.get_ident() != self.thread_id or engine is None
                or not engine._loaded or engine._in_fallback_mode
                or engine._prefill_guard is not guard
                or not guard._prefill_memory_guard
                or guard._memory_hard_limit_bytes <= 0
                or getattr(runtime, "clear_cache_boundaries", False) is not True):
            return
        requested = getattr(guard, "_launcher_pressure_reclaim_requested", 0)
        if requested == getattr(guard, "_launcher_pressure_reclaim_consumed", 0):
            return
        # Consume this ticket BEFORE synchronizing. A newer monitor request
        # arriving during the clear remains pending for the next token boundary.
        guard._launcher_pressure_reclaim_consumed = requested
        pool = int(self.mx.get_cache_memory())
        if pool <= 0:
            return  # A native periodic boundary already drained the pool.
        # TokenEvent is emitted after target verification/commit. Native may
        # have launched the next draft asynchronously on the default stream;
        # use native's same synchronization before clearing unused buffers.
        # Live KV, recurrent state, draft arrays and snapshots keep their refs.
        self.mx.synchronize()
        self.mx.clear_cache()
        guard.record_mlx_active_memory(self.mx.get_active_memory())
        logging.getLogger(__name__).info(
            "DFlash pressure cache reclaimed at committed boundary "
            "(pool_before_bytes=%d pool_after_bytes=%d)",
            pool, int(self.mx.get_cache_memory()))

    def close(self):
        iterator, self.iterator = self.iterator, None
        if iterator is not None:
            close = getattr(iterator, "close", None)
            if close is not None:
                close()


def install_dflash_pressure_reclaim(engine_type, guard_type, token_type,
                                   enforcer_type, mx, *, versions, prefill_type=None):
    """Connect oMLX's audited pressure signal to DFlash's committed events."""
    if engine_type.__dict__.get("_launcher_pressure_reclaim_installed"):
        return
    if (versions != ("0.6.4", "0.1.10+omlx.7")
            or hasattr(guard_type, "request_pressure_reclaim")
            or not callable(getattr(guard_type, "record_mlx_active_memory", None))
            or not callable(getattr(guard_type, "preflight_or_raise", None))
            or not callable(getattr(enforcer_type, "_request_scheduler_cache_reclaim", None))
            or getattr(enforcer_type, "_POOL_RECLAIM_FLOOR", None) != 2 * 1024**3
            or not {"token_id", "generated_tokens", "fallback_ar"}.issubset(
                getattr(token_type, "__dataclass_fields__", {}))
            or not all(callable(getattr(mx, name, None)) for name in (
                "synchronize", "clear_cache", "get_cache_memory", "get_active_memory"))
            or not callable(getattr(engine_type, "_stream_dflash_events", None))):
        raise RuntimeError("The audited oMLX DFlash pressure-reclaim interface changed.")
    original = engine_type._stream_dflash_events
    if not {"prompt_tokens", "max_tokens"}.issubset(inspect.signature(original).parameters):
        raise RuntimeError("The audited oMLX DFlash event iterator changed.")

    def request_pressure_reclaim(guard):
        # Called by ProcessMemoryEnforcer only after its own pool/headroom
        # checks. Match Scheduler's flag-only contract: no Metal calls here.
        if guard._prefill_memory_guard and guard._memory_hard_limit_bytes > 0:
            guard._launcher_pressure_reclaim_requested = (
                getattr(guard, "_launcher_pressure_reclaim_requested", 0) + 1)

    @wraps(original)
    def events(engine, *args, **kwargs):
        iterator, flow, stops = original(engine, *args, **kwargs)
        guard = engine._prefill_guard
        if (engine._loaded and not engine._in_fallback_mode
                and type(guard) is guard_type):
            iterator = _DFlashPressureEvents(iterator, engine, guard, token_type, mx, prefill_type)
        return iterator, flow, stops

    guard_type.request_pressure_reclaim = request_pressure_reclaim
    engine_type._stream_dflash_events = events
    engine_type._launcher_pressure_reclaim_installed = True


class _DFlashSDPAHeadroom:
    """Live, engine-owned input to oMLX's existing adaptive attention gate."""
    def __init__(self, engine, active_memory):
        self.engine = weakref.ref(engine)
        self.active_memory = active_memory

    def read(self):
        engine = self.engine()
        if (engine is None or not engine._loaded or engine._in_fallback_mode
                or getattr(engine, "_launcher_sdpa256_headroom", None) is not self):
            return -1
        guard = engine._prefill_guard
        if guard is None or guard._memory_hard_limit_bytes <= 0:
            return -1
        # This callback runs on the MLX step thread. Refresh native accounting
        # instead of reusing the admission-time sample as the prompt grows.
        guard.record_mlx_active_memory(self.active_memory())
        return (int(guard._memory_hard_limit_bytes * DFLASH_HEADROOM_RATIO)
                - guard._current_usage_bytes())


def install_dflash_sdpa256(engine_type, sdpa, active_memory):
    """Bind audited oMLX 0.6.4 attention routing without changing its kernels."""
    if engine_type.__dict__.get("_launcher_sdpa256_installed"):
        return
    lifecycle = ("start", "stop", "_evict_dflash_and_start_fallback")
    if (not all(callable(getattr(engine_type, name, None)) for name in lifecycle)
            or not callable(getattr(sdpa, "apply_sdpa256_attention_patch", None))
            or not callable(getattr(sdpa, "set_unfused_headroom_provider", None))
            or not hasattr(sdpa, "_HEADROOM_PROVIDER")
            or getattr(sdpa, "_SDPA256_MIN_Q_LEN", None) != 16):
        raise RuntimeError("The audited oMLX DFlash SDPA256 interface changed.")
    # DFlash-first processes otherwise never install this upstream patch.
    # Keep its shape gates and adaptive/explicit environment policy intact.
    sdpa.apply_sdpa256_attention_patch()
    if getattr(sdpa, "_PATCHED", False) is not True:
        raise RuntimeError("The oMLX SDPA256 attention patch could not be installed.")
    original_start, original_stop, original_fallback = (
        getattr(engine_type, name) for name in lifecycle
    )

    def detach(engine):
        provider = engine.__dict__.pop("_launcher_sdpa256_headroom", None)
        registered = sdpa._HEADROOM_PROVIDER
        if provider is not None and registered is not None:
            # A later engine/scheduler may already own the global upstream slot.
            if getattr(registered(), "__self__", None) is provider:
                sdpa._HEADROOM_PROVIDER = None

    @wraps(original_start)
    async def start(engine, *args, **kwargs):
        if engine._loaded:
            return await original_start(engine, *args, **kwargs)
        detach(engine)
        provider = _DFlashSDPAHeadroom(engine, active_memory)
        engine._launcher_sdpa256_headroom = provider
        sdpa.set_unfused_headroom_provider(provider.read)
        try:
            return await original_start(engine, *args, **kwargs)
        except BaseException:
            detach(engine)
            raise

    @wraps(original_stop)
    async def stop(engine, *args, **kwargs):
        detach(engine)
        return await original_stop(engine, *args, **kwargs)

    @wraps(original_fallback)
    async def fallback(engine, *args, **kwargs):
        detach(engine)
        return await original_fallback(engine, *args, **kwargs)

    engine_type.start = start
    engine_type.stop = stop
    engine_type._evict_dflash_and_start_fallback = fallback
    engine_type._launcher_sdpa256_installed = True


def snapshot_copy_bytes(values):
    """Read array sizes without copying/evaluating cache arrays."""
    if values is None or isinstance(values, (int, float, bool, str)):
        return 0
    if isinstance(values, (tuple, list)):
        return sum(snapshot_copy_bytes(v) for v in values)
    if isinstance(values, dict):
        return sum(snapshot_copy_bytes(v) for v in values.values())
    size = getattr(values, "nbytes", None)
    if isinstance(size, int) and size >= 0:
        return size
    return snapshot_copy_bytes(values.state)


class _SnapshotHiddenShape:
    """Run native snapshot slicing on dimensions, without allocating arrays."""
    def __init__(self, shape, itemsize):
        self.shape = shape
        self.itemsize = itemsize
        self.nbytes = math.prod(shape) * itemsize

    def __getitem__(self, key):
        if (not isinstance(key, tuple) or len(key) != 3
                or key[0] != slice(None) or key[2] != slice(None)
                or not isinstance(key[1], slice)):
            raise ValueError("Unknown native hidden-feature slice")
        rows = len(range(self.shape[1])[key[1]])
        return _SnapshotHiddenShape((self.shape[0], rows, self.shape[2]), self.itemsize)


def snapshot_hidden_copy_bytes(service, values, hidden_chunk_builder=None):
    """Bound joined hidden spans using the same trim policy as native build."""
    hidden = values.get("target_hidden")
    full_bytes = snapshot_copy_bytes(hidden)
    if hidden_chunk_builder is None:
        return full_bytes
    try:
        shape = tuple(int(dim) for dim in hidden.shape)
        prefix_len = len(values["token_ids"])
        itemsize = int(hidden.dtype.size)
        if (len(shape) != 3 or min(shape) < 0 or not 0 <= prefix_len <= shape[1]
                or itemsize <= 0):
            raise ValueError("Unknown native hidden-feature geometry")
        builder = service._builder
        # build_snapshot first trims hidden features to the token prefix. The
        # native helper then keeps its configured sink/tail, extending the tail
        # around a sidecar boundary or retaining full-attention coverage.
        chunks, _spans, _total = hidden_chunk_builder(
            _SnapshotHiddenShape((shape[0], prefix_len, shape[2]), itemsize),
            draft_model=builder.draft_model,
            draft_sink_size=builder.draft_sink_size,
            draft_window_size=builder.draft_window_size,
            allow_full_attention_context=values.get("allow_full_attention_context", False),
            clone=False, cover_boundary=int(values.get("sidecar_boundary", 0)),
        )
        return sum(chunk.nbytes for chunk in chunks)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError, OverflowError):
        # Changed native interfaces never make the memory guard more permissive.
        return full_bytes


def make_snapshot_reclaimer(manager_type, l1_type, mx, *, versions):
    """Release the single obsolete L1 entry before building its replacement."""
    if (versions != ("0.6.4", "0.1.10+omlx.7")
            or not all(callable(getattr(manager_type, name, None)) for name in (
                "maybe_insert_snapshot", "lookup"))
            or not callable(getattr(l1_type, "insert_with_evictions", None))
            or not all(callable(getattr(mx, name, None)) for name in (
                "synchronize", "clear_cache"))):
        raise RuntimeError("The audited DFlash snapshot replacement interface changed.")

    def reclaim(service, incoming_bytes):
        manager = getattr(service, "_cache_manager", None)
        if type(manager) is not manager_type:
            return False
        # Match native lock order. Neither shutdown nor another lookup can
        # retire/change this entry while its replacement eligibility is checked.
        with manager._state_lock:
            if manager._retired:
                return False
            store = manager._store
            l1 = getattr(store, "_l1", None)
            if type(l1) is not l1_type or store._l2 is not None:
                return False
            with l1._lock:
                if (l1._max_entries != 1 or len(l1._entries) != 1
                        or not 0 < incoming_bytes <= l1._max_bytes):
                    return False
                old = next(iter(l1._entries.values()))
                if old.kind != "generation":
                    return False  # Native can prefer an exact prefill entry.
                old_tokens = int(old.prefix_len)
                # With one slot and an incoming generation that fits, native
                # insertion necessarily evicts this generation entry. Doing it
                # after snapshot allocation needlessly retains both requests.
                l1._entries.clear()
                l1._lru_order.clear()
                l1._stats["evictions"] += 1
                del old
        # Called only by the generation-publication guard on the native MLX
        # executor. Drop actual references, then measure after native cleanup;
        # never subtract a logical cache size from physical memory accounting.
        mx.synchronize()
        mx.clear_cache()
        logging.getLogger(__name__).info(
            "Released superseded single-entry DFlash generation snapshot "
            "before replacement (tokens=%d)", old_tokens)
        return True

    return reclaim


def install_memory_headroom(guard_type, snapshot_type, active_memory, footprint,
                            hidden_chunk_builder=None, snapshot_reclaimer=None):
    """Reserve workspace below native eviction; never increase native limits."""
    original_preflight = guard_type.preflight_or_raise
    original_publish = snapshot_type.publish
    budget = {"limit": 0, "guard": None}

    def preflight(guard, *args, **kwargs):
        # Native DFlash admission checks the ceiling, but the enforcer queues
        # model eviction at 95% of it. Leave 10% for decode/cache transients.
        # Copy instead of mutating the guard written by the enforcer thread.
        admission = copy.copy(guard)
        ceiling = max(0, int(guard._memory_hard_limit_bytes))
        admission._memory_hard_limit_bytes = int(ceiling * DFLASH_HEADROOM_RATIO)
        budget["limit"] = admission._memory_hard_limit_bytes
        budget["guard"] = weakref.ref(guard)
        return original_preflight(admission, *args, **kwargs)

    def publish(service, **kwargs):
        # Snapshot construction can allocate before the cache's size/entry
        # limits evict anything. Skip this optional optimisation BEFORE build.
        try:
            retained_upper_bound = size = snapshot_copy_bytes([kwargs.get(name) for name in (
                "target_cache", "target_hidden", "last_logits",
                "sidecar_gdn_states", "sidecar_last_logits",
            )])
            manager = getattr(service, "_cache_manager", None)
            store = getattr(manager, "_store", None)
            adopted = (
                kwargs.get("kind") == "generation"
                and kwargs.get("adopt_cache_arrays") is True
                and not kwargs.get("l2_only", False)
                and store is not None
                and getattr(store, "_l2", False) is None
            )
            if adopted:
                # Native generation snapshots retain the already-resident KV,
                # recurrent state and logits. Charging another two full caches
                # rejects safe snapshots and causes full prefills next turn.
                # Hidden-chunk joining can allocate its retained sink/tail, not
                # another full prompt's hidden features. Keep two copies of
                # those exact native spans plus the fixed workspace reserve.
                # L2/copied snapshots retain the original full allowance.
                size = snapshot_hidden_copy_bytes(service, kwargs, hidden_chunk_builder)
            active_bytes, footprint_bytes = int(active_memory()), int(footprint())
            current = max(active_bytes, footprint_bytes)
            projected = current + 2 * size + 1024**3
            guard = budget["guard"]() if budget["guard"] is not None else None
            # The native enforcer may lower its ceiling during generation.
            limit = min(budget["limit"], int(max(0, guard._memory_hard_limit_bytes)
                        * DFLASH_HEADROOM_RATIO)) if guard is not None else 0
            allowed = limit > 0 and projected <= limit
            if (not allowed and limit > 0 and adopted and snapshot_reclaimer is not None
                    and snapshot_reclaimer(service, retained_upper_bound)):
                active_bytes, footprint_bytes = int(active_memory()), int(footprint())
                current = max(active_bytes, footprint_bytes)
                projected = current + 2 * size + 1024**3
                # A pressure tick can lower the ceiling during cleanup.
                limit = min(limit, int(max(0, guard._memory_hard_limit_bytes)
                            * DFLASH_HEADROOM_RATIO)) if guard is not None else 0
                allowed = limit > 0 and projected <= limit
        except (AttributeError, TypeError, ValueError, OverflowError):
            logging.getLogger(__name__).info(
                "Skipped optional DFlash snapshot: unknown allocation layout")
            return None
        if not allowed:
            logging.getLogger(__name__).info(
                "Skipped optional DFlash snapshot to preserve memory headroom "
                "(kind=%s adopted=%s active_bytes=%d footprint_bytes=%d "
                "current_bytes=%d projected_bytes=%d limit_bytes=%d)",
                kwargs.get("kind"), adopted, active_bytes, footprint_bytes, current, projected, limit)
            return None
        return original_publish(service, **kwargs)

    guard_type.preflight_or_raise = preflight
    snapshot_type.publish = publish


def tool_preview(text):
    """Best-effort display of Qwen's partial XML call; never used for execution."""
    start = text.rfind("<tool_call>")
    if start < 0:
        return None
    body = text[start + len("<tool_call>"):]
    if "</tool_call>" in body:
        return None
    function = re.match(r"\s*<function=([\w.-]{1,128})>", body)
    if not function:
        return {"title": "Writing · tool call", "text": body[-60000:]}
    args = {}
    for parameter in re.finditer(r"<parameter=([\w.-]{1,128})>", body):
        value = body[parameter.end():].split("</parameter>", 1)[0]
        # Incomplete delimiter suffixes should not flicker in the code panel.
        value = re.sub(r"<[/\w]*$", "", value).strip("\n")
        try:
            args[parameter[1]] = json.loads(value)
        except ValueError:
            args[parameter[1]] = value
    return {"title": "Writing · " + function[1], "text": json.dumps(args, ensure_ascii=False)}


def bounded_preview_text(text):
    """Keep the call header and newest output when a single call fills the tail."""
    maximum = 256000
    if len(text) <= maximum:
        return text
    start = text.rfind("<tool_call>")
    if (start >= 0 and len(text) - start > maximum
            and "</tool_call>" not in text[start:]):
        # This is display-only text, never a source of executable arguments.
        # Preserve function/path/parameter headers for long write/edit calls;
        # tool_preview still limits the visible content to its newest 60K.
        head = text[start:start + 4096]
        return head + text[-(maximum - len(head)):]
    return text[-maximum:]


class PreviewWriter:
    def __init__(self, path, response_id):
        self.path = Path(path)
        self.response_id = response_id
        self.text = ""
        self.last_write = 0.0

    def feed(self, delta):
        self.text = bounded_preview_text(self.text + delta)
        now = time.monotonic()
        if now - self.last_write < .25:
            return
        self.last_write = now
        preview = tool_preview(self.text)
        if preview is None:
            self.clear()
            return
        preview.update(responseId=self.response_id, updatedAt=time.time())
        text = preview["text"]
        try:
            args = json.loads(text)
            path = str(args.get("path") or args.get("file_path") or "")[:1024]
            if isinstance(args.get("content"), str):
                text = path + "\n\n" + args["content"][-58000:]
            elif isinstance(args.get("command"), str):
                text = args["command"]
            elif isinstance(args.get("edits"), list):
                text = path + "\n\n" + "\n\n".join(
                    "Before:\n" + str(edit.get("oldText", ""))
                    + "\n\nAfter:\n" + str(edit.get("newText", ""))
                    for edit in args["edits"] if isinstance(edit, dict)
                )
        except (ValueError, AttributeError):
            pass
        preview["text"] = text[-60000:]
        temporary = self.path.with_suffix(".tmp")
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as handle:
                json.dump(preview, handle, ensure_ascii=False)
            os.replace(temporary, self.path)
        except OSError:
            pass  # Rendering must never interrupt model output.

    def clear(self):
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass


def bounded_output(prompt_count, requested, context):
    remaining = context - prompt_count
    if remaining <= 0:
        raise ValueError(
            f"context_length_exceeded: The prompt has {prompt_count} tokens "
            f"and fills the {context}-token context window. Compact the conversation."
        )
    return min(requested, remaining)


class PrefillWriter:
    """Bounded numeric receipts, keyed to the public response ID; no text."""
    def __init__(self, path, response_id):
        self.path = Path(path)
        self.response_id = response_id
        self.record = {"responseId": response_id, "startedAt": time.time(), "phase": "prefill"}
        self.publish()

    def publish(self):
        try:
            records = json.loads(self.path.read_text()) if self.path.exists() else []
            records = [r for r in records if isinstance(r, dict) and r.get("responseId") != self.response_id][-31:]
            records.append({**self.record, "updatedAt": time.time()})
            temporary = self.path.with_suffix(".tmp")
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as handle:
                json.dump(records, handle, allow_nan=False)
            os.replace(temporary, self.path)
        except (OSError, ValueError, TypeError):
            pass

    def observe(self, event):
        # These are the native DFlash counters and its own prefill clock.
        if type(event).__name__ != "PrefillCompleteEvent":
            return
        elapsed = getattr(event, "prefill_us", None)
        prompt = getattr(event, "prompt_token_count", None)
        computed = getattr(event, "prefill_tokens_computed", None)
        restored = getattr(event, "prefill_tokens_restored", None)
        if (not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed <= 0
                or not all(type(n) is int and n >= 0 for n in (prompt, computed, restored))
                or computed + restored != prompt):
            return
        self.record.update(phase="decode", promptTokens=prompt,
            processedTokens=computed, cachedTokens=restored,
            elapsedSeconds=elapsed / 1e6, tokensPerSecond=computed * 1e6 / elapsed)
        self.publish()

    def events(self, iterator):
        try:
            for event in iterator:
                self.observe(event)
                yield event
        finally:
            close = getattr(iterator, "close", None)
            if close:
                close()

    def finish(self):
        self.record["phase"] = "finished"
        self.publish()


def install(server, context, preview_path):
    original = server.stream_chat_completion

    async def stream(engine, messages, request, *args, **kwargs):
        response_id = kwargs.get("response_id") or "chatcmpl-" + uuid.uuid4().hex[:8]
        kwargs["response_id"] = response_id
        writer = PreviewWriter(preview_path, response_id)
        prefill = PrefillWriter(Path(preview_path).with_name("prompt-stats.json"), response_id)

        class EngineView:
            active_stream = None

            def __getattr__(self, name):
                return getattr(engine, name)

            def stream_chat(self, messages, **generation):
                if self.active_stream is not None:
                    raise RuntimeError("A Hub response cannot own two generation streams.")
                self.active_stream = self._stream_chat(messages, **generation)
                return self.active_stream

            async def close(self):
                if self.active_stream is not None:
                    await self.active_stream.aclose()

            async def _stream_chat(self, messages, **generation):
                # Bind the guard to the exact text-only DFlash implementation
                # selected by build_omlx; unknown/fallback engines fail closed.
                if type(engine).__name__ != "DFlashEngine" or engine._in_fallback_mode:
                    raise ValueError("The guarded DFlash route changed engines; restart the session.")
                if (getattr(engine, "_fallback_engine_type", None) == "vlm"
                        and engine._has_multimodal_content(messages)):
                    raise ValueError("The guarded DFlash route requires text-only messages.")
                from omlx.api.tool_calling import convert_tools_for_template
                template_tools = generation.get("tools")
                if template_tools:
                    template_tools = convert_tools_for_template(template_tools)
                prompt = engine._apply_chat_template(
                    messages, template_tools,
                    chat_template_kwargs=generation.get("chat_template_kwargs"),
                    is_partial=generation.get("is_partial"),
                )
                tokens = engine._tokenize_prompt(prompt)
                generation["max_tokens"] = bounded_output(
                    len(tokens), int(generation.get("max_tokens", request.max_tokens or 256)), context,
                )
                # The audited native stream_chat does only fallback dispatch
                # and this template render before calling stream_generate.
                # Reuse the exact IDs counted by the guard. stream_generate
                # still owns context fallback, thinking budgets and sampling.
                generation.pop("chat_template_kwargs", None)
                generation.pop("is_partial", None)
                original_events = getattr(engine, "_stream_dflash_events", None)
                def observed_events(*event_args, **event_kwargs):
                    iterator, flow, stops = original_events(*event_args, **event_kwargs)
                    return prefill.events(iterator), flow, stops
                if callable(original_events):
                    engine._stream_dflash_events = observed_events
                try:
                    async with aclosing(engine.stream_generate(prompt=tokens, **generation)) as native:
                        async for output in native:
                            if output.new_text:
                                if prefill.record["phase"] == "prefill":
                                    prefill.record["phase"] = "decode"
                                    prefill.publish()
                                writer.feed(output.new_text)
                            yield output
                finally:
                    if callable(original_events) and engine._stream_dflash_events is observed_events:
                        engine._stream_dflash_events = original_events

        view = EngineView()
        try:
            async with aclosing(original(view, messages, request, *args, **kwargs)) as response:
                async for chunk in response:
                    yield chunk
        finally:
            # Upstream uses a bare async-for; closing its outer generator does
            # not close the inner one. Keep ownership until native cancellation
            # has drained and the temporary event observer has been restored.
            try:
                await view.close()
            finally:
                writer.clear()
                prefill.finish()

    server.stream_chat_completion = stream


def main():
    from importlib.metadata import version
    import omlx.server as server
    import mlx.core as mx
    from omlx.engine.dflash import DFlashEngine, _DFlashPrefillGuard, get_phys_footprint
    quantized_kv = os.environ.get("LLM_LAUNCHER_DFLASH_KV", "off")
    if quantized_kv != "off":
        if quantized_kv not in ("q4", "q6", "q8"):
            raise ValueError("Invalid DFlash target KV precision.")
        from dflash_quantized_kv import install_quantized_kv
        install_quantized_kv(DFlashEngine, int(quantized_kv[1:]),
            versions=(version("omlx"), version("dflash-mlx")))
    from omlx.patches import sdpa256_attention
    install_dflash_sdpa256(DFlashEngine, sdpa256_attention, mx.get_active_memory)
    from omlx.process_memory_enforcer import ProcessMemoryEnforcer
    from dflash_mlx.engine.events import TokenEvent, PrefillProgressEvent
    install_dflash_pressure_reclaim(DFlashEngine, _DFlashPrefillGuard, TokenEvent,
        ProcessMemoryEnforcer, mx, versions=(version("omlx"), version("dflash-mlx")),
        prefill_type=PrefillProgressEvent)
    from dflash_thinking_budget import install_dflash_thinking_budget
    install_dflash_thinking_budget(DFlashEngine)
    from dflash_mlx.cache.snapshot_service import SnapshotService
    from dflash_mlx.cache.snapshot import TargetHiddenChunks
    from dflash_mlx.engine.target_features import TargetFeatureStore
    from dflash_snapshot import install_chunked_snapshot_features, install_chunked_prefill_features
    install_chunked_snapshot_features(TargetFeatureStore, TargetHiddenChunks,
        versions=(version("omlx"), version("dflash-mlx")))
    install_chunked_prefill_features(TargetFeatureStore, TargetHiddenChunks, mx,
        versions=(version("omlx"), version("dflash-mlx")))
    from dflash_mlx.cache.codecs import _build_target_hidden_chunks
    from dflash_mlx.cache.manager import RuntimeCacheManager
    from dflash_mlx.cache.prefix_l1 import DFlashPrefixCache
    reclaim_snapshot = make_snapshot_reclaimer(RuntimeCacheManager, DFlashPrefixCache,
        mx, versions=(version("omlx"), version("dflash-mlx")))
    install_memory_headroom(_DFlashPrefillGuard, SnapshotService, mx.get_active_memory,
                            get_phys_footprint, _build_target_hidden_chunks, reclaim_snapshot)
    from omlx_admission import install_prefill_reclaim
    from omlx.exceptions import PrefillMemoryExceededError
    from omlx.engine_core import get_mlx_executor
    install_prefill_reclaim(DFlashEngine, _DFlashPrefillGuard, PrefillMemoryExceededError,
        mx, get_mlx_executor, versions=(version("omlx"), version("dflash-mlx")))
    context = int(os.environ["LLM_LAUNCHER_OMLX_CONTEXT"])
    install(server, context, os.environ["LLM_LAUNCHER_OMLX_PREVIEW"])
    from omlx.cli import main as cli_main
    cli_main()


if __name__ == "__main__":
    main()
