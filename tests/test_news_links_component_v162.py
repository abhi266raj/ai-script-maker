"""v1.6.3 (#303) — News Links renders as a two-panel card component.

``_render_news_links_panel`` (right half of ``_render_tag_link_panels``)
replaces the old single-row chip layout (#283, #274):

- bordered card; header = "News Links" title + Load more + Force fetch
  (icon-only, no text labels, no emoji, no collapse chevron);
- Load more (kind "more_news") appends one more batch of genuinely new
  links via a real network fetch; Force fetch (kind "news") re-pulls
  the full set; both own their loading state (native spinner + disabled
  while running);
- fixed 3-row list height with internal scroll (never resizes);
- rows are read-only single-line headlines with ellipsis; each opens the
  true article URL in a new tab; only the × remove control per row;
- footer reads only "Showing X of Y".

These tests drive the component directly with the recording fake
streamlit from test_one_row_toolbar_v16 and assert that contract.

Run: python -m pytest tests/test_news_links_component_v162.py -q
"""
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
    {"title": "Alpha headline that is quite long and must not wrap",
     "source": "Alpha", "url": "https://a.example/story-1"},
    {"title": "Beta headline", "source": "Beta",
     "url": "https://b.example/story-2"},
]


# ---------------------------------------------------------------------------
# panel contract: card + header (title + load more + force fetch)
# ---------------------------------------------------------------------------

