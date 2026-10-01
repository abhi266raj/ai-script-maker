"""v1.6.2 (#80) — "Update News" refresh kind.

The story-detail toolbar has Update Hashtags / Update Images but no way
to re-fetch news links. #80 adds a "news" refresh kind end-to-end:

- story_library: "news" is a first-class refresh kind — independent of
  hashtags/images (all three run concurrently, #54/#80), refused while
  reset/enrich runs, and reset stays exclusive while news runs.
  ``refresh_news_links`` re-fetches via ``news_fetcher.search_news``
  (the same source as save-time enrichment) and merges genuinely new
  links in — the stored list is never wiped. Fetch failures raise
  loudly; they are never reported as "nothing new".
- library_ui: icon-only "📰" toolbar button (#71 pattern — glyph +
  "Update News" tooltip), native spinner icon while running,
  stable label, per-kind disable, toast via the existing outcome path.

Run: python -m pytest tests/test_update_news_v162.py -q
"""
import json
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import story_library as lib  # noqa: E402
from test_library_v15 import (  # noqa: E402
    _make_story,
    _settle_enrichment,
    _ui_with_fake_st,
    libdir,  # noqa: F401  (pytest fixture reuse)
)
from test_refresh_buttons_v16 import _wait_idle  # noqa: E402


class _Article:
    def __init__(self, title, link, source):
        self.title = title
        self.link = link
        self.source = source


def _fake_news_fetcher(monkeypatch, articles=None, boom=None):
    """Inject a stub tools.news_fetcher (feedparser is absent in this env).

    ``articles``: list of _Article returned by search_news.
    ``boom``: exception instance raised by search_news instead.
    Returns the list of (topic, limit) calls.
    """
    calls = []

    class _Fetcher:
        def search_news(self, topic, limit=None):
            calls.append((topic, limit))
            if boom is not None:
                raise boom
            return list(articles or [])

    fake_pkg = types.ModuleType("tools")
    fake_mod = types.ModuleType("tools.news_fetcher")
    fake_mod.news_fetcher = _Fetcher()
    monkeypatch.setitem(sys.modules, "tools", fake_pkg)
    monkeypatch.setitem(sys.modules, "tools.news_fetcher", fake_mod)
    return calls


def _story_with_links(**kw):
    kw.setdefault("news_links", [
        {"title": "Old story", "url": "https://example.com/old",
         "source": "Example"},
    ])
    return _make_story(**kw)


# ---------------------------------------------------------------------------
# Library layer — kind registration and concurrency
# ---------------------------------------------------------------------------

def test_news_is_a_non_exclusive_refresh_kind():
    assert "news" in lib._REFRESH_KINDS
    assert "news" not in lib._EXCLUSIVE_KINDS


def test_news_runs_concurrently_with_hashtags_and_images(libdir, monkeypatch):
    """#54/#80: news is independent — it starts while hashtags runs, both
    are busy at once, and neither worker's file write clobbers the other."""
    import threading
    sid = _make_story()
    _settle_enrichment(sid)
    news_started = threading.Event()
    release = threading.Event()

    def _fake_news(sid_, topic):
        news_started.set()
        assert release.wait(timeout=10)
        lib.update_story_fields(sid_, news_links=[
            {"title": "N", "url": "https://example.com/n", "source": "S"}])
        return True, "added 1 news link"

    monkeypatch.setattr(lib, "refresh_news_links", _fake_news)
    # Simulate hashtags already in flight (no worker — we only need its
    # busy flag to prove news is not blocked by it).
    lib._set_refresh_busy(sid, "hashtags")
    ok, reason = lib.start_refresh(sid, "news")
    assert ok, reason
    assert news_started.wait(timeout=10)
    # Both kinds genuinely in flight at the same moment.
    assert lib.refresh_busy_kinds(lib.load_story(sid)["meta"]) == {
        "hashtags", "news"}
    release.set()
    lib._finish_refresh(sid, "hashtags", "succeeded", "test hashtags done")
    assert _wait_idle(sid), "news worker did not finish"
    meta = lib.load_story(sid)["meta"]
    assert meta["news_links"] == [
        {"title": "N", "url": "https://example.com/n", "source": "S"}]
    outcomes = {json.loads(e)["kind"]: json.loads(e)
                for e in meta["refresh_outcome_pending"]}
    assert outcomes["news"]["status"] == "succeeded"


def test_news_refused_while_reset_running(libdir):
    sid = _make_story()
    _settle_enrichment(sid)
    lib._set_refresh_busy(sid, "reset")
    ok, reason = lib.start_refresh(sid, "news")
    assert not ok and "already running" in reason


