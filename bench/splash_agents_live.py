#!/usr/bin/env python3
"""Opt-in, bounded installed Splash -> real Pi/oh-my-pi tool verification.

Loads one already-installed packed model, serializes with BenchLock, checks
live whole-host headroom and foreign engines, and terminates only processes
started here. All prompts, tool files, agent settings and logs are temporary.
The saved result contains route/settings and timing metadata, never messages
or keys. This is functional evidence, not a before/after inference benchmark.

Example (no downloads or permanent agent installs):
  python3 bench/splash_agents_live.py --splash /path/engine/splash \
    --pack /path/incoai/Qwen3.8-27B-Splash --pi /path/pi --omp /path/omp \
    --result bench/results/splash-agents-live.json
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from unittest import mock
import urllib.request
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import launcher
import darwin_memory
import launcher_shutdown
import session_proxy
import splash_runtime
from bench.harness import BenchLock


def free_port() -> int:
    with socket.socket() as handle:
        handle.bind(("127.0.0.1", 0))
        return handle.getsockname()[1]


def json_get(port: int, path: str, key: str = "") -> dict:
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                    headers={"Authorization": f"Bearer {key}"} if key else {})
    with urllib.request.urlopen(request, timeout=3) as response:
        return json.load(response)


def foreign_engines(owned_groups: set[int]) -> list[tuple[int, str]]:
    result = subprocess.run(["/bin/ps", "-ww", "-axo", "pid=,pgid=,command="],
                            capture_output=True, text=True, timeout=5, check=True)
    found = []
    names = {"omlx", "omlx-server", "mtplx", "llama-server", "slotstream", "splash", "Uzu", "uzu", "whallm"}
    scripts = {str(launcher.APP_DIR / relative) for relative in (
        "runtime_patches/kolibri/worker.py", "runtime_patches/kolibri/serve.py", "kolibri_runtime.py",
        "splash_runtime.py", "splash_reasoning.py", "slotstream_runtime.py", "whallm_runtime.py",
        "omlx_hub_runtime.py", "mtplx_hub_runtime.py")}
    for key in launcher_shutdown.ENGINE_KEYS:
        installed = launcher.BINARIES.get(key)
        if installed:
            scripts.update(launcher_shutdown._installed_server_scripts(key, installed))
    for line in result.stdout.splitlines():
        fields = line.strip().split(None, 2)
        if len(fields) != 3 or int(fields[1]) in owned_groups:
            continue
        try:
            tokens = shlex.split(fields[2])
        except ValueError:
            continue
        if not tokens:
            continue
        executable = Path(tokens[0]).name
        native_server = executable in {"omlx-server", "llama-server", "splash", "Uzu", "uzu", "whallm"}
        named_server = executable in names and any(arg in {"serve", "server", "api-server"} for arg in tokens[1:])
        python_server = any(launcher_shutdown._command_tail(fields[2], script) is not None for script in scripts)
        installed_engine = launcher_shutdown.process_label(
            launcher_shutdown.LocalProcess(os.getuid(), int(fields[0]), 0, "", fields[2]),
            launcher.BINARIES, launcher.APP_DIR) in launcher_shutdown.ENGINE_KEYS
        if native_server or named_server or python_server or installed_engine:
            found.append((int(fields[0]), executable))
    return found


class Safety:
    def __init__(self):
        self.groups: set[int] = set()
        self.allow_idle: dict[int, int] = {}
        self.stop = threading.Event()
        self.error: str | None = None
        self.minimum_free: float | None = None
        self.minimum_reclaimable: int | None = None
        self.protected_reserve: int | None = None
        self.peak_footprint = 0
        self.worker = threading.Thread(target=self.monitor, daemon=True)

    def check(self):
        if self.error:
            raise RuntimeError(self.error)

    def sample(self):
        memory = launcher.apple_memory_pressure_state()
        if memory.get("memoryAvailable") is not True:
            raise RuntimeError("Live whole-host memory headroom is unavailable")
        free = float(memory["freePercent"])
        self.minimum_free = min(self.minimum_free if self.minimum_free is not None else free, free)
        if free < 20:
            raise RuntimeError("Whole-host memory headroom fell below the protected20% reserve")
        physical_reserve = max(launcher.SESSION_OS_RESERVE_MIN_BYTES,
                               round(int(memory["totalBytes"]) * launcher.SESSION_OS_RESERVE_FRACTION))
        reclaimable = darwin_memory.snapshot_reclaimable_bytes(memory)
        if reclaimable is None:
            raise RuntimeError("Fresh native physical reclaimable capacity is unavailable")
        self.minimum_reclaimable = min(self.minimum_reclaimable if self.minimum_reclaimable is not None else reclaimable, reclaimable)
        self.protected_reserve = physical_reserve
        if reclaimable < physical_reserve:
            raise RuntimeError("Physical reclaimable memory fell below the protected macOS reserve")
        for pid, name in foreign_engines(self.groups):
            port = self.allow_idle.get(pid)
            if port is None:
                raise RuntimeError(f"A foreign {name} engine is present (PID{pid}); no new load is safe")
            status = json_get(port, "/api/status")
            if any(status.get(field) != 0 for field in ("models_loaded", "models_loading", "active_requests", "waiting_requests")):
                raise RuntimeError("The independently running oMLX service began work")
        for pgid in tuple(self.groups):
            footprint = launcher.darwin_process_group_physical_footprint(pgid)
            if (footprint.get("processGroupMemberCount", 0) > 0 and
                    footprint.get("processGroupFootprintAvailable") is not True):
                raise RuntimeError("Owned process-group physical footprint is unavailable")
            self.peak_footprint = max(self.peak_footprint, int(footprint.get("processGroupPhysicalFootprintBytes") or 0))

    def monitor(self):
        while not self.stop.wait(2):
            try:
                self.sample()
            except Exception as error:
                self.error = str(error)
                return


def stop_owned(process: subprocess.Popen):
    # A new session was created for every child; never signal another group.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def memory_guard(model: dict, project: Path, binaries: dict[str, str]) -> dict:
    """Apply the launcher validator and an independent physical-reclaim guard."""
    snapshot = launcher.apple_resource_snapshot()
    resource = launcher.public_session_resource(snapshot)
    admissions = []
    with mock.patch.dict(launcher.BINARIES, binaries):
        for client in ("pi", "omp"):
            payload = {"backend": "splash", "client": client, "modelId": model["id"],
                       "project": str(project), "context": 16384, "output": 1024,
                       "reasoning": "off", "agentHost": "terminal", "mode": "custom", "options": {}}
            admission = launcher.session_memory_admission(payload, [model], resource,
                {"phase": "idle"}, {"active": False})
            admissions.append({"client": client, "launchable": admission.get("launchable"),
                               "decision": admission.get("decision"), "requiresAcknowledgement": admission.get("requiresAcknowledgement"),
                               "estimate": admission.get("estimate")})
    required = max(int(item["estimate"]["requiredHeadroomBytes"]) for item in admissions)
    reclaimable = darwin_memory.snapshot_reclaimable_bytes(snapshot)
    # BenchLock's shared harness normally requires20GB. Preserve that floor
    # and the larger exact model+KV+runtime+protected macOS reserve estimate.
    required = max(required, 20_000_000_000)
    ready = all(item["launchable"] is True and item["decision"] == "ready" and
                item["requiresAcknowledgement"] is False for item in admissions) and reclaimable is not None and reclaimable >= required
    return {"ready": ready, "launcherAdmissions": admissions, "resource": resource,
            "physicalReclaimableBytes": reclaimable, "physicalRequiredHeadroomBytes": required,
            "physicalMemorySource": snapshot.get("reclaimableMemorySource"),
            "physicalGuardBasis": "host_statistics64 free-speculative+purgeable+file-backed pages; exact working-set+macOS reserve, minimum20GB"}


def native_status_metrics(port: int, key: str, model: str) -> dict:
    status = json_get(port, "/status", key)
    if status.get("instance", {}).get("model") != model or status.get("transport", {}).get("status_stale") is not False:
        raise RuntimeError("Splash native status is stale or targets a different model")
    fields = ("prefill_input_tokens", "prefill_wall_ms", "prefill_tokens_per_second",
              "decode_output_tokens", "decode_wall_ms", "decode_cycle_ms", "decode_tokens_per_second",
              "drafted_tokens", "accepted_draft_tokens", "draft_acceptance_rate")
    values = status.get("metrics") or {}
    return {"source": "splash-native-status-command-counters", "metrics": {field: values.get(field) for field in fields},
            "currentMemoryBytes": status.get("memory_actual", {}).get("current_bytes"),
            "peakMemoryBytes": status.get("memory_actual", {}).get("peak_bytes"),
            "memoryLimitBytes": status.get("memory_governor", {}).get("limit_bytes")}


def run_client(plan, binary: str, root: Path, safety: Safety) -> subprocess.CompletedProcess:
    project = root / "project"; project.mkdir()
    (root / "agent").mkdir()
    (root / "data/omp").mkdir(parents=True)
    marker = f"SPLASH_{plan.client.upper()}_VERIFIED_7182"
    prompt = (f"Use write to create proof.txt containing exactly {marker}. "
              "Then use read on proof.txt to verify it. Finally reply with that marker. "
              "Do not use other tools or files. This needs only a brief check.")
    env = {"PATH": os.environ["PATH"], "TMPDIR": str(root),
           "PI_CODING_AGENT_DIR": str(root / "agent"), "PI_CODING_AGENT_SESSION_DIR": str(root / "sessions"),
           "XDG_DATA_HOME": str(root / "data"), "PI_OFFLINE": "1", "PI_TELEMETRY": "0", **plan.client_env}
    args = ["--no-extensions", "--no-skills"]
    if plan.client == "pi":
        args += ["--no-prompt-templates", "--no-themes", "--no-context-files", "--no-approve", "--offline",
                 "--system-prompt", "You are verifying a local tool transport. Follow the exact small task and stop."]
    else:
        args += ["--no-rules", "--no-title", "--no-lsp", "--no-prewalk", "--no-pty", "--tools", "read,write"]
    argv = [binary, *args, *plan.client_argv[1:], "--mode", "json", "--print", "--no-session", prompt]
    child = subprocess.Popen(argv, cwd=project, env=env, text=True, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True)
    safety.groups.add(child.pid)
    try:
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            safety.check()
            try:
                stdout, stderr = child.communicate(timeout=1)
                break
            except subprocess.TimeoutExpired:
                continue
        else:
            raise TimeoutError(f"{plan.client} exceeded its180s functional-check deadline")
        if child.returncode != 0:
            raise RuntimeError(f"{plan.client} exited{child.returncode}: {stderr[-2000:]}")
        if not (project / "proof.txt").is_file() or (project / "proof.txt").read_text().strip() != marker:
            raise AssertionError(f"{plan.client} did not complete the real write/read task")
        events = [json.loads(line) for line in stdout.splitlines() if line.startswith("{")]
        finals = [event["message"] for event in events if event.get("type") == "message_end" and
                  event.get("message", {}).get("role") == "assistant"]
        if not finals or finals[-1].get("stopReason") != "stop" or marker not in json.dumps(finals[-1].get("content")):
            raise AssertionError(f"{plan.client} did not finish with the expected final answer")
        return subprocess.CompletedProcess(argv, child.returncode, stdout, stderr)
    finally:
        stop_owned(child)
        safety.groups.discard(child.pid)


def verify_agent(client: str, binary: str, model: dict, port: int, engine_key: str, root: Path, safety: Safety) -> dict:
    root.mkdir()
    run_id = str(uuid.uuid4())
    contract = launcher.build_sampling_contract("model").as_dict()
    enforcement = launcher.sampling_route_enforcement("splash", client, model["backends"]["splash"], contract)
    client_key = secrets.token_urlsafe(32)
    requests = []
    native_requests = []
    relay = session_proxy.RelayHTTPServer(("127.0.0.1", 0), session_proxy.ProxyHandler)
    relay.config = {"listenPort": relay.server_port, "upstreamPort": port, "upstreamKey": engine_key,
                    "controlKey": secrets.token_urlsafe(32), "backend": "splash", "servedModel": model["splash"]["id"],
                    "reasoning": "off", "outputLimit": 1024}
    relay.registry = session_proxy.SurfaceRegistry([{"id": run_id, "client": client, "key": client_key,
        "samplingContract": contract, "samplingEnforcement": enforcement}])
    relay.scheduler = session_proxy.RequestScheduler(1)
    worker = threading.Thread(target=relay.serve_forever, daemon=True); worker.start()
    plan = launcher.LaunchPlan(run_id=run_id, backend="splash", client=client, model=model,
        project=str(root / "project"), context=16384, output=1024, reasoning="off", port=port,
        mode="custom", options={}, run_dir=root)
    try:
        with mock.patch.dict(launcher.BINARIES, {client: binary}):
            builder = launcher.build_pi_client if client == "pi" else launcher.build_omp_client
            builder(plan, launcher.ClientRoute("splash-live", model["splash"]["id"],
                    f"http://127.0.0.1:{relay.server_port}/v1", client_key))
        relay.config["servedModelAliases"] = [launcher.pi_model_identity(plan)[1]]
        try:
            json_get(relay.server_port, "/v1/models")
        except urllib.error.HTTPError as error:
            if error.code != 401:
                raise AssertionError("The private relay returned an unexpected unauthenticated status") from error
        else:
            raise AssertionError("The private relay accepted an unauthenticated catalog request")
        splash_runtime.validate_served_catalog(json_get(relay.server_port, "/v1/models", client_key), model["splash"]["id"])
        transform = session_proxy.transform_chat_request
        metrics_type = session_proxy.ResponseMetrics
        class ObservedMetrics(metrics_type):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.native = {"source": "splash-native-stream-request-lifecycle", "usage": None, "timings": None, "metrics": None}
                native_requests.append(self.native)

            def _inspect(self, value):
                emitted = super()._inspect(value)
                if isinstance(value, dict):
                    # These documented engine fields contain counters and
                    # timings only; prompt/tool/reasoning/response deltas are
                    # never copied into the saved native observation.
                    for field in ("usage", "timings", "metrics"):
                        if isinstance(value.get(field), dict):
                            self.native[field] = value[field]
                return emitted
        def record(body, config, surface=None):
            result = transform(body, config, surface)
            requests.append(json.loads(result))
            return result
        start = time.monotonic()
        native_before = native_status_metrics(port, engine_key, model["splash"]["id"])
        with mock.patch.object(session_proxy, "transform_chat_request", record), \
                mock.patch.object(session_proxy, "ResponseMetrics", ObservedMetrics):
            run_client(plan, binary, root, safety)
        if len(requests) < 2:
            raise AssertionError(f"{client} omitted write/read/final turns")
        if any(request.get("model") != model["splash"]["id"] or request.get("max_tokens") != 1024 or
               request.get("reasoning_effort") != "none" for request in requests):
            raise AssertionError(f"{client} changed the exact served model/output/reasoning contract")
        messages = requests[-1]["messages"]
        tool_calls = [tool["function"]["name"] for message in messages if message.get("role") == "assistant"
                      for tool in message.get("tool_calls", [])]
        if not {"read", "write"}.issubset(tool_calls) or not any(message.get("role") == "tool" for message in messages):
            raise AssertionError(f"{client} lost actual tool history")
        read_ids = {tool["id"] for message in messages if message.get("role") == "assistant"
                    for tool in message.get("tool_calls", []) if tool["function"]["name"] == "read"}
        marker = f"SPLASH_{client.upper()}_VERIFIED_7182"
        if not any(message.get("role") == "tool" and message.get("tool_call_id") in read_ids
                   and marker in str(message.get("content")) for message in messages):
            raise AssertionError(f"{client} did not carry the actual successful file read into history")
        metrics = relay.scheduler.snapshot(relay.registry.public())["recent"]
        if len(metrics) != len(requests) or any(item.get("result") != "completed" for item in metrics):
            raise AssertionError(f"{client} relay did not record all completed model requests")
        if len(native_requests) != len(requests) or any(not item.get("usage") or not item.get("timings") for item in native_requests):
            raise AssertionError(f"{client} did not report native usage/timing for every model request")
        if any(not 1 <= item["usage"]["completion_tokens"] <= 1024 or
               item["usage"].get("completion_tokens_details", {}).get("reasoning_tokens") != 0 for item in native_requests):
            raise AssertionError(f"{client} violated its exact output or reasoning-off contract")
        native_after = native_status_metrics(port, engine_key, model["splash"]["id"])
        return {"client": client, "requests": len(requests), "nativeTools": ["write", "read"],
                "finalAnswerVerified": True, "historyVerified": True, "actualReadVerified": True,
                "surfaceAuthenticationEnforced": True, "reasoningOffVerified": True, "model": model["splash"]["id"],
                "context": 16384, "output": 1024, "reasoning": "off", "elapsedSeconds": round(time.monotonic() - start, 3),
                "nativeRequests": native_requests, "nativeStatusBefore": native_before, "nativeStatusAfter": native_after,
                "metrics": [{field: item.get(field) for field in ("promptTokens", "completionTokens", "runSeconds",
                    "firstOutputSeconds", "generationSeconds", "decodeTokensPerSecond", "endToEndTokensPerSecond",
                    "observedStatsSource", "runtimeTokensPerSecond", "runtimeStatsSource", "result", "statusCode")}
                    for item in reversed(metrics)]}
    finally:
        relay.shutdown(); relay.server_close(); worker.join(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("splash", "pack", "pi", "omp", "result"):
        parser.add_argument(f"--{argument}", required=True)
    parser.add_argument("--idle-omlx-port", type=int, help="Allow only a verified unloaded oMLX listener; monitor throughout")
    parser.add_argument("--guard-wait-seconds", type=int, default=60, help="Wait bounded for unmodified physical headroom")
    parser.add_argument("--agents", choices=("pi", "omp"), nargs="+", default=["pi", "omp"],
                        help="Verify selected agents; a fresh invocation owns a fresh engine")
    args = parser.parse_args()
    install = splash_runtime.inspect_install(args.splash)
    pack = splash_runtime.inspect_pack(Path(args.pack))
    if not install or install.get("ready") is not True or not pack or pack.get("kind") != "pack":
        raise RuntimeError("An installed, verified packed Splash model/runtime is required")
    model = splash_runtime.model_record(install, pack, [("splash", "Splash")], launcher.physical_memory_bytes())
    safety = Safety()
    with BenchLock("Splash1.2.1 real Pi/OMP bounded tools", wait_seconds=60), tempfile.TemporaryDirectory(prefix="launcher-splash-agents-") as tmp:
        root = Path(tmp)
        engines = foreign_engines(set())
        if args.idle_omlx_port and len(engines) == 1 and engines[0][1] == "omlx-server":
            listener = subprocess.run(["/usr/sbin/lsof", "-nP", "-a", "-p", str(engines[0][0]), "-iTCP", "-sTCP:LISTEN"],
                                      capture_output=True, text=True, timeout=5, check=True).stdout
            if f"127.0.0.1:{args.idle_omlx_port} (LISTEN)" in listener:
                safety.allow_idle[engines[0][0]] = args.idle_omlx_port
        safety.sample()
        engine = None
        results = {"kind": "native-functional-verification", "beforeAfterTPSClaim": False,
                   "runtime": install["runtimeVersion"], "release": install["release"],
                   "model": pack["id"], "artifactIdentity": pack["identity"], "agents": [],
                   "selectedAgents": args.agents,
                   "harnessSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        guard_deadline = time.monotonic() + max(0, min(args.guard_wait_seconds, 300))
        while True:
            safety.sample()
            guard = memory_guard(model, root, {"splash": args.splash, "pi": args.pi, "omp": args.omp})
            if guard["ready"]:
                break
            if time.monotonic() >= guard_deadline:
                results.update({"memoryGuard": guard, "engineStarted": False, "blocked": "physical-headroom"})
                destination = Path(args.result); destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(json.dumps(results, indent=2) + "\n")
                print(json.dumps({"result": str(destination), "blocked": "physical-headroom",
                    "reclaimableGB": round((guard["physicalReclaimableBytes"] or 0) / 1e9, 2),
                    "requiredGB": round(guard["physicalRequiredHeadroomBytes"] / 1e9, 2), "engineStarted": False}), flush=True)
                return
            print(f"[live] waiting for unmodified physical headroom: {(guard['physicalReclaimableBytes'] or 0)/1e9:.1f}GB/{guard['physicalRequiredHeadroomBytes']/1e9:.1f}GB", flush=True)
            time.sleep(5)
        results["memoryGuard"] = guard
        safety.worker.start()
        try:
            run = root / "engine"; run.mkdir()
            plan = launcher.LaunchPlan(run_id=str(uuid.uuid4()), backend="splash", client="chat", model=model,
                project=str(root), context=16384, output=1024, reasoning="off", port=free_port(),
                mode="custom", options={}, run_dir=run, runtime_binary=str(Path(args.splash).resolve()))
            launcher.build_splash(plan, model["backends"]["splash"])
            with (root / "engine.log").open("w") as log:
                engine = subprocess.Popen(plan.engine_argv, cwd=root, env={**os.environ, **plan.engine_env},
                    stdout=log, stderr=subprocess.STDOUT, text=True, start_new_session=True)
                safety.groups.add(engine.pid)
                results["engineStarted"] = True
                deadline = time.monotonic() + 150
                while time.monotonic() < deadline:
                    safety.check()
                    if engine.poll() is not None:
                        raise RuntimeError("Owned Splash process exited during startup; " + (root / "engine.log").read_text()[-2000:])
                    try:
                        catalog = json_get(plan.port, "/v1/models", plan.secrets["apiKey"])
                        splash_runtime.validate_served_catalog(catalog, pack["id"])
                        if any(item.get("max_model_len") != 16384 or item.get("context_length") != 16384 for item in catalog["data"]):
                            raise AssertionError("Native Splash catalog does not match the selected16K context")
                        results["nativeContextVerified"] = True
                        break
                    except OSError:
                        time.sleep(.25)
                else:
                    raise TimeoutError("Owned Splash process exceeded its150s startup deadline")
                try:
                    json_get(plan.port, "/v1/models")
                except urllib.error.HTTPError as error:
                    if error.code != 401:
                        raise AssertionError("Native Splash returned an unexpected unauthenticated status") from error
                    results["engineAuthenticationEnforced"] = True
                else:
                    raise AssertionError("Native Splash accepted an unauthenticated catalog request")
                for client, binary in ((client, args.pi if client == "pi" else args.omp) for client in args.agents):
                    print(f"[live] verifying real {client} through authenticated relay", flush=True)
                    results["agents"].append(verify_agent(client, binary, model, plan.port, plan.secrets["apiKey"], root / client, safety))
                    safety.check()
        except Exception as error:
            results["error"] = {"type": type(error).__name__, "message": str(error).splitlines()[0][:200]}
            raise
        finally:
            if engine is not None:
                stop_owned(engine)
                safety.groups.discard(engine.pid)
            safety.stop.set(); safety.worker.join(timeout=8)
            results.update({"minimumPressureFreePercent": safety.minimum_free,
                        "minimumPhysicalReclaimableBytes": safety.minimum_reclaimable,
                        "physicalMemorySource": darwin_memory.PHYSICAL_MEMORY_SOURCE,
                        "protectedMacOsReserveBytes": safety.protected_reserve,
                        "peakOwnedGroupPhysicalFootprintBytes": safety.peak_footprint,
                        "ownedEngineStopped": engine is not None and engine.poll() is not None})
            destination = Path(args.result); destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(results, indent=2) + "\n")
        print(json.dumps({"result": str(destination), "agents": [(r["client"], r["requests"]) for r in results["agents"]],
                          "ownedEngineStopped": results["ownedEngineStopped"]}), flush=True)


if __name__ == "__main__":
    main()
