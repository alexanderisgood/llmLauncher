"""Owned, authenticated Kolibri Q6 MLX server with SSD expert streaming."""
from __future__ import annotations

import functools
import importlib.util
import io
import json
import logging
import os
from pathlib import Path
import secrets
import sys

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(HERE))

import kolibri_runtime as route


def main(config_path: Path) -> None:
    config = route._json(config_path)
    model_info = route.inspect_model(Path(config["model"]["path"]))
    runtime = route.inspect_runtime(config["runtime"]["python"])
    if model_info != config["model"] or runtime != config["runtime"]:
        raise ValueError("Kolibri changed before allocation. Rescan models.")
    context, output, reasoning = config["context"], config["output"], config["reasoning"]
    if context not in route.CONTEXTS or type(output) is not int or not 1 <= output <= min(route.OUTPUT_MAXIMUM, context - 1024):
        raise ValueError("Invalid Kolibri context/output contract.")
    if reasoning not in {"off", "low", "medium", "high"} or not config.get("apiKey"):
        raise ValueError("Invalid Kolibri reasoning or authentication contract.")

    import mlx.core as mx
    import mlx_lm.server as srv
    from kolibri_adapter import register
    kv = config["options"].get("kv", "off")
    if kv not in route.KV_CHOICES:
        raise ValueError("Invalid Kolibri KV cache setting.")
    register(kv_bits=None if kv == "off" else int(kv[1:]), kv_group_size=route.KV_GROUP_SIZE)

    class ExpectedWarning(logging.Filter):
        def filter(self, record):
            return 'model of type `kolibri1` to instantiate a model of type ``' not in record.getMessage()
    logging.getLogger("transformers.configuration_utils").addFilter(ExpectedWarning())

    spec = importlib.util.spec_from_file_location("kolibri_stream_server", HERE / "serve.py")
    stream_server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stream_server)
    stream_server.load_streaming_model = functools.partial(stream_server.load_streaming_model, k=6)
    live_plan: dict = {}

    class KolibriHandler(srv.APIHandler):
        def _authorized(self):
            expected = "Bearer " + config["apiKey"]
            if secrets.compare_digest(self.headers.get("Authorization", ""), expected):
                return True
            self._error(401, "Authentication required.")
            return False

        def _error(self, status, message, code=None):
            error = {"message": message, "type": "invalid_request_error"}
            if code:
                error["code"] = code
            data = json.dumps({"error": error}).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self._authorized():
                return
            if self.path == "/v1/models":
                if self.response_generator.model_provider.tokenizer is None:
                    self._error(503, "Kolibri is still loading.")
                    return
                plan = dict(live_plan)
                plan.update({"peakMlxMemoryBytes": mx.get_peak_memory(),
                             "activeMlxMemoryBytes": mx.get_active_memory()})
                data = json.dumps({"object": "list", "data": [{
                    "id": route.MODEL_ID, "object": "model",
                    "max_context_length": context}], "kolibri": plan}).encode()
                self._set_completion_headers()
                self.end_headers()
                self.wfile.write(data)
            elif self.path == "/health":
                super().handle_health_check()
            else:
                self._error(404, "Unknown Kolibri endpoint.")

        def do_POST(self):
            if not self._authorized():
                return
            if self.path not in {"/v1/chat/completions", "/chat/completions"}:
                self._error(404, "Kolibri serves Chat Completions.")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 4 * 1024**2:
                    raise ValueError("Provide a bounded request body.")
                body = json.loads(self.rfile.read(length))
                body = route.checked_chat_body(body, context, output, reasoning)
                encoded = json.dumps(body).encode()
                # The stock handler keeps sampling/usage/stream framing. It
                # reads only this validated copy, with locked template effort.
                original = self.rfile
                self.rfile = io.BytesIO(encoded)
                self.headers.replace_header("Content-Length", str(len(encoded)))
                try:
                    super().do_POST()
                finally:
                    self.rfile = original
            except (ValueError, TypeError, UnicodeError):
                self._error(400, "Invalid Kolibri request or selected context/output limit exceeded.")

        def handle_completion(self, request, stop_words):
            tokenizer = self.response_generator.model_provider.tokenizer
            if request.tools and not tokenizer.has_tool_calling:
                self._error(400, "Kolibri's native function-tool parser is unavailable.")
                return
            # Native mlx-lm turns JSON argument strings into objects before
            # applying the template. Count exactly that representation, along
            # with the tools and the effective effort for this request.
            messages = json.loads(json.dumps(request.messages))
            srv.process_message_content(messages)
            template_args = dict(self.response_generator.model_provider.cli_args.chat_template_args)
            template_args.update(self.chat_template_kwargs or {})
            prompt = tokenizer.apply_chat_template(
                messages, tools=request.tools, tokenize=True,
                add_generation_prompt=True, **template_args)
            if len(prompt) + self.max_tokens > context:
                self._error(400, "context_length_exceeded: This conversation and response allowance exceed the selected Kolibri context window.",
                            code="context_length_exceeded")
                return
            return super().handle_completion(request, stop_words)

    srv.APIHandler = KolibriHandler
    native_http = srv._run_http_server

    def owned_http(host, port, response_generator):
        return native_http(host, port, response_generator, handler_class=KolibriHandler)

    srv._run_http_server = owned_http
    native_run = srv.run

    def bounded_run(host, port, model_provider):
        # This boundary is after mlx-lm.main's own wired-limit setup, before
        # its response thread loads the model or allocates any expert slots.
        resource = route.current_resource(mx.device_info()["max_recommended_working_set_size"])
        plan = route.memory_plan(model_info, context, config["options"], resource)
        if not plan["ready"]:
            raise ValueError("Not enough available memory for the selected Kolibri route. Close other models or reduce the memory ceiling.")
        live_plan.update(plan)
        mx.set_memory_limit(plan["processLimitBytes"])
        mx.set_wired_limit(plan["processLimitBytes"])
        mx.set_cache_limit(route.BUFFER_CACHE_BYTES)
        stream_server._CFG["budget_bytes"] = plan["expertCacheBytes"]
        stream_server._CFG["prompt_cache_bytes"] = plan["promptCacheBytes"]
        # Count the exact allocation actually used after the final recheck.
        memory_file = config_path.parent / "kolibri-memory.json"
        fd = os.open(memory_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as handle:
            json.dump(plan, handle, indent=2)
        print(f"[kolibri] {plan['residentExpertsPerLayer']}/384 experts per layer; "
              f"{plan['expertCacheBytes']/route.GIB:.2f} GiB expert cache; "
              f"{plan['residentWeightBytes']/1e9:.2f} GB resident weight capacity; "
              f"{plan['estimatedWorkingSetBytes']/1e9:.2f} GB working-set plan; "
              f"{plan['kvPrecision']} KV; {plan['prefillSize']} token prefill", flush=True)
        return native_run(host, port, model_provider)

    srv.run = bounded_run
    initial = route.memory_plan(model_info, context, config["options"],
                                route.current_resource(mx.device_info()["max_recommended_working_set_size"]))
    if not initial["ready"]:
        raise ValueError("Free memory before loading Kolibri.")
    effort = "none" if reasoning == "off" else reasoning
    sys.argv = [str(HERE / "serve.py"),
                "--model", model_info["path"], "--host", "127.0.0.1", "--port", str(config["port"]),
                "--budget-gib", str(initial["expertCacheBytes"] / route.GIB),
                "--prompt-cache-gib", str(initial["promptCacheBytes"] / route.GIB), "--mlx-cache-gib", "0.25",
                "--allowed-origins", f"http://127.0.0.1:{config['port']}",
                "--temp", "1.0", "--top-p", "0.97", "--top-k", "128", "--min-p", "0",
                "--max-tokens", str(output), "--prefill-step-size", str(initial["prefillSize"]),
                "--decode-concurrency", "1", "--prompt-concurrency", "1", "--log-level", "WARNING",
                "--tokenizer-config", "fix_mistral_regex=true", "--tokenizer-config", "local_files_only=true",
                "--chat-template-args", json.dumps({"reasoning_effort": effort})]
    stream_server.main()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Start Kolibri from LLM Launcher.")
    main(Path(sys.argv[1]))
