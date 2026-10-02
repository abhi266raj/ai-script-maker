"""Issue #289 — warm-up success leaves NO persistent result line.

Reversal of #204: `_render_fm_warmup_result` used to render a quiet
`st.caption` line on every rerun while the state was "done". The user
reported that persistent line as a bug (#289): a successful warm-up
must fire only the #181 auto-dismissing toast (exactly once per run)
and leave no persistent chrome under the tab bar. HIG §7: progress
indicators are transient — they disappear when the work completes.

Covers: no caption on success (first render or reruns), the #181 toast
still fires exactly once per run with timing + probe message (no
dangling dash on empty message, missing seconds formats as 0.0s, no
emoji), the failure path fires once as an auto-dismissing toast with
the verbatim probe message (deliberate user-requested exception to
#213; retry via the main warm-up button — no persistent error chrome,
no caption on failure), and idle/warming states render nothing.

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
# Success (#289): toast exactly once, NO persistent chrome
# ---------------------------------------------------------------------------

def test_done_renders_no_persistent_chrome(ui, monkeypatch):
    """#289: a successful warm-up leaves no persistent result line — the
    auto-dismissing toast is the only success signal."""
    _mailbox_state(monkeypatch, _done_state())
    lui._render_fm_warmup_result()

    assert ui.captions == [], f"no persistent line allowed: {ui.captions}"
    assert ui.errors == [], ui.errors
    assert len(ui.toasts) == 1, ui.toasts
    msg, icon = ui.toasts[0]
    assert "12.3s" in msg, msg
    assert "Apple Foundation Model ready (On-Device)" in msg, msg
    assert icon == ":material/check_circle:", ui.toasts
    assert "✅" not in msg and "❌" not in msg, \
        "toast must be quiet: no emoji (house rule)"


def test_done_rerun_after_toast_announced_renders_nothing(ui, monkeypatch):
    """Once #181's once-only toast is spent, reruns render nothing at
    all — no re-armed toast, no persistent line."""
    state = _done_state()
    marker = (state["started_at"], state["seconds"])
    ui.session_state[lui._FM_WARMUP_TOAST_ANNOUNCED_KEY] = marker
    _mailbox_state(monkeypatch, state)

    lui._render_fm_warmup_result()

    assert ui.toasts == [], "toast must not re-fire for the same run"
    assert ui.captions == [], "no persistent line on reruns"
    assert ui.errors == []


def test_done_toast_fires_exactly_once_across_reruns(ui, monkeypatch):
    """Two consecutive renders of the same completed run: exactly one
    toast total, zero captions — the success signal is never dropped and
    never duplicated."""
    _mailbox_state(monkeypatch, _done_state())
    lui._render_fm_warmup_result()
    lui._render_fm_warmup_result()

    assert len(ui.toasts) == 1, ui.toasts
    assert ui.captions == [], ui.captions


def test_done_new_run_rearms_toast(ui, monkeypatch):
    """A fresh warm-up run re-arms the toast (marker is the run's own
    started_at), still with no persistent line."""
    ui.session_state[lui._FM_WARMUP_TOAST_ANNOUNCED_KEY] = (
        1700000000.0, 12.345)
    _mailbox_state(monkeypatch, _done_state(started_at=1700000001.0,
                                            seconds=8.7))

    lui._render_fm_warmup_result()

    assert len(ui.toasts) == 1, ui.toasts
    assert "8.7s" in ui.toasts[0][0], ui.toasts
    assert ui.captions == [], ui.captions


def test_done_empty_message_toast_has_no_dangling_dash(ui, monkeypatch):
    _mailbox_state(monkeypatch, _done_state(message=""))
    lui._render_fm_warmup_result()

    assert ui.captions == [], ui.captions
    assert ui.toasts[0][0] == "Apple FM warmed up in 12.3s", ui.toasts


def test_done_missing_seconds_formats_as_zero(ui, monkeypatch):
    _mailbox_state(monkeypatch, _done_state(seconds=None, message=""))
    lui._render_fm_warmup_result()

    assert ui.captions == [], ui.captions
    assert ui.toasts[0][0] == "Apple FM warmed up in 0.0s", ui.toasts


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
