"""Single-flight guard for the Generate button (issue #195).

HIG §3: the control that starts work owns its progress — the Generate
button shows "Generating…" and stays disabled until the pipeline finishes
or fails, so a second click can never queue a duplicate generation.

Covers:
- the ``core.generation_guard`` state machine (pure dict state, no Streamlit
  needed): begin/end/is_in_flight/button_params, including the loud
  RuntimeError on a duplicate begin (fail loudly, never double-queue);
- source-level regression guards on app.py: the launch button renders
  disabled with the running label while in flight, every continuous launch
  site goes through ``begin_run``, the run block releases the button in a
  ``finally``, and no bare ``run_requested = True`` remains for the
  continuous pipeline.
"""

import sys
from pathlib import Path
import importlib.util

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def _load_guard():
    # Load core/generation_guard.py directly by path: the guard is
    # intentionally dependency-free, so the test must not drag in
    # core/__init__ (pydantic etc.) just to import it.
    spec = importlib.util.spec_from_file_location(
        "generation_guard", REPO_ROOT / "core" / "generation_guard.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gg = _load_guard()


# ---------------------------------------------------------------------------
# State machine unit tests (no Streamlit involved)
# ---------------------------------------------------------------------------

def test_begin_run_claims_slot():
    state = {}
    gg.begin_run(state)
    assert gg.is_in_flight(state) is True
    assert state["run_requested"] is True


def test_begin_run_twice_raises_loudly_and_keeps_single_run():
    state = {}
    gg.begin_run(state)
    with pytest.raises(RuntimeError, match="already in flight"):
        gg.begin_run(state)
    # Still exactly one run in flight — never double-queued.
    assert gg.is_in_flight(state) is True
    assert state["run_requested"] is True


def test_end_run_releases_slot():
    state = {}
    gg.begin_run(state)
    gg.end_run(state)
    assert gg.is_in_flight(state) is False


def test_end_run_idempotent_when_idle():
    state = {}
    gg.end_run(state)  # must not raise, must not create a phantom run
    assert gg.is_in_flight(state) is False


def test_is_in_flight_defaults_false_on_fresh_state():
    assert gg.is_in_flight({}) is False


def test_run_can_start_again_after_end():
    state = {}
    gg.begin_run(state)
    gg.end_run(state)
    gg.begin_run(state)  # no stuck-disabled state
    assert gg.is_in_flight(state) is True


def test_button_params_idle():
    params = gg.button_params({})
    assert params["label"] == "Generate (Continuous)"
    assert params["disabled"] is False


def test_button_params_in_flight():
    state = {}
    gg.begin_run(state)
    params = gg.button_params(state)
    assert params["label"] == "Generating…"
    assert params["disabled"] is True


# ---------------------------------------------------------------------------
# Source-level regression guards on app.py
# ---------------------------------------------------------------------------

APP_SRC = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")


def test_launch_button_owns_loading_state():
    assert 'key="launch_continuous_btn"' in APP_SRC
    # Label/disabled come from the guard, not hard-coded constants.
    assert "button_params(st.session_state)" in APP_SRC
    assert "disabled=_gen_btn[\"disabled\"]" in APP_SRC
    assert '"Generating…"' in APP_SRC


def test_duplicate_click_fails_loudly_in_handler():
    assert "is_in_flight(st.session_state)" in APP_SRC
    assert "A generation is already running" in APP_SRC


def test_all_continuous_launch_sites_use_begin_run():
    # Generate button, "Try again" after failure, compliance "Retry
    # Generation with Recommended Settings" — exactly three launch sites.
    assert APP_SRC.count("begin_run(st.session_state)") == 3


def test_no_bare_run_requested_for_continuous_pipeline():
    # begin_run() sets run_requested internally; a direct assignment would
    # bypass the single-flight guard and re-open the duplicate-click hole.
    for lineno, line in enumerate(APP_SRC.splitlines(), start=1):
        stripped = line.strip()
        if stripped == "st.session_state.run_requested = True":
            pytest.fail(
                f"app.py:{lineno}: bare run_requested assignment bypasses "
                "begin_run() — use the single-flight guard"
            )


def test_run_block_releases_button_in_finally():
    assert "end_run(st.session_state)" in APP_SRC
    idx_try = APP_SRC.find("# Issue #195: the Generate button owns this run.")
    idx_finally = APP_SRC.find("finally:\n            end_run(st.session_state)")
    assert idx_try != -1 and idx_finally != -1 and idx_try < idx_finally


def test_failure_path_reruns_to_reenable_button():
    # After a failure the button must re-enable immediately: the except
    # handler reruns so the failure renders via the generation_error block.
    idx = APP_SRC.find("status_box.update(label=_fail_label, state=\"error\")")
    assert idx != -1
    tail = APP_SRC[idx:idx + 2000]
    assert "st.rerun()" in tail


def test_in_flight_flag_initialized_in_session_state():
    assert '"generation_in_flight" not in st.session_state' in APP_SRC
