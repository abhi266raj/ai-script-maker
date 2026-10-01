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
sys.path.insert(0, str(Path(__file__).resolve().parent))
import story_library as lib  # noqa: E402
from _fake_images import fetch_for  # noqa: E402


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


def _settle_enrichment(sid):
    """Production-faithful setup for manual-refresh tests.

    ``save_story`` seeds ``enrichment_status="pending"`` and production
    always settles it via ``start_enrichment`` before any manual refresh
    can run. Tests that drive ``_refresh_worker`` directly must settle
    the seed first, otherwise the legacy fallback reads it as a phantom
    busy "enrich" kind.
    """
    lib._set_refresh_busy(sid, "enrich")
    lib._finish_refresh(sid, "enrich", "succeeded", "save-time enrichment done")
    # Drain the settled outcome: like the UI's first render, the toast has
    # been "shown" — manual-refresh tests start from a clean idle state.
    lib.update_story_fields(sid, refresh_outcome_pending=[])


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


def test_start_refresh_refuses_while_busy_new_format(libdir):
    # Same contract on the per-kind format (#53/#54): the same kind
    # re-kicked while busy is refused and the in-flight state is kept.
    sid = _make_story()
    _settle_enrichment(sid)
    lib._set_refresh_busy(sid, "hashtags")
    ok, reason = lib.start_refresh(sid, "hashtags")
    assert not ok and "already running" in reason
    meta = lib.load_story(sid)["meta"]
    assert meta["enrichment_status"] == "running"
    assert lib.refresh_busy_kinds(meta) == {"hashtags"}


def test_refresh_worker_writes_failure_note(libdir, monkeypatch):
    sid = _make_story()

    def _boom(sid_, topic, ai_engine=None):
        raise RuntimeError("network down")

    monkeypatch.setattr(lib, "refresh_hashtags", _boom)
    # Production flow: the starter marks the kind busy, the worker only
    # finishes it. (Without the mark, the save-seeded legacy "pending"
    # state would read as a phantom busy kind.)
    _settle_enrichment(sid)
    lib._set_refresh_busy(sid, "hashtags")
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
    _settle_enrichment(sid)
    lib._set_refresh_busy(sid, "images")
    lib._refresh_worker(sid, "images", "chubby dogs voting contest")
    meta = lib.load_story(sid)["meta"]
    assert meta["enrichment_status"] == "no_change"
    assert meta["refresh_kind"] == ""
    assert "No new images" in meta["refresh_note"]


def test_refresh_worker_busy_lock_leaves_state_untouched(libdir):
    sid = _make_story()
    _settle_enrichment(sid)
    lib._set_refresh_busy(sid, "hashtags")
    lock = lib._ENRICH_LOCKS.setdefault((sid, "hashtags"), threading.Lock())
    assert lock.acquire(blocking=False)
    try:
        lib._refresh_worker(sid, "hashtags", "chubby dogs voting contest")
    finally:
        lock.release()
    meta = lib.load_story(sid)["meta"]
    # The losing worker must not clobber the in-flight busy state — the UI
    # keeps showing the spinner instead of flipping to idle.
    assert meta["enrichment_status"] == "running"
    assert lib.refresh_busy_kinds(meta) == {"hashtags"}


# ---------------------------------------------------------------------------
def test_enrich_worker_records_work_note(libdir):
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
    # (url, alt) pairs: og:image first, then in-article photos;
    # relative + lazy-load absolutized.
    urls = [u for u, _ in found]
    alts = {u: a for u, a in found}
    assert urls[0] == "https://publisher.example/hero.jpg"
    assert "https://publisher.example/photos/dog1.jpg" in urls
    assert "https://cdn.example/lazy/dog2.jpg" in urls
    # Alt text is captured for in-article photos; hero images have none.
    assert alts["https://publisher.example/photos/dog1.jpg"] == "dogs"
    assert alts["https://publisher.example/hero.jpg"] is None
    # Logos and tracking pixels are filtered out.
    assert not any("logo" in u or "pixel" in u for u in urls)


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
    # Image fetches feed the content/visual dedupe: distinct bytes per URL.
    monkeypatch.setattr(lib, "_fetch_image_bytes", fetch_for())
    changed, note = lib.refresh_images(sid, "chubby dogs voting contest")
    assert changed is True
    meta = lib.load_story(sid)["meta"]
    # Existing URLs keep their order; new ones are appended, deduplicated.
    assert meta["image_urls"] == ["https://img.example/old.jpg",
                                 "https://img.example/new.jpg"]
    # Content hashes are persisted alongside, aligned by position.
    assert len(meta["image_hashes"]) == 2
    assert meta["image_hashes"][0] != meta["image_hashes"][1]
    # Perceptual hashes ride alongside, aligned by position as well.
    assert len(meta["image_phashes"]) == 2
    assert all(meta["image_phashes"])
    assert "Added 1 new image(s)" in note and "kept 1 existing" in note


def test_refresh_images_keeps_existing_when_fetch_empty(libdir, monkeypatch):
    sid = _make_story(image_urls=["https://img.example/old.jpg"])
    monkeypatch.setattr(lib, "_fetch_images_for_story",
                        lambda story, topic, **k: [])
    # Issue #57: the merge always runs, so missing hashes for the stored
    # image are backfilled (one-time network cost, then persisted) even
    # though the fetch found nothing new.
    monkeypatch.setattr(lib, "_fetch_image_bytes", fetch_for())
    changed, note = lib.refresh_images(sid, "chubby dogs voting contest")
    assert changed is True  # backfilled hashes were persisted
    meta = lib.load_story(sid)["meta"]
    assert meta["image_urls"] == ["https://img.example/old.jpg"]
    assert len(meta["image_hashes"]) == 1 and all(meta["image_hashes"])
    assert len(meta["image_phashes"]) == 1 and all(meta["image_phashes"])
    assert "No new images found" in note and "kept 1 existing" in note


