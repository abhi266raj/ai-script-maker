"""Focused tests for the v1.5 Library work: persisted AI controls, the
constrained AI hashtag path, fail-loud refresh states, and
verified-links-first media fetch.

Run: python -m pytest tests/test_library_v15.py -q
"""
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import story_library as lib  # noqa: E402


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
# AI engine options + persisted prefs
# ---------------------------------------------------------------------------

def test_engine_options_cover_all_modes():
    assert len(lib.LIBRARY_ENGINE_OPTIONS) == 7
    assert set(lib.LIBRARY_ENGINE_OPTIONS.values()) == lib.LIBRARY_ENGINE_MODES
    assert lib.DEFAULT_LIBRARY_AI_ENGINE in lib.LIBRARY_ENGINE_OPTIONS


def test_ai_prefs_round_trip(libdir):
    assert lib.load_prefs() == {}
    lib.save_prefs({"library_ai_enabled": True})
    lib.save_prefs({"library_ai_engine": "Codex"})
    prefs = lib.load_prefs()
    assert prefs["library_ai_enabled"] is True
    assert prefs["library_ai_engine"] == "Codex"


def test_ai_prefs_default_off(libdir):
    # A fresh prefs file means AI processing is off.
    assert lib.load_prefs().get("library_ai_enabled", False) is False


# ---------------------------------------------------------------------------
# AI hashtag validation: the AI may rank/rephrase but never invent
# ---------------------------------------------------------------------------

def _story():
    return {
        "meta": {
            "title": "Dog Showdown Reel",
            "source_topic": "chubby dogs voting contest",
            "source_headline": "Chubby dogs battle in voting contest",
        },
        "script": "AARAV: chubby dogs voting contest in the park",
    }


def test_validate_ai_tags_keeps_grounded():
    tags = lib._validate_ai_tags(["#ChubbyDogs", "#VotingContest", "#Park"], _story())
    assert "#ChubbyDogs" in tags
    assert "#VotingContest" in tags


def test_validate_ai_tags_drops_invented_and_malformed():
    tags = lib._validate_ai_tags(
        ["#RussiaKillsFour",  # off-topic invention
         "not-a-tag",
         "#x",                # too short
         "#ChubbyDogs!!",     # malformed
         "#ChubbyDogs", "#ChubbyDogs"],  # dupes collapse
        _story())
    assert tags == ["#ChubbyDogs"]


def test_suggest_hashtags_deterministic_when_ai_off(libdir):
    sid = _make_story()
    story = lib.load_story(sid)
    tags, note = lib._suggest_hashtags(story, "chubby dogs voting contest", ai_engine=None)
    assert note == ""
    assert tags, "deterministic path must always produce tags"
    assert all(t.startswith("#") for t in tags)


def test_suggest_hashtags_ai_failure_falls_back_loudly(libdir, monkeypatch):
    sid = _make_story()
    story = lib.load_story(sid)

    def _boom(*a, **k):
        raise RuntimeError("engine exploded")

    monkeypatch.setattr(lib, "_ai_hashtag_suggestions", _boom)
    tags, note = lib._suggest_hashtags(story, "chubby dogs voting contest",
                                      ai_engine="codex_only")
    assert tags, "deterministic fallback must still produce tags"
    assert "AI hashtag step failed" in note
    assert "engine exploded" in note


def test_suggest_hashtags_ai_success_validated(libdir, monkeypatch):
    # Patch at the engine boundary: the fake engine returns one grounded tag
    # and one invented off-topic tag. Validation inside
    # _ai_hashtag_suggestions must drop the invented one.
    sid = _make_story()
    story = lib.load_story(sid)
    import sys as _sys
    de = _sys.modules["core.dual_engine"]  # the module, not the instance

    class _FakeEngine:
        def generate(self, prompt="", instructions="", mode=""):
            assert mode == "codex_only"
            return "#ChubbyDogs\n#RussiaKillsFour\n", "fake-engine"

    monkeypatch.setattr(de, "dual_engine", _FakeEngine())
    tags, note = lib._suggest_hashtags(story, "chubby dogs voting contest",
                                      ai_engine="codex_only")
    assert "#ChubbyDogs" in tags
    assert "#RussiaKillsFour" not in tags
    assert "AI hashtag step failed" not in note


def test_ai_hashtag_rejects_unknown_engine(libdir):
    sid = _make_story()
    story = lib.load_story(sid)
    with pytest.raises(ValueError):
        lib._ai_hashtag_suggestions(story, "topic", "not_a_real_mode")


