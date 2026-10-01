"""v1.6.2 (#154) — all section rows render through dedicated reusable components.

``_render_title_row``, ``_render_hashtags_row``, ``_render_images_row`` and
``_render_upload_row`` (plus the earlier ``_render_news_links_row`` #156)
each own their full row: title + chips/controls including alignment
(column layout, markers, per-cell content). The inline blocks in
``_render_story_detail`` are now single calls — pure refactors with no
behavior change.

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
# _render_hashtags_row: title + chips with × in one row
# ---------------------------------------------------------------------------

_TAGS = ["#Alpha", "#Beta"]


def test_hashtags_row_renders_single_row(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_hashtags_row("teststory1", _TAGS)

    assert len(fake.column_specs) == 1, (
        f"hashtags must render exactly one columns() row; "
        f"saw {len(fake.column_specs)}")
    spec = fake.column_specs[0]
    expected = ([lui._section_title_weight("Hashtags")]
                + lui._chip_col_weights(_TAGS))
    assert spec == expected, (
        f"row spec must be [title, *chips]; saw {spec}, expected {expected}")


def test_hashtags_row_renders_chips_and_remove_overlays(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_hashtags_row("teststory1", _TAGS)

    assert any("Hashtags" in m for m in fake.markup), (
        f"'Hashtags' title must render; saw {fake.markup}")
    for tag in _TAGS:
        assert any(tag in m and "lib-chip" in m for m in fake.markup), (
            f"chip for {tag} must render; saw {fake.markup}")
    x_buttons = [b for b in fake.buttons if b[0] == "×"]
    assert [b[1] for b in x_buttons] == [
        "lib_xtag_teststory1_0", "lib_xtag_teststory1_1"], (
        f"each chip needs its × remove button; saw {fake.buttons}")


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
    expected = [1, 1, lui._load_more_weight("Load more images")]
    assert spec == expected, (
        f"row spec must be [1, 1, load-more]; saw {spec}, expected {expected}")


def test_images_row_has_load_more_and_remove_overlays(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_images_row("teststory1", ["https://img.example/a.jpg"], ["up1.png"],
                           set())

    assert ("Load more images", "lib_moreimg_teststory1") in fake.buttons, (
        f"'Load more images' button must render; saw {fake.buttons}")
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
# _render_upload_row: title + upload popover in one [11, 1] row
# ---------------------------------------------------------------------------

def test_upload_row_renders_single_row(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_upload_row("teststory1")

    assert len(fake.column_specs) == 1, (
        f"upload must render exactly one columns() row; "
        f"saw {len(fake.column_specs)}")
    assert fake.column_specs[0] == [11, 1], (
        f"upload row spec must be [11, 1]; saw {fake.column_specs[0]}")


def test_upload_row_renders_title_and_popover(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_upload_row("teststory1")

    assert any("Upload" in m and "lib-section-inline" in m
               for m in fake.markup), (
        f"'Upload' inline title must render; saw {fake.markup}")
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
    # Hashtag chips
    for tag in _TAGS:
        assert any(tag in m and "lib-chip" in m for m in fake.markup)
    # Upload popover (by its help text — the detail also renders reset/share/copy)
    assert any(p.get("help") == "Upload video or image" for p in fake.popovers), (
        f"upload popover must render; saw {fake.popovers}")
