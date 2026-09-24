"""Scene-style structural enforcement tests (all 8 styles).

Validates that get_dialogue_type_directive() pins a distinct structural mandate
for every supported scene style, and that validate_dialogue_structure()
deterministically checks parsed beats against the chosen style.
"""
import pytest

from agents.dialogue_writer import (
    get_dialogue_type_directive,
    validate_dialogue_structure,
    find_formal_hindi,
)
from core.models import CharacterProfile


def test_all_eight_styles_have_directives():
    styles = ["Dialogue", "Argument", "Speech", "Narration", "Interview",
              "Debate", "Monologue", "Lament"]
    for style in styles:
        d = get_dialogue_type_directive(style, 2, ["Ravi", "Priya"])
        assert d and len(d) > 40, f"empty directive for {style}"


def test_all_eight_styles_are_structurally_distinct():
    """No two styles may share the same directive text."""
    styles = ["Dialogue", "Argument", "Speech", "Narration", "Interview",
              "Debate", "Monologue", "Lament"]
    directives = {s: get_dialogue_type_directive(s, 2, ["Ravi", "Priya"]) for s in styles}
    assert len(set(directives.values())) == 8, "some styles share identical directives"


def test_dialogue_is_reactive_ping_pong():
    d = get_dialogue_type_directive("Dialogue", 2, ["Ravi", "Priya"])
    assert "NATURAL CONVERSATION" in d
    assert "reactive ping-pong" in d or "reacting" in d.lower()


def test_argument_is_heated_escalation():
    d = get_dialogue_type_directive("Argument", 2, ["Ravi", "Priya"])
    assert "HEATED ARGUMENT" in d
    assert "escalate" in d.lower()
    assert "react" in d.lower()


def test_interview_is_strict_qa():
    d = get_dialogue_type_directive("Interview", 2, ["Ravi", "Priya"])
    assert "INTERVIEW" in d
    assert "HOST" in d
    assert "GUEST" in d
    assert "RAVI" in d and "PRIYA" in d  # roles pinned to real names
    assert "never asks a question" in d.lower() or "never lectures" in d.lower()


def test_debate_has_opposing_sides_and_verdict():
    d = get_dialogue_type_directive("Debate", 2, ["Ravi", "Priya"])
    assert "DEBATE" in d
    assert "rebut" in d.lower()
    assert "verdict" in d.lower()
    assert "never swap" in d.lower() or "never agree" in d.lower()


def test_speech_is_public_address_to_crowd():
    d = get_dialogue_type_directive("Speech", 1, ["Ravi"])
    assert "SPEECH" in d
    assert "ONLY RAVI" in d
    assert "CROWD" in d or "audience" in d.lower()
    # Speech addresses a crowd, NOT the camera intimately
    assert "confidant" not in d.lower()


def test_monologue_is_intimate_direct_to_camera():
    d = get_dialogue_type_directive("Monologue", 1, ["Ravi"])
    assert "MONOLOGUE" in d
    assert "ONLY RAVI" in d
    assert "camera" in d.lower() or "lens" in d.lower()
    assert "confidant" in d.lower() or "personal" in d.lower()
    # Monologue is personal/intimate, NOT a public rally with a crowd
    assert "cheering crowd" not in d.lower()
    assert "applause" not in d.lower()


def test_narration_is_third_person_story():
    d = get_dialogue_type_directive("Narration", 1, ["Ravi"])
    assert "NARRATION" in d
    assert "ONLY RAVI" in d
    assert "third person" in d.lower() or "third-person" in d.lower()
    assert "story" in d.lower()
    # Narration describes events; it must NOT be direct-to-camera address
    assert "direct-to-camera" not in d.lower()


def test_lament_bans_jokes_and_laughter():
    d = get_dialogue_type_directive("Lament", 2, ["Ravi", "Priya"])
    assert "LAMENT" in d
    assert "NO jokes" in d
    assert "laughter" in d.lower()


def test_style_matching_is_case_insensitive():
    assert get_dialogue_type_directive("interview", 2) == get_dialogue_type_directive("Interview", 2)
    assert get_dialogue_type_directive("DEBATE", 2) == get_dialogue_type_directive("Debate", 2)
    assert get_dialogue_type_directive("NARRATION", 1) == get_dialogue_type_directive("Narration", 1)


def test_unknown_style_gets_safe_default():
    d = get_dialogue_type_directive("SomethingWeird", 2)
    assert "DIALOGUE TYPE" in d


# --- Structural validation ---

def test_validate_interview_enforces_qa():
    ok = [
        {"character": "Ravi", "dialogue": "Aapko kya lagta hai?"},
        {"character": "Priya", "dialogue": "Bahut badi khabar hai"},
    ]
    assert validate_dialogue_structure(ok, "Interview", ["Ravi", "Priya"]) == []
    bad = [
        {"character": "Ravi", "dialogue": "Yeh khabar hai"},
        {"character": "Priya", "dialogue": "Kya hua?"},
    ]
    issues = validate_dialogue_structure(bad, "Interview", ["Ravi", "Priya"])
    assert any("HOST question" in i for i in issues)
    assert any("GUEST answer" in i for i in issues)


