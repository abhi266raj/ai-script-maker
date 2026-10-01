"""v1.6.2 (#133, #135, #136) — news source fairness + link validity.

#133: source order is randomized on every search_news call and each
      source contributes at most 2 articles (round-robin).
#135: DuckDuckGo `uddg` values are double-encoded in the wild — decode
      until stable and reject non-http(s) results.
#136: Google News RSS links are aggregator redirects; resolve them to
      the final publisher URL before storage, skipping unresolvable
      ones loudly (never let a news.google.com URL reach the UI).

feedparser/httpx/bs4/pydantic are absent in this VM, so the test stubs
those modules (stdlib-only) before importing tools.news_fetcher.

Run: python -m pytest tests/test_news_sources_133_135_136.py -q
"""
import random
import re
import sys
import types
import urllib.parse
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
import html as _html

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
# Stub third-party + pydantic modules (absent in this VM)
# ---------------------------------------------------------------------------

def _install_stubs():
    if "tools.news_fetcher" in sys.modules:
        return

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


_pre_stub_module_keys = set(sys.modules)

_install_stubs()

from tools.news_fetcher import (  # noqa: E402
    NewsFetcher,
    NewsFetchError,
    NewsArticle,
)

for _key in [k for k in sys.modules if k not in _pre_stub_module_keys
             and k.split(".")[0] in ("bs4", "httpx", "feedparser", "core", "tools")]:
    del sys.modules[_key]
del _pre_stub_module_keys

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resp(status=200, text="", content=b"", url=""):
    return SimpleNamespace(status_code=status, text=text, content=content, url=url)


def _boom(self, *a):
    raise RuntimeError("source down")


def _src_stub(name, label, arts):
    """Build a _src_* replacement returning canned articles + report entry."""
    def _f(self, q, limit):
        return list(arts), [{"source": label, "outcome": "ok" if arts else "empty",
                             "count": len(arts), "detail": ""}]
    _f.__name__ = name
    return _f


# ---------------------------------------------------------------------------
# #135 — uddg decoding
# ---------------------------------------------------------------------------

def test_ddg_real_url_decodes_double_encoded_uddg():
    f = NewsFetcher._ddg_real_url
    # real DDG HTML double-encodes the target (parse_qs decodes once)
    assert f("//duckduckgo.com/l/?uddg=https%253A%252F%252Fexample.com%252Fa&rut=x") == \
        "https://example.com/a"
    # triple-encoded is unwound too
    assert f("//duckduckgo.com/l/?uddg=https%25253A%25252F%25252Fexample.com%25252Fa") == \
        "https://example.com/a"
    # single-encoded still works
    assert f("//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa&rut=x") == \
        "https://example.com/a"


def test_ddg_real_url_rejects_non_http():
    f = NewsFetcher._ddg_real_url
    bad = urllib.parse.quote("javascript:alert(1)", safe="")
    assert f(f"//duckduckgo.com/l/?uddg={bad}&rut=x") == ""
    assert f("//duckduckgo.com/l/?rut=x") == ""          # uddg missing
    assert f("https://duckduckgo.com/?q=x") == ""        # internal page
    assert f("") == ""


def test_ddg_src_decodes_double_encoded_links(monkeypatch):
    page = ('<html><body><a rel="nofollow" class="result__a" '
            'href="//duckduckgo.com/l/?uddg=https%253A%252F%252Fpublisher.example%252Fstory%253Fid%253D1'
            '&amp;rut=abc">Metro story</a></body></html>')
    monkeypatch.setattr(NewsFetcher, "_http_get", lambda self, url: _resp(text=page))
    arts = NewsFetcher()._src_duckduckgo("metro", 8)
    assert len(arts) == 1
    assert arts[0].link == "https://publisher.example/story?id=1"
    assert "%3A" not in arts[0].link and "%2F" not in arts[0].link


# ---------------------------------------------------------------------------
# #133 — randomized order + round-robin 1-2 per source
# ---------------------------------------------------------------------------

def test_source_order_varies_and_is_seeded(monkeypatch):
    calls = []

    def mk_list(name, label):
        art = NewsArticle(title=f"{name} metro news", link=f"https://{name}.example/1",
                          source=label, snippet="metro")
        def _f(self, q, limit):
            calls.append(name)
            return [art]
        return _f

    def mk_google(name, label):
        art = NewsArticle(title=f"{name} metro news", link=f"https://{name}.example/1",
                          source=label, snippet="metro")
        def _f(self, q, limit):
            calls.append(name)
            return [art], [{"source": label, "outcome": "ok", "count": 1, "detail": ""}]
        return _f

    monkeypatch.setattr(NewsFetcher, "_src_google_news", mk_google("google", "google-news-rss/24h"))
    monkeypatch.setattr(NewsFetcher, "_src_bing_news", mk_list("bing", "bing-news-rss"))
    monkeypatch.setattr(NewsFetcher, "_src_duckduckgo", mk_list("ddg", "duckduckgo-html"))

    orders = []
    for seed in range(12):
        calls.clear()
        NewsFetcher().search_news_multi("metro", 8, rng=random.Random(seed))
        orders.append(tuple(calls))
    assert len(set(orders)) >= 2, "source order never varied across 12 seeds"

    calls.clear()
    NewsFetcher().search_news_multi("metro", 8, rng=random.Random(3))
    first = tuple(calls)
    calls.clear()
    NewsFetcher().search_news_multi("metro", 8, rng=random.Random(3))
    assert tuple(calls) == first, "same seed must give same order"

    for o in orders:
        assert sorted(o) == ["bing", "ddg", "google"], f"each run must hit all 3 sources once: {o}"


