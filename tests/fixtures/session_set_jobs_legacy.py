"""Frozen complete pre-extraction workspace opening; private fixtures only."""

def _session_set_record_for_id(
    value: Any, models: list[dict[str, Any]],
) -> dict[str, Any]:
    record_id = _profile_identifier(value)
    if not record_id:
        raise ValueError("Choose a valid Session Set.")
    stored = next((item for item in load_session_sets() if item["id"] == record_id), None)
    if stored is None:
        raise ValueError("That Session Set no longer exists. Refresh the list.")
    validated = validated_session_set_record(stored, models)
    return {
        **{key: copy.deepcopy(stored[key]) for key in ("id", "name", "createdAt", "updatedAt", "modelName")},
        **validated,
    }

def _session_set_surface_signature(request: dict[str, Any]) -> str:
    return json.dumps(
        _session_set_surface_from_request(request),
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )

def public_session_set_open_plan(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(value)
        for key, value in plan.items() if not key.startswith("_")
    }

def request_requires_freetoken_experimental_approval(
    request: dict[str, Any], models: list[dict[str, Any]],
) -> bool:
    """Return whether a new model load needs the port's non-persistent approval."""
    if request.get("backend") != "freetoken":
        return False
    model_id = str(request.get("modelId") or "")
    model = next((item for item in models if item.get("id") == model_id), None)
    if not isinstance(model, dict) or model.get("remote") is True:
        return False
    capability = model.get("backends", {}).get("freetoken", {})
    return bool(
        isinstance(capability, dict)
        and capability.get("native") is True
        and capability.get("nativeContract", {}).get("qualification", {})
        .get("launcher", {}).get("readiness") == "experimental_synthetic_only"
    )

