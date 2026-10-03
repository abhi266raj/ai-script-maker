"""Developer on-demand Apple FM warm-up (issue #37).

The icon-only warm-up button next to the Studio/Library tab bar kicks
off the #4 availability probe (30s -> 30s -> 60s) in a daemon thread so
the first real generation skips the cold-start delay. Manual-only:
nothing automatic — warm-up runs solely on button tap.

Covers: mailbox read/write, double-start refusal, stale-state recovery,
worker terminal states (done only on probe-available, failed with the
probe's own message otherwise — same messaging as #4), and the HIG
loading/disabled button contract (pure helper, no Streamlit runtime).

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
# NOTE: `import core.dual_engine as de` would bind the *singleton instance*,
# because core/__init__.py rebinds the `dual_engine` attribute on the
# package. Import the module object via sys.modules instead.
import core  # noqa: E402
import sys as _sys  # noqa: E402
_dual_engine_mod = _sys.modules["core.dual_engine"]
from library_ui import _fm_warmup_button_props, _FM_WARMUP_ICON  # noqa: E402


@pytest.fixture
def libdir(tmp_path, monkeypatch):
    root = tmp_path / "HindiReelStudio"
    monkeypatch.setattr(lib, "LIBRARY_ROOT", root)
    monkeypatch.setattr(lib, "STORIES_DIR", root / "stories")
    monkeypatch.setattr(lib, "PREFS_PATH", root / "prefs.json")
    return root


def _mailbox(libdir):
    return libdir / "fm_warmup.json"


# ---------------------------------------------------------------------------
# Mailbox read
# ---------------------------------------------------------------------------

def test_read_missing_mailbox_is_idle(libdir):
    assert lib.read_fm_warmup_state() == {}


def test_read_corrupt_mailbox_is_idle(libdir):
    _mailbox(libdir).parent.mkdir(parents=True, exist_ok=True)
    _mailbox(libdir).write_text("{not json", encoding="utf-8")
    assert lib.read_fm_warmup_state() == {}


def test_read_non_dict_mailbox_is_idle(libdir):
    _mailbox(libdir).parent.mkdir(parents=True, exist_ok=True)
    _mailbox(libdir).write_text("[1, 2]", encoding="utf-8")
    assert lib.read_fm_warmup_state() == {}


# ---------------------------------------------------------------------------
# Kickoff
# ---------------------------------------------------------------------------

def test_start_writes_warming_state(libdir, monkeypatch):
    gate = threading.Event()

    def fake_worker(*a):
        gate.wait(timeout=10)

    monkeypatch.setattr(lib, "_fm_warmup_worker", fake_worker)
    ok, reason = lib.start_fm_warmup()
    assert ok, reason
    assert reason == ""
    state = lib.read_fm_warmup_state()
    assert state["state"] == "warming"
    gate.set()


def test_double_start_refused_while_warming(libdir, monkeypatch):
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


def test_start_never_raises(libdir, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("no threads for you")

    monkeypatch.setattr(lib.threading, "Thread", boom)
    ok, reason = lib.start_fm_warmup()
    assert not ok
    assert "Could not start warm-up" in reason


# ---------------------------------------------------------------------------
# Stale-state recovery
# ---------------------------------------------------------------------------

def test_stale_warming_recovered_as_interrupted(libdir):
    _mailbox(libdir).parent.mkdir(parents=True, exist_ok=True)
    _mailbox(libdir).write_text(json.dumps({
        "state": "warming",
        "message": "",
        "seconds": 0.0,
        "started_at": time.time() - (lib.FM_WARMUP_STALE_SECONDS + 60.0),
    }), encoding="utf-8")
    state = lib.read_fm_warmup_state()
    assert state["state"] == "failed"
    assert "interrupted" in state["message"]
    # The recovery is persisted, so the button is not stuck disabled.
    assert json.loads(_mailbox(libdir).read_text(encoding="utf-8"))["state"] == "failed"


def test_fresh_warming_not_recovered(libdir):
    _mailbox(libdir).parent.mkdir(parents=True, exist_ok=True)
    _mailbox(libdir).write_text(json.dumps({
        "state": "warming",
        "message": "",
        "seconds": 0.0,
        "started_at": time.time(),
    }), encoding="utf-8")
    assert lib.read_fm_warmup_state()["state"] == "warming"


# ---------------------------------------------------------------------------
# Worker terminal states (probe mocked — never runs a real model)
# ---------------------------------------------------------------------------

def _mock_probe(monkeypatch, status=None, exc=None):
    def fake_check_status(force=False, check_fm=True):
        assert force and check_fm, "warm-up must force a full FM probe"
        if exc is not None:
            raise exc
        return status

    monkeypatch.setattr(_dual_engine_mod.dual_engine, "check_status", fake_check_status)


def test_worker_done_only_when_probe_available(libdir, monkeypatch):
    _mock_probe(monkeypatch, status={
        "fm": {"available": True,
               "message": "Apple Foundation Model ready (On-Device)"}})
    lib._fm_warmup_worker()
    state = lib.read_fm_warmup_state()
    assert state["state"] == "done"
    assert state["message"] == "Apple Foundation Model ready (On-Device)"
    assert state["seconds"] >= 0.0


def test_worker_failed_carries_probe_message_verbatim(libdir, monkeypatch):
    probe_msg = ("Probe timed out: the on-device model may still be "
                 "initializing (first launch can download the model).")
    _mock_probe(monkeypatch, status={
        "fm": {"available": False, "message": probe_msg}})
    lib._fm_warmup_worker()
    state = lib.read_fm_warmup_state()
    assert state["state"] == "failed"
    assert state["message"] == probe_msg


def test_worker_failed_when_fm_binary_missing(libdir, monkeypatch):
    # No `fm` binary on this machine: check_status reports available=False
    # with its honest #4 "Not found" message — never a fake success.
    _mock_probe(monkeypatch, status={
        "fm": {"available": False, "message": "Not found",
               "path": "fm", "restricted": False}})
    lib._fm_warmup_worker()
    state = lib.read_fm_warmup_state()
    assert state["state"] == "failed"
    assert state["message"] == "Not found"


def test_worker_failed_when_probe_raises(libdir, monkeypatch):
    _mock_probe(monkeypatch, exc=OSError("fm binary exploded"))
    lib._fm_warmup_worker()
    state = lib.read_fm_warmup_state()
    assert state["state"] == "failed"
    assert "Warm-up failed" in state["message"]
    assert "fm binary exploded" in state["message"]


# ---------------------------------------------------------------------------
# HIG button contract: the starter owns its loading state
# ---------------------------------------------------------------------------

def test_button_idle_props():
    assert _fm_warmup_button_props({}) == (_FM_WARMUP_ICON, False)
    assert _fm_warmup_button_props({"state": "done"}) == (_FM_WARMUP_ICON, False)
    assert _fm_warmup_button_props({"state": "failed"}) == (_FM_WARMUP_ICON, False)


def test_button_warming_props_disabled():
    icon, disabled = _fm_warmup_button_props({"state": "warming"})
    assert disabled is True
    assert icon == _FM_WARMUP_ICON, \
        "stable icon while warming — the spinner + disabled state own the progress (#365)"
