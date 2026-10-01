"""v1.6 tests for GitHub issue #44: perceptual-hash duplicate detection.

A 64-bit dHash layer (PIL only — zero LLM tokens, zero extra network)
sits after the #21 pipeline: alt-text filter -> normalized-URL dedupe ->
SHA-256 dedupe -> perceptual-hash near-duplicate detection. Byte-different
look-alikes (re-sized, re-compressed, slightly cropped) are caught; genuinely
different photos are never dropped.

Threshold calibration (real photos, 64-bit dHash):
  JPEG re-save / resize            -> distance 0
  ~5% crop                        -> distance <= 4
  genuinely different photos      -> distance >= 24
_PHASH_DUP_THRESHOLD = 10 catches the variants with a wide margin
against false positives.

Run: python -m pytest tests/test_perceptual_hash_v16.py -q
"""
import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import story_library as lib  # noqa: E402
from _fake_images import fetch_for, jpeg_bytes_for, png_bytes_for  # noqa: E402
from PIL import Image  # noqa: E402


@pytest.fixture
def libdir(tmp_path, monkeypatch):
    root = tmp_path / "HindiReelStudio"
    monkeypatch.setattr(lib, "LIBRARY_ROOT", root)
    monkeypatch.setattr(lib, "STORIES_DIR", root / "stories")
    monkeypatch.setattr(lib, "PREFS_PATH", root / "prefs.json")
    return root


def _make_story(**kw):
    kw.setdefault("title", "Dog Showdown Reel")
    kw.setdefault("tone", "funny")
    kw.setdefault("hashtags", ["#DogShowdown"])
    kw.setdefault("dialogue_md", "")
    kw.setdefault("script_md", "AARAV: chubby dogs voting contest in the park")
    kw.setdefault("source_topic", "chubby dogs voting contest")
    kw.setdefault("source_headline", "Chubby dogs battle in voting contest")
    return lib.save_story(**kw)