def test_round_robin_caps_two_per_source(monkeypatch):
    asked = {}

    def mk_list(name, label):
        def _f(self, q, limit):
            asked[name] = limit
            arts = [NewsArticle(title=f"{name} metro story {i} xyz",
                                link=f"https://{name}.example/{i}",
                                source=label, snippet="metro")
                    for i in range(5)]
            return arts[:limit]
        return _f

    def mk_google(name, label):
        def _f(self, q, limit):
            asked[name] = limit
            arts = [NewsArticle(title=f"{name} metro story {i} xyz",
                                link=f"https://{name}.example/{i}",
                                source=label, snippet="metro")
                    for i in range(5)]
            return arts[:limit], [{"source": label, "outcome": "ok",
                                   "count": min(5, limit), "detail": ""}]
        return _f

    monkeypatch.setattr(NewsFetcher, "_src_google_news", mk_google("google", "google-news-rss/24h"))
    monkeypatch.setattr(NewsFetcher, "_src_bing_news", mk_list("bing", "bing-news-rss"))
    monkeypatch.setattr(NewsFetcher, "_src_duckduckgo", mk_list("ddg", "duckduckgo-html"))

    arts, _report = NewsFetcher().search_news_multi("metro", 8, rng=random.Random(1))
    assert asked == {"google": 2, "bing": 2, "ddg": 2}, f"each source asked for 2, got {asked}"
    counts = Counter(a.source for a in arts)
    assert all(v <= 2 for v in counts.values()), f"more than 2 from one source: {counts}"
    assert len(arts) <= 6


def test_total_failure_names_all_sources(monkeypatch):
    monkeypatch.setattr(NewsFetcher, "_src_google_news", _boom)
    monkeypatch.setattr(NewsFetcher, "_src_bing_news", _boom)
    monkeypatch.setattr(NewsFetcher, "_src_duckduckgo", _boom)
    try:
        NewsFetcher().search_news_multi("metro", 8)
    except NewsFetchError as e:
        msg = str(e)
        assert "google-news-rss" in msg
        assert "bing-news-rss" in msg
        assert "duckduckgo-html" in msg
    else:
        raise AssertionError("total failure did not raise NewsFetchError")


# ---------------------------------------------------------------------------
# #136 — aggregator redirects resolve to publisher URLs
# ---------------------------------------------------------------------------

_G_REDIRECT = "https://news.google.com/rss/articles/CBMiXWh0dHBzOi8vZXhhbXBsZS5jb20?oc=5"


def test_google_redirect_resolved_to_publisher_url(monkeypatch):
    g = NewsArticle(title="Gurugram metro approved", link=_G_REDIRECT,
                    source="News Wire", snippet="metro")
    monkeypatch.setattr(NewsFetcher, "_src_google_news",
                        _src_stub("g", "google-news-rss/24h", [g]))
    monkeypatch.setattr(NewsFetcher, "_src_bing_news", _boom)
    monkeypatch.setattr(NewsFetcher, "_src_duckduckgo", _boom)

    def fake_get(self, url):
        if "news.google.com/rss/articles" in url:
            return _resp(url="https://publisher.example.com/metro-story")
        raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setattr(NewsFetcher, "_http_get", fake_get)
    arts, _report = NewsFetcher().search_news_multi("gurugram metro", 8, rng=random.Random(0))
    assert len(arts) == 1
    assert arts[0].link == "https://publisher.example.com/metro-story"
    assert not any("news.google.com" in a.link for a in arts)


def test_unresolvable_redirect_skipped_loudly(monkeypatch):
    g = NewsArticle(title="Gurugram metro approved", link=_G_REDIRECT,
                    source="News Wire", snippet="metro")
    b = NewsArticle(title="Gurugram metro phase 2 green light", link="https://www.thehindu.com/x",
                    source="The Hindu", snippet="metro")
    monkeypatch.setattr(NewsFetcher, "_src_google_news",
                        _src_stub("g", "google-news-rss/24h", [g]))
    monkeypatch.setattr(NewsFetcher, "_src_bing_news", lambda self, q, limit: [b])
    monkeypatch.setattr(NewsFetcher, "_src_duckduckgo", _boom)

    def fake_get(self, url):
        raise ConnectionError("redirect blocked")

    monkeypatch.setattr(NewsFetcher, "_http_get", fake_get)
    arts, report = NewsFetcher().search_news_multi("gurugram metro", 8, rng=random.Random(0))
    assert not any("news.google.com" in a.link for a in arts), "aggregator URL leaked to output"
    assert any("redirect" in str(r.get("detail", "")).lower()
               and "skip" in str(r.get("detail", "")).lower() for r in report), \
        f"skip not reported loudly: {report}"


def test_all_redirects_unresolvable_raises(monkeypatch):
    g = NewsArticle(title="Gurugram metro approved", link=_G_REDIRECT,
                    source="News Wire", snippet="metro")
    monkeypatch.setattr(NewsFetcher, "_src_google_news",
                        _src_stub("g", "google-news-rss/24h", [g]))
    monkeypatch.setattr(NewsFetcher, "_src_bing_news", _boom)
    monkeypatch.setattr(NewsFetcher, "_src_duckduckgo", _boom)

    def fake_get(self, url):
        raise ConnectionError("redirect blocked")

    monkeypatch.setattr(NewsFetcher, "_http_get", fake_get)
    try:
        NewsFetcher().search_news_multi("gurugram metro", 8, rng=random.Random(0))
    except NewsFetchError as e:
        assert "redirect" in str(e).lower(), f"skip not loud in: {e}"
    else:
        raise AssertionError("all-unresolvable did not raise NewsFetchError")
