"""#229 — RSS fallback labels must use the publisher name derived from the
item's URL domain, never the fetch-method wire name
("News Wire" / "Bing News" / "Live Wire").

RSS items whose titles lack a " - Publisher" suffix used to be labeled with
the wire name, which then leaked into share text as if it were the
publisher. Regression tests: the label must come from
``publisher_name_from_url(link)``; the wire name survives only as a loud
last resort (with a visible warning) when no publisher can be derived.

feedparser/httpx/bs4/pydantic are absent in this VM, so the test stubs
those modules (stdlib-only) before importing tools.news_fetcher.

Run: python -m pytest tests/test_rss_fallback_labels_229.py -q
"""
import html as _html
import re
import sys
import types
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
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
            src_el = item.find("source")
            src = (SimpleNamespace(title=(src_el.text or "").strip())
                   if src_el is not None and src_el.text else None)
            entries.append(SimpleNamespace(
                title=item.findtext("title") or "",
                link=item.findtext("link") or "",
                published=item.findtext("pubDate") or "",
                summary=item.findtext("description") or "",
                source=src,
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

from tools.news_fetcher import NewsFetcher, publisher_name_from_url  # noqa: E402

# Restore the pristine import environment for the rest of the session.
for _key in [k for k in sys.modules if k not in _pre_stub_module_keys
             and k.split(".")[0] in ("bs4", "httpx", "feedparser", "core", "tools")]:
    del sys.modules[_key]
del _pre_stub_module_keys


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _rss(items_xml):
    return ("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
            "<rss version=\"2.0\"><channel><title>Wire</title>\n"
            + "\n".join(items_xml)
            + "\n</channel></rss>").encode()


def _item(title, link, source_el=""):
    return (f"<item><title>{title}</title><link>{link}</link>"
            f"{source_el}<description>snip</description></item>")


def _resp(content=b""):
    return SimpleNamespace(status_code=200, text="", content=content)


def _fake_http(monkeypatch, content):
    def _get(self, url):
        return _resp(content=content)
    monkeypatch.setattr(NewsFetcher, "_http_get", _get)


_WIRE_NAMES = ("News Wire", "Bing News", "Live Wire")


# ---------------------------------------------------------------------------
# #229: no wire name may leak into the label
# ---------------------------------------------------------------------------

def test_no_suffix_known_host_uses_domain_publisher_not_wire(monkeypatch):
    """Known domain -> mapped publisher display name, not the wire name."""
    _fake_http(monkeypatch, _rss([
        _item("Gurugram metro phase 2 approved",
              "https://www.thehindu.com/gurugram-metro"),
        _item("Market rally continues",
              "https://economictimes.indiatimes.com/markets"),
    ]))
    arts = NewsFetcher()._fetch_rss_or_raise(
        "https://feed.example/rss", 8, fallback_source="Bing News",
        max_age_hours=None)
    assert [a.source for a in arts] == ["The Hindu", "Economic Times"]
    assert all(a.source not in _WIRE_NAMES for a in arts)


def test_no_suffix_unknown_host_uses_titlecased_domain_label(monkeypatch):
    """Unknown domain -> title-cased domain label, never the wire name."""
    _fake_http(monkeypatch, _rss([
        _item("Local story breaks", "https://www.some-local-news.example/x"),
    ]))
    arts = NewsFetcher()._fetch_rss_or_raise(
        "https://feed.example/rss", 8, fallback_source="News Wire",
        max_age_hours=None)
    assert arts[0].source == "Some Local News"
    assert arts[0].source not in _WIRE_NAMES


def test_no_suffix_default_live_wire_never_leaks(monkeypatch):
    """The default fallback_source='Live Wire' must not label items either."""
    _fake_http(monkeypatch, _rss([
        _item("Story without suffix", "https://ndtv.com/india/story"),
    ]))
    arts = NewsFetcher()._fetch_rss_or_raise(
        "https://feed.example/rss", 8, max_age_hours=None)
    assert arts[0].source == "NDTV"
    assert arts[0].source not in _WIRE_NAMES


def test_title_suffix_publisher_still_wins(monkeypatch):
    """A ' - Publisher' suffix keeps working and still takes precedence."""
    _fake_http(monkeypatch, _rss([
        _item("Gurugram metro phase 2 approved - The Hindu",
              "https://www.thehindu.com/gurugram-metro"),
    ]))
    arts = NewsFetcher()._fetch_rss_or_raise(
        "https://feed.example/rss", 8, fallback_source="Bing News",
        max_age_hours=None)
    assert arts[0].title == "Gurugram metro phase 2 approved"
    assert arts[0].source == "The Hindu"


def test_entry_source_element_still_wins(monkeypatch):
    """An RSS <source> element keeps taking precedence over the domain."""
    _fake_http(monkeypatch, _rss([
        _item("Story without suffix", "https://www.thehindu.com/story",
              source_el="<source url=\"https://example.com\">Entry Publisher</source>"),
    ]))
    arts = NewsFetcher()._fetch_rss_or_raise(
        "https://feed.example/rss", 8, fallback_source="Bing News",
        max_age_hours=None)
    assert arts[0].source == "Entry Publisher"


def test_underivable_publisher_warns_loudly_and_keeps_wire(monkeypatch, capsys):
    """No derivable host: the wire name is kept ONLY as a loud last resort —
    a visible warning must be printed, never a silent mislabel."""
    _fake_http(monkeypatch, _rss([
        _item("Story with bad link", "not a url"),
    ]))
    arts = NewsFetcher()._fetch_rss_or_raise(
        "https://feed.example/rss", 8, fallback_source="Bing News",
        max_age_hours=None)
    assert arts[0].source == "Bing News"
    out = capsys.readouterr().out
    assert "#229" in out
    assert "could not derive a publisher name" in out
    assert "Bing News" in out


def test_bing_news_entry_point_never_leaks_wire(monkeypatch):
    """End-to-end via _src_bing_news (fallback_source='Bing News')."""
    _fake_http(monkeypatch, _rss([
        _item("Headline without publisher suffix",
              "https://www.hindustantimes.com/cities/delhi-news"),
    ]))
    arts = NewsFetcher()._src_bing_news("delhi news", 8)
    assert arts[0].source == "Hindustan Times"
    assert arts[0].source not in _WIRE_NAMES


def test_google_news_entry_point_never_leaks_wire(monkeypatch):
    """End-to-end via _src_google_news (fallback_source='News Wire')."""
    _fake_http(monkeypatch, _rss([
        _item("Headline without publisher suffix",
              "https://indianexpress.com/article/india/story"),
    ]))
    arts, _ = NewsFetcher()._src_google_news("delhi news", 8)
    assert arts[0].source == "Indian Express"
    assert arts[0].source not in _WIRE_NAMES


def test_publisher_name_from_url_sanity():
    assert publisher_name_from_url("") == ""
    assert publisher_name_from_url("not a url") == ""
    assert publisher_name_from_url("https://www.thehindu.com/x") == "The Hindu"
