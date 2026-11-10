#!/usr/bin/env python3
"""Isolated Strata/Slotstream measurements; never changes launcher preferences.

Each cold repetition owns a fresh engine under the shared benchmark lock.
Strata timing is bound to exactly one native request; streamed delivery is
never substituted for generation timing. Existing prompt files are read only.
"""
from __future__ import annotations

import argparse
import ast
import copy
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# Import the controller's native telemetry before quality.py adds bench/ to
# sys.path; bench/darwin_memory.py is an older, incompatible helper.
import darwin_memory
import resource_telemetry
import slotstream_runtime
from bench import harness, quality

STRATA_ROOT = ROOT / "bench/runtimes/strata-0.1.44.1"
PROMPTS = {32768: "ledger32k2-32768.txt", 131072: "ledger2-120000.txt"}
# This exact sidecar is part of the shipped Q8 route's qualification, although
# the upstream weight manifest predates it (runtime-patches/slotstream-q8/manifest.json).
SLOTSTREAM_EXTRA_FILES = [{
    "path": "lookahead/tap-correction-attention-rank128-v1.safetensors", "size": 37540708,
    "sha256": "37b00d3a32d1e1889a1794bbb8e97905a157a77c0508db620c1a11f2a895f7f5",
}]


def long_quality_prompt(reference):
    """Same synthetic facts and positions for both engines, without editing the standing ledger."""
    codes = {"early": "cedar-71829", "middle": "quartz-40617", "late": "cobalt-93582"}
    parts, positions, last = [], {}, 0
    for label, fraction in (("early", .10), ("middle", .50), ("late", .90)):
        offset = int(len(reference) * fraction)
        offset = reference.find("\n", offset) + 1 or offset
        parts.append(reference[last:offset])
        positions[label] = sum(map(len, parts))
        parts.append(f"\nIndependent audit fact: the {label} vault code is {codes[label]}.\n")
        last = offset
    parts.append(reference[last:])
    parts.append("\nFinal task: Return only one JSON object with keys early, middle, late, arithmetic, and bounded. "
                 "Use the three independent audit vault codes from the document. arithmetic is (17*23)+(144/12). "
                 "bounded is the three results of min(a+b,limit) for (2,3,10), (7,8,9), and (-4,1,10), in that order. "
                 "This final task replaces the ledger's earlier writing task. No prose or Markdown.\n")
    return "".join(parts), {**codes, "arithmetic": 403, "bounded": [5, 9, -3]}, positions


def _unfence(text):
    value = text.strip()
    if value.startswith("```") and value.endswith("```"):
        value = value.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return value


def score_probe(probe_id, content, expected=None):
    """Check known answers; generated code is parsed and interpreted, never executed."""
    value = _unfence(content)
    if probe_id == "arithmetic":
        try:
            number = Decimal(value)
            return number.is_finite() and number == 403
        except InvalidOperation:
            return False
    if probe_id == "recall":
        return value.lower() == "lattice"
    if probe_id in {"json-tool", "long-recall"}:
        try:
            return json.loads(value) == (expected if expected is not None else {"status": "ready", "count": 3})
        except (ValueError, TypeError):
            return False
    if probe_id != "code":
        raise ValueError("Unknown scored probe")
    try:
        tree = ast.parse(value)
        if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
            return False
        function = tree.body[0]
        if function.name != "bounded_add" or function.decorator_list or function.args.defaults or function.args.kw_defaults:
            return False
        if function.args.posonlyargs or function.args.kwonlyargs or function.args.vararg or function.args.kwarg:
            return False
        if [arg.arg for arg in function.args.args] != ["a", "b", "limit"]:
            return False
        body = list(function.body)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            body.pop(0)
        if len(body) != 1 or not isinstance(body[0], ast.Return):
            return False

        def evaluate(node, values):
            if isinstance(node, ast.Name) and node.id in values:
                return values[node.id]
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
                return evaluate(node.left, values) + evaluate(node.right, values)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "min" and len(node.args) == 2 and not node.keywords:
                return min(evaluate(arg, values) for arg in node.args)
            if isinstance(node, ast.IfExp):
                return evaluate(node.body if evaluate(node.test, values) else node.orelse, values)
            if isinstance(node, ast.Compare) and len(node.ops) == len(node.comparators) == 1:
                left, right = evaluate(node.left, values), evaluate(node.comparators[0], values)
                if isinstance(node.ops[0], ast.Lt):
                    return left < right
                if isinstance(node.ops[0], ast.LtE):
                    return left <= right
                if isinstance(node.ops[0], ast.Gt):
                    return left > right
            raise ValueError("Expression outside the bounded arithmetic probe")

        cases = [(2, 3, 10), (7, 8, 9), (-4, 1, 10), (1, 2, -1), (3, 6, 9)]
        return all(evaluate(body[0].value, dict(zip(("a", "b", "limit"), values))) == min(values[0] + values[1], values[2])
                   for values in cases)
    except (ValueError, SyntaxError, TypeError, RecursionError):
        return False


