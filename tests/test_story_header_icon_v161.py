"""v1.6.1 (#60) — story header shows one static glyph; the full title lives in a popover.

Bug: the story-detail header rendered the full title text inline (with an
"Edited … ago" caption underneath in the original report).

Fix: the header shows a single static glyph (🎬) for every story — never
the title text, never per-tone. The full title lives in a native popover
on the icon (click to reveal; a help tooltip names the affordance). The
✏️ title-edit flow and the delete popover's meta.get("title") naming (#58)
are untouched.

Run: python -m pytest tests/test_story_header_icon_v161.py -q
"""
import inspect
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _load_lui():
    """Import library_ui with a capturing streamlit stub.

    Returns (module, css_chunks). Restores sys.modules afterwards.
    """
    saved = dict(sys.modules)
    chunks = []
    try:
        fake_mod = types.ModuleType("streamlit")
        fake_mod.markdown = lambda *a, **k: chunks.append(a[0] if a else "")
        # Any other streamlit attribute access returns a no-op callable.
        fake_mod.__getattr__ = lambda name: (lambda *a, **k: None)
        sys.modules["streamlit"] = fake_mod
        sys.modules.pop("library_ui", None)
        import library_ui as lui
        lui.inject_library_css()
        return lui, "\n".join(chunks)
    finally:
        sys.modules.clear()
        sys.modules.update(saved)


def test_glyph_is_single_static_character():
    lui, _ = _load_lui()
    assert lui._STORY_ICON_GLYPH == "🎬"
    assert len(lui._STORY_ICON_GLYPH) == 1  # one glyph, never per-story


def test_no_inline_title_css_left():
    _, css = _load_lui()
    assert "lib-doc-title" not in css


def test_icon_css_centers_enlarges_and_stays_theme_safe():
    _, css = _load_lui()
    assert "lib-story-icon" in css
    assert "justify-content: center" in css  # glyph centered in the header
    assert "font-size: 44px" in css  # reads as an icon, not button text
    assert "color: inherit" in css  # theme-safe: follows light/dark
    assert "fill:" not in css  # text glyph, never forced SVG paint


def test_detail_renders_popover_not_title_text():
    lui, _ = _load_lui()
    src = inspect.getsource(lui._render_story_detail)
    assert "lib-doc-title" not in src
    assert "<h2" not in src  # no inline title text anywhere
    assert "Edited" not in src  # no "Edited … ago" caption emitted
    assert "st.popover(_STORY_ICON_GLYPH" in src
    assert 'key=f"lib_icon_{story_id}"' in src
    # The user-editable title is Markdown-escaped inside the popover.
    assert "_md_escape(title)" in src
    # The ✏️ title-edit flow survives: edit button + textarea editor.
    assert "lib_title_edit_" in src
    assert 'st.text_area("", value=title' in src
