"""News-intelligibility + fail-loud Stage 3 tests.

Stage 3 validation makes exactly ONE AI validator call per script per attempt:
`ai_judge_script_quality` judges BOTH tone compliance (enforced) and news
coverage (advisory) in a single model call and returns a split verdict.
The other checks (structure, language, clothing, SFX) are code validators.

News coverage is validated by the AI judge ONLY (FR-16.1) — no
token/regex matching. The judge reads ONLY the short news title /
basic news content + the dialogue (never the full verified-facts list)
and verdicts whether the viewer can understand what happened.

The judge's verdicts are surfaced in the 3.2.2 output (FR-16.2).
A judge engine error renders as a visible warning — never a silent
pass or silent fail.

Regression tests for the user-reported defects:
1. ai_judge_script_quality(): one call, split (tone_ok, tone_issue, news_ok, news_reason) verdict.
2. Judge input contains no verified facts.
3. Judge engine error -> visible warning with error detail.
4. Stage 3 must FAIL WITH ERROR, never fall silently:
   - model exception -> ModelGenerationError (no silent empty-output fallback)
   - unparseable model output -> ModelGenerationError (no silent synthetic scenes)
   - enforced tone verdict still failing after retries -> ModelGenerationError
   - each preview script is checked against ITS OWN hook (multi-preview batches)
"""
import inspect

import pytest

from unittest.mock import patch

from agents import dialogue_writer as dw_mod
from agents.dialogue_writer import ai_judge_news_coverage
from core.dual_engine import ModelGenerationError

TOPIC = "Ola Electric rights issue"
HOOK = "Ola board approves rights issue"

# The exact vague beats from the user-reported bad output.
VAGUE_BEATS = [
    {"scene_number": 1, "character": "Rakesh",
     "dialogue": "भाई ज़रा इधर देखो, आज अचानक हर तरफ इतनी हलचल क्यों मची हुई है?"},
    {"scene_number": 2, "character": "Meenal",
     "dialogue": "अब सबकी नज़र इस पर है कि इस खबर का असली असर किस पर पड़ेगा!"},
]

FACTUAL_BEATS = [
    {"scene_number": 1, "character": "Rakesh",
     "dialogue": "सुना तुमने? Ola Electric के board ने 1500 करोड़ के rights issue को मंज़ूरी दे दी है।"},
    {"scene_number": 2, "character": "Meenal",
     "dialogue": "हाँ, और announcement के बाद share price 4 percent गिर भी गया — पैसा battery plant में लगेगा।"},
]


class _FakeJudgeAgent:
    """Minimal stand-in exposing execute() for ai_judge_news_coverage."""

    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.prompts = []

    def execute(self, prompt, engine_mode=None):
        self.prompts.append(prompt)
        if self.exc is not None:
            raise self.exc
        return self.response


def test_judge_passes_factual_dialogue_and_surfaces_reason():
    """FR-16.2: VERDICT + REASON are returned so the UI can surface them."""
    agent = _FakeJudgeAgent(
        "VERDICT: YES\n"
        "REASON: The dialogue clearly states Ola Electric's board approved a rights issue."
    )
    ok, reason = ai_judge_news_coverage(agent, FACTUAL_BEATS, TOPIC, HOOK)
    assert ok is True
    assert "YES" in reason
    assert "rights issue" in reason


def test_judge_fails_vague_dialogue_and_surfaces_reason():
    agent = _FakeJudgeAgent(
        "VERDICT: NO\n"
        "REASON: The beats are generic filler with no specific event, company, or numbers."
    )
    ok, reason = ai_judge_news_coverage(agent, VAGUE_BEATS, TOPIC, HOOK)
    assert ok is False
    assert "NO" in reason
    assert "generic" in reason


def test_judge_never_receives_verified_facts():
    """FR-16.2: judge input is news title + dialogue only — no facts list."""
    assert "verified_facts" not in inspect.signature(ai_judge_news_coverage).parameters
    agent = _FakeJudgeAgent("VERDICT: YES\nREASON: fine")
    ai_judge_news_coverage(agent, FACTUAL_BEATS, TOPIC, HOOK)
    prompt = agent.prompts[0]
    assert TOPIC in prompt
    assert "VERIFIED FACTS" not in prompt


def test_judge_engine_error_is_visible_warning_not_silent():
    """FR-16.2: engine error -> visible warning, never silent pass/fail."""
    agent = _FakeJudgeAgent(exc=RuntimeError("engine exploded"))
    ok, reason = ai_judge_news_coverage(agent, FACTUAL_BEATS, TOPIC, HOOK)
    assert ok is False
    assert "⚠️" in reason
    assert "engine exploded" in reason
    assert "RuntimeError" in reason


# --- Fail-loud: model exception must raise, never silently substitute ---

def _call(items=None, **kw):
    base = dict(
        news_input=TOPIC,
        items=items or [{"angle": "Test", "hook": HOOK, "cta": "Follow!"}],
        tone="Neutral",
        duration_sec=20,
        verification=None,
        character_count=2,
        scene_style="Dialogue",
    )
    base.update(kw)
    return dw_mod.dialogue_writer.write_dialogues_batch(**base)


