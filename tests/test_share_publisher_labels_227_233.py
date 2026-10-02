"""Share-label publisher fixes — remaining gaps (#227/#231/#233 follow-ups).

Issues #227/#229/#230/#231/#232 shipped fixes on develop; re-audit found
three gaps in the same bug class (a fetch-method/aggregator label shown
where the publisher name belongs):

1. Fetch-time fail-open (#227-class): ``_resolve_aggregator_links`` kept a
   stale aggregator label ("DuckDuckGo") when ``resolve_final_url`` failed
   on a direct publisher URL (bot-blocking sites like Times of India). The
   label must refresh from the URL's domain — fail-open applies to the
   URL, never the label (#230's principle).
2. ``_compose_news_tags_text`` (copy/WhatsApp share text) never normalized
   stale labels — only the Telegram path did (#231). A stale label must
   never reach any user-facing share text.
3. News-link chips (#233) rendered the stored ``source`` verbatim; the
   render path must normalize stale labels like the share paths do.
   (#303 later replaced the chips with panel rows that render the
   headline only — no source label, no stale-label surface.)

feedparser/httpx/bs4/pydantic/streamlit are absent in this VM, so the test
stubs those modules (stdlib-only) before importing.

Run: python -m pytest tests/test_share_publisher_labels_227_233.py -q

NOTE: unlike some older test modules, this file does NOT stub
third-party modules — the repo venv ships the real feedparser, httpx,
bs4 and streamlit (1.64.0), so plain imports are used. Stubbing them
here broke ~80 unrelated tests via sys.modules pollution.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_repo_root = Path(__file__).resolve().parent.parent

from tools.news_fetcher import NewsFetcher, publisher_name_from_url  # noqa: E402
import story_library as lib  # noqa: E402
import library_ui as lui  # noqa: E402

TOI_URL = "https://timesofindia.indiatimes.com/india/sample-article.cms"
HINDU_URL = "https://www.thehindu.com/news/sample-article.cms"


def _ddg_article(url=TOI_URL, source="DuckDuckGo"):
    return SimpleNamespace(
        title="Sample headline", link=url, source=source,
        snippet="", published="", age_hours=None, time_label="")


# ---------------------------------------------------------------------------
# 1. Fetch-time fail-open refreshes the stale label (#227-class)
# ---------------------------------------------------------------------------

def test_resolve_fail_open_refreshes_stale_label():
    """Bot-blocking publisher URL: resolution fails (""), the URL is kept
    as-is (fail-open) but the stale "DuckDuckGo" label must become the
    publisher name derived from the domain."""
    fetcher = NewsFetcher()
    fetcher.resolve_final_url = lambda url: ""  # bot-blocked, like TOI
    kept, skipped = fetcher._resolve_aggregator_links(
        [_ddg_article(TOI_URL, "DuckDuckGo")])
    assert len(kept) == 1 and skipped == 0
    assert kept[0].link == TOI_URL  # URL untouched — fail-open
    assert kept[0].source == "Times of India"  # label refreshed, not stale


def test_resolve_fail_open_keeps_honest_label():
    """An honest (non-aggregator) label is never rewritten."""
    fetcher = NewsFetcher()
    fetcher.resolve_final_url = lambda url: ""
    kept, _ = fetcher._resolve_aggregator_links(
        [_ddg_article(HINDU_URL, "The Hindu")])
    assert kept[0].source == "The Hindu"


def test_resolve_fail_open_wire_labels_refreshed():
    """All stale wire/engine names refresh, not just DuckDuckGo."""
    fetcher = NewsFetcher()
    fetcher.resolve_final_url = lambda url: ""
    for stale in ("Bing News", "News Wire", "Live Wire"):
        kept, _ = fetcher._resolve_aggregator_links([_ddg_article(source=stale)])
        assert kept[0].source == "Times of India", stale


# ---------------------------------------------------------------------------
# 2. Copy/WhatsApp share text normalizes stale labels (#231-class)
# ---------------------------------------------------------------------------

def _meta_with_link(source):
    return {"title": "T", "hashtags": [],
            "news_links": [{"title": "X", "url": TOI_URL, "source": source}]}


def test_compose_share_text_normalizes_stale_label():
    text = lui._compose_news_tags_text(_meta_with_link("DuckDuckGo"), "T")
    assert "Times of India: " + TOI_URL in text
    assert "DuckDuckGo" not in text


def test_compose_share_text_keeps_honest_label():
    text = lui._compose_news_tags_text(_meta_with_link("The Hindu"), "T")
    assert "The Hindu: " + TOI_URL in text


def test_compose_share_text_empty_source_still_uses_publisher():
    """#232 behavior preserved: empty source -> publisher name, not netloc."""
    text = lui._compose_news_tags_text(_meta_with_link(""), "T")
    assert "Times of India: " + TOI_URL in text
    assert "timesofindia.indiatimes.com:" not in text


# ---------------------------------------------------------------------------
# 3. News-link render path — #303 replaced the chips with panel rows.
# The panel renders the headline only (never the stored source label),
# so no stale aggregator label can surface in the UI. The normalizer
# itself still serves the share paths.
# ---------------------------------------------------------------------------

def test_panel_render_path_has_no_stale_label_surface():
    """#303: the chip render path is gone — the News Links panel renders
    the headline as the row label and never touches the stored source,
    so there is no stale-label surface left in the render path."""
    import library_ui as lui_mod
    assert not hasattr(lui_mod, "_render_news_links_row"), (
        "the chip row must stay removed")
    assert not hasattr(lui_mod, "_news_chip_label"), (
        "the source-name chip label must stay removed")


def test_stale_label_normalizer_still_serves_share_paths():
    """End-to-end label logic: stale label -> normalizer -> publisher
    name (used by the share/copy paths)."""
    normalized = lib.refresh_stale_news_link_source("DuckDuckGo", TOI_URL)
    assert normalized == "Times of India"
    assert "DuckDuckGo" not in normalized


def test_normalizer_leaves_honest_labels_alone():
    assert lib.refresh_stale_news_link_source("The Hindu", TOI_URL) == "The Hindu"
    assert lib.refresh_stale_news_link_source("", TOI_URL) == ""
