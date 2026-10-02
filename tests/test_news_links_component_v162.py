"""v1.6.2 (#156) — News Links renders through a reusable component.

``_render_news_links_row`` owns the full row: "News Links" title + link
chips + "Load more news", including its own alignment (column layout,
markers, per-chip cells). The inline block in ``_render_story_detail``
is now a single call to it — a pure refactor with no behavior change.

These tests drive the component directly with the recording fake
streamlit from test_one_row_toolbar_v16 and assert the presentation
contract: one columns() call whose spec is
[title weight, *chip weights, load-more weight]; one native
link_button per link; the × remove overlay per link; and the
"Load more news" button as the last cell.

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
    {"title": "Alpha headline", "source": "Alpha",
     "url": "https://a.example/story-1"},
    {"title": "Beta headline", "source": "Beta",
     "url": "https://b.example/story-2"},
]


# ---------------------------------------------------------------------------
# component contract: title + chips + load-more in ONE aligned row
# ---------------------------------------------------------------------------

def test_component_renders_single_row_with_all_cells(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_news_links_row("sid1", _LINKS, set())

    assert len(fake.column_specs) == 1, (
        f"component must render exactly one columns() row; "
        f"saw {len(fake.column_specs)}")
    spec = fake.column_specs[0]
    expected = ([lui._section_title_weight("News Links")]
                + lui._chip_col_weights(["Alpha", "Beta"])
                + [lui._load_more_weight("Load more news")])
    assert spec == expected, (
        f"row spec must be [title, *chips, load-more]; "
        f"saw {spec}, expected {expected}")


def test_component_renders_one_link_button_per_link(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_news_links_row("sid1", _LINKS, set())

    assert fake.link_buttons == [
        ("Alpha", "https://a.example/story-1"),
        ("Beta", "https://b.example/story-2"),
    ], f"each link must be a native link_button; saw {fake.link_buttons}"


def test_component_has_load_more_last(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_news_links_row("sid1", _LINKS, set())

    assert ("Load more news", "lib_morenews_sid1") in fake.buttons, (
        f"'Load more news' button must render; saw {fake.buttons}")


def test_component_has_remove_overlay_per_link(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_news_links_row("sid1", _LINKS, set())

    x_buttons = [b for b in fake.buttons if b[0] == "×"]
    assert [b[1] for b in x_buttons] == [
        "lib_xlink_sid1_0", "lib_xlink_sid1_1"], (
        f"each chip needs its × remove button; saw {fake.buttons}")


def test_component_invalid_url_fails_loudly(libdir):
    lui, fake = _ui_with_recording_st()
    bad = [{"title": "Bad link", "source": "Bad",
            "url": "javascript:alert(1)"}]
    lui._render_news_links_row("sid1", bad, set())

    assert fake.link_buttons == [], (
        f"invalid URL must not render a link button; saw {fake.link_buttons}")
    assert any("invalid URL" in e for e in fake.errors), (
        f"invalid URL must surface an error; saw {fake.errors}")


# ---------------------------------------------------------------------------
# #205 — malformed URL renders a compact inline marker (warning pill +
# help tag), NOT a full st.error, inside the scroll row; the full error
# surfaces BELOW the row so the one-line geometry holds.
# ---------------------------------------------------------------------------

def test_component_invalid_url_compact_inline_marker(libdir):
    lui, fake = _ui_with_recording_st()
    bad = [{"title": "Bad link", "source": "Bad",
            "url": "javascript:alert(1)"}]
    lui._render_news_links_row("sid1", bad, set())

    # still exactly one columns() row — geometry preserved with a bad link
    assert len(fake.column_specs) == 1, (
        f"component must render exactly one columns() row; "
        f"saw {len(fake.column_specs)}")
    assert any('data-marker="lib-link-invalid"' in m for m in fake.markup), (
        f"invalid URL must render the compact inline marker; "
        f"saw {fake.markup}")
    warn = [k for k in fake.button_kwargs
            if k.get("key") == "lib_newslink_invalid_sid1_0"]
    assert warn, (
        f"invalid URL must render a warning marker button; "
        f"saw {fake.button_kwargs}")
    w = warn[0]
    assert w["label"] == "", "marker button must be icon-only (no text label)"
    assert w.get("icon") == ":material/warning:", (
        f"marker must use the warning icon; saw {w}")
    assert "invalid URL" in w.get("help", ""), (
        f"marker help tag must name the problem; saw {w}")
    assert fake.link_buttons == [], (
        f"invalid URL must not render a link button; saw {fake.link_buttons}")


def test_component_invalid_url_keeps_remove_overlay(libdir):
    lui, fake = _ui_with_recording_st()
    bad = [{"title": "Bad link", "source": "Bad",
            "url": "javascript:alert(1)"}]
    lui._render_news_links_row("sid1", bad, set())

    assert "lib_xlink_sid1_0" in [b[1] for b in fake.buttons], (
        f"bad link must keep its × remove button; saw {fake.buttons}")


def test_invalid_link_help_names_problem_and_stays_compact(libdir):
    lui, _ = _ui_with_recording_st()
    h = lui._invalid_link_help("javascript:alert(1)")
    assert "invalid URL" in h, f"help tag must name the problem; saw {h!r}"
    assert "javascript:alert(1)" in h, f"help tag must show the URL; saw {h!r}"
    assert len(h) <= 75, f"help tag must stay <=75 chars (HIG §2); saw {h!r}"


def test_invalid_link_help_truncates_long_url(libdir):
    lui, _ = _ui_with_recording_st()
    h = lui._invalid_link_help("https://example.com/" + "x" * 200)
    assert len(h) <= 75, f"help tag must stay <=75 chars (HIG §2); saw {h!r}"
    assert h.endswith("…)"), (
        f"truncated URL must show the ellipsis; saw {h!r}")
    assert "invalid URL" in h, f"help tag must name the problem; saw {h!r}"


# ---------------------------------------------------------------------------
# integration: story detail renders the same row through the component
# ---------------------------------------------------------------------------

def test_story_detail_news_row_unchanged(libdir, monkeypatch):
    lui, fake = _ui_with_recording_st()
    _story(monkeypatch, lui, news_links=_LINKS)
    lui._render_story_detail("sid1")

    assert fake.link_buttons == [
        ("Alpha", "https://a.example/story-1"),
        ("Beta", "https://b.example/story-2"),
    ], f"story detail must render the same chips; saw {fake.link_buttons}"
    assert ("Load more news", "lib_morenews_sid1") in fake.buttons


def test_story_detail_no_links_caption_unchanged(libdir, monkeypatch):
    lui, fake = _ui_with_recording_st()
    _story(monkeypatch, lui, news_links=[])
    lui._render_story_detail("sid1")

    assert fake.link_buttons == []
    assert "No news links yet." in fake.captions, (
        f"empty-links caption must survive the refactor; "
        f"saw {fake.captions}")