def _resized(data: bytes, size) -> bytes:
    img = Image.open(io.BytesIO(data)).resize(size, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _cropped(data: bytes, pct: float) -> bytes:
    img = Image.open(io.BytesIO(data))
    w, h = img.size
    dx, dy = int(w * pct / 2), int(h * pct / 2)
    img = img.crop((dx, dy, w - dx, h - dy)).resize((w, h), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# dHash primitive: near-duplicates close, different photos far
# ---------------------------------------------------------------------------

def test_dhash_identical_bytes_zero_distance():
    data = png_bytes_for("seed-a")
    a = lib._image_dhash(data, "https://img.example/a.jpg")
    b = lib._image_dhash(data, "https://img.example/b.jpg")
    assert lib._hamming_distance(a, b) == 0


def test_dhash_jpeg_recompress_within_threshold():
    base = png_bytes_for("seed-a")
    a = lib._image_dhash(base, "u1")
    b = lib._image_dhash(jpeg_bytes_for("seed-a", quality=60), "u2")
    assert lib._hamming_distance(a, b) <= lib._PHASH_DUP_THRESHOLD


def test_dhash_resize_within_threshold():
    base = png_bytes_for("seed-a")
    a = lib._image_dhash(base, "u1")
    b = lib._image_dhash(_resized(base, (80, 60)), "u2")
    assert lib._hamming_distance(a, b) <= lib._PHASH_DUP_THRESHOLD


def test_dhash_slight_crop_within_threshold():
    base = png_bytes_for("seed-a")
    a = lib._image_dhash(base, "u1")
    b = lib._image_dhash(_cropped(base, 0.05), "u2")
    assert lib._hamming_distance(a, b) <= lib._PHASH_DUP_THRESHOLD


def test_dhash_distinct_images_above_threshold():
    hashes = [lib._image_dhash(png_bytes_for(f"photo-{i}"), f"u{i}")
              for i in range(8)]
    for i in range(len(hashes)):
        for j in range(i + 1, len(hashes)):
            assert lib._hamming_distance(hashes[i], hashes[j]) > \
                lib._PHASH_DUP_THRESHOLD


def test_dhash_hex_roundtrip_and_corrupt_parse():
    ph = lib._image_dhash(png_bytes_for("seed-a"), "u")
    assert lib._parse_dhash(lib._dhash_to_hex(ph)) == ph
    assert lib._parse_dhash("") is None
    assert lib._parse_dhash("not-hex!!") is None


# ---------------------------------------------------------------------------
# Fail loudly: corrupt bytes name the URL, fetch failures propagate
# ---------------------------------------------------------------------------

def test_dhash_corrupt_bytes_raise_naming_url():
    with pytest.raises(lib.ImageDedupeError,
                       match="https://img.example/broken.jpg"):
        lib._image_dhash(b"this is not an image", "https://img.example/broken.jpg")


def test_fingerprints_fetch_failure_raises_loudly(monkeypatch):
    def _boom(url, **kw):
        raise lib.ImageDedupeError(f"Image dedupe failed: could not fetch {url}")
    monkeypatch.setattr(lib, "_fetch_image_bytes", _boom)
    with pytest.raises(lib.ImageDedupeError,
                       match="https://img.example/gone.jpg"):
        lib._image_fingerprints("https://img.example/gone.jpg")


def test_merge_fails_loudly_on_undecodable_candidate(monkeypatch):
    monkeypatch.setattr(
        lib, "_fetch_image_bytes",
        lambda url, **kw: b"garbage-not-an-image")
    with pytest.raises(lib.ImageDedupeError,
                       match="https://img.example/bad.jpg"):
        lib._merge_story_images(
            [], [], [], ["https://img.example/bad.jpg"])


# ---------------------------------------------------------------------------
# _merge_story_images: the visual layer in the full pipeline
# ---------------------------------------------------------------------------

def test_merge_drops_resized_variant_of_existing(monkeypatch):
    base = png_bytes_for("hero")
    monkeypatch.setattr(
        lib, "_fetch_image_bytes",
        fetch_for({"https://img.example/hero.jpg": base,
                   "https://img.example/hero-small.jpg": _resized(base, (80, 60))}))
    merged, hashes, phashes, stats = lib._merge_story_images(
        ["https://img.example/hero.jpg"], [], [],
        ["https://img.example/hero-small.jpg"])
    # Same pixels, different bytes: SHA-256 misses it, dHash catches it.
    assert merged == ["https://img.example/hero.jpg"]
    assert stats["dup_visual"] == 1
    assert stats["added"] == 0
    assert len(phashes) == 1 and all(phashes)


def test_merge_keeps_genuinely_different_candidate(monkeypatch):
    monkeypatch.setattr(lib, "_fetch_image_bytes", fetch_for())
    merged, hashes, phashes, stats = lib._merge_story_images(
        ["https://img.example/old.jpg"], [], [],
        ["https://img.example/new.jpg"])
    assert merged == ["https://img.example/old.jpg",
                      "https://img.example/new.jpg"]
    assert stats["added"] == 1 and stats["dup_visual"] == 0
    assert len(phashes) == 2 and all(p != "" for p in phashes)


def test_merge_drops_visual_dupe_within_batch(monkeypatch):
    base = png_bytes_for("hero")
    monkeypatch.setattr(
        lib, "_fetch_image_bytes",
        fetch_for({"https://img.example/a.jpg": base,
                   "https://img.example/b.jpg": jpeg_bytes_for("hero", quality=55)}))
    merged, hashes, phashes, stats = lib._merge_story_images(
        [], [], [],
        ["https://img.example/a.jpg", "https://img.example/b.jpg"])
    assert merged == ["https://img.example/a.jpg"]
    assert stats["added"] == 1 and stats["dup_visual"] == 1


def test_merge_sha_dupe_counted_as_content_not_visual(monkeypatch):
    # Pipeline order: an identical byte match is dup_content; the visual
    # layer never even sees it.
    data = png_bytes_for("same")
    monkeypatch.setattr(
        lib, "_fetch_image_bytes",
        fetch_for({"https://img.example/a.jpg": data,
                   "https://img.example/b.jpg": data}))
    _, _, _, stats = lib._merge_story_images(
        [], [], [],
        ["https://img.example/a.jpg", "https://img.example/b.jpg"])
    assert stats["dup_content"] == 1 and stats["dup_visual"] == 0


def test_merge_collapses_existing_visual_dupes(monkeypatch):
    base = png_bytes_for("hero")
    monkeypatch.setattr(
        lib, "_fetch_image_bytes",
        fetch_for({"https://img.example/a.jpg": base,
                   "https://img.example/b.jpg": _resized(base, (80, 60)),
                   "https://img.example/c.jpg": png_bytes_for("fresh")}))
    merged, hashes, phashes, stats = lib._merge_story_images(
        ["https://img.example/a.jpg", "https://img.example/b.jpg"], [], [],
        ["https://img.example/c.jpg"])
    assert merged == ["https://img.example/a.jpg",
                      "https://img.example/c.jpg"]
    assert stats["removed_existing_dupes"] == 1
    assert stats["added"] == 1


def test_threshold_boundary_exact(monkeypatch):
    # Controlled dHashes: distance exactly at the threshold drops, one bit
    # over keeps. Proves the boundary is inclusive and conservative.
    monkeypatch.setattr(lib, "_fetch_image_bytes", fetch_for())
    base_ph = 0
    monkeypatch.setattr(lib, "_image_dhash",
                        lambda data, url: {
                            "https://img.example/kept.jpg": base_ph,
                            "https://img.example/at.jpg":
                                base_ph ^ ((1 << lib._PHASH_DUP_THRESHOLD) - 1),
                            "https://img.example/over.jpg":
                                base_ph ^ ((1 << (lib._PHASH_DUP_THRESHOLD + 1)) - 1),
                        }[url])
    merged, _, _, stats = lib._merge_story_images(
        ["https://img.example/kept.jpg"], [""], [""],
        ["https://img.example/at.jpg", "https://img.example/over.jpg"])
    assert merged == ["https://img.example/kept.jpg",
                      "https://img.example/over.jpg"]
    assert stats["dup_visual"] == 1 and stats["added"] == 1


def test_merge_backfills_missing_phash_with_one_fetch(monkeypatch):
    calls = []

    def _fetch(url, **kw):
        calls.append(url)
        return png_bytes_for(url)

    monkeypatch.setattr(lib, "_fetch_image_bytes", _fetch)
    merged, hashes, phashes, stats = lib._merge_story_images(
        ["https://img.example/old.jpg"], ["0" * 64], [],
        ["https://img.example/new.jpg"])
    # Existing entry had a SHA-256 but no dHash: exactly one fetch fills it.
    assert calls.count("https://img.example/old.jpg") == 1
    assert len(phashes) == 2 and all(phashes)
    assert stats["added"] == 1


# ---------------------------------------------------------------------------
# Persistence: image_phashes rides alongside image_hashes
# ---------------------------------------------------------------------------

def test_phashes_persisted_and_aligned(libdir, monkeypatch):
    sid = _make_story(image_urls=[])
    monkeypatch.setattr(lib, "_fetch_images_for_story",
                        lambda story, topic, **k: ["https://img.example/a.jpg"])
    monkeypatch.setattr(lib, "_fetch_image_bytes", fetch_for())
    changed, _ = lib.refresh_images(sid, "chubby dogs voting contest")
    assert changed is True
    meta = lib.load_story(sid)["meta"]
    assert len(meta["image_urls"]) == 1
    assert len(meta["image_hashes"]) == 1
    assert len(meta["image_phashes"]) == 1
    assert meta["image_phashes"][0] != ""
    # A second refresh reuses the stored phash: no refetch of existing.
    seen = []
    monkeypatch.setattr(
        lib, "_fetch_image_bytes",
        lambda url, **kw: seen.append(url) or png_bytes_for(url))
    monkeypatch.setattr(lib, "_fetch_images_for_story",
                        lambda story, topic, **k: ["https://img.example/b.jpg"])
    lib.refresh_images(sid, "chubby dogs voting contest")
    assert "https://img.example/a.jpg" not in seen


def test_load_migrates_legacy_story_without_phashes(libdir, monkeypatch):
    # Pre-#44 stories have no image_phashes key: load aligns it purely,
    # with no network.
    sid = _make_story(image_urls=["https://img.example/a.jpg"])

    def _boom(url, **kw):
        raise AssertionError("load migration must not fetch")
    monkeypatch.setattr(lib, "_fetch_image_bytes", _boom)
    meta = lib.load_story(sid)["meta"]
    assert meta["image_urls"] == ["https://img.example/a.jpg"]
    assert meta["image_phashes"] == [""]
    assert meta["image_hashes"] == [""]


def test_update_fetched_image_url_invalidates_phash(libdir):
    sid = _make_story(image_urls=["https://img.example/a.jpg"])
    lib.update_story_fields(sid, image_hashes=["0" * 64],
                            image_phashes=["f" * 16])
    assert lib.update_fetched_image_url(sid, 0, "https://img.example/z.jpg")
    meta = lib.load_story(sid)["meta"]
    assert meta["image_phashes"] == [""]


def test_remove_fetched_image_drops_phash(libdir):
    sid = _make_story(image_urls=["https://img.example/a.jpg",
                                  "https://img.example/b.jpg"])
    lib.update_story_fields(sid, image_hashes=["0" * 64, "1" * 64],
                            image_phashes=["a" * 16, "b" * 16])
    assert lib.remove_fetched_image(sid, "https://img.example/a.jpg") is True
    meta = lib.load_story(sid)["meta"]
    assert meta["image_urls"] == ["https://img.example/b.jpg"]
    assert meta["image_hashes"] == ["1" * 64]
    assert meta["image_phashes"] == ["b" * 16]
