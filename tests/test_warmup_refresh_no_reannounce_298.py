"""Issue #298 — Apple FM warm-up must be manual-only, end to end.

The user reported the "Apple FM warmed up …" toast appearing on page
refresh (and at launch) without ever tapping the warm-up button. Two
compounding mechanisms:

1. Automatic launch-time warm-up (`maybe_auto_cold_start`, #115/#122) —
   already removed by #263; asserted gone here as a regression guard.
2. Stale "done" re-announced on refresh: the mailbox keeps
   `state="done"` forever, and a refresh starts a fresh
   `st.session_state`, so the #181 once-per-run guard had never seen the
   marker and re-fired the toast. Fixed by keying the announcement on
   runs initiated in the CURRENT session (via the button tap):
   `library_ui._FM_WARMUP_SESSION_RUNS_KEY`.

Covers:
- refresh after a completed manual warm-up fires NO toast/result;
- refresh after a failed warm-up fires NO toast;
- a run initiated in this session still toasts exactly once;
- the button tap registers the run in the session set (nothing starts
  without the tap — the mailbox is untouched by mere rendering);
- the worker's terminal state preserves the kick-off `started_at`, so
  the session correlation is stable for the whole run.

The refresh tests FAIL on pristine develop (the toast re-fires) and
PASS with the fix. Behavior-preservation tests pass on both.

Run: python -m pytest tests/test_warmup_refresh_no_reannounce_298.py -q
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import story_library as lib  # noqa: E402
import library_ui as lui  # noqa: E402


class _FakeSt:
    """Minimal Streamlit stub for the warm-up button/result renderers."""

    def __init__(self):
        self.session_state = {}
        self.toasts = []          # (msg, icon) tuples
        self.captions = []
        self.errors = []
        self.buttons = []
        self.button_results = {}
        self.reruns = 0

    def caption(self, text, **kw):
        self.captions.append(text)

    def error(self, text, **kw):
        self.errors.append(text)

    def toast(self, msg, icon=None):
        self.toasts.append((msg, icon))

    def button(self, label, **kw):
        self.buttons.append((label, kw.get("icon")))
        return self.button_results.get(kw.get("icon") or label, False)

    def spinner(self, text):
        import contextlib
        return contextlib.nullcontext()

    def rerun(self):
        self.reruns += 1


@pytest.fixture
def ui(monkeypatch):
    fake = _FakeSt()
    monkeypatch.setattr(lui, "st", fake)
    return fake


@pytest.fixture
def libdir(tmp_path, monkeypatch):
    root = tmp_path / "HindiReelStudio"
    monkeypatch.setattr(lib, "LIBRARY_ROOT", root)
    monkeypatch.setattr(lib, "STORIES_DIR", root / "stories")
    monkeypatch.setattr(lib, "PREFS_PATH", root / "prefs.json")
    return root


def _done_mailbox(started_at=1700000009.0, seconds=3.2):
    return {"state": "done",
            "message": "Apple Foundation Model ready (On-Device)",
            "seconds": seconds,
            "started_at": started_at}


# ---------------------------------------------------------------------------
# The reported bug: refresh must not re-announce a previous session's run
# ---------------------------------------------------------------------------

def test_refresh_after_completed_manual_warmup_fires_no_toast(ui, monkeypatch):
    """#298: the mailbox still says "done" from a run the user started in
    a previous session. A refresh (fresh session state) must render
    nothing — no toast, no result line."""
    monkeypatch.setattr(lui.lib, "read_fm_warmup_state",
                        lambda: _done_mailbox())
    # fresh session_state: this session never tapped the button
    assert ui.session_state == {}

    lui._render_fm_warmup_result()

    assert ui.toasts == [], f"stale done must not re-fire: {ui.toasts}"
    assert ui.captions == []
    assert ui.errors == []


def test_refresh_after_failed_warmup_fires_no_toast(ui, monkeypatch):
    """#298, failure side: a stale "failed" from a previous session must
    not re-fire its toast on refresh either."""
    monkeypatch.setattr(lui.lib, "read_fm_warmup_state",
                        lambda: {"state": "failed",
                                 "message": "probe timed out",
                                 "started_at": 1700000011.0})
    assert ui.session_state == {}

    lui._render_fm_warmup_result()

    assert ui.toasts == [], f"stale failure must not re-fire: {ui.toasts}"
    assert ui.errors == []


def test_stale_done_rerenders_still_silent(ui, monkeypatch):
    """Repeated renders of the stale state stay silent — the toast is
    not merely deferred one rerun."""
    monkeypatch.setattr(lui.lib, "read_fm_warmup_state",
                        lambda: _done_mailbox())
    for _ in range(3):
        lui._render_fm_warmup_result()
    assert ui.toasts == []


# ---------------------------------------------------------------------------
# Behavior preservation: a run started in THIS session still announces once
# ---------------------------------------------------------------------------

def test_session_initiated_done_still_toasts_exactly_once(ui, monkeypatch):
    monkeypatch.setattr(lui.lib, "read_fm_warmup_state",
                        lambda: _done_mailbox())
    ui.session_state[lui._FM_WARMUP_SESSION_RUNS_KEY] = {1700000009.0}

    lui._render_fm_warmup_result()
    lui._render_fm_warmup_result()

    assert len(ui.toasts) == 1, ui.toasts
    assert "3.2s" in ui.toasts[0][0]


def test_session_initiated_failed_still_toasts_once(ui, monkeypatch):
    """Failure stays loud at the moment it happens for a run started in
    this session — the #298 gate only silences previous sessions."""
    monkeypatch.setattr(lui.lib, "read_fm_warmup_state",
                        lambda: {"state": "failed", "message": "boom",
                                 "started_at": 1700000012.0})
    ui.session_state[lui._FM_WARMUP_SESSION_RUNS_KEY] = {1700000012.0}

    lui._render_fm_warmup_result()

    assert len(ui.toasts) == 1, ui.toasts
    assert "boom" in ui.toasts[0][0]


