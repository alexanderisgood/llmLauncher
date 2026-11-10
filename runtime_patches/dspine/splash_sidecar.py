"""Run Tencent's DSpine proposer for a single local Splash connection."""

import argparse
import json
import os
import socket
import struct
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import mlx.core as mx
import mlx.nn as nn
import numpy as np
from dspine_mlx.generate import DSpineGenerator
from dspine_mlx.model import load_draft, quantize_draft
from dspine_mlx.target import HeadAccess


HEADER = struct.Struct("<4I")
RESET, APPEND, PROPOSE = 1, 2, 3
CONTEXT_LIMIT = 262144
DRAFT_WINDOW = 8192
MAX_APPEND_ROWS = 256
CONTEXT_BATCH_ROWS = 1024
ALLOCATOR_CACHE_BYTES = 512 * 1024**2
COMPACT_CACHE_BYTES = 128 * 1024**2
WIDTH, VOCAB = 5120, 248320
TAPS = (1, 16, 31, 46, 61)
ROW_BYTES = 2 * WIDTH * len(TAPS)
QUANTIZATION = {"group_size": 64, "bits": 4, "mode": "affine"}


def quantized_tensors(root, weight_map, prefix):
    for field, dtype, shape in (
        ("weight", "<u4", (VOCAB, WIDTH // 8)),
        ("scales", "<u2", (VOCAB, WIDTH // 64)),
        ("biases", "<u2", (VOCAB, WIDTH // 64)),
    ):
        name = f"{prefix}.{field}"
        path = root / Path(weight_map[name]).name
        with path.open("rb") as file:
            size = struct.unpack("<Q", file.read(8))[0]
            if size > 1024 * 1024:
                raise ValueError(f"Invalid safetensors header size for {name}")
            meta = json.loads(file.read(size))[name]
            start, end = meta["data_offsets"]
            expected_dtype = "U32" if field == "weight" else "BF16"
            length = int(np.prod(shape)) * np.dtype(dtype).itemsize
            if tuple(meta["shape"]) != shape or meta["dtype"] != expected_dtype:
                raise ValueError(f"Unexpected shape or type for {name}")
            if start < 0 or end - start != length:
                raise ValueError(f"Invalid safetensors offsets for {name}")
            if 8 + size + end > os.fstat(file.fileno()).st_size:
                raise ValueError(f"Truncated safetensors payload for {name}")
            yield field, file, dtype, shape, 8 + size + start


def load_quantized_module(root, weight_map, prefix, module):
    weights = []
    for field, file, dtype, shape, offset in quantized_tensors(root, weight_map, prefix):
        file.seek(offset)
        tensor = mx.array(np.fromfile(file, dtype=dtype, count=int(np.prod(shape))).reshape(shape))
        weights.append((field, tensor if field == "weight" else tensor.view(mx.bfloat16)))
    module.load_weights(weights)
    mx.eval(module.parameters())
    return module


class MappedEmbedding:
    """Read only the target embedding rows in the current proposal block."""

    def __init__(self, root, weight_map):
        self.fields = [
            np.memmap(file, dtype=dtype, mode="r", offset=offset, shape=shape)
            for _, file, dtype, shape, offset in quantized_tensors(
                root, weight_map, "language_model.model.embed_tokens")
        ]

    def __call__(self, ids):
        indices = np.asarray(ids)
        packed, scales, biases = (mx.array(field[indices]) for field in self.fields)
        return mx.dequantize(
            packed, scales.view(mx.bfloat16), biases.view(mx.bfloat16),
            **QUANTIZATION, dtype=mx.bfloat16,
        )


class MappedRefinementRows:
    """Keep identical BF16 table rows in reclaimable file-backed storage."""

    def __init__(self, array, scratch):
        with tempfile.TemporaryFile(dir=scratch) as backing:
            np.asarray(array.view(mx.uint16)).tofile(backing)
            self.rows = np.memmap(backing, dtype=np.uint16, mode="r", shape=array.shape)

    def __getitem__(self, indices):
        return mx.array(self.rows[np.asarray(indices)]).view(mx.bfloat16)


class Proposer:
    def __init__(self, target, draft_path, *, compact=False, scratch=None):
        config = json.loads((target / "config.json").read_text())
        text = config["text_config"]
        quantization = config["quantization"]
        if (
            text["model_type"] != "qwen3_5_text"
            or text["hidden_size"] != WIDTH
            or text["vocab_size"] != VOCAB
            or text["num_hidden_layers"] != 64
            or text["tie_word_embeddings"]
            or any(quantization.get(k) != v for k, v in QUANTIZATION.items())
        ):
            raise ValueError("Expected the Qwen3.8-27B MLX 4-bit affine checkpoint")

        weights = json.loads((target / "model.safetensors.index.json").read_text())["weight_map"]
        if compact:
            embedding = MappedEmbedding(target, weights)
        else:
            embedding = load_quantized_module(
                target, weights, "language_model.model.embed_tokens",
                nn.QuantizedEmbedding(VOCAB, WIDTH, **QUANTIZATION),
            )
        head = load_quantized_module(
            target, weights, "language_model.lm_head",
            nn.QuantizedLinear(WIDTH, VOCAB, bias=False, **QUANTIZATION),
        )
        self.draft, draft_config = load_draft(draft_path)
        if tuple(draft_config.target_layer_ids) != TAPS or draft_config.sliding_window != DRAFT_WINDOW:
            raise ValueError("Unexpected DSpine target capture layers or attention window")
        if compact:
            # Finish conversion before Splash loads the target. The proposal
            # verifier still uses the original target and INT8 target KV.
            quantize_draft(self.draft, bits=4)
            mx.eval(self.draft.parameters())
            mx.clear_cache()
        self.draft.bind(SimpleNamespace(embed_tokens=embedding))
        target_head = SimpleNamespace(
            head=HeadAccess(head), hidden_size=WIDTH, vocab_size=VOCAB,
        )
        generator = DSpineGenerator(target_head, self.draft, block_size=8)
        self.tail = generator.tail
        print(f"DSpine refinement tables ready in {generator.tables_seconds:.2f}s", flush=True)
        if compact:
            self.tail.tg = MappedRefinementRows(generator.tg, scratch)
            self.tail.tsv = MappedRefinementRows(generator.tsv, scratch)
            del generator
            mx.clear_cache()
            print("DSpine compact draft ready · Q4 backbone · file-backed BF16 refinement rows", flush=True)
        self.reset()

    def reset(self):
        self.position = self.origin = None
        self.pending = []
        self.pending_rows = 0
        self.caches = self.draft.make_cache()

    def check_append(self, position, rows):
        if (
            (self.position is not None and position != self.position)
            or not 0 <= position < CONTEXT_LIMIT
            or not 0 < rows <= min(MAX_APPEND_ROWS, CONTEXT_LIMIT - position)
        ):
            raise ValueError("Unexpected DSpine context position or length")

    def take_pending(self):
        if not self.pending:
            return None
        hidden = self.pending[0] if len(self.pending) == 1 else mx.concatenate(self.pending, axis=1)
        self.pending.clear()
        self.pending_rows = 0
        return hidden

    def append(self, position, rows, payload):
        self.check_append(position, rows)
        if self.position is None:
            # A long prompt starts at its retained suffix. RoPE still uses
            # the positions of those tokens in the complete target context.
            self.origin = position
            for cache in self.caches:
                cache.offset = position
        hidden = np.frombuffer(payload, dtype="<u2").reshape(1, rows, WIDTH * len(TAPS))
        self.pending.append(mx.array(hidden).view(mx.bfloat16))
        self.position = position + rows
        self.pending_rows += rows
        if self.pending_rows >= CONTEXT_BATCH_ROWS:
            self.draft.append_context(self.take_pending(), self.caches)
            mx.eval(*(tensor for cache in self.caches for tensor in (cache.keys, cache.values)))

    def propose(self, anchor, rows):
        if (
            anchor >= VOCAB
            or not 1 <= rows <= 8
            or self.position is None or not 0 < self.position <= CONTEXT_LIMIT - rows
        ):
            raise ValueError("Unexpected DSpine proposal position, anchor or length")
        if self.origin and self.position - self.origin < DRAFT_WINDOW - 1:
            raise ValueError("DSpine needs the complete trailing attention window")
        if rows == 1:
            return b""
        block = mx.array([[anchor] + [self.draft.mask_token_id] * (rows - 1)], dtype=mx.int32)
        self.draft.set_block_size(rows)
        output, stash = self.draft(self.take_pending(), block, self.caches)
        ids, _ = self.tail.greedy(output[0, 1:], stash, anchor)
        return np.asarray(ids, dtype="<i4").tobytes()


def serve_connection(connection, proposer):
    with connection.makefile("rb") as request:
        reset = False
        while header := request.read(HEADER.size):
            try:
                command, arg0, arg1, size = HEADER.unpack(header)
                if command == RESET and arg0 == arg1 == size == 0:
                    proposer.reset()
                    reset = True
                    reply = b""
                elif not reset:
                    raise ValueError("DSpine request requires RESET")
                elif command == APPEND and size == ROW_BYTES * arg1:
                    proposer.check_append(arg0, arg1)
                    payload = request.read(size)
                    if len(payload) != size:
                        raise ValueError("Truncated DSpine append payload")
                    proposer.append(arg0, arg1, payload)
                    reply = b""
                elif command == PROPOSE and size == 0:
                    reply = proposer.propose(arg0, arg1)
                else:
                    raise ValueError("Invalid DSpine request frame")
            except (ValueError, RuntimeError, struct.error) as error:
                reply = str(error).encode("utf-8")[:1024]
                connection.sendall(HEADER.pack(1, 0, 0, len(reply)) + reply)
                return
            connection.sendall(HEADER.pack(0, 0, 0, len(reply)) + reply)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--draft", type=Path, required=True)
    parser.add_argument("--parent-pid", type=int)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    if not args.socket.is_absolute() or args.socket.parent.stat().st_mode & 0o077:
        parser.error("Use an absolute socket path in a private directory")
    if args.parent_pid is not None:
        def watch_parent():
            while os.getppid() == args.parent_pid:
                time.sleep(0.25)
            os._exit(0)

        threading.Thread(target=watch_parent, daemon=True).start()
    mx.set_cache_limit(COMPACT_CACHE_BYTES if args.compact else ALLOCATOR_CACHE_BYTES)
    proposer = Proposer(args.target, args.draft, compact=args.compact, scratch=args.socket.parent)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(args.socket))
        try:
            server.listen(1)
            args.socket.chmod(0o600)
            print("DSpine Splash sidecar ready", flush=True)
            while True:
                connection, _ = server.accept()
                with connection:
                    connection.settimeout(120)
                    try:
                        serve_connection(connection, proposer)
                    except (ConnectionError, TimeoutError) as error:
                        print(f"DSpine connection ended: {error}", flush=True)
                    finally:
                        proposer.reset()
        finally:
            args.socket.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
