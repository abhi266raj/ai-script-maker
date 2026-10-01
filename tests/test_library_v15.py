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


def _topic_story():
    return {"meta": {"title": "Dog Showdown Reel",
                     "source_topic": "chubby dogs voting contest",
                     "source_headline": "Chubby dogs battle in voting contest"},
            "script": "[Format Requirement: 9:16 Vertical Reel]"}


def test_validate_ai_tags_keeps_relevant():
    # Relevance = topic/headline/title words. Script words never count:
    # "#Park" appears only in the screenplay, so it is dropped.
    tags = lib._validate_ai_tags(["#ChubbyDogs", "#VotingContest", "#Park"],
                                 _topic_story())
    assert "#ChubbyDogs" in tags
    assert "#VotingContest" in tags
    assert "#Park" not in tags


def test_validate_ai_tags_drops_invented_and_malformed():
    tags = lib._validate_ai_tags(
        ["#RussiaKillsFour",  # off-topic invention
         "not-a-tag",
         "#x",                # too short
         "#ChubbyDogs!!",     # malformed
         "#ChubbyDogs", "#ChubbyDogs"],  # dupes collapse
        _topic_story())
    assert tags == ["#ChubbyDogs"]


def test_suggest_hashtags_ai_is_primary_path(libdir, monkeypatch):
    # The AI is always asked first — even with ai_engine=None. The engine
    # resolves from the persisted label, falling back to the default.
    sid = _make_story()
    story = lib.load_story(sid)
    monkeypatch.setattr(lib, "_ai_hashtag_suggestions",
                        lambda story, topic, mode: ["#ChubbyDogs"])
    tags, note = lib._suggest_hashtags(story, "chubby dogs voting contest",
                                      ai_engine=None)
    assert tags == ["#ChubbyDogs"]
    assert note == "Tags from AI-found trending hashtags."


def test_suggest_hashtags_ai_failure_falls_back_loudly(libdir, monkeypatch):
    sid = _make_story()
    story = lib.load_story(sid)

    def _boom(*a, **k):
        raise RuntimeError("engine exploded")

    monkeypatch.setattr(lib, "_ai_hashtag_suggestions", _boom)
    monkeypatch.setattr(lib, "_fetch_trending_hashtags",
                        lambda topic, story=None: (["#ChubbyDogsVoting"], ""))
    tags, note = lib._suggest_hashtags(story, "chubby dogs voting contest",
                                      ai_engine="codex_only")
    assert tags, "deterministic fallback must still produce tags"
    assert "AI hashtag step failed" in note
    assert "engine exploded" in note
    assert "deterministic fallback" in note


def test_suggest_hashtags_ai_success_validated(libdir, monkeypatch):
    # Patch at the engine boundary: the fake engine returns one grounded tag
    # and one invented off-topic tag. Validation inside
    # _ai_hashtag_suggestions must drop the invented one.
    sid = _make_story()
    story = lib.load_story(sid)
    de = _dual_engine_module()  # the module, not the instance

    class _FakeEngine:
        def generate(self, prompt="", instructions="", mode="", timeout=None):
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
    monkeypatch.setattr(lib, "_suggest_hashtags",
                        lambda story, topic, ai_engine=None: (["#DogShowdown", "#ChubbyDogs"], ""))
    changed, note = lib.refresh_hashtags(sid, "chubby dogs voting contest",
                                            ai_engine="codex_only")
    assert changed is True
    assert "Validated 1 existing hashtag(s)." in note
    assert "Added 1: #ChubbyDogs." in note
    assert "#DogShowdown" in lib.load_story(sid)["meta"]["hashtags"]
    assert "#ChubbyDogs" in lib.load_story(sid)["meta"]["hashtags"]


def test_refresh_hashtags_no_change_is_honest(libdir, monkeypatch):
    sid = _make_story(hashtags=["#DogShowdown"])
    monkeypatch.setattr(lib, "_suggest_hashtags",
                        lambda story, topic, ai_engine=None: (["#DogShowdown"], ""))
    changed, note = lib.refresh_hashtags(sid, "chubby dogs voting contest",
                                            ai_engine="codex_only")
    assert changed is False
    assert "Validated 1 existing hashtag(s)." in note
    assert "Everything still valid — nothing new found." in note


