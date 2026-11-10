"""Narrow structural lifetimes shared by temporary launcher operations."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol
from benchmark_evidence import unload_receipt_issue


class OperationPlan(Protocol):
    run_id: str
    backend: str
    client: str
    model: dict[str, Any]
    context: int
    output: int
    reasoning: str
    options: dict[str, Any]
    port: int
    project: str
    run_dir: Path | None
    secrets: dict[str, Any]


@dataclass(frozen=True)
class TemporaryRunOwner:
    """Root binds callbacks to one accepted plan plus its cancellation epoch."""
    snapshot: Callable[[], dict[str, Any]]
    start: Callable[[OperationPlan], None]
    owns_plan: Callable[[OperationPlan], bool]
    stop: Callable[..., None]
    clean_unload: Callable[[OperationPlan], dict[str, Any]]
    admitted: Callable[[OperationPlan], bool]
    open_request: Callable[..., Any]


def stop_owned_temporary_run(owner: TemporaryRunOwner, plan: OperationPlan) -> dict[str, Any]:
    """An exact stop alone does not certify that descendants/model/ports retired."""
    owner.stop(expected_plan=plan)
    receipt = owner.clean_unload(plan)
    issue = unload_receipt_issue(receipt, plan.backend)
    if issue:
        raise RuntimeError("The temporary runtime did not unload cleanly. " + issue[:400])
    return receipt


@dataclass(frozen=True)
class SurfaceSnapshot:
    """Detached surface facts; no lifecycle/controller attachment is exported."""
    surface_id: str
    request: dict[str, Any]
    status: str


@dataclass(frozen=True)
class ResidenceSnapshot:
    owner_run_id: str
    phase: str
    message: str


@dataclass(frozen=True)
class SessionLease:
    """Opaque Root-held plan/epoch witness; never serialized in public status."""
    owner_run_id: str
    token: object


@dataclass(frozen=True)
class SessionResidence:
    hub_snapshot: Callable[[], dict[str, Any]]
    warm_route_plan: Callable[..., dict[str, Any]]
    surfaces: Callable[[], list[SurfaceSnapshot]]
    validate_target: Callable[[dict[str, Any]], None]
    start: Callable[[OperationPlan], None]
    owner_snapshot: Callable[[], ResidenceSnapshot]
    attach: Callable[[dict[str, Any]], dict[str, Any]]
    restart: Callable[[dict[str, Any]], dict[str, Any]]
    acquire: Callable[[str], SessionLease]
    leased_snapshot: Callable[[SessionLease], ResidenceSnapshot]
    attach_leased: Callable[[SessionLease, dict[str, Any]], dict[str, Any]]
    restart_leased: Callable[[SessionLease, dict[str, Any]], dict[str, Any]]
    release: Callable[[SessionLease], None]
    admitted: Callable[[OperationPlan], bool]


class _OwnedHTTPResponse:
    def __init__(self, response: Any, connection: Any):
        self._response, self._connection = response, connection
    def __getattr__(self, name: str) -> Any:
        return getattr(self._response, name)
    def __iter__(self):
        return iter(self._response)
    def __enter__(self):
        return self
    def __exit__(self, *_args):
        self.close()
    def close(self) -> None:
        try:
            self._response.close()
        finally:
            self._connection.close()


class EpochRequestDispatcher:
    """Fence a bounded loopback connect/send; response reads hold no owner lock."""
    def __init__(self, owner_lock: Any, is_current: Callable[[OperationPlan], bool],
                 cancelled: type[Exception], connection_factory: Callable[..., Any] | None = None):
        import http.client
        self.lock, self.is_current, self.cancelled = owner_lock, is_current, cancelled
        self.connection_factory = connection_factory or http.client.HTTPConnection

    def open(self, plan: OperationPlan, request: Any, timeout: float) -> Any:
        import urllib.parse
        import urllib.error
        value = urllib.parse.urlsplit(request.full_url)
        ports = {plan.port, getattr(plan, 'client_port', None)} - {None}
        if (value.scheme != 'http' or value.hostname != '127.0.0.1'
                or value.port not in ports or value.username or value.password or value.fragment):
            raise ValueError('The owned request must target this plan’s private loopback listener.')
        data = request.data
        if data is not None and (not isinstance(data, bytes) or len(data) > 1024**2):
            raise ValueError('The owned request body exceeds its dispatch quota.')
        headers = dict(request.header_items())
        connection = self.connection_factory('127.0.0.1', value.port, timeout=min(1.0, timeout))
        try:
            with self.lock:
                if not self.is_current(plan):
                    raise self.cancelled('The accepted runtime epoch changed before request dispatch.')
                connection.connect()
                # A replacement admitted while connect was intercepted must fail too.
                if not self.is_current(plan):
                    raise self.cancelled('The accepted runtime epoch changed before request dispatch.')
                connection.request(request.get_method(), value.path + ('?' + value.query if value.query else ''), body=data, headers=headers)
            if connection.sock is not None:
                connection.sock.settimeout(timeout)
            response = connection.getresponse()
            wrapped = _OwnedHTTPResponse(response, connection)
            if 300 <= response.status < 400:
                wrapped.close()
                raise RuntimeError('The private runtime attempted to redirect its owned request.')
            if response.status >= 400:
                raise urllib.error.HTTPError(request.full_url, response.status, response.reason, response.headers, wrapped)
            return wrapped
        except BaseException as error:
            if not isinstance(error, urllib.error.HTTPError):
                connection.close()
            raise
