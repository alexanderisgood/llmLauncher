"""Audited MTPLX 2.11.2 adapter for long, single-session 27B Hub runs.

Loaded by the selected runtime's Python. Installed packages are never edited.
All tensor work remains on MTPLX's model-owner thread; the pressure monitor
and native cancellation/error paths remain in control.
"""
from contextvars import ContextVar
from contextlib import contextmanager
from functools import wraps
import hashlib
import inspect
import json
import logging
import os
import sys
from pathlib import Path
import time
import textwrap
import weakref

GIB = 1024**3
POLICY = "hub-prefill-1"
_checkpoint_deadline = ContextVar("launcher_checkpoint_deadline", default=None)
LOG = logging.getLogger(__name__)


@contextmanager
def closing_transaction(connection):
    """SQLite's transaction context commits/rolls back but does not close."""
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def prefill_chunk_size(active, limit, requested=2048):
    """Leave workspace for full-precision attention and cache conversion."""
    available = max(0, limit - active)
    cap = 128 if available < 6 * GIB else 256 if available < 10 * GIB else 512
    return max(1, min(int(requested), cap))


def _compile_patch(original, replacements):
    source = textwrap.dedent(inspect.getsource(original))
    manifest = json.loads((Path(__file__).parent / "runtime_patches/mtplx/2.11.2/admission.json").read_text())
    if hashlib.sha256(source.encode()).hexdigest() != manifest["functions"][original.__qualname__]:
        raise RuntimeError(f"MTPLX {original.__qualname__} changed; the Hub adapter needs review.")
    for before, after in replacements:
        if source.count(before) != 1:
            raise RuntimeError("MTPLX patch does not match the audited source.")
        source = source.replace(before, after)
    namespace = {}
    globals_ = dict(original.__globals__, _launcher_weakref=weakref.ref,
                    _launcher_closing_transaction=closing_transaction,
                    _launcher_runtime_path=str(Path(__file__).resolve()))
    exec(compile(source, str(Path(__file__)) + ":" + original.__name__, "exec"), globals_, namespace)
    return namespace[original.__name__]


def _patched_admission(server):
    return _compile_patch(server._prefill_admission_shed, [
        ('int(getattr(plan, "kv_bytes_per_token_effective", 0) or 0)',
         'max(int(getattr(plan, "kv_bytes_per_token", 0) or 0), int(getattr(plan, "kv_bytes_per_token_effective", 0) or 0))'),
        ('if miss_tokens < _prefill_admission_min_miss_tokens():\n            return None',
         '# Warm restores still need workspace; a short suffix is not free.\n'
         '        raw_kv = int(getattr(plan, "kv_bytes_per_token", 0) or 0)\n'
         '        effective_kv = int(getattr(plan, "kv_bytes_per_token_effective", 0) or 0)\n'
         '        promotion_bytes = reused_tokens * raw_kv if 0 < effective_kv < raw_kv else 0\n'
         '        transients += promotion_bytes'),
    ])


