"""v1.6.2 (#154) — all section rows render through dedicated reusable components.

``_render_title_row``, ``_render_images_row`` and ``_render_upload_popover_trigger``
each own their row; since #303 the hashtags/news-links sections render as
two side-by-side panel cards (``_render_hashtags_panel`` /
``_render_news_links_panel``) instead of single chip rows.
The inline blocks in ``_render_story_detail`` are now single calls —
pure refactors with no behavior change.

These tests drive each component directly with the recording fake
streamlit and assert the presentation contract: one columns() call per
row with the expected spec, and the expected controls per cell.

Run: python -m pytest tests/test_row_components_v162.py -q
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


# ---------------------------------------------------------------------------
# _render_title_row: h2 + edit icon in one [11, 1] row (or text area)
# ---------------------------------------------------------------------------

def test_title_row_renders_single_row(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_title_row("teststory1", "My Title", editing=False, busy=False)

    assert len(fake.column_specs) == 1, (
        f"title must render exactly one columns() row; "
        f"saw {len(fake.column_specs)}")
    assert fake.column_specs[0] == [11, 1], (
        f"title row spec must be [11, 1]; saw {fake.column_specs[0]}")


def test_title_row_renders_h2_and_edit_button(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_title_row("teststory1", "My Title", editing=False, busy=False)

    assert any("My Title" in m and "lib-doc-title" in m
               for m in fake.markup), (
        f"title h2 must render; saw {fake.markup}")
    assert ("", "lib_title_edit_teststory1") in fake.buttons, (
        f"edit icon button must render; saw {fake.buttons}")


def test_title_row_editing_renders_text_area(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_title_row("teststory1", "My Title", editing=True, busy=False)

    assert fake.column_specs == [], (
        f"editing mode must not render the columns row; "
        f"saw {fake.column_specs}")
    assert ("", "lib_title_edit_teststory1") not in fake.buttons


# ---------------------------------------------------------------------------
# _render_hashtags_panel: card with header (title + load more + force
# fetch), fixed-height list, read-only rows with ×, "Showing X of Y"
# ---------------------------------------------------------------------------

_TAGS = ["#Alpha", "#Beta"]


def test_hashtags_panel_renders_card_with_header(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_hashtags_panel(
        story_id="teststory1", tags=_TAGS, busy_kinds=set(),
        ai_engine="Dummy")

    cards = [c for c in fake.containers if c["border"] is True]
    assert cards, (
        f"panel must render as a bordered card; saw {fake.containers}")
    assert any("Hashtags" in m and "lib-panel-title" in m
               for m in fake.markup), (
        f"'Hashtags' panel title must render; saw {fake.markup}")
    keys = [b[1] for b in fake.buttons]
    assert "lib_panel_moretags_teststory1" in keys, (
        f"Load more button must render; saw {keys}")
    assert "lib_panel_tags_teststory1" in keys, (
        f"Force fetch button must render; saw {keys}")


def test_hashtags_panel_renders_rows_and_remove_buttons(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_hashtags_panel(
        story_id="teststory1", tags=_TAGS, busy_kinds=set(),
        ai_engine="Dummy")

    for tag in _TAGS:
        assert any(tag in m and "lib-panel-row" in m for m in fake.markup), (
            f"row for {tag} must render; saw {fake.markup}")
    x_buttons = [b for b in fake.buttons if b[0] == "×"]
    assert [b[1] for b in x_buttons] == [
        "lib_panel_xtag_teststory1_0", "lib_panel_xtag_teststory1_1"], (
        f"each row needs its × remove button; saw {fake.buttons}")
    assert "Showing 2 of 2" in fake.captions, (
        f"footer must read 'Showing 2 of 2'; saw {fake.captions}")


# ---------------------------------------------------------------------------
# _render_images_row: cards + Load more in one scroll row
# ---------------------------------------------------------------------------

def test_images_row_renders_single_row(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_images_row("teststory1", ["https://img.example/a.jpg"], ["up1.png"],
                           set())

    assert len(fake.column_specs) == 1, (
        f"images must render exactly one columns() row; "
        f"saw {len(fake.column_specs)}")
    spec = fake.column_specs[0]
    expected = [1, 1, lui._load_more_weight()]
    assert spec == expected, (
        f"row spec must be [1, 1, load-more]; saw {spec}, expected {expected}")


def test_images_row_has_load_more_and_remove_overlays(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_images_row("teststory1", ["https://img.example/a.jpg"], ["up1.png"],
                           set())

    assert ("", "lib_moreimg_teststory1") in fake.buttons, (
        f"icon-only load-more button must render; saw {fake.buttons}")
    x_buttons = [b for b in fake.buttons if b[0] == "×"]
    assert [b[1] for b in x_buttons] == [
        "lib_ximg_teststory1_0", "lib_xup_teststory1_1"], (
        f"each card needs its × remove button; saw {fake.buttons}")


def test_images_row_fetched_card_has_edit_overlay(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_images_row("teststory1", ["https://img.example/a.jpg"], [], set())

    assert ("✎", "lib_xedit_teststory1_0") in fake.buttons, (
        f"fetched card needs its ✎ address-editor button; "
        f"saw {fake.buttons}")


# ---------------------------------------------------------------------------
# _render_upload_popover_trigger: icon-only upload trigger (no row)
# ---------------------------------------------------------------------------

def test_upload_row_renders_single_row(libdir):
    """The standalone Upload row is gone — the trigger renders no columns
    row of its own; it lives in the detail toolbar beside Share/Copy."""
    lui, fake = _ui_with_recording_st()
    lui._render_upload_popover_trigger("teststory1")

    assert fake.column_specs == [], (
        f"upload trigger must render no columns() row; "
        f"saw {fake.column_specs}")
    assert any('data-marker="lib-upload-btn"' in m for m in fake.markup), (
        "upload trigger marker must render for the marker-scoped CSS")


def test_upload_row_renders_title_and_popover(libdir):
    """No 'Upload' title anymore — the icon-only popover trigger still
    renders exactly once."""
    lui, fake = _ui_with_recording_st()
    lui._render_upload_popover_trigger("teststory1")

    assert not any("lib-section-inline" in m and "Upload" in m
                   for m in fake.markup), (
        "standalone 'Upload' title must be gone")
    assert len(fake.popovers) == 1, (
        f"upload popover must render once; saw {len(fake.popovers)}")


# ---------------------------------------------------------------------------
# integration: story detail renders the same rows through the components
# ---------------------------------------------------------------------------

def test_story_detail_rows_unchanged(libdir, monkeypatch):
    lui, fake = _ui_with_recording_st()
    _story(monkeypatch, lui,
           title="T",
           hashtags=_TAGS,
           image_urls=["https://img.example/a.jpg"],
           uploaded_images=[],
           news_links=[])
    lui._render_story_detail("teststory1")

    # Title row
    assert any("lib-doc-title" in m for m in fake.markup)
    assert ("", "lib_title_edit_teststory1") in fake.buttons
    # Hashtag panel rows
    for tag in _TAGS:
        assert any(tag in m and "lib-panel-row" in m for m in fake.markup)
    assert "Showing 2 of 2" in fake.captions
    # Upload popover (by its help text — the detail also renders reset/share/copy)
    assert any(p.get("help") == "Upload video or image" for p in fake.popovers), (
        f"upload popover must render; saw {fake.popovers}")
