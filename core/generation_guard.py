"""Single-flight guard for the continuous script-generation pipeline (issue #195).

HIG §3 (https://developer.apple.com/design/human-interface-guidelines/):
the control that starts work owns its progress — the Generate button shows
the loading state and stays disabled until the run finishes or fails, so a
second click can never queue a duplicate generation.

Because Streamlit reruns the whole script on every interaction and the
multi-minute pipeline blocks the script run, the in-flight run is tracked in
session state (``generation_in_flight``):

* every launch site calls :func:`begin_run` BEFORE the rerun, so the button
  renders disabled ("Generating…") for the entire run;
* the output-column run block calls :func:`end_run` in a ``finally``, so the
  button is released whether the pipeline finishes, fails, or is interrupted;
* any attempt to start a second run while one is in flight raises
  :class:`RuntimeError` — fail loudly, never silently swallow or double-queue.

The functions take a plain ``dict``-like state object so the state machine is
unit-testable without Streamlit; ``st.session_state`` satisfies the protocol.
"""

IN_FLIGHT_KEY = "generation_in_flight"
RUN_REQUESTED_KEY = "run_requested"


def is_in_flight(state) -> bool:
    """True when a generation run currently owns the Generate button."""
    return bool(state.get(IN_FLIGHT_KEY, False))


def begin_run(state) -> None:
    """Claim the generation slot for a new run.

    Sets ``generation_in_flight`` and ``run_requested`` atomically from the
    caller's point of view. Raises RuntimeError if a run is already in
    flight — a duplicate launch is a bug, so it fails loudly instead of
    queueing a second pipeline.
    """
    if is_in_flight(state):
        raise RuntimeError(
            "Cannot start generation: a generation run is already in flight. "
            "Refusing to double-queue the pipeline."
        )
    state[IN_FLIGHT_KEY] = True
    state[RUN_REQUESTED_KEY] = True


def end_run(state) -> None:
    """Release the generation slot. Idempotent — safe when no run is in flight."""
    state[IN_FLIGHT_KEY] = False


def button_params(state) -> dict:
    """Render params so the Generate button owns its loading state.

    Returns the ``label``/``disabled`` pair for ``st.button``: while a run is
    in flight the button reads "Generating…" and is disabled (no second
    click, ever); otherwise it reads "Generate (Continuous)" and is enabled.
    """
    in_flight = is_in_flight(state)
    return {
        "label": "Generating…" if in_flight else "Generate (Continuous)",
        "disabled": in_flight,
    }