def install(server, generation, bank_type, cold_type, mx, *, version):
    if version != "2.11.2":
        raise RuntimeError("The long-context Hub adapter requires audited MTPLX 2.11.2.")
    if getattr(server, "_launcher_memory_policy", None) == POLICY:
        return
    # Validate before changing any hooks.
    admission = _patched_admission(server)
    for owner, name in ((bank_type, "_enqueue_cold_entry"), (bank_type, "_cold_enqueue_job"),
                        (bank_type, "run_live_ref_spill"), (cold_type, "spill_entry")):
        if not callable(getattr(owner, name, None)):
            raise RuntimeError(f"MTPLX persistence interface changed: {name}")
    original_size = generation._prefill_chunk_size
    original_spans = generation._iter_prefill_chunk_spans
    # Pending persistence must not own evicted snapshots. The bank owns the
    # entry; a queued job may encode it only while it still exists.
    weak_job = 'lambda ref=_launcher_weakref(entry): self._cold_enqueue_job(current, put_entry) if (current := ref()) is not None else None'
    original_enqueue = _compile_patch(bank_type._enqueue_cold_entry, [
        ('lambda: self._cold_enqueue_job(entry, put_entry)', weak_job),
    ])
    cold_job = _compile_patch(bank_type._cold_enqueue_job, [
        ('lambda: self._cold_enqueue_job(entry, put_entry)', weak_job),
    ])
    settle = _compile_patch(bank_type._schedule_snapshot_settle, [
        ('def _settle_job() -> None:',
         'def _settle_job(ref=_launcher_weakref(entry)) -> None:\n'
         '        entry = ref()\n'
         '        if entry is None:\n'
         '            return'),
    ])
    connect = _compile_patch(cold_type._connect, [('return conn', 'return _launcher_closing_transaction(conn)')])
    archive = _compile_patch(cold_type._archive_legacy_store_if_needed, [
        ('with sqlite3.connect(str(manifest), timeout=5.0) as conn:',
         'with _launcher_closing_transaction(sqlite3.connect(str(manifest), timeout=5.0)) as conn:'),
    ])
    original_schedule = bank_type._schedule_live_ref_spill
    original_bank_init = bank_type.__init__
    original_health = server._startup_health_payload

    # MLX exposes a setter, not a memory-limit getter. Use the same explicit
    # byte budget that the native server applies and reports in /health.
    limit = int(os.environ["MTPLX_MEMORY_LIMIT_BYTES"])
    if limit <= 0:
        raise RuntimeError("A positive MTPLX memory limit is required.")

    @wraps(original_bank_init)
    def bank_init(bank, *args, **kwargs):
        original_bank_init(bank, *args, **kwargs)
        bank.max_bytes = min(bank.max_bytes, 12 * GIB)
        bank.per_session_max_bytes = min(bank.per_session_max_bytes, bank.max_bytes)

    def size():
        return prefill_chunk_size(mx.get_active_memory(), limit, original_size())

    @wraps(original_spans)
    def spans(token_count, *, mandatory_edges=(), chunk_size=None):
        requested = size() if chunk_size is None else prefill_chunk_size(
            mx.get_active_memory(), limit, chunk_size)
        return original_spans(token_count, mandatory_edges=mandatory_edges, chunk_size=requested)

    original_spill = cold_type.spill_entry

    @wraps(original_spill)
    def spill(cold, entry, **kwargs):
        deadline = _checkpoint_deadline.get()
        if deadline is None:
            return original_spill(cold, entry, **kwargs)
        # TreeCodec captures this callback. A context-local deadline permits
        # an owner-thread checkpoint despite queued foreground traffic, but
        # the writer thread still sees the real busy state. Never wait for
        # queued GPU work while occupying its executor.
        original_busy = cold.foreground_busy
        def busy():
            local_deadline = _checkpoint_deadline.get()
            if local_deadline is not None:
                return time.monotonic() >= local_deadline or mx.get_active_memory() + GIB >= limit
            return bool(original_busy and original_busy())
        cold.foreground_busy = busy
        try:
            return original_spill(cold, entry, **kwargs)
        finally:
            cold.foreground_busy = original_busy

    def checkpoint(bank, entry):
        now = time.monotonic()
        # Periodic durability, not an 8-10 GB write after every tool call.
        # Native streaming deduplication, disk-space and hourly limits apply.
        needed = int(entry.nbytes or getattr(entry, "oversized_nbytes", 0) or 0)
        due = now - getattr(bank, "_launcher_checkpoint_attempt", float("-inf")) >= 300
        cold = bank.cold_tier
        if entry.cold_encode_completed_at is not None:
            return True
        if (cold is not None and needed >= 4 * GIB and due
                and mx.get_active_memory() + GIB < limit):
            bank._launcher_checkpoint_attempt = now
            token = _checkpoint_deadline.set(now + 30)
            try:
                if entry.live_ref_only:
                    bank.run_live_ref_spill(entry.token_ids, entry.snapshot_epoch)
                else:
                    bank._cold_enqueue_job(entry, cold.put_entry)
                stored = entry.cold_encode_completed_at is not None
                bank._launcher_checkpoint = {"stored": stored, "prefix_tokens": entry.prefix_len,
                    "elapsed_s": round(time.monotonic() - now, 3)}
                LOG.info("Hub SSD checkpoint %s", bank._launcher_checkpoint)
                if stored:
                    return True
            except Exception as error:
                bank._launcher_checkpoint = {"stored": False, "error": str(error)[:300]}
                LOG.warning("Hub SSD checkpoint deferred: %s", error)
            finally:
                _checkpoint_deadline.reset(token)
        return False

    @wraps(original_enqueue)
    def enqueue(bank, entry, timing_out=None):
        if checkpoint(bank, entry):
            return
        return original_enqueue(bank, entry, timing_out)

    @wraps(original_schedule)
    def schedule(bank, entry):
        if checkpoint(bank, entry):
            return
        return original_schedule(bank, entry)

    @wraps(original_health)
    def health(state):
        result = original_health(state)
        result["launcher_memory_policy"] = {
            "version": POLICY, "prefill_kv_accounting": "full_precision",
            "prefill_chunk_max": 512, "checkpoint_interval_s": 300,
            "checkpoint_slice_s": 30,
            "checkpoint": getattr(getattr(getattr(state, "sessions", None), "bank", None), "_launcher_checkpoint", None),
        }
        return result

    server._prefill_admission_shed = admission
    generation._prefill_chunk_size = size
    generation._iter_prefill_chunk_spans = spans
    cold_type.spill_entry = spill
    cold_type._connect = connect
    cold_type._archive_legacy_store_if_needed = archive
    bank_type._cold_enqueue_job = cold_job
    bank_type.__init__ = bank_init
    bank_type._schedule_snapshot_settle = settle
    bank_type._enqueue_cold_entry = enqueue
    bank_type._schedule_live_ref_spill = schedule
    server._startup_health_payload = health
    server._launcher_memory_policy = POLICY


def install_cli(public):
    # `mtplx serve` execs a fresh Python process after applying its profile.
    # Carry the adapter through that handoff, retaining -P and every native
    # server argument, fan watchdog and parent-process lifetime rule.
    public.cmd_serve_public = _compile_patch(public.cmd_serve_public, [
        ('"-m",\n        "mtplx.server.openai",',
         '_launcher_runtime_path,\n        "--server-child",'),
    ])


def main():
    from importlib.metadata import version
    if version("mtplx") != "2.11.2":
        raise RuntimeError("The Hub memory adapter requires MTPLX 2.11.2.")
    if sys.argv[1:2] != ["--server-child"]:
        import mtplx.commands.public as public
        install_cli(public)
        from mtplx.cli import main as cli_main
        return cli_main()
    import mlx.core as mx
    import mtplx.server.openai as server
    import mtplx.generation as generation
    from mtplx.session_bank import SessionBank
    from mtplx.cache_bank.cold_tier import SessionBankColdTier
    install(server, generation, SessionBank, SessionBankColdTier, mx, version=version("mtplx"))
    server.main(sys.argv[2:])


if __name__ == "__main__":
    raise SystemExit(main())