def test_refresh_images_no_change_when_nothing_new(libdir, monkeypatch):
    sid = _make_story(image_urls=["https://img.example/old.jpg"])
    monkeypatch.setattr(lib, "_fetch_images_for_story",
                        lambda story, topic, **k: ["https://img.example/old.jpg"])
    # Issue #57: the stored image's missing hashes are backfilled even
    # though the only candidate is a URL-dupe — that backfill is
    # persisted, so the refresh reports a change.
    monkeypatch.setattr(lib, "_fetch_image_bytes", fetch_for())
    changed, note = lib.refresh_images(sid, "chubby dogs voting contest")
    assert changed is True
    meta = lib.load_story(sid)["meta"]
    assert meta["image_urls"] == ["https://img.example/old.jpg"]
    assert all(meta["image_hashes"]) and all(meta["image_phashes"])


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
# delete confirmation popover: Apple-style, red Yes / normal No
# ---------------------------------------------------------------------------

class _FakeCtx:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeSt:
    """Minimal streamlit stand-in to exercise _delete_popover logic."""

    def __init__(self, clicks=()):
        self._clicks = set(clicks)
        self.session_state = {}
        self.errors = []
        self.successes = []
        self.reran = False
        self.popover_kwargs = None
        self.popovers = []  # every popover's kwargs, in render order
        self.buttons = []  # (label, key) in render order
        self.button_kwargs = []  # full kwargs per button, in render order
        self.link_buttons = []  # (label, url) in render order
        self.codes = []
        self.markup = []  # raw markdown html, in render order
        self.toasts = []  # (message, icon) in render order

    def markdown(self, *a, **k):
        self.markup.append(a[0] if a else "")

    def caption(self, *a, **k):
        pass

    def success(self, msg):
        self.successes.append(msg)

    def error(self, msg):
        self.errors.append(msg)

    def rerun(self):
        self.reran = True

    def button(self, label, key=None, on_click=None, **k):
        self.buttons.append((label, key))
        self.button_kwargs.append({"label": label, "key": key, **k})
        if key in self._clicks:
            if on_click is not None:
                on_click()
            return True
        return False

    def toast(self, msg, icon=None):
        self.toasts.append((msg, icon))

    def columns(self, spec):
        n = spec if isinstance(spec, int) else len(spec)
        return [_FakeCtx() for _ in range(n)]

    def popover(self, label, **k):
        self.popover_kwargs = {"label": label, **k}
        self.popovers.append(self.popover_kwargs)
        return _FakeCtx()

    def link_button(self, label, url, **k):
        self.link_buttons.append((label, url))
        return False

    def code(self, body, **k):
        self.codes.append(body)


def _ui_with_fake_st(clicks=()):
    """Import library_ui bound to a fake streamlit; restores sys.modules."""
    import types
    saved = dict(sys.modules)
    fake = _FakeSt(clicks)
    try:
        fake_mod = types.ModuleType("streamlit")
        for name in ("markdown", "caption", "success", "error", "rerun",
                     "button", "columns", "popover", "link_button", "code",
                     "toast"):
            setattr(fake_mod, name, getattr(fake, name))
        fake_mod.session_state = fake.session_state
        sys.modules["streamlit"] = fake_mod
        sys.modules.pop("library_ui", None)
        import library_ui
        return library_ui, fake
    finally:
        sys.modules.clear()
        sys.modules.update(saved)


def _pop_kwargs(**kw):
    d = dict(trigger_label="Delete", popover_key="dp",
             title="Delete this story?", message="M",
             destructive_label="Delete story")
    d.update(kw)
    return d


def test_delete_popover_renders_cancel_and_destructive_verb():
    lui, fake = _ui_with_fake_st()
    lui._delete_popover(**_pop_kwargs(on_yes=lambda: None))
    assert fake.popover_kwargs["label"] == "Delete"
    assert fake.popover_kwargs["key"] == "dp"
    assert fake.popover_kwargs["on_change"] == "rerun"
    # #58: explicit red verb + standard Cancel, never Yes/No. Cancel leads.
    assert fake.buttons == [("Cancel", "dp-no"), ("Delete story", "dp-yes")]


def test_delete_popover_destructive_runs_callback_and_closes():
    lui, fake = _ui_with_fake_st(clicks=("dp-yes",))
    fired = []
    kw = _pop_kwargs(on_yes=lambda: fired.append(1))
    lui._delete_popover(**kw)  # run 1: destructive clicked -> close + go flags armed
    assert fired == []
    assert fake.session_state["dp"] is False
    assert fake.session_state["dp-go"] is True
    fake._clicks.clear()
    lui._delete_popover(**kw)  # run 2: armed flag consumed -> on_yes runs
    assert fired == [1]
    assert fake.session_state.get("dp") is False
    assert fake.errors == []


def test_delete_popover_cancel_dismisses_without_deleting():
    lui, fake = _ui_with_fake_st(clicks=("dp-no",))
    fired = []
    lui._delete_popover(**_pop_kwargs(on_yes=lambda: fired.append(1)))
    assert fired == []
    assert fake.session_state["dp"] is False
    assert "dp-go" not in fake.session_state


def test_delete_popover_destructive_failure_is_loud():
    lui, fake = _ui_with_fake_st(clicks=("dp-yes",))

    def _boom():
        raise RuntimeError("disk gone")

    kw = _pop_kwargs(on_yes=_boom)
    lui._delete_popover(**kw)  # run 1: arm the confirmation
    fake._clicks.clear()
    lui._delete_popover(**kw)  # run 2: on_yes raises -> loud error, popover reopened
    assert fake.errors == ["Delete failed: disk gone"]
    assert fake.session_state.get("dp") is True


