"""Read-only controller API routing, independent of HTTP transport.

The service object is the owning controller module. Dynamic lookup preserves
lifecycle identity, runtime selections and test injection. The router can be
exercised without sockets or process startup.
"""
from __future__ import annotations

import copy
from typing import Any


# Lifecycle snapshots are always live. This table only removes HTTP dispatch
# duplication; it deliberately does not cache process or operation state.
_STATUS_SERVICES = {
    "/api/status": "MANAGER",
    "/api/benchmark/status": "BENCHMARK",
    "/api/route-check/status": "ROUTE_CHECK",
    "/api/setup/status": "SETUP",
    "/api/ane/status": "ANE_TUNER",
    "/api/ane/clone/status": "ANE_CLONER",
}


def _roots(controller: Any) -> list[dict[str, Any]]:
    return [
        {"label": label, "path": str(path), "exists": path.exists()}
        for label, path in controller.model_roots()
    ]


def read_response(route_path: str, controller: Any, csrf_token: str) -> dict[str, Any] | None:
    service = _STATUS_SERVICES.get(route_path)
    if service is not None:
        return getattr(controller, service).snapshot()
    if route_path == "/api/bootstrap":
        return {
            "version": controller.VERSION,
            "controllerSourceCurrent": controller.controller_source_is_current(),
            "controllerRestartMessage": controller.CONTROLLER_RESTART_MESSAGE,
            "token": csrf_token,
            "binaries": controller.public_binary_status(),
            "adapters": controller.adapter_inventory(),
            "clientSupport": controller.public_client_support(),
            "freeToken": controller.public_freetoken_connection(),
            "roots": _roots(controller),
        }
    if route_path == "/api/models":
        return {"models": controller.presentation_models(refresh=True)}
    if route_path == "/api/freetoken/status":
        return {"freeToken": controller.public_freetoken_connection()}
    if route_path == "/api/model-library":
        models = controller.presentation_models()
        return {
            "modelLibrary": controller.model_library_inventory(models),
            "models": models, "roots": _roots(controller),
        }
    if route_path == "/api/runtime/status":
        return {"runtimeManager": controller.runtime_inventory()}
    if route_path == "/api/runtime/update/status":
        return {
            "runtimeUpdate": controller.RUNTIME_UPDATE.snapshot(),
            "catalog": controller.runtime_update_overview(),
        }
    if route_path == "/api/runtime/promotion/status":
        records = controller.load_runtime_promotion_records()
        return {
            "runtimePromotion": controller.RUNTIME_PROMOTION.snapshot(),
            "recordCount": len(records),
            "latestResult": copy.deepcopy(max(
                records, key=lambda item: str(item.get("createdAt") or ""), default=None,
            )),
        }
    if route_path == "/api/profiles":
        return controller.launch_profile_inventory(controller.presentation_models())
    if route_path == "/api/session-sets":
        return controller.session_set_inventory(controller.presentation_models())
    if route_path == "/api/session-sets/status":
        return {"sessionSet": controller.SESSION_SETS.snapshot()}
    if route_path == "/api/chat/history":
        return controller.chat_history_inventory()
    if route_path == "/api/acquisition/status":
        return {
            "acquisition": controller.ACQUISITION.snapshot(),
            "roots": controller.model_acquisition_roots(),
            "downloaderReady": bool(controller.BINARIES.get("hf")), "publicAnonymous": True,
        }
    if route_path.startswith("/api/log"):
        plan = controller.MANAGER.plan
        text = controller.read_log_tail(plan.run_dir / "engine.log", 40_000) if plan and plan.run_dir else ""
        return {"log": text}
    return None
