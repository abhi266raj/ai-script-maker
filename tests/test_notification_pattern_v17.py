"""Single notification pattern (issue #88).

All transient status notifications must funnel through ``library_ui._notify``,
which wraps ``st.toast`` — Streamlit renders toasts in one fixed position
(bottom-right), auto-dismisses them after a few seconds, and styles them
identically. Loud failures keep using ``st.error``/``st.warning`` so they
stay visible until acknowledged.

Covers:
- source-level guard: no bare ``st.success(``/``st.toast(`` call sites remain
  in library_ui.py — every transient status goes through ``_notify``;
- ``_notify`` records a toast (never a persistent success banner);
- the warm-up "done" notice (the issue's screenshot example) toasts and
  auto-dismisses instead of lingering as a success banner;
- the warm-up "failed" notice fires once as an auto-dismissing toast
  (deliberate user-requested exception to the errors-belong-in-alerts
  rule); retry stays available through the main warm-up button.
"""

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import story_library as lib  # noqa: E402


class _FakeSt:
    def __init__(self):
        self.session_state = {}
        self.toasts = []      # (message, icon) in render order
        self.successes = []
        self.errors = []
        self.buttons = []

    def toast(self, msg, icon=None):
        self.toasts.append((msg, icon))

    def success(self, msg):
        self.successes.append(msg)

    def error(self, msg):
        self.errors.append(msg)

    def button(self, label, key=None, **k):
        self.buttons.append((label, key))
        return False


def _ui_with_fake_st():
    """Import library_ui bound to a fake streamlit; restores sys.modules."""
    saved = dict(sys.modules)
    fake = _FakeSt()
    try:
        fake_mod = types.ModuleType("streamlit")
        for name in ("toast", "success", "error", "button"):
            setattr(fake_mod, name, getattr(fake, name))
        fake_mod.session_state = fake.session_state
        sys.modules["streamlit"] = fake_mod
        sys.modules.pop("library_ui", None)
        import library_ui
        return library_ui, fake
    finally:
        sys.modules.clear()
        sys.modules.update(saved)


def _ui_src():
    return (Path(__file__).resolve().parent.parent
            / "library_ui.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Source-level guard: the single pattern
# ---------------------------------------------------------------------------

def test_no_bare_success_or_toast_call_sites():
    """#88: every transient status funnels through ``_notify``.

    A bare ``st.success(`` is a lingering banner; a bare ``st.toast(``
    outside the helper is a second notification pattern. Neither may
    exist — the only ``st.toast(`` call is inside ``_notify`` itself.
    """
    src = _ui_src()
    assert "st.success(" not in src, \
        "transient status must use _notify, not a lingering st.success banner"
    assert src.count("st.toast(") == 1, \
        "the only st.toast call site must be inside _notify"
    assert "def _notify(" in src


# ---------------------------------------------------------------------------
# _notify behaviour
# ---------------------------------------------------------------------------

def test_notify_records_toast_never_success_banner():
    lui, fake = _ui_with_fake_st()
    lui._notify("Saved to Library.", icon=":material/check_circle:")
    assert fake.toasts == [("Saved to Library.", ":material/check_circle:")]
    assert fake.successes == []


def test_notify_without_icon():
    lui, fake = _ui_with_fake_st()
    lui._notify("plain status")
    assert fake.toasts == [("plain status", None)]
    assert fake.successes == []


# ---------------------------------------------------------------------------
# Warm-up result: done toasts; failure toasts once (user-requested exception)
# ---------------------------------------------------------------------------

def test_warmup_done_toasts_with_timing(monkeypatch):
    """The issue's screenshot example: 'Apple FM warmed up in 10.4s …'
    must toast (auto-dismiss) instead of lingering as a success banner."""
    lui, fake = _ui_with_fake_st()
    monkeypatch.setattr(
        lib, "read_fm_warmup_state",
        lambda: {"state": "done", "seconds": 10.4,
                 "message": "Apple Foundation Model ready (On-Device)",
                 "started_at": 1700000006.0})
    # #298: this session initiated the run, so the toast announces it.
    fake.session_state[lui._FM_WARMUP_SESSION_RUNS_KEY] = {1700000006.0}
    lui._render_fm_warmup_result()
    assert fake.toasts == [
        ("Apple FM warmed up in 10.4s — "
         "Apple Foundation Model ready (On-Device)", ":material/check_circle:")]
    assert fake.successes == []
    assert fake.errors == []


def test_warmup_done_without_message_still_honest(monkeypatch):
    lui, fake = _ui_with_fake_st()
    monkeypatch.setattr(
        lib, "read_fm_warmup_state",
        lambda: {"state": "done", "seconds": 3.0, "message": "",
                 "started_at": 1700000007.0})
    fake.session_state[lui._FM_WARMUP_SESSION_RUNS_KEY] = {1700000007.0}
    lui._render_fm_warmup_result()
    assert fake.toasts == [("Apple FM warmed up in 3.0s", ":material/check_circle:")]
    assert fake.successes == []


def test_warmup_failed_toasts_once_then_dismisses(monkeypatch):
    """User-requested exception to the errors-belong-in-alerts rule: a
    failed warm-up fires once as an auto-dismissing toast (the probe's
    message verbatim — still loud at the moment it happens), then goes
    away instead of re-rendering forever. No persistent error chrome;
    retry stays available through the main warm-up button."""
    lui, fake = _ui_with_fake_st()
    monkeypatch.setattr(
        lib, "read_fm_warmup_state",
        lambda: {"state": "failed", "message": "probe timed out",
                 "started_at": 1700000005.0})
    fake.session_state[lui._FM_WARMUP_SESSION_RUNS_KEY] = {1700000005.0}
    lui._render_fm_warmup_result()
    assert fake.toasts == [("Warm-up failed: probe timed out",
                            ":material/warning:")]
    assert fake.errors == []
    assert fake.buttons == []
    # Second render of the same failed run: nothing re-fires.
    lui._render_fm_warmup_result()
    assert fake.toasts == [("Warm-up failed: probe timed out",
                            ":material/warning:")]
