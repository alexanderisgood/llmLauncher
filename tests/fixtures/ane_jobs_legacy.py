"""Frozen complete pre-extraction ANE operations; private fixtures only."""

def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None

def sanitize_ane_snapshot(snapshot: Any) -> dict[str, Any]:
    """Expose only the bounded, documented tuner result surface."""
    if not isinstance(snapshot, dict):
        raise ValueError("oMLX returned an invalid ANE tuning status.")
    status = str(snapshot.get("status") or "running")[:32]
    phase = str(snapshot.get("phase") or status)[:64]
    message = str(snapshot.get("message") or "Tuning ANE prefill…")[:600]
    current = snapshot.get("current")
    total = snapshot.get("total")
    current = current if isinstance(current, int) and not isinstance(current, bool) and current >= 0 else 0
    total = total if isinstance(total, int) and not isinstance(total, bool) and total >= 0 else 0
    public_results: list[dict[str, Any]] = []
    for value in snapshot.get("results") or []:
        if not isinstance(value, dict) or len(public_results) >= 12:
            continue
        row: dict[str, Any] = {
            "label": str(value.get("label") or "Candidate")[:120],
            "detail": str(value.get("detail") or "")[:300] or None,
            "stage": str(value.get("stage") or "measurement")[:64],
            "state": str(value.get("state") or "pending")[:32],
            "enabled": value.get("enabled") is True,
            "gdn_enabled": value.get("gdn_enabled") is True,
            "cpu_enabled": value.get("cpu_enabled") is True,
            "error": str(value.get("error") or "")[:500] or None,
        }
        for key in (
            "mlp_fraction", "gdn_fraction", "cpu_fraction", "cpu_down_fraction",
            "cpu_gdn_fraction", "processing_tps", "latency_ms", "speedup_percent",
        ):
            row[key] = _finite_number(value.get(key))
        samples = [_finite_number(item) for item in (value.get("samples") or [])[:8]]
        row["samples"] = [item for item in samples if item is not None]
        public_results.append(row)
    recommendation = snapshot.get("recommendation")
    public_recommendation: dict[str, Any] | None = None
    if isinstance(recommendation, dict):
        public_recommendation = {
            "enabled": recommendation.get("enabled") is True,
            "gdn_enabled": recommendation.get("gdn_enabled") is True,
            "cpu_enabled": recommendation.get("cpu_enabled") is True,
            "cpu_shared_resource": recommendation.get("cpu_shared_resource") is True,
            "sequence_length": recommendation.get("sequence_length"),
            "cpu_threads": recommendation.get("cpu_threads"),
        }
        for key in (
            "mlp_fraction", "gdn_fraction", "cpu_fraction", "cpu_down_fraction",
            "cpu_gdn_fraction", "processing_tps", "speedup_percent",
        ):
            public_recommendation[key] = _finite_number(recommendation.get(key))
    return {
        "tuningId": str(snapshot.get("tuning_id") or snapshot.get("tuningId") or "")[:100],
        "status": status, "phase": phase, "message": message,
        "current": current, "total": total, "results": public_results,
        "recommendation": public_recommendation,
        "error": str(snapshot.get("error") or "")[:800] or None,
        "terminationReason": str(snapshot.get("termination_reason") or "")[:800] or None,
    }

def valid_ane_recommendation(value: Any, allow_cpu: bool = False) -> bool:
    if not isinstance(value, dict) or value.get("enabled") is not True:
        return False
    sequence = value.get("sequence_length")
    mlp_fraction = _finite_number(value.get("mlp_fraction"))
    processing = _finite_number(value.get("processing_tps"))
    speedup = _finite_number(value.get("speedup_percent"))
    cpu_enabled = value.get("cpu_enabled")
    gdn_enabled = value.get("gdn_enabled")
    if (
        sequence != ANE_TUNER_SEQUENCE_LENGTH
        or mlp_fraction is None or not 0 < mlp_fraction < 1
        or processing is None or processing <= 0
        or speedup is None or speedup < ANE_TUNER_MINIMUM_SPEEDUP_PERCENT
        or (cpu_enabled is not True and cpu_enabled is not False)
        or (gdn_enabled is not True and gdn_enabled is not False)
    ):
        return False
    cpu_fraction = _finite_number(value.get("cpu_fraction", 0.0))
    cpu_down_fraction = _finite_number(value.get("cpu_down_fraction", 0.0))
    cpu_gdn_fraction = _finite_number(value.get("cpu_gdn_fraction", 0.0))
    if any(number is None for number in (cpu_fraction, cpu_down_fraction, cpu_gdn_fraction)):
        return False
    assert cpu_fraction is not None and cpu_down_fraction is not None and cpu_gdn_fraction is not None
    if cpu_enabled:
        threads = value.get("cpu_threads")
        if (
            not allow_cpu
            or not 0 <= cpu_fraction <= 0.25
            or not 0 <= cpu_down_fraction <= 0.50
            or not 0 <= cpu_gdn_fraction <= 0.35
            or max(cpu_fraction, cpu_down_fraction, cpu_gdn_fraction) <= 0
            or mlp_fraction + cpu_fraction >= 1
            or not isinstance(threads, int) or isinstance(threads, bool)
            or not 1 <= threads <= 64
            or not isinstance(value.get("cpu_shared_resource"), bool)
        ):
            return False
    elif any(number != 0 for number in (cpu_fraction, cpu_down_fraction, cpu_gdn_fraction)):
        return False
    if gdn_enabled:
        gdn_fraction = _finite_number(value.get("gdn_fraction"))
        if (
            gdn_fraction is None or not 0 < gdn_fraction < 1
            or gdn_fraction + cpu_gdn_fraction >= 1
        ):
            return False
    elif (
        value.get("gdn_fraction") not in (None, 0, 0.0)
        or cpu_gdn_fraction != 0
    ):
        return False
    return True