def test_refresh_hashtags_removes_invalid_existing(libdir, monkeypatch):
    # Stale/off-topic tags stored earlier are validated against the story's
    # topic/headline on refresh and removed — not silently kept.
    sid = _make_story(hashtags=["#DogShowdown", "#RussiaKillsFour",
                               "#FormatRequirementVertical", "bogus"])
    monkeypatch.setattr(lib, "_suggest_hashtags",
                        lambda story, topic, ai_engine=None: ([], ""))
    changed, note = lib.refresh_hashtags(sid, "chubby dogs voting contest",
                                            ai_engine="codex_only")
    assert changed is True
    assert ("Removed 3 not relevant to the story topic/headline: "
            "#RussiaKillsFour, #FormatRequirementVertical, bogus.") in note
    remaining = lib.load_story(sid)["meta"]["hashtags"]
    assert remaining == ["#DogShowdown"]


# ---------------------------------------------------------------------------
# start_refresh: topic fallback + background worker notes
# ---------------------------------------------------------------------------

def test_start_refresh_falls_back_to_title(libdir, monkeypatch):
    sid = _make_story(source_topic="")  # old story without source_topic
    lib.update_story_fields(sid, enrichment_status="succeeded")  # idle, not busy
    seen = {}
    done = threading.Event()

    def _fake_worker(sid_, kind, topic, ai_engine=None):
        seen["topic"] = topic
        done.set()

    monkeypatch.setattr(lib, "_refresh_worker", _fake_worker)
    ok, reason = lib.start_refresh(sid, "hashtags")
    assert ok, reason
    assert done.wait(timeout=5)
    assert seen["topic"] == "Dog Showdown Reel"


def test_start_refresh_rejects_bad_kind(libdir):
    sid = _make_story()
    ok, reason = lib.start_refresh(sid, "bogus")
    assert not ok and "bogus" in reason


def test_start_refresh_refuses_while_busy(libdir):
    sid = _make_story()
    lib.update_story_fields(sid, enrichment_status="running", refresh_kind="hashtags")
    ok, reason = lib.start_refresh(sid, "hashtags")
    assert not ok and "already running" in reason
    # The in-flight state is untouched — the loader keeps showing.
    meta = lib.load_story(sid)["meta"]
    assert meta["enrichment_status"] == "running"
    assert meta["refresh_kind"] == "hashtags"


def test_refresh_worker_writes_failure_note(libdir, monkeypatch):
    sid = _make_story()

    def _boom(sid_, topic, ai_engine=None):
        raise RuntimeError("network down")

    monkeypatch.setattr(lib, "refresh_hashtags", _boom)
    lib._refresh_worker(sid, "hashtags", "chubby dogs voting contest")
    meta = lib.load_story(sid)["meta"]
    assert meta["enrichment_status"] == "failed"
    assert meta["refresh_kind"] == ""
    assert "Hashtag refresh failed" in meta["refresh_note"]
    assert "network down" in meta["refresh_note"]


def test_refresh_worker_no_change_state(libdir, monkeypatch):
    sid = _make_story()
    monkeypatch.setattr(lib, "refresh_images",
                        lambda sid_, topic: (False, "No new images found; kept 1 existing."))
    lib._refresh_worker(sid, "images", "chubby dogs voting contest")
    meta = lib.load_story(sid)["meta"]
    assert meta["enrichment_status"] == "no_change"
    assert meta["refresh_kind"] == ""
    assert "No new images" in meta["refresh_note"]