# ---------------------------------------------------------------------------
# refresh_hashtags: merge-only, never wipes, reports honestly
# ---------------------------------------------------------------------------

def test_refresh_hashtags_merges_and_reports(libdir, monkeypatch):
    sid = _make_story(hashtags=["#DogShowdown"])
    monkeypatch.setattr(lib, "_fetch_trending_hashtags",
                        lambda topic, story=None: ["#DogShowdown", "#ChubbyDogs"])
    changed, note = lib.refresh_hashtags(sid, "chubby dogs voting contest")
    assert changed is True
    assert "Validated 1 existing hashtag(s)." in note
    assert "Added 1: #ChubbyDogs." in note
    assert "#DogShowdown" in lib.load_story(sid)["meta"]["hashtags"]
    assert "#ChubbyDogs" in lib.load_story(sid)["meta"]["hashtags"]


def test_refresh_hashtags_no_change_is_honest(libdir, monkeypatch):
    sid = _make_story(hashtags=["#DogShowdown"])
    monkeypatch.setattr(lib, "_fetch_trending_hashtags",
                        lambda topic, story=None: ["#DogShowdown"])
    changed, note = lib.refresh_hashtags(sid, "chubby dogs voting contest")
    assert changed is False
    assert "Validated 1 existing hashtag(s)." in note
    assert "Everything still valid — nothing new found." in note


def test_refresh_hashtags_removes_invalid_existing(libdir, monkeypatch):
    # Stale/off-topic tags stored earlier are validated against the story's
    # own content on refresh and removed — not silently kept.
    sid = _make_story(hashtags=["#DogShowdown", "#RussiaKillsFour", "bogus"])
    monkeypatch.setattr(lib, "_fetch_trending_hashtags",
                        lambda topic, story=None: [])
    changed, note = lib.refresh_hashtags(sid, "chubby dogs voting contest")
    assert changed is True
    assert "Removed 2 invalid: #RussiaKillsFour, bogus." in note
    remaining = lib.load_story(sid)["meta"]["hashtags"]
    assert remaining == ["#DogShowdown"]


# ---------------------------------------------------------------------------
# start_refresh: topic fallback + background worker notes
# ---------------------------------------------------------------------------

def test_start_refresh_falls_back_to_title(libdir, monkeypatch):
    sid = _make_story(source_topic="")  # old story without source_topic
    monkeypatch.setattr(lib, "_refresh_worker",
                        lambda sid_, kind, topic, ai_engine=None: None)
    assert lib.start_refresh(sid, "hashtags") is True


def test_start_refresh_rejects_bad_kind(libdir):
    sid = _make_story()
    assert lib.start_refresh(sid, "bogus") is False


def test_refresh_worker_writes_failure_note(libdir, monkeypatch):
    sid = _make_story()

    def _boom(sid_, topic, ai_engine=None):
        raise RuntimeError("network down")

    monkeypatch.setattr(lib, "refresh_hashtags", _boom)
    lib._refresh_worker(sid, "hashtags", "chubby dogs voting contest")
    meta = lib.load_story(sid)["meta"]
    assert meta["enrichment_status"] == "done"
    assert meta["refresh_kind"] == ""
    assert "Refresh failed" in meta["refresh_note"]
    assert "network down" in meta["refresh_note"]


def test_refresh_worker_busy_lock_is_honest(libdir):
    sid = _make_story()
    lock = lib._ENRICH_LOCKS.setdefault(sid, threading.Lock())
    assert lock.acquire(blocking=False)
    try:
        lib._refresh_worker(sid, "hashtags", "chubby dogs voting contest")
    finally:
        lock.release()
    meta = lib.load_story(sid)["meta"]
    assert "already running" in meta["refresh_note"]


# ---------------------------------------------------------------------------
# retry path: notes recorded, links/content untouched
# ---------------------------------------------------------------------------

def test_do_media_refresh_returns_note_and_preserves_links(libdir, monkeypatch):
    links = [{"title": "Exact story", "url": "https://example.com/exact",
              "source": "Example"}]
    sid = _make_story(news_links=links, hashtags=["#DogShowdown"])
    monkeypatch.setattr(lib, "_fetch_images_for_story", lambda story, topic, **k: [])
    monkeypatch.setattr(lib, "_suggest_hashtags",
                        lambda story, topic, ai_engine=None: (["#NewTag"], ""))
    note = lib._do_media_refresh(sid, "chubby dogs voting contest")
    assert isinstance(note, str) and note
    meta = lib.load_story(sid)["meta"]
    assert meta["news_links"] == links, "retry must never touch verified links"
    assert "#NewTag" in meta["hashtags"]
    assert "#DogShowdown" in meta["hashtags"]