def positive(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"Missing or invalid {label}")
    return value


def integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"Missing or invalid {label}")
    return value


def bind_strata_timing(sample, before, after):
    """Bind native DONE counters to the sole request since the prior snapshot.

    Strata's API completion count may include server-added framing tokens.
    The /metrics row supplies the separate native generation count; using the
    API count divided by native time would inflate generation throughput.
    """
    previous = integer(before.get("totals", {}).get("requests"), "previous request count")
    current = integer(after.get("totals", {}).get("requests"), "current request count")
    if current != previous + 1 or after.get("live", {}).get("state") != "idle":
        raise ValueError("Strata metrics do not describe exactly one settled request")
    rows = after.get("requests")
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        raise ValueError("Strata did not publish a native request record")
    row = rows[0]
    prompt = integer(sample.get("promptTokens"), "API prompt tokens", 1)
    output = integer(sample.get("completionTokens"), "API completion tokens", 1)
    if row.get("prompt_tokens") != prompt or row.get("output_tokens") != output:
        raise ValueError("Strata native request does not match API usage")
    generated = integer(row.get("engine_generated"), "native generated tokens", 1)
    processed = integer(row.get("prompt_read"), "native processed prompt tokens")
    reused = integer(row.get("reused"), "native reused tokens")
    if processed + reused != prompt:
        raise ValueError("Strata processed/reused counters do not match the prompt")
    timings = sample.get("engineTimings")
    if not isinstance(timings, dict) or timings.get("predicted_n") != output:
        raise ValueError("Strata response lacks matching request-native timing")
    decode_ms = positive(row.get("decode_ms"), "native decode milliseconds")
    if not math.isclose(positive(timings.get("predicted_ms"), "response decode milliseconds"), decode_ms, abs_tol=.11):
        raise ValueError("Strata response and native decode clocks disagree")
    if timings.get("prompt_n") != processed or timings.get("cache_n") != reused:
        raise ValueError("Strata response and native prompt counters disagree")
    rate = generated * 1000 / decode_ms
    if not math.isclose(positive(timings.get("predicted_per_second"), "native decode rate"), rate, abs_tol=.11):
        raise ValueError("Strata response rate disagrees with its native count and clock")
    result = copy.deepcopy(sample)
    result.update({
        "decodeTokensPerSecond": rate, "generationTokensPerSecond": rate,
        "nativeDecodeTokensPerSecond": rate, "decodeTimingValid": True,
        "decodeTimingSource": "strata-request-native-done",
        "decodeTimingBasis": "native-generation-count-and-clock",
        "cachedPromptTokens": reused,
        "generationProof": {"version": 1, "backend": "strata", "completionTokens": output,
                            "decodeTokenCount": generated, "generationSeconds": decode_ms / 1000,
                            "tokensPerSecond": rate, "nativeRequest": copy.deepcopy(row)},
    })
    for key in ("nativePrefillTokensPerSecond", "prefillTokensPerSecond", "prefillSeconds"):
        result.pop(key, None)
    if processed:
        prompt_ms = positive(row.get("prompt_ms"), "native prompt milliseconds")
        if not math.isclose(positive(timings.get("prompt_ms"), "response prompt milliseconds"), prompt_ms, abs_tol=.11):
            raise ValueError("Strata response and native prompt clocks disagree")
        result.update(nativePrefillTokensPerSecond=processed * 1000 / prompt_ms,
                      prefillTokensPerSecond=processed * 1000 / prompt_ms,
                      prefillSeconds=prompt_ms / 1000)
    return result


