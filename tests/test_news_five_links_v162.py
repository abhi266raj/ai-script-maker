"""v1.6.2 (#82) — news links target at least 5 related links, max 5.

- ``_news_query_variants``: full topic first, then progressively looser
  queries (first clause, keyword core) when the topic under-fetches.
- ``_fetch_news_link_candidates``: reusable "fetch up to N new links for
  topic T excluding existing URLs" primitive (#91 load-more composes
  with it). Distinct links only (normalized-URL dedupe), honest
  shortfall, loud failure.
- Save-time enrichment, the #80 Update News refresh, and Reset all
  target ``NEWS_LINKS_TARGET`` (5): refresh/reset top up to / replace
  with at most 5; verified Stage-1 links keep their place (#62).

Run: python -m pytest tests/test_news_five_links_v162.py -q
"""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import story_library as lib  # noqa: E402
from test_library_v15 import (  # noqa: E402
    _make_story,
    libdir,  # noqa: F401  (pytest fixture reuse)
)
from _fake_images import fetch_for  # noqa: E402


class _Article:
    def __init__(self, title, link, source):
        self.title = title
        self.link = link
        self.source = source


def _specs(*triples):
    return [_Article(t, u, s) for t, u, s in triples]


def _fake_news_fetcher(monkeypatch, handler=None, articles=None, boom=None):
    """Inject a stub tools.news_fetcher (feedparser may be absent).

    ``handler(query, limit)`` decides per query; ``articles`` is
    returned for every query; ``boom`` is raised for every query.
    Returns the list of (query, limit) calls.
    """
    calls = []

    class _Fetcher:
        def search_news(self, query, limit=None):
            calls.append((query, limit))
            if boom is not None:
                raise boom
            if handler is not None:
                return handler(query, limit)
            return list(articles or [])

    # Only the news_fetcher submodule is stubbed: the real ``tools``
    # package stays in place so ``tools.story_link`` (used by the image
    # dedupe path inside enrichment/reset) keeps importing. The dummy
    # NewsFetcher satisfies tools/__init__'s
    # ``from .news_fetcher import news_fetcher, NewsFetcher`` when the
    # package __init__ runs against the stubbed submodule.
    fake_mod = types.ModuleType("tools.news_fetcher")
    fake_mod.news_fetcher = _Fetcher()
    fake_mod.NewsFetcher = type("NewsFetcher", (), {})
    monkeypatch.setitem(sys.modules, "tools.news_fetcher", fake_mod)
    return calls


def _enrich_stubs(monkeypatch, tags=(), images=()):
    monkeypatch.setattr(lib, "_fetch_trending_hashtags",
                        lambda topic, story=None: (list(tags), "tags note"))
    monkeypatch.setattr(lib, "_fetch_images_for_story",
                        lambda story, topic, **k: list(images))
    monkeypatch.setattr(lib, "_fetch_image_bytes", fetch_for())


def _reset_stubs(monkeypatch, tags=(), images=()):
    monkeypatch.setattr(lib, "_suggest_hashtags",
                        lambda story, topic, ai_engine=None: (list(tags),
                                                              "AI tags."))
    monkeypatch.setattr(lib, "_fetch_images_for_story",
                        lambda story, topic, **k: list(images))
    monkeypatch.setattr(lib, "_fetch_image_bytes", fetch_for())


def _story_with_n_links(n):
    return _make_story(news_links=[
        {"title": f"Old {i}", "url": f"https://example.com/old-{i}",
         "source": "Ex"} for i in range(n)])


# ---------------------------------------------------------------------------
# Query variants
# ---------------------------------------------------------------------------

def test_query_variants_broaden_progressively():
    variants = lib._news_query_variants(
        "Big relief for Gurugram commuters! Metro Phase 2 stretch gets "
        "green light; 14 stations planned")
    assert variants[0] == ("Big relief for Gurugram commuters! Metro Phase 2 "
                           "stretch gets green light; 14 stations planned")
    assert variants[1] == "Big relief for Gurugram commuters"
    assert variants[2] == "relief Gurugram commuters"
    assert len(variants) == len({v.lower() for v in variants})


def test_query_variants_simple_topic_stays_short():
    assert lib._news_query_variants("Sensex") == ["Sensex"]
    assert lib._news_query_variants("") == []
    assert lib._news_query_variants("  ") == []


# ---------------------------------------------------------------------------
# _fetch_news_link_candidates — the reusable primitive
# ---------------------------------------------------------------------------

