"""Automatic background cold-start (issue #115).

``story_library.maybe_auto_cold_start()`` fires the FM warm-up probe once
per process in a daemon thread so the UI renders immediately and stays
interactive. These tests cover:

- (a) the kick-off never blocks the caller, even when init is slow;
- (b) it fires at most once per process (incl. under concurrent calls);
- (c) background completion is picked up via the mailbox;
- (d) background failure surfaces loudly via the mailbox (never silent);
- (e) the kick-off never raises, even if the starter itself blows up;
- (f) ``render_tab_bar`` wires the auto cold-start (source contract —
      ``library_ui`` needs streamlit, which this env lacks).

Follows the mailbox patterns of tests/test_fm_warmup_v16.py.
"""

import threading
import time
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import story_library as lib  # noqa: E402


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


# ---------------------------------------------------------------------------
# (a) never blocks the caller, even when init is slow
# ---------------------------------------------------------------------------

def test_auto_cold_start_returns_fast_on_slow_init(libdir, monkeypatch):
    # The kick-off must not block the render even when the background
    # worker itself is very slow: the slowness lives in the daemon thread.
    gate = threading.Event()

    def slow_worker():
        gate.wait(timeout=10)

    monkeypatch.setattr(lib, "_fm_warmup_worker", slow_worker)
    t0 = time.time()
    lib.maybe_auto_cold_start()
    elapsed = time.time() - t0
    gate.set()
    # Well under a second even though the worker would take up to 10s.
    assert elapsed < 1.0, f"maybe_auto_cold_start blocked for {elapsed:.2f}s"
    assert lib.read_fm_warmup_state().get("state") == "warming"


def test_auto_cold_start_fires_thread_not_caller(libdir, monkeypatch):
    """The real start_fm_warmup spawns a daemon thread and returns at once."""
    gate = threading.Event()

    def fake_worker():
        gate.wait(timeout=10)

    monkeypatch.setattr(lib, "_fm_warmup_worker", fake_worker)
    t0 = time.time()
    lib.maybe_auto_cold_start()
    elapsed = time.time() - t0
    gate.set()
    assert elapsed < 1.0, f"blocked for {elapsed:.2f}s"
    assert lib.read_fm_warmup_state().get("state") == "warming"


# ---------------------------------------------------------------------------
# (b) fires at most once per process
# ---------------------------------------------------------------------------

def test_auto_cold_start_fires_once(libdir, monkeypatch):
    calls = []
    monkeypatch.setattr(lib, "start_fm_warmup",
                        lambda: (calls.append(1), (True, ""))[1])
    lib.maybe_auto_cold_start()
    lib.maybe_auto_cold_start()
    lib.maybe_auto_cold_start()
    assert len(calls) == 1


def test_auto_cold_start_concurrent_calls_fire_once(libdir, monkeypatch):
    calls = []
    lock = threading.Lock()

    def counting_start():
        with lock:
            calls.append(1)
        return True, ""

    monkeypatch.setattr(lib, "start_fm_warmup", counting_start)
    threads = [threading.Thread(target=lib.maybe_auto_cold_start)
               for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    # At most one kick-off; the starter's own double-start refusal is the
    # second line of defence, but the flag must already serialize this.
    assert len(calls) == 1


def test_auto_cold_start_resets_for_tests(libdir, monkeypatch):
    calls = []
    monkeypatch.setattr(lib, "start_fm_warmup",
                        lambda: (calls.append(1), (True, ""))[1])
    lib.maybe_auto_cold_start()
    assert len(calls) == 1
    lib._reset_auto_cold_start_for_tests()
    lib.maybe_auto_cold_start()
    assert len(calls) == 2


# ---------------------------------------------------------------------------
# (c) background completion is picked up via the mailbox
# ---------------------------------------------------------------------------

def test_background_completion_picked_up(libdir, monkeypatch):
    done = threading.Event()

    def fake_worker():
        lib._write_fm_warmup_state({
            "state": "done",
            "message": "Apple Foundation Model ready (On-Device)",
            "seconds": 1.5,
            "started_at": time.time(),
        })
        done.set()

    monkeypatch.setattr(lib, "_fm_warmup_worker", fake_worker)
    lib.maybe_auto_cold_start()
    assert done.wait(timeout=10), "background worker never finished"
    # The main thread picks the terminal state up on its next read —
    # no st.session_state touched from the worker thread.
    state = lib.read_fm_warmup_state()
    assert state["state"] == "done"
    assert "ready" in state["message"]


# ---------------------------------------------------------------------------
# (d) background failure surfaces loudly via the mailbox
# ---------------------------------------------------------------------------

def test_background_failure_surfaces_loudly(libdir, monkeypatch):
    done = threading.Event()

    def fake_worker():
        lib._write_fm_warmup_state({
            "state": "failed",
            "message": "Apple Foundation Model unavailable: not signed in",
            "seconds": 2.0,
            "started_at": time.time(),
        })
        done.set()

    monkeypatch.setattr(lib, "_fm_warmup_worker", fake_worker)
    lib.maybe_auto_cold_start()
    assert done.wait(timeout=10), "background worker never finished"
    state = lib.read_fm_warmup_state()
    # Fail loudly: explicit terminal state with the probe's own message —
    # the UI renders st.error from this, never a silent half-ready app.
    assert state["state"] == "failed"
    assert "not signed in" in state["message"]


def test_worker_exception_becomes_failed_state(libdir, monkeypatch):
    """The real worker never raises: a blowing-up probe becomes a failed
    mailbox state with the error message (fail loudly, never silent)."""
    # NOTE: `import core.dual_engine as de` binds the singleton *instance*
    # because core/__init__.py rebinds the attribute — get the module via
    # sys.modules (same pattern as test_fm_warmup_v16.py).
    import sys as _sys
    import core.dual_engine  # noqa: F401  (ensures sys.modules entry)
    _de_mod = _sys.modules["core.dual_engine"]

    def boom_probe(*a, **k):
        raise RuntimeError("probe exploded")

    monkeypatch.setattr(_de_mod.dual_engine, "check_status", boom_probe)
    # Run the REAL worker in a thread, like start_fm_warmup does.
    t = threading.Thread(target=lib._fm_warmup_worker, daemon=True)
    t.start()
    t.join(timeout=10)
    state = lib.read_fm_warmup_state()
    assert state["state"] == "failed"
    assert "probe exploded" in state["message"]


# ---------------------------------------------------------------------------
# (e) the kick-off never raises
# ---------------------------------------------------------------------------

def test_auto_cold_start_never_raises(libdir, monkeypatch):
    def boom():
        raise RuntimeError("no threads for you")

    monkeypatch.setattr(lib, "start_fm_warmup", boom)
    # Must not propagate — the render must survive a broken kick-off.
    lib.maybe_auto_cold_start()
    # And it still counts as fired (no retry storm on every render).
    lib.maybe_auto_cold_start()


# ---------------------------------------------------------------------------
# (f) render_tab_bar wires the auto cold-start
# ---------------------------------------------------------------------------

def test_render_tab_bar_wires_auto_cold_start():
    """Source contract: render_tab_bar() fires the background cold-start
    before anything else. (library_ui needs streamlit, absent here, so this
    asserts the wiring statically.)"""
    src = (Path(__file__).resolve().parent.parent
           / "library_ui.py").read_text(encoding="utf-8")
    idx_def = src.index("def render_tab_bar()")
    idx_css = src.index("inject_library_css()", idx_def)
    idx_call = src.index("maybe_auto_cold_start()", idx_def)
    assert idx_def < idx_call < idx_css, \
        "render_tab_bar must call maybe_auto_cold_start() before rendering"