def test_reset_refused_while_news_running(libdir):
    """Reset stays exclusive: it refuses while the news kind runs."""
    sid = _make_story()
    _settle_enrichment(sid)
    lib._set_refresh_busy(sid, "news")
    ok, reason = lib.start_refresh(sid, "reset")
    assert not ok
    assert "reset clears" in reason


def test_news_refused_while_enrich_running(libdir):
    sid = _make_story()
    _settle_enrichment(sid)
    lib._set_refresh_busy(sid, "enrich")
    ok, reason = lib.start_refresh(sid, "news")
    assert not ok and "enrichment" in reason


def test_same_kind_news_second_kick_refused(libdir):
    sid = _make_story()
    _settle_enrichment(sid)
    lib._set_refresh_busy(sid, "news")
    ok, reason = lib.start_refresh(sid, "news")
    assert not ok and "already running" in reason


# ---------------------------------------------------------------------------
# Library layer — refresh_news_links body
# ---------------------------------------------------------------------------

def test_refresh_news_links_adds_new_and_dedupes(libdir, monkeypatch):
    sid = _story_with_links()
    _fake_news_fetcher(monkeypatch, articles=[
        _Article("Old story", "https://example.com/old", "Example"),
        _Article("Fresh story", "https://example.com/fresh/", "FreshWire"),
    ])
    changed, note = lib.refresh_news_links(sid, "chubby dogs voting contest")
    assert changed is True
    assert "Added 1 new news link(s)" in note
    links = lib.load_story(sid)["meta"]["news_links"]
    assert [lk["url"] for lk in links] == [
        "https://example.com/old", "https://example.com/fresh/"]
    # The new entry keeps the fetcher's title/source shape.
    assert links[1]["title"] == "Fresh story"
    assert links[1]["source"] == "FreshWire"


def test_refresh_news_links_nothing_new_is_honest(libdir, monkeypatch):
    """All fetched links already stored -> (False, honest note)."""
    sid = _story_with_links()
    _fake_news_fetcher(monkeypatch, articles=[
        _Article("Old story", "https://example.com/old", "Example"),
    ])
    changed, note = lib.refresh_news_links(sid, "chubby dogs voting contest")
    assert changed is False
    assert "No new news links found" in note
    assert "kept 1 existing" in note


def test_refresh_news_links_fetch_failure_is_loud(libdir, monkeypatch):
    """A broken search raises — never reported as 'nothing new'."""
    sid = _make_story()
    _fake_news_fetcher(monkeypatch, boom=ConnectionError("dns down"))
    try:
        lib.refresh_news_links(sid, "chubby dogs voting contest")
    except RuntimeError as e:
        assert "News search failed" in str(e)
        assert "dns down" in str(e)
    else:
        raise AssertionError("fetch failure did not raise")


def test_refresh_news_links_needs_topic(libdir, monkeypatch):
    sid = _make_story(source_topic="")
    # _make_story defaults source_topic; blank it via update.
    lib.update_story_fields(sid, source_topic="", title="")
    try:
        lib.refresh_news_links(sid, "")
    except RuntimeError as e:
        assert "No topic" in str(e)
    else:
        raise AssertionError("missing topic did not raise")


def test_news_worker_records_honest_outcome(libdir, monkeypatch):
    """End-to-end through _refresh_worker: busy clears, outcome toasts."""
    sid = _make_story()
    _settle_enrichment(sid)
    monkeypatch.setattr(
        lib, "refresh_news_links",
        lambda sid_, topic: (True, "Added 2 new news link(s); kept 1 existing."))
    ok, reason = lib.start_refresh(sid, "news")
    assert ok, reason
    assert _wait_idle(sid), "news worker did not finish"
    meta = lib.load_story(sid)["meta"]
    assert lib.refresh_busy_kinds(meta) == set()
    outcomes = {json.loads(e)["kind"]: json.loads(e)
                for e in meta["refresh_outcome_pending"]}
    assert outcomes["news"]["status"] == "succeeded"
    assert "Added 2" in outcomes["news"]["note"]


def test_news_worker_failure_outcome_is_loud(libdir, monkeypatch):
    def _boom(sid_, topic):
        raise RuntimeError("feed exploded")
    sid = _make_story()
    _settle_enrichment(sid)
    monkeypatch.setattr(lib, "refresh_news_links", _boom)
    ok, _ = lib.start_refresh(sid, "news")
    assert ok
    assert _wait_idle(sid)
    meta = lib.load_story(sid)["meta"]
    outcomes = {json.loads(e)["kind"]: json.loads(e)
                for e in meta["refresh_outcome_pending"]}
    assert outcomes["news"]["status"] == "failed"
    assert "News refresh failed" in outcomes["news"]["note"]
    assert "feed exploded" in outcomes["news"]["note"]


