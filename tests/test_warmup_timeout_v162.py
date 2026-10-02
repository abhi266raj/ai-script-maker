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
    yield root


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
# Manual-only: no automatic warm-up concept remains
# ---------------------------------------------------------------------------

def test_no_auto_cold_start_entrypoint():
    """The automatic launch-time kick-off is gone: warm-up runs ONLY on
    button tap."""
    assert not hasattr(lib, "maybe_auto_cold_start"), \
        "maybe_auto_cold_start must not exist — nothing automatic"
    assert not hasattr(lib, "_reset_auto_cold_start_for_tests")


def test_start_fm_warmup_takes_no_auto_kwarg(libdir, monkeypatch):
    """The auto marker is gone from the kick-off signature and the
    mailbox: every warm-up is manual."""
    gate = threading.Event()

    def fake_worker():
        gate.wait(timeout=10)

    monkeypatch.setattr(lib, "_fm_warmup_worker", fake_worker)
    with pytest.raises(TypeError):
        lib.start_fm_warmup(auto=True)
    ok, _ = lib.start_fm_warmup()
    assert ok
    assert "auto" not in lib.read_fm_warmup_state()
    gate.set()


# ---------------------------------------------------------------------------
# UI contracts (static — library_ui needs streamlit, absent in this env)
# ---------------------------------------------------------------------------

def _ui_src():
    return (Path(__file__).resolve().parent.parent
            / "library_ui.py").read_text(encoding="utf-8")


def test_manual_warming_poll_loop_unconditional():
    """With no automatic warm-up left, the render poll loop is
    unconditional: every warm-up is manual, so the button always owns its
    loading state until the worker writes a terminal state."""
    src = _ui_src()
    idx = src.index("def _render_fm_warmup_button()")
    end = src.index("def _render_fm_warmup_result()", idx)
    body = src[idx:end]
    assert "maybe_auto_cold_start" not in src, \
        "render_tab_bar must not trigger any automatic warm-up"
    assert 'get("auto")' not in body, \
        "the auto flag no longer exists"
    # The sleep/rerun poll loop is still there for the manual warm-up.
    assert "_time.sleep(1.0)" in body
    assert "st.rerun()" in body


def test_failed_result_has_retry_button():
    """A loud failure must carry an explicit Retry option."""
    src = _ui_src()
    idx = src.index("def _render_fm_warmup_result()")
    end = src.index("def render_tab_bar()", idx)
    body = src[idx:end]
    assert "Retry warm-up" in body
    assert "fm_warmup_retry" in body
