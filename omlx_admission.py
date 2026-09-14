"""Recheck DFlash admission after releasing unused allocator buffers.

The original typed memory guard remains authoritative. All Metal work runs on
its owning executor, with no model/KV/snapshot eviction and no limit changes.
"""
import asyncio
from functools import wraps
import inspect
import logging
import threading


def install_prefill_reclaim(engine_type, guard_type, refusal_type, mx, executor, *, versions):
    if engine_type.__dict__.get('_launcher_prefill_reclaim_installed'):
        return
    methods = ('preflight_chat', 'preflight_completion')
    if (versions != ('0.6.4', '0.1.10+omlx.7')
            or not all(inspect.iscoroutinefunction(getattr(engine_type, name, None)) for name in methods)
            or not callable(getattr(guard_type, 'record_mlx_active_memory', None))
            or not all(callable(getattr(mx, name, None)) for name in
                       ('get_active_memory', 'get_cache_memory', 'synchronize', 'clear_cache'))
            or not isinstance(refusal_type, type) or not issubclass(refusal_type, Exception)):
        raise RuntimeError('The audited DFlash admission-reclaim interface changed.')

    def eligible(engine, guard):
        return (type(guard) is guard_type and engine._prefill_guard is guard
                and engine._loaded and not engine._in_fallback_mode
                and not engine._active_request and guard._prefill_memory_guard
                and guard._memory_hard_limit_bytes > 0)

    def wrap(original):
        @wraps(original)
        async def preflight(engine, *args, **kwargs):
            try:
                return await original(engine, *args, **kwargs)
            except refusal_type:
                guard = engine._prefill_guard
                if not eligible(engine, guard):
                    raise
                cancelled = threading.Event()

                def reclaim():
                    # Revalidate AFTER waiting for executor ownership: the engine
                    # may have stopped, switched routes, or started other work.
                    if cancelled.is_set() or not eligible(engine, guard):
                        return False
                    pool = int(mx.get_cache_memory())
                    if pool > 0:
                        mx.synchronize()
                        if cancelled.is_set() or not eligible(engine, guard):
                            return False
                        mx.clear_cache()
                    guard.record_mlx_active_memory(mx.get_active_memory())
                    logging.getLogger(__name__).info(
                        'DFlash admission refreshed before one guarded recheck '
                        '(unused_pool_before_bytes=%d unused_pool_after_bytes=%d)',
                        pool, int(mx.get_cache_memory()))
                    return True

                try:
                    refreshed = await asyncio.get_running_loop().run_in_executor(executor(), reclaim)
                except asyncio.CancelledError:
                    cancelled.set()
                    raise
                except Exception:
                    logging.getLogger(__name__).warning('DFlash admission cleanup failed', exc_info=True)
                    refreshed = False
                if not refreshed:
                    raise
                # One recheck only. No request replay, sampling, or cache-token
                # discount: DFlash still pays for its full cloned prompt KV.
                return await original(engine, *args, **kwargs)
        return preflight

    for name in methods:
        setattr(engine_type, name, wrap(getattr(engine_type, name)))
    engine_type._launcher_prefill_reclaim_installed = True
