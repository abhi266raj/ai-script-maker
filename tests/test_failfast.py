"""Fail-fast Stage 3 validation tests.

User requirement (2026-09-24): if 3.x.1 (Structure) fails, 3.x.2-3.x.5 must
NOT run -- they are recorded as "Skipped (<failed check> failed)", never
merely "Not reached". Retry refines the previous full draft using only the
first failure's exact feedback; re-validation then starts again at
Structure. Check order is the contract: Structure -> Tone+news (ONE AI
validator call: tone enforced, news advisory) -> Language -> Clothing -> SFX
(most failure-prone first). There is no separate final gate: when all
numbered checks pass, the narrations are fully validated. Every check is
labeled "AI validator" or "code validator" so the UI shows which checks
cost a model call.
"""
from types import SimpleNamespace

import pytest

import agents.dialogue_writer as dw
from agents.dialogue_writer import (
    DialogueNarrationAgent,
    run_validation_checks_fail_fast,
)
from core.dual_engine import ModelGenerationError

DRAFT = """SCRIPT 1:
BEAT 1:
Rakesh: "सुना तुमने? Ola Electric के board ने बड़ा फैसला लिया है।"
BEAT 2:
Meenal: "हाँ, मैंने भी यही सुना है।"
"""


def _make_specs(calls, results):
    """Build 3 fake check specs. results: name -> (problems, feedback)."""
    specs = []
    for name in ("A check", "B check", "C check"):
        def _run(n=name):
            calls.append(n)
            problems, fb = results[n]
            return {"problems": problems, "pass_output": f"{n} ok",
                    "feedback": fb}
        specs.append({"sub": str(len(specs) + 1), "name": name, "run": _run,
                      "input": f"input for {name}"})
    return specs


# ---------- helper unit tests ----------

def test_failfast_stops_at_first_failure():
    calls, events = [], []
    specs = _make_specs(calls, {
        "A check": (["boom"], "A fb"),
        "B check": ([], ""),
        "C check": ([], ""),
    })
    sub_checks, feedback = run_validation_checks_fail_fast(
        specs, stage_prefix="3", val_num=2,
        emit=lambda s, n, p, **kw: events.append((s, n, p, kw.get("status"))),
    )
    assert calls == ["A check"], f"B and C must never run, ran: {calls}"
    assert [c["stage"] for c in sub_checks] == ["3.2.1", "3.2.2", "3.2.3"]
    assert sub_checks[0]["passed"] is False
    assert sub_checks[0]["output"] == "boom"
    for c in sub_checks[1:]:
        assert c["passed"] is None
        assert c["skipped"] is True
        assert c["skipped_due_to"] == "3.2.1 A check"
        assert c["output"] == "Skipped (3.2.1 A check failed)"
    assert feedback == ["A fb"], "only the first failure's feedback is kept"
    statuses = [(s, st) for s, n, p, st in events if p == "complete"]
    assert ("3.2.1", "fail") in statuses
    assert ("3.2.2", "skipped") in statuses
    assert ("3.2.3", "skipped") in statuses


def test_failfast_middle_failure_skips_rest():
    calls = []
    specs = _make_specs(calls, {
        "A check": ([], ""),
        "B check": (["bad news"], "B fb"),
        "C check": ([], ""),
    })
    sub_checks, feedback = run_validation_checks_fail_fast(
        specs, stage_prefix="3", val_num=4)
    assert calls == ["A check", "B check"]
    assert [c["passed"] for c in sub_checks] == [True, False, None]
    assert sub_checks[2]["output"] == "Skipped (3.4.2 B check failed)"
    assert feedback == ["B fb"]


def test_failfast_all_pass_runs_in_exact_order():
    calls = []
    specs = _make_specs(calls, {
        "A check": ([], ""), "B check": ([], ""), "C check": ([], "")})
    sub_checks, feedback = run_validation_checks_fail_fast(
        specs, stage_prefix="3", val_num=2)
    assert calls == ["A check", "B check", "C check"]
    assert all(c["passed"] for c in sub_checks)
    assert [c["output"] for c in sub_checks] == ["A check ok", "B check ok", "C check ok"]
    assert feedback == []


def test_validator_label_propagates_to_sub_checks():
    specs = [
        {"sub": "1", "name": "AI-ish", "validator": "AI validator",
         "run": lambda: {"problems": [], "pass_output": "ok", "feedback": ""}},
        {"sub": "2", "name": "Code-ish", "validator": "code validator",
         "run": lambda: {"problems": ["x"], "pass_output": "", "feedback": "fb"}},
        {"sub": "3", "name": "Skipped-ish", "validator": "code validator",
         "run": lambda: {"problems": [], "pass_output": "ok", "feedback": ""}},
    ]
    sub_checks, _ = run_validation_checks_fail_fast(specs, stage_prefix="3", val_num=2)
    assert sub_checks[0]["validator"] == "AI validator"
    assert sub_checks[1]["validator"] == "code validator"
    # skipped checks keep their validator label too
    assert sub_checks[2]["validator"] == "code validator"
    assert sub_checks[2]["skipped"] is True


# ---------- Stage 3 integration tests ----------

def _agent():
    agent = DialogueNarrationAgent()
    agent.execute = lambda prompt, engine_mode=None: DRAFT  # model stub
    return agent


def _invoke(agent, **kw):
    items = [{"hook": "Ola board approves rights issue",
              "cta": "Follow for more", "angle": "news", "topic": "Ola"}]
    verification = SimpleNamespace(
        verified_facts=["Ola Electric board approves Rs 1500 crore rights issue"],
        physical_props=[], key_locations=[], core_conflict_or_irony="")
    chars = [SimpleNamespace(name="Rakesh", role_or_job="Anchor",
                             attire="Kurta", emotional_stance="Neutral"),
             SimpleNamespace(name="Meenal", role_or_job="Co-anchor",
                             attire="Saree", emotional_stance="Neutral")]
    events = []
    result = agent.write_dialogues_batch(
        news_input="Ola Electric rights issue",
        items=items,
        tone="funny",
        duration_sec=30,
        verification=verification,
        character_count=2,
        scene_style="Dialogue",
        finalized_characters=chars,
        on_substep=events.append,
        **kw,
    )
    return result, events


