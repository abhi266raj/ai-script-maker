"""v1.6.2 (#91) — "Load more" for images and news references.

Fetched images are capped at 5 (#83) and news links target 5 (#82); #91
adds the explicit, user-driven way past those caps: "Load more images"
and "Load more news" controls on the story detail. Each fetches ONE more
batch (up to 5) of genuinely new items, appended after the existing
ones, with dedupe applied (#21/#44 for images, normalized-URL for news).

Contract pinned here:

- story_library: "more_images" / "more_news" are first-class refresh
  kinds — independent of everything except their sibling kind
  ("images"<->"more_images", "news"<->"more_news" both write the same
  field, so each pair is mutually exclusive; concurrent writers would
  silently clobber each other's appended batch). Reset stays exclusive
  while a load-more runs and vice versa.
- ``load_more_images`` goes deeper than a refresh (12 articles vs 6, 4
  images/page vs 3, web-search fallback) and merges through the full
  ``_merge_story_images`` pipeline — the #83 cap is bypassed by this
  explicit request, dedupe never is. ``load_more_news_links`` fetches a
  deeper pool (15 vs 6) and appends up to 5 new URLs.
- Fail-loud: missing story/topic or a fetch failure raises; an empty
  deeper pool returns (False, "No more … found") — never a faked add.
- library_ui: section-level buttons owning the #53 loading contract
  (stable label, lib-spin-<kind> spinner, disabled while running or
  while the sibling runs, toast via the existing outcome path).

Run: python -m pytest tests/test_load_more_v162.py -q
"""
import hashlib
import json
import sys
import threading
import types
from pathlib import Path

import pytest  # noqa: E402

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
    def __init__(self, title, link, source="Src"):
        self.title = title
        self.link = link
        self.source = source


def _fake_news_fetcher(monkeypatch, articles=None, boom=None):
    """Inject a stub tools.news_fetcher (feedparser is absent in this env)."""
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


def _dhash_for(url):
    """Deterministic fake 64-bit dHash — distinct URLs land far apart."""
    return int.from_bytes(
        hashlib.sha256(("ph:" + url).encode()).digest()[:8], "big")


def _img_entry(url):
    """(url, sha_hex, phash_hex) triple with the same scheme as the stub."""
    return (url, hashlib.sha256(url.encode()).hexdigest(),
            lib._dhash_to_hex(_dhash_for(url)))


def _fake_fingerprints(monkeypatch, dhash_map=None):
    """Stub _image_fingerprints: deterministic, no network.

    ``dhash_map`` overrides the dHash for chosen URLs (e.g. to force a
    visual near-dupe within the Hamming threshold).
    """
    dhash_map = dhash_map or {}

    def _fp(url):
        return (hashlib.sha256(url.encode()).hexdigest(),
                dhash_map.get(url, _dhash_for(url)))

    monkeypatch.setattr(lib, "_image_fingerprints", _fp)


def _fake_image_pool(monkeypatch, pairs, article_links=(), web_images=()):
    """Stub the image fetch layer: articles + (url, alt) extraction.

    ``web_images`` stubs the web-search fallback (unstubbed it shells
    out to the real image-search CLI — never in tests).
    """
    calls = []

    def _articles(topic, limit=6):
        calls.append((topic, limit))
        return [_Article(f"T{i}", link) for i, link in enumerate(article_links)]

    monkeypatch.setattr(lib, "_fetch_news_articles", _articles)
    monkeypatch.setattr(
        lib, "_grab_article_images",
        lambda urls, tries=3, per_page=3: list(pairs))
    monkeypatch.setattr(
        lib, "_search_web_images",
        lambda topic, limit=4: list(web_images))
    return calls


