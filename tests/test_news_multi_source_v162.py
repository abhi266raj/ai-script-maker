"""v1.6.2 (#121) — aggressive multi-source news search.

search_news is now backed by a Google News RSS -> Bing News RSS ->
DuckDuckGo HTML (regex extraction) chain with relevance ranking and a
loud NewsFetchError when every source fails or returns nothing.

feedparser/httpx/bs4/pydantic are absent in this VM, so the test stubs
those modules (stdlib-only) before importing tools.news_fetcher.

Run: python -m pytest tests/test_news_multi_source_v162.py -q
"""
import html as _html
import re
import sys
import types
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
# Stub third-party + pydantic modules (absent in this VM)
# ---------------------------------------------------------------------------

def _install_stubs():
    if "tools.news_fetcher" in sys.modules:
        return

    # bs4: regex tag stripper
    bs4_mod = types.ModuleType("bs4")

    class _Soup:
        def __init__(self, raw, parser):
            self.raw = raw or ""

        def get_text(self, separator=" ", strip=True):
            text = re.sub(r"<[^>]+>", separator, self.raw)
            text = _html.unescape(text)
            return separator.join(text.split()) if strip else text

    bs4_mod.BeautifulSoup = _Soup
    sys.modules["bs4"] = bs4_mod

    # httpx: never actually used (tests monkeypatch _http_get)
    httpx_mod = types.ModuleType("httpx")

    class _Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url):
            raise RuntimeError("httpx stub: network disabled in tests")

    httpx_mod.Client = _Client
    httpx_mod.Response = SimpleNamespace  # annotation-only use
    sys.modules["httpx"] = httpx_mod

    # feedparser: minimal RSS 2.0 parser over stdlib xml
    fp_mod = types.ModuleType("feedparser")

    def _parse(content):
        root = ET.fromstring(content)
        entries = []
        for item in root.iter("item"):
            entries.append(SimpleNamespace(
                title=item.findtext("title") or "",
                link=item.findtext("link") or "",
                published=item.findtext("pubDate") or "",
                summary=item.findtext("description") or "",
            ))
        return SimpleNamespace(entries=entries, bozo=False)

    fp_mod.parse = _parse
    sys.modules["feedparser"] = fp_mod

    # core.models: NewsArticle dataclass mirroring the pydantic model's fields
    core_pkg = types.ModuleType("core")
    core_pkg.__path__ = []
    models_mod = types.ModuleType("core.models")

    @dataclass
    class NewsArticle:
        title: str = ""
        link: str = ""
        source: str = ""
        snippet: str = ""
        published: str = ""
        age_hours: object = None
        time_label: str = ""

    models_mod.NewsArticle = NewsArticle
    sys.modules["core"] = core_pkg
    sys.modules["core.models"] = models_mod


# Snapshot before stubbing so we can evict every module the stubs pulled
# in — otherwise the stubbed bs4/httpx/feedparser/core leak into other
# test modules via sys.modules and change their collection behaviour.
_pre_stub_module_keys = set(sys.modules)

_install_stubs()

from tools.news_fetcher import (  # noqa: E402
    NewsFetcher,
    NewsFetchError,
    NewsArticle,
    _topic_score,
)

# Restore the pristine import environment for the rest of the session.
for _key in [k for k in sys.modules if k not in _pre_stub_module_keys
             and k.split(".")[0] in ("bs4", "httpx", "feedparser", "core", "tools")]:
    del sys.modules[_key]
