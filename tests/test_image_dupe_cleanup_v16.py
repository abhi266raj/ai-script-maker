"""v1.6 tests for GitHub issue #57: stored duplicate images must be
cleaned even when a refresh finds nothing new.

Holes fixed:
- ``_merge_story_images`` returned early when no fresh candidates
  survived, skipping the hash backfill + existing-entries collapse.
  The backfill + collapse now always runs.
- ``refresh_images`` returned early when the fetch found nothing; it now
  always merges, writes back cleaned/backfilled state, and reports
  removed stored duplicates in the outcome note.
- ``save_story`` stays network-free (URL-only dedupe); the next refresh
  (or post-save enrichment) cleans whatever that let through.

Run: python -m pytest tests/test_image_dupe_cleanup_v16.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import story_library as lib  # noqa: E402
from _fake_images import fetch_for, jpeg_bytes_for, png_bytes_for  # noqa: E402


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


# ---------------------------------------------------------------------------
# _merge_story_images: existing-entries backfill + collapse always runs
# ---------------------------------------------------------------------------

def test_merge_empty_candidates_still_collapses_stored_byte_dupes(monkeypatch):
    # The issue #57 hole: no fresh candidates used to skip the collapse.
    _same = png_bytes_for("same-image")
    monkeypatch.setattr(
        lib, "_fetch_image_bytes",
        fetch_for({"https://img.example/a.jpg": _same,
                   "https://cdn.example/b.jpg": _same}))
    merged, hashes, phashes, stats = lib._merge_story_images(
        ["https://img.example/a.jpg", "https://cdn.example/b.jpg"],
        [], [], [])
    assert merged == ["https://img.example/a.jpg"]  # first wins
    assert len(hashes) == 1 and all(hashes)
    assert len(phashes) == 1 and all(phashes)
    assert stats["removed_existing_dupes"] == 1
    assert stats["added"] == 0


def test_merge_empty_candidates_still_collapses_stored_visual_dupes(monkeypatch):
    # Same photo, resized: different bytes, dHash within the threshold.
    _big = png_bytes_for("vis-photo", size=(320, 240))
    _small = png_bytes_for("vis-photo", size=(160, 120))
    monkeypatch.setattr(
        lib, "_fetch_image_bytes",
        fetch_for({"https://img.example/big.jpg": _big,
                   "https://cdn.example/small.jpg": _small}))
    merged, hashes, phashes, stats = lib._merge_story_images(
        ["https://img.example/big.jpg", "https://cdn.example/small.jpg"],
        [], [], [])
    assert merged == ["https://img.example/big.jpg"]  # first wins
    assert stats["removed_existing_dupes"] == 1


def test_merge_empty_candidates_backfills_missing_hashes(monkeypatch):
    _img = png_bytes_for("lone-image")
    monkeypatch.setattr(
        lib, "_fetch_image_bytes",
        fetch_for({"https://img.example/lone.jpg": _img}))
    merged, hashes, phashes, stats = lib._merge_story_images(
        ["https://img.example/lone.jpg"], [], [], [])
    assert merged == ["https://img.example/lone.jpg"]
    assert len(hashes) == 1 and all(hashes)
    assert len(phashes) == 1 and all(phashes)
    assert stats["removed_existing_dupes"] == 0


def test_merge_backfill_failure_raises_loudly_not_silently_skipped(monkeypatch):
    def _boom(url, **kw):
        raise lib.ImageDedupeError(
            f"Image dedupe failed: could not fetch {url} (connection refused)")
    monkeypatch.setattr(lib, "_fetch_image_bytes", _boom)
    with pytest.raises(lib.ImageDedupeError,
                       match="https://img.example/a.jpg"):
        lib._merge_story_images(["https://img.example/a.jpg"], [], [], [])


# ---------------------------------------------------------------------------
# refresh_images: fetch-finds-nothing still cleans stored dupes
# ---------------------------------------------------------------------------

def test_refresh_images_empty_fetch_removes_stored_byte_dupes(libdir, monkeypatch):
    sid = _make_story(image_urls=[])
    _same = png_bytes_for("same-image")
    lib.update_story_fields(
        sid, image_urls=["https://img.example/a.jpg", "https://cdn.example/b.jpg"])
    monkeypatch.setattr(lib, "_fetch_images_for_story",
                        lambda story, topic, **k: [])
    monkeypatch.setattr(
        lib, "_fetch_image_bytes",
        fetch_for({"https://img.example/a.jpg": _same,
                   "https://cdn.example/b.jpg": _same}))
    changed, note = lib.refresh_images(sid, "chubby dogs voting contest")
    assert changed is True
    meta = lib.load_story(sid)["meta"]
    assert meta["image_urls"] == ["https://img.example/a.jpg"]
    assert len(meta["image_hashes"]) == 1 and all(meta["image_hashes"])
    assert len(meta["image_phashes"]) == 1 and all(meta["image_phashes"])
    assert "No new images found" in note
    assert "Removed 1 duplicate image(s) already stored" in note


def test_refresh_images_empty_fetch_removes_stored_visual_dupes(libdir, monkeypatch):
    sid = _make_story(image_urls=[])
    _big = png_bytes_for("vis-photo", size=(320, 240))
    _small = png_bytes_for("vis-photo", size=(160, 120))
    lib.update_story_fields(
        sid, image_urls=["https://img.example/big.jpg",
                         "https://cdn.example/small.jpg"])
    monkeypatch.setattr(lib, "_fetch_images_for_story",
                        lambda story, topic, **k: [])
    monkeypatch.setattr(
        lib, "_fetch_image_bytes",
        fetch_for({"https://img.example/big.jpg": _big,
                   "https://cdn.example/small.jpg": _small}))
    changed, note = lib.refresh_images(sid, "chubby dogs voting contest")
    assert changed is True
    meta = lib.load_story(sid)["meta"]
    assert meta["image_urls"] == ["https://img.example/big.jpg"]
    assert "Removed 1 duplicate image(s) already stored" in note


def test_refresh_images_empty_fetch_backfills_hashes_without_url_change(
        libdir, monkeypatch):
    sid = _make_story(image_urls=["https://img.example/kept.jpg"])
    monkeypatch.setattr(lib, "_fetch_images_for_story",
                        lambda story, topic, **k: [])
    monkeypatch.setattr(lib, "_fetch_image_bytes", fetch_for())
    changed, note = lib.refresh_images(sid, "chubby dogs voting contest")
    # No URL changed, but the backfilled hashes are persisted — that is a
    # real change (the next refresh will not pay the fetch cost again).
    assert changed is True
    meta = lib.load_story(sid)["meta"]
    assert meta["image_urls"] == ["https://img.example/kept.jpg"]
    assert all(meta["image_hashes"]) and all(meta["image_phashes"])
    assert "No new images found" in note and "kept 1 existing" in note


def test_refresh_images_backfill_failure_raises_loudly(libdir, monkeypatch):
    sid = _make_story(image_urls=["https://img.example/a.jpg"])
    monkeypatch.setattr(lib, "_fetch_images_for_story",
                        lambda story, topic, **k: [])

    def _boom(url, **kw):
        raise lib.ImageDedupeError(
            f"Image dedupe failed: could not fetch {url} (connection refused)")
    monkeypatch.setattr(lib, "_fetch_image_bytes", _boom)
    with pytest.raises(lib.ImageDedupeError,
                       match="https://img.example/a.jpg"):
        lib.refresh_images(sid, "chubby dogs voting contest")
    # Nothing was written: the dedupe check was not silently skipped.
    assert lib.load_story(sid)["meta"]["image_urls"] == [
        "https://img.example/a.jpg"]


# ---------------------------------------------------------------------------
# creation path: save_story stays network-free; the next refresh cleans up
# ---------------------------------------------------------------------------

def test_save_story_stays_network_free_and_next_refresh_cleans_up(
        libdir, monkeypatch):
    # save_story dedupes by URL only — byte-identical images under
    # different URLs are stored (no network at save time).
    def _boom(url, **kw):
        raise AssertionError("save_story must not touch the network")
    monkeypatch.setattr(lib, "_fetch_image_bytes", _boom)
    sid = _make_story(image_urls=["https://img.example/a.jpg",
                                  "https://cdn.example/b.jpg"])
    assert lib.load_story(sid)["meta"]["image_urls"] == [
        "https://img.example/a.jpg", "https://cdn.example/b.jpg"]
    # The next refresh collapses them (fail-loud backfill, then pure).
    _same = png_bytes_for("same-image")
    monkeypatch.setattr(lib, "_fetch_images_for_story",
                        lambda story, topic, **k: [])
    monkeypatch.setattr(
        lib, "_fetch_image_bytes",
        fetch_for({"https://img.example/a.jpg": _same,
                   "https://cdn.example/b.jpg": _same}))
    changed, note = lib.refresh_images(sid, "chubby dogs voting contest")
    assert changed is True
    assert lib.load_story(sid)["meta"]["image_urls"] == [
        "https://img.example/a.jpg"]
    assert "Removed 1 duplicate image(s) already stored" in note


def test_jpeg_quality_variants_are_visual_dupes_not_distinct(libdir, monkeypatch):
    # Same photo re-compressed: different bytes, dHash within threshold —
    # stored side by side, one refresh collapses them.
    sid = _make_story(image_urls=[])
    _q90 = jpeg_bytes_for("vis-photo", quality=90)
    _q50 = jpeg_bytes_for("vis-photo", quality=50)
    lib.update_story_fields(
        sid, image_urls=["https://img.example/q90.jpg",
                         "https://img.example/q50.jpg"])
    monkeypatch.setattr(lib, "_fetch_images_for_story",
                        lambda story, topic, **k: [])
    monkeypatch.setattr(
        lib, "_fetch_image_bytes",
        fetch_for({"https://img.example/q90.jpg": _q90,
                   "https://img.example/q50.jpg": _q50}))
    changed, note = lib.refresh_images(sid, "chubby dogs voting contest")
    assert changed is True
    assert lib.load_story(sid)["meta"]["image_urls"] == [
        "https://img.example/q90.jpg"]