def _story_with_images(urls, **kw):
    # save_story() takes image_urls but always seeds empty hash lists —
    # set the precomputed fingerprints afterwards so the merge never
    # touches the network in tests.
    kw.setdefault("image_urls", list(urls))
    sid = _make_story(**kw)
    entries = [_img_entry(u) for u in urls]
    lib.update_story_fields(sid,
                            image_hashes=[e[1] for e in entries],
                            image_phashes=[e[2] for e in entries])
    return sid


# ---------------------------------------------------------------------------
# Library layer — kind registration and concurrency
# ---------------------------------------------------------------------------

def test_more_kinds_registered(libdir):
    assert "more_images" in lib._REFRESH_KINDS
    assert "more_news" in lib._REFRESH_KINDS
    for kind in ("more_images", "more_news"):
        entry = json.dumps({"kind": kind, "status": "succeeded", "note": "x"})
        assert lib.parse_refresh_outcome(entry)["kind"] == kind


def test_more_images_refused_while_images_busy(libdir):
    sid = _make_story()
    _settle_enrichment(sid)
    lib._set_refresh_busy(sid, "images")
    ok, reason = lib.start_refresh(sid, "more_images")
    assert ok is False
    assert "already running" in reason
    lib._finish_refresh(sid, "images", "succeeded", "cleanup")


def test_images_refused_while_more_images_busy(libdir):
    sid = _make_story()
    _settle_enrichment(sid)
    lib._set_refresh_busy(sid, "more_images")
    ok, reason = lib.start_refresh(sid, "images")
    assert ok is False
    assert "already running" in reason
    lib._finish_refresh(sid, "more_images", "succeeded", "cleanup")


def test_more_news_refused_while_news_busy_and_vice_versa(libdir):
    sid = _make_story()
    _settle_enrichment(sid)
    lib._set_refresh_busy(sid, "news")
    ok, reason = lib.start_refresh(sid, "more_news")
    assert ok is False and "already running" in reason
    lib._finish_refresh(sid, "news", "succeeded", "cleanup")
    lib._set_refresh_busy(sid, "more_news")
    ok, reason = lib.start_refresh(sid, "news")
    assert ok is False and "already running" in reason
    lib._finish_refresh(sid, "more_news", "succeeded", "cleanup")


def test_more_images_independent_of_hashtags_and_news(libdir, monkeypatch):
    """#91: more_images runs alongside hashtags/news — only the sibling is
    exclusive."""
    sid = _make_story()
    _settle_enrichment(sid)
    # Gate the worker so it can't finish (and clear its busy flag)
    # before the test observes both kinds busy together.
    release = threading.Event()

    def _stub(s, t=""):
        assert release.wait(timeout=10)
        return True, "stubbed"

    monkeypatch.setattr(lib, "load_more_images", _stub)
    lib._set_refresh_busy(sid, "hashtags")
    ok, reason = lib.start_refresh(sid, "more_images")
    assert ok, reason
    try:
        busy = lib.refresh_busy_kinds(lib.load_story(sid)["meta"])
        assert busy == {"hashtags", "more_images"}
    finally:
        release.set()
    lib._finish_refresh(sid, "hashtags", "succeeded", "cleanup")
    assert _wait_idle(sid)


def test_reset_exclusive_with_load_more(libdir):
    sid = _make_story()
    _settle_enrichment(sid)
    lib._set_refresh_busy(sid, "more_images")
    ok, reason = lib.start_refresh(sid, "reset")
    assert ok is False and "already running" in reason
    lib._finish_refresh(sid, "more_images", "succeeded", "cleanup")
    lib._set_refresh_busy(sid, "reset")
    ok, reason = lib.start_refresh(sid, "more_news")
    assert ok is False and "already running" in reason
    lib._finish_refresh(sid, "reset", "succeeded", "cleanup")


def test_unknown_kind_still_rejected(libdir):
    sid = _make_story()
    _settle_enrichment(sid)
    ok, reason = lib.start_refresh(sid, "more_everything")
    assert ok is False and "Unknown refresh kind" in reason