def verified_ane_tuning_record(
    record: Any, model_fingerprint: str, runtime_version: str,
    machine: str | None = None,
) -> bool:
    if not isinstance(record, dict) or not model_fingerprint or not runtime_version:
        return False
    machine = machine or hardware_fingerprint()
    recommendation = record.get("recommendation")
    cpu_recommended = isinstance(recommendation, dict) and recommendation.get("cpu_enabled") is True
    cpu_proof = bool(
        not cpu_recommended
        or (
            record.get("cpuAssist") is True
            and record.get("cpuFloatDtype") == "F16"
            and isinstance(record.get("cpuProfileFingerprint"), str)
            and re.fullmatch(r"[0-9a-f]{64}", record["cpuProfileFingerprint"])
        )
    )
    return bool(
        record.get("scope") == "local"
        and record.get("status") == "completed"
        and record.get("accepted") is True
        and record.get("executionObserved") is True
        and isinstance(record.get("maxOperations"), int)
        and not isinstance(record.get("maxOperations"), bool)
        and record.get("maxOperations") > 0
        and not record.get("executionFailure")
        and record.get("modelFingerprint") == model_fingerprint
        and record.get("runtimeVersion") == runtime_version
        and record.get("hardwareFingerprint") == machine
        and record.get("sequenceLength") == ANE_TUNER_SEQUENCE_LENGTH
        and omlx_version_at_least(runtime_version, ANE_TUNER_MINIMUM_RUNTIME)
        and cpu_proof
        and valid_ane_recommendation(
            recommendation, allow_cpu=record.get("cpuAssist") is True,
        )
    )

def matching_ane_tuning_record(
    records: list[dict[str, Any]], model_fingerprint: str,
    runtime_version: str, machine: str | None = None,
) -> dict[str, Any] | None:
    machine = machine or hardware_fingerprint()
    matches = [
        copy.deepcopy(record) for record in records
        if record.get("scope") == "local"
        and record.get("modelFingerprint") == model_fingerprint
        and record.get("runtimeVersion") == runtime_version
        and record.get("hardwareFingerprint") == machine
        and record.get("sequenceLength") == ANE_TUNER_SEQUENCE_LENGTH
    ]
    matches.sort(key=lambda item: str(item.get("createdAt") or ""))
    return matches[-1] if matches else None

def ane_execution_proof(log_text: str) -> dict[str, Any]:
    """Require profiler proof that at least one ANE operation really ran."""
    operations: list[int] = []
    configured_layers: list[int] = []
    for line in str(log_text or "").splitlines():
        if "[benchmark-ane-profile]" not in line:
            continue
        operation_match = re.search(r"\boperations=(\d+)\b", line)
        configured_match = re.search(r"\bconfigured_layers=(\d+)\b", line)
        if operation_match:
            operations.append(int(operation_match.group(1)))
        if configured_match:
            configured_layers.append(int(configured_match.group(1)))
    failure_patterns = (
        r"hard memory pressure", r"request aborted", r"evicting model",
        r"disabling ane(?: prefill)?", r"ane candidate loaded, but no eligible",
        r"ane compiled but never executed",
    )
    failure = next(
        (pattern for pattern in failure_patterns if re.search(pattern, str(log_text or ""), re.IGNORECASE)),
        None,
    )
    maximum = max(operations, default=0)
    return {
        "executionObserved": maximum > 0 and failure is None,
        "maxOperations": maximum,
        "maxConfiguredLayers": max(configured_layers, default=0),
        "profileRows": len(operations),
        "executionFailure": failure,
    }

def ane_fp16_clone_destination(source: Path) -> Path:
    name = source.name
    if re.search(r"(?:^|[-_.])fp16(?:$|[-_.])", name, re.IGNORECASE):
        raise ValueError("This checkpoint name already identifies an FP16 variant.")
    destination_name = (
        f"{name[:-4]}-fp16-mtp" if name.lower().endswith("-mtp")
        else f"{name}-fp16"
    )
    return source.parent / destination_name

def regular_directory_inventory(path: Path) -> tuple[bool, int, str]:
    """Bound a clone source to regular files and reject every symlink."""
    total = 0
    try:
        for directory, names, files in os.walk(path, followlinks=False):
            base = Path(directory)
            for name in [*names, *files]:
                item = base / name
                if item.is_symlink():
                    return False, 0, f"The source contains a symbolic link: {item.relative_to(path)}"
            for name in files:
                item = base / name
                details = item.stat()
                if not stat.S_ISREG(details.st_mode):
                    return False, 0, f"The source contains a non-regular file: {item.relative_to(path)}"
                total += details.st_size
                if total > 512 * 1024**3:
                    return False, 0, "The source exceeds the 512 GiB clone safety limit."
    except OSError as error:
        return False, 0, f"The source could not be inventoried: {error}"
    return bool(total > 0), total, "The source contains regular files only."

