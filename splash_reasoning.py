"""Launcher-owned thinking budget for Splash's native speculative decoder.

The closing token is sampled by the engine and enters its real KV history.
This is not an SSE rewrite, cancellation, task replay, or second generation.
The existing tool/JSON grammar remains in force after the thinking phase.
"""
from __future__ import annotations

import functools
import hashlib
import pathlib
import sys
import threading


THINK_END = 248069
VOCABULARY = 248320
EOS = (248044, 248046)
WORDS = VOCABULARY // 32
ROW_BYTES = WORDS * 4
CLOSURE_RESERVE = 8
BUDGETS = {"none": 0, "off": 0, "low": 1024, "medium": 4096, "xhigh": 32768}

# This adapter depends on the committed-token vs simulated-token contract.
# Refuse unqualified frontend changes rather than silently losing the cap.
QUALIFIED_SOURCES = {
    "frontend.py": "6b35c8014055ce675afc0f518c4f1d7f81b7b8ead9bc21d16ca181aeb8e29a9b",
    "backend.py": "be109a1c8d4f210831423da1c4b9c5966a49f10c3f962c14c5c601b5204d8d61",
    "constraints.py": "1475d94101a4153261593c934e5a0bd8e1b20554f9c8f5b513a50f9a2bbc60c9",
    "protocol.py": "c02233ba5ccd79ac2008e618f5b371cc656e354fa77c620621edc4f8e203de1c",
    "tool_schema.py": "965112214b7f9156667dc7eb820d2c0fcfd6321cfd3dfb7facd6a3f6a3a1b8bb",
}
QUALIFIED_MODERN_SOURCES = {
    "frontend.py": "d9e4aafef5b95d6524a57ca2ff22fc5ec153a7fcd8e118015d93d3bb8ba4f97f",
    "backend.py": "50f85a5bc92ecf6dce606e68fc8aa7c6ad5526db1adfb170004ce605128ae5a5",
    "constraints.py": "620ad9eb564c476d02d0962eb3b22fcdcb708bb6879b3b4e911a345c2a564f90",
    "protocol.py": "a1e0716a05a9b151d323a4c4b4b7aa1e5b0e5228986e6277658e172b2786582f",
    "tool_schema.py": "92f33bd6669b3f65214e09a714bd9cdf8c6572212821c6482b82daa77e0905b9",
}


