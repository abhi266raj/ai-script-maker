"""Tests for #143: URLs fully resolved after redirects.

- resolve_final_url follows the full redirect chain (multi-hop).
- _resolve_aggregator_links resolves EVERY URL universally (not just
  known aggregator hosts) — catches Bing redirects, shorteners, etc.
- Unresolvable known-redirect URLs are skipped loudly; other
  unresolvable URLs are kept (fail-open for bot-blocking publishers).
- repair_news_link_urls fixes stored redirect URLs in existing stories.

httpx/feedparser/bs4 are absent in this VM, so the test stubs those
modules (stdlib-only) before importing tools.news_fetcher.
"""

import re
import sys
import types
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _install_stubs():
    if "tools.news_fetcher" in sys.modules:
        return
    # bs4 stub: regex tag stripper (same as test_news_multi_source_v162.py)
    import html as _html
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
    # httpx stub (tests monkeypatch _http_get; never hits network)
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
    httpx_mod.Response = SimpleNamespace
    sys.modules["httpx"] = httpx_mod
    # feedparser stub: minimal RSS 2.0 parser over stdlib xml
    # (same as test_news_multi_source_v162.py)
    import xml.etree.ElementTree as ET
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
    # core.models stub
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


_install_stubs()

# Snapshot before stubbing so we can evict every module the stubs pulled
# in — otherwise the stubbed bs4/httpx/feedparser/core leak into other
# test modules via sys.modules and change their behaviour.
_pre_stub_module_keys = set(sys.modules)

from tools.news_fetcher import NewsFetcher, publisher_name_from_url  # noqa: E402
from core.models import NewsArticle  # noqa: E402

# Restore the pristine import environment for the rest of the session.
for _key in [k for k in sys.modules if k not in _pre_stub_module_keys
             and k.split(".")[0] in ("bs4", "httpx", "feedparser", "core", "tools")]:
    del sys.modules[_key]
del _pre_stub_module_keys


class _FakeResponse:
    def __init__(self, url, status_code=200):
        self.url = url
        self.status_code = status_code
        self.text = ""


def _make_fetcher(resolve_map):
    """NewsFetcher whose _http_get follows a fake redirect map.

    resolve_map: {request_url: final_url} — simulates the collapsed
    chain (httpx follow_redirects=True). Missing keys raise
    ConnectionError (unresolvable).
    """
    f = NewsFetcher.__new__(NewsFetcher)
    f._timeout = 8

    def _http_get(url):
        if url in resolve_map:
            return _FakeResponse(resolve_map[url], 200)
        raise ConnectionError(f"blocked: {url}")

    f._http_get = _http_get
    return f


def _art(link):
    return NewsArticle(title="T", link=link, source="S")


class TestResolveFinalUrl:
    def test_multi_hop_chain_fully_resolved(self):
        f = _make_fetcher({
            "https://news.google.com/rss/articles/ABC":
                "https://publisher.example.com/real-article",
        })
        assert f.resolve_final_url("https://news.google.com/rss/articles/ABC") == \
            "https://publisher.example.com/real-article"

    def test_direct_url_unchanged(self):
        f = _make_fetcher({
            "https://publisher.example.com/article":
                "https://publisher.example.com/article",
        })
        assert f.resolve_final_url("https://publisher.example.com/article") == \
            "https://publisher.example.com/article"

    def test_unresolvable_returns_empty(self):
        f = _make_fetcher({})
        assert f.resolve_final_url("https://news.google.com/rss/articles/XYZ") == ""

    def test_non_200_returns_empty(self):
        f = NewsFetcher.__new__(NewsFetcher)
        f._timeout = 8
        f._http_get = lambda url: _FakeResponse(url, 403)
        assert f.resolve_final_url("https://news.google.com/rss/articles/ABC") == ""

    def test_protocol_relative_url(self):
        f = _make_fetcher({
            "https://news.google.com/rss/articles/ABC":
                "https://publisher.example.com/a",
        })
        assert f.resolve_final_url("//news.google.com/rss/articles/ABC") == \
            "https://publisher.example.com/a"

    def test_double_encoded_url_decoded(self):
        f = _make_fetcher({
            "https://publisher.example.com/a?x=1":
                "https://publisher.example.com/a?x=1",
        })
        encoded = "https%3A%2F%2Fpublisher.example.com%2Fa%3Fx%3D1"
        assert f.resolve_final_url(encoded) == "https://publisher.example.com/a?x=1"

    def test_final_still_aggregator_returns_empty(self):
        f = _make_fetcher({
            "https://news.google.com/rss/articles/ABC":
                "https://news.google.com/articles/DEF",
        })
        assert f.resolve_final_url("https://news.google.com/rss/articles/ABC") == ""

    def test_empty_url_returns_empty(self):
        f = _make_fetcher({})
        assert f.resolve_final_url("") == ""
        assert f.resolve_final_url("   ") == ""


