"""Compare the pinned DSpine draft with greedy 27B autoregressive decoding."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import mlx.core as mx
from dflash_mlx.engine.target_qwen_gdn import QwenGdnTargetOps
from dspine_mlx.generate import DSpineGenerator, baseline_generate
from dspine_mlx.model import load_draft
from dspine_mlx.target import HeadAccess
from mlx_lm import load


class HybridTarget:
    """Adapt the existing MLX Gated DeltaNet verifier to DSpine's cache API."""

    def __init__(self, model, taps, *, speculative):
        self.model = model
        self.ops = QwenGdnTargetOps()
        self.head = HeadAccess(self.ops.text_wrapper(model).lm_head)
        self.hidden_size = self.head.hidden_size
        self.vocab_size = self.head.vocab_size
        self.taps = list(taps)
        self.capture_keys = {tap + 1 for tap in taps}
        self.speculative = speculative

    def reset(self):
        self.cache = self.ops.make_cache(
            self.model, enable_speculative_linear_cache=self.speculative
        )
        self.position = 0
        self.pending_rows = 0

    def prefill(self, prompt, capture=True):
        hidden = []
        for start in range(0, prompt.shape[1], 256):
            tokens = prompt[:, start : start + 256]
            logits, captured = self.ops.forward_with_hidden_capture(
                self.model, input_ids=tokens, cache=self.cache,
                capture_layer_ids=self.capture_keys if capture else set(),
                logits_last_only=True,
            )
            if capture:
                hidden.append(self.ops.extract_context_feature(captured, self.taps))
                mx.eval(logits, hidden[-1])
            else:
                mx.eval(logits)
            self.position += tokens.shape[1]
        return logits, mx.concatenate(hidden, axis=1) if capture else None

    def step(self, token):
        return self.model(mx.array([[token]], dtype=mx.int32), cache=self.cache)

    def verify(self, tokens):
        if self.pending_rows:
            raise RuntimeError("Previous target verification has not been committed")
        self.ops.arm_rollback(self.cache, prefix_len=self.position)
        logits, captured = self.ops.verify_block(
            target_model=self.model, verify_ids=tokens, target_cache=self.cache,
            capture_layer_ids=self.capture_keys,
        )
        self.pending_rows = tokens.shape[1]
        return logits, self.ops.extract_context_feature(captured, self.taps)

    def trim(self, rejected):
        if not 0 <= rejected < self.pending_rows:
            raise ValueError("Invalid speculative rejection count")
        retained = self.pending_rows - rejected
        self.position += retained
        self.ops.restore_after_acceptance(
            self.cache, target_len=self.position, acceptance_length=retained - 1,
            drafted_tokens=self.pending_rows - 1,
        )
        self.pending_rows = 0


def metrics(stats):
    return {
        **asdict(stats),
        "decode_tps": stats.decode_tps,
        "accepted_per_round": stats.accepted_per_round,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--draft", type=Path, required=True)
    parser.add_argument("--max-tokens", type=int, default=96, choices=range(2, 513))
    parser.add_argument("--block-size", type=int, default=8, choices=range(2, 17))
    parser.add_argument(
        "--prompt", default="Write a Python implementation of Conway's Game of Life with comments."
    )
    args = parser.parse_args()

    print("Loading 27B target", flush=True)
    model, tokenizer = load(str(args.target))
    prompt = tokenizer.apply_chat_template(
        [{"role": "user", "content": args.prompt}],
        add_generation_prompt=True, enable_thinking=False,
    )
    if not 0 < len(prompt) <= 2048:
        parser.error("Expected a prompt of 1 to 2048 tokens")
    eos = tokenizer.eos_token_ids
    baseline = HybridTarget(model, [], speculative=False)
    expected, baseline_stats = baseline_generate(
        baseline, prompt, max_tokens=args.max_tokens, stop_ids=eos
    )
    del baseline
    mx.clear_cache()
    print(json.dumps({"autoregressive": metrics(baseline_stats)}), flush=True)

    print("Loading DSpine draft and building refinement tables", flush=True)
    draft, config = load_draft(args.draft)
    draft.bind(model)
    hybrid = HybridTarget(model, config.target_layer_ids, speculative=True)
    generator = DSpineGenerator(hybrid, draft, block_size=args.block_size)
    tokens, stats = generator.generate(prompt, max_tokens=args.max_tokens, stop_ids=eos)
    print(json.dumps({
        "dspine": metrics(stats),
        "tables_seconds": generator.tables_seconds,
        "identical_tokens": tokens == expected,
    }), flush=True)
    if tokens != expected:
        for offset, (reference, actual) in enumerate(zip(expected, tokens)):
            if reference != actual:
                raise SystemExit(f"Token {offset} differs: {reference} vs {actual}")
        raise SystemExit(f"Different output lengths: {len(expected)} vs {len(tokens)}")


if __name__ == "__main__":
    main()