def test_refresh_worker_busy_lock_leaves_state_untouched(libdir):
    sid = _make_story()
    lib.update_story_fields(sid, enrichment_status="running", refresh_kind="hashtags")
    lock = lib._ENRICH_LOCKS.setdefault(sid, threading.Lock())
    assert lock.acquire(blocking=False)
    try:
        lib._refresh_worker(sid, "hashtags", "chubby dogs voting contest")
    finally:
        lock.release()
    meta = lib.load_story(sid)["meta"]
    # The losing worker must not clobber the in-flight "running" state —
    # the UI keeps showing the loader instead of flipping to idle.
    assert meta["enrichment_status"] == "running"
    assert meta["refresh_kind"] == "hashtags"


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
    changed, note = lib._do_media_refresh(sid, "chubby dogs voting contest",
                                          ai_engine="agy_only")
    assert changed is True
    assert isinstance(note, str) and note
    meta = lib.load_story(sid)["meta"]
    assert meta["news_links"] == links, "retry must never touch verified links"
    assert "#NewTag" in meta["hashtags"]
    assert "#DogShowdown" in meta["hashtags"]


def test_do_media_refresh_ai_off_fails_loudly(libdir):
    sid = _make_story()
    with pytest.raises(RuntimeError, match="AI processing is disabled"):
        lib._do_media_refresh(sid, "chubby dogs voting contest", ai_engine=None)


def test_enrich_worker_records_retry_note(libdir):
    sid = _make_story()
    lib._enrich_worker(sid, "chubby dogs voting contest",
                       lambda s, t: (True, "Images updated (2 found)."))
    meta = lib.load_story(sid)["meta"]
    assert meta["enrichment_status"] == "succeeded"
    assert meta["refresh_note"] == "Images updated (2 found)."


def test_enrich_worker_failure_is_failed_not_done(libdir):
    sid = _make_story()

    def _boom(sid_, topic):
        raise RuntimeError("disk gone")

    lib._enrich_worker(sid, "chubby dogs voting contest", _boom)
    meta = lib.load_story(sid)["meta"]
    assert meta["enrichment_status"] == "failed"
    assert "disk gone" in meta["refresh_note"]


def test_start_enrichment_no_topic_is_no_change(libdir):
    sid = _make_story()
    ok, reason = lib.start_enrichment(sid, "")
    assert not ok
    meta = lib.load_story(sid)["meta"]
    assert meta["enrichment_status"] == "no_change"
    assert "No topic" in meta["refresh_note"]


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
    changed, note = lib._do_media_refresh(sid, "chubby dogs voting contest",
                                          ai_engine="agy_only")
    assert changed is True
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


# ---------------------------------------------------------------------------
# Hashtag redesign: AI-found trending first, relevance standard, no script words
# ---------------------------------------------------------------------------

def _trend_story():
    return {
        "meta": {
            "title": "Dog Showdown Reel",
            "source_topic": "dog contest Delhi",
            "source_headline": "64 Dogs Compete in Delhi Contest",
            "news_links": [{"url": "https://example.com/dogs-delhi-contest"}],
        },
        "script": ("[Format Requirement: 9:16 Vertical Reel]\n"
                   "AARAV: chubby dogs voting contest in the park"),
    }


def _dual_engine_module():
    # The real submodule: ``core/__init__`` shadows the ``dual_engine``
    # attribute with the instance, so grab the module from sys.modules
    # after importing it for real.
    import sys
    import core.dual_engine  # noqa: F401
    return sys.modules["core.dual_engine"]


def _fake_trending(monkeypatch, tags=None, boom=False):
    import sys
    import tools.news_fetcher  # noqa: F401 (real submodule, not the instance)
    nf = sys.modules["tools.news_fetcher"]
    if boom:
        def _raise(limit=12):
            raise RuntimeError("net down")
        monkeypatch.setattr(nf.news_fetcher, "fetch_famous_english_hashtags",
                            _raise)
    else:
        monkeypatch.setattr(nf.news_fetcher, "fetch_famous_english_hashtags",
                            lambda limit=12: tags or [])


