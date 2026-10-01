"""v1.6.2 (#90) — story-detail toolbar uses ONE icon font, no text/emoji.

All seven toolbar controls (Update Hashtags / Images / News, Reset, Share,
Copy, Delete) are icon-only: single PUA glyphs from the bundled
"LibToolbarIcons" font (a 7-glyph Material Symbols Outlined subset,
Apache 2.0, self-hosted as a base64 data URI — no CDN). Tooltips keep the
text labels for discoverability and accessibility (#71 pattern); the #53
contract (spinner owns loading, stable width, disabled while running) is
untouched.

Run: python -m pytest tests/test_icon_font_toolbar_v162.py -q
"""
import base64
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_library_v15 import _ui_with_fake_st  # noqa: E402
from test_one_row_toolbar_v16 import (  # noqa: E402
    _story,
    _ui_with_recording_st,
)

_FONT_FILE = (Path(__file__).resolve().parent.parent
              / "library_ui.py").parent / "assets" / "fonts" / "toolbar-icons.woff2"

_TOOLTIP_TEXT = {
    "tags": "Update Hashtags",
    "images": "Update Images",
    "news": "Update News",
    "reset": "Clear and re-fetch hashtags, images and news links",
    "share": "Share this story's news links and hashtags",
    "copy": "Copy the screenplay in different formats",
    "delete": "Delete this story",
}


def _render_toolbar(monkeypatch):
    """Render the full story-detail toolbar; return (lui, fake)."""
    lui, fake = _ui_with_recording_st()
    _story(monkeypatch, lui)
    lui._render_story_detail("sid1")
    return lui, fake


def _is_pua_icon(s):
    return isinstance(s, str) and len(s) == 1 and 0xE000 <= ord(s) <= 0xF8FF


# ---------------------------------------------------------------------------
# All seven controls are icon-only — no text, no emoji
# ---------------------------------------------------------------------------

def test_all_seven_toolbar_controls_are_icon_only(monkeypatch):
    lui, fake = _ui_with_recording_st()
    _story(monkeypatch, lui)
    lui._render_story_detail("sid1")
    # The three refresh buttons render first, in toolbar order.
    assert [b[0] for b in fake.buttons[:3]] == [
        lui._TB_ICON_TAG, lui._TB_ICON_IMAGE, lui._TB_ICON_NEWS]
    # Popovers: Reset, Share, Copy, Delete (#84 reverted the title popover —
    # every popover here is a toolbar action).
    pop_labels = [p["label"] for p in fake.popovers]
    assert pop_labels == [
        lui._TB_ICON_RESET, lui._TB_ICON_SHARE,
        lui._TB_ICON_COPY, lui._TB_ICON_DELETE]
    for label in [b[0] for b in fake.buttons[:3]] + pop_labels:
        assert _is_pua_icon(label), f"not a single PUA icon glyph: {label!r}"


def test_no_text_or_emoji_labels_remain_in_toolbar(monkeypatch):
    lui, fake = _ui_with_recording_st()
    _story(monkeypatch, lui)
    lui._render_story_detail("sid1")
    labels = ([b[0] for b in fake.buttons[:3]]
              + [p["label"] for p in fake.popovers])
    for banned in ("Reset", "Share", "Copy", "Delete", "#",
                   "\U0001F5BC", "\U0001F4F0"):
        assert banned not in labels, f"old label still present: {banned!r}"


# ---------------------------------------------------------------------------
# Tooltips keep the text labels (discoverability + accessibility)
# ---------------------------------------------------------------------------

def test_toolbar_tooltips_keep_text_labels(monkeypatch):
    lui, fake = _ui_with_recording_st()
    _story(monkeypatch, lui)
    lui._render_story_detail("sid1")
    helps = [k.get("help") for k in fake.button_kwargs[:3]]
    assert helps == [_TOOLTIP_TEXT["tags"], _TOOLTIP_TEXT["images"],
                     _TOOLTIP_TEXT["news"]]
    pop_helps = {p["label"]: p.get("help") for p in fake.popovers}
    assert pop_helps[lui._TB_ICON_RESET] == _TOOLTIP_TEXT["reset"]
    assert pop_helps[lui._TB_ICON_SHARE] == _TOOLTIP_TEXT["share"]
    assert pop_helps[lui._TB_ICON_COPY] == _TOOLTIP_TEXT["copy"]
    assert pop_helps[lui._TB_ICON_DELETE] == _TOOLTIP_TEXT["delete"]


# ---------------------------------------------------------------------------
# data-tbicon markers: the CSS hook for the icon font
# ---------------------------------------------------------------------------

def test_kind_buttons_emit_tbicon_marker(monkeypatch):
    """The tbicon marker immediately precedes each refresh button's element
    (rides the spin-marker div while running, so the spinner `+` rule keeps
    its required DOM order)."""
    lui, fake = _ui_with_fake_st()
    lui._render_kind_button(story_id="sid1", kind="hashtags",
                            label=lui._TB_ICON_TAG, button_key="lib_tags_sid1",
                            kick_label="hashtag", help_text="Update Hashtags",
                            busy_kinds={"hashtags"}, ai_engine=None)
    running_markup = "".join(fake.markup)
    assert 'data-marker="lib-spin-hashtags" data-tbicon' in running_markup
    lui2, fake2 = _ui_with_fake_st()
    lui2._render_kind_button(story_id="sid1", kind="images",
                             label=lui2._TB_ICON_IMAGE,
                             button_key="lib_imgs_sid1", kick_label="image",
                             help_text="Update Images",
                             busy_kinds=set(), ai_engine=None)
    idle_markup = "".join(fake2.markup)
    assert "<div data-tbicon" in idle_markup
    assert "lib-spin-images" not in idle_markup