# ---------------------------------------------------------------------------
# Nothing starts without the button tap
# ---------------------------------------------------------------------------

def test_render_without_tap_starts_nothing(libdir, ui, monkeypatch):
    """Rendering the button without tapping it touches neither the
    mailbox nor the session-runs set."""
    monkeypatch.setattr(lib, "_fm_warmup_worker", lambda *a: None)
    # button not tapped
    lui._render_fm_warmup_button()

    assert lib.read_fm_warmup_state() == {}, "mailbox must stay idle"
    assert ui.session_state.get(lui._FM_WARMUP_SESSION_RUNS_KEY) in (None, set())


def test_button_tap_registers_run_in_session(libdir, ui, monkeypatch):
    """Tapping the warm-up button kicks off the probe AND records the run's
    started_at in this session, so the completion toast announces."""
    monkeypatch.setattr(lib, "_fm_warmup_worker", lambda *a: None)
    ui.button_results[lui._FM_WARMUP_ICON] = True

    lui._render_fm_warmup_button()

    assert ui.reruns == 1, "tap must rerun so the button shows its busy state"
    kicked = lib.read_fm_warmup_state()
    assert kicked["state"] == "warming"
    runs = ui.session_state.get(lui._FM_WARMUP_SESSION_RUNS_KEY) or set()
    assert runs == {kicked["started_at"]}, \
        "the tap must register exactly the kicked-off run"


def test_tap_target_is_icon_only_warmup_button(libdir, ui, monkeypatch):
    """The tap target is the icon-only warm-up button (#365): empty label,
    stable icon, help tag carrying the description."""
    monkeypatch.setattr(lib, "_fm_warmup_worker", lambda *a: None)
    lui._render_fm_warmup_button()
    assert ui.buttons == [("", lui._FM_WARMUP_ICON)], ui.buttons


# ---------------------------------------------------------------------------
# Stable run identity: kickoff started_at survives to the terminal state
# ---------------------------------------------------------------------------

def test_worker_terminal_state_preserves_kickoff_started_at(
        libdir, monkeypatch):
    """#298: the worker must reuse the kick-off's started_at for the
    terminal state — otherwise the UI's per-session correlation (keyed on
    started_at) could never match a completed run to the tap."""
    import sys as _sys
    import core  # noqa: F401  (binds core.dual_engine in sys.modules)
    mod = _sys.modules["core.dual_engine"]

    def fake_check_status(force=False, check_fm=True):
        return {"fm": {"available": True, "message": "ready"}}

    monkeypatch.setattr(mod.dual_engine, "check_status", fake_check_status)
    kicked_at = 1700000013.0
    lib._write_fm_warmup_state({"state": "warming", "message": "",
                                "seconds": 0.0, "started_at": kicked_at})

    lib._fm_warmup_worker(kicked_at)

    state = lib.read_fm_warmup_state()
    assert state["state"] == "done"
    assert state["started_at"] == kicked_at, \
        "terminal state must keep the kick-off's started_at"


# ---------------------------------------------------------------------------
# Regression guard: the automatic path stays gone
# ---------------------------------------------------------------------------

def test_no_automatic_warmup_entrypoint():
    """#298 root cause (1): the #115/#122 automatic launch-time warm-up
    stays decommissioned — nothing may reintroduce it."""
    assert not hasattr(lib, "maybe_auto_cold_start")
    assert not hasattr(lib, "_reset_auto_cold_start_for_tests")
    src = (Path(__file__).resolve().parent.parent
           / "library_ui.py").read_text(encoding="utf-8")
    assert "maybe_auto_cold_start" not in src