def test_enrich_worker_records_retry_note(libdir):
    sid = _make_story()
    lib._enrich_worker(sid, "chubby dogs voting contest",
                       lambda s, t: "Images updated (2 found).")
    meta = lib.load_story(sid)["meta"]
    assert meta["enrichment_status"] == "done"
    assert meta["refresh_note"] == "Images updated (2 found)."


# ---------------------------------------------------------------------------
# media fetch: verified story links first
# ---------------------------------------------------------------------------

def test_story_direct_link_urls_prefers_verified(libdir):
    sid = _make_story(news_links=[
        {"title": "Exact", "url": "https://publisher.example/exact-story", "source": "P"},
        {"title": "Bad", "url": "not-a-url", "source": "P"},
    ])
    story = lib.load_story(sid)
    assert lib._story_direct_link_urls(story) == ["https://publisher.example/exact-story"]
    assert lib._story_direct_link_urls(None) == []


def test_fetch_images_for_story_tries_verified_links_first(libdir, monkeypatch):
    sid = _make_story(news_links=[
        {"title": "Exact", "url": "https://publisher.example/exact-story", "source": "P"}])
    story = lib.load_story(sid)
    calls = []

    def _grab(urls, tries=3):
        calls.append(list(urls))
        return ["https://img.example/hero.jpg"]

    monkeypatch.setattr(lib, "_grab_article_images", _grab)
    monkeypatch.setattr(lib, "_fetch_news_articles",
                        lambda topic, limit=6: (_ for _ in ()).throw(
                            AssertionError("topic search must not run")))
    found = lib._fetch_images_for_story(story, "chubby dogs voting contest")
    assert found == ["https://img.example/hero.jpg"]
    assert calls[0] == ["https://publisher.example/exact-story"]


def test_fetch_images_for_story_falls_back_to_topic(libdir, monkeypatch):
    sid = _make_story()  # no verified links
    story = lib.load_story(sid)
    monkeypatch.setattr(lib, "_grab_article_images",
                        lambda urls, tries=3: [])
    monkeypatch.setattr(lib, "_fetch_article_images",
                        lambda articles, topic="", tries=3: ["https://img.example/t.jpg"])
    found = lib._fetch_images_for_story(story, "chubby dogs voting contest")
    assert found == ["https://img.example/t.jpg"]


# ---------------------------------------------------------------------------
# image fetch: article <img> tags, not just og:image
# ---------------------------------------------------------------------------

_ARTICLE_HTML = """<html><head>
<meta property="og:image" content="https://publisher.example/hero.jpg">
</head><body><article>
<img src="/photos/dog1.jpg" alt="dogs">
<img data-src="https://cdn.example/lazy/dog2.jpg" alt="lazy">
<img src="https://publisher.example/assets/logo.png" alt="logo">
<img src="https://tracker.example/pixel.gif" alt="t">
</article></body></html>"""


class _FakeResp:
    def __init__(self, text, status=200, ctype="text/html; charset=utf-8"):
        self.text = text
        self.status_code = status
        self.headers = {"content-type": ctype}


def _fake_httpx_get(html, status=200, ctype="text/html; charset=utf-8"):
    def _get(url, **kw):
        return _FakeResp(html, status, ctype)
    return _get


def test_grab_article_images_extracts_body_img_tags(libdir, monkeypatch):
    monkeypatch.setattr("httpx.get", _fake_httpx_get(_ARTICLE_HTML))
    found = lib._grab_article_images(["https://publisher.example/story"],
                                     tries=1)
    # og:image first, then in-article photos; relative + lazy-load absolutized.
    assert found[0] == "https://publisher.example/hero.jpg"
    assert "https://publisher.example/photos/dog1.jpg" in found
    assert "https://cdn.example/lazy/dog2.jpg" in found
    # Logos and tracking pixels are filtered out.
    assert not any("logo" in u or "pixel" in u for u in found)


def test_grab_article_images_skips_non_html(libdir, monkeypatch):
    monkeypatch.setattr("httpx.get",
                        _fake_httpx_get("{}", ctype="application/json"))
    assert lib._grab_article_images(["https://publisher.example/api"],
                                    tries=1) == []