def test_no_tag_from_raw_script_keywords(libdir, monkeypatch):
    # Script-only words (Aarav, park) must never seed or validate a tag —
    # a trending tag built from screenplay internals is dropped.
    _fake_trending(monkeypatch, tags=[{"tag": "#AaravParkScene"}])
    tags, note = lib._fetch_trending_hashtags("dog contest Delhi",
                                              _trend_story())
    joined = " ".join(tags).lower()
    assert "aarav" not in joined and "park" not in joined
    assert "fallback" in note  # nothing relevant -> headline/topic fallback


def test_trending_tag_kept_only_when_relevant(libdir, monkeypatch):
    _fake_trending(monkeypatch, tags=[{"tag": "#DelhiDogContest"},
                                      {"tag": "#ViralCelebrityGossip"}])
    tags, note = lib._fetch_trending_hashtags("dog contest Delhi",
                                              _trend_story())
    assert "#DelhiDogContest" in tags
    assert "#ViralCelebrityGossip" not in tags
    assert note == "", "trending path used: nothing to report"


def test_trending_lookup_failure_degrades_loudly(libdir, monkeypatch):
    _fake_trending(monkeypatch, boom=True)
    tags, note = lib._fetch_trending_hashtags("dog contest Delhi",
                                              _trend_story())
    assert tags, "fallback must still produce tags"
    assert "Trending-hashtag lookup failed" in note
    assert "fallback" in note


def test_fallback_never_leaves_story_hashtag_less(libdir, monkeypatch):
    _fake_trending(monkeypatch, tags=[])
    tags, _note = lib._fetch_trending_hashtags("", None)
    assert tags == ["#HindiReelStudio"]
    tags2, _ = lib._fetch_trending_hashtags("dog contest Delhi", None)
    assert tags2 and all(t.startswith("#") for t in tags2)


def test_ai_finds_trending_tags_with_news_link_context(libdir, monkeypatch):
    # The AI gets the topic, headline/title, AND the verified news link(s)
    # so it can find what is genuinely trending for this story.
    de = _dual_engine_module()
    seen = {}

    class _FakeEngine:
        def generate(self, prompt="", instructions="", mode="", timeout=None):
            seen["prompt"] = prompt
            seen["mode"] = mode
            return "#DelhiDogShow\n#DogContestDelhi\n", "fake-engine"

    monkeypatch.setattr(de, "dual_engine", _FakeEngine())
    tags = lib._ai_hashtag_suggestions(_trend_story(), "dog contest Delhi",
                                       "codex_only")
    assert seen["mode"] == "codex_only"
    assert "STORY LINKS:" in seen["prompt"]
    assert "https://example.com/dogs-delhi-contest" in seen["prompt"]
    assert "dog contest Delhi" in seen["prompt"]
    assert "64 Dogs Compete in Delhi Contest" in seen["prompt"]
    assert "#DelhiDogShow" in tags
    assert "#DogContestDelhi" in tags


def test_ai_irrelevant_tags_dropped_however_trending(libdir, monkeypatch):
    de = _dual_engine_module()

    class _FakeEngine:
        def generate(self, prompt="", instructions="", mode="", timeout=None):
            return "#DelhiDogShow\n#CryptoMoonShot\n", "fake-engine"

    monkeypatch.setattr(de, "dual_engine", _FakeEngine())
    tags = lib._ai_hashtag_suggestions(_trend_story(), "dog contest Delhi",
                                       "codex_only")
    assert "#DelhiDogShow" in tags
    assert "#CryptoMoonShot" not in tags


def test_ai_empty_result_falls_back_and_note_says_so(libdir, monkeypatch):
    # The AI runs but every suggestion fails relevance -> deterministic
    # fallback, and the note says so.
    de = _dual_engine_module()

    class _FakeEngine:
        def generate(self, prompt="", instructions="", mode="", timeout=None):
            return "#CryptoMoonShot\n", "fake-engine"

    monkeypatch.setattr(de, "dual_engine", _FakeEngine())
    monkeypatch.setattr(lib, "_fetch_trending_hashtags",
                        lambda topic, story=None: (["#DogContestDelhi"], ""))
    sid = _make_story()
    story = lib.load_story(sid)
    tags, note = lib._suggest_hashtags(story, "dog contest Delhi")
    assert tags == ["#DogContestDelhi"]
    assert "deterministic fallback" in note