def test_validate_solo_styles_reject_second_voice():
    for style in ("Speech", "Monologue", "Narration"):
        bad = [
            {"character": "Ravi", "dialogue": "Main bol raha hoon"},
            {"character": "Priya", "dialogue": "Main bhi bol rahi hoon"},
        ]
        issues = validate_dialogue_structure(bad, style, ["Ravi", "Priya"])
        assert any("only ONE voice" in i for i in issues), f"{style} allowed 2 speakers"
        ok = [{"character": "Ravi", "dialogue": "Main bol raha hoon"}]
        assert validate_dialogue_structure(ok, style, ["Ravi"]) == []


def test_validate_debate_requires_alternation():
    bad = [
        {"character": "Ravi", "dialogue": "Pehla point"},
        {"character": "Ravi", "dialogue": "Doosra point"},
    ]
    issues = validate_dialogue_structure(bad, "Debate", ["Ravi", "Priya"])
    assert any("alternation" in i for i in issues)


def test_validate_lament_rejects_laughter():
    for laugh in ("hahaha", "hehe", "\u0939\u093e\u0939\u093e"):
        bad = [{"character": "Ravi", "dialogue": f"Bahut dukh hua {laugh}"}]
        issues = validate_dialogue_structure(bad, "Lament", ["Ravi"])
        assert any("laughter" in i for i in issues), f"lament allowed {laugh!r}"
    ok = [{"character": "Ravi", "dialogue": "Bahut dukh ki khabar hai"}]
    assert validate_dialogue_structure(ok, "Lament", ["Ravi"]) == []


def test_validate_dialogue_style_is_freeform():
    lines = [
        {"character": "Ravi", "dialogue": "Kya haal hai?"},
        {"character": "Ravi", "dialogue": "Sab badhiya"},
    ]
    assert validate_dialogue_structure(lines, "Dialogue", ["Ravi", "Priya"]) == []


def test_validate_rejects_unknown_speaker():
    # Current contract: unknown speaker names are NOT errors -- the model is
    # allowed creative naming and new speakers are enriched downstream.
    # Every beat must still HAVE a speaker label.
    lines = [{"character": "Ajnabi", "dialogue": "Main kaun hoon"}]
    issues = validate_dialogue_structure(lines, "Argument", ["Ravi", "Priya"])
    assert issues == []
    bad = [{"character": "", "dialogue": "Main kaun hoon"}]
    issues = validate_dialogue_structure(bad, "Argument", ["Ravi", "Priya"])
    assert any("no speaker label" in i for i in issues)


# --- Formal Hindi detection ---

def test_find_formal_hindi_detects_shuddh():
    found = find_formal_hindi("\u0939\u093e\u0901, \u0905\u0927\u093f\u0915\u093e\u0930 \u0928\u093f\u0930\u094d\u0917\u092e \u0938\u0947 \u092e\u0902\u091c\u093c\u0942\u0930\u0940 \u092e\u093f\u0932\u0940\u0964")
    assert "\u0905\u0927\u093f\u0915\u093e\u0930 \u0928\u093f\u0930\u094d\u0917\u092e" in found


def test_find_formal_hindi_detects_passive_voice():
    found = find_formal_hindi("\u0918\u094b\u0937\u0923\u093e \u0915\u0940 \u0917\u0908 \u0915\u093f \u092a\u0948\u0938\u093e \u092e\u093f\u0932\u0947\u0917\u093e\u0964")
    assert found, "passive-voice bureaucratic Hindi not detected"


def test_find_formal_hindi_passes_common_hindi():
    assert find_formal_hindi("\u0939\u093e\u0901, \u0930\u093e\u0907\u091f\u094d\u0938 \u0907\u0936\u094d\u092f\u0942 \u0938\u0947 \u092e\u0902\u091c\u0942\u0930\u0940 \u092e\u093f\u0932\u0940\u0964") == []
    assert find_formal_hindi("") == []


# --- Mocked correction-path tests ---
# NOTE (fail-fast, 2026-09-24): the old per-check retry flags
# (_structure_fix_done / _hindi_fix_done) no longer exist. There is ONE
# combined retry carrying the exact failed draft plus ONLY the first
# failure's feedback; later checks are skipped, never run.

