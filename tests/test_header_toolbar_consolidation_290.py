"""Header/toolbar consolidation + #290 collapsible stories master view.

- Upload moves into the story-detail toolbar beside Share/Copy; the
  standalone Upload row is gone.
- The AI engine dropdown moves into the same toolbar; the "Enable AI
  processing" toggle is gone. Selecting "None" disables AI processing —
  invoking AI then fails loudly.
- #290: the stories master view collapses into the "Stories · N" header
  (borderless toggle); Delete-all lives in that header with the
  Apple-style destructive confirmation.

Run: python -m pytest tests/test_header_toolbar_consolidation_290.py -q
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_library_v15 import _ui_with_fake_st  # noqa: E402
from test_one_row_toolbar_v16 import (  # noqa: E402
    _ui_with_recording_st,
    _story,
)

LIB_PATH = Path(__file__).resolve().parent.parent / "library_ui.py"


def _source():
    return LIB_PATH.read_text(encoding="utf-8")


def _page_stubs(monkeypatch, lui):
    """Stub the library page's data layer for render_library_page."""
    _story(monkeypatch, lui)
    stories = [
        {"id": "a", "title": "Alpha story"},
        {"id": "b", "title": "Beta story"},
        {"id": "c", "title": "Gamma story"},
    ]
    monkeypatch.setattr(lui.lib, "list_stories", lambda: stories)
    monkeypatch.setattr(lui.lib, "recover_orphaned_refreshes",
                        lambda: None)


def _story_radios(fake):
    """The story picker radio calls (not the upload media-type radio)."""
    return [r for r in fake.radios if r["key"] == "lib_story_radio"]


# ---------------------------------------------------------------------------
# Structural source checks
# ---------------------------------------------------------------------------

def test_no_standalone_upload_row():
    src = _source()
    assert "_render_upload_row" not in src, \
        "standalone Upload row still present"
    assert "def _render_upload_popover_trigger" in src
    # The trigger is placed in the detail toolbar (both modes).
    assert src.count("_render_upload_popover_trigger(story_id)") >= 2


def test_ai_toggle_gone():
    src = _source()
    # No toggle WIDGET with that label may remain (migration comments may
    # still mention the old toggle by name).
    assert not re.search(r'st\.toggle\(\s*"Enable AI processing"', src), \
        '"Enable AI processing" toggle widget still present'
    assert 'key="lib_ai_toggle"' not in src


def test_header_toggle_marker_and_css():
    src = _source()
    assert 'data-marker="lib-master-toggle"' in src
    assert re.search(r"lib-master-toggle.*button\[kind=\"tertiary\"\]",
                     src, re.S), \
        "borderless tertiary styling for the Stories toggle missing"
    # Theme tokens only in the new rule — no hard-coded colors.
    rule = src[src.index("lib-master-toggle"):]
    rule = rule[:rule.index("/* #220: hairline VERTICAL")]
    assert "var(--ink)" in rule and "var(--accent)" in rule


# ---------------------------------------------------------------------------
# Upload trigger
# ---------------------------------------------------------------------------

def test_upload_trigger_is_icon_only_popover():
    lui, fake = _ui_with_fake_st()
    lui._render_upload_popover_trigger("sid1")
    assert any('data-marker="lib-upload-btn"' in m for m in fake.markup)
    assert len(fake.popovers) == 1
    pop = fake.popovers[0]
    assert pop["label"] == ""
    assert pop["icon"] == lui._TB_ICON_UPLOAD


# ---------------------------------------------------------------------------
# AI engine dropdown: None disables AI, loudly
# ---------------------------------------------------------------------------

def test_ai_engine_selectbox_saves_choice(monkeypatch):
    lui, fake = _ui_with_fake_st()
    saved = {}
    monkeypatch.setattr(lui.lib, "load_prefs", lambda: {})
    monkeypatch.setattr(lui.lib, "save_prefs",
                        lambda d: saved.update(d))
    fake.session_state["lib_ai_engine"] = "Codex"
    lui._render_ai_engine_selectbox()
    assert saved == {"library_ai_engine": "Codex"}


def test_ai_engine_selectbox_save_failure_is_loud(monkeypatch):
    lui, fake = _ui_with_fake_st()

    def _boom(_d):
        raise OSError("disk full")

    monkeypatch.setattr(lui.lib, "load_prefs", lambda: {})
    monkeypatch.setattr(lui.lib, "save_prefs", _boom)
    fake.session_state["lib_ai_engine"] = "Codex"
    lui._render_ai_engine_selectbox()
    assert fake.errors, "save failure must surface, never silently drop"
    assert "Codex" not in str(fake.errors) or "Could not save" in \
        fake.errors[0]