def test_suggest_hashtags_note_states_ai_path(libdir, monkeypatch):
    de = _dual_engine_module()

    class _FakeEngine:
        def generate(self, prompt="", instructions="", mode="", timeout=None):
            return "#DelhiDogShow\n", "fake-engine"

    monkeypatch.setattr(de, "dual_engine", _FakeEngine())
    sid = _make_story(source_topic="dog contest Delhi",
                      source_headline="64 Dogs Compete in Delhi Contest")
    story = lib.load_story(sid)
    tags, note = lib._suggest_hashtags(story, "dog contest Delhi")
    assert "#DelhiDogShow" in tags
    assert note == "Tags from AI-found trending hashtags."


def test_resolve_engine_mode_prefers_persisted_label(libdir):
    assert lib._resolve_library_engine_mode(None) == "first_local_then_agy"
    assert lib._resolve_library_engine_mode("codex_only") == "codex_only"
    assert lib._resolve_library_engine_mode("Nope") == "first_local_then_agy"
    lib.save_prefs({"library_ai_engine": "Grok Low"})
    assert lib._resolve_library_engine_mode(None) == "grok_low"


# ---------------------------------------------------------------------------
# Share text: news link(s) + hashtags (library_ui composer)
# ---------------------------------------------------------------------------

def _library_ui_module():
    """Import library_ui with a stubbed streamlit (not installed in test env)."""
    import types
    for name in ("streamlit", "streamlit.components", "streamlit.components.v1"):
        sys.modules.setdefault(name, types.ModuleType(name))
    import library_ui
    return library_ui


def test_compose_news_tags_text_links_then_tags():
    lui = _library_ui_module()
    meta = {
        "news_links": [
            {"title": "T1", "url": "https://a.example/1", "source": "S1"},
            {"title": "T2", "url": "https://b.example/2", "source": ""},
        ],
        "hashtags": ["#DogShowdown", "#Reel"],
    }
    assert lui._compose_news_tags_text(meta) == (
        "https://a.example/1\nhttps://b.example/2\n\n#DogShowdown #Reel"
    )


def test_compose_news_tags_text_dedupes_and_skips_blanks():
    lui = _library_ui_module()
    meta = {
        "news_links": [
            {"url": "https://a.example/1"},
            {"url": "https://a.example/1"},
            {"url": ""},
            {"url": "  https://b.example/2  "},
        ],
        "hashtags": [],
    }
    assert lui._compose_news_tags_text(meta) == "https://a.example/1\nhttps://b.example/2"


def test_compose_news_tags_text_tags_only_and_empty():
    lui = _library_ui_module()
    assert lui._compose_news_tags_text({"hashtags": ["#Only"]}) == "#Only"
    assert lui._compose_news_tags_text({}) == ""
    assert lui._compose_news_tags_text({"news_links": [], "hashtags": []}) == ""


# ---------------------------------------------------------------------------
# AI toggle: explicit refresh with AI off fails loudly, never silently falls back
# ---------------------------------------------------------------------------

def test_refresh_hashtags_ai_off_raises_loudly(libdir):
    sid = _make_story()
    with pytest.raises(RuntimeError, match="AI processing is disabled"):
        lib.refresh_hashtags(sid, "chubby dogs voting contest", ai_engine=None)


def test_update_hashtags_ai_off_reports_failed_and_changes_nothing(libdir):
    sid = _make_story()
    lib.update_story_fields(sid, enrichment_status="succeeded")  # idle
    lib._refresh_worker(sid, "hashtags", "chubby dogs voting contest", ai_engine=None)
    meta = lib.load_story(sid)["meta"]
    assert meta["enrichment_status"] == "failed"
    assert meta["refresh_kind"] == ""
    assert "AI processing is disabled" in meta["refresh_note"]
    assert "enable AI processing in Library settings" in meta["refresh_note"]
    assert meta["hashtags"] == ["#DogShowdown"], "failed refresh must change no tags"