def test_structural_correction_receives_exact_failed_draft_once():
    """Fail-fast: a structure failure retries exactly once with previous_draft
    set to the exact failed raw_output and ONLY the structure feedback
    (news/tone/language never ran, so they contribute nothing)."""
    from unittest.mock import patch
    from agents import dialogue_writer as dw_mod

    # Interview violation: Guest asks a question (only Host may ask).
    failed_raw = (
        "SCRIPT 1:\n"
        "BEAT 1:\nCHARACTER: Host\nDIALOGUE: \"Welcome to the show?\"\n"
        "BEAT 2:\nCHARACTER: Guest\nDIALOGUE: \"Thanks, shall we begin?\"\n"
    )
    # Fixed version: Guest answers, does not ask.
    fixed_raw = (
        "SCRIPT 1:\n"
        "BEAT 1:\nCHARACTER: Host\nDIALOGUE: \"Welcome to the show?\"\n"
        "BEAT 2:\nCHARACTER: Guest\nDIALOGUE: \"Thanks, happy to be here.\"\n"
    )

    agent = dw_mod.dialogue_writer
    orig = dw_mod.DialogueNarrationAgent.write_dialogues_batch
    seen = []

    def spy(self, **kwargs):
        seen.append(kwargs)
        return orig(self, **kwargs)

    # Fail-fast: one combined retry (no per-check retry flags). The AI judges
    # would fail on the stubbed model output, so patch them to pass.
    with patch.object(dw_mod.DialogueNarrationAgent, "write_dialogues_batch", spy), \
         patch.object(agent, "execute", side_effect=[failed_raw, fixed_raw]), \
         patch.object(dw_mod, "ai_judge_news_coverage", return_value=(True, "mocked pass")), \
         patch.object(dw_mod, "ai_judge_tone_compliance", return_value=(True, "")), \
         patch.object(dw_mod, "find_formal_hindi", return_value=[]):
        result = agent.write_dialogues_batch(
            news_input="talk show episode", items=[{"angle": "Test", "hook": "Welcome to the show", "cta": "Test CTA"}],
            tone="Neutral", duration_sec=20,
            verification=None, character_count=2, scene_style="Interview",
            _max_retries=1,
        )
    assert len(seen) == 2, f"expected exactly 1 retry, got {len(seen) - 1}"
    retry_kwargs = seen[1]
    assert retry_kwargs["previous_draft"] == failed_raw, "retry must carry the exact failed draft"
    assert "STRUCTURE FIX" in retry_kwargs["feedback"]
    # Fail-fast: news/tone/language never ran before the structure failure,
    # so the retry feedback carries ONLY the structure fix.
    assert "NEWS COVERAGE FIX" not in retry_kwargs["feedback"]
    assert "TONE CORRECTION" not in retry_kwargs["feedback"]
    assert result and len(result) == 1


def test_hindi_correction_receives_exact_draft_and_flagged_tokens():
    """Fail-fast: the language retry carries the exact failed draft and names
    ONLY the flagged formal tokens; it must run only once (no blind substitution)."""
    from unittest.mock import patch
    from agents import dialogue_writer as dw_mod

    failed_raw = (
        "SCRIPT 1:\n"
        "BEAT 1:\nCHARACTER: Ravi\nDIALOGUE: \"हाँ, अधिकार निर्गम से मंजूरी मिली।\"\n"
    )
    fixed_raw = (
        "SCRIPT 1:\n"
        "BEAT 1:\nCHARACTER: Ravi\nDIALOGUE: \"हाँ, राइट्स इश्यू से मंजूरी मिली।\"\n"
    )

    agent = dw_mod.dialogue_writer
    orig = dw_mod.DialogueNarrationAgent.write_dialogues_batch
    seen = []

    def spy(self, **kwargs):
        seen.append(kwargs)
        return orig(self, **kwargs)

    # Fail-fast: language is check 3.x.4, so structure/news/tone must pass
    # first; the AI judges would fail on the stubbed model output, so patch them.
    with patch.object(dw_mod.DialogueNarrationAgent, "write_dialogues_batch", spy), \
         patch.object(agent, "execute", side_effect=[failed_raw, fixed_raw]), \
         patch.object(dw_mod, "ai_judge_news_coverage", return_value=(True, "mocked pass")), \
         patch.object(dw_mod, "ai_judge_tone_compliance", return_value=(True, "")):
        result = agent.write_dialogues_batch(
            news_input="rights issue approval", items=[{"angle": "Test", "hook": "राइट्स इश्यू को मंजूरी", "cta": "Test CTA"}],
            tone="Neutral", duration_sec=20,
            verification=None, character_count=1, scene_style="Monologue",
            finalized_characters=[CharacterProfile(name="Ravi", role_or_job="Anchor")],
            _max_retries=1,
        )
    assert len(seen) == 2, f"expected exactly 1 hindi retry, got {len(seen) - 1}"
    retry_kwargs = seen[1]
    assert retry_kwargs["previous_draft"] == failed_raw
    assert "COMMON-HINDI FIX" in retry_kwargs["feedback"]
    assert "अधिकार निर्गम" in retry_kwargs["feedback"], "feedback must name the flagged tokens"
    assert "STRUCTURE FIX" not in retry_kwargs["feedback"]
    assert result and len(result) == 1
    # The detector flags tokens; it never rewrites the input (no blind substitution).
    original = "प्रेम ने कहा कि युद्ध होगा।"
    assert dw_mod.find_formal_hindi(original) == dw_mod.find_formal_hindi(original)
