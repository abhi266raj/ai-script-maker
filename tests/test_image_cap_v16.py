"""v1.6.2 tests for GitHub issue #83: fetched story images are capped at
max 5. Uploaded media is EXEMPT — uploads live in the separate
``uploaded_images`` field and are never trimmed.

The cap applies at the merge point (``_merge_story_images``) AFTER all
dedupe (#21 URL+content, #44 perceptual), so dedupe-then-cap ordering
holds on every path that adds fetched images (save-time enrichment,
Update Images refresh, Reset media). When trimming, the first N are
kept (existing entries first, publisher-declared og:image etc. earliest
among fresh candidates) and the outcome note says so honestly.

Run: python -m pytest tests/test_image_cap_v16.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import story_library as lib  # noqa: E402
from _fake_images import fetch_for  # noqa: E402


CAP = lib._MAX_FETCHED_IMAGES


def _urls(n, prefix="https://img.example"):
    return [f"{prefix}/pic{i}.jpg" for i in range(n)]


@pytest.fixture
def libdir(tmp_path, monkeypatch):
    root = tmp_path / "HindiReelStudio"
    monkeypatch.setattr(lib, "LIBRARY_ROOT", root)
    monkeypatch.setattr(lib, "STORIES_DIR", root / "stories")
    monkeypatch.setattr(lib, "PREFS_PATH", root / "prefs.json")
    monkeypatch.setattr(lib, "_fetch_image_bytes", fetch_for())
    return root


def _make_story(**kw):
    kw.setdefault("title", "Cap Test Reel")
    kw.setdefault("tone", "funny")
    kw.setdefault("hashtags", ["#CapTest"])
    kw.setdefault("dialogue_md", "")
    kw.setdefault("script_md", "AARAV: eight photos of the festival")
    kw.setdefault("source_topic", "festival photos")
    kw.setdefault("source_headline", "Festival in full swing")
    return lib.save_story(**kw)


# ---------------------------------------------------------------------------
# _merge_story_images: cap behaviour
# ---------------------------------------------------------------------------

def test_cap_is_five():
    # The issue pins the number.
    assert CAP == 5


def test_fetched_capped_at_five(libdir):
    merged, hashes, phashes, stats = lib._merge_story_images(
        [], [], [], _urls(8), cap=CAP)
    assert merged == _urls(5)
    assert len(hashes) == 5 and all(hashes)
    assert len(phashes) == 5 and all(phashes)
    assert stats["added"] == 8
    assert stats["trimmed"] == 3


def test_no_cap_by_default_keeps_everything(libdir):
    # "Load more" (issue #91) omits the cap to bypass it.
    merged, hashes, phashes, stats = lib._merge_story_images(
        [], [], [], _urls(8))
    assert merged == _urls(8)
    assert stats["trimmed"] == 0


def test_cap_keeps_existing_first(libdir):
    existing = _urls(3, prefix="https://kept.example")
    merged, hashes, phashes, stats = lib._merge_story_images(
        existing, [], [], _urls(5), cap=CAP)
    assert merged == existing + _urls(2)
    assert len(hashes) == len(phashes) == CAP
    assert stats["trimmed"] == 3


def test_dedupe_runs_before_cap(libdir):
    # 8 candidates, two of which are URL-dupes of each other: dedupe
    # leaves 7 unique, so the cap trims 2 — not 3.
    cands = _urls(8)
    cands[6] = cands[0]  # dup URL within the batch
    merged, hashes, phashes, stats = lib._merge_story_images(
        [], [], [], cands, cap=CAP)
    assert len(merged) == CAP
    assert stats["dup_url"] == 1
    assert stats["added"] == 7
    assert stats["trimmed"] == 2


def test_cap_trims_stored_excess_even_with_no_new_candidates(libdir):
    # A story that already holds more than the cap (stored before the
    # cap existed) is trimmed on the next merge.
    merged, hashes, phashes, stats = lib._merge_story_images(
        _urls(7), [], [], [], cap=CAP)
    assert merged == _urls(5)
    assert stats["trimmed"] == 2


# ---------------------------------------------------------------------------
# refresh_images: cap + uploads exempt + honest note
# ---------------------------------------------------------------------------

def test_refresh_images_caps_fetched_and_says_so(libdir, monkeypatch):
    sid = _make_story(image_urls=[])
    monkeypatch.setattr(lib, "_fetch_images_for_story",
                        lambda story, topic, **k: _urls(8))
    changed, note = lib.refresh_images(sid, "festival photos")
    meta = lib.load_story(sid)["meta"]
    assert meta["image_urls"] == _urls(5)
    assert len(meta["image_hashes"]) == 5 and all(meta["image_hashes"])
    assert len(meta["image_phashes"]) == 5 and all(meta["image_phashes"])
    assert "Capped fetched images at 5" in note
    assert "3 extra not kept" in note


def test_refresh_images_never_touches_uploads(libdir, monkeypatch):
    # Uploads are deliberate — the cap must not trim them, and the merge
    # must not move them into the fetched row.
    sid = _make_story(image_urls=[])
    uploads = [f"upload{i}.jpg" for i in range(7)]
    lib.update_story_fields(sid, uploaded_images=uploads)
    monkeypatch.setattr(lib, "_fetch_images_for_story",
                        lambda story, topic, **k: _urls(8))
    changed, note = lib.refresh_images(sid, "festival photos")
    meta = lib.load_story(sid)["meta"]
    assert meta["uploaded_images"] == uploads
    assert meta["image_urls"] == _urls(5)
    # The honest trim note names the upload exemption.
    assert "uploads are never capped" in note