def test_confirm_delete_story_deletes_and_cleans_session(libdir):
    lui, fake = _ui_with_fake_st()
    sid = _make_story()
    fake.session_state["lib_selected_story"] = sid
    lui._confirm_delete_story(sid)
    assert not (libdir / "stories" / f"{sid}.md").exists()
    assert "lib_selected_story" not in fake.session_state
    assert fake.successes == ["Story deleted."]


def test_confirm_delete_story_missing_file_fails_loudly(libdir):
    lui, fake = _ui_with_fake_st()
    with pytest.raises(RuntimeError, match="could not be removed"):
        lui._confirm_delete_story("nope-not-here")
    assert fake.successes == []


def test_confirm_delete_all_removes_everything(libdir):
    lui, fake = _ui_with_fake_st()
    _make_story(title="Story A")
    _make_story(title="Story B")
    lui._confirm_delete_all()
    assert list((libdir / "stories").glob("*.md")) == []
    assert fake.successes == ["Deleted 2 stories."]
# remove_hashtag / remove_news_link: manual per-item removal (fail loudly)
# ---------------------------------------------------------------------------

def test_remove_hashtag_removes_only_that_tag(libdir):
    sid = _make_story(hashtags=["#DogShowdown", "#ChubbyDogs", "#Funny"])
    assert lib.remove_hashtag(sid, "#ChubbyDogs") is True
    assert lib.load_story(sid)["meta"]["hashtags"] == ["#DogShowdown", "#Funny"]


def test_remove_hashtag_unknown_story_raises(libdir):
    with pytest.raises(ValueError):
        lib.remove_hashtag("nope-not-a-story", "#DogShowdown")


def test_remove_hashtag_missing_tag_raises(libdir):
    sid = _make_story(hashtags=["#DogShowdown"])
    with pytest.raises(ValueError):
        lib.remove_hashtag(sid, "#Nope")


def test_remove_hashtag_leaves_everything_else_untouched(libdir):
    sid = _make_story(hashtags=["#A", "#B"],
                      news_links=[{"title": "T", "url": "https://example.com/t"}],
                      script_md="AARAV: hello")
    lib.remove_hashtag(sid, "#A")
    meta = lib.load_story(sid)["meta"]
    assert meta["hashtags"] == ["#B"]
    assert meta["news_links"] == [{"title": "T", "url": "https://example.com/t"}]
    assert meta["title"] == "Dog Showdown Reel"


def test_remove_news_link_removes_only_that_link(libdir):
    sid = _make_story(news_links=[
        {"title": "A", "url": "https://example.com/a", "source": "Ex"},
        {"title": "B", "url": "https://example.com/b", "source": "Ex"},
    ])
    assert lib.remove_news_link(sid, "https://example.com/a") is True
    remaining = lib.load_story(sid)["meta"]["news_links"]
    assert [lk["url"] for lk in remaining] == ["https://example.com/b"]


def test_remove_news_link_unknown_story_raises(libdir):
    with pytest.raises(ValueError):
        lib.remove_news_link("nope-not-a-story", "https://example.com/a")


def test_remove_news_link_missing_url_raises(libdir):
    sid = _make_story(news_links=[{"title": "A", "url": "https://example.com/a"}])
    with pytest.raises(ValueError):
        lib.remove_news_link(sid, "https://example.com/zzz")


def test_remove_news_link_last_link_allowed(libdir):
    sid = _make_story(news_links=[{"title": "A", "url": "https://example.com/a"}],
                      hashtags=["#DogShowdown"])
    assert lib.remove_news_link(sid, "https://example.com/a") is True
    assert lib.load_story(sid)["meta"]["news_links"] == []


# ---------------------------------------------------------------------------
# reset: destructive clear + fresh re-fetch of all three rows
# ---------------------------------------------------------------------------

class _FakeArticle:
    def __init__(self, title, link, source):
        self.title = title
        self.link = link
        self.source = source


def _reset_mocks(monkeypatch, tags, images, articles):
    monkeypatch.setattr(lib, "_suggest_hashtags",
                        lambda story, topic, ai_engine=None: (tags, "AI tags."))
    monkeypatch.setattr(lib, "_fetch_images_for_story",
                        lambda story, topic, **k: images)
    monkeypatch.setattr(lib, "_fetch_news_articles",
                        lambda topic, limit=6: articles)
    # Reset now content-hashes fresh images: distinct bytes per URL.
    monkeypatch.setattr(lib, "_fetch_image_bytes", fetch_for())


def test_do_reset_clears_and_refetches_all_rows(libdir, monkeypatch):
    sid = _make_story(
        hashtags=["#StaleTag"],
        image_urls=["https://img.example/stale.jpg"],
        news_links=[{"title": "Old", "url": "https://example.com/old",
                     "source": "Ex"}],
        script_md="AARAV: hello",
    )
    lib.update_story_fields(sid, uploaded_images=["upload1.png"])
    _reset_mocks(monkeypatch,
                 tags=["#FreshOne", "#FreshTwo"],
                 images=["https://img.example/fresh.jpg"],
                 articles=[_FakeArticle("New story", "https://example.com/new",
                                        "Ex")])
    changed, note = lib._do_reset(sid, "chubby dogs voting contest",
                                  ai_engine="agy_only")
    assert changed is True
    assert "2 hashtag(s), 1 image(s) and 1 news link(s)" in note
    story = lib.load_story(sid)
    meta = story["meta"]
    # Stale rows discarded, fresh rows in place.
    assert meta["hashtags"] == ["#FreshOne", "#FreshTwo"]
    assert meta["image_urls"] == ["https://img.example/fresh.jpg"]
    assert meta["news_links"] == [{"title": "New story",
                                   "url": "https://example.com/new",
                                   "source": "Ex"}]
    # The reset also stored the fresh image's perceptual hash.
    assert len(meta["image_phashes"]) == 1 and all(meta["image_phashes"])
    # Never touched: manual uploads, screenplay, story content.
    assert meta["uploaded_images"] == ["upload1.png"]
    assert "AARAV: hello" in story["script"]


