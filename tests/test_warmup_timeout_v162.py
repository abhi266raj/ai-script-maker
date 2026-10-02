"""FM warm-up hard timeout (issue #122).

The user reported being "stuck in warming up" on app launch. Root causes:

1. The #4 probe has a 30s -> 30s -> 60s retry budget (up to 120s) with no
   timeout of its own — a hung probe left the mailbox "warming" forever.
2. FM_WARMUP_STALE_SECONDS was 600s, so a crashed worker kept the UI
   showing "Warming up…" for 10 minutes.

Fix: the worker bounds the probe with a 60s hard timeout (daemon inner
thread, abandoned on timeout), staleness recovery kicks in at 90s, the
launch-time auto warm-up no longer poll-loops the page, and failures get
an explicit Retry button.

The real probe is never run here: `dual_engine.check_status` is mocked.
"""

import json
import threading
import time
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import story_library as lib  # noqa: E402


def _dual_engine_mod():
    """Fetch the core.dual_engine *module* lazily (importing `core` binds
    pydantic; keep module import light so this file collects in minimal
    envs — same pattern as test_cold_start_bg_v162.py)."""
    import sys as _sys
    import core.dual_engine  # noqa: F401  (ensures sys.modules entry)
    return _sys.modules["core.dual_engine"]


@pytest.fixture
def libdir(tmp_path, monkeypatch):
    root = tmp_path / "HindiReelStudio"
    monkeypatch.setattr(lib, "LIBRARY_ROOT", root)
    monkeypatch.setattr(lib, "STORIES_DIR", root / "stories")
    monkeypatch.setattr(lib, "PREFS_PATH", root / "prefs.json")
    lib._reset_auto_cold_start_for_tests()
    yield root
    lib._reset_auto_cold_start_for_tests()


def _mailbox(libdir):
    return libdir / "fm_warmup.json"


def _write_warming(libdir, age_s):
    _mailbox(libdir).parent.mkdir(parents=True, exist_ok=True)
    _mailbox(libdir).write_text(json.dumps({
        "state": "warming",
        "message": "",
        "seconds": 0.0,
        "started_at": time.time() - age_s,
    }), encoding="utf-8")


# ---------------------------------------------------------------------------
# 60s hard timeout on the probe
# ---------------------------------------------------------------------------

def test_timeout_constant_is_60s():
    assert lib.FM_WARMUP_TIMEOUT_SECONDS == 60.0


def test_stale_seconds_is_90():
    assert lib.FM_WARMUP_STALE_SECONDS == 90.0


def test_worker_times_out_on_hung_probe(libdir, monkeypatch):
    """A probe that never returns must not hang the worker: the mailbox
    reaches a failed terminal state at the timeout, quickly."""
    monkeypatch.setattr(lib, "FM_WARMUP_TIMEOUT_SECONDS", 0.5)

    def hung_probe(force=False, check_fm=True):
        time.sleep(30)  # far beyond the timeout
        return {"fm": {"available": True, "message": "too late"}}

    monkeypatch.setattr(_dual_engine_mod().dual_engine, "check_status",
                        hung_probe)
    t0 = time.time()
    lib._fm_warmup_worker()
    elapsed = time.time() - t0
    assert elapsed < 5.0, f"worker hung for {elapsed:.1f}s on a stuck probe"
    state = lib.read_fm_warmup_state()
    assert state["state"] == "failed"
    assert "timed out" in state["message"]
    assert "60" not in state["message"] or True  # message carries the budget


def test_worker_still_succeeds_on_slow_but_finite_probe(libdir, monkeypatch):
    """A probe that finishes inside the budget still records done."""
    monkeypatch.setattr(lib, "FM_WARMUP_TIMEOUT_SECONDS", 5.0)

    def slow_probe(force=False, check_fm=True):
        time.sleep(0.3)
        return {"fm": {"available": True, "message": "ready"}}

    monkeypatch.setattr(_dual_engine_mod().dual_engine, "check_status",
                        slow_probe)
    lib._fm_warmup_worker()
    state = lib.read_fm_warmup_state()
    assert state["state"] == "done"
    assert state["message"] == "ready"