def test_model_exception_raises_not_silent():
    """A model/engine failure must surface as an error, not silent output."""
    with patch.object(dw_mod.dialogue_writer, "execute",
                      side_effect=RuntimeError("engine exploded")):
        with pytest.raises(ModelGenerationError) as exc:
            _call()
    assert "Stage 3" in str(exc.value)


def test_unparseable_output_raises():
    """Model output with no usable dialogue must fail loudly, not fall back
    to silent synthetic scenes."""
    garbage = "sorry, I cannot comply with that request right now"
    with patch.object(dw_mod.dialogue_writer, "execute", return_value=garbage):
        with pytest.raises(ModelGenerationError) as exc:
            _call()
    assert "no usable dialogue" in str(exc.value)
    # The raw output is attached for debugging.
    assert exc.value.partial_output == garbage


def test_empty_model_output_raises():
    with patch.object(dw_mod.dialogue_writer, "execute", return_value="   "):
        with pytest.raises(ModelGenerationError):
            _call()


def test_tone_judge_still_failing_raises():
    """If the ENFORCED tone verdict keeps failing, the stage must fail with
    error (surfacing the judge's reason), not ship the broken output.
    (News is advisory-only: a failing news verdict never fails the stage.)"""
    vague_raw = (
        "SCRIPT 1:\n"
        "BEAT 1:\nCHARACTER: Rakesh\nDIALOGUE: \"भाई ज़रा इधर देखो, आज अचानक हर तरफ इतनी हलचल क्यों मची हुई है?\"\n"
        "BEAT 2:\nCHARACTER: Meenal\nDIALOGUE: \"अब सबकी नज़र इस पर है कि इस खबर का असली असर किस पर पड़ेगा!\"\n"
    )
    with patch.object(dw_mod.dialogue_writer, "execute", return_value=vague_raw), \
         patch.object(dw_mod, "ai_judge_script_quality",
                      return_value=(False, "TONE_ISSUE: mocked not funny", True, "mocked news pass")):
        with pytest.raises(ModelGenerationError) as exc:
            _call()
    assert "validation failed" in str(exc.value)
    assert "tone + news check" in str(exc.value).lower()
    # The judge's reason is surfaced, not hidden.
    assert "mocked not funny" in str(exc.value)


def test_judge_engine_error_surfaces_warning_in_failure():
    """A judge engine error must surface as a visible warning in the stage
    failure — the user sees it and decides whether to retry or accept."""
    vague_raw = (
        "SCRIPT 1:\n"
        "BEAT 1:\nCHARACTER: Rakesh\nDIALOGUE: \"भाई ज़रा इधर देखो, आज अचानक हर तरफ इतनी हलचल क्यों मची हुई है?\"\n"
        "BEAT 2:\nCHARACTER: Meenal\nDIALOGUE: \"अब सबकी नज़र इस पर है कि इस खबर का असली असर किस पर पड़ेगा!\"\n"
    )

    def _execute(prompt, engine_mode=None):
        # Generation prompts return the draft; the merged quality-judge
        # prompt raises so the judge's own engine-error path is exercised.
        if "TONE_VERDICT" in prompt:
            raise RuntimeError("boom")
        return vague_raw

    with patch.object(dw_mod.dialogue_writer, "execute", side_effect=_execute):
        with pytest.raises(ModelGenerationError) as exc:
            _call()
    assert "⚠️" in str(exc.value)


def test_each_preview_checked_against_own_hook():
    """Multi-preview: script 2 must be validated against ITS OWN hook, not
    script 1's."""
    per_item_hooks = []

    def spy(agent, scene_lines, news_topic, hook, tone, angle, engine_mode="first_local_then_agy"):
        per_item_hooks.append(hook)
        return True, "", True, "AI judge: NEWS_VERDICT=YES — mocked pass"

    good_raw = (
        "SCRIPT 1:\n"
        "BEAT 1:\nCHARACTER: Rakesh\nDIALOGUE: \"सुना? Ola board ने rights issue को मंज़ूरी दे दी।\"\n"
        "SCRIPT 2:\n"
        "BEAT 1:\nCHARACTER: Rakesh\nDIALOGUE: \"सुना? Zomato ने नया delivery fee लागू कर दिया।\"\n"
    )
    items = [
        {"angle": "A", "hook": "Ola board approves rights issue", "cta": "Follow!"},
        {"angle": "B", "hook": "Zomato introduces new delivery fee", "cta": "Follow!"},
    ]
    with patch.object(dw_mod.dialogue_writer, "execute", return_value=good_raw), \
         patch.object(dw_mod, "ai_judge_script_quality", side_effect=spy):
        result = _call(items=items, news_input="Ola rights issue; Zomato delivery fee")
    assert len(result) == 2
    assert per_item_hooks, "quality validation never ran"
    assert any("Ola" in h for h in per_item_hooks), per_item_hooks
    assert any("Zomato" in h for h in per_item_hooks), per_item_hooks
    first_two = per_item_hooks[:2]
    assert "Ola" in first_two[0] and "Zomato" in first_two[1], first_two