def test_do_reset_ai_off_fails_loudly_and_changes_nothing(libdir):
    sid = _make_story(hashtags=["#KeepMe"],
                      image_urls=["https://img.example/k.jpg"])
    with pytest.raises(RuntimeError, match="AI processing is disabled"):
        lib._do_reset(sid, "chubby dogs voting contest", ai_engine=None)
    meta = lib.load_story(sid)["meta"]
    assert meta["hashtags"] == ["#KeepMe"]
    assert meta["image_urls"] == ["https://img.example/k.jpg"]


def test_do_reset_unknown_story_raises(libdir):
    with pytest.raises(RuntimeError, match="story not found"):
        lib._do_reset("nope-not-a-story", "topic", ai_engine="agy_only")


def test_do_reset_no_change_when_refetch_identical(libdir, monkeypatch):
    sid = _make_story(hashtags=["#Same"],
                      image_urls=["https://img.example/s.jpg"],
                      news_links=[{"title": "T", "url": "https://example.com/t",
                                   "source": "Ex"}])
    _reset_mocks(monkeypatch, tags=["#Same"],
                 images=["https://img.example/s.jpg"],
                 articles=[_FakeArticle("T", "https://example.com/t", "Ex")])
    changed, note = lib._do_reset(sid, "chubby dogs voting contest",
                                  ai_engine="agy_only")
    assert changed is False
    assert "nothing changed" in note


def test_do_reset_empty_results_clear_rows(libdir, monkeypatch):
    sid = _make_story(hashtags=["#Old"],
                      image_urls=["https://img.example/o.jpg"],
                      news_links=[{"title": "T", "url": "https://example.com/t"}])
    _reset_mocks(monkeypatch, tags=[], images=[], articles=[])
    changed, note = lib._do_reset(sid, "chubby dogs voting contest",
                                  ai_engine="agy_only")
    assert changed is True
    meta = lib.load_story(sid)["meta"]
    assert meta["hashtags"] == []
    assert meta["image_urls"] == []
    assert meta["news_links"] == []
    assert "row cleared" in note


def test_start_refresh_reset_runs_to_honest_state(libdir, monkeypatch):
    import time
    sid = _make_story(hashtags=["#Old"])
    lib.update_story_fields(sid, enrichment_status="succeeded")  # idle, not busy
    _reset_mocks(monkeypatch, tags=["#New"], images=[], articles=[])
    ok, reason = lib.start_refresh(sid, "reset", ai_engine="agy_only")
    assert ok, reason
    for _ in range(200):
        meta = lib.load_story(sid)["meta"]
        if meta.get("enrichment_status") not in lib.BUSY_STATES:
            break
        time.sleep(0.05)
    meta = lib.load_story(sid)["meta"]
    assert meta["enrichment_status"] == "succeeded"
    assert meta["refresh_kind"] == ""
    assert meta["hashtags"] == ["#New"]
    assert "Reset re-fetched" in meta["refresh_note"]


def test_refresh_worker_reset_failure_is_failed_not_done(libdir):
    # AI off -> _do_reset raises the disabled message -> failed, and the
    # stored rows are untouched (the write never happened).
    sid = _make_story(hashtags=["#KeepMe"])
    _settle_enrichment(sid)
    lib._set_refresh_busy(sid, "reset")
    lib._refresh_worker(sid, "reset", "chubby dogs voting contest",
                        ai_engine=None)
    meta = lib.load_story(sid)["meta"]
    assert meta["enrichment_status"] == "failed"
    assert meta["refresh_kind"] == ""
    assert "Reset refresh failed" in meta["refresh_note"]
    assert "AI processing is disabled" in meta["refresh_note"]
    assert meta["hashtags"] == ["#KeepMe"]


# ---------------------------------------------------------------------------
# whatsapp share link + confirm popover (fail_label)
# ---------------------------------------------------------------------------

def test_whatsapp_share_url_carries_exact_text():
    lui, _fake = _ui_with_fake_st()
    text = ("https://example.com/a\nhttps://example.com/b\n\n"
            "#DogShowdown #Funny")
    url = lui._whatsapp_share_url(text)
    # #28: deep-link into the installed Mac app, not the browser (wa.me).
    assert url.startswith("whatsapp://send?text=")
    assert "wa.me" not in url
    import urllib.parse as up
    assert up.unquote(url.split("?text=", 1)[1]) == text


def test_confirm_popover_fail_label_is_used():
    lui, fake = _ui_with_fake_st(clicks=("rp-yes",))

    def _boom():
        raise RuntimeError("nope")

    kw = dict(trigger_label="Reset", popover_key="rp", title="T", message="M",
              on_yes=_boom, fail_label="Reset", destructive_label="Reset media")
    lui._confirm_popover(**kw)  # run 1: arm the confirmation
    fake._clicks.clear()
    lui._confirm_popover(**kw)  # run 2: on_yes raises -> loud error, reopened
    assert fake.errors == ["Reset failed: nope"]
    assert fake.session_state.get("rp") is True


# ---------------------------------------------------------------------------
# share / copy dropdowns (fake streamlit) — #27/#28/#29/#30
# ---------------------------------------------------------------------------

