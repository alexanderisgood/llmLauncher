"""Kolibri Q6 discovery and maximal bounded SSD expert-cache planning.

This module uses only the standard library in the controller. MLX and the
vendored model implementation are imported only in the owned engine worker.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import re
import struct
import subprocess
import sys
from typing import Any

GIB = 1024**3
MODEL_ID = "kolibri-1-q6-ssd"
VERSION = "Kolibri SSD 8 · streamlx 146507b · cached prefill + native metrics"
CONTEXTS = (2048, 4096, 8192, 16384, 32768, 65536, 131072, 262144)
DEFAULT_CONTEXT = 32768
DEFAULT_MEMORY_GB = 40
DEFAULT_OUTPUT = 4096
OUTPUT_MAXIMUM = 65536
KV_CHOICES = ("off", "q8", "q6", "q4")
KV_GROUP_SIZE = 64
PREFILL_SIZES = (64, 128, 256, 512, 1024, 2048)
DEFAULT_PREFILL = 64
DEFAULT_PROMPT_CACHE_GB = 1
VENDOR = Path(__file__).resolve().parent / "runtime_patches" / "kolibri"
PROMPT_CACHE_BYTES = GIB
BUFFER_CACHE_BYTES = GIB // 4
WORKSPACE_RESERVE_BYTES = 2 * GIB
OS_RESERVE_MIN_BYTES = 4 * GIB
RUNTIME_VERSIONS = {"mlx": "0.32.0", "mlx_lm": "0.31.3"}
EXPERT = re.compile(r"(?:^|\.)layers\.(\d+)\.mlp\.experts\.(gate_proj|up_proj|down_proj)\.(weight|scales|biases)$")


def _json(path: Path) -> dict[str, Any]:
    if path.stat().st_size > 4 * 1024**2:
        raise ValueError("Oversized Kolibri metadata.")
    result = json.loads(path.read_text())
    if not isinstance(result, dict):
        raise ValueError("Invalid Kolibri metadata.")
    return result


def _identity(paths: list[Path], content: Any = None) -> str:
    entries = []
    for path in paths:
        info = path.stat()
        entries.append([str(path.resolve()), info.st_dev, info.st_ino,
                        info.st_size, info.st_mtime_ns])
    return hashlib.sha256(json.dumps([entries, content], sort_keys=True).encode()).hexdigest()


def inspect_runtime(binary: str | None = None) -> dict[str, Any] | None:
    """Discover the already installed and exercised MLX library pair."""
    if platform.system() != "Darwin" or platform.machine() not in {"arm64", "aarch64"}:
        return None
    base = Path.home() / ".lmstudio/extensions/backends/vendor/_amphibian"
    candidates = [Path(binary)] if binary else sorted(
        base.glob("app-mlx-generate-mac*-arm64@*/bin/python"), reverse=True)
    for python in candidates:
        try:
            packages = next((python.parent.parent / "lib").glob("python*/site-packages"))
            identities = [python]
            for package, version in RUNTIME_VERSIONS.items():
                metadata = packages / f"{package}-{version}.dist-info/METADATA"
                if not metadata.is_file() or f"Version: {version}\n" not in metadata.read_text():
                    raise ValueError("An unqualified MLX library version is installed.")
                identities.append(metadata)
            server = packages / "mlx_lm/server.py"
            identities.append(server)
            if not os.access(python, os.X_OK):
                continue
            source_files = [Path(__file__), Path(__file__).resolve().parent / "pi_protocol.py",
                            Path(__file__).resolve().parent / "darwin_memory.py",
                            Path(__file__).resolve().parent / "resource_telemetry.py",
                            *sorted(VENDOR.rglob("*.py"))]
            manifest = _json(VENDOR / "provenance.json")
            for relative, expected in manifest["sha256"].items():
                source = VENDOR / relative
                if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
                    raise ValueError("The reviewed Kolibri runtime source changed.")
            return {"python": str(python), "version": VERSION,
                    "identity": _identity(identities + source_files, manifest), "ready": True}
        except (OSError, ValueError, KeyError, StopIteration):
            continue
    return None


def discover_python() -> str | None:
    runtime = inspect_runtime()
    return runtime["python"] if runtime else None


def inspect_model(root: Path) -> dict[str, Any] | None:
    """Read tensor headers and identities, never materialise model weights."""
    try:
        root = root.resolve(strict=True)
        config = _json(root / "config.json")
        expected = {"model_type": "kolibri1", "num_hidden_layers": 50,
                    "num_experts": 384, "num_experts_per_tok": 6,
                    "hidden_size": 2560, "moe_intermediate_size": 512,
                    "num_key_value_heads": 4, "num_attention_heads": 48, "head_dim": 128,
                    "sliding_window": 513, "max_position_embeddings": 262144,
                    "layer_types": ["sliding_attention"] * 4 + ["full_attention"]}
        expected["layer_types"] *= 10
        if any(config.get(key) != value for key, value in expected.items()):
            return None
        quant = config.get("quantization") or config.get("quantization_config") or {}
        if quant.get("bits") != 6 or quant.get("group_size") != 64:
            return None
        index = _json(root / "model.safetensors.index.json")
        weight_map = index["weight_map"]
        if not isinstance(weight_map, dict) or not weight_map:
            return None
        paths = [root / name for name in ("config.json", "model.safetensors.index.json",
                                         "tokenizer.json", "tokenizer_config.json", "chat_template.jinja")]
        if not all(p.is_file() for p in paths):
            return None
        tensor_bytes = trunk_bytes = 0
        expert_parts: dict[int, dict[str, int]] = {}
        seen = set()
        for filename in sorted(set(weight_map.values())):
            if not isinstance(filename, str) or Path(filename).name != filename:
                return None
            shard = root / filename
            size = shard.stat().st_size
            with shard.open("rb") as handle:
                header_length = struct.unpack("<Q", handle.read(8))[0]
                if not 0 < header_length <= 4 * 1024**2 or header_length + 8 >= size:
                    return None
                header = json.loads(handle.read(header_length))
            paths.append(shard)
            tensor_bytes += size
            for name, tensor in header.items():
                if name == "__metadata__":
                    continue
                if name not in weight_map or weight_map[name] != filename or name in seen:
                    return None
                seen.add(name)
                start, end = tensor["data_offsets"]
                if not 0 <= start < end <= size - 8 - header_length:
                    return None
                match = EXPERT.search(name)
                if match:
                    layer, projection, part = match.groups()
                    input_width = 512 if projection == "down_proj" else 2560
                    output_width = 2560 if projection == "down_proj" else 512
                    columns = input_width * 6 // 32 if part == "weight" else input_width // 64
                    dtype = "U32" if part == "weight" else "BF16"
                    expected_shape = [384, output_width, columns]
                    scalar_bytes = 4 if part == "weight" else 2
                    if tensor["shape"] != expected_shape or tensor["dtype"] != dtype or (end - start) != math.prod(expected_shape) * scalar_bytes:
                        return None
                    expert_parts.setdefault(int(layer), {})[f"{projection}.{part}"] = (end - start) // 384
                else:
                    trunk_bytes += end - start
        if seen != set(weight_map) or set(expert_parts) != set(range(50)):
            return None
        if any(len(parts) != 9 for parts in expert_parts.values()):
            return None
        row_bytes = [sum(expert_parts[layer].values()) for layer in range(50)]
        if len(set(row_bytes)) != 1:
            return None
        return {"path": str(root), "identity": _identity(paths, [config, index]),
                "weightBytes": tensor_bytes, "trunkBytes": trunk_bytes,
                "expertBytes": sum(row_bytes) * 384,
                "slotBytes": sum(row_bytes), "expertCount": 384, "topK": 6,
                "layers": 50, "fullAttentionLayers": 10, "slidingAttentionLayers": 40,
                "nativeContext": config["max_position_embeddings"], "attentionHeads": 48,
                "slidingWindow": 513, "kvBytesPerTokenPerLayer": 4 * 128 * 2 * 2}
    except (OSError, ValueError, TypeError, KeyError, IndexError, struct.error):
        return None


def memory_plan(model: dict[str, Any], context: int, options: dict[str, Any],
                resource: dict[str, Any]) -> dict[str, Any]:
    """Spend all admissible memory on whole expert slots, with explicit reserves."""
    if context not in CONTEXTS:
        raise ValueError("Choose a supported Kolibri context from 2K to 256K.")
    kv = options.get("kv", "off")
    if kv not in KV_CHOICES:
        raise ValueError("Choose full precision, Q8, Q6 or Q4 Kolibri KV cache.")
    prefill = options.get("prefillSize", DEFAULT_PREFILL)
    if type(prefill) is not int or prefill not in PREFILL_SIZES:
        raise ValueError("Choose a supported Kolibri prefill chunk from 64 to 2,048 tokens.")
    prompt_gb = options.get("promptCacheGB", DEFAULT_PROMPT_CACHE_GB)
    if type(prompt_gb) is not int or not 0 <= prompt_gb <= 8:
        raise ValueError("Kolibri retained prompt cache must be 0–8 GiB.")
    ceiling_gb = options.get("memoryGB", DEFAULT_MEMORY_GB)
    if type(ceiling_gb) is not int or not 8 <= ceiling_gb <= 512:
        raise ValueError("Kolibri maximum process memory must be 8–512 GB.")
    mode = options.get("memoryMode", "auto")
    if mode not in {"auto", "fixed"}:
        raise ValueError("Choose automatic or fixed Kolibri memory sizing.")
    total = int(resource.get("totalMemoryBytes") or 0)
    headroom = int(resource.get("headroomBytes") or 0)
    metal = int(resource.get("metalRecommendedWorkingSetBytes") or 0)
    reserve = max(OS_RESERVE_MIN_BYTES, math.ceil(total * .10))
    bits = None if kv == "off" else int(kv[1:])
    full_token_bytes = model["kvBytesPerTokenPerLayer"]
    if bits:
        # Packed uint32 weights plus BF16 scale and bias for every 64 values.
        values = full_token_bytes // 2
        full_token_bytes = values * bits // 8 + values // KV_GROUP_SIZE * 4
    full_kv = full_token_bytes * model["fullAttentionLayers"] * context
    # MLX does not implement rotating-cache quantization. Keep the native
    # sliding caches intact; their bounded size is small even at 256K.
    sliding_kv = model["kvBytesPerTokenPerLayer"] * model["slidingAttentionLayers"] * min(context, model["slidingWindow"])
    kv_bytes = full_kv + sliding_kv
    prompt_bytes = prompt_gb * GIB
    # Quantized attention materialises query/key scores, unlike fused SDPA.
    # Reserve float32 score/masking/softmax scratch for a complete prefill
    # chunk at the selected window, plus transient rotating-cache growth.
    attention_workspace = (model.get("attentionHeads", 48) * min(prefill, context) * context * 8) if bits else 0
    sliding_workspace = model["kvBytesPerTokenPerLayer"] * model["slidingAttentionLayers"] * prefill
    workspace = WORKSPACE_RESERVE_BYTES + attention_workspace + sliding_workspace
    overhead = model["trunkBytes"] + kv_bytes + prompt_bytes + BUFFER_CACHE_BYTES + workspace
    available = bool(resource.get("memoryAvailable") is True and total > 0 and headroom > 0)
    # The launcher observes Metal without importing MLX. The worker supplies
    # the device's exact limit at the final boundary before model allocation.
    metal_limit = metal or math.floor(total * .75)
    admissible = min(max(0, headroom - reserve), max(0, total - reserve), metal_limit)
    ceiling = ceiling_gb * 1_000_000_000
    target = min(ceiling, admissible) if mode == "auto" else ceiling
    slots = min(model["expertCount"], max(0, (target - overhead) // model["slotBytes"]))
    expert_bytes = slots * model["slotBytes"]
    working = overhead + expert_bytes
    ready = bool(available and slots >= model["topK"] and working <= admissible
                 and (mode == "auto" or ceiling <= admissible))
    return {"version": 2, "ready": ready, "memoryMode": mode,
            "memoryCeilingBytes": ceiling, "processLimitBytes": min(target, admissible),
            "expertCacheBytes": expert_bytes, "residentExpertsPerLayer": slots,
            "totalExpertsPerLayer": model["expertCount"],
            "residentWeightBytes": model["trunkBytes"] + expert_bytes,
            "residentWeightFraction": (model["trunkBytes"] + expert_bytes) / model["weightBytes"],
            "kvCacheBytes": kv_bytes, "fullAttentionKvBytes": full_kv, "slidingAttentionKvBytes": sliding_kv,
            "kv": kv, "kvBits": bits, "kvGroupSize": KV_GROUP_SIZE if bits else None,
            "kvPrecision": "full precision" if bits is None else f"{kv.upper()} full attention · BF16 sliding",
            "quantizedKvLayers": model["fullAttentionLayers"] if bits else 0,
            "fullPrecisionKvLayers": model["slidingAttentionLayers"] if bits else model["layers"],
            "prefillSize": prefill, "promptCacheBytes": prompt_bytes,
            "attentionWorkspaceBytes": attention_workspace, "workspaceReserveBytes": workspace,
            "runtimeReserveBytes": overhead - model["trunkBytes"] - kv_bytes,
            "estimatedWorkingSetBytes": working, "osReserveBytes": reserve,
            "requiredHeadroomBytes": working + reserve, "contextTokens": context,
            "basis": "Complete Q6 trunk plus the largest whole expert cache fitting current macOS headroom, the selected ceiling and Metal's working set. The selected KV precision applies to full attention; sliding caches remain BF16. Full selected-context KV, retained chat cache and prefill workspace have separate reserves. Rechecked before loading."}


def current_resource(metal_limit: int = 0) -> dict[str, Any]:
    # The engine wrapper runs with -I -S, so import only these verified local
    # standard-library modules explicitly. Never search a user project path.
    modules = {}
    for name in ("darwin_memory", "resource_telemetry"):
        path = Path(__file__).resolve().parent / f"{name}.py"
        module = sys.modules.get(name)
        if module is not None:
            if Path(getattr(module, "__file__", "")).resolve() != path:
                raise ValueError("Kolibri's native memory reader has an unexpected source.")
        else:
            spec = importlib.util.spec_from_file_location(name, path)
            if spec is None or spec.loader is None:
                raise ValueError("Kolibri's native memory reader is unavailable.")
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        modules[name] = module
    sample = modules["resource_telemetry"].apple_memory_pressure_state()
    headroom = modules["darwin_memory"].snapshot_reclaimable_bytes(sample)
    if headroom is None:
        raise ValueError("macOS cannot report physical memory headroom for Kolibri.")
    return {"memoryAvailable": True, "totalMemoryBytes": sample["totalBytes"],
            "headroomBytes": headroom,
            "memorySource": sample["reclaimableMemorySource"],
            "memorySemanticsVersion": sample["memorySemanticsVersion"],
            "metalRecommendedWorkingSetBytes": metal_limit}


def capability(model: dict[str, Any] | None, runtime: dict[str, Any] | None) -> dict[str, Any]:
    ready = bool(model and runtime and runtime.get("ready"))
    return {"runnable": ready,
            "reason": "Full Kolibri Q6 with SSD expert streaming and automatic memory sizing." if ready else "Requires the complete Kolibri Q6 checkpoint and the qualified local MLX runtime.",
            "mtp": False, "dflash": False, "kv": ready, "kvChoices": list(KV_CHOICES) if ready else ["off"],
            "kvScope": "full-attention", "kvGroupSize": KV_GROUP_SIZE,
            "mtpReason": "Kolibri uses its full native top-6 expert routing without speculative decoding.",
            "dflashReason": "No Kolibri draft model is qualified.",
            "preferredAcceleration": "off", "fallbackAcceleration": "off", "depth": 1, "depthMax": 1,
            "agentReasoning": ["off", "low", "medium", "high"], "codexReasoning": ["auto"],
            "contextWindows": list(CONTEXTS), "contextMaximum": max(CONTEXTS), "outputMaximum": OUTPUT_MAXIMUM,
            "prefillSizes": list(PREFILL_SIZES),
            "runtimeVersion": VERSION, "runtimeIdentity": runtime,
            "benchmarkModelFingerprint": model["identity"] if model else "",
            "customSampling": True, "implicitSamplingDefaultsVerified": False,
            "ssdStreaming": True, "exactExpertRouting": True,
            "modelPath": model["path"] if model else None,
            "localBenchmarks": [], "localBenchmark": None, "benchmarkHistoryCount": 0}


def clean_environment(env: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in env.items()
            if not key.startswith(("MLX_", "STREAMLX_", "DYLD_", "PYTHON", "SLOTSTREAM_", "MTPLX_"))}


def validate_served_catalog(data: Any, context: int, options: dict[str, Any] | None = None) -> dict[str, Any]:
    entries = data.get("data", []) if isinstance(data, dict) else []
    if len(entries) != 1 or entries[0].get("id") != MODEL_ID or entries[0].get("max_context_length") != context:
        raise ValueError("Kolibri's live model or context differs from the requested route.")
    live = data.get("kolibri")
    if not isinstance(live, dict) or live.get("ready") is not True or live.get("contextTokens") != context:
        raise ValueError("Kolibri did not confirm its expert memory plan.")
    options = options or {}
    expected = {"kv": options.get("kv", "off"),
                "prefillSize": options.get("prefillSize", DEFAULT_PREFILL),
                "promptCacheBytes": options.get("promptCacheGB", DEFAULT_PROMPT_CACHE_GB) * GIB}
    if any(live.get(key) != value for key, value in expected.items()):
        raise ValueError("Kolibri's live KV cache or prefill settings differ from the requested route.")
    return live


def _function_name(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value) is not None


def checked_chat_body(body: Any, context: int, output: int, reasoning: str) -> dict[str, Any]:
    """Validate text, function tools and Pi history before passing it to mlx-lm."""
    # The isolated bootstrap imports only the standard library. The worker
    # installs the trusted project path before calling this request validator.
    from pi_protocol import is_pi_summary

    if not isinstance(body, dict) or body.get("model") != MODEL_ID:
        raise ValueError("Choose the served Kolibri Q6 model.")
    forbidden = ("adapters", "draft_model", "num_draft_tokens", "chat_template_kwargs",
                 "kv_bits", "kv_group_size", "quantized_kv_start")
    if any(body.get(name) not in (None, [], {}, "") for name in forbidden):
        raise ValueError("Kolibri's draft, template and KV settings belong to the launched route.")
    tools = body.get("tools")
    if tools is not None:
        if not isinstance(tools, list) or len(tools) > 128:
            raise ValueError("Provide at most 128 function tools.")
        names = set()
        for tool in tools:
            function = tool.get("function") if isinstance(tool, dict) else None
            if (not isinstance(function, dict) or tool.get("type") != "function"
                    or not _function_name(function.get("name"))
                    or not isinstance(function.get("parameters", {}), dict)
                    or not isinstance(function.get("description", ""), str)
                    or function["name"] in names):
                raise ValueError("Provide distinct named function tools with JSON schemas.")
            names.add(function["name"])
    tool_choice = body.get("tool_choice")
    if tool_choice not in (None, "auto", "none"):
        raise ValueError("Kolibri supports automatic tool selection or tool_choice none.")
    messages = body.get("messages")
    if not isinstance(messages, list) or not 1 <= len(messages) <= 4096:
        raise ValueError("Provide a bounded text conversation.")
    checked_messages = []
    for message in messages:
        if not isinstance(message, dict) or message.get("role") not in {"system", "user", "assistant", "tool"}:
            raise ValueError("Kolibri accepts text messages and function-tool results.")
        message = dict(message)
        calls = message.get("tool_calls")
        if calls is not None:
            if message["role"] != "assistant" or not isinstance(calls, list) or len(calls) > 128:
                raise ValueError("Only assistant messages may contain function-tool calls.")
            for call in calls:
                function = call.get("function") if isinstance(call, dict) else None
                if (not isinstance(function, dict) or call.get("type") != "function"
                        or not isinstance(call.get("id"), str) or not 1 <= len(call["id"]) <= 256
                        or not _function_name(function.get("name"))
                        or not isinstance(function.get("arguments"), str)):
                    raise ValueError("Provide function-tool calls with IDs and JSON arguments.")
                try:
                    arguments = json.loads(function["arguments"])
                except ValueError as exc:
                    raise ValueError("Tool-call arguments must be a JSON object.") from exc
                if not isinstance(arguments, dict):
                    raise ValueError("Tool-call arguments must be a JSON object.")
        content = message.get("content")
        if content is None and message["role"] == "assistant" and calls:
            content = ""
        if isinstance(content, list):
            if any(not isinstance(part, dict) or part.get("type") != "text"
                   or not isinstance(part.get("text"), str) for part in content):
                raise ValueError("Kolibri accepts text content only.")
            content = "".join(part["text"] for part in content)
        if not isinstance(content, str):
            raise ValueError("Kolibri accepts text messages only.")
        message["content"] = content
        for field in ("reasoning", "reasoning_content"):
            if message.get(field) is None:
                message.pop(field, None)
            elif not isinstance(message[field], str):
                raise ValueError("Assistant reasoning must be text.")
        if message["role"] == "tool":
            call_id = message.get("tool_call_id")
            if not isinstance(call_id, str) or not 1 <= len(call_id) <= 256:
                raise ValueError("Tool results require their original tool-call ID.")
        checked_messages.append(message)
    tokens = body.get("max_completion_tokens", body.get("max_tokens", output))
    if type(tokens) is not int or not 1 <= tokens <= output or tokens >= context:
        raise ValueError("The response exceeds the selected Kolibri output limit.")
    effort = "none" if reasoning == "off" else reasoning
    requested_effort = body.get("reasoning_effort", effort)
    summary = is_pi_summary(checked_messages)
    if summary and requested_effort == "none":
        effort = "none"
    elif requested_effort not in {reasoning, effort}:
        raise ValueError("Reasoning differs from the launched Kolibri setting.")
    result = dict(body)
    result["messages"] = checked_messages
    result["max_tokens"] = min(tokens, 4096) if summary else tokens
    result.pop("max_completion_tokens", None)
    if tool_choice == "none":
        result.pop("tools", None)
    # mlx-lm chooses tools automatically from the native chat template; it
    # does not implement forced tool selection. Do not pass an ignored control.
    result.pop("tool_choice", None)
    result["chat_template_kwargs"] = {"reasoning_effort": effort}
    return result


def run_verified(config_path: Path) -> None:
    config = _json(config_path)
    runtime = inspect_runtime(config["runtime"]["python"])
    model = inspect_model(Path(config["model"]["path"]))
    if runtime != config["runtime"] or not model or model != config["model"]:
        raise ValueError("Kolibri changed after planning. Rescan before launching.")
    env = clean_environment(dict(os.environ))
    env.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                "HF_HUB_DISABLE_TELEMETRY": "1", "STREAMLX_PREFETCH": "0", "STREAMLX_RESIDENT": "off"})
    argv = [runtime["python"], "-I", "-B", "-u", str(VENDOR / "worker.py"), str(config_path)]
    os.execve(argv[0], argv, env)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Use the Kolibri route inside LLM Launcher.")
    run_verified(Path(sys.argv[1]))