def metrics(engine):
    request = urllib.request.Request(f"http://127.0.0.1:{engine.port}/metrics",
                                     headers={"Authorization": "Bearer " + engine.api_key})
    with urllib.request.urlopen(request, timeout=10) as response:
        raw = response.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("Strata metrics exceed the bounded report size")
    return json.loads(raw)


def served_catalog(engine):
    request = urllib.request.Request(f"http://127.0.0.1:{engine.port}/v1/models")
    if engine.api_key:
        request.add_header("Authorization", "Bearer " + engine.api_key)
    with urllib.request.urlopen(request, timeout=10) as response:
        raw = response.read(65537)
    if len(raw) > 65536:
        raise ValueError("Served model catalog exceeds the bounded size")
    return json.loads(raw)


def validate_strata_catalog(catalog, model_id, context):
    """Strata reports the native READY context through meta.n_ctx."""
    data = catalog.get("data") if isinstance(catalog, dict) else None
    if not isinstance(data, list):
        raise ValueError("Strata served model catalog is unavailable")
    models = [row for row in data if isinstance(row, dict) and row.get("id") == model_id]
    if len(models) != 1:
        raise ValueError("Strata served model identity is missing or ambiguous")
    model = models[0]
    meta, status = model.get("meta"), model.get("status")
    if not isinstance(meta, dict) or type(meta.get("n_ctx")) is not int or meta["n_ctx"] != context:
        raise ValueError("Strata served context does not match the requested window")
    if not isinstance(status, dict) or status.get("value") != "loaded":
        raise ValueError("Strata served model is not loaded")


def replace_option(args, name, value):
    result = list(args)
    positions = [i for i, item in enumerate(result) if item == name or item.startswith(name + "=")]
    if len(positions) > 1:
        raise ValueError(f"Duplicate {name} in engine configuration")
    if positions:
        i = positions[0]
        if "=" in result[i]:
            result[i:i + 1] = [name, str(value)]
        else:
            if i + 1 == len(result):
                raise ValueError(f"Missing {name} value")
            result[i:i + 2] = [name, str(value)]
    else:
        result += [name, str(value)]
    return result


def make_strata(config_path, context, port, work):
    source_bytes = Path(config_path).read_bytes()
    original = json.loads(source_bytes.decode("utf-8-sig"))
    if original.get("backend") != "metal" or "flash-next" not in original.get("model_name", "").lower():
        raise ValueError("Expected an installed Flash-Next Metal configuration")
    if "ud-q4_k_xl" not in original["model_name"].lower():
        raise ValueError("This comparison requires the full-expert Q4 route")
    cfg = copy.deepcopy(original)
    exe = Path(cfg["exe"]).resolve()
    if not exe.is_file():
        raise FileNotFoundError(exe)
    args = cfg.get("args")
    if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        raise ValueError("Invalid Strata engine arguments")
    cfg["args"] = replace_option(args, "--max-context", context)
    cfg["env"] = {**cfg.get("env", {}), "STRATA_ROUTE_TAIL_SKIP": "0", "STRATA_PREFILL_CPU_SHARE": "0"}
    cfg.update(host="127.0.0.1", port=port, parallel=1, api_key=secrets.token_urlsafe(32),
               log=str(work / "strata-native.log"))
    for key in ("mcp_servers", "vision", "images", "slot_save_path"):
        cfg.pop(key, None)
    private = work / "strata.json"
    engine = harness.Engine(
        name="strata", argv=[str(STRATA_ROOT / ".venv/bin/python"), "-u", "-m", "serve.server",
                             "--engine", "strata", "--config", str(private), "--host", "127.0.0.1",
                             "--port", str(port)],
        env={"PYTHONPATH": str(STRATA_ROOT), "PYTHONUNBUFFERED": "1"},
        port=port, model_id=cfg["model_name"], work_dir=work, api_key=cfg["api_key"], ready_timeout=1800,
        extra={"backend": "strata", "context": context, "sourceConfig": str(config_path),
               "sourceConfigSha256": hashlib.sha256(source_bytes).hexdigest(),
               "_privateConfig": cfg, "_privateConfigPath": private},
    )
    return engine