def test_ai_hashtag_suggestions_uses_bounded_timeout(libdir, monkeypatch):
    de = _dual_engine_module()  # the module, not the instance
    seen = {}

    class _FakeEngine:
        def generate(self, prompt="", instructions="", mode="", timeout=None):
            seen["timeout"] = timeout
            return "#DogShowdown", "fake-engine"

    monkeypatch.setattr(de, "dual_engine", _FakeEngine())
    story = {"meta": {"title": "Dog Showdown Reel",
                      "source_topic": "chubby dogs voting contest",
                      "source_headline": "Chubby dogs battle in voting contest"}}
    tags = lib._ai_hashtag_suggestions(story, "chubby dogs voting contest", "agy_only")
    assert seen["timeout"] == lib._AI_HASHTAG_TIMEOUT_S
    assert tags == ["#DogShowdown"]


# ---------------------------------------------------------------------------
# Timeouts: slow steps raise TimeoutError naming the step; refreshes stay honest
# ---------------------------------------------------------------------------

def test_run_bounded_times_out_and_names_step():
    import time as _t
    with pytest.raises(TimeoutError, match="slow step"):
        lib._run_bounded(lambda: _t.sleep(30), 0.2, "slow step")


def test_run_bounded_reraises_worker_errors_loudly():
    def _boom():
        raise ValueError("kaput")

    with pytest.raises(ValueError, match="kaput"):
        lib._run_bounded(_boom, 5.0, "step")


def test_refresh_images_timeout_keeps_existing_media(libdir, monkeypatch):
    sid = _make_story()
    lib.update_story_fields(sid, image_urls=["https://img.example/kept.jpg"])

    def _hang(story, topic, tries=3):
        raise TimeoutError("article image fetch timed out after 40s")

    monkeypatch.setattr(lib, "_fetch_images_for_story", _hang)
    changed, note = lib.refresh_images(sid, "chubby dogs voting contest")
    assert changed is False
    assert "timed out" in note and "article image fetch" in note
    meta = lib.load_story(sid)["meta"]
    assert meta["image_urls"] == ["https://img.example/kept.jpg"]


# ---------------------------------------------------------------------------
# Startup recovery: orphaned busy states become interrupted, never stuck
# ---------------------------------------------------------------------------

def test_recover_orphaned_refreshes(libdir, monkeypatch):
    monkeypatch.setattr(lib, "_RECOVERY_DONE", False)
    s1 = _make_story(title="Stuck refresh")
    lib.update_story_fields(s1, enrichment_status="refreshing", refresh_kind="hashtags")
    s2 = _make_story(title="Stuck pending")
    lib.update_story_fields(s2, enrichment_status="pending", refresh_kind="all")
    s3 = _make_story(title="Healthy done")
    lib.update_story_fields(s3, enrichment_status="succeeded", refresh_note="ok")
    assert lib.recover_orphaned_refreshes() == 2
    for sid in (s1, s2):
        meta = lib.load_story(sid)["meta"]
        assert meta["enrichment_status"] == "interrupted"
        assert meta["refresh_kind"] == ""
        assert "interrupted" in meta["refresh_note"]
    healthy = lib.load_story(s3)["meta"]
    assert healthy["enrichment_status"] == "succeeded"
    assert healthy["refresh_note"] == "ok"
    # Idempotent: a second call in the same process recovers nothing.
    assert lib.recover_orphaned_refreshes() == 0


# ---------------------------------------------------------------------------
# Google News redirect resolution -> publisher article images
# ---------------------------------------------------------------------------

_GN_TOKEN = "CBMiTestToken123"
_GN_URL = f"https://news.google.com/rss/articles/{_GN_TOKEN}?oc=5"
_PUBLISHER_URL = "https://example-publisher.com/world/article-1"
_PUBLISHER_IMG = "https://example-publisher.com/img/hero.jpg"


class _GNFakeResp:
    def __init__(self, status_code=200, content=b"", text=""):
        self.status_code = status_code
        self.content = content
        self.text = text
        self.headers = {"content-type": "text/html"}


