"""v1.6.2 (#84) — story header shows the full title text, not the icon popover.

Bug (#84): #60 replaced the story-detail title with a single static 🎬 glyph
plus a title popover. The user called that the wrong design — the header
must show the full title text again.

Fix: restore the h2 (lib-doc-title) title — multiline, left-aligned (#120) —
with the inline title-edit flow. "Edited … ago" stays removed. The #79
`.lib-doc-title a { display:none }` guard stays: with the h2 back,
Streamlit would otherwise show its heading-anchor 🔗 link icon on the
title (the user's screenshot that prompted the guard).

Run: python -m pytest tests/test_story_title_v162.py -q
"""
import html
import inspect
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_one_row_toolbar_v16 import (  # noqa: E402
    _story,
    _ui_with_recording_st,
)


def _render_detail(monkeypatch, title, editing=False):
    lui, fake = _ui_with_recording_st()
    _story(monkeypatch, lui, title=title)
    if editing:
        fake.session_state["lib_edit_title_sid1"] = True
    lui._render_story_detail("sid1")
    return lui, fake


def _css(lui, fake):
    lui.inject_library_css()
    return "\n".join(fake.markup)


def _rule_bodies(css, selector):
    """Return the bodies of every CSS rule whose selector contains `selector`."""
    clean = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return [m.group(2) for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", clean)
            if selector in m.group(1)]


# ---------------------------------------------------------------------------
# #84 — full title text is back as an h2
# ---------------------------------------------------------------------------

def test_title_renders_full_h2_with_html_escaped_title(monkeypatch):
    title = 'Metro "relief" <b>&</b> more'
    _, fake = _render_detail(monkeypatch, title)
    expected = f"<h2 class='lib-doc-title'>{html.escape(title)}</h2>"
    assert any(expected == m for m in fake.markup), (
        "full title h2 not rendered; markup was: "
        + repr([m for m in fake.markup if "lib-doc-title" in m]))


def test_no_icon_glyph_popover_or_marker_left(monkeypatch):
    _, fake = _render_detail(monkeypatch, "T")
    assert not any("lib-story-icon" in m for m in fake.markup)
    assert not any("lib_icon_" in str(p) for p in fake.popovers)
    assert not any(p.get("label") == "🎬" for p in fake.popovers)


def test_edit_flow_survives_revert(monkeypatch):
    # View mode: the edit button (icon-only, no emoji) is next to the title.
    lui, fake = _render_detail(monkeypatch, "T")
    assert ("", "lib_title_edit_sid1") in fake.buttons
    assert any(kw.get("key") == "lib_title_edit_sid1"
               and kw.get("icon") == lui._TB_ICON_EDIT
               for kw in fake.button_kwargs), "title edit must use the material edit icon"
    # Edit mode: a text editor takes the title's place (Save/Cancel live
    # in the toolbar above). #154: the title row is now the reusable
    # _render_title_row component.
    src = inspect.getsource(lui._render_title_row)
    assert 'st.text_area("", value=title' in src


def test_no_edited_ago_caption(monkeypatch):
    # "Edited … ago" stays removed: no recency caption is emitted in the
    # rendered header. (Source inspection can't be used here — the code
    # comments name the removed caption.)
    _, fake = _render_detail(monkeypatch, "T")
    assert not any("Edited" in m for m in fake.markup)


def test_render_source_has_no_icon_popover(monkeypatch):
    lui, _ = _render_detail(monkeypatch, "T")
    src = inspect.getsource(lui._render_story_detail)
    assert "_STORY_ICON_GLYPH" not in src
    assert "lib_icon_" not in src
    assert "lib-story-icon" not in src
    # #154: the h2 title now lives in the reusable _render_title_row component.
    assert "<h2 class='lib-doc-title'>" in inspect.getsource(lui._render_title_row)