def test_grab_article_images_skips_failed_pages(libdir, monkeypatch):
    def _boom(url, **kw):
        raise RuntimeError("connection refused")
    monkeypatch.setattr("httpx.get", _boom)
    assert lib._grab_article_images(["https://publisher.example/down"],
                                    tries=1) == []


# ---------------------------------------------------------------------------
# refresh_images: merge, never replace
# ---------------------------------------------------------------------------

def test_refresh_images_merges_not_replaces(libdir, monkeypatch):
    sid = _make_story(image_urls=["https://img.example/old.jpg"])
    monkeypatch.setattr(
        lib, "_fetch_images_for_story",
        lambda story, topic, **k: ["https://img.example/old.jpg",
                                  "https://img.example/new.jpg"])
    changed, note = lib.refresh_images(sid, "chubby dogs voting contest")
    assert changed is True
    meta = lib.load_story(sid)["meta"]
    # Existing URLs keep their order; new ones are appended, deduplicated.
    assert meta["image_urls"] == ["https://img.example/old.jpg",
                                 "https://img.example/new.jpg"]
    assert "Added 1 new image(s)" in note and "kept 1 existing" in note


def test_refresh_images_keeps_existing_when_fetch_empty(libdir, monkeypatch):
    sid = _make_story(image_urls=["https://img.example/old.jpg"])
    monkeypatch.setattr(lib, "_fetch_images_for_story",
                        lambda story, topic, **k: [])
    changed, note = lib.refresh_images(sid, "chubby dogs voting contest")
    assert changed is False
    assert lib.load_story(sid)["meta"]["image_urls"] == [
        "https://img.example/old.jpg"]
    assert "kept 1 existing" in note


def test_refresh_images_no_change_when_nothing_new(libdir, monkeypatch):
    sid = _make_story(image_urls=["https://img.example/old.jpg"])
    monkeypatch.setattr(lib, "_fetch_images_for_story",
                        lambda story, topic, **k: ["https://img.example/old.jpg"])
    changed, note = lib.refresh_images(sid, "chubby dogs voting contest")
    assert changed is False
    assert lib.load_story(sid)["meta"]["image_urls"] == [
        "https://img.example/old.jpg"]


def test_do_media_refresh_merges_images(libdir, monkeypatch):
    sid = _make_story(image_urls=["https://img.example/old.jpg"],
                      news_links=[{"title": "T", "url": "https://example.com/x",
                                   "source": "E"}])
    monkeypatch.setattr(lib, "_fetch_images_for_story",
                        lambda story, topic, **k: ["https://img.example/new.jpg"])
    monkeypatch.setattr(lib, "_suggest_hashtags",
                        lambda story, topic, ai_engine=None: ([], ""))
    note = lib._do_media_refresh(sid, "chubby dogs voting contest")
    meta = lib.load_story(sid)["meta"]
    assert meta["image_urls"] == ["https://img.example/old.jpg",
                                 "https://img.example/new.jpg"]
    assert "Added 1 new image(s)" in note
    # Retry never touches verified links or the script.
    assert meta["news_links"][0]["url"] == "https://example.com/x"
    assert "AARAV" in lib.load_story(sid)["script"]


# ---------------------------------------------------------------------------
# update_fetched_image_url: edit control, fail loudly
# ---------------------------------------------------------------------------

def test_update_fetched_image_url(libdir):
    sid = _make_story(image_urls=["https://img.example/a.jpg",
                                 "https://img.example/b.jpg"])
    assert lib.update_fetched_image_url(sid, 1, "https://img.example/c.jpg") is True
    assert lib.load_story(sid)["meta"]["image_urls"] == [
        "https://img.example/a.jpg", "https://img.example/c.jpg"]


def test_update_fetched_image_url_rejects_bad_values(libdir):
    sid = _make_story(image_urls=["https://img.example/a.jpg"])
    for bad in ("", "   ", "ftp://img.example/a.jpg", "not a url"):
        try:
            lib.update_fetched_image_url(sid, 0, bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {bad!r}")
    # The original is untouched after rejected edits.
    assert lib.load_story(sid)["meta"]["image_urls"] == [
        "https://img.example/a.jpg"]


def test_update_fetched_image_url_rejects_bad_index_and_story(libdir):
    sid = _make_story(image_urls=["https://img.example/a.jpg"])
    for index in (-1, 1, 99):
        try:
            lib.update_fetched_image_url(sid, index, "https://img.example/c.jpg")
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for index {index}")
    try:
        lib.update_fetched_image_url("no-such-story", 0,
                                    "https://img.example/c.jpg")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for unknown story")
