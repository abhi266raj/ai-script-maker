"""resume_stream tests (failure recovery: skip stage / retry stage).

Every pipeline failure must offer Skip stage, Retry stage, Retry fresh and
Stop. Skip/Retry-stage in continuous mode resume the pipeline mid-flight via
``ReelWorkflow.resume_stream`` instead of restarting from stage 1. These
tests pin the resume event protocol: stage-start events, live substep
events, stage-complete events carrying the state, the final completed event,
and fail-loud rejection of an invalid resume stage.

Run: python3 -m pytest tests/test_workflow_resume.py -v
"""

import os
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest

import core.workflow as wf_mod
from core.workflow import ReelWorkflow


# ---------------------------------------------------------------- helpers

def _stub_coordinator(monkeypatch, calls):
    """Replace the chief-editor singleton with a stub whose stages are fake.

    Each fake stage appends its number to ``calls``, emits one substep
    event, and returns the state with a ``stages_done`` trail.
    """
    def _pump(stage_fn, stage_num, *args, **kwargs):
        yield {"type": "substep", "step": stage_num, "substep": f"{stage_num}.1",
               "phase": "complete", "name": f"fake {stage_num}"}
        state = args[0]
        calls.append(stage_num)
        trail = list(state.get("stages_done", [])) + [stage_num]
        outcome = dict(state)
        outcome["stages_done"] = trail
        return outcome

    stub = SimpleNamespace(
        name="Stub Chief",
        icon="🧪",
        _pump_stage_with_substeps=_pump,
        execute_stage_2=object(),
        execute_stage_3=object(),
        execute_stage_4=object(),
        execute_stage_5=object(),
        execute_stage_6=object(),
    )
    monkeypatch.setattr(wf_mod, "chief_editor_coordinator", stub)
    monkeypatch.setattr(wf_mod.dual_engine, "validate_mode", lambda mode: None)
    return stub


def _drain(gen):
    """Collect all yielded events; return (events, generator return value)."""
    events = []
    try:
        while True:
            events.append(next(gen))
    except StopIteration as stop:
        return events, stop.value


# ---------------------------------------------------------------- tests

def test_resume_replays_stages_in_order_with_protocol_events(monkeypatch):
    calls = []
    _stub_coordinator(monkeypatch, calls)
    wf = ReelWorkflow()
    state = {"stages_done": [1, 2, 3], "batch_result": "RESULT"}

    gen = wf.resume_stream(state=state, from_stage=4, engine_mode="x")
    events, returned = _drain(gen)

    # Stages replayed in order.
    assert calls == [4, 5, 6]
    # Generator returns the batch result like run_stream does.
    assert returned == "RESULT"

    # Event protocol: per stage -> start (data None), substep, complete
    # (data carries state); then the final completed event.
    kinds = [
        ("start", e["step"]) if e.get("data") is None and e.get("type") != "substep"
        else ("substep", e["step"]) if e.get("type") == "substep"
        else ("complete", e["step"]) if not e.get("completed")
        else ("final", e["step"])
        for e in events
    ]
    assert kinds == [
        ("start", 4), ("substep", 4), ("complete", 4),
        ("start", 5), ("substep", 5), ("complete", 5),
        ("start", 6), ("substep", 6), ("complete", 6),
        ("final", 6),
    ]
    final = events[-1]
    assert final["completed"] is True
    assert final["data"]["batch_result"] == "RESULT"
    assert final["total_steps"] == 6


def test_resume_threads_state_through_stages(monkeypatch):
    calls = []
    _stub_coordinator(monkeypatch, calls)
    wf = ReelWorkflow()
    state = {"stages_done": [1, 2, 3, 4], "batch_result": "R"}

    gen = wf.resume_stream(state=state, from_stage=5, engine_mode="x")
    events, _ = _drain(gen)

    # The stage-5 complete event carries the state that stage 6 will build
    # on — the trail accumulates across the resumed stages.
    complete_5 = next(e for e in events
                      if e.get("step") == 5 and e.get("data") is not None
                      and not e.get("completed"))
    assert complete_5["data"]["stages_done"] == [1, 2, 3, 4, 5]
    complete_6 = next(e for e in events
                      if e.get("step") == 6 and e.get("data") is not None
                      and not e.get("completed"))
    assert complete_6["data"]["stages_done"] == [1, 2, 3, 4, 5, 6]


def test_resume_rejects_stage_1_and_out_of_range(monkeypatch):
    calls = []
    _stub_coordinator(monkeypatch, calls)
    wf = ReelWorkflow()
    # Stage 1 builds the state from raw inputs — it cannot be resumed.
    with pytest.raises(ValueError, match="Cannot resume from stage 1"):
        _drain(wf.resume_stream(state={}, from_stage=1, engine_mode="x"))
    with pytest.raises(ValueError, match="Cannot resume from stage 7"):
        _drain(wf.resume_stream(state={}, from_stage=7, engine_mode="x"))
    assert calls == []


def test_resume_from_6_runs_only_final_stage(monkeypatch):
    calls = []
    _stub_coordinator(monkeypatch, calls)
    wf = ReelWorkflow()
    state = {"stages_done": [1, 2, 3, 4, 5], "batch_result": "R"}

    events, returned = _drain(wf.resume_stream(state=state, from_stage=6, engine_mode="x"))

    assert calls == [6]
    assert returned == "R"
    final = events[-1]
    assert final["completed"] is True and final["step"] == 6