# ---------------------------------------------------------------------------
# #120 — the h2 title styling is LEFT-aligned, multiline, theme-safe
# ---------------------------------------------------------------------------

def test_doc_title_css_left_aligned_multiline_and_theme_safe():
    lui, fake = _ui_with_recording_st()
    css = _css(lui, fake)
    bodies = _rule_bodies(css, ".lib-doc-title")
    # The guard rule `.lib-doc-title a` also matches; the title rule is
    # the one carrying the typography.
    typo = [b for b in bodies if "text-align" in b]
    assert typo, "no .lib-doc-title typography rule in library CSS"
    body = typo[0]
    assert "text-align: left" in body
    assert "text-align: center" not in body
    assert "font-size: 30px" in body
    assert "overflow-wrap: anywhere" in body  # multiline, never clipped
    assert "fill:" not in body and "stroke:" not in body  # never forced paint


# ---------------------------------------------------------------------------
# #79 guard — heading-anchor 🔗 icon stays hidden (now load-bearing, not
# belt-and-braces: the h2 title is back)
# ---------------------------------------------------------------------------

def test_story_title_heading_anchor_guard_pinned():
    lui, fake = _ui_with_recording_st()
    css = _css(lui, fake)
    bodies = _rule_bodies(css, ".lib-doc-title a")
    assert bodies, "no .lib-doc-title anchor guard in library CSS"
    assert any("display: none !important;" in b for b in bodies), \
        "story-title heading anchor is not hidden"


# ---------------------------------------------------------------------------
# #120 — title left-aligned; edit icon hugs the title (quiet, borderless)
# ---------------------------------------------------------------------------

def test_title_edit_marker_emitted_before_button(monkeypatch):
    _, fake = _render_detail(monkeypatch, "Some title")
    idx = next((i for i, m in enumerate(fake.markup)
                if 'data-marker="lib-title-edit"' in m), None)
    assert idx is not None, "lib-title-edit marker not emitted"
    # The h2 title is rendered in the same row (title column precedes it).
    h2 = next((i for i, m in enumerate(fake.markup)
               if "<h2 class='lib-doc-title'>" in m), None)
    assert h2 is not None and h2 < idx, \
        "title h2 should render before its edit marker in the same row"


def test_title_edit_button_uses_material_icon_and_tooltip(monkeypatch):
    _, fake = _render_detail(monkeypatch, "Some title")
    kw = next((k for k in fake.button_kwargs
               if k.get("key") == "lib_title_edit_sid1"), None)
    assert kw is not None, "title edit button not rendered"
    assert kw.get("icon") == ":material/edit:", \
        "title edit must use the native material edit icon"
    assert kw.get("label") == "", "title edit must stay icon-only"
    assert kw.get("help") == "Edit title", "tooltip/accessibility label kept"


def test_title_edit_button_borderless_quiet_css():
    lui, fake = _ui_with_recording_st()
    css = _css(lui, fake)
    assert '[data-marker="lib-title-edit"]' in css, \
        "no lib-title-edit marker rule in library CSS"
    bodies = _rule_bodies(css, '[data-marker="lib-title-edit"]')
    assert bodies, "no lib-title-edit CSS rule bodies found"
    joined = " ".join(bodies)
    assert "border: none !important;" in joined, \
        "title edit button must be borderless (no boxed widget)"
    assert "background: transparent !important;" in joined
    assert "color: inherit !important;" in joined, \
        "title edit icon must follow the theme, not a hard-coded color"
    assert "fill:" not in joined and "stroke:" not in joined, \
        "never force SVG paint"


def test_title_row_uses_narrow_trailing_edit_column(monkeypatch):
    _, fake = _render_detail(monkeypatch, "Some title")
    # The title row is [11, 1]: title fills the row left-aligned, the edit
    # icon-button hugs it in the narrow trailing column.
    assert [11, 1] in fake.column_specs, \
        f"title row should use [11, 1] columns; specs were {fake.column_specs}"
