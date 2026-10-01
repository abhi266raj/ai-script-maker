"""v1.6.2 (#84) — story header shows the full title text, not the icon popover.

Bug (#84): #60 replaced the story-detail title with a single static 🎬 glyph
plus a title popover. The user called that the wrong design — the header
must show the full title text again.

Fix: restore the h2 (lib-doc-title) title — multiline, centered — with the
✏️ inline title-edit flow. "Edited … ago" stays removed. The #79
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
    # View mode: the ✏️ edit button is next to the title.
    lui, fake = _render_detail(monkeypatch, "T")
    assert ("✏️", "lib_title_edit_sid1") in fake.buttons
    # Edit mode: a text editor takes the title's place (Save/Cancel live
    # in the toolbar above).
    src = inspect.getsource(lui._render_story_detail)
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
    assert "<h2 class='lib-doc-title'>" in src


# ---------------------------------------------------------------------------
# #84 — the h2 title styling is centered, multiline, theme-safe
# ---------------------------------------------------------------------------

def test_doc_title_css_centered_multiline_and_theme_safe():
    lui, fake = _ui_with_recording_st()
    css = _css(lui, fake)
    bodies = _rule_bodies(css, ".lib-doc-title")
    # The guard rule `.lib-doc-title a` also matches; the title rule is
    # the one carrying the typography.
    typo = [b for b in bodies if "text-align" in b]
    assert typo, "no .lib-doc-title typography rule in library CSS"
    body = typo[0]
    assert "text-align: center" in body
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