def test_share_popover_renders_copy_and_whatsapp(monkeypatch):
    lui, fake = _ui_with_fake_st()
    copies = []
    monkeypatch.setattr(lui, "_copy_button",
                        lambda label, text, key: copies.append((label, text, key)))
    share_text = "https://example.com/a\n\n#DogShowdown #Funny"
    lui._render_share_popover("sid1", share_text)
    # Popover trigger is the self-describing dropdown (#30).
    assert fake.popover_kwargs["label"] == "Share"
    assert fake.popover_kwargs["key"] == "lib_sharepop_sid1"
    # Copy button gets the exact share text…
    assert copies == [("Copy News Link + Hashtags", share_text, "n-sid1")]
    # …and the WhatsApp link carries the exact same text, URL-encoded,
    # deep-linking into the installed Mac app (#28).
    assert fake.link_buttons == [("Send via WhatsApp",
                                  lui._whatsapp_share_url(share_text))]
    assert fake.link_buttons[0][1].startswith("whatsapp://send?text=")
    import urllib.parse as up
    sent = up.unquote(fake.link_buttons[0][1].split("?text=", 1)[1])
    assert sent == share_text
    # No share-text preview block anymore (#27).
    assert fake.codes == []


def test_share_popover_empty_state(monkeypatch):
    lui, fake = _ui_with_fake_st()
    monkeypatch.setattr(lui, "_copy_button",
                        lambda label, text, key: (_ for _ in ()).throw(
                            AssertionError("copy must not render")))
    lui._render_share_popover("sid1", "")
    assert fake.popover_kwargs["label"] == "Share"
    assert fake.link_buttons == []
    assert fake.codes == []


def test_copy_popover_renders_four_actions(monkeypatch):
    lui, fake = _ui_with_fake_st()
    copies = []
    monkeypatch.setattr(lui, "_copy_button",
                        lambda label, text, key: copies.append((label, text, key)))
    meta = {"hashtags": ["#DogShowdown", "#Funny"],
            "image_urls": ["https://example.com/pic.jpg"],
            "uploaded_images": []}
    script_md = "**Hook:** hello"
    lui._render_copy_popover("sid1", meta, script_md)
    assert fake.popover_kwargs["label"] == "Copy"
    assert fake.popover_kwargs["key"] == "lib_copypop_sid1"
    labels = [c[0] for c in copies]
    assert labels == ["Script", "Script + Tags", "Script + Media", "All"]
    keys = [c[2] for c in copies]
    assert keys == ["s-sid1", "h-sid1", "m-sid1", "a-sid1"]
    # Copied texts are identical to the old flat buttons (#30).
    plain = lui._script_plain_text(script_md)
    assert copies[0][1] == plain
    assert copies[1][1] == lui._compose_share_text(meta, script_md, False, True)
    assert copies[2][1] == lui._compose_share_text(meta, script_md, True, False)
    assert copies[3][1] == lui._compose_share_text(meta, script_md, True, True)
    assert "#DogShowdown #Funny" in copies[1][1]
    assert "https://example.com/pic.jpg" in copies[2][1]


def test_copy_popover_empty_state(monkeypatch):
    lui, fake = _ui_with_fake_st()
    monkeypatch.setattr(lui, "_copy_button",
                        lambda label, text, key: (_ for _ in ()).throw(
                            AssertionError("copy must not render")))
    lui._render_copy_popover("sid1", {}, "")
    assert fake.popover_kwargs["label"] == "Copy"
    assert fake.codes == []


def test_action_dropdowns_have_no_actions_header(monkeypatch):
    # #29: the vague "Actions" lib-section header is gone — the Share /
    # Copy triggers are self-describing. #46: the dropdowns now live in
    # the single detail toolbar row, so the old separate-row helper is
    # gone; assert at the source level that no "Actions" header markup
    # remains and the helper was removed.
    import pathlib
    src = (pathlib.Path(__file__).resolve().parent.parent
           / "library_ui.py").read_text()
    assert '<div class="lib-section">Actions</div>' not in src
    assert "_render_action_dropdowns" not in src


def test_reset_popover_idle_wiring():
    lui, fake = _ui_with_fake_st()
    lui._render_reset_popover("sid1", set(), ai_engine=None)
    assert fake.popover_kwargs["label"] == "Reset"
    assert fake.popover_kwargs["key"] == "lib_resetpop_sid1"
    assert fake.popover_kwargs["disabled"] is False
    assert fake.popover_kwargs["on_change"] == "rerun"
    # #58: explicit red verb + standard Cancel, never Yes/No.
    assert ("Reset media", "lib_resetpop_sid1-yes") in fake.buttons
    assert ("Cancel", "lib_resetpop_sid1-no") in fake.buttons


def test_reset_popover_busy_label_stable_and_disabled():
    # #53: the trigger label NEVER changes to "Resetting…" — it keeps
    # "Reset", shows the CSS spinner and stays disabled while resetting.
    lui, fake = _ui_with_fake_st()
    lui._render_reset_popover("sid1", {"reset"}, ai_engine=None)
    assert fake.popover_kwargs["label"] == "Reset"
    assert fake.popover_kwargs["disabled"] is True


def test_reset_popover_blocked_by_other_kind_no_spinner():
    # #54: Reset is exclusive — disabled (but no spinner: it is blocked,
    # not working) while another kind runs.
    lui, fake = _ui_with_fake_st()
    lui._render_reset_popover("sid1", {"hashtags"}, ai_engine=None)
    assert fake.popover_kwargs["label"] == "Reset"
    assert fake.popover_kwargs["disabled"] is True
    assert 'data-marker="lib-spin-reset"' not in "".join(fake.markup)


def test_reset_popover_destructive_kicks_reset_refresh(monkeypatch):
    lui, fake = _ui_with_fake_st(clicks=("lib_resetpop_sid1-yes",))
    calls = []
    monkeypatch.setattr(lui.lib, "start_refresh",
                        lambda sid, kind, ai_engine=None: (
                            calls.append((sid, kind, ai_engine)) or (True, "")))
    kw = dict(story_id="sid1", busy_kinds=set(), ai_engine="eng1")
    lui._render_reset_popover(**kw)  # run 1: destructive clicked -> flags armed
    fake._clicks.clear()
    lui._render_reset_popover(**kw)  # run 2: confirmation consumed
    assert calls == [("sid1", "reset", "eng1")]
    assert fake.errors == []
    assert fake.session_state.get("lib_resetpop_sid1") is not True


