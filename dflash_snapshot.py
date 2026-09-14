"""Keep native DFlash features chunked until its snapshot trim policy runs."""
from functools import wraps
import logging


def install_chunked_snapshot_features(store_type, chunks_type, *, versions):
    if store_type.__dict__.get('_launcher_chunked_snapshot_installed'):
        return
    if (versions != ('0.6.4', '0.1.10+omlx.7')
            or not callable(getattr(store_type, 'generation_snapshot_hidden', None))
            or not {'_prefill_hidden_for_snapshot', '_generation_chunks'} <=
                set(getattr(store_type, '__dataclass_fields__', {}))
            or not {'total_len', 'chunks', 'spans'} <=
                set(getattr(chunks_type, '__dataclass_fields__', {}))):
        raise RuntimeError('The audited DFlash snapshot feature interface changed.')
    original = store_type.generation_snapshot_hidden

    @wraps(original)
    def generation_snapshot_hidden(store):
        prefill = store._prefill_hidden_for_snapshot
        generated = store._generation_chunks
        if prefill is None or not generated:
            return None
        if isinstance(prefill, chunks_type):
            chunks, spans = list(prefill.chunks), list(prefill.spans)
            end = int(prefill.total_len)
        else:
            end = int(prefill.shape[1])
            chunks, spans = [prefill], [(0, end)]
        # Native snapshot construction already accepts these spans, validates
        # coverage, and joins only the sink/tail/full-context range it needs.
        # Do not concatenate the entire prompt before that policy can run.
        for chunk in generated:
            next_end = end + int(chunk.shape[1])
            chunks.append(chunk)
            spans.append((end, next_end))
            end = next_end
        return chunks_type(total_len=end, chunks=tuple(chunks), spans=tuple(spans))

    store_type.generation_snapshot_hidden = generation_snapshot_hidden
    store_type._launcher_chunked_snapshot_installed = True
    logging.getLogger(__name__).info('DFlash snapshot features remain chunked until native trimming')


def install_chunked_prefill_features(store_type, chunks_type, mx, *, versions):
    """Build prefill features in chunks instead of allocating the prompt up front.

    Preserve native zero-filled gaps. Full-attention eligibility is still checked
    against the original snapshot by spec_epoch before hydration is reached.
    """
    if store_type.__dict__.get('_launcher_chunked_prefill_installed'):
        return
    if (versions != ('0.6.4', '0.1.10+omlx.7')
            or not all(callable(getattr(store_type, name, None)) for name in
                       ('hydrate_from_snapshot', 'write_prompt_slice', '_project'))
            or not {'prompt_len', '_current_hidden'} <=
                set(getattr(store_type, '__dataclass_fields__', {}))
            or not {'total_len', 'chunks', 'spans'} <=
                set(getattr(chunks_type, '__dataclass_fields__', {}))):
        raise RuntimeError('The audited DFlash prefill feature interface changed.')
    original_hydrate = store_type.hydrate_from_snapshot
    original_write = store_type.write_prompt_slice

    def empty_hidden(prompt, ref):
        # broadcast_to keeps zeros scalar-backed even after evaluation. Unlike
        # sparse holes, explicit zero spans preserve native prefix_view values.
        zeros = mx.broadcast_to(mx.array(0, dtype=ref.dtype),
                                (int(ref.shape[0]), prompt, int(ref.shape[-1])))
        return chunks_type(prompt, (zeros,), ((0, prompt),))

    def replace_span(hidden, start, end, features):
        chunks, spans = [], []
        inserted = False
        for chunk, (left, right) in zip(hidden.chunks, hidden.spans):
            if right <= start:
                chunks.append(chunk)
                spans.append((left, right))
                continue
            if left < start:
                chunks.append(chunk[:, :start-left, :])
                spans.append((left, start))
            if not inserted:
                chunks.append(features)
                spans.append((start, end))
                inserted = True
            if right > end:
                chunks.append(chunk[:, max(end-left, 0):, :])
                spans.append((max(left, end), right))
        return chunks_type(hidden.total_len, tuple(chunks), tuple(spans))

    @wraps(original_hydrate)
    def hydrate_from_snapshot(store, prefix_snapshot, *, snap_prefix_len):
        store._launcher_chunked_prefill_active = False
        prefix, prompt = int(snap_prefix_len), int(store.prompt_len)
        if not 0 < prefix < prompt:
            return original_hydrate(store, prefix_snapshot, snap_prefix_len=snap_prefix_len)
        cached = prefix_snapshot.target_hidden_chunks
        spans = prefix_snapshot.target_hidden_chunk_spans
        if not cached:
            return original_hydrate(store, prefix_snapshot, snap_prefix_len=snap_prefix_len)
        ref = cached[0]
        hidden = empty_hidden(prompt, ref)
        for chunk, (start, end) in zip(cached, spans):
            start, end = int(start), min(int(end), prefix, prompt)
            if end <= start:
                continue
            features = mx.broadcast_to(chunk[:, :end-start, :].astype(ref.dtype),
                                       (int(ref.shape[0]), end-start, int(ref.shape[-1])))
            hidden = replace_span(hidden, start, end, features)
        mx.eval(*hidden.chunks)
        store._current_hidden = hidden
        store._launcher_chunked_prefill_active = True
        return hidden

    @wraps(original_write)
    def write_prompt_slice(store, *, start, end, features):
        hidden = store._current_hidden
        start, end = int(start), int(end)
        cold = hidden is None and 0 <= start < end <= int(store.prompt_len)
        chunked = (getattr(store, '_launcher_chunked_prefill_active', False)
                   and isinstance(hidden, chunks_type)
                   and 0 <= start < end <= int(hidden.total_len))
        if not (cold or chunked):
            return original_write(store, start=start, end=end, features=features)
        features = store._project(features)
        if cold:
            hidden = empty_hidden(int(store.prompt_len), features)
        features = mx.broadcast_to(features.astype(hidden.dtype),
                                   (hidden.shape[0], end-start, hidden.shape[-1]))
        mx.eval(features)
        store._current_hidden = replace_span(hidden, start, end, features)
        store._launcher_chunked_prefill_active = True
        return store._current_hidden

    store_type.hydrate_from_snapshot = hydrate_from_snapshot
    store_type.write_prompt_slice = write_prompt_slice
    store_type._launcher_chunked_prefill_installed = True
    logging.getLogger(__name__).info('DFlash prefill grows feature chunks and reuses cached spans')
