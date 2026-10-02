"""v1.6.2 (#134) — clicking a news link must open the article.

Root cause: news links were raw-HTML ``<a>`` anchors inside
``st.markdown(unsafe_allow_html=True)``. Streamlit's markdown pipeline
(react-markdown + rehype) neuters the anchor — clicks do nothing.
The fix renders each news link as a NATIVE ``st.link_button`` (which
forces a new browser tab — the same guarantee the #95 WhatsApp comment
relies on). Since #303 the links live in the News Links panel as
single-line headline rows (ellipsis) with the × remove control; the
source moved to the tooltip.

These tests drive the real ``_render_story_detail`` with the recording
fake streamlit from test_one_row_toolbar_v16 (which records
link_button calls) and assert the presentation contract + CSS.

Run: python -m pytest tests/test_news_link_button_v162.py -q
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import story_library as lib  # noqa: E402
from test_library_v15 import libdir  # noqa: F401  (pytest fixture reuse)
from test_one_row_toolbar_v16 import (  # noqa: E402
    _story,
    _ui_with_recording_st,
)


_LINKS = [
    {"title": "Alpha headline", "source": "Alpha",
     "url": "https://a.example/story-1"},
    {"title": "Beta headline", "source": "Beta",
     "url": "https://b.example/story-2"},
]


# ---------------------------------------------------------------------------
# rendering: native link buttons, not raw anchors
# ---------------------------------------------------------------------------

def test_news_links_render_as_link_buttons(libdir, monkeypatch):
    lui, fake = _ui_with_recording_st()
    _story(monkeypatch, lui, news_links=_LINKS)
    lui._render_story_detail("sid1")

    # #303: rows show the headline (single line, ellipsis) and open the
    # true article URL — the source moved to the tooltip.
    assert fake.link_buttons == [
        ("Alpha headline", "https://a.example/story-1"),
        ("Beta headline", "https://b.example/story-2"),
    ], f"each news link must be a native link_button; saw {fake.link_buttons}"


def test_news_links_have_no_raw_html_anchor(libdir, monkeypatch):
    lui, fake = _ui_with_recording_st()
    _story(monkeypatch, lui, news_links=_LINKS)
    lui._render_story_detail("sid1")

    anchors = [m for m in fake.markup if "<a href" in m]
    assert not anchors, \
        f"news links must not render raw <a> anchors; saw {anchors!r}"


def test_remove_x_overlay_still_rendered_per_link(libdir, monkeypatch):
    lui, fake = _ui_with_recording_st()
    _story(monkeypatch, lui, news_links=_LINKS)
    lui._render_story_detail("sid1")

    x_keys = [k for (label, k) in fake.buttons
              if label == "×" and (k or "").startswith("lib_panel_xlink_")]
    assert len(x_keys) == 2, \
        f"each news link keeps its × remove button; saw {fake.buttons!r}"


def test_hashtag_chips_untouched(libdir, monkeypatch):
    """#303 replaced hashtag chips with panel rows (same × pattern)."""
    lui, fake = _ui_with_recording_st()
    _story(monkeypatch, lui, news_links=_LINKS, hashtags=["#DogShowdown"])
    lui._render_story_detail("sid1")

    rows = [m for m in fake.markup if 'class="lib-panel-row"' in m]
    assert len(rows) == 1 and "#DogShowdown" in rows[0]


# ---------------------------------------------------------------------------
# fail loudly: malformed URLs
# ---------------------------------------------------------------------------

def test_malformed_url_fails_loudly_no_dead_chip(libdir, monkeypatch):
    lui, fake = _ui_with_recording_st()
    _story(monkeypatch, lui, news_links=[
        {"title": "Good", "source": "G", "url": "https://g.example/ok"},
        {"title": "Bad", "source": "B", "url": "not-a-url"},
        {"title": "Empty", "source": "E", "url": ""},
        {"title": "JS", "source": "J", "url": "javascript:alert(1)"},
    ])
    lui._render_story_detail("sid1")

    assert fake.link_buttons == [("Good", "https://g.example/ok")], \
        f"only the valid URL becomes a link button; saw {fake.link_buttons}"
    assert len(fake.errors) == 3, \
        f"each malformed URL must surface st.error; saw {fake.errors!r}"
    # The × remove buttons still render so bad links can be deleted.
    x_keys = [k for (label, k) in fake.buttons
              if label == "×" and (k or "").startswith("lib_panel_xlink_")]
    assert len(x_keys) == 4


def test_is_openable_article_url():
    lui, _ = _ui_with_recording_st()
    assert lui._is_openable_article_url("https://a.example/x") is True
    assert lui._is_openable_article_url("http://a.example/x") is True
    assert lui._is_openable_article_url("not-a-url") is False
    assert lui._is_openable_article_url("") is False
    assert lui._is_openable_article_url("javascript:alert(1)") is False
    assert lui._is_openable_article_url("https://") is False
    assert lui._is_openable_article_url(None) is False


# ---------------------------------------------------------------------------
# CSS contract
# ---------------------------------------------------------------------------

def _css_source():
    src = (Path(__file__).resolve().parent.parent / "library_ui.py").read_text()
    return re.sub(r"/\*.*?\*/", "", src, flags=re.S)


def test_link_button_chip_pill_css():
    clean = _css_source()
    # The link_button's anchor is styled as the chip pill.
    assert '[data-testid="stLinkButton"] a' in clean
    assert "border-radius: 999px" in clean
    assert "var(--lib-chip-bg)" in clean
    assert "var(--lib-chip-text)" in clean
    assert "var(--lib-chip-border)" in clean
    # 44px right clearance for the × (same as .lib-chip).
    assert "padding: 3px 44px 3px 12px" in clean


def test_x_overlay_selectors_cover_link_button_columns():
    clean = _css_source()
    assert (':has(.lib-chip, [data-testid="stLinkButton"], '
            '[data-marker="lib-link-invalid"])') in clean, \
        "the chip × positioning must apply to news-link-button columns " \
        "(#205: and to invalid-URL marker columns) too"


def test_no_global_svg_fill_stroke_forcing():
    clean = _css_source()
    for line in clean.splitlines():
        s = line.strip()
        if re.match(r"^(fill|stroke)\s*:", s) and "!important" in s:
            assert False, f"global SVG fill/stroke forcing: {s!r}"