def measured_chat(engine, prompt, tokens):
    before = metrics(engine) if engine.name == "strata" else None
    result = harness.stream_chat(engine, prompt, max_tokens=tokens, temperature=0, seed=42,
                                 reasoning_effort="none", extra_body={"top_p": 1, "top_k": 0})
    if before is not None:
        result = bind_strata_timing(result, before, metrics(engine))
    if result.get("nativeDecodeTokensPerSecond") is None:
        raise ValueError("Benchmark requires request-native generation timing")
    result["sha256"] = hashlib.sha256(result["content"].encode()).hexdigest()
    return result


class ResourceGuard:
    def __init__(self, process, ceiling_bytes, reserve_bytes):
        self.process, self.ceiling, self.reserve = process, ceiling_bytes, reserve_bytes
        self.done = threading.Event()
        self.samples, self.failure = [], None
        self.thread = threading.Thread(target=self._watch, daemon=True)

    def _watch(self):
        while not self.done.wait(1):
            if self.process.poll() is not None:
                return
            reason = None
            try:
                vm = darwin_memory.physical_reclaimable_state(resource_telemetry.physical_memory_bytes())
                group = resource_telemetry.darwin_process_group_physical_footprint(self.process.pid)
                row = {"at": time.monotonic(), "memory": vm, "processGroup": group,
                       "thermal": resource_telemetry.apple_process_resource_state({0: "nominal", 1: "fair", 2: "serious", 3: "critical"})}
                if self.process.poll() is not None:
                    return
                self.samples.append(row)
                if not vm.get("physicalMemoryAvailable") or not group.get("processGroupFootprintAvailable"):
                    reason = "Required native resource telemetry is unavailable"
                elif vm["reclaimableBytes"] < self.reserve:
                    reason = "Protected macOS memory reserve reached"
                elif group["processGroupPhysicalFootprintBytes"] > self.ceiling:
                    reason = "Private benchmark process ceiling exceeded"
            except Exception as error:
                reason = f"Resource monitor failed: {type(error).__name__}: {error}"
            if reason:
                if self.process.poll() is not None:
                    return
                self.failure = reason
                try:
                    os.killpg(self.process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                except OSError as error:
                    self.failure += f"; owned process-group stop failed: {type(error).__name__}: {error}"
                return

    def stop(self):
        self.done.set()
        if self.thread.ident is not None:
            self.thread.join(timeout=5)


def start_clean(engine):
    """Drop inherited runtime tuning; keep only this engine's explicit plan."""
    engine.work_dir.mkdir(parents=True, exist_ok=True)
    if "_privateConfig" in engine.extra:
        with engine.extra["_privateConfigPath"].open("x", encoding="utf-8") as config_file:
            stat = os.fstat(config_file.fileno())
            engine.extra["_createdPrivateConfigIdentity"] = (stat.st_dev, stat.st_ino)
            os.chmod(engine.extra["_privateConfigPath"], 0o600)
            json.dump(engine.extra["_privateConfig"], config_file, indent=2)
    engine.log_path = engine.work_dir / "engine.log"
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("STRATA_", "SLOTSTREAM_", "MTPLX_", "MLX_", "DYLD_"))}
    env.update(engine.env)
    with engine.log_path.open("ab") as output:
        engine.process = subprocess.Popen(engine.argv, env=env, stdout=output, stderr=subprocess.STDOUT,
                                          start_new_session=True)


def dispose_private_config(engine):
    identity = engine.extra.get("_createdPrivateConfigIdentity")
    path = engine.extra.get("_privateConfigPath")
    if identity is None or path is None:
        return
    try:
        stat = path.lstat()
        if (stat.st_dev, stat.st_ino) == identity:
            path.unlink()
    except FileNotFoundError:
        pass