class TestUniversalResolution:
    def test_bing_redirect_resolved(self):
        # Bing redirect host NOT in the original #136 list — #143 must
        # still resolve it via the universal chain.
        f = _make_fetcher({
            "https://www.bing.com/news/article/123":
                "https://publisher.example.com/bing-story",
        })
        arts = [_art("https://www.bing.com/news/article/123")]
        kept, skipped = f._resolve_aggregator_links(arts)
        assert skipped == 0
        assert kept[0].link == "https://publisher.example.com/bing-story"

    def test_shortener_resolved(self):
        f = _make_fetcher({
            "https://bit.ly/xyz": "https://publisher.example.com/short-story",
        })
        arts = [_art("https://bit.ly/xyz")]
        kept, skipped = f._resolve_aggregator_links(arts)
        assert kept[0].link == "https://publisher.example.com/short-story"

    def test_unresolvable_aggregator_skipped_loudly(self):
        f = _make_fetcher({})  # nothing resolves
        arts = [_art("https://news.google.com/rss/articles/DEAD")]
        kept, skipped = f._resolve_aggregator_links(arts)
        assert kept == []
        assert skipped == 1

    def test_unresolvable_direct_link_kept_fail_open(self):
        # A direct publisher link whose server blocks bots must NOT be
        # dropped — it still works in the user's browser.
        f = _make_fetcher({})
        arts = [_art("https://publisher.example.com/bot-blocked")]
        kept, skipped = f._resolve_aggregator_links(arts)
        assert len(kept) == 1
        assert kept[0].link == "https://publisher.example.com/bot-blocked"
        assert skipped == 0

    def test_empty_link_skipped(self):
        f = _make_fetcher({})
        arts = [_art("")]
        kept, skipped = f._resolve_aggregator_links(arts)
        assert kept == []
        assert skipped == 1

    def test_direct_link_verified_kept(self):
        f = _make_fetcher({
            "https://publisher.example.com/a": "https://publisher.example.com/a",
        })
        arts = [_art("https://publisher.example.com/a")]
        kept, skipped = f._resolve_aggregator_links(arts)
        assert len(kept) == 1 and skipped == 0


class TestRepairNewsLinkUrls:
    def _patch(self, monkeypatch, links, resolve_map):
        import story_library as lib

        def fake_load(sid):
            return {"meta": {"news_links": links}}

        updated = {}
        monkeypatch.setattr(lib, "load_story", fake_load)
        monkeypatch.setattr(lib, "update_story_fields",
                            lambda sid, **f: updated.update(f))
        fake_fetcher = _make_fetcher(resolve_map)
        # repair_news_link_urls does `from tools.news_fetcher import
        # news_fetcher` at call time — inject a fake module.
        fake_mod = types.ModuleType("tools.news_fetcher")
        fake_mod.news_fetcher = fake_fetcher
        # repair_news_link_urls also imports publisher_name_from_url
        # (#153) — inject the real pure function.
        fake_mod.publisher_name_from_url = publisher_name_from_url
        # _AGGREGATOR_REDIRECT_HOSTS is accessed as news_fetcher._AGGREGATOR_REDIRECT_HOSTS
        monkeypatch.setitem(sys.modules, "tools.news_fetcher", fake_mod)
        return lib, updated

    def test_repairs_stored_redirects(self, monkeypatch):
        lib, updated = self._patch(
            monkeypatch,
            [{"title": "T1", "url": "https://news.google.com/rss/articles/OLD", "source": "G"},
             {"title": "T2", "url": "https://publisher.example.com/fine", "source": "P"}],
            {"https://news.google.com/rss/articles/OLD":
                 "https://publisher.example.com/repaired",
             "https://publisher.example.com/fine":
                 "https://publisher.example.com/fine"})
        changed, note = lib.repair_news_link_urls("x")
        assert changed is True
        urls = [lk["url"] for lk in updated["news_links"]]
        assert "https://publisher.example.com/repaired" in urls
        assert "https://publisher.example.com/fine" in urls
        assert not any("news.google.com" in u for u in urls)
        assert "re-resolved 1" in note

    def test_drops_unresolvable_redirect_loudly(self, monkeypatch):
        lib, updated = self._patch(
            monkeypatch,
            [{"title": "T1", "url": "https://news.google.com/rss/articles/DEAD", "source": "G"}],
            {})
        changed, note = lib.repair_news_link_urls("x")
        assert changed is True
        assert updated["news_links"] == []
        assert "dropped 1" in note

    def test_no_change_when_already_final(self, monkeypatch):
        import story_library as lib
        called = []

        def fake_load(sid):
            return {"meta": {"news_links": [
                {"title": "T", "url": "https://publisher.example.com/a", "source": "P"},
            ]}}

        monkeypatch.setattr(lib, "load_story", fake_load)
        monkeypatch.setattr(lib, "update_story_fields",
                            lambda sid, **f: called.append(f))
        fake_fetcher = _make_fetcher({
            "https://publisher.example.com/a": "https://publisher.example.com/a",
        })
        fake_mod = types.ModuleType("tools.news_fetcher")
        fake_mod.news_fetcher = fake_fetcher
        fake_mod.publisher_name_from_url = publisher_name_from_url
        monkeypatch.setitem(sys.modules, "tools.news_fetcher", fake_mod)

        changed, note = lib.repair_news_link_urls("x")
        assert changed is False
        assert called == []
        assert "already final" in note