# ---------------------------------------------------------------------------
# load_more_news_links
# ---------------------------------------------------------------------------

def test_load_more_news_appends_next_five(libdir, monkeypatch):
    sid = _make_story(news_links=[
        {"title": "Old", "url": "https://example.com/old", "source": "Ex"}])
    _settle_enrichment(sid)
    calls = []

    def _fake(topic, count=5, exclude_urls=()):
        calls.append({"topic": topic, "count": count,
                      "exclude": list(exclude_urls)})
        return [{"title": f"T{i}", "url": f"https://example.com/n{i}",
                 "source": "Ex"} for i in range(5)]

    monkeypatch.setattr(lib, "_fetch_news_link_candidates", _fake)
    changed, note = lib.load_more_news_links(sid)
    assert changed is True
    assert "Added 5 more news link(s)" in note
    urls = [lk["url"] for lk in lib.load_story(sid)["meta"]["news_links"]]
    assert urls == ["https://example.com/old"] + \
        [f"https://example.com/n{i}" for i in range(5)]
    # One batch via #82's primitive; the stored URL is excluded up front.
    assert calls and calls[0]["count"] == 5
    assert "https://example.com/old" in calls[0]["exclude"]


def test_load_more_news_appends_short_batch_honestly(libdir, monkeypatch):
    """A shortfall (fewer than 5 genuinely related links exist) is an
    honest short add, never padded or invented."""
    sid = _make_story()
    _settle_enrichment(sid)
    monkeypatch.setattr(
        lib, "_fetch_news_link_candidates",
        lambda topic, count=5, exclude_urls=(): [
            {"title": "T1", "url": "https://example.com/n1", "source": "Ex"},
            {"title": "T2", "url": "https://example.com/n2", "source": "Ex"}])
    changed, note = lib.load_more_news_links(sid)
    assert changed is True
    assert "Added 2 more news link(s)" in note
    urls = [lk["url"] for lk in lib.load_story(sid)["meta"]["news_links"]]
    assert urls == ["https://example.com/n1", "https://example.com/n2"]


def test_load_more_news_honest_empty(libdir, monkeypatch):
    sid = _make_story(news_links=[
        {"title": "Old", "url": "https://example.com/old", "source": "Ex"}])
    _settle_enrichment(sid)
    monkeypatch.setattr(lib, "_fetch_news_link_candidates",
                        lambda topic, count=5, exclude_urls=(): [])
    changed, note = lib.load_more_news_links(sid)
    assert changed is False
    assert "No more news links found" in note
    assert "kept 1 existing" in note


def test_load_more_news_search_failure_raises_loudly(libdir, monkeypatch):
    sid = _make_story()
    _settle_enrichment(sid)

    def _boom(topic, count=5, exclude_urls=()):
        raise RuntimeError("News search failed (net down) — news links unchanged.")

    monkeypatch.setattr(lib, "_fetch_news_link_candidates", _boom)
    with pytest.raises(RuntimeError, match="News search failed"):
        lib.load_more_news_links(sid)


def test_load_more_news_missing_story_and_topic_raise(libdir):
    with pytest.raises(RuntimeError, match="Story not found"):
        lib.load_more_news_links("no-such-story")
    sid = _make_story(source_topic="")
    _settle_enrichment(sid)
    lib.update_story_fields(sid, source_topic="")
    with pytest.raises(RuntimeError, match="No topic"):
        lib.load_more_news_links(sid, topic="")


# ---------------------------------------------------------------------------
# load_more_images
# ---------------------------------------------------------------------------