del _pre_stub_module_keys

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_BING_RSS = b"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel><title>Bing News</title>
<item><title>Gurugram metro phase 2 approved - The Hindu</title>
<link>https://www.thehindu.com/gurugram-metro</link>
<pubDate>Thu, 01 Oct 2026 10:00:00 GMT</pubDate>
<description>Metro phase 2 gets green light in Gurugram.</description></item>
<item><title>Unrelated cricket story - ESPN</title>
<link>https://www.espn.com/cricket</link>
<pubDate>Thu, 01 Oct 2026 09:00:00 GMT</pubDate>
<description>Cricket match report.</description></item>
</channel></rss>"""

_DDG_HTML = """
<html><body>
<div class="result">
<a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fmetro-news&amp;rut=abc">Gurugram <b>metro</b> phase 2 green light</a>
<a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fmetro-news">Commuters cheer as the metro stretch is approved.</a>
</div>
<div class="result">
<a rel="nofollow" class="result__a" href="https://direct.example.com/other-story">Direct link story</a>
<a class="result__snippet" href="https://direct.example.com/other-story">Another snippet here.</a>
</div>
</body></html>
"""


def _resp(status=200, text="", content=b""):
    return SimpleNamespace(status_code=status, text=text, content=content)


def _fake_http(monkeypatch, handler):
    """Monkeypatch NewsFetcher._http_get with handler(url) -> response."""
    def _get(self, url):
        return handler(url)
    monkeypatch.setattr(NewsFetcher, "_http_get", _get)


# ---------------------------------------------------------------------------
# DuckDuckGo regex extraction
# ---------------------------------------------------------------------------

def test_ddg_regex_extracts_links_and_unwraps_uddg(monkeypatch):
    _fake_http(monkeypatch, lambda url: _resp(text=_DDG_HTML))
    arts = NewsFetcher()._src_duckduckgo("gurugram metro", 8)
    assert len(arts) == 2
    assert arts[0].title == "Gurugram metro phase 2 green light"
    assert arts[0].link == "https://example.com/metro-news"
    assert arts[0].source == "DuckDuckGo"
    assert "Commuters cheer" in arts[0].snippet
    assert arts[1].link == "https://direct.example.com/other-story"


def test_ddg_skips_internal_links(monkeypatch):
    page = ('<a class="result__a" href="https://duckduckgo.com/?q=x">internal</a>'
            '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Freal.example%2Fa">Real</a>')
    _fake_http(monkeypatch, lambda url: _resp(text=page))
    arts = NewsFetcher()._src_duckduckgo("x", 8)
    assert [a.link for a in arts] == ["https://real.example/a"]


def test_ddg_no_anchors_raises_loudly(monkeypatch):
    _fake_http(monkeypatch, lambda url: _resp(text="<html><body>blocked</body></html>"))
    try:
        NewsFetcher()._src_duckduckgo("x", 8)
    except RuntimeError as e:
        assert "DuckDuckGo" in str(e)
    else:
        raise AssertionError("DDG shape change did not raise")


def test_ddg_http_error_raises(monkeypatch):
    _fake_http(monkeypatch, lambda url: _resp(status=403))
    try:
        NewsFetcher()._src_duckduckgo("x", 8)
    except RuntimeError as e:
        assert "403" in str(e)
    else:
        raise AssertionError("DDG HTTP 403 did not raise")


def test_ddg_real_url_unwrap():
    f = NewsFetcher._ddg_real_url
    assert f("//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa&rut=x") == "https://example.com/a"
    assert f("https://duckduckgo.com/?q=x") == ""
    assert f("https://www.theregister.com/x") == "https://www.theregister.com/x"
    assert f("") == ""


# ---------------------------------------------------------------------------
# Bing RSS
# ---------------------------------------------------------------------------

def test_bing_rss_parsed(monkeypatch):
    _fake_http(monkeypatch, lambda url: _resp(content=_BING_RSS))
    arts = NewsFetcher()._src_bing_news("gurugram metro", 8)
    assert len(arts) == 2
    assert arts[0].title == "Gurugram metro phase 2 approved"
    assert arts[0].source == "The Hindu"  # " - " suffix split
    assert arts[0].link == "https://www.thehindu.com/gurugram-metro"


def test_rss_http_error_raises(monkeypatch):
    _fake_http(monkeypatch, lambda url: _resp(status=500))
    try:
        NewsFetcher()._src_bing_news("x", 8)
    except RuntimeError as e:
        assert "500" in str(e)
    else:
        raise AssertionError("Bing HTTP 500 did not raise")


# ---------------------------------------------------------------------------
# Chain behaviour
# ---------------------------------------------------------------------------

def test_chain_falls_back_google_error_to_bing(monkeypatch):
    def handler(url):
        if "news.google.com" in url:
            raise ConnectionError("dns down")
        return _resp(content=_BING_RSS)
    _fake_http(monkeypatch, handler)
    arts, report = NewsFetcher().search_news_multi("gurugram metro", 8)
    assert any("thehindu.com" in a.link for a in arts)
    by_src = {r["source"]: r for r in report}
    assert by_src["google-news-rss"]["outcome"] == "error"
    assert "dns down" in by_src["google-news-rss"]["detail"]
    assert by_src["bing-news-rss"]["outcome"] == "ok"


def test_chain_uses_ddg_when_rss_empty(monkeypatch):
    def handler(url):
        if "duckduckgo" in url:
            return _resp(text=_DDG_HTML)
        return _resp(content=b'<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>')
    _fake_http(monkeypatch, handler)
    arts, report = NewsFetcher().search_news_multi("gurugram metro", 8)
    # #227: DDG articles carry the publisher name derived from their URL's
    # domain — never the "DuckDuckGo" engine stamp. (This assertion
    # previously expected the stale stamp; the stale label was the bug.)
    assert {a.source for a in arts} == {"Example", "Direct"}
    assert not any(a.source == "DuckDuckGo" for a in arts)
    assert any(r["source"] == "duckduckgo-html" and r["outcome"] == "ok" for r in report)


def test_total_failure_raises_news_fetch_error_with_report(monkeypatch):
    def handler(url):
        raise ConnectionError("network unreachable")
    _fake_http(monkeypatch, handler)
    try:
        NewsFetcher().search_news_multi("gurugram metro", 8)
    except NewsFetchError as e:
        msg = str(e)
        assert "google-news-rss" in msg
        assert "bing-news-rss" in msg
        assert "duckduckgo-html" in msg
        assert "network unreachable" in msg
        assert len(e.report) == 3
        assert all(r["outcome"] == "error" for r in e.report)
    else:
        raise AssertionError("total failure did not raise NewsFetchError")


def test_all_empty_raises_too(monkeypatch):
    empty_rss = b'<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'
    def handler(url):
        if "duckduckgo" in url:
            return _resp(text="<html></html>")  # no anchors -> error
        return _resp(content=empty_rss)
    _fake_http(monkeypatch, handler)
    try:
        NewsFetcher().search_news_multi("some very obscure topic xyz", 8)
    except NewsFetchError as e:
        assert "found nothing" in str(e)
    else:
        raise AssertionError("all-empty did not raise NewsFetchError")


def test_empty_query_raises(monkeypatch):
    try:
        NewsFetcher().search_news_multi("   ", 8)
    except NewsFetchError as e:
        assert "empty query" in str(e)
    else:
        raise AssertionError("empty query did not raise")


# ---------------------------------------------------------------------------
# Ranking / dedupe
# ---------------------------------------------------------------------------

def test_topic_relevance_ranking_prefers_query_match(monkeypatch):
    arts = [
        NewsArticle(title="Cricket world cup final thriller", link="https://a.example/1",
                    source="Wire", snippet="cricket", age_hours=1.0),
        NewsArticle(title="Gurugram metro phase 2 approved for commuters", link="https://b.example/2",
                    source="Wire", snippet="metro", age_hours=20.0),
    ]
    ranked = NewsFetcher()._dedupe_rank_topic(arts, "gurugram metro", 8)
    assert ranked[0].link == "https://b.example/2"


def test_dedupe_across_sources(monkeypatch):
    def handler(url):
        return _resp(content=_BING_RSS)  # same feed for google + bing URLs
    _fake_http(monkeypatch, handler)
    arts, _report = NewsFetcher().search_news_multi("gurugram metro", 8)
    links = [a.link for a in arts]
    assert len(links) == len(set(links))  # no dupes across the two RSS sources


def test_topic_score_counts_terms():
    assert _topic_score("Gurugram metro approved", "", "gurugram metro") > \
        _topic_score("Cricket match report", "", "gurugram metro")
    assert _topic_score("Anything", "", "") == 0


def test_search_news_signature_preserved(monkeypatch):
    _fake_http(monkeypatch, lambda url: _resp(content=_BING_RSS))
    arts = NewsFetcher().search_news("gurugram metro", limit=4)
    assert isinstance(arts, list)
    assert len(arts) <= 4