def test_reset_popover_destructive_failure_is_loud(monkeypatch):
    lui, fake = _ui_with_fake_st(clicks=("lib_resetpop_sid1-yes",))
    monkeypatch.setattr(lui.lib, "start_refresh",
                        lambda sid, kind, ai_engine=None: (False, "boom"))
    kw = dict(story_id="sid1", busy_kinds=set(), ai_engine=None)
    lui._render_reset_popover(**kw)  # run 1: arm the confirmation
    fake._clicks.clear()
    lui._render_reset_popover(**kw)  # run 2: start fails -> loud, reopened
    assert fake.errors == ["Reset failed: Could not start the reset: boom"]
    assert fake.session_state.get("lib_resetpop_sid1") is True


# ---------------------------------------------------------------------------
# v1.5.2 — detail visual hierarchy: × floats OVER its card (z-axis),
# uniform card baselines, one 38px action-button system.
# ---------------------------------------------------------------------------

def _capture_library_css(lui, monkeypatch):
    """Capture the <style> HTML emitted by inject_library_css."""
    chunks = []
    monkeypatch.setattr(lui.st, "markdown",
                        lambda *a, **k: chunks.append(a[0] if a else ""))
    lui.inject_library_css()
    return "\n".join(chunks)


def test_overlay_button_marker_immediately_precedes_button(monkeypatch):
    """DOM prerequisite for the × overlay: the marker element must be the
    immediate predecessor of the button element, otherwise the
    adjacent-sibling CSS selector has nothing to match and the × would
    render as an in-flow button beside the card."""
    lui, _fake = _ui_with_fake_st()
    seq = []
    monkeypatch.setattr(lui.st, "markdown",
                        lambda *a, **k: seq.append(("md", a[0] if a else "")))
    orig_button = lui.st.button

    def rec_button(label, key=None, **k):
        seq.append(("btn", label, key))
        return orig_button(label, key=key, **k)

    monkeypatch.setattr(lui.st, "button", rec_button)
    assert lui._overlay_button("lib-x-r", "k1", "×", help="Remove x") is False
    assert [s[0] for s in seq] == ["md", "btn"]
    assert 'data-marker="lib-x-r"' in seq[0][1]
    assert seq[1][1:] == ("×", "k1")


def test_overlay_css_pins_button_over_card_not_beside_it(monkeypatch):
    """The × overlay CSS must pin the button's element container absolute
    over the card with a z-index. The selector must follow Streamlit's real
    DOM: stLayoutWrapper > stHorizontalBlock > stColumn (Streamlit names
    the testid "stColumn", not "column"), and the button container is the
    adjacent sibling of the marker's element container. The old
    child-selector forms never matched, leaving the × as a normal button
    beside the card — proven broken by real-browser screenshots."""
    lui, _fake = _ui_with_fake_st()
    css = _capture_library_css(lui, monkeypatch)
    # Braces balanced — a truncated <style> block would silently drop rules.
    assert css.count("{") == css.count("}")
    assert 'div[data-testid="stColumn"]' in css  # positioning context set
    assert 'div[data-testid="column"]' not in css  # Streamlit never uses this
    present = ('div[data-testid="stElementContainer"]:has([data-marker="lib-x-r"])\n'
               '        + div[data-testid="stElementContainer"]')
    assert present in css  # adjacent-sibling overlay, per real DOM
    for needle in ("position: absolute", "z-index: 10", "top: 4px",
                   "backdrop-filter: blur(6px)"):
        assert needle in css, needle


def test_image_cards_share_one_baseline(monkeypatch):
    """Image columns holding an stImage get a fixed card size; the image
    covers the frame (cropped, never distorted) — the row shares a
    horizontal baseline instead of ragged aspect-ratio heights."""
    lui, _fake = _ui_with_fake_st()
    css = _capture_library_css(lui, monkeypatch)
    assert 'div[data-testid="stColumn"]:has([data-testid="stImage"])' in css
    for needle in ("flex: 0 0 180px", "height: 120px",
                   "object-fit: cover", "border-radius: 10px"):
        assert needle in css, needle


def test_actions_row_buttons_share_38px_height(monkeypatch):
    """v1.6 (#27/#28/#30, #46): the Share/Copy dropdowns moved INTO the
    single detail toolbar row, so the old marker-scoped actions-row gap
    rule is gone (dead selector — its DOM target no longer exists). The
    triggers now share the toolbar's own gap/alignment. The copy-button
    iframe height still equals the 38px action system."""
    lui, _fake = _ui_with_fake_st()
    css = _capture_library_css(lui, monkeypatch)
    # The lib-actions marker rule is gone…
    assert '[data-marker="lib-actions"]' not in css
    # …and the flat-layout link-button height rule stays gone.
    assert '[data-testid="stLinkButton"] a' not in css
    assert lui._LIB_ACTION_BTN_H_PX == 38


# ---------------------------------------------------------------------------
# v1.6 (#24) — danger-marker containers collapsed: "Reset"/"Delete"
# triggers and the red destructive button must share the baseline of plain buttons.
# ---------------------------------------------------------------------------

def _capture_story_list_css(lui, monkeypatch):
    """Capture the <style> HTML emitted by _inject_story_list_css (the
    Library-view block holding the danger-marker / red-button rules)."""
    chunks = []
    monkeypatch.setattr(lui.st, "markdown",
                        lambda *a, **k: chunks.append(a[0] if a else ""))
    lui._inject_story_list_css()
    return "\n".join(chunks)