def test_load_more_images_appends_genuinely_new(libdir, monkeypatch):
    sid = _story_with_images(["https://img.example/a.jpg",
                              "https://img.example/b.jpg"])
    _settle_enrichment(sid)
    _fake_fingerprints(monkeypatch)
    pool = [("https://img.example/a.jpg", "photo A"),   # URL dupe
            ("https://img.example/c.jpg", "photo C"),
            ("https://img.example/d.jpg", "photo D")]
    article_calls = _fake_image_pool(
        monkeypatch, pool,
        article_links=["https://news.example/s1", "https://news.example/s2"])
    changed, note = lib.load_more_images(sid)
    assert changed is True
    assert "Added 2 more image(s)" in note
    urls = lib.load_story(sid)["meta"]["image_urls"]
    assert urls == ["https://img.example/a.jpg", "https://img.example/b.jpg",
                    "https://img.example/c.jpg", "https://img.example/d.jpg"]
    # Deeper than a refresh: 12 articles, not 6.
    assert article_calls and article_calls[0][1] == 12


def test_load_more_images_visual_dupe_dropped_honestly(libdir, monkeypatch):
    existing = "https://img.example/a.jpg"
    sid = _story_with_images([existing])
    _settle_enrichment(sid)
    new_url = "https://img.example/a-resized.jpg"
    # Near-dupe dHash (3 bits away — within the #44 threshold).
    _fake_fingerprints(monkeypatch,
                       {new_url: _dhash_for(existing) ^ 0b111})
    _fake_image_pool(monkeypatch, [(new_url, "resized copy")])
    changed, note = lib.load_more_images(sid)
    assert changed is False
    assert "No more images found" in note
    assert "already stored" in note
    assert lib.load_story(sid)["meta"]["image_urls"] == [existing]


def test_load_more_images_bypasses_cap_explicitly(libdir, monkeypatch):
    """#91: the #83 cap is bypassed by explicit request — six stored
    images do not stop the next batch."""
    sid = _story_with_images([f"https://img.example/i{i}.jpg"
                              for i in range(6)])
    _settle_enrichment(sid)
    _fake_fingerprints(monkeypatch)
    _fake_image_pool(monkeypatch, [
        ("https://img.example/new1.jpg", "fresh one"),
        ("https://img.example/new2.jpg", "fresh two")])
    changed, note = lib.load_more_images(sid)
    assert changed is True
    urls = lib.load_story(sid)["meta"]["image_urls"]
    assert len(urls) == 8
    assert urls[-2:] == ["https://img.example/new1.jpg",
                         "https://img.example/new2.jpg"]
    assert "8 total" in note


def test_load_more_images_web_search_fills_short_pool(libdir, monkeypatch):
    """When article extraction yields fewer than a batch, the web image
    search fallback tops the batch up (genuinely new only)."""
    sid = _story_with_images(["https://img.example/a.jpg"])
    _settle_enrichment(sid)
    _fake_fingerprints(monkeypatch)
    _fake_image_pool(
        monkeypatch,
        [("https://img.example/b.jpg", "article photo")],
        web_images=["https://img.example/a.jpg",   # already stored
                    "https://img.example/w1.jpg",
                    "https://img.example/w2.jpg"])
    changed, note = lib.load_more_images(sid)
    assert changed is True
    urls = lib.load_story(sid)["meta"]["image_urls"]
    assert urls == ["https://img.example/a.jpg", "https://img.example/b.jpg",
                    "https://img.example/w1.jpg", "https://img.example/w2.jpg"]
    assert "Added 3 more image(s)" in note


def test_load_more_images_honest_empty(libdir, monkeypatch):
    sid = _story_with_images(["https://img.example/a.jpg"])
    _settle_enrichment(sid)
    _fake_fingerprints(monkeypatch)
    _fake_image_pool(monkeypatch, [])  # deeper pool, nothing at all
    changed, note = lib.load_more_images(sid)
    assert changed is False
    assert "No more images found" in note
    assert "kept 1 existing" in note


