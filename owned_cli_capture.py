"""Bounded bytes from one newly spawned CLI session; no foreign-process scan.

The child remains unreaped until its owned process group has been retired.
waitid(WNOWAIT) proves that exact parent-child relationship before every signal,
so an exited leader's PID cannot be reused while descendants retain its pipe.
"""
from __future__ import annotations
import ctypes
import math
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time
from typing import Mapping, Sequence, Any, Callable


class CaptureLimitError(RuntimeError):
    pass


class CaptureCancelled(RuntimeError):
    pass


class CaptureOwnershipError(RuntimeError):
    pass


def _darwin_group_is_terminal(pgid: int) -> bool:
    """Recognize Darwin's EPERM for an owned group containing only zombies.

    Query only the retained new-session group, bounded to 1,024 members. The
    SDK's proc_listpgrppids returns a PID count (not proc_listpids' byte count).
    Unknown, changed, excessive or nonterminal members never authorize success.
    """
    if sys.platform != 'darwin':
        return False
    from retitled_servers import _BSDInfo
    if ctypes.sizeof(_BSDInfo) != 136 or _BSDInfo.status.offset != 4:
        return False
    try:
        library = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
        group = library.proc_listpgrppids
        group.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
        group.restype = ctypes.c_int
        members = (ctypes.c_int * 1024)()
        ctypes.set_errno(0)
        count = group(pgid, members, ctypes.sizeof(members))
        if not 0 <= count < len(members) or ctypes.get_errno():
            return False
        info = library.proc_pidinfo
        info.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
        info.restype = ctypes.c_int
        for pid in members[:count]:
            if pid == pgid:
                continue  # The caller freshly proved its retained exited leader.
            details = _BSDInfo()
            if (pid <= 1 or info(pid, 3, 0, ctypes.byref(details), ctypes.sizeof(details)) != ctypes.sizeof(details)
                    or details.pid != pid or details.pgid != pgid or details.status != 5):
                return False
        return True
    except (OSError, AttributeError, ValueError, ctypes.ArgumentError):
        return False