def test_google_news_article_id_forms():
    assert lib._google_news_article_id(_GN_URL) == _GN_TOKEN
    assert lib._google_news_article_id(
        f"https://news.google.com/articles/{_GN_TOKEN}") == _GN_TOKEN
    assert lib._google_news_article_id(
        f"https://news.google.com/__i/rss/rd/articles/{_GN_TOKEN}?oc=5"
    ) == _GN_TOKEN
    assert lib._google_news_article_id(
        "https://indianexpress.com/article/trending/x-123/") is None
    assert lib._google_news_article_id("https://news.google.com/") is None
    assert lib._google_news_article_id("not a url") is None


def test_resolve_google_news_url_mocked(monkeypatch):
    import httpx
    page = (b'<html><body><c-wiz><div data-n-a-sg="SG123" '
            b'data-n-a-ts="1700000000"></div></c-wiz></body></html>')
    rpc = (')]}}\'\n\n[[["wrb.fr","Fbv4je","[\\"garturlres\\",\\"'
           + _PUBLISHER_URL + '\\",1]"]]]')
    posted = {}

    def fake_get(url, **kw):
        assert "hl=&gl=&ceid=" in url
        return _GNFakeResp(200, content=page, text=page.decode())

    def fake_post(url, **kw):
        posted["body"] = kw.get("content", "")
        assert "batchexecute" in url
        return _GNFakeResp(200, text=rpc)

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)
    assert lib._resolve_google_news_url(_GN_URL) == _PUBLISHER_URL
    # The RPC envelope must carry the token, ts and sg.
    assert _GN_TOKEN in posted["body"]
    assert "SG123" in posted["body"]


def test_resolve_google_news_url_failures_are_none(monkeypatch):
    import httpx
    # Non-Google URL: not our job.
    assert lib._resolve_google_news_url(
        "https://example.com/x") is None
    # Page fetch fails.
    monkeypatch.setattr(httpx, "get",
                        lambda url, **kw: _GNFakeResp(404, content=b"no"))
    assert lib._resolve_google_news_url(_GN_URL) is None
    # Page has no sg/ts tokens.
    monkeypatch.setattr(httpx, "get",
                        lambda url, **kw: _GNFakeResp(
                            200, content=b"<html></html>", text="<html></html>"))
    assert lib._resolve_google_news_url(_GN_URL) is None
    # Network explodes.
    def boom(url, **kw):
        raise RuntimeError("net down")
    monkeypatch.setattr(httpx, "get", boom)
    assert lib._resolve_google_news_url(_GN_URL) is None
    # RPC returns no usable URL.
    monkeypatch.setattr(
        httpx, "get",
        lambda url, **kw: _GNFakeResp(
            200,
            content=(b'<div data-n-a-sg="S" data-n-a-ts="1"></div>'),
            text='<div data-n-a-sg="S" data-n-a-ts="1"></div>'))
    monkeypatch.setattr(httpx, "post",
                        lambda url, **kw: _GNFakeResp(200, text=")]}'\nnope"))
    assert lib._resolve_google_news_url(_GN_URL) is None


def test_resolve_article_url_passthrough_and_fallback(monkeypatch):
    plain = "https://indianexpress.com/article/x-1/"
    assert lib._resolve_article_url(plain) == plain
    assert lib._resolve_article_url("") == ""
    # Resolution failure must never invent a URL: original comes back.
    monkeypatch.setattr(lib, "_resolve_google_news_url",
                        lambda url, timeout=12.0: None)
    assert lib._resolve_article_url(_GN_URL) == _GN_URL


def test_og_image_resolves_google_news_first(monkeypatch):
    import httpx
    html = (f'<html><head><meta property="og:image" content="{_PUBLISHER_IMG}">'
            '</head></html>')

    def fake_get(url, **kw):
        assert url == _PUBLISHER_URL, url  # resolved, not the wrapper
        return _GNFakeResp(200, content=html.encode(), text=html)

    monkeypatch.setattr(lib, "_resolve_google_news_url",
                        lambda url, timeout=12.0: _PUBLISHER_URL)
    monkeypatch.setattr(httpx, "get", fake_get)
    assert lib._og_image(_GN_URL) == _PUBLISHER_IMG


