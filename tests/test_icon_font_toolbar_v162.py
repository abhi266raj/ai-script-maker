"""v1.6.2 (#111) — story-detail toolbar uses Streamlit NATIVE icons.

#111 killed the #90 self-hosted icon font: the bundled woff2 + data-URI
@font-face never loaded in the browser (tofu boxes), so all seven toolbar
controls (Update Hashtags / Images / News, Reset, Share, Copy, Delete)
now use Streamlit's native Material Symbols support
(``icon=":material/<name>:"``) with an empty text label — icon-only, no
text, no emoji. The spinner is also native: ``icon="spinner"`` renders
Streamlit's animated spinner while a refresh runs (#53 HIG: the button
that starts work owns its loading state). Tooltips keep the text labels
for discoverability and accessibility (#71 pattern).

Run: python -m pytest tests/test_icon_font_toolbar_v162.py -q
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_library_v15 import _ui_with_fake_st  # noqa: E402
from test_one_row_toolbar_v16 import (  # noqa: E402
    _story,
    _ui_with_recording_st,
)

_MATERIAL_ICONS = {
    "tags": ":material/tag:",
    "images": ":material/image:",
    "news": ":material/newspaper:",
    "reset": ":material/refresh:",
    "share": ":material/share:",
    "copy": ":material/content_copy:",
    "delete": ":material/delete:",
}

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


def _is_material_icon(s):
    return (isinstance(s, str) and s.startswith(":material/")
            and s.endswith(":") and len(s) > len(":material/:"))


# ---------------------------------------------------------------------------
# All seven controls are icon-only — native material icons, no text/emoji
# ---------------------------------------------------------------------------

def test_all_seven_toolbar_controls_are_icon_only(monkeypatch):
    lui, fake = _ui_with_recording_st()
    _story(monkeypatch, lui)
    lui._render_story_detail("sid1")
    # The three refresh buttons render first, in toolbar order: empty
    # text label, native material icon via icon=.
    assert [b[0] for b in fake.buttons[:3]] == ["", "", ""]
    assert [k.get("icon") for k in fake.button_kwargs[:3]] == [
        lui._TB_ICON_TAG, lui._TB_ICON_IMAGE, lui._TB_ICON_NEWS]
    # Popovers: Reset, Share, Copy (#84 reverted the title popover —
    # every popover here is a toolbar action). #114: the upload popover
    # is icon-only now — it lives in the upload row, so it is excluded
    # from the icon-only assertion by its upload icon. #119: Delete is a
    # direct button, not a popover — no dropdown chevron (Apple HIG).
    toolbar_pops = [p for p in fake.popovers
                    if p.get("icon") != lui._TB_ICON_UPLOAD]
    assert [p["label"] for p in toolbar_pops] == ["", "", ""]
    assert [p.get("icon") for p in toolbar_pops] == [
        lui._TB_ICON_RESET, lui._TB_ICON_SHARE, lui._TB_ICON_COPY]
    _del_trig = [k for k in fake.button_kwargs
                 if k.get("key") == "lib_delpop_sid1-trigger"]
    assert len(_del_trig) == 1
    assert _del_trig[0]["label"] == ""
    assert _del_trig[0]["icon"] == lui._TB_ICON_DELETE
    for icon in ([k.get("icon") for k in fake.button_kwargs[:3]]
                 + [p.get("icon") for p in toolbar_pops]
                 + [_del_trig[0]["icon"]]):
        assert _is_material_icon(icon), f"not a material icon: {icon!r}"


def test_material_icon_constants_match_expected_names():
    lui, _ = _ui_with_fake_st()
    assert lui._TB_ICON_TAG == _MATERIAL_ICONS["tags"]
    assert lui._TB_ICON_IMAGE == _MATERIAL_ICONS["images"]
    assert lui._TB_ICON_NEWS == _MATERIAL_ICONS["news"]
    assert lui._TB_ICON_RESET == _MATERIAL_ICONS["reset"]
    assert lui._TB_ICON_SHARE == _MATERIAL_ICONS["share"]
    assert lui._TB_ICON_COPY == _MATERIAL_ICONS["copy"]
    assert lui._TB_ICON_DELETE == _MATERIAL_ICONS["delete"]
    assert lui._TB_ICON_SPINNER == "spinner"


def test_no_text_or_emoji_labels_remain_in_toolbar(monkeypatch):
    lui, fake = _ui_with_recording_st()
    _story(monkeypatch, lui)
    lui._render_story_detail("sid1")
    labels = ([b[0] for b in fake.buttons[:3]]
              + [p["label"] for p in fake.popovers])
    for banned in ("Reset", "Share", "Copy", "Delete", "#",
                   "\U0001F5BC", "\U0001F4F0"):
        assert banned not in labels, f"old label still present: {banned!r}"
    # No PUA tofu glyphs either (#111).
    for label in labels:
        assert not (isinstance(label, str) and len(label) == 1
                    and 0xE000 <= ord(label) <= 0xF8FF), \
            f"PUA tofu glyph still present: {label!r}"


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
    pop_helps = {(p["label"], p.get("icon")): p.get("help")
                 for p in fake.popovers}
    assert pop_helps[("", lui._TB_ICON_RESET)] == _TOOLTIP_TEXT["reset"]
    assert pop_helps[("", lui._TB_ICON_SHARE)] == _TOOLTIP_TEXT["share"]
    assert pop_helps[("", lui._TB_ICON_COPY)] == _TOOLTIP_TEXT["copy"]
    # #119: Delete is a direct button now — its tooltip rides on the
    # button, not a popover.
    _del_trig = [k for k in fake.button_kwargs
                 if k.get("key") == "lib_delpop_sid1-trigger"]
    assert len(_del_trig) == 1
    assert _del_trig[0]["help"] == _TOOLTIP_TEXT["delete"]


# ---------------------------------------------------------------------------
# Native spinner while running (#53 HIG, #111)
# ---------------------------------------------------------------------------

def test_kind_button_shows_native_spinner_while_running():
    lui, fake = _ui_with_fake_st()
    lui._render_kind_button(story_id="sid1", kind="hashtags",
                            label=lui._TB_ICON_TAG, button_key="lib_tags_sid1",
                            kick_label="hashtag", help_text="Update Hashtags",
                            busy_kinds={"hashtags"}, ai_engine=None)
    assert fake.button_kwargs[0]["icon"] == "spinner"
    assert fake.button_kwargs[0]["label"] == ""  # text label never changes
    assert fake.button_kwargs[0]["disabled"] is True
    # Idle: material icon, enabled.
    lui2, fake2 = _ui_with_fake_st()
    lui2._render_kind_button(story_id="sid1", kind="images",
                             label=lui2._TB_ICON_IMAGE,
                             button_key="lib_imgs_sid1", kick_label="image",
                             help_text="Update Images",
                             busy_kinds=set(), ai_engine=None)
    assert fake2.button_kwargs[0]["icon"] == lui2._TB_ICON_IMAGE
    assert fake2.button_kwargs[0]["disabled"] is False


def test_reset_popover_shows_native_spinner_while_resetting():
    lui, fake = _ui_with_fake_st()
    lui._render_reset_popover("sid1", {"reset"}, ai_engine=None)
    assert fake.popover_kwargs["icon"] == "spinner"
    assert fake.popover_kwargs["label"] == ""
    assert fake.popover_kwargs["disabled"] is True
    # Idle: refresh icon, enabled.
    lui2, fake2 = _ui_with_fake_st()
    lui2._render_reset_popover("sid1", set(), ai_engine=None)
    assert fake2.popover_kwargs["icon"] == lui2._TB_ICON_RESET
    assert fake2.popover_kwargs["disabled"] is False


def test_load_more_button_shows_native_spinner_while_running(monkeypatch):
    lui, fake = _ui_with_fake_st()
    monkeypatch.setattr(lui.lib, "_SIBLING_KINDS",
                        {"more_images": "images"}, raising=False)
    lui._render_load_more_button(story_id="sid1", kind="more_images",
                                 button_key="lib_more_imgs_sid1",
                                 help_text="Load more images",
                                 busy_kinds={"more_images"})
    assert fake.button_kwargs[0]["icon"] == "spinner"
    assert fake.button_kwargs[0]["label"] == ""  # #202: icon-only
    assert fake.button_kwargs[0]["disabled"] is True
    # Idle: add icon, enabled, still icon-only.
    lui2, fake2 = _ui_with_fake_st()
    lui2._render_load_more_button(story_id="sid1", kind="more_images",
                                  button_key="lib_more_imgs_sid1",
                                  help_text="Load more images",
                                  busy_kinds=set())
    assert fake2.button_kwargs[0]["icon"] == ":material/add:"
    assert fake2.button_kwargs[0]["label"] == ""
    assert fake2.button_kwargs[0]["disabled"] is False


# ---------------------------------------------------------------------------
# #111: no markers, no custom font, no @font-face anywhere
# ---------------------------------------------------------------------------

def test_no_tbicon_or_spin_markers_emitted(monkeypatch):
    lui, fake = _ui_with_recording_st()
    _story(monkeypatch, lui)
    lui._render_story_detail("sid1")
    markup = "".join(getattr(fake, "markup", []))
    assert "data-tbicon" not in markup
    assert "lib-spin-" not in markup


def test_no_font_face_or_custom_font_in_css():
    lui, fake = _ui_with_fake_st()
    lui.inject_library_css()
    css = "".join(fake.markup)
    assert "@font-face" not in css
    assert "LibToolbarIcons" not in css
    assert "data:font/woff2" not in css


def test_no_custom_font_asset_on_disk():
    font_file = (Path(__file__).resolve().parent.parent
                 / "assets" / "fonts" / "toolbar-icons.woff2")
    assert not font_file.exists(), \
        f"dead font asset still present: {font_file}"


def test_no_global_fill_stroke_forcing():
    """Never force SVG fill/stroke globally (standing rule)."""
    lui, fake = _ui_with_fake_st()
    lui.inject_library_css()
    css = "".join(fake.markup)
    css_no_comments = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    assert not re.search(r"^\s*(fill|stroke)\s*:", css_no_comments, flags=re.M)


def test_delete_all_trigger_stays_text():
    """Out of scope: the master-section "Delete All" trigger keeps its
    text label — only the toolbar Delete becomes icon-only. #119: it is
    now a direct button (no popover, no chevron), still text-labeled.
    #130: the trigger records pending state; the shared dialog opens via
    _maybe_open_delete_dialog()."""
    lui, fake = _ui_with_fake_st(clicks=("dp-all-trigger",))
    lui._delete_popover(trigger_label="Delete All", popover_key="dp-all",
                        title="T", message="M", on_yes=lambda: None,
                        destructive_label="Delete all stories",
                        _pending_delete_kind="all")
    assert fake.popovers == []
    _trig = fake.button_kwargs[0]
    assert _trig["label"] == "Delete All"
    assert _trig.get("icon") is None
    # #130: trigger sets pending (no dialog yet); the shared dialog opens
    # once via _maybe_open_delete_dialog().
    assert fake.dialogs == []
    assert fake.session_state[lui._PENDING_DELETE_KEY]["kind"] == "all"
    lui._maybe_open_delete_dialog()
    assert fake.dialogs == ["Delete"]
    # And the real call site never opts into an icon.
    src = (Path(__file__).resolve().parent.parent / "library_ui.py").read_text()
    seg = src[src.index('popover_key="lib_delpop_all"'):]
    seg = seg[:seg.index(")", seg.index("destructive_label"))]
    assert "trigger_icon" not in seg