def thinking_budget(effort, output_limit):
    """Keep roughly half the response available for the answer/tool call."""
    if effort in (None, "auto"):
        effort = "xhigh"  # Qwen3.8's actual template default.
    effort = {"minimal": "low", "high": "xhigh", "max": "xhigh"}.get(effort, effort)
    if effort not in BUDGETS:
        raise ValueError("Unsupported Splash reasoning effort")
    return min(BUDGETS[effort], max(0, output_limit // 2))


def verify_frontend(directory):
    directory = pathlib.Path(directory)
    modern = (directory / "__init__.py").is_file()
    sources = QUALIFIED_MODERN_SOURCES if modern else QUALIFIED_SOURCES
    for name, expected in sources.items():
        if hashlib.sha256((pathlib.Path(directory) / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError(
                f"Splash {name} changed: its thinking-budget adapter needs qualification before launch."
            )


class ThinkingConstraint:
    """Intersect native grammar masks with a per-request phase budget.

    Splash asks for masks BEFORE and AFTER each speculative simulation token.
    Simulations never commit state; accepted batches advance the real counter.
    Consequently a seven-token draft cannot overrun the boundary and a
    rejected draft cannot use up the budget or close the real thinking phase.
    """

    def __init__(self, inner, budget, on_close=lambda *_: None):
        self.inner = inner
        self.budget = budget
        # A token boundary can split UTF-8. Begin closing slightly before the
        # ceiling so llguidance can finish that character without exceeding it.
        self.close_after = max(0, budget - CLOSURE_RESERVE)
        self.tokens = 0
        self.thinking = True
        self.on_close = on_close
        self._lock = threading.Lock()
        self._committed = []

    def commit(self, token_ids):
        # Splash 1.2 delivers accepted batches on its reader thread. Apply
        # them on the mask thread, exactly as the native grammar does.
        with self._lock:
            self._committed.append(tuple(token_ids))

    def _consume_committed(self):
        with self._lock:
            batches, self._committed = self._committed, []
        for tokens in batches:
            self.consume(tokens)

    def finish(self):
        self._consume_committed()
        if self.inner is not None and hasattr(self.inner, "finish"):
            self.inner.finish()

    def masks(self, simulation_tokens):
        self._consume_committed()
        if len(simulation_tokens) >= 9:
            raise ValueError("Too many Splash simulation tokens")
        payload = (self.inner.masks(simulation_tokens) if self.inner is not None
                   else b"\xff" * (ROW_BYTES * (len(simulation_tokens) + 1)))
        if not self.thinking:
            return payload
        if self.inner is not None and self.tokens + len(simulation_tokens) < self.close_after:
            return payload
        data = bytearray(payload)
        if len(data) != ROW_BYTES * (len(simulation_tokens) + 1):
            raise ValueError("Unexpected Splash token mask geometry")
        words = memoryview(data).cast("I")
        count, thinking = self.tokens, self.thinking
        for row in range(len(simulation_tokens) + 1):
            offset = row * WORDS
            if thinking:
                if count >= self.close_after:
                    # Never bypass the grammar or split an unfinished UTF-8
                    # character. Close at the first legal boundary in reserve.
                    can_close = words[offset + THINK_END // 32] & (1 << (THINK_END % 32))
                    if not can_close and count >= self.budget:
                        raise ValueError("Splash grammar cannot close thinking at its budget")
                    if can_close:
                        data[row * ROW_BYTES:(row + 1) * ROW_BYTES] = b"\x00" * ROW_BYTES
                        words[offset + THINK_END // 32] = 1 << (THINK_END % 32)
                elif self.inner is None:
                    # A plain-text request must close thinking before EOS too.
                    for token in EOS:
                        words[offset + token // 32] &= ~(1 << (token % 32))
            if row < len(simulation_tokens) and thinking:
                if simulation_tokens[row] == THINK_END:
                    thinking = False
                else:
                    count += 1
        return bytes(data)

    def consume(self, token_ids):
        if self.inner is not None:
            if hasattr(self.inner, "commit"):
                self.inner.commit(token_ids)
            else:
                self.inner.consume(token_ids)
        for token in token_ids:
            if not self.thinking:
                break
            if token == THINK_END:
                self.thinking = False
                if self.tokens >= self.close_after:
                    self.on_close(self.tokens)
            else:
                if self.tokens >= self.budget:
                    raise ValueError("Splash generated past the enforced thinking budget")
                self.tokens += 1


def install_budget(frontend_class, bad_request=ValueError):
    original = frontend_class._prepare

    @functools.wraps(original)
    def prepare(self, body, *args, **kwargs):
        # A caller may ask for less thinking, but cannot remove the launcher
        # ceiling. Zero still produces a real closing token if thinking is on.
        requested = body.get("thinking_budget_tokens")
        if requested is not None and (type(requested) is not int or requested < 0):
            raise bad_request("thinking_budget_tokens must be a non-negative integer")
        prepared = original(self, body, *args, **kwargs)
        job = prepared[0] if isinstance(prepared, tuple) else prepared
        thinking = prepared[1] if isinstance(prepared, tuple) else job.thinking
        if thinking:
            budget = thinking_budget(body.get("reasoning_effort"), job.max_new_tokens)
            if requested is not None:
                budget = min(budget, requested)
            def closed(tokens):
                print(f"LLM Launcher Splash: thinking budget reached ({tokens} tokens); "
                      "continuing to answer/tools in the same request.", file=sys.stderr, flush=True)
            job.constraint = ThinkingConstraint(job.constraint, budget, closed)
        return prepared

    frontend_class._prepare = prepare


def main():
    server_path = pathlib.Path(sys.argv[1]).resolve()
    verify_frontend(server_path.parent)
    if (server_path.parent / "__init__.py").is_file():
        sys.path.insert(0, str(server_path.parent.parent))
        from server import frontend, server
        from server.errors import APIError
    else:
        sys.path.insert(0, str(server_path.parent))
        import frontend
        import server
        from errors import APIError
    install_budget(frontend.Frontend, lambda message: APIError(400, message))
    sys.argv = [str(server_path), *sys.argv[2:]]
    print("LLM Launcher Splash: native thinking budgets active "
          "(low 1024, medium 4096, xhigh/default 32768; at most half Max response).",
          file=sys.stderr, flush=True)
    server.main()


if __name__ == "__main__":
    main()
