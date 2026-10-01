"""v1.6 tests for GitHub issue #21: duplicate/unwanted story images.

- Adding an image that is already attached is a no-op, detected by
  normalized URL AND by identical content (SHA-256 of fetched bytes).
- Stories seeded with duplicates show each image once after opening.
- Alt text is the primary signal for excluding unwanted assets
  (logos, avatars, ads); missing alt text is not a pass by itself.
- Hash/fetch failures raise loudly — the dedupe check is never
  silently skipped.

Run: python -m pytest tests/test_image_dedup_v16.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import story_library as lib  # noqa: E402
from _fake_images import fetch_for, png_bytes_for  # noqa: E402
from tools.story_link import (  # noqa: E402
    extract_story_images,
    extract_story_images_with_alt,
    image_alt_is_unwanted,
)


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
# normalize_image_url: trivial variants collapse to one key
# ---------------------------------------------------------------------------

def test_normalize_image_url_collapses_trivial_variants():
    base = lib.normalize_image_url("https://img.example/a.jpg")
    assert lib.normalize_image_url("https://IMG.EXAMPLE/a.jpg") == base
    assert lib.normalize_image_url("https://img.example/a.jpg/") == base
    assert lib.normalize_image_url("https://img.example:443/a.jpg") == base
    assert lib.normalize_image_url("https://img.example/a.jpg#frag") == base
    assert lib.normalize_image_url("https://img.example//a.jpg") == base


def test_normalize_image_url_sorts_query_params():
    a = lib.normalize_image_url("https://img.example/a.jpg?x=1&y=2")
    b = lib.normalize_image_url("https://img.example/a.jpg?y=2&x=1")
    assert a == b
    # Different query VALUES are still different images.
    c = lib.normalize_image_url("https://img.example/a.jpg?x=1&y=3")
    assert c != a
    # A query string at all is different from none.
    assert lib.normalize_image_url("https://img.example/a.jpg") != a


def test_normalize_image_url_keeps_scheme_and_host():
    # Conservative by design: scheme/host differences are left for the
    # content hash to resolve, never collapsed by the key.
    assert (lib.normalize_image_url("http://img.example/a.jpg")
            != lib.normalize_image_url("https://img.example/a.jpg"))
    assert (lib.normalize_image_url("https://www.img.example/a.jpg")
            != lib.normalize_image_url("https://img.example/a.jpg"))


# ---------------------------------------------------------------------------
# image_alt_is_unwanted: alt text is the primary keep/remove signal
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("alt", [
    "site logo", "Company Logo", "favicon", "author photo", "author avatar",
    "profile picture", "advertisement", "Advertisement", "sponsored",
    "share on twitter", "follow us", "social share buttons", "search icon",
    "tracking pixel", "decorative spacer", "placeholder image", "banner ad",
    "ad",
])
def test_unwanted_alt_text_is_flagged(alt):
    assert image_alt_is_unwanted(alt) is True


@pytest.mark.parametrize("alt", [
    "dogs playing in the park", "protesters marching in Delhi",
    "cricket stadium at night", "iconic victory moment", "banner",
    "", "   ", None,
])
def test_descriptive_or_missing_alt_text_is_not_flagged(alt):
    # Missing alt text is not a pass by itself — but it is never a
    # removal signal on its own either.
    assert image_alt_is_unwanted(alt) is False


# ---------------------------------------------------------------------------
# extract_story_images_with_alt: alt capture + alt-driven exclusion
# ---------------------------------------------------------------------------

_ALT_HTML = """<html><head>
<meta property="og:image" content="https://publisher.example/hero.jpg">
</head><body><article>
<img src="/photos/dogs.jpg" alt="dogs playing in the park">
<img src="https://publisher.example/assets/logo.png" alt="site logo">
<img src="/photos/crowd.jpg" alt="protesters marching">
</article></body></html>"""


def test_extract_story_images_with_alt_captures_and_filters():
    pairs = extract_story_images_with_alt(_ALT_HTML, "https://publisher.example/s")
    urls = [u for u, _ in pairs]
    alts = {u: a for u, a in pairs}
    # The logo is excluded by its alt text even though the URL junk
    # filter would also catch it.
    assert "https://publisher.example/assets/logo.png" not in urls
    assert "https://publisher.example/photos/dogs.jpg" in urls
    assert alts["https://publisher.example/photos/dogs.jpg"] == "dogs playing in the park"
    # og:image carries no alt text.
    assert alts["https://publisher.example/hero.jpg"] is None
    # The URL-only wrapper applies the same filtering.
    assert extract_story_images(_ALT_HTML, "https://publisher.example/s") == urls


# ---------------------------------------------------------------------------
# refresh_images: no-op on duplicates (URL, normalized URL, content)
# ---------------------------------------------------------------------------

def test_refresh_images_same_url_twice_is_noop(libdir, monkeypatch):
    sid = _make_story(image_urls=["https://img.example/a.jpg"])
    monkeypatch.setattr(lib, "_fetch_images_for_story",
                        lambda story, topic, **k: ["https://img.example/a.jpg"])
    # Issue #57: the merge always runs, so the stored image's missing
    # hashes are backfilled (one-time fetch, then persisted). No second
    # copy of the image is ever stored.
    monkeypatch.setattr(lib, "_fetch_image_bytes", fetch_for())
    changed, note = lib.refresh_images(sid, "chubby dogs voting contest")
    assert changed is True  # backfilled hashes were persisted
    meta = lib.load_story(sid)["meta"]
    assert meta["image_urls"] == ["https://img.example/a.jpg"]
    assert all(meta["image_hashes"]) and all(meta["image_phashes"])


def test_refresh_images_normalized_url_variant_is_noop(libdir, monkeypatch):
    sid = _make_story(image_urls=["https://img.example/a.jpg?x=1&y=2"])
    monkeypatch.setattr(
        lib, "_fetch_images_for_story",
        lambda story, topic, **k: ["https://IMG.EXAMPLE/a.jpg/?y=2&x=1",
                                   "https://img.example/a.jpg?x=1&y=2#frag"])
    # Both candidates collapse to the stored URL before any candidate
    # content check — but issue #57 backfills the stored entry's missing
    # hashes (one-time fetch, then persisted).
    monkeypatch.setattr(lib, "_fetch_image_bytes", fetch_for())
    changed, note = lib.refresh_images(sid, "chubby dogs voting contest")
    assert changed is True  # backfilled hashes were persisted
    assert lib.load_story(sid)["meta"]["image_urls"] == [
        "https://img.example/a.jpg?x=1&y=2"]
    assert "already stored" in note


def test_refresh_images_identical_content_different_url_is_noop(libdir, monkeypatch):
    sid = _make_story(image_urls=["https://img.example/one.jpg"])
    monkeypatch.setattr(
        lib, "_fetch_images_for_story",
        lambda story, topic, **k: [("https://img.example/one.jpg", None),
                                   ("https://cdn.example/mirror.jpg", None)])
    # mirror.jpg serves byte-identical content to one.jpg.
    _same = png_bytes_for("same-image")
    monkeypatch.setattr(
        lib, "_fetch_image_bytes",
        fetch_for({"https://img.example/one.jpg": _same,
                   "https://cdn.example/mirror.jpg": _same}))
    changed, note = lib.refresh_images(sid, "chubby dogs voting contest")
    # No duplicate stored (the mirror is recognised by content) — but issue
    # #57 backfills the stored entry's missing hashes, which is persisted.
    assert changed is True
    meta = lib.load_story(sid)["meta"]
    assert meta["image_urls"] == ["https://img.example/one.jpg"]
    assert all(meta["image_hashes"]) and all(meta["image_phashes"])
    assert "already stored" in note


def test_refresh_images_excludes_unwanted_alt_text(libdir, monkeypatch):
    sid = _make_story(image_urls=[])
    monkeypatch.setattr(
        lib, "_fetch_images_for_story",
        lambda story, topic, **k: [("https://img.example/logo.png", "site logo"),
                                   ("https://img.example/dogs.jpg",
                                    "dogs playing in the park")])
    monkeypatch.setattr(lib, "_fetch_image_bytes", fetch_for())
    changed, note = lib.refresh_images(sid, "chubby dogs voting contest")
    assert changed is True
    meta = lib.load_story(sid)["meta"]
    assert meta["image_urls"] == ["https://img.example/dogs.jpg"]
    assert "Excluded 1 unwanted image(s)" in note


def test_refresh_images_fails_loudly_when_hash_fetch_fails(libdir, monkeypatch):
    sid = _make_story(image_urls=["https://img.example/old.jpg"])
    # The existing image already has both hashes: only the NEW candidate's
    # fetch fails, so the error must name the new URL.
    lib.update_story_fields(sid, image_hashes=["0" * 64],
                            image_phashes=["f" * 16])
    monkeypatch.setattr(lib, "_fetch_images_for_story",
                        lambda story, topic, **k: ["https://img.example/new.jpg"])

    def _boom(url, **kw):
        raise lib.ImageDedupeError(
            f"Image dedupe failed: could not fetch {url} (connection refused)")
    monkeypatch.setattr(lib, "_fetch_image_bytes", _boom)
    with pytest.raises(lib.ImageDedupeError, match="https://img.example/new.jpg"):
        lib.refresh_images(sid, "chubby dogs voting contest")
    # Nothing was stored: the dedupe check was not silently skipped.
    assert lib.load_story(sid)["meta"]["image_urls"] == ["https://img.example/old.jpg"]


def test_refresh_images_cleans_up_stored_content_dupes(libdir, monkeypatch):
    sid = _make_story(image_urls=[])
    # Seed two legacy entries with identical bytes under different URLs.
    _same = png_bytes_for("same-image")
    lib.update_story_fields(
        sid, image_urls=["https://img.example/a.jpg", "https://cdn.example/b.jpg"])
    monkeypatch.setattr(lib, "_fetch_images_for_story",
                        lambda story, topic, **k: ["https://img.example/c.jpg"])
    monkeypatch.setattr(
        lib, "_fetch_image_bytes",
        fetch_for({"https://img.example/a.jpg": _same,
                   "https://cdn.example/b.jpg": _same}))
    changed, note = lib.refresh_images(sid, "chubby dogs voting contest")
    assert changed is True
    meta = lib.load_story(sid)["meta"]
    assert meta["image_urls"] == ["https://img.example/a.jpg",
                                 "https://img.example/c.jpg"]
    assert "Removed 1 duplicate image(s) already stored" in note


# ---------------------------------------------------------------------------
# load/save migration: seeded duplicates are cleaned up on open
# ---------------------------------------------------------------------------

def test_load_story_dedupes_seeded_duplicates(libdir):
    sid = _make_story(image_urls=["https://img.example/a.jpg"])
    # Seed duplicates the way a pre-#21 story carries them (bypasses the
    # save-time dedupe via a direct field write).
    lib.update_story_fields(
        sid,
        image_urls=["https://img.example/a.jpg",
                    "https://img.example/a.jpg",
                    "https://IMG.example/a.jpg/",
                    "https://img.example/b.jpg"])
    meta = lib.load_story(sid)["meta"]
    assert meta["image_urls"] == ["https://img.example/a.jpg",
                                 "https://img.example/b.jpg"]
    assert meta["image_hashes"] == ["", ""]
    # The cleanup is persisted, not just a view.
    raw = lib.story_path(sid).read_text(encoding="utf-8")
    assert raw.count("https://img.example/a.jpg") == 1


def test_save_story_never_stores_duplicates(libdir):
    sid = lib.save_story(
        title="t", tone="funny", hashtags=[], dialogue_md="", script_md="x",
        image_urls=["https://img.example/a.jpg",
                    "https://img.example/a.jpg",
                    "https://IMG.example/a.jpg/"])
    assert lib.load_story(sid)["meta"]["image_urls"] == ["https://img.example/a.jpg"]


# ---------------------------------------------------------------------------
# update_fetched_image_url: editing to a duplicate fails loudly
# ---------------------------------------------------------------------------

def test_update_fetched_image_url_rejects_duplicate(libdir):
    sid = _make_story(image_urls=["https://img.example/a.jpg",
                                 "https://img.example/b.jpg"])
    with pytest.raises(ValueError, match="already attached"):
        lib.update_fetched_image_url(sid, 1, "https://img.example/a.jpg/")
    # The original is untouched after the rejected edit.
    assert lib.load_story(sid)["meta"]["image_urls"] == [
        "https://img.example/a.jpg", "https://img.example/b.jpg"]


def test_update_fetched_image_url_invalidates_hash(libdir):
    sid = _make_story(image_urls=["https://img.example/a.jpg"])
    lib.update_story_fields(sid, image_hashes=["0" * 64])
    assert lib.update_fetched_image_url(sid, 0, "https://img.example/z.jpg") is True
    meta = lib.load_story(sid)["meta"]
    assert meta["image_urls"] == ["https://img.example/z.jpg"]
    # The new address has unknown content until a refresh re-hashes it.
    assert meta["image_hashes"] == [""]


# ---------------------------------------------------------------------------
# _merge_story_images: the full pipeline in one mixed batch
# ---------------------------------------------------------------------------

def test_merge_story_images_mixed_batch(monkeypatch):
    _keep = png_bytes_for("keep-image")
    monkeypatch.setattr(
        lib, "_fetch_image_bytes",
        fetch_for({"https://img.example/keep.jpg": _keep,
                   "https://cdn.example/x.jpg": _keep}))
    merged, hashes, phashes, stats = lib._merge_story_images(
        ["https://img.example/keep.jpg"], [""], [],
        [("https://img.example/keep.jpg/", None),          # dup URL
         ("https://img.example/logo.png", "company logo"),  # alt-rejected
         ("https://cdn.example/x.jpg", None),               # dup content
         ("https://img.example/fresh.jpg", "dogs")])        # genuinely new
    assert merged == ["https://img.example/keep.jpg",
                      "https://img.example/fresh.jpg"]
    assert len(hashes) == 2 and all(hashes)
    assert len(phashes) == 2 and all(phashes)
    assert stats == {"added": 1, "dup_url": 1, "dup_content": 1,
                     "dup_visual": 0, "rejected_alt": 1,
                     "removed_existing_dupes": 0}


def test_merge_story_images_accepts_bare_url_strings(monkeypatch):
    # Backward compatibility: callers without alt text pass plain strings.
    monkeypatch.setattr(lib, "_fetch_image_bytes", fetch_for())
    merged, hashes, phashes, stats = lib._merge_story_images(
        [], [], [], ["https://img.example/a.jpg", "https://img.example/a.jpg"])
    assert merged == ["https://img.example/a.jpg"]
    assert stats["added"] == 1 and stats["dup_url"] == 1