def capture_owned_cli(
    argv: Sequence[str], *, timeout: float, max_bytes: int,
    environment: Mapping[str, str] | None = None, cwd: str | Path | None = None,
    cancel_event: Any = None, terminate_grace: float = 0.1,
    on_bytes: Callable[[bytes], None] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Return complete bounded output, or fail after retiring only this session.

    Output is bytes so callers retain their existing decoding/character quota.
    No poll()/wait() reaps the leader before TERM/KILL. Cancellation, overflow,
    silence, and an exited leader with inherited pipes all have bounded cleanup.
    """
    if (not argv or not isinstance(argv[0], str) or not argv[0]
            or any(not isinstance(item, str) or '\0' in item for item in argv)):
        raise ValueError('Choose a nonempty command argument vector.')
    if type(max_bytes) is not int or max_bytes < 0:
        raise ValueError('The CLI output quota must be a nonnegative byte count.')
    if isinstance(timeout, bool) or not isinstance(timeout, (float, int)) or not math.isfinite(timeout) or timeout < 0:
        raise ValueError('The CLI timeout must be finite and nonnegative.')
    if isinstance(terminate_grace, bool) or not isinstance(terminate_grace, (float, int)) or not math.isfinite(terminate_grace) or not 0 <= terminate_grace <= 5:
        raise ValueError('The CLI cleanup grace must be between zero and five seconds.')
    if on_bytes is not None and not callable(on_bytes):
        raise ValueError('The CLI output observer must be callable.')
    if not all(hasattr(os, name) for name in ('waitid', 'P_PID', 'WEXITED', 'WNOHANG', 'WNOWAIT')):
        raise RuntimeError('This host cannot retain safe ownership of a CLI child.')
    if cancel_event is not None and cancel_event.is_set():
        raise CaptureCancelled('CLI inspection was cancelled.')
    process = subprocess.Popen(
        list(argv), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, start_new_session=True, close_fds=True,
        env=dict(environment) if environment is not None else None,
        cwd=str(cwd) if cwd is not None else None, bufsize=0,
    )
    output = bytearray()
    owned = True
    retired = False
    eof = False
    failure: BaseException | None = None
    stream = process.stdout

    def observe() -> Any:
        nonlocal owned
        if not owned:
            raise CaptureOwnershipError('The CLI child is no longer owned; no signal was sent.')
        try:
            value = os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        except (ChildProcessError, OSError) as error:
            owned = False
            raise CaptureOwnershipError('The CLI child could not be revalidated; no signal was sent.') from error
        if value is not None and getattr(value, 'si_pid', process.pid) not in (0, process.pid):
            owned = False
            raise CaptureOwnershipError('The CLI child identity changed; no signal was sent.')
        return value if value is not None and getattr(value, 'si_pid', 0) == process.pid else None

    def send(sig: int) -> None:
        observe()
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass
        except PermissionError:
            if observe() is None or not _darwin_group_is_terminal(process.pid):
                raise
            observe()  # Still our retained child after the native group query.

    def drain(*, collect: bool, wait: float = 0.0) -> None:
        nonlocal eof
        if eof or stream is None:
            if wait:
                time.sleep(wait)
            return
        ready, _, _ = select.select([stream.fileno()], [], [], wait)
        if not ready:
            return
        try:
            data = os.read(stream.fileno(), 32 * 1024)
        except BlockingIOError:
            return
        if not data:
            eof = True
        elif collect:
            available = max_bytes + 1 - len(output)
            output.extend(data[:max(0, available)])
            if len(output) > max_bytes:
                raise CaptureLimitError(f'The CLI output exceeded its {max_bytes}-byte quota.')
            if on_bytes is not None:
                on_bytes(data)

    def retire(*, collect: bool) -> None:
        nonlocal retired
        if retired or not owned:
            return
        send(signal.SIGTERM)
        try:
            deadline = time.monotonic() + terminate_grace
            while time.monotonic() < deadline:
                drain(collect=collect, wait=min(0.02, max(0.0, deadline - time.monotonic())))
        finally:
            # A read/limit error must never bypass retirement of the owned group.
            send(signal.SIGKILL)
            retired = True
        # A finite final drain preserves bytes already written before termination.
        deadline = time.monotonic() + 0.25
        while not eof and time.monotonic() < deadline:
            drain(collect=collect, wait=min(0.02, max(0.0, deadline - time.monotonic())))

    try:
        if stream is None:
            raise RuntimeError('The CLI did not expose its private output pipe.')
        os.set_blocking(stream.fileno(), False)
        deadline = time.monotonic() + timeout
        while True:
            if cancel_event is not None and cancel_event.is_set():
                raise CaptureCancelled('CLI inspection was cancelled.')
            if time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired(list(argv), timeout, output=bytes(output))
            if observe() is not None:
                retire(collect=True)
                break
            drain(collect=True, wait=min(0.02, max(0.0, deadline - time.monotonic())))
    except BaseException as error:
        failure = error
    finally:
        try:
            if owned and not retired:
                retire(collect=False)
        except BaseException as cleanup_error:
            if failure is None:
                failure = cleanup_error
        finally:
            if stream is not None:
                stream.close()
            if owned:
                try:
                    # Signals have finished while ownership was still retained.
                    observe()
                    return_code = process.wait(timeout=2)
                except CaptureOwnershipError as error:
                    failure = error
                except (OSError, subprocess.TimeoutExpired) as error:
                    if failure is None:
                        failure = RuntimeError('The owned CLI child did not exit cleanly.')
                        failure.__cause__ = error
            if not owned:
                # Prevent Popen's destructor from probing a reaped/reused PID.
                # This object is never returned as a successful result.
                process.returncode = -1
    if failure is not None:
        raise failure
    if not eof:
        raise RuntimeError('The CLI output pipe did not close after owned cleanup.')
    return subprocess.CompletedProcess(list(argv), return_code, bytes(output), None)