def test_candidates_cap_five_distinct_links(monkeypatch):
    arts = _specs(
        ("T1", "https://a.example/1", "A"),
        ("T1 dup slash", "https://a.example/1/", "A"),
        ("T1 dup case", "HTTPS://A.EXAMPLE/1", "A"),
        ("T2", "https://a.example/2", "A"),
        ("T3", "https://a.example/3", "A"),
        ("T4", "https://a.example/4", "A"),
        ("T5", "https://a.example/5", "A"),
        ("T6", "https://a.example/6", "A"),
    )
    _fake_news_fetcher(monkeypatch, articles=arts)
    found = lib._fetch_news_link_candidates("chubby dogs voting contest",
                                            count=5)
    assert len(found) == 5  # never more than asked, dupes collapsed
    keys = [lib._normalize_news_url(lk["url"]) for lk in found]
    assert len(set(keys)) == 5
    assert found[0] == {"title": "T1", "url": "https://a.example/1",
                        "source": "A"}


def test_candidates_broaden_query_when_first_is_short(monkeypatch):
    pool_a = _specs(("A1", "https://a.example/1", "A"),
                    ("A2", "https://a.example/2", "A"))
    pool_b = _specs(("B1", "https://b.example/3", "B"),
                    ("B2", "https://b.example/4", "B"),
                    ("B3", "https://b.example/5", "B"))
    calls = []

    def handler(query, limit):
        calls.append(query)
        return pool_a if len(calls) == 1 else pool_b

    _fake_news_fetcher(monkeypatch, handler=handler)
    found = lib._fetch_news_link_candidates(
        "Metro Phase 2 stretch gets green light; 14 stations planned",
        count=5)
    assert len(found) == 5
    assert len({q.lower() for q in calls}) >= 2  # looser query was tried


def test_candidates_honest_shortfall_not_padded(monkeypatch):
    arts = _specs(("T1", "https://a.example/1", "A"),
                  ("T2", "https://a.example/2", "A"))
    _fake_news_fetcher(monkeypatch, articles=arts)
    found = lib._fetch_news_link_candidates("chubby dogs voting contest",
                                            count=5)
    assert len(found) == 2  # what exists — never invented


def test_candidates_total_failure_raises_loudly(monkeypatch):
    _fake_news_fetcher(monkeypatch, boom=ConnectionError("dns down"))
    try:
        lib._fetch_news_link_candidates("chubby dogs voting contest",
                                       count=5)
    except RuntimeError as e:
        assert "News search failed" in str(e)
        assert "dns down" in str(e)
    else:
        raise AssertionError("fetch failure did not raise")


def test_candidates_respect_count_and_exclude(monkeypatch):
    arts = _specs(("T1", "https://a.example/1", "A"),
                  ("T2", "https://a.example/2", "A"),
                  ("T3", "https://a.example/3", "A"))
    calls = _fake_news_fetcher(monkeypatch, articles=arts)
    found = lib._fetch_news_link_candidates(
        "chubby dogs voting contest", count=2,
        exclude_urls=["https://a.example/1/"])
    assert [lk["url"] for lk in found] == ["https://a.example/2",
                                          "https://a.example/3"]
    # count=0 searches nothing (lets #91 compose without a wasted fetch).
    assert lib._fetch_news_link_candidates("topic", count=0) == []
    assert calls and all(q for q, _ in calls)


def test_candidates_empty_topic_raises(monkeypatch):
    _fake_news_fetcher(monkeypatch, articles=[])
    try:
        lib._fetch_news_link_candidates("   ", count=5)
    except RuntimeError as e:
        assert "No topic" in str(e)
    else:
        raise AssertionError("empty topic did not raise")


# ---------------------------------------------------------------------------
# Save-time enrichment
# ---------------------------------------------------------------------------

def test_enrichment_targets_five_links(libdir, monkeypatch):
    sid = _make_story(hashtags=["#Old"])
    _enrich_stubs(monkeypatch, tags=["#FreshTag"])
    arts = _specs(*[(f"T{i}", f"https://a.example/{i}", "A")
                    for i in range(8)])
    _fake_news_fetcher(monkeypatch, articles=arts)
    changed, note = lib._do_enrich(sid, "chubby dogs voting contest")
    meta = lib.load_story(sid)["meta"]
    assert len(meta["news_links"]) == 5
    assert "Found 5 news link(s)." in note
    assert "Only" not in note
    assert changed is True


def test_enrichment_honest_shortfall_note(libdir, monkeypatch):
    sid = _make_story(hashtags=["#Old"])
    _enrich_stubs(monkeypatch)
    arts = _specs(("T1", "https://a.example/1", "A"),
                  ("T2", "https://a.example/2", "A"))
    _fake_news_fetcher(monkeypatch, articles=arts)
    changed, note = lib._do_enrich(sid, "chubby dogs voting contest")
    meta = lib.load_story(sid)["meta"]
    assert len(meta["news_links"]) == 2
    assert "Found 2 news link(s)." in note
    assert "Only 2 related article(s) found." in note


