"""Step-wise buttons own their loading state (issue #198).

HIG §3 (https://developer.apple.com/design/human-interface-guidelines/):
the control that starts work owns its progress — the initiating button shows
loading and stays disabled until the step result lands. No second click.

Covers:
- the ``core.stepwise_flow`` state machine: ``request_step_run`` claims the
  in-flight slot and refuses duplicates loudly; ``complete_step_run``
  releases it (idempotent, success and failure alike); ``step_run_inflight``
  covers the whole pending-to-result window;
- source-level wiring in ``app.py``: every step-wise initiating button
  (Launch / Restart / Retry / Proceed / Re-run) renders ``disabled`` while a
  run is in flight, shows a running label when it is the in-flight action,
  and guards its handler with ``request_step_run``;
- the run block executes AFTER the action buttons have rendered (so the
  disabled states reach the page before the blocking step call), renders
  progress into a top-anchored ``step_status_slot``, and releases the
  in-flight marker in a ``finally``.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import stepwise_flow as sf  # noqa: E402


def _state():
    return {}


# ---------------------------------------------------------------------------
# State machine: request / refuse / complete
# ---------------------------------------------------------------------------

def test_request_claims_inflight_slot():
    s = _state()
    assert sf.request_step_run(s, sf.ACTION_PROCEED) is True
    assert s[sf.INFLIGHT_KEY] == sf.ACTION_PROCEED
    assert s[sf.RUN_REQUESTED_KEY] is True


def test_duplicate_request_refused_and_state_untouched():
    s = _state()
    assert sf.request_step_run(s, sf.ACTION_PROCEED) is True
    # A second click while the run is in flight is refused — loudly (the
    # caller shows an error), never queued, never overwriting the action.
    assert sf.request_step_run(s, sf.ACTION_RERUN) is False
    assert s[sf.INFLIGHT_KEY] == sf.ACTION_PROCEED
    assert s[sf.RUN_REQUESTED_KEY] is True


def test_complete_releases_slot_and_request():
    s = _state()
    sf.request_step_run(s, sf.ACTION_RETRY)
    sf.complete_step_run(s)
    assert sf.INFLIGHT_KEY not in s
    assert s[sf.RUN_REQUESTED_KEY] is False
    assert sf.step_run_inflight(s) is False


def test_complete_is_idempotent():
    s = _state()
    sf.complete_step_run(s)  # no run in flight — must not raise
    sf.complete_step_run(s)
    assert sf.step_run_inflight(s) is False


def test_new_action_can_start_after_complete():
    s = _state()
    sf.request_step_run(s, sf.ACTION_LAUNCH)
    sf.complete_step_run(s)
    assert sf.request_step_run(s, sf.ACTION_PROCEED) is True
    assert s[sf.INFLIGHT_KEY] == sf.ACTION_PROCEED


def test_inflight_action_reports_current_action():
    s = _state()
    assert sf.inflight_action(s) is None
    sf.request_step_run(s, sf.ACTION_RERUN)
    assert sf.inflight_action(s) == sf.ACTION_RERUN


def test_inflight_covers_pending_request_without_marker():
    # Defensive: if run_requested is set without an action marker (e.g. a
    # legacy path), buttons still lock.
    assert sf.step_run_inflight({sf.RUN_REQUESTED_KEY: True}) is True
    assert sf.step_run_inflight({}) is False
    assert sf.step_run_inflight({sf.RUN_REQUESTED_KEY: False}) is False


def test_action_names_are_distinct():
    actions = [sf.ACTION_LAUNCH, sf.ACTION_RETRY, sf.ACTION_BACK,
               sf.ACTION_PROCEED, sf.ACTION_RERUN, sf.ACTION_RESTART]
    assert len(set(actions)) == len(actions)


def test_full_lifecycle_launch_then_duplicate_proceed():
    """The issue's scenario: click Proceed mid-run -> refused; after the
    step result lands -> the next action is accepted."""
    s = _state()
    assert sf.request_step_run(s, sf.ACTION_LAUNCH) is True
    assert sf.step_run_inflight(s) is True
    assert sf.request_step_run(s, sf.ACTION_PROCEED) is False  # duplicate
    sf.complete_step_run(s)  # step result lands
    assert sf.step_run_inflight(s) is False
    assert sf.request_step_run(s, sf.ACTION_PROCEED) is True


# ---------------------------------------------------------------------------
# Source-level wiring in app.py
# ---------------------------------------------------------------------------

def _app_src():
    return (Path(__file__).resolve().parent.parent
            / "app.py").read_text(encoding="utf-8")


def test_every_initiating_handler_guards_with_request_step_run():
    """Each button that starts a step run must claim the in-flight slot via
    request_step_run — Launch, Restart, Retry, Proceed, Re-run."""
    src = _app_src()
    for action in ("ACTION_LAUNCH", "ACTION_RESTART", "ACTION_RETRY",
                   "ACTION_PROCEED", "ACTION_RERUN"):
        assert f"request_step_run(st.session_state, {action})" in src, \
            f"handler for {action} must guard with request_step_run"


def test_buttons_render_disabled_while_inflight():
    """All step-wise action buttons pass disabled= tied to the in-flight
    state, so no second click is possible mid-run."""
    src = _app_src()
    assert "disabled=step_run_inflight(st.session_state)" in src  # launch/restart/retry
    assert "disabled=_sw_inflight" in src  # checkpoint back/proceed/re-run


def test_initiating_buttons_show_running_labels():
    """The in-flight initiating button owns its loading state visibly."""
    src = _app_src()
    assert "Retrying Step " in src and "…" in src
    assert "Re-running Step " in src
    assert "Proceeding to Step " in src
    assert "Integrating & validating…" in src
    assert "Restarting Step 1…" in src


def test_run_block_renders_progress_into_top_slot():
    """The detached st.status is anchored at the top of the output column via
    a slot, so live progress is owned by the initiating control's area."""
    src = _app_src()
    assert "step_status_slot = st.empty()" in src
    assert "with step_status_slot.status(" in src


def test_run_block_executes_after_action_buttons():
    """The blocking step call must come AFTER the action buttons render, so
    the disabled in-flight states reach the page before the run blocks."""
    src = _app_src()
    slot_pos = src.index("step_status_slot = st.empty()")
    proceed_pos = src.index('key=f"proceed_btn_{curr_step}"')
    exec_pos = src.index("with step_status_slot.status(")
    assert slot_pos < proceed_pos < exec_pos, \
        "slot, then buttons, then the blocking step execution"


def test_inflight_released_in_finally():
    """complete_step_run runs in a finally — success AND loud failure release
    the buttons exactly when the step result lands; they can never stick
    disabled."""
    src = _app_src()
    finally_pos = src.index("complete_step_run(st.session_state)")
    context = src[max(0, finally_pos - 800):finally_pos]
    assert "finally:" in context
    # Failure still records generation_error (fail loudly, never swallowed).
    assert 'st.session_state.generation_error = {' in src


def test_no_bare_run_requested_set_in_initiating_handlers():
    """request_step_run is the only writer of stepwise_run_requested=True —
    no handler may set the flag without claiming the in-flight slot."""
    src = _app_src()
    assert src.count("st.session_state.stepwise_run_requested = True") == 0, \
        "all run requests must go through request_step_run"
