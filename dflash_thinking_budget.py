"""Request-local reasoning budgets for the audited DFlash token sampler.

The native patch calls this before target sampling, never on decoded text.
Draft proposals keep their original distribution; rejection sampling compares
them with the constrained target distribution. Rejected candidate histories
are rolled back together with the upstream processor's state.
"""
from functools import partial, wraps
from contextlib import aclosing
import inspect
import json


class DFlashThinkingBudget:
    def __init__(self, processor, prompt_tokens):
        self.processor = processor
        self.history = list(prompt_tokens)
        self.prompt_len = len(self.history)
        self._first = True
        self._rows = None

    def process_first_logits(self, logits):
        if not self._first or self._rows is not None:
            raise RuntimeError("DFlash budget first-token processing was repeated.")
        self._first = False
        return self.processor(self.history, logits)

    def process_block(self, logits, generated_tokens, candidate_tokens):
        if self._first or self._rows is not None:
            raise RuntimeError("DFlash budget transaction is out of order.")
        if self.history[self.prompt_len:] != list(generated_tokens):
            raise RuntimeError("DFlash budget history differs from committed tokens.")
        if len(candidate_tokens) != int(logits.shape[-2]):
            raise RuntimeError("DFlash budget candidate/logit row mismatch.")
        import mlx.core as mx
        self._base = len(self.history)
        self._rows = []
        processed = []
        changed = False
        for index, token in enumerate(candidate_tokens):
            self.history.append(int(token))
            row = logits[:, index:index + 1, :]
            result = self.processor(self.history, row)
            changed = changed or result is not row
            processed.append(result)
            self._rows.append(self.processor.snapshot_state())
        return mx.concatenate(processed, axis=1) if changed else logits

    def commit(self, accepted_draft_tokens):
        row = int(accepted_draft_tokens)
        if self._rows is None or not 0 <= row < len(self._rows):
            raise RuntimeError("DFlash budget acceptance row is invalid.")
        # Row a predicts the next staged token, after the first token and a
        # accepted draft tokens. Its processor state is the only surviving one.
        self.processor.restore_state(self._rows[row])
        del self.history[self._base + row + 1:]
        self._rows = None

    def process_next_logits(self, logits, generated_tokens):
        """Native AR fallback: each target token uses the same causal policy."""
        if self._first or self._rows is not None:
            raise RuntimeError("DFlash budget fallback is out of order.")
        count = len(self.history) - self.prompt_len
        if len(generated_tokens) != count + 1:
            raise RuntimeError("DFlash budget fallback skipped a committed token.")
        self.history.append(int(generated_tokens[-1]))
        return self.processor(self.history, logits)


def _token_piece_reader(tokenizer):
    byte_decoder = getattr(tokenizer, "byte_decoder", None)
    if not isinstance(byte_decoder, dict):
        # Qwen's fast tokenizer stores ByteLevel in its Rust decoder rather
        # than exposing the slow tokenizer's byte_decoder mapping.
        backend = getattr(tokenizer, "backend_tokenizer", None)
        decoder = getattr(backend, "decoder", None)
        try:
            is_byte_level = json.loads(decoder.__getstate__()).get("type") == "ByteLevel"
        except (AttributeError, TypeError, ValueError):
            is_byte_level = False
        if is_byte_level:
            from mlx_lm.tokenizer_utils import BPEStreamingDetokenizer
            BPEStreamingDetokenizer.make_byte_decoder()
            byte_decoder = BPEStreamingDetokenizer._byte_decoder

    def read(token_id):
        piece = tokenizer.convert_ids_to_tokens(token_id)
        if isinstance(byte_decoder, dict) and isinstance(piece, str):
            try:
                return bytes(byte_decoder[ch] for ch in piece)
            except KeyError:
                pass  # Special markers are complete strings, not byte pieces.
        return piece

    return read


def create_budget(engine, budget, prompt_tokens):
    """Called once on the executor, after the tokenizer and prompt exist."""
    tokenizer = getattr(engine, '_executor_tokenizer', None) or engine._tokenizer_obj

    def encode(text):
        ids = list(tokenizer.encode(text, add_special_tokens=False))
        if not ids:
            raise ValueError("The thinking close pattern could not be tokenized.")
        return ids

    start_ids = encode("<think>")
    close_ids = encode("</think>")
    if len(start_ids) != 1 or len(close_ids) != 1:
        raise ValueError("DFlash thinking budgets require single-token native think markers.")
    start = start_ids[0]
    tail = list(prompt_tokens[-3:])
    if start not in tail or close_ids[0] in tail[tail.index(start) + 1:]:
        return None  # Disabled thinking / an ordinary non-thinking prompt.
    if getattr(engine, "_output_parser_factory", None) is not None:
        raise ValueError("DFlash thinking budgets require the native <think> template.")
    from omlx.api.thinking import ThinkingBudgetProcessor
    processor = ThinkingBudgetProcessor(
        think_end_token_ids=close_ids, budget=budget,
        think_start_token_id=start, leading_token_ids=encode("\n"),
        trailing_token_ids=encode("\n\n"), token_to_piece=_token_piece_reader(tokenizer),
    )
    return DFlashThinkingBudget(processor, prompt_tokens)


def install_dflash_thinking_budget(engine_type):
    if engine_type.__dict__.get("_launcher_thinking_budget_installed"):
        return
    parameters = inspect.signature(engine_type._stream_dflash_events).parameters
    if "logits_processor_factory" not in parameters:
        raise RuntimeError("The audited DFlash thinking-budget runtime patch is missing.")
    original_generate = engine_type.generate
    original_stream = engine_type.stream_generate

    def request_options(engine, kwargs):
        options = dict(kwargs)
        budget = options.get("thinking_budget")
        if budget is not None:
            if isinstance(budget, bool) or not isinstance(budget, int) or budget < 1:
                raise ValueError("DFlash thinking_budget must be a positive integer.")
            options["logits_processor_factory"] = partial(create_budget, engine, budget)
        return options

    @wraps(original_generate)
    async def generate(engine, *args, **kwargs):
        return await original_generate(engine, *args, **request_options(engine, kwargs))

    @wraps(original_stream)
    async def stream_generate(engine, *args, **kwargs):
        async with aclosing(original_stream(engine, *args, **request_options(engine, kwargs))) as stream:
            async for result in stream:
                yield result

    engine_type.generate = generate
    engine_type.stream_generate = stream_generate
    engine_type.preserve_native_thinking = True
    engine_type._launcher_thinking_budget_installed = True
