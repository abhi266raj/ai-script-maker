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
    added, note = lib.refresh_hashtags(sid, "chubby dogs voting contest")
    assert added is True
    assert "Hashtags updated." in note
    assert "#DogShowdown" in lib.load_story(sid)["meta"]["hashtags"]
    assert "#ChubbyDogs" in lib.load_story(sid)["meta"]["hashtags"]


def test_refresh_hashtags_no_change_is_honest(libdir, monkeypatch):
    sid = _make_story(hashtags=["#DogShowdown"])
    monkeypatch.setattr(lib, "_fetch_trending_hashtags",
                        lambda topic, story=None: ["#DogShowdown"])
    added, note = lib.refresh_hashtags(sid, "chubby dogs voting contest")
    assert added is False
    assert "kept the existing ones" in note


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

    monkeypatch.setattr(lib, "_grab_og_images", _grab)
    monkeypatch.setattr(lib, "_fetch_news_articles",
                        lambda topic, limit=6: (_ for _ in ()).throw(
                            AssertionError("topic search must not run")))
    found = lib._fetch_images_for_story(story, "chubby dogs voting contest")
    assert found == ["https://img.example/hero.jpg"]
    assert calls[0] == ["https://publisher.example/exact-story"]


def test_fetch_images_for_story_falls_back_to_topic(libdir, monkeypatch):
    sid = _make_story()  # no verified links
    story = lib.load_story(sid)
    monkeypatch.setattr(lib, "_grab_og_images", lambda urls, tries=3: [])
    monkeypatch.setattr(lib, "_fetch_article_images",
                        lambda articles, topic="", tries=3: ["https://img.example/t.jpg"])
    found = lib._fetch_images_for_story(story, "chubby dogs voting contest")
    assert found == ["https://img.example/t.jpg"]
