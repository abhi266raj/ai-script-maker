"""Deterministic fake-but-valid image bytes for dedupe tests.

The old ``b"bytes-for-" + url`` fakes are not decodable images; since
issue #44 the dedupe pipeline perceptual-hashes every fetched image and
fails loudly on undecodable bytes. These helpers generate tiny but REAL
PNG/JPEG images, deterministic per seed, so tests keep their semantics
("distinct bytes per URL", "same bytes for mapped URLs") with honest
image data.

Run: python -m pytest tests/test_perceptual_hash_v16.py -q
"""
import hashlib
import io
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402


def png_bytes_for(seed: str, size=(160, 120)) -> bytes:
    """Deterministic valid PNG bytes, distinct per ``seed`` (overwhelmingly).

    Random-rectangle composition: distinct seeds produce visually
    different images (dHash distance well above the duplicate
    threshold); the same seed always produces identical bytes.
    """
    h = int(hashlib.sha256(str(seed).encode()).hexdigest(), 16)
    rng = random.Random(h)
    img = Image.new(
        "RGB", size,
        (rng.randrange(256), rng.randrange(256), rng.randrange(256)))
    draw = ImageDraw.Draw(img)
    for _ in range(24):
        x0, x1 = sorted((rng.randrange(size[0]), rng.randrange(size[0])))
        y0, y1 = sorted((rng.randrange(size[1]), rng.randrange(size[1])))
        draw.rectangle(
            [x0, y0, x1, y1],
            fill=(rng.randrange(256), rng.randrange(256), rng.randrange(256)))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def jpeg_bytes_for(seed: str, quality: int = 85, size=(160, 120)) -> bytes:
    """Deterministic valid JPEG bytes for ``seed`` at the given quality."""
    img = Image.open(io.BytesIO(png_bytes_for(seed, size)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def fetch_for(mapping=None, fmt: str = "png"):
    """Build a ``_fetch_image_bytes`` stub: valid image bytes per URL.

    ``mapping`` maps a URL to explicit bytes (use it to force two URLs
    to share identical — or near-duplicate — content); unmapped URLs get
    deterministic per-URL images. ``fmt`` is "png" or "jpeg".
    """
    mapping = mapping or {}

    def _fetch(url, **kw):
        if url in mapping:
            return mapping[url]
        if fmt == "jpeg":
            return jpeg_bytes_for(url)
        return png_bytes_for(url)

    return _fetch