def _patch_validators(monkeypatch, order, struct=(),
                      tone_ok=True, tone_issue="not funny",
                      news_ok=True, news_reason="judge: NEWS_VERDICT=YES",
                      lang=(), clothing=(), sfx=()):
    """Patch the validators with spies.

    The AI side is ONE merged judge (ai_judge_script_quality) returning
    (tone_ok, tone_issue, news_ok, news_reason): tone is enforced, news is
    advisory-only and never fails the stage. struct/lang/clothing/sfx are
    code validators returning problem lists.
    """
    monkeypatch.setattr(
        dw, "validate_dialogue_structure",
        lambda sl, style, speakers: (order.append("structure"), list(struct))[1])
    monkeypatch.setattr(
        dw, "ai_judge_script_quality",
        lambda agent_self, scene_lines, news_topic, hook, tone, angle, engine_mode=None:
            (order.append("quality"),
             (tone_ok, "" if tone_ok else tone_issue, news_ok, news_reason))[1])
    monkeypatch.setattr(
        dw, "find_formal_hindi",
        lambda text: (order.append("language"), list(lang))[1])
    monkeypatch.setattr(
        dw, "validate_clothing_specificity",
        lambda chars: (order.append("clothing"), list(clothing))[1])
    monkeypatch.setattr(
        dw, "validate_sfx_tone_match",
        lambda sl, tone: (order.append("sfx"), list(sfx))[1])


def _val_step(agent):
    return next(s for s in agent.last_validation_steps if s["stage"] == "3.2")


def test_structure_failure_skips_rest(monkeypatch):
    order = []
    _patch_validators(monkeypatch, order, struct=["Script 1: bad structure"])
    agent = _agent()
    with pytest.raises(ModelGenerationError) as exc:
        _invoke(agent, _max_retries=0)
    # quality/language/clothing/sfx must NEVER have run
    assert order == ["structure"], f"later checks ran: {order}"
    assert "Structure check" in str(exc.value)
    step = _val_step(agent)
    subs = step["sub_checks"]
    assert [s["stage"] for s in subs] == ["3.2.1", "3.2.2", "3.2.3", "3.2.4", "3.2.5"]
    assert subs[0]["passed"] is False
    for s in subs[1:]:
        assert s["passed"] is None and s["skipped"] is True
    assert subs[1]["output"] == "Skipped (3.2.1 Structure check failed)"
    assert subs[1]["skipped_due_to"] == "3.2.1 Structure check"
    # failed-name reporting names ONLY the failed check, not skipped ones
    assert step["output"] == "Failed: Structure check"


def test_news_failure_is_advisory_never_retries(monkeypatch):
    # News coverage is advisory-only: even a NEWS_VERDICT=NO inside the merged
    # AI judge must NOT fail the stage, trigger a retry, or appear in retry
    # feedback. The verdict is surfaced in the 3.2.2 sub-check output instead.
    order = []
    _patch_validators(monkeypatch, order, news_ok=False,
                      news_reason="NEWS_VERDICT=NO — beats state no specific event")
    agent = _agent()
    orig = agent.write_dialogues_batch
    retry_kwargs = []

    def spy(*a, **k):
        retry_kwargs.append(k)
        return orig(*a, **k)

    agent.write_dialogues_batch = spy
    result, events = _invoke(agent, _max_retries=1)

    assert result, "advisory news failure must not fail the stage"
    assert len(retry_kwargs) == 1, "no retry on advisory news failure"
    # all five checks ran in contract order; none skipped
    assert order == ["structure", "quality", "language", "clothing", "sfx"], order
    step = _val_step(agent)
    subs = step["sub_checks"]
    assert [s["passed"] for s in subs] == [True] * 5
    # news verdict visible as advisory note inside the merged check's output
    assert "advisory, not blocking" in subs[1]["output"]
    assert "NEWS_VERDICT=NO" in subs[1]["output"]
    assert step["output"] == "All 5 checks passed"


def test_all_pass_runs_five_checks_in_exact_order(monkeypatch):
    order = []
    _patch_validators(monkeypatch, order)
    agent = _agent()
    result, events = _invoke(agent, _max_retries=0)
    assert result and len(result) == 1
    # numbered 3.2 checks run in exact contract order with exactly ONE AI
    # validator call; no separate final gate re-runs anything afterwards.
    assert order == ["structure", "quality", "language", "clothing", "sfx"], order
    step = _val_step(agent)
    assert step["output"] == "All 5 checks passed"
    assert all(s["passed"] for s in step["sub_checks"])
    # validator labels: exactly one AI validator, four code validators
    validators = [s["validator"] for s in step["sub_checks"]]
    assert validators == ["code validator", "AI validator", "code validator",
                          "code validator", "code validator"], validators


def test_tone_failure_skips_language_clothing_sfx(monkeypatch):
    order = []
    _patch_validators(monkeypatch, order, tone_ok=False)
    agent = _agent()
    with pytest.raises(ModelGenerationError):
        _invoke(agent, _max_retries=0)
    assert order == ["structure", "quality"], f"later checks must not run: {order}"
    subs = _val_step(agent)["sub_checks"]
    assert [s["passed"] for s in subs] == [True, False, None, None, None]
    assert subs[2]["output"] == "Skipped (3.2.2 Tone + news check failed)"