def test_load_more_images_timeout_is_honest(libdir, monkeypatch):
    sid = _story_with_images(["https://img.example/a.jpg"])
    _settle_enrichment(sid)
    monkeypatch.setattr(
        lib, "_run_bounded",
        lambda fn, timeout_s, step_name: (_ for _ in ()).throw(
            TimeoutError("load-more image fetch hit 90.0s")))
    changed, note = lib.load_more_images(sid)
    assert changed is False
    assert "timed out" in note
    assert "kept 1 existing" in note


def test_load_more_images_missing_story_and_topic_raise(libdir):
    with pytest.raises(RuntimeError, match="Story not found"):
        lib.load_more_images("no-such-story")
    sid = _make_story(source_topic="")
    _settle_enrichment(sid)
    lib.update_story_fields(sid, source_topic="")
    with pytest.raises(RuntimeError, match="No topic"):
        lib.load_more_images(sid, topic="")


def test_load_more_images_unwanted_alt_rejected(libdir, monkeypatch):
    """Alt-text relevance filter still applies on the load-more path."""
    sid = _story_with_images(["https://img.example/a.jpg"])
    _settle_enrichment(sid)
    _fake_fingerprints(monkeypatch)
    _fake_image_pool(monkeypatch, [
        ("https://img.example/logo.png", "site logo"),
        ("https://img.example/good.jpg", "street photo")])
    changed, note = lib.load_more_images(sid)
    assert changed is True
    urls = lib.load_story(sid)["meta"]["image_urls"]
    assert urls == ["https://img.example/a.jpg",
                    "https://img.example/good.jpg"]


# ---------------------------------------------------------------------------
# Worker end-to-end + UI layer
# ---------------------------------------------------------------------------

def test_more_news_worker_writes_honest_outcome(libdir, monkeypatch):
    sid = _make_story()
    _settle_enrichment(sid)
    _fake_news_fetcher(monkeypatch,
                       [_Article("Fresh", "https://example.com/fresh")])
    ok, reason = lib.start_refresh(sid, "more_news")
    assert ok, reason
    assert _wait_idle(sid)
    pending = lib.load_story(sid)["meta"].get("refresh_outcome_pending") or []
    kinds = [json.loads(e)["kind"] for e in pending]
    assert "more_news" in kinds
    note = [json.loads(e)["note"] for e in pending
            if json.loads(e)["kind"] == "more_news"][0]
    assert "Added 1 more news link(s)" in note


def _load_more_kwargs(kind="more_images", **kw):
    d = dict(story_id="sid1", kind=kind,
             label=("Load more images" if kind == "more_images"
                    else "Load more news"),
             button_key=("lib_moreimg_sid1" if kind == "more_images"
                         else "lib_morenews_sid1"),
             help_text="Fetch up to 5 more",
             busy_kinds=set())
    d.update(kw)
    return d


def test_load_more_button_idle_state():
    lui, fake = _ui_with_fake_st()
    lui._render_load_more_button(**_load_more_kwargs())
    assert fake.buttons == [("Load more images", "lib_moreimg_sid1")]
    assert fake.button_kwargs[0]["disabled"] is False
    assert "lib-spin-more-images" not in "".join(fake.markup)


def test_load_more_button_running_shows_spinner_and_disables():
    """#53: label never changes; spinner + disabled while its kind runs."""
    lui, fake = _ui_with_fake_st()
    lui._render_load_more_button(
        **_load_more_kwargs(busy_kinds={"more_images"}))
    assert fake.buttons == [("Load more images", "lib_moreimg_sid1")]
    kw = fake.button_kwargs[0]
    assert kw["disabled"] is True
    assert kw["help"] == "Fetch up to 5 more"
    assert 'data-marker="lib-spin-more-images"' in "".join(fake.markup)


def test_load_more_button_blocked_while_sibling_runs_no_spinner():
    """#91: disabled (blocked, not working) while Update Images runs."""
    lui, fake = _ui_with_fake_st()
    lui._render_load_more_button(
        **_load_more_kwargs(busy_kinds={"images"}))
    assert fake.button_kwargs[0]["disabled"] is True
    assert "lib-spin-more-images" not in "".join(fake.markup)