def verify_slotstream_weights(engine, previous=None):
    """Hash the pinned weights once, then bind later repetitions to that identity."""
    install = slotstream_runtime.inspect_install(engine.argv[0], engine.extra["model"])
    if not install["ready"] or not install["mtp"] or install["missing"]:
        raise ValueError("The complete pinned Slotstream model and MTP weights are required")
    root = Path(install["modelPath"])
    extra_identities = []
    for row in SLOTSTREAM_EXTRA_FILES:
        path = root / row["path"]
        if path.is_symlink() or not path.is_file() or path.stat().st_size != row["size"]:
            raise ValueError("The qualified Slotstream lookahead sidecar is required")
        extra_identities.append(slotstream_runtime.identity(path))
    if previous is not None:
        for key in ("artifactIdentity", "runtimeIdentity"):
            if install[key] != previous["install"][key]:
                raise ValueError("Slotstream files changed after full checksum verification")
        if extra_identities != previous["extraFileIdentities"]:
            raise ValueError("Slotstream sidecar changed after full checksum verification")
        return previous
    started = time.monotonic()
    files = []
    print("[bench] verifying complete Slotstream model checksums", flush=True)
    for row in [*slotstream_runtime.FILES, *SLOTSTREAM_EXTRA_FILES]:
        path = root / row["path"]
        before = slotstream_runtime.identity(path)
        actual = slotstream_runtime.digest(path)
        if actual != row["sha256"] or before != slotstream_runtime.identity(path):
            raise ValueError(f"Slotstream checksum or file identity mismatch: {row['path']}")
        files.append({"path": row["path"], "bytes": row["size"], "sha256": actual})
    settled = slotstream_runtime.inspect_install(engine.argv[0], engine.extra["model"])
    if settled != install or extra_identities != [slotstream_runtime.identity(root / row["path"]) for row in SLOTSTREAM_EXTRA_FILES]:
        raise ValueError("Slotstream files changed during full checksum verification")
    return {"install": install, "files": files, "extraFileIdentities": extra_identities,
            "verificationSeconds": time.monotonic() - started}


def argument_value(args, name):
    positions = [i for i, value in enumerate(args) if value == name or value.startswith(name + "=")]
    if len(positions) != 1:
        raise ValueError(f"Expected exactly one {name} argument")
    i = positions[0]
    if "=" in args[i]:
        return args[i].split("=", 1)[1]
    if i + 1 >= len(args):
        raise ValueError(f"Missing {name} value")
    return args[i + 1]


def strata_runtime_files(runtime_root, exe):
    """Metal reads shader source at runtime; the executable hash alone is insufficient."""
    root = Path(runtime_root).resolve()
    paths = {Path(exe).resolve(), root / "third_party/llama.cpp/ggml/src/ggml-common.h",
             root / "tools/strata_tokenizer.py", root / "data/expert-profile.bin"}
    paths.update(p for p in (root / "metal").rglob("*") if p.suffix in {".metal", ".h", ".hpp"})
    paths.update((root / "serve").rglob("*.py"))
    return sorted({p.resolve() for p in paths}, key=str)