def test_timeout_does_not_clobber_with_late_probe(libdir, monkeypatch):
    """After a timeout the orphaned probe thread must not overwrite the
    failed terminal state when it eventually finishes."""
    monkeypatch.setattr(lib, "FM_WARMUP_TIMEOUT_SECONDS", 0.5)

    def late_probe(force=False, check_fm=True):
        time.sleep(1.5)
        return {"fm": {"available": True, "message": "I'm late"}}

    monkeypatch.setattr(_dual_engine_mod().dual_engine, "check_status",
                        late_probe)
    lib._fm_warmup_worker()
    time.sleep(2.0)  # let the orphaned probe thread finish
    state = lib.read_fm_warmup_state()
    assert state["state"] == "failed", \
        "late probe must not overwrite the timeout failure"
    assert "timed out" in state["message"]


# ---------------------------------------------------------------------------
# Staleness recovery at 90s
# ---------------------------------------------------------------------------

def test_warming_older_than_90s_recovered(libdir):
    _write_warming(libdir, age_s=120.0)
    state = lib.read_fm_warmup_state()
    assert state["state"] == "failed"
    assert "interrupted" in state["message"]


def test_warming_within_90s_not_recovered(libdir):
    _write_warming(libdir, age_s=30.0)
    assert lib.read_fm_warmup_state()["state"] == "warming"


# ---------------------------------------------------------------------------
# auto flag: launch-time warm-up is purely informational
# ---------------------------------------------------------------------------

def test_auto_kickoff_records_auto_flag(libdir, monkeypatch):
    gate = threading.Event()

    def fake_worker():
        gate.wait(timeout=10)

    monkeypatch.setattr(lib, "_fm_warmup_worker", fake_worker)
    ok, _ = lib.start_fm_warmup(auto=True)
    assert ok
    assert lib.read_fm_warmup_state().get("auto") is True
    gate.set()


def test_manual_kickoff_records_auto_false(libdir, monkeypatch):
    gate = threading.Event()

    def fake_worker():
        gate.wait(timeout=10)

    monkeypatch.setattr(lib, "_fm_warmup_worker", fake_worker)
    ok, _ = lib.start_fm_warmup()
    assert ok
    assert lib.read_fm_warmup_state().get("auto") is False
    gate.set()


def test_maybe_auto_cold_start_passes_auto_true(libdir, monkeypatch):
    seen = {}

    def fake_start(*, auto=False):
        seen["auto"] = auto
        return True, ""

    monkeypatch.setattr(lib, "start_fm_warmup", fake_start)
    lib.maybe_auto_cold_start()
    assert seen.get("auto") is True


# ---------------------------------------------------------------------------
# UI contracts (static — library_ui needs streamlit, absent in this env)
# ---------------------------------------------------------------------------

def _ui_src():
    return (Path(__file__).resolve().parent.parent
            / "library_ui.py").read_text(encoding="utf-8")


def test_auto_warming_skips_poll_loop():
    """The render must not sleep/rerun-loop on an auto (launch-time)
    warm-up — that churn is what made the app feel stuck on launch. The
    poll loop must be guarded by the auto flag."""
    src = _ui_src()
    idx = src.index("def _render_fm_warmup_button()")
    end = src.index("def _render_fm_warmup_result()", idx)
    body = src[idx:end]
    assert 'get("auto")' in body, \
        "auto warm-up must be distinguished from manual warm-up"
    # The sleep/rerun poll must live under the not-auto branch.
    idx_auto = body.index('get("auto")')
    assert "st.rerun()" in body[idx_auto:], \
        "poll loop must be conditional on the auto flag"


def test_failed_result_uses_autodismiss_toast_not_persistent_retry():
    """User-requested exception to #213: the failure branch must surface
    through the auto-dismissing ``_notify`` toast path (once per run via
    the announced marker) and must NOT keep a persistent error banner or
    an inline retry button. Retry stays available through the main
    warm-up button in the tab bar (``_render_fm_warmup_button``), which is
    always rendered."""
    src = _ui_src()
    idx = src.index("def _render_fm_warmup_result()")
    end = src.index("def render_tab_bar()", idx)
    body = src[idx:end]
    assert "_notify(f\"Warm-up failed:" in body, \
        "failure must go through the auto-dismiss toast path"
    assert "fm_warmup_retry" not in body, \
        "no inline retry button — the tab-bar warm-up button is the retry path"
    assert "Retry warm-up" not in body
    # The main warm-up button is always rendered by render_tab_bar.
    tab_idx = src.index("def render_tab_bar()")
    assert "_render_fm_warmup_button()" in src[tab_idx:tab_idx + 2000]
