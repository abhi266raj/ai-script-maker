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


# Issue #350: per-step failure tracking + user bypass markers. A step that
# fails persistently must never trap the user in a retry-only dead end —
# once the step's own attempts are exhausted, the human is right and may
# move to the next step. These helpers take the same plain-dict state
# protocol as the run-state functions above, so they stay unit-testable
# without Streamlit.

FAIL_COUNTS_KEY = "stepwise_step_fail_counts"
BYPASSED_KEY = "stepwise_bypassed_steps"


def record_step_failure(state, step):
    """Increment the consecutive-failure count for *step*; return the new count."""
    counts = state.setdefault(FAIL_COUNTS_KEY, {})
    counts[step] = counts.get(step, 0) + 1
    return counts[step]


def step_fail_count(state, step):
    """Consecutive failures recorded for *step* (0 when it never failed)."""
    return (state.get(FAIL_COUNTS_KEY) or {}).get(step, 0)


def clear_step_fail_count(state, step):
    """Reset the failure count for *step* (success, bypass, or navigation)."""
    (state.get(FAIL_COUNTS_KEY) or {}).pop(step, None)


def mark_step_bypassed(state, step):
    """Record that the user bypassed failed *step* via 'Move to next step'."""
    state.setdefault(BYPASSED_KEY, set()).add(step)


def step_was_bypassed(state, step):
    """True when *step* was skipped via the failure-panel bypass."""
    return step in (state.get(BYPASSED_KEY) or set())


def reset_stepwise_run_markers(state):
    """Clear failure counts and bypassed marks on launch / restart / exit."""
    state[FAIL_COUNTS_KEY] = {}
    state[BYPASSED_KEY] = set()
