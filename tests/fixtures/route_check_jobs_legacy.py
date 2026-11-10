"""Frozen complete pre-extraction temporary route operation; private fixtures only."""

def route_verification_identity(
    request: dict[str, Any], models: list[dict[str, Any]],
) -> dict[str, Any]:
    """Bind a live route result to the scanned checkpoint and selected runtime copy."""
    backend = str(request.get("backend") or "")
    model_id = str(request.get("modelId") or "")
    model = next((item for item in models if item.get("id") == model_id), None)
    if model is None or backend not in ENGINE_ADAPTERS:
        raise ValueError("The route identity no longer matches a scanned model and runtime.")
    capability = model.get("backends", {}).get(backend, {})
    model_fingerprint = str(capability.get("benchmarkModelFingerprint") or "")
    if not model_fingerprint:
        model_fingerprint = hashlib.sha256(json.dumps({
            "id": model_id,
            "artifact": hashlib.sha256(
                str(model.get("artifact") or model.get("path") or "").encode("utf-8", "replace")
            ).hexdigest(),
            "size": int(model.get("size") or 0),
            "format": str(model.get("format") or ""),
            "architecture": str(model.get("architecture") or ""),
            "quantization": str(model.get("quantization") or ""),
        }, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    adapter = ENGINE_ADAPTERS[backend]
    runtime_path = str(BINARIES.get(adapter.binary_key or "") or "")
    runtime_revision: dict[str, Any] = {
        "path": hashlib.sha256(runtime_path.encode("utf-8", "replace")).hexdigest(),
        "size": None, "modifiedNs": None,
    }
    if runtime_path:
        try:
            stat = Path(runtime_path).expanduser().resolve().stat()
            runtime_revision.update({"size": stat.st_size, "modifiedNs": stat.st_mtime_ns})
        except OSError:
            pass
    runtime_version = str(capability.get("runtimeVersion") or "Unreported")
    identity_value = {
        "schema": ROUTE_CHECK_RECEIPT_VERSION,
        "adapterSchema": ADAPTER_SCHEMA_VERSION,
        "backend": backend,
        "modelId": model_id,
        "modelFingerprint": model_fingerprint,
        "runtimeVersion": runtime_version,
        "runtimeRevision": runtime_revision,
    }
    return {
        "id": hashlib.sha256(json.dumps(
            identity_value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")).hexdigest()[:24],
        "modelFingerprint": model_fingerprint,
        "runtimeVersion": runtime_version,
        "adapterSchemaVersion": ADAPTER_SCHEMA_VERSION,
    }

def route_check_plan(
    payload: dict[str, Any], models: list[dict[str, Any]],
    resource_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Describe a route check without allocating a port, creating files, or loading weights."""
    sessions = session_dashboard_plan(payload, models, resource_snapshot)
    admission = sessions["admission"]
    request = admission.get("request")
    if not isinstance(request, dict):
        return {
            "version": ROUTE_CHECK_VERSION,
            "ready": False,
            "contractId": None,
            "detail": str(admission.get("detail") or "Finish the visible route settings."),
            "route": None,
            "checks": [],
            "privacy": {
                "planningStartsRuntime": False,
                "planningAllocatesPort": False,
                "planningCreatesRunFiles": False,
                "usesProjectData": False,
            },
        }
    client = str(request["client"])
    descriptor = CLIENT_ADAPTERS[client]
    identity = route_verification_identity(request, models)
    decision = str(admission.get("decision") or "invalid")
    if decision == "ready":
        capacity_status = "pass"
    elif admission.get("launchable") is True:
        capacity_status = "advisory"
    else:
        capacity_status = "fail"
    checks = [
        {
            "id": "contract", "label": "Visible contract", "status": "pass",
            "detail": (
                f"{BACKEND_LABELS[request['backend']]} → {CLIENT_LABELS[client]} · "
                f"{int(request['context']):,} context · {int(request['output']):,} max response · "
                f"{request['reasoning']} reasoning."
            ),
        },
        {
            "id": "capacity", "label": "Memory admission", "status": capacity_status,
            "detail": str(admission.get("detail") or "Capacity was not available."),
        },
        {
            "id": "surface", "label": "Work-surface adapter", "status": "pass",
            "detail": (
                f"{descriptor.label} is registered for {descriptor.protocol}"
                + (" and needs no external executable." if descriptor.built_in else " and its executable is installed.")
            ),
        },
        {
            "id": "model", "label": "Exact model discovery", "status": "pending",
            "detail": "The live check will require the runtime to list the selected served-model ID.",
        },
        {
            "id": "protocol", "label": "Client-facing protocol", "status": "pending",
            "detail": f"The live check will send generated text through {descriptor.protocol}.",
        },
        {
            "id": "stream", "label": "Streaming response", "status": "pending",
            "detail": "Waiting to verify server-sent response events rather than only endpoint existence.",
        },
        {
            "id": "tools", "label": "Agent tool schema",
            "status": "skipped" if client == "chat" else "pending",
            "detail": (
                "Built-in Chat does not require an agent tool-call contract."
                if client == "chat" else
                "The live check will submit one harmless synthetic function schema."
            ),
        },
        {
            "id": "usage", "label": "Authoritative token usage", "status": "pending",
            "detail": "Missing usage is reported as an advisory and is never estimated from characters.",
        },
        {
            "id": "reasoning", "label": "Reasoning exposure", "status": "pending",
            "detail": "The check records only reasoning text explicitly returned by the runtime.",
        },
    ]
    contract_id = hashlib.sha256(json.dumps(
        {
            "version": ROUTE_CHECK_VERSION,
            "admissionContract": admission.get("contractId"),
            "request": request,
            "protocol": descriptor.protocol,
            "routeIdentity": identity["id"],
        },
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")).hexdigest()[:20]
    ready = admission.get("launchable") is True and sessions["operation"].get("active") is not True
    return {
        "version": ROUTE_CHECK_VERSION,
        "ready": ready,
        "contractId": contract_id,
        "detail": (
            "Ready for one temporary local load and synthetic protocol check."
            if ready else str(admission.get("detail") or sessions["operation"].get("detail") or "Another operation is active.")
        ),
        "route": {
            **copy.deepcopy(admission["route"]),
            "surface": CLIENT_LABELS[client],
            "protocol": descriptor.protocol,
            "output": request["output"],
            "reasoning": request["reasoning"],
        },
        "identity": identity,
        "request": copy.deepcopy(request),
        "checks": checks,
        "work": {
            "modelLoads": 1,
            "generatedRequests": 1 if client == "chat" else 2,
            "maxGeneratedTokensPerRequest": min(ROUTE_CHECK_MAX_TOKENS, int(request["output"])),
            "opensWorkSurface": False,
            "stopsTemporaryRoute": True,
        },
        "capacity": {
            "decision": decision,
            "label": admission.get("label"),
            "requiresReview": admission.get("requiresAcknowledgement") is True,
            "estimate": copy.deepcopy(admission.get("estimate")),
        },
        "privacy": {
            "planningStartsRuntime": False,
            "planningAllocatesPort": False,
            "planningCreatesRunFiles": False,
            "usesProjectData": False,
            "liveCheckLoadsWeights": True,
            "liveCheckUsesGeneratedPrompts": True,
            "storesGeneratedText": False,
            "opensWorkSurface": False,
            "stopsTemporaryRoute": True,
        },
    }

class RouteCheckManager:
    """Own one temporary model load and prove the selected client-facing protocol."""

    ACTIVE_PHASES = {"queued", "starting", "running", "stopping"}

    def __init__(self, run_manager: RunManager) -> None:
        self.run_manager = run_manager
        self.lock = threading.RLock()
        self.cancel_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.active_plan: LaunchPlan | None = None
        self.state: dict[str, Any] = {
            "phase": "idle", "message": "No route check is running.",
            "progress": 0.0, "job": None, "checks": [], "result": None, "events": [],
        }

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return json.loads(json.dumps(self.state))

    def is_active(self) -> bool:
        with self.lock:
            return self.state.get("phase") in self.ACTIVE_PHASES or bool(
                self.thread and self.thread.is_alive()
            )

    def validated_launch_receipt(
        self, payload: dict[str, Any], models: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Validate an in-memory checked-launch handoff against the exact current route."""
        token = payload.get("routeVerification")
        if not isinstance(token, dict):
            raise ValueError("Run Route Check before requesting a verified launch.")
        job_id = str(token.get("jobId") or "")
        contract_id = str(token.get("contractId") or "")
        if not job_id or not contract_id:
            raise ValueError("The checked-launch receipt is incomplete. Run Route Check again.")
        report = route_check_plan(payload, models)
        if report.get("ready") is not True:
            raise ValueError(str(report.get("detail") or "The current route is no longer launchable."))
        with self.lock:
            snapshot = copy.deepcopy(self.state)
        result = snapshot.get("result") if isinstance(snapshot.get("result"), dict) else {}
        receipt = result.get("receipt") if isinstance(result.get("receipt"), dict) else {}
        job = snapshot.get("job") if isinstance(snapshot.get("job"), dict) else {}
        identity = report.get("identity") if isinstance(report.get("identity"), dict) else {}
        if snapshot.get("phase") != "completed" or receipt.get("ready") is not True:
            raise ValueError("Route Check has not finished unloading its temporary model.")
        if result.get("temporaryRouteStopped") is not True:
            raise ValueError("The temporary Route Check model has not stopped yet.")
        if result.get("verdict") not in {"pass", "advisory"}:
            raise ValueError("The route failed its live check and cannot be launched as verified.")
        tool_required = str(job.get("client") or "") != "chat"
        tool_evidence = result.get("tool") if isinstance(result.get("tool"), dict) else {}
        if tool_required and not (
            receipt.get("toolContractVerified") is True
            and tool_evidence.get("toolContractValid") is True
        ):
            raise ValueError(
                "The agent tool-call contract was not verified. Run Route Check again."
            )
        if job.get("id") != job_id or receipt.get("jobId") != job_id:
            raise ValueError("The checked-launch receipt belongs to an older Route Check run.")
        if (
            job.get("contractId") != contract_id
            or receipt.get("contractId") != contract_id
            or report.get("contractId") != contract_id
        ):
            raise ValueError("Visible settings changed after Route Check. Check this exact route again.")
        if receipt.get("identityId") != identity.get("id"):
            raise ValueError("The model checkpoint or selected runtime changed after Route Check.")
        try:
            expires_at = datetime.fromisoformat(str(receipt.get("expiresAt") or ""))
        except ValueError as error:
            raise ValueError("The checked-launch receipt has no valid expiry. Run Route Check again.") from error
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            raise ValueError("The checked-launch receipt expired. Run the short Route Check again.")
        return copy.deepcopy(receipt)

    def _event(self, message: str, level: str = "info") -> None:
        with self.lock:
            self.state["message"] = message
            self.state["events"] = (
                self.state.get("events", [])
                + [{"time": time.strftime("%H:%M:%S"), "level": level, "message": message}]
            )[-80:]

    def _set_check(self, check_id: str, status: str, detail: str) -> None:
        with self.lock:
            checks = self.state.get("checks")
            if not isinstance(checks, list):
                return
            check = next(
                (item for item in checks if isinstance(item, dict) and item.get("id") == check_id),
                None,
            )
            if check is not None:
                check["status"] = status
                check["detail"] = detail

    def start(self, payload: dict[str, Any], models: list[dict[str, Any]]) -> dict[str, Any]:
        report = route_check_plan(payload, models)
        if report.get("ready") is not True:
            raise ValueError(str(report.get("detail") or "This route is not ready to check."))
        if str(payload.get("confirmation") or "") != report.get("contractId"):
            raise ValueError(
                "Review and approve the temporary model load for this exact route before starting Route Check."
            )
        if self.run_manager.snapshot().get("phase") != "idle":
            raise ValueError("Stop the active launcher operation before starting Route Check.")
        plan = normalized_request(copy.deepcopy(report["request"]), models, purpose="route-check")
        job = {
            "id": plan.run_id,
            "version": ROUTE_CHECK_VERSION,
            "contractId": report["contractId"],
            "backend": plan.backend,
            "backendLabel": BACKEND_LABELS[plan.backend],
            "client": plan.client,
            "surface": CLIENT_LABELS[plan.client],
            "protocol": CLIENT_ADAPTERS[plan.client].protocol,
            "model": plan.model["name"],
            "context": plan.context,
            "output": plan.output,
            "reasoning": plan.reasoning,
            "identityId": report["identity"]["id"],
            "runtimeVersion": report["identity"]["runtimeVersion"],
            "temporaryLoad": True,
            "opensSurface": False,
        }
        with self.lock:
            if self.is_active():
                raise ValueError("A route check is already running.")
            self.cancel_event = threading.Event()
            self.active_plan = plan
            self.state = {
                "phase": "queued",
                "message": "Route Check accepted. Preparing the temporary local model route…",
                "progress": 0.03,
                "job": job,
                "checks": copy.deepcopy(report["checks"]),
                "result": None,
                "events": [],
            }
            self._set_check("surface", "pass", "The private work-surface overlay was built without opening it.")
            thread = threading.Thread(target=self._worker, args=(plan,), daemon=True)
            self.thread = thread
            try:
                thread.start()
            except Exception:
                self.thread = None
                self.active_plan = None
                self.cancel_event.set()
                self.state["phase"] = "failed"
                self._event("The Route Check worker could not start. Try the check again.", "error")
                dispose_plan_secrets(plan)
                raise
        return copy.deepcopy(job)

    def _wait_for_engine(self, plan: LaunchPlan) -> None:
        deadline = time.monotonic() + 930
        while time.monotonic() < deadline:
            if self.cancel_event.wait(0.2):
                raise LaunchCancelled("Route Check stopped.")
            status = self.run_manager.snapshot()
            if status.get("phase") == "running" and self.run_manager.plan is plan:
                return
            if status.get("phase") == "failed":
                raise RuntimeError(str(status.get("message") or "The temporary route failed to start."))
        raise RuntimeError("Route Check timed out while loading the selected model.")

    def _worker(self, plan: LaunchPlan) -> None:
        basic: dict[str, Any] | None = None
        tool: dict[str, Any] | None = None
        try:
            with self.lock:
                self.state["phase"] = "starting"
                self.state["progress"] = 0.08
            self._set_check("model", "running", "Loading the selected model and waiting for its exact served ID…")
            self._event("Loading the selected model once; no agent or Chat surface will be opened.")
            try:
                admission = require_live_model_load_admission(
                    _session_set_plan_payload(plan), [plan.model],
                    purpose="route-check", hub=self.run_manager.snapshot(),
                )
            except BaseException:
                dispose_plan_secrets(plan)
                raise
            with self.lock:
                if isinstance(self.state.get("job"), dict):
                    self.state["job"]["memoryAdmission"] = copy.deepcopy(admission)
            self.run_manager.start(plan)
            self._wait_for_engine(plan)
            self._set_check("model", "pass", "The runtime listed the exact selected model ID on loopback.")
            with self.lock:
                self.state["phase"] = "running"
                self.state["progress"] = 0.36
            self._set_check("protocol", "running", "Sending a bounded synthetic request through the selected protocol…")
            self._event(f"The model is ready. Probing {CLIENT_ADAPTERS[plan.client].protocol} with generated text only.")
            basic = run_route_check_request(plan, self.cancel_event)
            if basic.get("terminalComplete") is not True:
                raise RuntimeError(
                    "The synthetic response ended without an explicit complete terminal state."
                )
            if not (
                int(basic.get("contentCharacters") or 0)
                or int(basic.get("reasoningCharacters") or 0)
            ):
                raise RuntimeError("The route accepted the request but returned no text or exposed reasoning.")
            self._set_check(
                "protocol", "pass",
                f"The {basic['protocol']} endpoint accepted the model, authentication, and response ceiling.",
            )
            self._set_check(
                "stream", "pass" if basic.get("streamed") else "advisory",
                (
                    f"Received {int(basic.get('eventCount') or 0)} server-sent stream events."
                    if basic.get("streamed") else
                    "The endpoint returned valid JSON rather than server-sent streaming events."
                ),
            )
            usage = basic.get("usage") or {}
            self._set_check(
                "usage", "pass" if usage.get("available") else "advisory",
                (
                    f"Runtime reported {int(usage['promptTokens']):,} prompt and "
                    f"{int(usage['completionTokens']):,} response tokens."
                    if usage.get("available") else
                    "The request worked, but this runtime did not provide authoritative token usage."
                ),
            )
            reasoning_characters = int(basic.get("reasoningCharacters") or 0)
            if plan.reasoning == "off":
                reasoning_status = "pass" if reasoning_characters == 0 else "advisory"
                reasoning_detail = (
                    "No separate reasoning text was exposed, matching the selected Off contract."
                    if reasoning_characters == 0 else
                    "The runtime exposed reasoning even though the visible contract requested Off."
                )
            elif plan.reasoning == "auto":
                reasoning_status = "skipped"
                reasoning_detail = "Model-default reasoning has no forced exposure requirement."
            else:
                reasoning_status = "pass" if reasoning_characters else "advisory"
                reasoning_detail = (
                    f"The runtime exposed {reasoning_characters:,} reasoning characters in the synthetic probe."
                    if reasoning_characters else
                    "The short probe returned an answer but no separately exposed reasoning; this does not prove hidden reasoning was absent."
                )
            self._set_check("reasoning", reasoning_status, reasoning_detail)
            with self.lock:
                self.state["progress"] = 0.70

            if plan.client == "chat":
                self._set_check("tools", "skipped", "Built-in Chat does not require an agent tool-call contract.")
            else:
                self._set_check("tools", "running", "Submitting one harmless synthetic function schema…")
                try:
                    tool = run_route_check_request(plan, self.cancel_event, tool_probe=True)
                    if tool.get("toolContractValid") is True:
                        self._set_check(
                            "tools", "pass",
                            str(tool.get("toolContractDetail") or (
                                f"The route emitted a valid {ROUTE_CHECK_TOOL_NAME} tool call."
                            )),
                        )
                    else:
                        self._set_check(
                            "tools", "fail",
                            str(tool.get("toolContractDetail") or (
                                "The route did not satisfy the exact agent tool-call contract."
                            )),
                        )
                except Exception as error:  # noqa: BLE001 - preserved as a visible route failure
                    if isinstance(error, LaunchCancelled):
                        raise
                    self._set_check("tools", "fail", str(error))
            with self.lock:
                self.state["progress"] = 0.92
                checks = copy.deepcopy(self.state.get("checks") or [])
            failed = [item for item in checks if item.get("status") == "fail"]
            advisories = [item for item in checks if item.get("status") == "advisory"]
            verdict = "fail" if failed else ("advisory" if advisories else "pass")
            message = (
                "Route failed one or more required checks; review the evidence before launching."
                if verdict == "fail" else
                "Route is usable with advisories; review the yellow evidence before launching."
                if verdict == "advisory" else
                "Route passed every applicable live check."
            )
            checked_at = datetime.now(timezone.utc)
            expires_at = checked_at + timedelta(seconds=ROUTE_CHECK_RECEIPT_TTL_SECONDS)
            with self.lock:
                self.state["phase"] = "stopping"
                self.state["progress"] = 0.96
                job = self.state.get("job") if isinstance(self.state.get("job"), dict) else {}
                self.state["result"] = {
                    "version": ROUTE_CHECK_VERSION,
                    "verdict": verdict,
                    "summary": message,
                    "checkedAt": checked_at.isoformat(),
                    "basic": copy.deepcopy(basic),
                    "tool": copy.deepcopy(tool),
                    "generatedTextStored": False,
                    "surfaceOpened": False,
                    "temporaryRouteStopped": False,
                    "receipt": {
                        "version": ROUTE_CHECK_RECEIPT_VERSION,
                        "ready": False,
                        "jobId": str(job.get("id") or ""),
                        "contractId": str(job.get("contractId") or ""),
                        "identityId": str(job.get("identityId") or ""),
                        "verdict": verdict,
                        "toolContractRequired": plan.client != "chat",
                        "toolContractVerified": (
                            plan.client == "chat"
                            or bool(tool and tool.get("toolContractValid") is True)
                        ),
                        "verifiedAt": checked_at.isoformat(),
                        "expiresAt": expires_at.isoformat(),
                    },
                }
            self._event("Live checks finished. Unloading the temporary model before enabling launch.")
        except LaunchCancelled:
            with self.lock:
                self.state["phase"] = "cancelled"
            self._event("Route Check stopped. No result was saved and no work surface was opened.", "warning")
        except Exception as error:  # noqa: BLE001
            if self.cancel_event.is_set():
                with self.lock:
                    self.state["phase"] = "cancelled"
                self._event("Route Check stopped. No result was saved and no work surface was opened.", "warning")
            else:
                with self.lock:
                    running = next(
                        (
                            item for item in self.state.get("checks", [])
                            if item.get("status") == "running"
                        ),
                        None,
                    )
                    if running is not None:
                        running["status"] = "fail"
                        running["detail"] = str(error)
                    self.state["phase"] = "failed"
                    self.state["result"] = {
                        "version": ROUTE_CHECK_VERSION,
                        "verdict": "fail",
                        "summary": str(error),
                        "checkedAt": datetime.now(timezone.utc).isoformat(),
                        "generatedTextStored": False,
                        "surfaceOpened": False,
                        "temporaryRouteStopped": False,
                    }
                self._event(str(error), "error")
        finally:
            if self.run_manager.plan is plan:
                self.run_manager.stop()
            completion_message: str | None = None
            completion_level = "info"
            with self.lock:
                result = self.state.get("result")
                if isinstance(result, dict):
                    result["temporaryRouteStopped"] = True
                if self.state.get("phase") == "stopping" and isinstance(result, dict):
                    if self.cancel_event.is_set():
                        self.state["phase"] = "cancelled"
                        self.state["result"] = None
                        self.state["message"] = "Route Check stopped. No result was saved and no work surface was opened."
                    else:
                        receipt = result.get("receipt")
                        if isinstance(receipt, dict):
                            receipt["ready"] = (
                                result.get("verdict") in {"pass", "advisory"}
                                and receipt.get("toolContractVerified") is True
                            )
                        self.state["phase"] = "completed"
                        self.state["progress"] = 1.0
                        completion_message = str(result.get("summary") or "Route Check completed.")
                        completion_level = "warning" if result.get("verdict") != "pass" else "info"
                self.active_plan = None
                if self.thread is threading.current_thread():
                    self.thread = None
            if completion_message:
                self._event(completion_message, completion_level)

    def cancel(self) -> None:
        with self.lock:
            if not self.is_active():
                return
            self.cancel_event.set()
            self.state["phase"] = "stopping"
            self.state["message"] = "Stopping Route Check and unloading its temporary model…"
            plan = self.active_plan
        if plan is not None and self.run_manager.plan is plan:
            self.run_manager.stop()