def test_danger_marker_containers_are_collapsed(monkeypatch):
    """The hidden lib-danger-/lib-danger-pop- marker divs are display:none,
    but their stElementContainer wrapper still occupies one inter-element
    gap in Streamlit's vertical block — that gap pushed the
    "Reset"/"Delete" triggers (and the red destructive button) lower than
    their plain-button siblings. The wrapper must be collapsed out of flow."""
    lui, _fake = _ui_with_fake_st()
    css = _capture_story_list_css(lui, monkeypatch)
    assert css.count("{") == css.count("}")
    # One rule covers both _danger_button (lib-danger-…) and the popover
    # trigger (lib-danger-pop-…) markers; other markers are untouched.
    assert ('div[data-testid="stElementContainer"]:has([data-marker^="lib-danger-"]) {'
            in css)
    assert 'display: none !important;' in css
    # The collapse must not have swallowed the neighbouring sidebar rules
    # in the same block, and the selector must stay prefix-scoped.
    assert '[data-marker="lib-story-list"]' in css
    assert '[data-marker^="lib-"]' not in css  # never collapse all markers


def test_danger_red_button_rules_survive_collapse_trigger_is_neutral(monkeypatch):
    """#58: macOS red lives ONLY on the explicit destructive button inside
    the popover — the trigger is neutral (deliberate reversal of #38).

    display:none removes the marker container from layout but NOT from
    the DOM, so the adjacent-sibling red rule for the destructive button
    (which matches on DOM order) must still be present in normal and
    :hover states. The old red popover-TRIGGER rules must be gone."""
    lui, _fake = _ui_with_fake_st()
    css = _capture_story_list_css(lui, monkeypatch)
    red_btn = ('div[data-testid="stElementContainer"]:has([data-marker^="lib-danger-"])\n'
               '        + div[data-testid="stElementContainer"] [data-testid="stButton"] button')
    assert red_btn in css
    assert red_btn + ":hover" in css
    # The trigger is neutral now: no red popover-trigger selectors remain.
    assert '[data-testid="stPopoverButton"]' not in css
    # Exactly the destructive button + its hover carry the red.
    assert css.count("color: #FF3B30 !important;") == 2


def test_danger_button_marker_immediately_precedes_button(monkeypatch):
    """DOM prerequisite for the red-button `+` rule: the marker must be
    the immediate predecessor of the button element."""
    lui, _fake = _ui_with_fake_st()
    seq = []
    monkeypatch.setattr(lui.st, "markdown",
                        lambda *a, **k: seq.append(("md", a[0] if a else "")))
    orig_button = lui.st.button

    def rec_button(label, key=None, **k):
        seq.append(("btn", label, key))
        return orig_button(label, key=key, **k)

    monkeypatch.setattr(lui.st, "button", rec_button)
    assert lui._danger_button("Delete story", key="dp-yes") is False
    assert [s[0] for s in seq] == ["md", "btn"]
    assert 'data-marker="lib-danger-dp-yes"' in seq[0][1]
    assert seq[1][1:] == ("Delete story", "dp-yes")


def test_confirm_popover_marker_immediately_precedes_popover(monkeypatch):
    """DOM prerequisite for the red-trigger `+` rule: the marker must be
    the immediate predecessor of the popover element."""
    lui, fake = _ui_with_fake_st()
    seq = []
    monkeypatch.setattr(lui.st, "markdown",
                        lambda *a, **k: seq.append(("md", a[0] if a else "")))
    orig_popover = lui.st.popover

    def rec_popover(label, **k):
        seq.append(("pop", label))
        return orig_popover(label, **k)

    monkeypatch.setattr(lui.st, "popover", rec_popover)
    lui._confirm_popover(**_pop_kwargs(on_yes=lambda: None))
    assert seq[0][0] == "md"
    assert 'data-marker="lib-danger-pop-dp"' in seq[0][1]
    assert seq[1] == ("pop", "Delete")
    assert fake.popover_kwargs["key"] == "dp"


# v1.6 (#38) — Delete popover HIG: full trigger labels + anchored caret.
# ---------------------------------------------------------------------------

def test_detail_toolbar_weights_fit_full_labels():
    """#38: the Delete trigger was ellipsized to "D..." in the 1.0-weight
    column. #71: hashtags/images are icon-only buttons ("#"/"🖼" glyphs, the
    tooltip keeps the "Update …" label), so their columns shrank to icon
    width and the freed weight moved to the spacer — no dead space in the
    action area, Delete stays trailing. #53: glyph labels never change
    mid-work, so the static labels are the longest state. #46: Share/Copy
    joined the same row; each toolbar total is unchanged (10.0) so the
    overall layout — and the #24 baseline alignment — is preserved."""
    lui, _fake = _ui_with_fake_st()
    assert round(sum(lui._DETAIL_TOOLBAR_WEIGHTS), 6) == 10.0
    assert round(sum(lui._TITLE_EDIT_TOOLBAR_WEIGHTS), 6) == 10.0
    # Icon columns fit the glyph + spinner (generous headroom); text
    # columns unchanged from the #38 fit.
    assert lui._DETAIL_TOOLBAR_WEIGHTS[0] >= 0.8  # hashtag icon button
    assert lui._DETAIL_TOOLBAR_WEIGHTS[1] >= 0.8  # image icon button
    assert lui._DETAIL_TOOLBAR_WEIGHTS[2] >= 1.3  # Reset popover trigger
    assert lui._DETAIL_TOOLBAR_WEIGHTS[3] >= 1.0  # Share popover trigger
    assert lui._DETAIL_TOOLBAR_WEIGHTS[4] >= 1.0  # Copy popover trigger
    assert lui._DETAIL_TOOLBAR_WEIGHTS[6] >= 1.5  # Delete popover trigger
    assert lui._TITLE_EDIT_TOOLBAR_WEIGHTS[-1] >= 1.4  # Delete in edit mode


