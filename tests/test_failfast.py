"""Fail-fast Stage 3 validation tests.

User requirement (2026-09-24): if 3.x.1 (Structure) fails, 3.x.2-3.x.4 must
NOT run -- they are recorded as "Skipped (<failed check> failed)", never
merely "Not reached". Retry refines the previous full draft using only the
first failure's exact feedback; re-validation then starts again at
Structure. Check order is the contract: Structure -> News -> Tone ->
Language (most failure-prone first).
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


def _patch_validators(monkeypatch, order, struct=(), news_ok=True,
                      news_reason="judge: VERDICT=YES — mocked pass",
                      tone_ok=True, lang=()):
    """Patch the 4 module-level validators with spies.

    struct/lang: problems to return. news_ok/news_reason: the AI news
    judge's verdict (FR-16.1: judge-only news validation).
    tone_ok: AI tone judge verdict.
    """
    monkeypatch.setattr(
        dw, "validate_dialogue_structure",
        lambda sl, style, speakers: (order.append("structure"), list(struct))[1])
    monkeypatch.setattr(
        dw, "ai_judge_news_coverage",
        lambda agent_self, scene_lines, news_topic, hook, engine_mode=None:
            (order.append("news-judge"), (news_ok, news_reason))[1])
    monkeypatch.setattr(
        dw, "ai_judge_tone_compliance",
        lambda self, sl, tone, angle, engine_mode=None:
            (order.append("tone"), (tone_ok, "" if tone_ok else "not funny"))[1])
    monkeypatch.setattr(
        dw, "find_formal_hindi",
        lambda text: (order.append("language"), list(lang))[1])


def _val_step(agent):
    return next(s for s in agent.last_validation_steps if s["stage"] == "3.2")


def test_structure_failure_skips_news_tone_language(monkeypatch):
    order = []
    _patch_validators(monkeypatch, order, struct=["Script 1: bad structure"])
    agent = _agent()
    with pytest.raises(ModelGenerationError) as exc:
        _invoke(agent, _max_retries=0)
    # news/tone/language must NEVER have run
    assert order == ["structure"], f"later checks ran: {order}"
    assert "Structure check" in str(exc.value)
    step = _val_step(agent)
    subs = step["sub_checks"]
    assert [s["stage"] for s in subs] == ["3.2.1", "3.2.2", "3.2.3", "3.2.4"]
    assert subs[0]["passed"] is False
    for s in subs[1:]:
        assert s["passed"] is None and s["skipped"] is True
    assert subs[1]["output"] == "Skipped (3.2.1 Structure check failed)"
    assert subs[1]["skipped_due_to"] == "3.2.1 Structure check"
    # failed-name reporting names ONLY the failed check, not skipped ones
    assert step["output"] == "Failed: Structure check"


def test_news_failure_skips_tone_language_and_retries_with_first_error_only(monkeypatch):
    order = []
    judge_calls = {"n": 0}

    def fake_judge(agent_self, scene_lines, news_topic, hook, engine_mode=None):
        # FR-16.1: the AI judge is the sole news validator.
        order.append("news-judge")
        judge_calls["n"] += 1
        if judge_calls["n"] == 1:
            return False, "VERDICT=NO — beats state no specific event"
        return True, "VERDICT=YES — mocked pass"

    monkeypatch.setattr(dw, "validate_dialogue_structure",
                        lambda sl, style, speakers: (order.append("structure"), [])[1])
    monkeypatch.setattr(dw, "ai_judge_news_coverage", fake_judge)
    monkeypatch.setattr(dw, "ai_judge_tone_compliance",
                        lambda self, sl, tone, angle, engine_mode=None:
                            (order.append("tone"), (True, ""))[1])
    monkeypatch.setattr(dw, "find_formal_hindi",
                        lambda text: (order.append("language"), [])[1])

    agent = _agent()
    orig = agent.write_dialogues_batch
    retry_kwargs = []

    def spy(*a, **k):
        retry_kwargs.append(k)
        return orig(*a, **k)

    agent.write_dialogues_batch = spy
    result, events = _invoke(agent, _max_retries=1)

    assert result, "retry should succeed once news is fixed"
    # Fail-fast in round 1: structure -> news-judge(fail); tone/language never ran.
    assert order[:2] == ["structure", "news-judge"], order
    # Round 2 re-validation restarts at Structure and runs all four in order,
    # followed by the final gate's own re-run (structure, language, news, tone).
    assert order[2:6] == ["structure", "news-judge", "tone", "language"], order
    assert order[6:] == ["structure", "language", "news-judge", "tone"], order
    # retry refined the previous full draft with ONLY the first error
    assert len(retry_kwargs) == 2
    assert retry_kwargs[1]["previous_draft"] == DRAFT
    assert "NEWS COVERAGE FIX" in retry_kwargs[1]["feedback"]
    assert "TONE CORRECTION" not in retry_kwargs[1]["feedback"]
    assert "COMMON-HINDI FIX" not in retry_kwargs[1]["feedback"]
    # live events show skipped substeps for round 1
    skipped = [e for e in events
               if e.get("phase") == "complete" and e.get("status") == "skipped"]
    assert {e["substep"] for e in skipped} >= {"3.2.3", "3.2.4"}


def test_all_pass_runs_four_checks_in_exact_order(monkeypatch):
    order = []
    _patch_validators(monkeypatch, order)
    agent = _agent()
    result, events = _invoke(agent, _max_retries=0)
    assert result and len(result) == 1
    # numbered 3.2 checks run in exact contract order (news = AI judge, FR-16.1)...
    assert order[:4] == ["structure", "news-judge", "tone", "language"], order
    # ...then the pre-existing final gate double-checks (structure, language, news, tone)
    assert order[4:] == ["structure", "language", "news-judge", "tone"], order
    step = _val_step(agent)
    assert step["output"] == "All 4 checks passed"
    assert all(s["passed"] for s in step["sub_checks"])


def test_tone_failure_skips_language_only(monkeypatch):
    order = []
    _patch_validators(monkeypatch, order, tone_ok=False)
    agent = _agent()
    with pytest.raises(ModelGenerationError):
        _invoke(agent, _max_retries=0)
    assert order == ["structure", "news-judge", "tone"], f"language must not run: {order}"
    subs = _val_step(agent)["sub_checks"]
    assert [s["passed"] for s in subs] == [True, True, False, None]
    assert subs[3]["output"] == "Skipped (3.2.3 Tone check failed)"