def test_panel_renders_bordered_card(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_news_links_panel(
        story_id="sid1", links=_LINKS, busy_kinds=set())

    cards = [c for c in fake.containers if c["border"] is True]
    assert cards, (
        f"panel must render as a bordered card; saw {fake.containers}")


def test_panel_header_has_title_load_more_and_force_fetch(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_news_links_panel(
        story_id="sid1", links=_LINKS, busy_kinds=set())

    assert any("News Links" in m and "lib-panel-title" in m
               for m in fake.markup), (
        f"panel header must carry the title; saw {fake.markup}")
    keys = [b[1] for b in fake.buttons]
    assert "lib_panel_morenews_sid1" in keys, (
        f"header must have the Load more button; saw {keys}")
    assert "lib_panel_news_sid1" in keys, (
        f"header must have the Force fetch button; saw {keys}")
    # icon-only: empty text labels, no emoji anywhere on the buttons
    for label, key in fake.buttons:
        if key in ("lib_panel_morenews_sid1", "lib_panel_news_sid1"):
            assert label == "", (
                f"header buttons must be icon-only; saw {label!r}")


def test_panel_header_buttons_have_help_tags(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_news_links_panel(
        story_id="sid1", links=_LINKS, busy_kinds=set())

    by_key = {k["key"]: k for k in fake.button_kwargs}
    assert by_key["lib_panel_morenews_sid1"].get("help"), (
        "Load more needs a help tag")
    assert by_key["lib_panel_news_sid1"].get("help"), (
        "Force fetch needs a help tag")


def test_panel_has_no_collapse_chevron(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_news_links_panel(
        story_id="sid1", links=_LINKS, busy_kinds=set())

    assert fake.expanders == [], (
        f"panels do not collapse; saw expanders {fake.expanders}")
    assert not any("chevron" in (m or "").lower() for m in fake.markup), (
        "no collapse chevron in the panel")


# ---------------------------------------------------------------------------
# rows: read-only single-line headlines, true article URLs, × remove only
# ---------------------------------------------------------------------------

def test_panel_link_buttons_open_article_urls(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_news_links_panel(
        story_id="sid1", links=_LINKS, busy_kinds=set())

    assert fake.link_buttons == [
        ("Alpha headline that is quite long and must not wrap",
         "https://a.example/story-1"),
        ("Beta headline", "https://b.example/story-2"),
    ], f"each row must open its true article URL; saw {fake.link_buttons}"


def test_panel_rows_show_headlines_not_sources(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_news_links_panel(
        story_id="sid1", links=_LINKS, busy_kinds=set())

    labels = [lb[0] for lb in fake.link_buttons]
    assert "Alpha" not in labels and "Beta" not in labels, (
        f"rows must show headlines, not source names; saw {labels}")


def test_panel_has_remove_x_per_link_only(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_news_links_panel(
        story_id="sid1", links=_LINKS, busy_kinds=set())

    x_buttons = [b for b in fake.buttons if b[0] == "×"]
    assert [b[1] for b in x_buttons] == [
        "lib_panel_xlink_sid1_0", "lib_panel_xlink_sid1_1"], (
        f"each row needs exactly its × remove button; saw {fake.buttons}")
    # read-only: no editable widgets anywhere in the panel
    assert not any("Add" in (b[0] or "") for b in fake.buttons), (
        "no Add buttons in the panel")


def test_panel_invalid_url_fails_loudly(libdir):
    lui, fake = _ui_with_recording_st()
    bad = [{"title": "Bad link", "source": "Bad",
            "url": "javascript:alert(1)"}]
    lui._render_news_links_panel(
        story_id="sid1", links=bad, busy_kinds=set())

    assert fake.link_buttons == [], (
        f"invalid URL must not render a link button; saw {fake.link_buttons}")
    assert any("invalid URL" in e for e in fake.errors), (
        f"invalid URL must surface an error; saw {fake.errors}")
    assert "lib_panel_xlink_sid1_0" in [b[1] for b in fake.buttons], (
        f"bad link must keep its × remove button; saw {fake.buttons}")


# ---------------------------------------------------------------------------
# fixed 3-row list height + footer contract
# ---------------------------------------------------------------------------

def test_panel_list_has_fixed_height(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_news_links_panel(
        story_id="sid1", links=_LINKS, busy_kinds=set())

    lists = [c for c in fake.containers if c["height"] is not None]
    assert lists, (
        f"panel list must use a fixed-height container; saw {fake.containers}")
    assert lists[0]["height"] == lui._PANEL_LIST_HEIGHT_PX, (
        f"list height must be the 3-row constant; saw {lists[0]['height']}")
    assert lists[0]["border"] is False, (
        "the scroll list itself is borderless inside the card")


def test_panel_footer_shows_only_counts(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_news_links_panel(
        story_id="sid1", links=_LINKS, busy_kinds=set())

    assert "Showing 2 of 2" in fake.captions, (
        f"footer must read only 'Showing X of Y'; saw {fake.captions}")
    assert len(fake.captions) == 1, (
        f"footer is the ONLY caption in the panel; saw {fake.captions}")


def test_panel_empty_shows_zero_counts(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_news_links_panel(
        story_id="sid1", links=[], busy_kinds=set())

    assert "Showing 0 of 0" in fake.captions, (
        f"empty panel footer must read 'Showing 0 of 0'; saw {fake.captions}")
    assert fake.link_buttons == []


# ---------------------------------------------------------------------------
# loading states: the tapped button owns the spinner, sibling blocks
# ---------------------------------------------------------------------------

def test_panel_load_more_spins_while_running(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_news_links_panel(
        story_id="sid1", links=_LINKS, busy_kinds={"more_news"})

    by_key = {k["key"]: k for k in fake.button_kwargs}
    btn = by_key["lib_panel_morenews_sid1"]
    assert btn.get("icon") == "spinner", (
        f"Load more must show the spinner while running; saw {btn}")
    assert btn.get("disabled") is True


def test_panel_force_fetch_blocked_while_load_more_runs(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_news_links_panel(
        story_id="sid1", links=_LINKS, busy_kinds={"more_news"})

    by_key = {k["key"]: k for k in fake.button_kwargs}
    btn = by_key["lib_panel_news_sid1"]
    assert btn.get("disabled") is True, (
        "Force fetch must block while Load more runs (same field)")
    assert btn.get("icon") != "spinner", (
        "blocked is not working — no spinner on the blocked button")


# ---------------------------------------------------------------------------
# integration: story detail renders the panels through the section
# ---------------------------------------------------------------------------

def test_story_detail_renders_news_panel(libdir, monkeypatch):
    lui, fake = _ui_with_recording_st()
    _story(monkeypatch, lui, news_links=_LINKS)
    lui._render_story_detail("sid1")

    assert fake.link_buttons == [
        ("Alpha headline that is quite long and must not wrap",
         "https://a.example/story-1"),
        ("Beta headline", "https://b.example/story-2"),
    ], f"story detail must render the panel rows; saw {fake.link_buttons}"
    assert ("", "lib_panel_morenews_sid1") in fake.buttons
    assert "Showing 2 of 2" in fake.captions


def test_story_detail_empty_links_panel(libdir, monkeypatch):
    lui, fake = _ui_with_recording_st()
    _story(monkeypatch, lui, news_links=[])
    lui._render_story_detail("sid1")

    assert fake.link_buttons == []
    assert "Showing 0 of 0" in fake.captions, (
        f"empty panel must show zero counts; saw {fake.captions}")
    assert "No news links yet." not in fake.captions, (
        "the old hint caption is gone — the footer is the only text")
