"""Shared, verified Flash-Next image projector for the installed GGUF routes.

The installation receipt binds the projector to exact existing model files.
Capability checks are read-only and never fetch a model or enable another
checkpoint merely because its name contains 'Flash'.
"""
from functools import lru_cache
import hashlib
import json
from pathlib import Path

ROOT = Path.home() / 'Library/Application Support/LLM Launcher/vision/qwen3.8-flash-next'
RECEIPT = ROOT / 'vision.json'
PROJECTOR_NAME = 'mmproj-Qwen3.8-Flash-Next-BF16.gguf'
PROJECTOR_BYTES = 907_543_008
PROJECTOR_SHA256 = 'b1a82259702816a5330d7bd7607cd9676b11780e79ff7348c21103ff3ce49bd0'
MODEL_ID = 'qwen3.8-flash-next'
# The upstream Mac reader measured about 1.18 GB; reserve 1.5 GiB for it.
MEMORY_RESERVE_BYTES = 3 * 1024**3 // 2


def file_identity(path):
    path = Path(path).resolve(strict=True)
    s = path.stat()
    return {'path': str(path), 'size': s.st_size, 'device': s.st_dev,
            'inode': s.st_ino, 'mtime_ns': s.st_mtime_ns, 'ctime_ns': s.st_ctime_ns}


@lru_cache(maxsize=8)
def _verified_projector(path, identity):
    before = file_identity(path)
    if tuple(before.values()) != identity or before['size'] != PROJECTOR_BYTES:
        return False
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest() == PROJECTOR_SHA256 and file_identity(path) == before


def inspect_model(model_path):
    """Return image capability only for this complete, receipt-bound model."""
    try:
        if RECEIPT.stat().st_size > 64 * 1024:
            return None
        receipt = json.loads(RECEIPT.read_text())
        if receipt.get('schemaVersion') != 1 or receipt.get('model') != MODEL_ID:
            return None
        aliases = {str(Path(p).resolve(strict=True)) for p in receipt['modelPaths']}
        if str(Path(model_path).resolve(strict=True)) not in aliases:
            return None
        sources = receipt['sourceFiles']
        if not 1 <= len(sources) <= 64 or any(file_identity(x['path']) != x for x in sources):
            return None
        projector = file_identity(receipt['projector']['path'])
        if projector != receipt['projector'] or not _verified_projector(projector['path'], tuple(projector.values())):
            return None
        # LM Studio discovers a projector beside the GGUF, while Strata and
        # Splash get the same path explicitly. Require that published link.
        linked = Path(sources[0]['path']).parent / PROJECTOR_NAME
        if linked.resolve(strict=True) != Path(projector['path']):
            return None
        identity = hashlib.sha256(json.dumps([sources, projector], sort_keys=True).encode()).hexdigest()
        return {'ready': True, 'projector': projector['path'], 'sha256': PROJECTOR_SHA256,
                'identity': identity, 'bytes': PROJECTOR_BYTES, 'memoryReserveBytes': MEMORY_RESERVE_BYTES,
                'input': ['text', 'image'], 'sourceFirst': sources[0]['path']}
    except (OSError, ValueError, KeyError, TypeError, RuntimeError):
        return None