def verify_strata_weights(engine, manifest_path, previous=None):
    """Bind native tensors, host-converted pack and tokenizer to the verified installation."""
    from bench import strata_stream_repack as preparation
    manifest_path = Path(manifest_path)
    preparation.owned_regular(manifest_path)
    installed = json.loads(manifest_path.read_text())
    if installed.get("schemaVersion") != 1 or installed.get("status") != "verified":
        raise ValueError("Complete the verified Strata model installation before benchmarking")
    model_root = Path(installed["workDirectory"]).resolve(strict=True)
    pack_root = Path(installed["packDirectory"]).resolve(strict=True)
    prepared_path, state_path = model_root / "verified-model.json", model_root / "stream-state.json"
    for path in (prepared_path, state_path):
        preparation.owned_regular(path)
    prepared, state = json.loads(prepared_path.read_text()), json.loads(state_path.read_text())
    if (prepared.get("status") != "verified" or prepared.get("sourceRevision") != preparation.REVISION
            or prepared.get("sources") != preparation.SOURCES or state.get("stage") != "complete"
            or state.get("planSha256") != prepared.get("planSha256")
            or slotstream_runtime.digest(prepared_path) != installed.get("preparedManifestSha256")
            or installed.get("nativeOutputs") != prepared.get("outputs")):
        raise ValueError("Strata installation is incomplete or its source identity changed")
    proofs = prepared.get("sourceProofs", {})
    if any(proofs.get(str(i), {}).get("sha256") != source["sha256"] for i, source in enumerate(preparation.SOURCES)):
        raise ValueError("Strata preparation lacks complete pinned source verification")
    identity = installed.get("expertIdentity", {})
    if identity.get("layers") != 48 or identity.get("expertsPerLayer") != 512:
        raise ValueError("The original full-expert Strata model is required")
    native_args = engine.extra["_privateConfig"]["args"]
    if Path(argument_value(native_args, "--pack")).resolve() != pack_root:
        raise ValueError("Strata configuration points to an unverified pack")
    expected_files = []
    runtime_root = Path(installed["runtimeDirectory"]).resolve(strict=True)
    exe = Path(engine.extra["_privateConfig"]["exe"]).resolve(strict=True)
    declared_runtime = set()
    for row in installed["runtimeFiles"]:
        path = Path(row["path"]).resolve(strict=True)
        if not path.is_relative_to(runtime_root) or path in declared_runtime:
            raise ValueError("Invalid Strata runtime inventory")
        declared_runtime.add(path)
        expected_files.append((path, row["bytes"], row["sha256"]))
    if declared_runtime != set(strata_runtime_files(runtime_root, exe)):
        raise ValueError("Strata executable, kernel or server source inventory changed")
    for key, flag in (("native", "--native"), ("ple", "--ple-gguf")):
        row = installed["nativeOutputs"][key]
        path = model_root / f"{key}.gguf"
        if Path(row["path"]).resolve() != path or Path(argument_value(native_args, flag)).resolve() != path:
            raise ValueError("Strata configuration points to unverified model weights")
        expected_files.append((path, row["bytes"], row["sha256"]))
    declared = set()
    for row in installed["packFiles"]:
        relative = Path(row["path"])
        if relative.is_absolute() or ".." in relative.parts or row["path"] in declared:
            raise ValueError("Invalid installed pack inventory")
        declared.add(row["path"])
        expected_files.append((pack_root / relative, row["bytes"], row["sha256"]))
    required = {"dense.bin", "index.txt", "native_experts.txt", "tokenizer/vocab.json", "tokenizer/chat_template.jinja"}
    actual = set()
    for path in pack_root.rglob("*"):
        if path.is_symlink():
            raise ValueError("Unexpected link in the installed Strata pack")
        if path.is_file() and path.name != ".DS_Store":
            actual.add(str(path.relative_to(pack_root)))
    if not required <= declared or actual != declared:
        raise ValueError("Strata pack or tokenizer inventory changed")
    if (model_root / "native.gguf.experts").exists():
        raise ValueError("Register and verify the optional expert streaming copy before benchmarking it")
    paths = [manifest_path, prepared_path, state_path, *(p for p, _, _ in expected_files)]

    def snapshots():
        result = []
        for path in paths:
            info = preparation.owned_regular(path)
            result.append({"path": str(path), "device": info.st_dev, "inode": info.st_ino, "bytes": info.st_size,
                           "mtimeNs": info.st_mtime_ns, "ctimeNs": info.st_ctime_ns})
        return result

    before = snapshots()
    if previous is not None:
        if previous["fileSnapshots"] != before:
            raise ValueError("Strata weights, pack or tokenizer changed after verification")
        return previous
    started = time.monotonic()
    print("[bench] verifying Strata native weights, host pack and tokenizer", flush=True)
    for path, size, expected in expected_files:
        if path.stat().st_size != size or slotstream_runtime.digest(path) != expected:
            raise ValueError(f"Strata installed-file checksum mismatch: {path.name}")
    if before != snapshots():
        raise ValueError("Strata installed files changed during verification")
    return {"backend": "strata", "preparedManifestSha256": installed["preparedManifestSha256"],
            "fileSnapshots": before, "expertIdentity": identity, "sourceRevision": preparation.REVISION,
            "sourcePins": preparation.SOURCES, "verificationSeconds": time.monotonic() - started}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("strata", "slotstream"), required=True)
    parser.add_argument("--strata-config", type=Path)
    parser.add_argument("--strata-install-manifest", type=Path, default=ROOT / "bench/results/20261015-strata-model-install.json")
    parser.add_argument("--context", type=int, choices=tuple(PROMPTS), required=True)
    parser.add_argument("--prompt-file", type=Path)
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--tokens", type=int, default=256)
    parser.add_argument("--port", type=int, default=18765)
    parser.add_argument("--memory-gb", type=float, default=slotstream_runtime.DEFAULT_MEMORY_GB)
    parser.add_argument("--label", default="strata-comparison")
    parser.add_argument("--quality-only", action="store_true")
    parser.add_argument("--long-quality-only", action="store_true", help="run one fresh long-quality request to complete a previous measurement batch")
    parser.add_argument("--skip-long-quality", action="store_true", help="omit the extra long retrieval request during tuning; record this limit")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not 1 <= args.reps <= 10 or not 1 <= args.tokens <= 4096 or not 1024 <= args.port <= 65535:
        parser.error("Invalid repetition, token or port limit")
    if not 8 <= args.memory_gb <= 40:
        parser.error("Memory ceiling must be 8–40 decimal GB")
    if args.engine == "strata" and args.strata_config is None:
        parser.error("--strata-config is required")
    if args.long_quality_only and (args.quality_only or args.skip_long_quality):
        parser.error("--long-quality-only cannot be combined with other quality stage switches")
    prompt_path = args.prompt_file or ROOT / "bench/prompts" / PROMPTS[args.context]
    prompt = prompt_path.read_text()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    report = {"schemaVersion": 1, "label": args.label, "engine": args.engine, "context": args.context,
              "promptFile": str(prompt_path), "promptSha256": hashlib.sha256(prompt.encode()).hexdigest(),
              "configuredOutputTokens": args.tokens, "measurements": [], "quality": [], "resources": [],
              "status": "prepared", "qualityPassed": None, "defaultChanged": False, "runs": [],
              "runnerSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "coldScope": "fresh engine and no prompt-prefix reuse; OS file cache is not forcibly cleared",
              "qualityScope": "four bounded probes per repetition plus long retrieval/arithmetic in a separate fresh engine" if not args.skip_long_quality else "four bounded probes only"}
    if args.long_quality_only:
        report["qualityScope"] = "one long retrieval/arithmetic probe in a fresh engine"
    report_path = ROOT / "bench/results" / f"{run_id}-{args.engine}-comparison.json"

    def save():
        report_path.parent.mkdir(exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n")

    verified_slotstream = None
    verified_strata = None
    cycles = [] if args.long_quality_only else [("baseline", rep) for rep in range(args.reps)]
    if not args.skip_long_quality:
        cycles.append(("long-quality", 0))
    report["expectedEngineStarts"] = len(cycles)
    for cycle_index, (phase, rep) in enumerate(cycles):
        work = ROOT / "bench/runs" / f"{run_id}-{args.engine}-{phase}-{rep}"
        if args.engine == "strata":
            engine = make_strata(args.strata_config, args.context, args.port, work)
        else:
            engine = harness.make_slotstream(context=args.context, port=args.port, kv="q8", memory_gb=args.memory_gb,
                                             memory_auto=True, draft_depth=2, mtp="on", work_dir=work)
        if args.dry_run:
            print(json.dumps({"engine": args.engine, "context": args.context, "command": engine.argv,
                              "environment": engine.env, "phase": phase, "expectedEngineStarts": len(cycles),
                              "promptSha256": report["promptSha256"]}, indent=2))
            return 0
        public_config = engine.extra.get("_privateConfig", {})
        report["runs"].append({"rep": rep, "phase": phase, "command": engine.argv, "environment": engine.env,
                               "runtimeSha256": hashlib.sha256(Path(public_config.get("exe") or engine.argv[0]).read_bytes()).hexdigest(),
                               "nativeArguments": public_config.get("args"),
                               "nativeEnvironment": public_config.get("env"),
                               "sourceConfigSha256": engine.extra.get("sourceConfigSha256"),
                               "modelName": engine.model_id})
        guard = None
        try:
            with harness.bench_run(f"{args.label} {args.engine} {phase} rep {rep + 1}", minimum_headroom_gb=20):
                try:
                    if args.engine == "slotstream":
                        verified_slotstream = verify_slotstream_weights(engine, verified_slotstream)
                        report["weightVerification"] = verified_slotstream
                        # Allow released Metal allocations and memory statistics
                        # to settle before the same native doctor used by the launcher.
                        time.sleep(3)
                        report["runs"][-1]["nativeMemoryPlan"] = slotstream_runtime.doctor(
                            verified_slotstream["install"], args.context,
                            {"kv": "q8", "depth": 2, "acceleration": "mtp", "memoryMode": "auto",
                             "memoryGB": args.memory_gb})
                    else:
                        verified_strata = verify_strata_weights(engine, args.strata_install_manifest, verified_strata)
                        report["weightVerification"] = verified_strata
                    start_clean(engine)
                    report["runs"][-1]["pid"] = engine.process.pid
                    guard = ResourceGuard(engine.process, int(args.memory_gb * 1e9), int(resource_telemetry.physical_memory_bytes() * .10))
                    guard.thread.start()
                    engine.wait_ready()
                    catalog = served_catalog(engine)
                    report["runs"][-1]["servedCatalog"] = catalog
                    if args.engine == "slotstream":
                        slotstream_runtime.validate_served_catalog(catalog, args.context, "q8")
                    else:
                        validate_strata_catalog(catalog, engine.model_id, args.context)
                    if phase == "baseline" and not args.quality_only:
                        result = measured_chat(engine, prompt, args.tokens)
                        if result.get("cachedPromptTokens") != 0:
                            raise ValueError("Cold benchmark unexpectedly reused prompt tokens")
                        positive(result.get("nativePrefillTokensPerSecond"), "request-native cold prefill rate")
                        report["measurements"].append({"rep": rep, **result})
                    for probe in quality.PROBES if phase == "baseline" else ():
                        result = measured_chat(engine, probe["prompt"], probe["maxTokens"])
                        passed = score_probe(probe["id"], result["content"])
                        report["quality"].append({"rep": rep, "phase": phase, "probeId": probe["id"], "passed": passed, **result})
                        if not passed:
                            report["qualityPassed"] = False
                    if phase == "long-quality":
                        long_prompt, expected, positions = long_quality_prompt(prompt)
                        quality_path = ROOT / "bench/prompts" / f"strata-quality-v1-{args.context}.txt"
                        if quality_path.exists():
                            if quality_path.read_text() != long_prompt:
                                raise ValueError("Saved quality prompt differs; preserve it and use a new version")
                        else:
                            with quality_path.open("x", encoding="utf-8") as handle:
                                handle.write(long_prompt)
                        result = measured_chat(engine, long_prompt, 256)
                        if result.get("cachedPromptTokens") != 0:
                            raise ValueError("Fresh long-quality request unexpectedly reused prompt tokens")
                        passed = score_probe("long-recall", result["content"], expected)
                        report["quality"].append({"rep": rep, "phase": phase, "probeId": "long-recall", "passed": passed,
                                                  "promptFile": str(quality_path), "factCharacterOffsets": positions,
                                                  "promptSha256": hashlib.sha256(long_prompt.encode()).hexdigest(),
                                                  "expected": expected, **result})
                        if not passed:
                            report["qualityPassed"] = False
                    if guard.failure:
                        raise RuntimeError(guard.failure)
                finally:
                    if guard is not None:
                        guard.stop()
                    engine.stop()
                    if guard is not None:
                        report["resources"].append({"rep": rep, "phase": phase, "failure": guard.failure, "samples": guard.samples})
        except BaseException as error:
            report.update(status="failed", error=f"{type(error).__name__}: {error}")
            save()
            raise
        finally:
            dispose_private_config(engine)
        # A wrong answer is a recorded accuracy result, not a resource failure.
        # Collect the complete comparison without granting a passing quality gate.
        failed = sum(row["passed"] is False for row in report["quality"])
        complete = cycle_index == len(cycles) - 1
        report["qualityPassed"] = False if failed else (True if complete else None)
        report["qualitySummary"] = {"passed": len(report["quality"]) - failed, "failed": failed,
                                    "total": len(report["quality"]), "complete": complete}
        report["status"] = ("failed-quality" if failed else "measured") if complete else "in_progress"
        save()
        print(f"Saved {phase} repetition {rep + 1}: {report_path}", flush=True)
    return 2 if report["qualityPassed"] is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