def test_share_copy_popovers_emit_tbicon_marker(monkeypatch):
    lui, fake = _ui_with_fake_st()
    monkeypatch.setattr(lui, "_copy_button",
                        lambda label, text, key: None)
    lui._render_share_popover("sid1", "https://example.com/a\n\n#X")
    lui._render_copy_popover("sid1", {"hashtags": []}, "script")
    assert "".join(fake.markup).count("<div data-tbicon") == 2


def test_reset_delete_popovers_carry_tbicon_on_danger_marker():
    """#90: the tbicon attribute rides the last marker before the popover
    trigger — the danger-pop marker when idle (its data-marker is
    untouched, so the #24 collapse and #53/#81 spin `+` chains keep
    matching)."""
    lui, fake = _ui_with_fake_st()
    lui._render_reset_popover("sid1", set(), ai_engine=None)
    markup = "".join(fake.markup)
    assert 'data-marker="lib-danger-pop-lib_resetpop_sid1" data-tbicon' in markup


def test_reset_popover_tbicon_moves_to_spin_marker_while_running():
    """#81 + #90: while resetting, the spin marker is emitted between the
    danger-pop marker and the popover trigger — data-tbicon rides the
    spin marker there, so the icon-font CSS keeps the same
    adjacent-sibling anchor as the spinner CSS (the glyph must render
    while the spinner shows)."""
    lui, fake = _ui_with_fake_st()
    lui._render_reset_popover("sid1", {"reset"}, ai_engine=None)
    markup = "".join(fake.markup)
    assert 'data-marker="lib-spin-reset" data-tbicon' in markup
    # …and the danger-pop marker no longer carries it (exactly one anchor).
    assert markup.count("data-tbicon") == 1
    assert 'data-marker="lib-danger-pop-lib_resetpop_sid1" style' in markup


def test_delete_all_trigger_stays_text():
    """Out of scope for #90: the master-section "Delete All" trigger keeps
    its text label — only the toolbar Delete becomes icon-only."""
    lui, fake = _ui_with_fake_st()
    lui._delete_popover(trigger_label="Delete All", popover_key="dp-all",
                        title="T", message="M", on_yes=lambda: None,
                        destructive_label="Delete all stories")
    assert fake.popover_kwargs["label"] == "Delete All"
    assert "data-tbicon" not in "".join(fake.markup)
    # And the real call site never opts in.
    src = (Path(__file__).resolve().parent.parent / "library_ui.py").read_text()
    seg = src[src.index('popover_key="lib_delpop_all"'):]
    seg = seg[:seg.index(")", seg.index("destructive_label"))]
    assert "icon_trigger" not in seg


# ---------------------------------------------------------------------------
# The font itself: bundled asset, @font-face, fail loudly
# ---------------------------------------------------------------------------

def test_font_face_injected_from_bundled_asset():
    lui, fake = _ui_with_fake_st()
    lui.inject_library_css()
    css = "".join(fake.markup)
    assert "@font-face" in css
    assert 'font-family: "LibToolbarIcons"' in css
    m = re.search(r"url\(data:font/woff2;base64,([A-Za-z0-9+/=]+)\)", css)
    assert m, "@font-face has no base64 data URI (no CDN allowed)"
    assert base64.b64decode(m.group(1)) == _FONT_FILE.read_bytes()


def test_icon_font_css_is_scoped_not_global():
    """The icon font must reach exactly the tbicon-marked controls — never
    a global button rule, and never a forced SVG fill/stroke."""
    lui, fake = _ui_with_fake_st()
    lui.inject_library_css()
    css = "".join(fake.markup)
    assert "LibToolbarIcons" in css
    # Strip the @font-face block: it declares the font, it doesn't apply it.
    css_no_face = re.sub(r"@font-face\s*\{[^}]*\}", "", css)
    for m in re.finditer(r"LibToolbarIcons", css_no_face):
        # Every remaining mention must sit inside a data-tbicon-scoped rule.
        brace = css_no_face.rfind("{", 0, m.start())
        sel_start = css_no_face.rfind("}", 0, brace) + 1
        selector = css_no_face[sel_start:brace]
        assert "data-tbicon" in selector, \
            f"unscoped icon-font rule: {selector.strip()}"
    # No declaration may force SVG presentation attributes (comments
    # stripped first — the tbicon comment names the anti-pattern).
    css_no_comments = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    assert not re.search(r"^\s*(fill|stroke)\s*:", css_no_comments, flags=re.M)


def test_missing_font_asset_fails_loudly(monkeypatch):
    lui, fake = _ui_with_fake_st()
    monkeypatch.setattr(lui, "_TOOLBAR_FONT_FILE",
                        Path("/nonexistent/toolbar-icons.woff2"))
    monkeypatch.setattr(lui, "_tb_font_b64", None)
    with pytest.raises(RuntimeError, match="toolbar icon font"):
        lui._toolbar_icon_font_b64()
    monkeypatch.setattr(lui, "_tb_font_b64", None)
    with pytest.raises(RuntimeError, match="toolbar icon font"):
        lui.inject_library_css()


def test_empty_font_asset_fails_loudly(monkeypatch, tmp_path):
    lui, fake = _ui_with_fake_st()
    empty = tmp_path / "empty.woff2"
    empty.write_bytes(b"")
    monkeypatch.setattr(lui, "_TOOLBAR_FONT_FILE", empty)
    monkeypatch.setattr(lui, "_tb_font_b64", None)
    with pytest.raises(RuntimeError, match="empty"):
        lui._toolbar_icon_font_b64()