def test_library_ai_engine_resolution(monkeypatch):
    lui, _fake = _ui_with_fake_st()
    none_label = lui.lib.LIBRARY_AI_ENGINE_NONE_LABEL
    assert none_label == "None"

    monkeypatch.setattr(lui.lib, "load_prefs",
                        lambda: {"library_ai_engine": "None"})
    assert lui._library_ai_engine() is None

    monkeypatch.setattr(lui.lib, "load_prefs",
                        lambda: {"library_ai_engine": "Codex"})
    assert lui._library_ai_engine() == \
        lui.lib.LIBRARY_ENGINE_OPTIONS["Codex"]

    # Legacy migration: no engine pref + old toggle off -> None.
    monkeypatch.setattr(lui.lib, "load_prefs", lambda: {})
    assert lui._library_ai_engine() is None

    # Legacy migration: no engine pref + old toggle on -> default engine.
    monkeypatch.setattr(lui.lib, "load_prefs",
                        lambda: {"library_ai_enabled": True})
    assert lui._library_ai_engine() == \
        lui.lib.LIBRARY_ENGINE_OPTIONS[lui.lib.DEFAULT_LIBRARY_AI_ENGINE]

    # Unknown label -> None (fail-safe direction is "AI off").
    monkeypatch.setattr(lui.lib, "load_prefs",
                        lambda: {"library_ai_engine": "Nope"})
    assert lui._library_ai_engine() is None


def test_ai_none_fails_loudly_on_hashtag_refresh(monkeypatch):
    lui, _fake = _ui_with_fake_st()
    monkeypatch.setattr(
        lui.lib, "load_story",
        lambda sid: {"meta": {"title": "T", "hashtags": []}, "script": ""})
    with pytest.raises(RuntimeError) as exc:
        lui.lib.refresh_hashtags("a", ai_engine=None)
    assert "toolbar" in str(exc.value).lower(), \
        f"message must point at the toolbar dropdown: {exc.value}"


# ---------------------------------------------------------------------------
# #290: collapsible master view + Delete-all in the header
# ---------------------------------------------------------------------------

def test_header_toggle_flips_collapsed_state(monkeypatch):
    lui, fake = _ui_with_recording_st(clicks=("lib_master_toggle",))
    _page_stubs(monkeypatch, lui)
    lui.render_library_page()
    assert fake.session_state.get("lib_master_collapsed") is True
    assert fake.reran is True
    # The toggle is a borderless tertiary button labeled "Stories · N".
    tog = [k for k in fake.button_kwargs
           if k.get("key") == "lib_master_toggle"]
    assert len(tog) == 1
    assert tog[0]["label"] == "Stories · 3"
    assert tog[0].get("type") == "tertiary"


def test_collapsed_shows_two_item_peek(monkeypatch):
    """#290: collapsed never means header-only — the two newest stories
    stay visible under the header as a peek."""
    lui, fake = _ui_with_recording_st()
    _page_stubs(monkeypatch, lui)
    fake.session_state["lib_master_collapsed"] = True
    lui.render_library_page()
    specs = [s for s in fake.column_specs if isinstance(s, list)]
    assert [1, 3] not in specs, \
        "master/detail columns must not render when collapsed"
    picker = _story_radios(fake)
    assert len(picker) == 1
    assert picker[0]["options"] == ["a", "b"], \
        f"collapsed peek must show exactly the two newest stories, got {picker[0]['options']}"
    # The detail still renders below the peek (its toolbar popovers).
    icons = [p.get("icon") for p in fake.popovers]
    assert lui._TB_ICON_SHARE in icons


def test_collapsed_peek_selection_falls_back(monkeypatch):
    """A selection outside the collapsed peek (e.g. made while expanded)
    falls back to the first visible story — the detail always matches a
    visible item."""
    lui, fake = _ui_with_recording_st()
    _page_stubs(monkeypatch, lui)
    fake.session_state["lib_master_collapsed"] = True
    fake.session_state["lib_selected_story"] = "c"
    fake.session_state["lib_story_radio"] = "c"
    lui.render_library_page()
    assert fake.session_state["lib_selected_story"] == "a"
    # The stale radio value is reset before the widget is created.
    assert "lib_story_radio" not in fake.session_state


def test_collapsed_peek_keeps_valid_selection(monkeypatch):
    """A selection inside the peek survives collapsing."""
    lui, fake = _ui_with_recording_st()
    _page_stubs(monkeypatch, lui)
    fake.session_state["lib_master_collapsed"] = True
    fake.session_state["lib_selected_story"] = "b"
    fake.session_state["lib_story_radio"] = "b"
    lui.render_library_page()
    assert fake.session_state["lib_selected_story"] == "b"


def test_expanded_shows_all_stories(monkeypatch):
    lui, fake = _ui_with_recording_st()
    _page_stubs(monkeypatch, lui)
    lui.render_library_page()
    specs = [s for s in fake.column_specs if isinstance(s, list)]
    assert [1, 3] in specs
    picker = _story_radios(fake)
    assert len(picker) == 1
    assert picker[0]["options"] == ["a", "b", "c"]


def test_delete_all_trigger_lives_in_header(monkeypatch):
    lui, fake = _ui_with_recording_st()
    _page_stubs(monkeypatch, lui)
    lui.render_library_page()
    trig = [k for k in fake.button_kwargs
            if k.get("key") == "lib_delpop_all-trigger"]
    assert len(trig) == 1
    assert trig[0]["label"] == ""
    assert trig[0]["icon"] == lui._TB_ICON_DELETE
    assert trig[0].get("help") == "Delete every saved story"


def test_header_uses_divider_separator(monkeypatch):
    lui, fake = _ui_with_recording_st()
    _page_stubs(monkeypatch, lui)
    lui.render_library_page()
    assert fake.dividers, \
        "the header must use st.divider() as its section separator"