def build_ane_fp16_clone_plan(
    payload: dict[str, Any], models: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    model_id = str(payload.get("modelId") or "")
    model = next((item for item in models if item.get("id") == model_id), None)
    if not model:
        raise ValueError("Choose a scanned oMLX checkpoint before preparing an FP16 clone.")
    capability = model.get("backends", {}).get("omlx") or {}
    if not model.get("ready") or model.get("format") != "mlx" or not capability.get("runnable"):
        raise ValueError(str(capability.get("reason") or "This checkpoint is not a ready oMLX model."))
    try:
        source = Path(str(model["path"])).resolve(strict=True)
    except (KeyError, OSError, RuntimeError) as error:
        raise ValueError("The selected checkpoint moved after scanning. Rescan models.") from error
    config = read_json(source / "config.json")
    complete, status, weight_bytes = weight_completeness(source, config)
    source_profile = ane_fp16_clone_source_profile(source, config, weight_bytes)
    if not complete:
        raise ValueError(f"The selected checkpoint is incomplete: {status}.")
    if not source_profile.get("eligible"):
        raise ValueError(str(source_profile.get("reason") or "This checkpoint cannot use the guarded FP16 clone path."))
    inventory_ready, source_bytes, inventory_reason = regular_directory_inventory(source)
    if not inventory_ready:
        raise ValueError(inventory_reason)
    destination = ane_fp16_clone_destination(source)
    runtime_version = command_version(BINARIES.get("omlx"))
    runtime_python = omlx_runtime_python(BINARIES.get("omlx"))
    fingerprint = model_artifact_fingerprint(source, config)
    if not fingerprint or fingerprint != capability.get("benchmarkModelFingerprint"):
        raise ValueError("The checkpoint changed after scanning. Rescan models before preparing a clone.")
    helper_digest = ""
    try:
        helper_digest = hashlib.sha256(ANE_FP16_CLONE_HELPER.read_bytes()).hexdigest()
    except OSError:
        pass
    blockers: list[str] = []
    if not omlx_version_at_least(runtime_version, ANE_TUNER_MINIMUM_RUNTIME):
        blockers.append(f"Select oMLX {ANE_TUNER_MINIMUM_RUNTIME} or newer.")
    if not runtime_python:
        blockers.append("The selected oMLX runtime has no matching Python environment.")
    if not helper_digest:
        blockers.append("The launcher's audited FP16 clone helper is missing.")
    if destination.exists():
        blockers.append(f"The destination already exists: {destination.name}.")
    try:
        free_bytes = shutil.disk_usage(destination.parent).free
    except OSError:
        free_bytes = 0
    required_bytes = source_bytes + ANE_FP16_CLONE_DISK_RESERVE_BYTES
    if free_bytes < required_bytes:
        blockers.append(
            f"Free at least {display_size(required_bytes)} in the destination volume before cloning."
        )
    contract_value = {
        "modelId": model_id,
        "modelFingerprint": fingerprint,
        "sourceTensorFingerprint": source_profile["sourceTensorFingerprint"],
        "source": str(source), "destination": str(destination),
        "sourceBytes": source_bytes, "runtimeVersion": runtime_version,
        "runtimePython": runtime_python, "helperDigest": helper_digest,
    }
    contract_id = hashlib.sha256(json.dumps(
        contract_value, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()[:20]
    plan = {
        "version": 1,
        "planId": str(uuid.uuid4()),
        "contractId": contract_id,
        "confirmation": f"CREATE {destination.name}",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "expiresAtEpoch": time.time() + ANE_FP16_CLONE_PLAN_TTL_SECONDS,
        "ready": not blockers,
        "blockers": blockers,
        "modelId": model_id,
        "model": str(model.get("name") or source.name),
        "modelFingerprint": fingerprint,
        "sourceTensorFingerprint": source_profile["sourceTensorFingerprint"],
        "source": str(source),
        "sourceName": source.name,
        "destination": str(destination),
        "destinationName": destination.name,
        "sourceBytes": source_bytes,
        "sourceSizeLabel": display_size(source_bytes),
        "requiredBytes": required_bytes,
        "requiredSizeLabel": display_size(required_bytes),
        "freeBytes": free_bytes,
        "freeSizeLabel": display_size(free_bytes),
        "diskReserveBytes": ANE_FP16_CLONE_DISK_RESERVE_BYTES,
        "floatDtypes": source_profile["floatDtypes"],
        "gateUpScalePairs": source_profile["gateUpScalePairs"],
        "runtimeVersion": runtime_version,
        "runtimePython": runtime_python,
        "helperDigest": helper_digest,
        "sourceUrl": ANE_FP16_CLONE_SOURCE_URL,
        "security": {
            "sourceReadOnly": True,
            "atomicDestination": True,
            "networkUsed": False,
            "packedIntegerWeightsPreserved": True,
        },
    }
    return copy.deepcopy(model), plan

class ANETunerManager:
    """Own a temporary oMLX server and trust only positively traced ANE work."""

    ACTIVE_PHASES = {"queued", "starting", "running", "stopping"}
    # Private-engine port -> "omlx_admin_session=..." header, for the oMLX
    # runtimes that require an admin session on /admin/api/*.
    _ADMIN_COOKIES: dict[int, str] = {}

    def __init__(self, run_manager: RunManager) -> None:
        self.run_manager = run_manager
        self.lock = threading.RLock()
        self.cancel_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.active_plan: LaunchPlan | None = None
        self.upstream_tuning_id = ""
        self.state: dict[str, Any] = {
            "phase": "idle", "message": "No ANE tuning run is active.",
            "progress": 0.0, "job": None, "results": [],
            "recommendation": None, "result": None, "events": [],
        }

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return json.loads(json.dumps(self.state))

    def is_active(self) -> bool:
        with self.lock:
            return bool(
                self.state.get("phase") in self.ACTIVE_PHASES
                or (self.thread and self.thread.is_alive())
            )

    def _event(self, message: str, level: str = "info") -> None:
        with self.lock:
            self.state["message"] = message
            self.state["events"] = (
                self.state.get("events", [])
                + [{"time": time.strftime("%H:%M:%S"), "level": level, "message": message}]
            )[-100:]

    def start(self, payload: dict[str, Any], models: list[dict[str, Any]]) -> dict[str, Any]:
        _model, plan, job = validated_ane_tuning_request(payload, models)
        if self.run_manager.snapshot().get("phase") != "idle":
            raise ValueError("Stop the active launcher run before starting ANE Tuner.")
        with self.lock:
            if self.is_active():
                raise ValueError("ANE Tuner is already running.")
            self.cancel_event = threading.Event()
            self.active_plan = plan
            self.upstream_tuning_id = ""
            self.state = {
                "phase": "queued", "message": "ANE tuning accepted. Preparing an isolated oMLX engine…",
                "progress": 0.0, "job": copy.deepcopy(job), "results": [],
                "recommendation": None, "result": None, "events": [],
            }
            thread = threading.Thread(target=self._worker, args=(plan, job), daemon=True)
            self.thread = thread
            try:
                thread.start()
            except Exception:
                self.thread = None
                self.active_plan = None
                self.cancel_event.set()
                self.state["phase"] = "failed"
                self._event("The ANE tuning worker could not start. Try the tuning job again.", "error")
                dispose_plan_secrets(plan)
                raise
        return copy.deepcopy(job)

    def _wait_for_engine(self, plan: LaunchPlan) -> None:
        deadline = time.monotonic() + 930
        while time.monotonic() < deadline:
            if self.cancel_event.wait(0.2):
                raise LaunchCancelled("ANE tuning cancelled.")
            status = self.run_manager.snapshot()
            if status.get("phase") == "running" and self.run_manager.plan is plan:
                return
            if status.get("phase") == "failed":
                raise RuntimeError(str(status.get("message") or "The private oMLX engine failed to start."))
        raise RuntimeError("ANE Tuner timed out while loading the private model engine.")

    @staticmethod
    def _request_json(
        plan: LaunchPlan, path: str, method: str = "GET",
        payload: dict[str, Any] | None = None, timeout: float = 30,
    ) -> dict[str, Any]:
        def attempt(cookie: str) -> bytes:
            data = json.dumps(payload).encode("utf-8") if payload is not None else None
            api_key = plan.secrets.get("apiKey", "local")
            headers = {
                "Authorization": f"Bearer {api_key}", "X-API-Key": api_key,
                "Content-Type": "application/json", "Accept": "application/json",
            }
            if cookie:
                headers["Cookie"] = cookie
            request = urllib.request.Request(
                f"http://127.0.0.1:{plan.port}{path}", data=data, method=method,
                headers=headers,
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read(MAX_JSON + 1)

        cookie = ANETunerManager._ADMIN_COOKIES.get(int(plan.port), "")
        try:
            raw = attempt(cookie)
        except urllib.error.HTTPError as error:
            raw = error.read(16_000)
            try:
                detail = json.loads(raw).get("detail")
            except (ValueError, AttributeError):
                detail = raw.decode("utf-8", "replace")
            # oMLX 0.7.x gates /admin/api/* behind an admin session cookie; the
            # bearer key it still accepts for inference is not enough. Log in
            # once with the private engine's own key and retry (0.6.x, which
            # accepts the bearer, never reaches this branch).
            if error.code == 401 and "admin authentication" in str(detail).lower():
                cookie = ANETunerManager._admin_cookie(plan)
                try:
                    raw = attempt(cookie)
                except urllib.error.HTTPError as retry_error:
                    raw = retry_error.read(16_000)
                    try:
                        detail = json.loads(raw).get("detail")
                    except (ValueError, AttributeError):
                        detail = raw.decode("utf-8", "replace")
                    raise RuntimeError(
                        f"oMLX ANE Tuner returned HTTP {retry_error.code}: {str(detail)[:600]}"
                    ) from retry_error
            else:
                raise RuntimeError(f"oMLX ANE Tuner returned HTTP {error.code}: {str(detail)[:600]}") from error
        if len(raw) > MAX_JSON:
            raise RuntimeError("oMLX returned an oversized ANE tuning response.")
        value = json.loads(raw or b"{}")
        if not isinstance(value, dict):
            raise RuntimeError("oMLX returned an invalid ANE tuning response.")
        return value

    @staticmethod
    def _admin_cookie(plan: LaunchPlan, timeout: float = 15) -> str:
        """Create an oMLX admin session and return its cookie header value.

        The private ANE engine is launched with the plan's own API key, so the
        same key authenticates the admin login on oMLX 0.7.x runtimes.
        """
        api_key = plan.secrets.get("apiKey", "local")
        request = urllib.request.Request(
            f"http://127.0.0.1:{plan.port}/admin/api/login",
            data=json.dumps({"api_key": api_key, "remember": False}).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                response.read(4096)
                cookies = response.headers.get_all("Set-Cookie") or []
        except urllib.error.HTTPError as error:
            detail = error.read(4096).decode("utf-8", "replace")
            raise RuntimeError(
                f"oMLX admin login failed with HTTP {error.code}: {detail[:300]}"
            ) from error
        for cookie in cookies:
            name, _, value = str(cookie).split(";", 1)[0].partition("=")
            if name.strip() == "omlx_admin_session" and value.strip():
                header = f"omlx_admin_session={value.strip()}"
                ANETunerManager._ADMIN_COOKIES[int(plan.port)] = header
                return header
        raise RuntimeError("oMLX admin login returned no session cookie.")

    def _publish_upstream(self, snapshot: dict[str, Any]) -> None:
        public = sanitize_ane_snapshot(snapshot)
        progress = min(0.99, public["current"] / public["total"]) if public["total"] else 0.0
        with self.lock:
            self.state.update({
                "phase": "running", "message": public["message"],
                "progress": progress, "results": public["results"],
                "recommendation": public["recommendation"],
            })

    @staticmethod
    def _read_engine_log(plan: LaunchPlan) -> str:
        if not plan.run_dir:
            return ""
        return read_log_tail(plan.run_dir / "engine.log", 2_000_000)

    def _build_record(
        self, plan: LaunchPlan, job: dict[str, Any], snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        public = sanitize_ane_snapshot(snapshot)
        recommendation = public.get("recommendation") or {}
        proof = ane_execution_proof(self._read_engine_log(plan))
        cpu_assist = job.get("cpuAssist") is True
        accepted = bool(
            public.get("status") == "completed"
            and valid_ane_recommendation(recommendation, allow_cpu=cpu_assist)
            and proof["executionObserved"]
        )
        if proof.get("executionFailure"):
            decision = "Rejected: the private engine log recorded an ANE or memory failure."
        elif not proof.get("executionObserved"):
            decision = "Rejected: no positive ANE profiler operation was recorded."
        elif recommendation.get("enabled") is not True:
            decision = "Keep GPU-only prefill: the tuner found no faster ANE split."
        elif (_finite_number(recommendation.get("speedup_percent")) or 0) < ANE_TUNER_MINIMUM_SPEEDUP_PERCENT:
            decision = f"Keep GPU-only prefill: the gain did not clear the {ANE_TUNER_MINIMUM_SPEEDUP_PERCENT:.0f}% noise floor."
        elif not accepted:
            decision = "Rejected: the recommendation did not satisfy the launcher's strict settings contract."
        else:
            route = "ANE/GPU/CPU" if recommendation.get("cpu_enabled") is True else "ANE/GPU"
            decision = (
                f"Measured {route} split accepted: {float(recommendation['speedup_percent']):.1f}% faster prefill "
                "with positive hardware execution proof."
            )
        return {
            "id": str(uuid.uuid4()),
            "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "scope": "local", "status": "completed", "accepted": accepted,
            "modelId": job["modelId"], "model": job["model"],
            "modelFingerprint": job["modelFingerprint"],
            "runtimeVersion": job["runtimeVersion"],
            "hardwareFingerprint": job["hardwareFingerprint"],
            "sequenceLength": ANE_TUNER_SEQUENCE_LENGTH,
            "repeats": ANE_TUNER_REPEATS,
            "cpuAssist": cpu_assist,
            "cpuFloatDtype": job.get("cpuFloatDtype") if cpu_assist else None,
            "cpuProfileFingerprint": job.get("cpuProfileFingerprint") if cpu_assist else None,
            "cpuReserveBytes": job.get("cpuReserveBytes") if cpu_assist else None,
            "approximate": True,
            "minimumSpeedupPercent": ANE_TUNER_MINIMUM_SPEEDUP_PERCENT,
            "upstreamTuningId": public.get("tuningId") or self.upstream_tuning_id,
            "results": public.get("results") or [],
            "recommendation": recommendation,
            "decision": decision,
            **proof,
        }

    def _worker(self, plan: LaunchPlan, job: dict[str, Any]) -> None:
        try:
            self._event("Loading the model in a private oMLX process; global oMLX settings remain untouched.")
            with self.lock:
                self.state["phase"] = "starting"
            try:
                admission = require_live_model_load_admission(
                    _session_set_plan_payload(plan), [plan.model],
                    purpose="ane-tune", hub=self.run_manager.snapshot(),
                )
            except BaseException:
                dispose_plan_secrets(plan)
                raise
            with self.lock:
                if isinstance(self.state.get("job"), dict):
                    self.state["job"]["memoryAdmission"] = copy.deepcopy(admission)
            self.run_manager.start(plan)
            self._wait_for_engine(plan)
            if self.cancel_event.is_set():
                raise LaunchCancelled("ANE tuning cancelled.")
            started = self._request_json(
                plan, "/admin/api/bench/ane-tune/start", "POST",
                {
                    "model_id": plan.model["servedId"],
                    "sequence_length": ANE_TUNER_SEQUENCE_LENGTH,
                    "repeats": ANE_TUNER_REPEATS,
                    "allow_cpu": job.get("cpuAssist") is True,
                    "allow_cpu_gate": job.get("cpuGateEligible") is True,
                    "allow_cpu_down": job.get("cpuDownEligible") is True,
                    "allow_ane_gdn": True,
                    "allow_cpu_gdn": job.get("cpuGdnEligible") is True,
                    "allow_cpu_shared_resource": job.get("cpuAssist") is True,
                },
                timeout=60,
            )
            public_started = sanitize_ane_snapshot(started)
            tuning_id = public_started.get("tuningId") or str(started.get("id") or "")
            if not tuning_id:
                raise RuntimeError("oMLX did not return an ANE tuning identifier.")
            with self.lock:
                self.upstream_tuning_id = tuning_id
            candidate_route = "ANE/GPU/CPU" if job.get("cpuAssist") is True else "ANE/GPU"
            self._event(f"GPU baseline and temporary {candidate_route} candidates are now being measured.")
            deadline = time.monotonic() + 4 * 60 * 60
            final_snapshot: dict[str, Any] | None = None
            while time.monotonic() < deadline:
                if self.cancel_event.wait(1.0):
                    raise LaunchCancelled("ANE tuning cancelled.")
                snapshot = self._request_json(
                    plan, f"/admin/api/bench/ane-tune/{tuning_id}/results", timeout=30,
                )
                self._publish_upstream(snapshot)
                status = str(snapshot.get("status") or "")
                if status in {"completed", "cancelled", "error", "failed"}:
                    final_snapshot = snapshot
                    break
            if final_snapshot is None:
                raise RuntimeError("ANE Tuner exceeded its four-hour safety limit.")
            public_final = sanitize_ane_snapshot(final_snapshot)
            if public_final["status"] == "cancelled":
                raise LaunchCancelled("ANE tuning cancelled.")
            if public_final["status"] != "completed":
                raise RuntimeError(public_final.get("error") or public_final.get("terminationReason") or "oMLX ANE tuning failed.")
            # Let the final profiler line reach the private log before proving execution.
            self.cancel_event.wait(0.2)
            record = self._build_record(plan, job, final_snapshot)
            save_ane_tuning_record(record)
            with self.lock:
                self.state.update({
                    "phase": "completed", "progress": 1.0,
                    "results": record["results"], "recommendation": record["recommendation"],
                    "result": copy.deepcopy(record),
                })
            self._event(record["decision"], "info" if record["accepted"] else "warning")
        except LaunchCancelled:
            with self.lock:
                self.state["phase"] = "cancelled"
            self._event("ANE tuning stopped. No partial recommendation was saved or enabled.", "warning")
        except Exception as error:  # noqa: BLE001
            if self.cancel_event.is_set():
                with self.lock:
                    self.state["phase"] = "cancelled"
                self._event("ANE tuning stopped. No partial recommendation was saved or enabled.", "warning")
            else:
                with self.lock:
                    self.state["phase"] = "failed"
                self._event(str(error), "error")
        finally:
            if self.run_manager.plan is plan:
                self.run_manager.stop()
            with self.lock:
                self.active_plan = None
                self.upstream_tuning_id = ""
                if self.thread is threading.current_thread():
                    self.thread = None

    def cancel(self) -> None:
        with self.lock:
            if not self.is_active():
                return
            self.cancel_event.set()
            self.state["phase"] = "stopping"
            self.state["message"] = "Stopping ANE Tuner and its private oMLX engine…"
            plan = self.active_plan
            tuning_id = self.upstream_tuning_id
        if plan is not None and tuning_id:
            try:
                self._request_json(
                    plan, f"/admin/api/bench/ane-tune/{tuning_id}/cancel",
                    "POST", {}, timeout=10,
                )
            except Exception:  # noqa: BLE001
                pass
        if plan is not None and self.run_manager.plan is plan:
            self.run_manager.stop()

class ANEFP16CloneManager:
    """Create one source-preserving FP16 checkpoint clone after explicit review."""

    ACTIVE_PHASES = {"queued", "validating", "converting", "verifying", "stopping"}

    def __init__(self, run_manager: RunManager) -> None:
        self.run_manager = run_manager
        self.lock = threading.RLock()
        self.cancel_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.process: subprocess.Popen[str] | None = None
        self.current_plan: dict[str, Any] | None = None
        self.state: dict[str, Any] = {
            "phase": "idle", "message": "No FP16 clone is being prepared.",
            "progress": 0.0, "plan": None, "result": None, "events": [],
        }

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return json.loads(json.dumps(self.state))

    def is_active(self) -> bool:
        with self.lock:
            return bool(
                self.state.get("phase") in self.ACTIVE_PHASES
                or (self.thread and self.thread.is_alive())
            )

    def _event(self, message: str, level: str = "info") -> None:
        with self.lock:
            self.state["message"] = message
            self.state["events"] = (
                self.state.get("events", [])
                + [{"time": time.strftime("%H:%M:%S"), "level": level, "message": message}]
            )[-80:]

    @staticmethod
    def _public_plan(plan: dict[str, Any]) -> dict[str, Any]:
        public = copy.deepcopy(plan)
        public.pop("expiresAtEpoch", None)
        public.pop("runtimePython", None)
        return public

    def plan(self, payload: dict[str, Any], models: list[dict[str, Any]]) -> dict[str, Any]:
        if self.is_active():
            raise ValueError("An FP16 clone is already being prepared.")
        _model, plan = build_ane_fp16_clone_plan(payload, models)
        with self.lock:
            self.current_plan = copy.deepcopy(plan)
            self.state = {
                "phase": "idle",
                "message": (
                    "FP16 clone plan ready for review. Nothing has been written."
                    if plan.get("ready") else
                    str((plan.get("blockers") or ["The FP16 clone plan is blocked."])[0])
                ),
                "progress": 0.0,
                "plan": self._public_plan(plan),
                "result": None,
                "events": [],
            }
        return self._public_plan(plan)

    def start(self, payload: dict[str, Any], models: list[dict[str, Any]]) -> dict[str, Any]:
        if payload.get("approved") is not True:
            raise ValueError("Review and approve the source-preserving FP16 clone first.")
        with self.lock:
            stored = copy.deepcopy(self.current_plan)
        if not stored:
            raise ValueError("Open a fresh FP16 clone plan before starting.")
        if (
            payload.get("planId") != stored.get("planId")
            or payload.get("confirmation") != stored.get("confirmation")
        ):
            raise ValueError("The FP16 clone confirmation no longer matches the reviewed plan.")
        if time.time() > float(stored.get("expiresAtEpoch") or 0):
            raise ValueError("The FP16 clone plan expired. Review it again.")
        _model, current = build_ane_fp16_clone_plan(
            {"modelId": stored.get("modelId")}, models,
        )
        if current.get("contractId") != stored.get("contractId"):
            raise ValueError("The source, runtime, helper, or destination changed. Review a fresh plan.")
        if not current.get("ready"):
            raise ValueError(str((current.get("blockers") or ["The clone plan is blocked."])[0]))
        if self.run_manager.snapshot().get("phase") != "idle":
            raise ValueError("Stop the active launcher run before preparing an FP16 clone.")
        job_id = str(uuid.uuid4())
        current["planId"] = stored["planId"]
        current["confirmation"] = stored["confirmation"]
        current["expiresAtEpoch"] = stored["expiresAtEpoch"]
        current["jobId"] = job_id
        with self.lock:
            if self.is_active():
                raise ValueError("An FP16 clone is already being prepared.")
            self.cancel_event = threading.Event()
            self.current_plan = copy.deepcopy(current)
            self.state = {
                "phase": "queued",
                "message": "FP16 clone approved. Preparing an isolated staging folder…",
                "progress": 0.0,
                "plan": self._public_plan(current),
                "result": None, "events": [],
            }
            thread = threading.Thread(target=self._worker, args=(current,), daemon=True)
            self.thread = thread
            try:
                thread.start()
            except Exception:
                self.thread = None
                self.cancel_event.set()
                self.state["phase"] = "failed"
                self._event("The clone worker could not start. Try the reviewed operation again.", "error")
                raise
        return self._public_plan(current)

    @staticmethod
    def _terminate(process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass

    @staticmethod
    def _cleanup_staging(staging: Path, destination: Path, job_id: str) -> None:
        expected_name = f".llm-launcher-fp16-{job_id}"
        try:
            if (
                staging.name == expected_name
                and staging.parent.resolve(strict=True) == destination.parent.resolve(strict=True)
                and staging.exists()
                and not staging.is_symlink()
            ):
                shutil.rmtree(staging)
        except OSError:
            pass

    @staticmethod
    def _verify_clone(plan: dict[str, Any], staging: Path) -> dict[str, Any]:
        source = Path(str(plan["source"])).resolve(strict=True)
        source_config = read_json(source / "config.json")
        if (
            model_artifact_fingerprint(source, source_config) != plan.get("modelFingerprint")
            or ane_cpu_sharing_profile(source).get("profileFingerprint")
            != plan.get("sourceTensorFingerprint")
        ):
            raise ValueError("The source checkpoint changed during cloning; the staging copy was rejected.")
        clone_config = read_json(staging / "config.json")
        ready, status, _weight_bytes = weight_completeness(staging, clone_config)
        if not ready:
            raise ValueError(f"The staged FP16 checkpoint is incomplete: {status}.")
        if not ane_quantization_profile(clone_config).get("compatible"):
            raise ValueError("The staged clone no longer matches the ANE quantisation contract.")
        clone_profile = ane_cpu_sharing_profile(staging)
        if not clone_profile.get("eligible"):
            raise ValueError(str(clone_profile.get("reason") or "The staged clone is not all-FP16."))
        source_valid, source_tensors, _source_manifest = safetensors_inventory(source)
        clone_valid, clone_tensors, _clone_manifest = safetensors_inventory(staging)
        if not source_valid or not clone_valid or set(source_tensors) != set(clone_tensors):
            raise ValueError("The staged clone tensor inventory does not match the source.")
        for name, source_tensor in source_tensors.items():
            clone_tensor = clone_tensors[name]
            if source_tensor.get("shape") != clone_tensor.get("shape"):
                raise ValueError(f"The staged clone changed tensor shape: {name}.")
            source_dtype = source_tensor.get("dtype")
            clone_dtype = clone_tensor.get("dtype")
            if source_dtype in {"BF16", "F16"}:
                if clone_dtype != "F16":
                    raise ValueError(f"The staged clone did not convert floating tensor: {name}.")
            elif clone_dtype != source_dtype:
                raise ValueError(f"The staged clone changed packed tensor dtype: {name}.")
        regular, size_bytes, reason = regular_directory_inventory(staging)
        if not regular:
            raise ValueError(reason)
        return {
            "path": str(Path(str(plan["destination"]))),
            "name": str(plan["destinationName"]),
            "sizeBytes": size_bytes,
            "sizeLabel": display_size(size_bytes),
            "cpuProfileFingerprint": clone_profile["profileFingerprint"],
            "floatDtypes": clone_profile["floatDtypes"],
            "gateUpScalePairs": clone_profile["gateUpScalePairs"],
        }

    def _worker(self, plan: dict[str, Any]) -> None:
        destination = Path(str(plan["destination"]))
        job_id = str(plan["jobId"])
        staging = destination.parent / f".llm-launcher-fp16-{job_id}"
        process: subprocess.Popen[str] | None = None
        try:
            if destination.exists() or staging.exists():
                raise ValueError("The destination changed before the clone could start.")
            self._event("Validating every source shard before writing the staging clone.")
            with self.lock:
                self.state["phase"] = "validating"
                self.state["progress"] = 0.01
            process = subprocess.Popen(
                [
                    str(plan["runtimePython"]), str(ANE_FP16_CLONE_HELPER),
                    str(plan["source"]), str(staging),
                ],
                cwd=str(APP_DIR), env=_hf_public_environment(), text=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                start_new_session=True, close_fds=True, bufsize=1,
            )
            with self.lock:
                self.process = process
            assert process.stdout is not None
            last_error = ""
            for raw_line in process.stdout:
                if self.cancel_event.is_set():
                    raise LaunchCancelled("FP16 clone preparation stopped.")
                try:
                    event = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue
                kind = str(event.get("event") or "")
                current = int(event.get("current") or 0)
                total = max(1, int(event.get("total") or 1))
                filename = Path(str(event.get("file") or "checkpoint shard")).name[:160]
                if kind == "validated":
                    progress = 0.35 * min(1.0, current / total)
                    message = f"Validated source shard {current}/{total}: {filename}"
                    phase = "validating"
                elif kind == "converted":
                    progress = 0.35 + 0.58 * min(1.0, current / total)
                    message = f"Prepared FP16 shard {current}/{total}: {filename}"
                    phase = "converting"
                elif kind == "error":
                    last_error = str(event.get("message") or "FP16 clone helper failed.")[:800]
                    continue
                else:
                    continue
                with self.lock:
                    self.state.update({"phase": phase, "progress": progress, "message": message})
            return_code = process.wait()
            if self.cancel_event.is_set():
                raise LaunchCancelled("FP16 clone preparation stopped.")
            if return_code != 0:
                raise RuntimeError(last_error or f"FP16 clone helper exited with status {return_code}.")
            with self.lock:
                self.state.update({
                    "phase": "verifying", "progress": 0.95,
                    "message": "Verifying the complete FP16 tensor contract before promotion…",
                })
            result = self._verify_clone(plan, staging)
            if destination.exists():
                raise ValueError("The final destination appeared during verification; the staging clone was not promoted.")
            staging.replace(destination)
            result.update({
                "source": str(plan["source"]),
                "sourceName": str(plan["sourceName"]),
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "sourcePreserved": True,
                "verified": True,
            })
            with self.lock:
                self.state.update({
                    "phase": "completed", "progress": 1.0,
                    "message": "Verified FP16 clone ready. The source checkpoint was not changed.",
                    "result": result,
                })
            self._event("Verified FP16 clone promoted atomically; rescan to use it.")
        except LaunchCancelled:
            with self.lock:
                self.state.update({
                    "phase": "cancelled", "message": "FP16 clone stopped; the private staging folder was removed.",
                })
        except Exception as error:  # noqa: BLE001
            with self.lock:
                self.state.update({"phase": "failed", "message": str(error)[:800]})
            self._event(str(error)[:800], "error")
        finally:
            if process is not None and process.poll() is None:
                self._terminate(process)
            if not destination.exists():
                self._cleanup_staging(staging, destination, job_id)
            with self.lock:
                if self.process is process:
                    self.process = None
                if self.thread is threading.current_thread():
                    self.thread = None

    def cancel(self) -> None:
        with self.lock:
            if not self.is_active():
                return
            self.cancel_event.set()
            self.state.update({
                "phase": "stopping",
                "message": "Stopping the clone helper and removing only its private staging folder…",
            })
            process = self.process
        if process is not None:
            self._terminate(process)
