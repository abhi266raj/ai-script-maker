"""Step-wise generation run-state machine (issue #198).

HIG §3 (https://developer.apple.com/design/human-interface-guidelines/):
the control that starts work owns its progress — the initiating button shows
the loading state and stays disabled until the step result lands, so a
second click can never queue a duplicate step run.

This mirrors the ``generation_guard`` single-flight pattern (issue #195),
extended for step-wise mode's several initiating buttons (Launch, Retry,
Proceed, Re-run, Restart): the in-flight marker carries the *action name* so
the exact initiating button can render its running label while every other
step-wise action button renders disabled.

Because Streamlit reruns the whole script on every interaction and a step
run blocks the script run for minutes, the in-flight run is tracked in
session state (``stepwise_inflight``):

* every initiating button calls :func:`request_step_run` in its handler and
  renders ``disabled`` while :func:`step_run_inflight` is true;
* the run block calls :func:`complete_step_run` on success AND on failure,
  so the buttons re-enable exactly when the step result lands and can never
  be left permanently disabled;
* a click that lands while a run is already in flight is refused loudly
  (``request_step_run`` returns False and the handler shows an error) —
  never silently swallowed, never double-queued.

The functions take a plain ``dict``-like state object so the state machine is
unit-testable without Streamlit; ``st.session_state`` satisfies the protocol.
"""

# Action names for the in-flight marker.
ACTION_LAUNCH = "launch"
ACTION_RETRY = "retry"
ACTION_BACK = "back"      # navigates; never starts a run, but nav is locked too
ACTION_PROCEED = "proceed"
ACTION_RERUN = "rerun"
ACTION_RESTART = "restart"

INFLIGHT_KEY = "stepwise_inflight"
RUN_REQUESTED_KEY = "stepwise_run_requested"


def request_step_run(state, action):
    """Record a new step-wise run.

    Returns True and marks the run in flight. Returns False — recording
    nothing — when a run is already in flight, so a duplicate click can
    never start a second run.
    """
    if state.get(INFLIGHT_KEY):
        return False
    state[INFLIGHT_KEY] = action
    state[RUN_REQUESTED_KEY] = True
    return True


def complete_step_run(state):
    """Clear the in-flight marker once the step result has landed.

    Must be called on success and on failure alike; idempotent.
    """
    state.pop(INFLIGHT_KEY, None)
    state[RUN_REQUESTED_KEY] = False


def inflight_action(state):
    """Return the action name of the in-flight run, or None."""
    return state.get(INFLIGHT_KEY)


def step_run_inflight(state):
    """True while a step-wise run is pending or executing.

    Buttons stay disabled for the whole window: from the click, through
    the blocking step execution, until the result lands and
    :func:`complete_step_run` runs.
    """
    return bool(state.get(INFLIGHT_KEY) or state.get(RUN_REQUESTED_KEY))