def build_session_set_open_plan(
    payload: dict[str, Any], models: list[dict[str, Any]],
    resource_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Plan a complete saved workspace without allocating a port or opening a surface."""
    record = _session_set_record_for_id(payload.get("id"), models)
    requests = session_set_requests(record, models)
    base = requests[0]
    hub = MANAGER.hub_snapshot()
    operation = active_launcher_operation(hub)
    phase = str(hub.get("phase") or "idle")
    session = hub.get("session") if isinstance(hub.get("session"), dict) else None
    mode = "blocked"
    ready = False
    owner_run_id: str | None = None
    admission: dict[str, Any] | None = None
    existing_match_count = 0
    unverified_terminal_handoff_count = 0
    restart_surfaces: list[dict[str, Any]] = []
    missing_requests: list[dict[str, Any]] = []
    detail = ""

    if SESSION_SETS.is_active():
        detail = "Another Session Set is still opening. Wait for it to finish or stop its remaining surfaces."
    elif session is not None and phase == "running":
        warm = MANAGER.warm_route_plan(base, models)
        differences = list(warm.get("differences") or [])
        if differences or warm.get("engineResident") is not True:
            labels = ", ".join(str(item.get("label") or "route") for item in differences[:4])
            detail = (
                f"The resident model differs in {labels or 'its shared engine contract'}. "
                "Stop that route before opening this Session Set."
            )
        elif operation.get("kind") not in {"session", "idle"}:
            detail = str(operation.get("detail") or "Another private launcher operation is active.")
        else:
            owner_run_id = str(session.get("runId") or "")
            with MANAGER.lock:
                current_attachments = list(MANAGER.attachments.values())
                if not current_attachments and MANAGER.plan is not None:
                    fallback_plan = MANAGER.plan
                    current_attachments = [SurfaceAttachment(
                        owner_run_id=fallback_plan.run_id,
                        plan=fallback_plan,
                        primary=True,
                        status=(
                            "ready" if fallback_plan.client == "chat" else
                            "running" if fallback_plan.agent_host == "console" else
                            "handoff"
                        ),
                    )]
            existing_signatures: list[str] = []
            restart_candidates: list[dict[str, Any]] = []
            for attachment in current_attachments:
                current_plan = attachment.plan
                current_request = validated_launch_profile_request(
                    _session_set_plan_payload(current_plan), models,
                )
                # Terminal is an external handoff: the launcher deliberately
                # owns neither its process nor its lifetime. Retaining the
                # relay registration is not proof that the Terminal window is
                # still alive, so it must never satisfy a saved surface match.
                if (
                    current_request["client"] != "chat"
                    and current_request["agentHost"] == "terminal"
                ):
                    unverified_terminal_handoff_count += 1
                    continue
                signature = _session_set_surface_signature(current_request)
                if (
                    current_request["client"] != "chat"
                    and current_request["agentHost"] == "console"
                    and attachment.status in {"exited", "stopped", "failed"}
                ):
                    restart_candidates.append({
                        "surfaceId": current_plan.run_id,
                        "signature": signature,
                        "request": current_request,
                    })
                elif current_request["client"] == "chat" and attachment.status != "ready":
                    continue
                else:
                    existing_signatures.append(signature)
            remaining_signatures = list(existing_signatures)
            for request in requests:
                signature = _session_set_surface_signature(request)
                if signature in remaining_signatures:
                    remaining_signatures.remove(signature)
                    existing_match_count += 1
                else:
                    restart_index = next((
                        index for index, candidate in enumerate(restart_candidates)
                        if candidate["signature"] == signature
                    ), None)
                    if restart_index is not None:
                        restart_surfaces.append(restart_candidates.pop(restart_index))
                    else:
                        missing_requests.append(request)
            if len(current_attachments) + len(missing_requests) > SURFACE_ATTACHMENT_MAX:
                detail = (
                    f"This route has {len(current_attachments)} surfaces and the Session Set needs "
                    f"{len(missing_requests)} more; the safe limit is {SURFACE_ATTACHMENT_MAX}."
                )
            else:
                for request in missing_requests:
                    MANAGER._validated_attachment_target({
                        "ownerRunId": owner_run_id,
                        **_session_set_surface_from_request(request),
                    })
                mode = "already-open" if not missing_requests and not restart_surfaces else "reuse"
                ready = True
                if mode == "already-open":
                    detail = "Every saved work surface is already open on this exact resident model."
                else:
                    actions: list[str] = []
                    if restart_surfaces:
                        actions.append(
                            f"restart {len(restart_surfaces)} stopped Hub Console"
                            f"{'s' if len(restart_surfaces) != 1 else ''}"
                        )
                    if missing_requests:
                        actions.append(
                            f"open {len(missing_requests)} missing work surface"
                            f"{'s' if len(missing_requests) != 1 else ''}"
                        )
                    action_copy = " and ".join(actions)
                    detail = (
                        "The exact model is already resident. "
                        + action_copy[:1].upper() + action_copy[1:]
                        + " without reloading weights."
                    )
    elif hub.get("active"):
        detail = str(hub.get("message") or "Wait for the current launcher-owned operation to finish.")
    else:
        sessions = session_dashboard_plan(base, models, resource_snapshot)
        admission = sessions["admission"]
        if admission.get("launchable") is True:
            mode = "launch"
            ready = True
            missing_requests = requests[1:]
            detail = (
                f"Load one {BACKEND_LABELS[base['backend']]} model, open the primary "
                f"{CLIENT_LABELS[base['client']]} surface, then attach {len(missing_requests)} more "
                f"surface{'s' if len(missing_requests) != 1 else ''} to the same private relay."
            )
        else:
            detail = str(admission.get("detail") or "The saved model route cannot start yet.")

    opening_requests = (
        requests if mode == "launch" else
        [item["request"] for item in restart_surfaces] + missing_requests
    )
    terminal_count = sum(
        1 for request in opening_requests
        if request["client"] != "chat" and request["agentHost"] == "terminal"
    )
    hub_console_count = sum(
        1 for request in opening_requests
        if request["client"] != "chat" and request["agentHost"] == "console"
    )
    chat_count = sum(1 for request in opening_requests if request["client"] == "chat")
    requires_experimental_approval = bool(
        mode == "launch"
        and request_requires_freetoken_experimental_approval(base, models)
    )
    contract_value = {
        "version": SESSION_SET_PLAN_VERSION,
        "setId": record["id"], "updatedAt": record["updatedAt"],
        "mode": mode, "ownerRunId": owner_run_id,
        "baseEngine": {key: copy.deepcopy(base.get(key)) for key in SESSION_SET_ENGINE_KEYS},
        "restartSurfaceIds": [item["surfaceId"] for item in restart_surfaces],
        "missingSurfaces": [_session_set_surface_from_request(item) for item in missing_requests],
        "requiresExperimentalApproval": requires_experimental_approval,
    }
    contract_id = hashlib.sha256(json.dumps(
        contract_value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")).hexdigest()[:24] if ready else None
    confirmation = f"session-set:{contract_id}" if contract_id else None
    action_label = (
        "Everything is already open" if mode == "already-open" else
        f"Load model + open {len(requests)} surfaces" if mode == "launch" else
        f"Restore {len(opening_requests)} surface{'s' if len(opening_requests) != 1 else ''}"
        if mode == "reuse" else "Unavailable"
    )
    return {
        "version": SESSION_SET_PLAN_VERSION,
        "ready": ready,
        "mode": mode,
        "setId": record["id"],
        "setName": record["name"],
        "modelName": record["modelName"],
        "surfaceCount": len(requests),
        "surfaceLabels": [CLIENT_LABELS[request["client"]] for request in requests],
        "existingMatchCount": existing_match_count,
        "unverifiedTerminalHandoffCount": unverified_terminal_handoff_count,
        "restartSurfaceCount": len(restart_surfaces),
        "missingSurfaceCount": len(missing_requests),
        "ownerRunId": owner_run_id,
        "willLoadModel": mode == "launch",
        "willReloadWeights": mode == "launch",
        "requiresExperimentalApproval": requires_experimental_approval,
        "willOpenSurfaceCount": len(opening_requests),
        "terminalCount": terminal_count,
        "hubConsoleCount": hub_console_count,
        "chatCount": chat_count,
        "contractId": contract_id,
        "confirmation": confirmation,
        "action": {"label": action_label} if ready else None,
        "detail": detail,
        "admission": copy.deepcopy(admission),
        "privacy": {
            "planningStartsRuntime": False,
            "planningLoadsWeights": False,
            "planningAllocatesPort": False,
            "planningCreatesRunFiles": False,
            "planningOpensTerminal": False,
            "planningOpensHubConsole": False,
            "storesTranscripts": False,
            "storesConsoleOutput": False,
        },
        "_record": record,
        "_restartSurfaceIds": [item["surfaceId"] for item in restart_surfaces],
        "_missingRequests": missing_requests,
    }

class SessionSetRunner:
    """Open one saved multi-surface workspace through the ordinary session contracts."""

    ACTIVE_PHASES = {"starting", "waiting", "attaching", "stopping"}

    def __init__(self, run_manager: RunManager) -> None:
        self.run_manager = run_manager
        self.lock = threading.RLock()
        self.cancel_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.state: dict[str, Any] = self._idle_state()

    @staticmethod
    def _idle_state() -> dict[str, Any]:
        return {
            "version": SESSION_SET_STATUS_VERSION,
            "phase": "idle", "message": "No Session Set is opening.",
            "jobId": None, "setId": None, "setName": None,
            "mode": None, "ownerRunId": None,
            "totalSurfaceCount": 0, "pendingSurfaceCount": 0,
            "openedSurfaceCount": 0, "opened": [], "error": None,
        }

    def is_active(self) -> bool:
        with self.lock:
            return str(self.state.get("phase") or "idle") in self.ACTIVE_PHASES

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return copy.deepcopy(self.state)

    def start(self, payload: dict[str, Any], models: list[dict[str, Any]]) -> dict[str, Any]:
        with self.lock:
            if self.is_active() or (self.thread is not None and self.thread.is_alive()):
                raise ValueError("Another Session Set is still opening.")
        plan = build_session_set_open_plan(payload, models)
        if plan.get("ready") is not True:
            raise ValueError(str(plan.get("detail") or "This Session Set cannot open yet."))
        expected = str(plan.get("confirmation") or "")
        supplied = str(payload.get("confirmation") or "")
        if not expected or not secrets.compare_digest(supplied, expected):
            raise ValueError("The Session Set plan changed. Review it again before opening anything.")
        admission = plan.get("admission") if isinstance(plan.get("admission"), dict) else {}
        if (
            admission.get("requiresAcknowledgement") is True
            and str(payload.get("memoryAcknowledgement") or "") != str(admission.get("contractId") or "")
        ):
            raise ValueError(
                f"{admission.get('label') or 'Capacity review required'}: "
                f"{admission.get('detail') or 'Review the current memory estimate.'}"
            )
        private_record = plan.get("_record")
        restart_surface_ids = plan.get("_restartSurfaceIds")
        missing_requests = plan.get("_missingRequests")
        if (
            not isinstance(private_record, dict)
            or not isinstance(restart_surface_ids, list)
            or any(not isinstance(value, str) for value in restart_surface_ids)
            or len(restart_surface_ids) > SURFACE_ATTACHMENT_MAX
            or not isinstance(missing_requests, list)
        ):
            raise ValueError("The Session Set plan is incomplete. Refresh it and try again.")
        mode = str(plan.get("mode") or "")
        owner_run_id = str(plan.get("ownerRunId") or "")
        if mode == "launch":
            launch_request = copy.deepcopy(private_record["baseRequest"])
            if plan.get("requiresExperimentalApproval") is True:
                if payload.get("experimentalQualificationConsent") is not True:
                    raise ValueError(
                        "This Session Set would start a synthetic-only FreeToken checkpoint. "
                        "Review and approve that explicit experimental run first."
                    )
                launch_request.setdefault("options", {})[
                    "experimentalQualificationConsent"
                ] = True
            launch_plan = normalized_request(launch_request, models)
            try:
                require_live_model_load_admission(
                    launch_request, models, purpose="session-set",
                    approval_payload=payload, hub=self.run_manager.snapshot(),
                )
            except BaseException:
                dispose_plan_secrets(launch_plan)
                raise
            self.run_manager.start(launch_plan)
            owner_run_id = launch_plan.run_id
        elif mode not in {"reuse", "already-open"}:
            raise ValueError("This Session Set has no safe opening action.")

        job_id = str(uuid.uuid4())
        work_required = mode == "launch" or bool(restart_surface_ids) or bool(missing_requests)
        initial_phase = ("waiting" if mode == "launch" else "attaching") if work_required else "completed"
        initial_message = (
            "Every Session Set surface is already open on this model."
            if not work_required else
            "Loading the saved model and opening its primary work surface…"
            if mode == "launch" else
            "Restoring the saved work surfaces on the resident model…"
        )
        with self.lock:
            self.cancel_event = threading.Event()
            self.state = {
                "version": SESSION_SET_STATUS_VERSION,
                "phase": initial_phase, "message": initial_message,
                "jobId": job_id, "setId": private_record["id"],
                "setName": private_record["name"], "mode": mode,
                "ownerRunId": owner_run_id,
                "totalSurfaceCount": int(plan.get("surfaceCount") or 0),
                "pendingSurfaceCount": (
                    len(restart_surface_ids) + len(missing_requests)
                    + (1 if mode == "launch" else 0)
                ),
                "openedSurfaceCount": 0, "opened": [], "error": None,
            }
            if work_required:
                thread = threading.Thread(
                    target=self._worker,
                    args=(
                        job_id, owner_run_id, mode,
                        copy.deepcopy(restart_surface_ids),
                        copy.deepcopy(missing_requests),
                    ),
                    daemon=True,
                )
                self.thread = thread
                try:
                    thread.start()
                except Exception:
                    self.thread = None
                    self.cancel_event.set()
                    self.state["phase"] = "failed"
                    self.state["message"] = "The Session Set worker could not start. The model route and opened surfaces stay active."
                    self.state["error"] = self.state["message"]
                    raise
            else:
                self.thread = None
        return self.snapshot()

    def _wait_for_owner(self, job_id: str, owner_run_id: str) -> None:
        deadline = time.monotonic() + 930
        while time.monotonic() < deadline:
            if self.cancel_event.wait(0.3):
                raise LaunchCancelled(
                    "Remaining Session Set work was cancelled. The model route and opened surfaces were left alone."
                )
            with self.run_manager.lock:
                owner = self.run_manager.plan
                phase = str(self.run_manager.state.get("phase") or "idle")
                same_owner = bool(owner is not None and owner.run_id == owner_run_id)
                message = str(self.run_manager.state.get("message") or "")
            if not same_owner:
                raise LaunchCancelled("The model route changed before this Session Set finished opening.")
            if phase == "running":
                return
            if phase in {"failed", "idle"}:
                raise RuntimeError(message or "The saved model route did not become ready.")
            with self.lock:
                if self.state.get("jobId") == job_id:
                    self.state["phase"] = "waiting"
                    self.state["message"] = message or "Waiting for the saved model route…"
        raise RuntimeError("Timed out waiting for the saved model route to become ready.")

    def _worker(
        self, job_id: str, owner_run_id: str, mode: str,
        restart_surface_ids: list[str],
        missing_requests: list[dict[str, Any]],
    ) -> None:
        opened: list[dict[str, Any]] = []
        primary_opened = 0
        restore_step_count = len(restart_surface_ids) + len(missing_requests)
        try:
            if mode == "launch":
                self._wait_for_owner(job_id, owner_run_id)
                primary_opened = 1
                with self.lock:
                    if self.state.get("jobId") == job_id:
                        self.state["openedSurfaceCount"] = 1
                        self.state["pendingSurfaceCount"] = restore_step_count
            for index, surface_id in enumerate(restart_surface_ids):
                if self.cancel_event.is_set():
                    raise LaunchCancelled(
                        "Remaining Session Set work was cancelled. The model route and opened surfaces were left alone."
                    )
                with self.lock:
                    if self.state.get("jobId") != job_id:
                        raise LaunchCancelled("A newer Session Set operation replaced this one.")
                    self.state["phase"] = "attaching"
                    self.state["message"] = (
                        f"Restarting stopped Hub Console ({index + 1} of {restore_step_count})…"
                    )
                    self.state["pendingSurfaceCount"] = restore_step_count - len(opened)
                with SESSION_OPERATION_LOCK:
                    console = self.run_manager.restart_agent_console({
                        "ownerRunId": owner_run_id,
                        "surfaceId": surface_id,
                    })
                opened.append(console)
                with self.lock:
                    if self.state.get("jobId") == job_id:
                        self.state["opened"] = copy.deepcopy(opened)
                        self.state["openedSurfaceCount"] = primary_opened + len(opened)
                        self.state["pendingSurfaceCount"] = restore_step_count - len(opened)
            for index, request in enumerate(missing_requests):
                if self.cancel_event.is_set():
                    raise LaunchCancelled(
                        "Remaining Session Set work was cancelled. The model route and opened surfaces were left alone."
                    )
                surface = CLIENT_LABELS.get(str(request.get("client") or ""), "work surface")
                with self.lock:
                    if self.state.get("jobId") != job_id:
                        raise LaunchCancelled("A newer Session Set operation replaced this one.")
                    self.state["phase"] = "attaching"
                    step = len(restart_surface_ids) + index + 1
                    self.state["message"] = f"Opening {surface} ({step} of {restore_step_count})…"
                    self.state["pendingSurfaceCount"] = restore_step_count - len(opened)
                attachment_payload = {
                    "ownerRunId": owner_run_id,
                    **_session_set_surface_from_request(request),
                }
                with SESSION_OPERATION_LOCK:
                    attachment = self.run_manager.attach_surface(attachment_payload)
                opened.append(attachment)
                with self.lock:
                    if self.state.get("jobId") == job_id:
                        self.state["opened"] = copy.deepcopy(opened)
                        self.state["openedSurfaceCount"] = primary_opened + len(opened)
                        self.state["pendingSurfaceCount"] = restore_step_count - len(opened)
            with self.lock:
                if self.state.get("jobId") == job_id:
                    self.state["phase"] = "completed"
                    opened_count = primary_opened + len(opened)
                    self.state["message"] = (
                        f"Session Set loaded one model and opened {opened_count} work surface"
                        f"{'s' if opened_count != 1 else ''}."
                        if mode == "launch" else
                        f"Session Set restored {opened_count} work surface"
                        f"{'s' if opened_count != 1 else ''} on the resident model."
                    )
                    self.state["pendingSurfaceCount"] = 0
        except LaunchCancelled as error:
            with self.lock:
                if self.state.get("jobId") == job_id:
                    self.state["phase"] = "cancelled"
                    self.state["message"] = str(error)
                    self.state["error"] = None
        except Exception as error:  # noqa: BLE001
            with self.lock:
                if self.state.get("jobId") == job_id:
                    self.state["phase"] = "failed"
                    opened_count = primary_opened + len(opened)
                    self.state["message"] = (
                        f"Session Set stopped after opening {opened_count} surface"
                        f"{'s' if opened_count != 1 else ''}. {error}"
                    )
                    self.state["error"] = str(error)
        finally:
            with self.lock:
                if self.thread is threading.current_thread():
                    self.thread = None

    def cancel(self) -> dict[str, Any]:
        with self.lock:
            if not self.is_active():
                return copy.deepcopy(self.state)
            self.cancel_event.set()
            self.state["phase"] = "stopping"
            self.state["message"] = (
                "Stopping only the remaining Session Set steps. The model route and already opened surfaces stay active."
            )
            return copy.deepcopy(self.state)