class TestPublisherNameFromUrl:
    """#153: publisher display names derived from the final URL's domain."""

    def test_known_publisher(self):
        assert publisher_name_from_url(
            "https://indianexpress.com/article/cities/pune/x-10902805/") == "Indian Express"

    def test_www_prefix_stripped(self):
        assert publisher_name_from_url(
            "https://www.mypunepulse.com/traders-call-off-x/") == "MyPunePulse"

    def test_subdomain_publisher(self):
        assert publisher_name_from_url(
            "https://timesofindia.indiatimes.com/city/pune/x-123.cms") == "Times of India"

    def test_unknown_host_title_cased(self):
        assert publisher_name_from_url(
            "https://some-new-portal.example.org/story") == "Some New Portal"

    def test_empty_url_returns_empty(self):
        assert publisher_name_from_url("") == ""
        assert publisher_name_from_url("   ") == ""
        assert publisher_name_from_url("not a url") == ""


class TestSourceRefreshOnResolution:
    """#153: resolving a URL must refresh the source label to the publisher."""

    def test_fetch_time_source_updated_when_url_resolved(self):
        f = _make_fetcher({
            "https://www.bing.com/news/article/123":
                "https://indianexpress.com/article/x-1/",
        })
        arts = [NewsArticle(title="T", link="https://www.bing.com/news/article/123",
                            source="Bing News")]
        kept, skipped = f._resolve_aggregator_links(arts)
        assert skipped == 0
        assert kept[0].link == "https://indianexpress.com/article/x-1/"
        assert kept[0].source == "Indian Express"

    def test_fetch_time_source_kept_when_url_unchanged(self):
        f = _make_fetcher({
            "https://indianexpress.com/article/x-1/":
                "https://indianexpress.com/article/x-1/",
        })
        arts = [NewsArticle(title="T", link="https://indianexpress.com/article/x-1/",
                            source="Indian Express")]
        kept, _ = f._resolve_aggregator_links(arts)
        assert kept[0].source == "Indian Express"

    def test_repair_refreshes_source_when_url_resolved(self, monkeypatch):
        lib, updated = TestRepairNewsLinkUrls()._patch(
            monkeypatch,
            [{"title": "T1", "url": "https://www.bing.com/news/article/123",
              "source": "Bing News"}],
            {"https://www.bing.com/news/article/123":
                 "https://indianexpress.com/article/x-1/"})
        changed, note = lib.repair_news_link_urls("x")
        assert changed is True
        lk = updated["news_links"][0]
        assert lk["url"] == "https://indianexpress.com/article/x-1/"
        assert lk["source"] == "Indian Express"
        assert "refreshed 1 source label" in note

    def test_repair_refreshes_stale_source_without_url_change(self, monkeypatch):
        # Direct publisher URL whose stored source is still the aggregator.
        lib, updated = TestRepairNewsLinkUrls()._patch(
            monkeypatch,
            [{"title": "T1",
              "url": "https://www.mypunepulse.com/traders-call-off-x/",
              "source": "DuckDuckGo"}],
            {"https://www.mypunepulse.com/traders-call-off-x/":
                 "https://www.mypunepulse.com/traders-call-off-x/"})
        changed, note = lib.repair_news_link_urls("x")
        assert changed is True
        lk = updated["news_links"][0]
        assert lk["url"] == "https://www.mypunepulse.com/traders-call-off-x/"
        assert lk["source"] == "MyPunePulse"
        assert "refreshed 1 source label" in note

    def test_repair_keeps_good_source_when_url_unchanged(self, monkeypatch):
        lib, updated = TestRepairNewsLinkUrls()._patch(
            monkeypatch,
            [{"title": "T1", "url": "https://indianexpress.com/article/x-1/",
              "source": "Indian Express"}],
            {"https://indianexpress.com/article/x-1/":
                 "https://indianexpress.com/article/x-1/"})
        changed, _ = lib.repair_news_link_urls("x")
        assert changed is False
        assert updated == {}