def _sandbox_proxy_workaround(monkeypatch):
    # This sandbox's no_proxy carries bracketed IPv6 entries that httpx
    # 0.28.1 cannot parse (InvalidURL in Client.__init__); the user's Mac
    # has no such entries. Neutralize for live-network tests only.
    monkeypatch.setenv("no_proxy", "localhost,127.0.0.1,::1")
    monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1,::1")


def test_live_google_news_url_resolves_to_publisher(monkeypatch):
    _sandbox_proxy_workaround(monkeypatch)
    url = ("https://news.google.com/rss/articles/"
           "CBMingJBVV95cUxOZG1HQU9WaG42S01RVWZjNTlTQVBPSVd3WU05N0VHTUpkOWJhOENfS3hQUnpJR25SVGsyR3FpUjEtOE82WWVhU2tqQ2h1UGhjNG9OeHRGZVR0eHBRNmZoR1dVTzNoQ3NZYmpDX25GbEwyam5ENUctNmx3eHV0eXRjU0t2OGpkbGpsQlNWU01qUnpCTzZQeGhFMU4wcUZRQkRQRnpXQ3VrUGZKSEdhbHMtSzQ2YXJjblVPc1BMcFBodGpEQVgwRHdFZzg2SXRGeFYydnVPdVVzSmFpa1FNRTU5QWNTLW42S0dha2U1c0NGUDd1bmhmMW1EcUV5aGZZV0t1TEttVGJpMmJXam9oei1fbUN0QURGQ2F1VnlaLUpR0gGjAkFVX3lxTE5jLTdfUUNYS1c1emJNRlpQc0sxdkhzTDk3OVJ1S1BDcEt2bGRTWmxxM2RaQ1plY1B6bEVnU1B1cXdOQWQzNHVoa3MwekloT1dwVW1JRXY0dGZNZzRsczZQS0h4bE1NT0FlTWNqUEVkWDAyS29pNFNab0hKQV9ScmNrdjRKNWZsRFM2R1FkM2pRbEhETElLRGtWaV9Xd3lNdWpXOC1VQkxBazFTOWhVeUVZRG8xQm5EeTlWM1Bxb1RFZzN1S3BZdk9CVi1yV1B6QU1yWURTaGJyQ3Y4Tkw4WllqSUs3LXlaa3BmN0NlN0tvOU9hUEt1UDZPN2JzX0ZnQnhOZms5d2NucDY4SjVOcXlQQ0ZWanZieWJjYURxZ1hHNkhGTQ"
           "?oc=5")
    try:
        resolved = lib._resolve_google_news_url(url, timeout=20.0)
    except Exception as e:  # noqa: BLE001 - network-dependent
        pytest.skip(f"network unavailable: {e}")
    assert resolved is not None, "Google changed the RPC; resolution failed"
    assert resolved.startswith("https://timesofindia.indiatimes.com/")
    # And the publisher page yields its og:image through the real path.
    try:
        img = lib._og_image(url, timeout=20.0)
    except Exception as e:  # noqa: BLE001 - network-dependent
        pytest.skip(f"network unavailable: {e}")
    assert img is not None and img.startswith("https://"), img


def test_live_indianexpress_direct_url_og_image(monkeypatch):
    _sandbox_proxy_workaround(monkeypatch)
    url = ("https://indianexpress.com/article/trending/trending-in-india/"
           "mumbai-metro-installs-touchless-spit-bin-spitting-fine-irony-10900972/")
    try:
        img = lib._og_image(url, timeout=20.0)
    except Exception as e:  # noqa: BLE001 - network-dependent
        pytest.skip(f"network unavailable: {e}")
    assert img == ("https://images.indianexpress.com/2026/09/"
                   "Mumbai-Metro-spit-bin.jpg"), img