def test_destructive_popover_has_hig_anchor_caret(monkeypatch):
    """#38: the confirmation must read as a HIG popover anchored to its
    trigger, not a detached card. The caret is scoped to popover bodies
    carrying the lib-danger-pop-body marker: a 45° square inheriting the
    body's own background, so it tracks the light/dark theme with no
    hard-coded surface color."""
    lui, _fake = _ui_with_fake_st()
    css = _capture_story_list_css(lui, monkeypatch)
    assert css.count("{") == css.count("}")
    rule = ('div[data-testid="stPopoverBody"]'
            ':has([data-marker="lib-danger-pop-body"])::before')
    assert rule in css
    assert 'transform: rotate(45deg) !important;' in css
    assert 'background: inherit !important;' in css
    # Theme-safe: the caret introduces no hard-coded surface color, and the
    # #58 red rule set is exactly the destructive button + hover (the
    # trigger is neutral now).
    assert css.count("color: #FF3B30 !important;") == 2


def test_confirm_popover_emits_body_anchor_marker_first(monkeypatch):
    """#38: the lib-danger-pop-body marker must be the first node inside the
    popover body. The body lives in a floating overlay portal, unreachable
    from the trigger marker, so the caret rule anchors to this marker
    instead. Emitted first so the red-button `+` sibling rules (DOM order)
    never see a button-bearing container after it."""
    lui, fake = _ui_with_fake_st()
    seq = []
    monkeypatch.setattr(lui.st, "markdown",
                        lambda *a, **k: seq.append(("md", a[0] if a else "")))
    orig_popover = lui.st.popover

    def rec_popover(label, **k):
        seq.append(("pop", label))
        return orig_popover(label, **k)

    monkeypatch.setattr(lui.st, "popover", rec_popover)
    lui._confirm_popover(**_pop_kwargs(on_yes=lambda: None))
    md_calls = [s[1] for s in seq if s[0] == "md"]
    # [0] trigger marker (outside), [1] body anchor marker (first inside).
    assert 'data-marker="lib-danger-pop-dp"' in md_calls[0]
    assert 'data-marker="lib-danger-pop-body"' in md_calls[1]
    # The body marker must not disturb the Cancel/destructive buttons.
    assert ("Cancel", "dp-no") in fake.buttons
    assert ("Delete story", "dp-yes") in fake.buttons


# ---------------------------------------------------------------------------
# v1.6 (#58) — destructive popovers name the object and use explicit verbs:
# Cancel + "Delete story" / "Delete all stories" / "Reset media" (red),
# never Yes/No. Triggers are neutral; red lives only inside the popover.
# ---------------------------------------------------------------------------

def test_md_escape_neutralises_markdown_syntax():
    lui, _fake = _ui_with_fake_st()
    assert lui._md_escape('A *B* [C](http://x) `code`') == \
        'A \\*B\\* \\[C\\]\\(http://x\\) \\`code\\`'
    assert lui._md_escape('100% #hashtag _under_') == \
        '100% \\#hashtag \\_under\\_'
    assert lui._md_escape('back\\slash') == 'back\\\\slash'
    assert lui._md_escape('') == ''
    assert lui._md_escape(None) == ''
    # Plain prose (the common case) passes through untouched.
    assert lui._md_escape("Delete this story?") == "Delete this story?"


def test_confirm_popover_escapes_markdown_in_title():
    """#58: the title may carry a user-editable story name — Markdown
    specials must render literally and must not break the bold wrapper
    or inject a link."""
    lui, fake = _ui_with_fake_st()
    lui._confirm_popover(**_pop_kwargs(
        title='Delete "A *B* [C]"?', on_yes=lambda: None))
    title_md = [m for m in fake.markup if m.startswith("**")]
    assert title_md == ['**Delete "A \\*B\\* \\[C\\]"?**']


def test_confirm_popover_requires_destructive_label():
    """#58: the explicit verb is mandatory — a missing destructive_label
    fails loudly (TypeError), never renders a bare Yes."""
    lui, _fake = _ui_with_fake_st()
    kw = dict(_pop_kwargs(on_yes=lambda: None))
    del kw["destructive_label"]
    with pytest.raises(TypeError):
        lui._confirm_popover(**kw)


def test_delete_all_popover_uses_explicit_verb():
    """#58: the library sidebar Delete-All confirmation uses the explicit
    red verb "Delete all stories" (source-level: render_library_page is
    too heavy for the fake streamlit harness)."""
    import pathlib
    src = (pathlib.Path(__file__).resolve().parent.parent
           / "library_ui.py").read_text()
    seg = src[src.index('popover_key="lib_delpop_all"'):]
    seg = seg[:seg.index(")", seg.index("destructive_label"))]
    assert 'destructive_label="Delete all stories"' in seg
    assert 'title="Delete all stories?"' in seg


def test_story_delete_popover_names_the_story():
    """#58: the story-delete confirmation titles the popover with the
    quoted story name and the explicit verb (source-level: the helper is
    a closure inside _render_story_detail)."""
    import pathlib
    src = (pathlib.Path(__file__).resolve().parent.parent
           / "library_ui.py").read_text()
    seg = src[src.index("def _story_delete_popover"):]
    seg = seg[:seg.index("def ", 10)]
    assert 'title=f\'Delete "{_story_title}"?\'' in seg
    assert 'destructive_label="Delete story"' in seg
    # The title comes from meta (bound before the closure runs), with the
    # same Untitled fallback the header uses.
    assert 'meta.get("title", "Untitled Story") or "Untitled Story"' in seg


def test_reset_popover_uses_explicit_verb_source():
    """#58: the Reset confirmation's destructive verb is the explicit
    "Reset media" (behavioral part is covered by
    test_reset_popover_idle_wiring)."""
    import pathlib
    src = (pathlib.Path(__file__).resolve().parent.parent
           / "library_ui.py").read_text()
    seg = src[src.index("def _render_reset_popover"):]
    seg = seg[:seg.index("\ndef ", 10)]
    assert 'destructive_label="Reset media"' in seg
    assert 'title="Reset media rows?"' in seg