def test_enrichment_news_failure_is_honest_note_not_lost_work(
        libdir, monkeypatch):
    sid = _make_story(hashtags=["#Old"])
    _enrich_stubs(monkeypatch, tags=["#FreshTag"])
    _fake_news_fetcher(monkeypatch, boom=ConnectionError("dns down"))
    # Does not raise: the story is already saved; hashtags/images land,
    # and the news failure is named in the outcome note.
    changed, note = lib._do_enrich(sid, "chubby dogs voting contest")
    assert "News search failed" in str(note)
    assert "dns down" in str(note)
    assert "no links added" in note
    assert "#FreshTag" in lib.load_story(sid)["meta"]["hashtags"]


# ---------------------------------------------------------------------------
# Update News refresh (#80 path) — top up toward 5, never beyond
# ---------------------------------------------------------------------------

def test_refresh_tops_up_to_five_keep_verified_place(libdir, monkeypatch):
    sid = _story_with_n_links(3)
    arts = _specs(*[(f"New {i}", f"https://new.example/{i}", "N")
                    for i in range(4)])
    _fake_news_fetcher(monkeypatch, articles=arts)
    changed, note = lib.refresh_news_links(sid, "chubby dogs voting contest")
    assert changed is True
    assert "Added 2 new news link(s); now at 5 of 5." in note
    links = lib.load_story(sid)["meta"]["news_links"]
    assert [lk["url"] for lk in links] == [
        "https://example.com/old-0", "https://example.com/old-1",
        "https://example.com/old-2", "https://new.example/0",
        "https://new.example/1"]
    # New entries keep the fetcher's title/source shape.
    assert links[3]["title"] == "New 0"
    assert links[3]["source"] == "N"


def test_refresh_at_cap_searches_nothing(libdir, monkeypatch):
    sid = _story_with_n_links(5)
    calls = _fake_news_fetcher(monkeypatch, articles=_specs(
        ("X", "https://x.example/1", "X")))
    changed, note = lib.refresh_news_links(sid, "chubby dogs voting contest")
    assert changed is False
    assert "at the 5-link cap" in note
    assert calls == []
    assert len(lib.load_story(sid)["meta"]["news_links"]) == 5


def test_refresh_shortfall_note_is_honest(libdir, monkeypatch):
    sid = _story_with_n_links(3)
    arts = _specs(("New 0", "https://new.example/0", "N"))
    _fake_news_fetcher(monkeypatch, articles=arts)
    changed, note = lib.refresh_news_links(sid, "chubby dogs voting contest")
    assert changed is True
    assert "Added 1 new news link(s); now at 4 of 5." in note
    assert "Only 4 related article(s) found." in note


def test_refresh_failure_still_loud(libdir, monkeypatch):
    sid = _make_story()
    _fake_news_fetcher(monkeypatch, boom=ConnectionError("dns down"))
    try:
        lib.refresh_news_links(sid, "chubby dogs voting contest")
    except RuntimeError as e:
        assert "News search failed" in str(e)
        assert "dns down" in str(e)
    else:
        raise AssertionError("fetch failure did not raise")


# ---------------------------------------------------------------------------
# Reset — fresh fetch targets 5; failure clears the row with honest note
# ---------------------------------------------------------------------------

def test_reset_targets_five_links(libdir, monkeypatch):
    sid = _make_story(
        news_links=[{"title": "Old", "url": "https://example.com/old",
                     "source": "Ex"}])
    _reset_stubs(monkeypatch, tags=["#Fresh"])
    arts = _specs(*[(f"R{i}", f"https://r.example/{i}", "R")
                    for i in range(7)])
    _fake_news_fetcher(monkeypatch, articles=arts)
    changed, note = lib._do_reset(sid, "chubby dogs voting contest",
                                  ai_engine="agy_only")
    assert changed is True
    links = lib.load_story(sid)["meta"]["news_links"]
    assert len(links) == 5
    assert "5 news link(s)" in note


def test_reset_news_failure_clears_row_with_honest_note(libdir, monkeypatch):
    sid = _make_story(
        news_links=[{"title": "Old", "url": "https://example.com/old",
                     "source": "Ex"}])
    _reset_stubs(monkeypatch, tags=["#Fresh"])
    _fake_news_fetcher(monkeypatch, boom=ConnectionError("dns down"))
    changed, note = lib._do_reset(sid, "chubby dogs voting contest",
                                  ai_engine="agy_only")
    assert changed is True
    assert lib.load_story(sid)["meta"]["news_links"] == []
    assert "News search failed" in note
    assert "dns down" in note
    assert "row cleared" in note