def test_load_more_button_independent_of_hashtags():
    lui, fake = _ui_with_fake_st()
    lui._render_load_more_button(
        **_load_more_kwargs(busy_kinds={"hashtags"}))
    assert fake.button_kwargs[0]["disabled"] is False
    assert "lib-spin-more-images" not in "".join(fake.markup)


def test_load_more_news_button_markers():
    lui, fake = _ui_with_fake_st()
    lui._render_load_more_button(
        **_load_more_kwargs(kind="more_news", busy_kinds={"more_news"}))
    assert fake.buttons == [("Load more news", "lib_morenews_sid1")]
    assert fake.button_kwargs[0]["disabled"] is True
    assert 'data-marker="lib-spin-more-news"' in "".join(fake.markup)


def test_load_more_button_click_kicks_kind(monkeypatch):
    lui, fake = _ui_with_fake_st(clicks=("lib_moreimg_sid1",))
    calls = []
    monkeypatch.setattr(lui.lib, "start_refresh",
                        lambda sid, kind, ai_engine=None: (
                            calls.append((sid, kind)) or (True, "")))
    lui._render_load_more_button(**_load_more_kwargs())
    assert calls == [("sid1", "more_images")]
    assert fake.reran is True
    assert fake.errors == []


def test_load_more_button_kick_failure_is_loud(monkeypatch):
    lui, fake = _ui_with_fake_st(clicks=("lib_moreimg_sid1",))
    monkeypatch.setattr(lui.lib, "start_refresh",
                        lambda sid, kind, ai_engine=None: (False, "boom"))
    lui._render_load_more_button(**_load_more_kwargs())
    assert fake.errors == ["Could not start: boom"]
    assert fake.reran is False


def test_more_spinner_css_rules_match_dom_order():
    """The lib-spin-more-* selectors must share the exact adjacent-sibling
    shape as the hashtags/images/news selectors — a mismatched middle
    sibling silently kills the spinner (cf. the #81 reset-loader bug)."""
    import re
    saved = dict(sys.modules)
    chunks = []

    class _Cap:
        def markdown(self, *a, **k):
            chunks.append(a[0] if a else "")

    try:
        fake_mod = types.ModuleType("streamlit")
        fake_mod.markdown = _Cap().markdown
        sys.modules["streamlit"] = fake_mod
        sys.modules.pop("library_ui", None)
        import library_ui as lui2
        lui2.inject_library_css()
    finally:
        sys.modules.clear()
        sys.modules.update(saved)
    css = "\n".join(chunks)
    clean = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for kind in ("more_images", "more_news"):
        # CSS markers use hyphens (lib-spin-more-images).
        marker = "lib-spin-" + kind.replace("_", "-")
        pat = (r'div\[data-testid="stElementContainer"\]:has\(\[data-marker='
               rf'"{marker}"\]\)\s*\+\s*div\[data-testid="stElementContainer"\]'
               r'\s*\[data-testid="stButton"\]\s*button::before')
        assert re.search(pat, clean), \
            f"{marker} selector missing or wrong DOM order"


def test_more_toast_text():
    lui, _fake = _ui_with_fake_st()
    assert lui._refresh_toast_text(
        "more_images", "succeeded", "Added 3.") == "More images updated — Added 3."
    assert lui._refresh_toast_text(
        "more_news", "no_change", "") == "More news: nothing new"
    assert lui._refresh_toast_text(
        "more_images", "failed", "x") == "More images failed — x"


def test_images_hint_suppressed_while_load_more_runs():
    """The 'No images yet.' caption hides while a load-more-images run is
    in flight (same as the images kind)."""
    import inspect
    lui, _fake = _ui_with_fake_st()
    src = inspect.getsource(lui._render_story_detail)
    assert '{"images", "more_images", "reset", "enrich"}' in src
