"""Issue #204 — warm-up success leaves a quiet persistent result line.

`_render_fm_warmup_result`'s docstring promised an "honest terminal result
under the tab bar", but on success it only fired the #181 toast. Once the
toast auto-dismissed there was zero on-screen evidence the warm-up had
succeeded. The fix renders a quiet `st.caption` line on every rerun while
the state is "done", independent of the once-only toast.

Covers: persistent caption on success (timing + probe message), caption
renders even when the toast was already announced (no re-arm, no
duplicate toast), empty-message and missing-seconds formatting, the
failure path fires once as an auto-dismissing toast with the verbatim
probe message (deliberate user-requested exception to #213; retry via
the main warm-up button — no persistent error chrome, no caption on
failure), idle state renders nothing, and the #181 toast contract is
untouched.

Run: python -m pytest tests/test_warmup_result_line_v162.py -q
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import library_ui as lui  # noqa: E402


class _FakeSt:
    """Minimal Streamlit stub capturing the calls _render_fm_warmup_result
    makes: caption, error, button, toast, rerun, session_state."""

    def __init__(self):
        self.session_state = {}
        self.captions = []
        self.errors = []
        self.toasts = []          # (msg, icon) tuples
        self.buttons = []         # labels, in render order
        self.button_results = {}
        self.reruns = 0

    def caption(self, text, **kw):
        self.captions.append(text)

    def error(self, text, **kw):
        self.errors.append(text)

    def toast(self, msg, icon=None):
        self.toasts.append((msg, icon))

    def button(self, label, **kw):
        self.buttons.append(label)
        return self.button_results.get(label, False)

    def rerun(self):
        self.reruns += 1


@pytest.fixture
def ui(monkeypatch):
    """library_ui with its `st` module-global replaced by the stub."""
    fake = _FakeSt()
    monkeypatch.setattr(lui, "st", fake)
    return fake


def _mailbox_state(monkeypatch, state):
    monkeypatch.setattr(lui.lib, "read_fm_warmup_state",
                        lambda: dict(state))


def _done_state(**over):
    state = {"state": "done",
             "message": "Apple Foundation Model ready (On-Device)",
             "seconds": 12.345,
             "started_at": 1700000000.0}
    state.update(over)
    return state


# ---------------------------------------------------------------------------
# Success: persistent quiet result line
# ---------------------------------------------------------------------------

def test_done_renders_persistent_caption_with_timing(ui, monkeypatch):
    _mailbox_state(monkeypatch, _done_state())
    lui._render_fm_warmup_result()

    assert len(ui.captions) == 1, ui.captions
    line = ui.captions[0]
    assert "12.3s" in line, line
    assert "Apple Foundation Model ready (On-Device)" in line, line
    assert "✅" not in line and "❌" not in line, \
        "result line must be quiet: no emoji (house rule)"


def test_done_caption_renders_when_toast_already_announced(ui, monkeypatch):
    """#204's core complaint: the caption must not depend on the toast
    firing — once #181's once-only toast is spent, the line stays."""
    state = _done_state()
    marker = (state["started_at"], state["seconds"])
    ui.session_state[lui._FM_WARMUP_TOAST_ANNOUNCED_KEY] = marker
    _mailbox_state(monkeypatch, state)

    lui._render_fm_warmup_result()

    assert ui.toasts == [], "toast must not re-fire for the same run"
    assert len(ui.captions) == 1, ui.captions
    assert "12.3s" in ui.captions[0]


def test_done_caption_still_fires_first_toast(ui, monkeypatch):
    """The #181 toast is untouched: first render of a new run still toasts
    exactly once, AND the persistent line renders alongside it."""
    _mailbox_state(monkeypatch, _done_state())
    lui._render_fm_warmup_result()

    assert len(ui.toasts) == 1, ui.toasts
    msg, icon = ui.toasts[0]
    assert icon == ":material/check_circle:", ui.toasts
    assert "12.3s" in msg, msg
    assert len(ui.captions) == 1, ui.captions


def test_done_empty_message_caption_has_no_dangling_dash(ui, monkeypatch):
    _mailbox_state(monkeypatch, _done_state(message=""))
    lui._render_fm_warmup_result()

    assert ui.captions == ["Apple FM warmed up in 12.3s"], ui.captions


def test_done_missing_seconds_formats_as_zero(ui, monkeypatch):
    _mailbox_state(monkeypatch, _done_state(seconds=None, message=""))
    lui._render_fm_warmup_result()

    assert ui.captions == ["Apple FM warmed up in 0.0s"], ui.captions


# ---------------------------------------------------------------------------
# Failure: one auto-dismissing toast, verbatim message; no persistent chrome
# (deliberate user-requested exception to #213 — retry via the main
# warm-up button in the tab bar)
# ---------------------------------------------------------------------------

def test_failed_fires_once_as_autodismiss_toast(ui, monkeypatch):
    probe_msg = ("Probe timed out: the on-device model may still be "
                 "initializing (first launch can download the model).")
    _mailbox_state(monkeypatch, {"state": "failed", "message": probe_msg,
                                 "started_at": 1700000001.0})
    lui._render_fm_warmup_result()

    assert ui.errors == [], "no persistent alert — the toast auto-dismisses"
    assert ui.buttons == [], "no inline retry button; the tab-bar warm-up button is the retry path"
    assert ui.captions == [], "no quiet line for failures"
    assert len(ui.toasts) == 1, ui.toasts
    msg, icon = ui.toasts[0]
    assert probe_msg in msg, \
        "failure must carry the probe's own message verbatim — fail loudly"
    assert icon == ":material/warning:", ui.toasts


def test_failed_fallback_message_is_never_silent(ui, monkeypatch):
    _mailbox_state(monkeypatch, {"state": "failed", "message": "   ",
                                 "started_at": 1700000002.0})
    lui._render_fm_warmup_result()

    assert ui.errors == []
    assert len(ui.toasts) == 1 and "unknown error" in ui.toasts[0][0], ui.toasts


def test_failed_toast_does_not_refire_for_same_run(ui, monkeypatch):
    state = {"state": "failed", "message": "boom", "started_at": 1700000003.0}
    ui.session_state[lui._FM_WARMUP_TOAST_ANNOUNCED_KEY] = (
        state["started_at"], "failed")
    _mailbox_state(monkeypatch, state)
    lui._render_fm_warmup_result()

    assert ui.toasts == [], "already announced: no second toast"
    assert ui.errors == []


def test_failed_new_run_rearms_toast(ui, monkeypatch):
    ui.session_state[lui._FM_WARMUP_TOAST_ANNOUNCED_KEY] = (
        1700000003.0, "failed")
    _mailbox_state(monkeypatch, {"state": "failed", "message": "boom again",
                                 "started_at": 1700000004.0})
    lui._render_fm_warmup_result()

    assert len(ui.toasts) == 1, ui.toasts
    assert "boom again" in ui.toasts[0][0]


# ---------------------------------------------------------------------------
# Non-terminal states render nothing
# ---------------------------------------------------------------------------

def test_idle_renders_nothing(ui, monkeypatch):
    _mailbox_state(monkeypatch, {})
    lui._render_fm_warmup_result()

    assert ui.captions == [] and ui.errors == [] and ui.toasts == [], \
        "no warm-up has run: nothing under the tab bar"


def test_warming_renders_nothing(ui, monkeypatch):
    """While the probe is in flight the button owns its progress — the
    result line only appears once the state is terminal."""
    _mailbox_state(monkeypatch, {"state": "warming", "started_at": 1.0})
    lui._render_fm_warmup_result()

    assert ui.captions == [] and ui.errors == [] and ui.toasts == []