class TestDdgStaleSourceRefresh227:
    """#227: DDG unwraps to the final publisher URL at parse time, so the
    URL never changes in _resolve_aggregator_links — the stale
    "DuckDuckGo" label must still be refreshed to the publisher's name
    (mirrors repair_news_link_urls' condition)."""

    def test_ddg_label_refreshed_when_url_unchanged(self):
        # Exact #227 symptom: a Times of India article whose link is
        # already the final publisher URL was labeled "DuckDuckGo".
        f = _make_fetcher({
            "https://timesofindia.indiatimes.com/city/pune/x-123.cms":
                "https://timesofindia.indiatimes.com/city/pune/x-123.cms",
        })
        arts = [NewsArticle(title="T",
                            link="https://timesofindia.indiatimes.com/city/pune/x-123.cms",
                            source="DuckDuckGo")]
        kept, skipped = f._resolve_aggregator_links(arts)
        assert skipped == 0
        assert kept[0].link == "https://timesofindia.indiatimes.com/city/pune/x-123.cms"
        assert kept[0].source == "Times of India"

    def test_bing_label_refreshed_when_url_unchanged(self):
        f = _make_fetcher({
            "https://indianexpress.com/article/x-1/":
                "https://indianexpress.com/article/x-1/",
        })
        arts = [NewsArticle(title="T", link="https://indianexpress.com/article/x-1/",
                            source="Bing News")]
        kept, _ = f._resolve_aggregator_links(arts)
        assert kept[0].source == "Indian Express"

    def test_wire_labels_refreshed_when_url_unchanged(self):
        for stale in ("News Wire", "Live Wire"):
            f = _make_fetcher({
                "https://www.mypunepulse.com/traders-call-off-x/":
                    "https://www.mypunepulse.com/traders-call-off-x/",
            })
            arts = [NewsArticle(title="T",
                                link="https://www.mypunepulse.com/traders-call-off-x/",
                                source=stale)]
            kept, _ = f._resolve_aggregator_links(arts)
            assert kept[0].source == "MyPunePulse", stale

    def test_non_aggregator_label_untouched_when_url_unchanged(self):
        # A real publisher label must not be clobbered.
        f = _make_fetcher({
            "https://indianexpress.com/article/x-1/":
                "https://indianexpress.com/article/x-1/",
        })
        arts = [NewsArticle(title="T", link="https://indianexpress.com/article/x-1/",
                            source="Indian Express")]
        kept, _ = f._resolve_aggregator_links(arts)
        assert kept[0].source == "Indian Express"

    def test_stale_label_refreshed_when_url_also_resolved(self):
        f = _make_fetcher({
            "https://www.bing.com/news/article/123":
                "https://indianexpress.com/article/x-1/",
        })
        arts = [NewsArticle(title="T", link="https://www.bing.com/news/article/123",
                            source="DuckDuckGo")]
        kept, _ = f._resolve_aggregator_links(arts)
        assert kept[0].link == "https://indianexpress.com/article/x-1/"
        assert kept[0].source == "Indian Express"

    def test_stale_label_warns_loudly_when_publisher_undecipherable(self, caplog):
        # Fail loudly: a final URL with no derivable host keeps the old
        # label audibly (warning), never silently mislabeled.
        f = NewsFetcher.__new__(NewsFetcher)
        f._timeout = 8
        f.resolve_final_url = lambda url: "https://"
        arts = [NewsArticle(title="T", link="https://publisher.example.com/a",
                            source="DuckDuckGo")]
        with caplog.at_level("WARNING", logger="tools.news_fetcher"):
            kept, _ = f._resolve_aggregator_links(arts)
        assert kept[0].source == "DuckDuckGo"
        assert "could not derive publisher name" in caplog.text
