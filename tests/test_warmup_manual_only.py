"""Manual-only local LLM warm-up (issue #37).

"warming up should only happen on click of button. Nothing automatic."

- No automatic warm-up trigger exists anywhere: warm-up runs ONLY when
  the user taps the button.
- The button is icon-only (#365, HIG §2): the icon is stable across
  states; the help tag carries the description.
- HIG loading-state contract: while warming, the button keeps its stable
  icon, shows a spinner next to it, and stays disabled (no second tap).

library_ui needs streamlit (absent in this env), so UI contracts are
asserted statically against the source.
"""

import threading
import time
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import story_library as lib  # noqa: E402


def _lib_path():
    return Path(__file__).resolve().parent.parent


def _ui_src():
    return (_lib_path() / "library_ui.py").read_text(encoding="utf-8")


def _button_props_src():
    src = _ui_src()
    idx = src.index("def _fm_warmup_button_props(")
    end = src.index("def _render_fm_warmup_button()", idx)
    return src[idx:end]


# ---------------------------------------------------------------------------
# Nothing automatic
# ---------------------------------------------------------------------------

def test_no_automatic_warmup_entrypoint():
    assert not hasattr(lib, "maybe_auto_cold_start"), \
        "automatic warm-up must not exist"


def test_render_tab_bar_triggers_no_warmup():
    src = _ui_src()
    assert "maybe_auto_cold_start" not in src
    assert "start_fm_warmup" not in src.split("def render_tab_bar()")[1].split(
        "\ndef ")[0], \
        "render_tab_bar must not kick off warm-up"


def test_start_fm_warmup_only_runnable_explicitly(tmp_path, monkeypatch):
    """The only way to start a warm-up is an explicit start_fm_warmup()
    call (i.e. the button tap path) — nothing in module import or render
    triggers it."""
    root = tmp_path / "HindiReelStudio"
    monkeypatch.setattr(lib, "LIBRARY_ROOT", root)
    monkeypatch.setattr(lib, "STORIES_DIR", root / "stories")
    monkeypatch.setattr(lib, "PREFS_PATH", root / "prefs.json")
    calls = []
    orig = lib.start_fm_warmup
    monkeypatch.setattr(lib, "start_fm_warmup",
                        lambda *a, **k: (calls.append(1), orig(*a, **k))[1])
    # Import-time and render-time paths must not exist; the mailbox stays
    # untouched until an explicit call.
    assert lib.read_fm_warmup_state() == {}
    assert calls == []


# ---------------------------------------------------------------------------
# Button: icon-only with a stable icon across states (#365)
# ---------------------------------------------------------------------------

def test_idle_button_props_use_stable_icon():
    body = _button_props_src()
    assert "return _FM_WARMUP_ICON, False" in body, \
        "idle warm-up button must return the stable icon, not disabled"


# ---------------------------------------------------------------------------
# HIG: the button owns its loading state
# ---------------------------------------------------------------------------

def test_warming_button_props_stable_icon_and_disabled():
    body = _button_props_src()
    assert "return _FM_WARMUP_ICON, True" in body, \
        "while warming the button must keep its stable icon and be disabled"


def test_warming_button_rendered_disabled():
    """The disabled render path passes disabled=True with the stable icon
    (no second tap) and shows a spinner next to the button."""
    src = _ui_src()
    idx = src.index("def _render_fm_warmup_button()")
    end = src.index("def _render_fm_warmup_result()", idx)
    body = src[idx:end]
    assert 'key="fm_warmup_btn", disabled=True' in body
    assert 'with st.spinner(""):' in body, \
        "while warming the button must show a spinner (stable icon, HIG §3)"


def test_double_start_refused(tmp_path, monkeypatch):
    """A second kick-off while warming is refused loudly, never stacked."""
    root = tmp_path / "HindiReelStudio"
    monkeypatch.setattr(lib, "LIBRARY_ROOT", root)
    monkeypatch.setattr(lib, "STORIES_DIR", root / "stories")
    monkeypatch.setattr(lib, "PREFS_PATH", root / "prefs.json")
    gate = threading.Event()

    def fake_worker(*a):
        gate.wait(timeout=10)

    monkeypatch.setattr(lib, "_fm_warmup_worker", fake_worker)
    ok, _ = lib.start_fm_warmup()
    assert ok
    ok2, reason = lib.start_fm_warmup()
    assert not ok2
    assert "already running" in reason
    gate.set()