# ---------------------------------------------------------------------------
# UI layer — icon-only button, spinner marker, toast
# ---------------------------------------------------------------------------

def _news_button_kwargs(lui, **kw):
    d = dict(story_id="sid1", kind="news", label=lui._TB_ICON_NEWS,
             button_key="lib_news_sid1", kick_label="news",
             help_text="Update News", busy_kinds=set(), ai_engine=None)
    d.update(kw)
    return d


def test_news_button_icon_only_and_stable_while_running():
    """#71/#80/#111: icon-only button — native material icon via icon=,
    empty text label, tooltip keeps "Update News", disabled + native
    spinner while running."""
    lui, fake = _ui_with_fake_st()
    lui._render_kind_button(**_news_button_kwargs(lui, busy_kinds={"news"}))
    assert fake.buttons == [("", "lib_news_sid1")]
    kw = fake.button_kwargs[0]
    assert kw["icon"] == "spinner"
    assert kw["disabled"] is True
    assert kw["use_container_width"] is True
    assert kw["help"] == "Update News"
    assert "lib-spin-news" not in "".join(fake.markup)


def test_news_button_idle_state():
    lui, fake = _ui_with_fake_st()
    lui._render_kind_button(**_news_button_kwargs(lui))
    assert fake.buttons == [("", "lib_news_sid1")]
    assert fake.button_kwargs[0]["icon"] == lui._TB_ICON_NEWS
    assert fake.button_kwargs[0]["disabled"] is False
    assert "lib-spin-news" not in "".join(fake.markup)


def test_news_button_independent_while_sibling_runs():
    """#54/#80: the news button stays enabled while hashtags runs."""
    lui, fake = _ui_with_fake_st()
    lui._render_kind_button(**_news_button_kwargs(lui, busy_kinds={"hashtags"}))
    assert fake.button_kwargs[0]["disabled"] is False
    assert "lib-spin-news" not in "".join(fake.markup)


def test_news_button_click_kicks_news_refresh(monkeypatch):
    lui, fake = _ui_with_fake_st(clicks=("lib_news_sid1",))
    calls = []
    monkeypatch.setattr(lui.lib, "start_refresh",
                        lambda sid, kind, ai_engine=None: (
                            calls.append((sid, kind, ai_engine)) or (True, "")))
    lui._render_kind_button(**_news_button_kwargs(lui))
    assert calls == [("sid1", "news", None)]
    assert fake.reran is True
    assert fake.errors == []


def test_news_button_kick_failure_is_loud(monkeypatch):
    lui, fake = _ui_with_fake_st(clicks=("lib_news_sid1",))
    monkeypatch.setattr(lui.lib, "start_refresh",
                        lambda sid, kind, ai_engine=None: (False, "boom"))
    lui._render_kind_button(**_news_button_kwargs(lui))
    assert fake.errors == ["Could not start the news refresh: boom"]
    assert fake.reran is False


def test_no_spinner_css_rules_remain():
    """#111: the marker + ::before spinner CSS is gone — the spinner is
    Streamlit's native icon="spinner"."""
    import re
    lui, _fake = _ui_with_fake_st()
    chunks = []

    class _Cap:
        def markdown(self, *a, **k):
            chunks.append(a[0] if a else "")

    import types
    saved = dict(sys.modules)
    try:
        fake_mod = types.ModuleType("streamlit")
        cap = _Cap()
        fake_mod.markdown = cap.markdown
        sys.modules["streamlit"] = fake_mod
        sys.modules.pop("library_ui", None)
        import library_ui as lui2
        lui2.inject_library_css()
    finally:
        sys.modules.clear()
        sys.modules.update(saved)
    css = "\n".join(chunks)
    clean = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    assert "lib-spin-" not in clean
    assert "button::before" not in clean


def test_news_toast_text():
    lui, _fake = _ui_with_fake_st()
    assert lui._refresh_toast_text(
        "news", "succeeded", "Added 2.") == "News updated — Added 2."
    assert lui._refresh_toast_text(
        "news", "no_change", "") == "News: nothing new"
    assert lui._refresh_toast_text(
        "news", "failed", "x") == "News failed — x"


def test_news_hint_suppressed_while_running():
    """The 'No news links yet.' caption hides while a news refresh runs."""
    import inspect
    lui, _fake = _ui_with_fake_st()
    src = inspect.getsource(lui._render_story_detail)
    # #91: more_news also re-fetches links, so it joins the set.
    assert '{"news", "more_news", "reset", "enrich"}' in src
