"""Emotion system (issue #354).

Replaces the legacy 'Vibe' concept with 8 frozen genuine human emotions that
drive dialogue writing, screenplay delivery cues, and teleprompter direction.

Covers:
- frozen palette: exactly 8 emotions, frozen order, Hindi names, delivery
  directions, news triggers;
- get_emotion_instruction: directive carries the feeling + delivery + derived
  angle; fails loudly on unknown/empty emotions (no invented directives);
- emotion_to_angle: frozen derivation; fails loudly on unknown emotions;
- build_tailored_instruction(emotion=...): emotion directive present; fails
  loudly with no emotion and on legacy vibe values (no artificial mapping);
- SceneItem.emotion: scene_director stamps the frozen emotion per beat and
  fails loudly on non-palette tones;
- screenplay formatter: renders `CHARACTER (Emotion): "..."` delivery cues;
  fails loudly when a beat has no emotion;
- teleprompter: `[CHARACTER | Feeling: Emotion — Part N (ts)]` headers;
  fails loudly when a beat has no emotion;
- 70% compliance gate language: the dialogue prompt + AI judge name the
  required emotion with its delivery (no vague 'tone').

Run: python -m pytest tests/test_emotion_system_354.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.constants import (
    ALL_EMOTIONS,
    EMOTION_HINDI,
    EMOTION_DELIVERY,
    EMOTION_TRIGGERS,
    EMOTION_TO_ANGLE,
    emotion_to_angle,
    EMOTION_JOKE,
    EMOTION_SORROW,
    EMOTION_PRIDE,
)
from core.prompt_matrix import (
    EMOTION_INSTRUCTIONS,
    get_emotion_instruction,
    build_tailored_instruction,
)
from core.models import ReelScript, SceneItem
from core.screenplay_formatter import (
    format_industry_screenplay,
    format_teleprompter_text,
)


def _script_with_emotion(emotion):
    return ReelScript(
        id=1,
        title="Emotion reel",
        angle="Funny & Relatable",
        hook_hindi="सुनो!",
        narration_hindi="सुनो!",
        call_to_action="",
        scenes=[
            SceneItem(
                scene_number=1,
                character="Priya",
                dialogue="ये क्या हो रहा है!",
                timestamp="0:00 - 0:03",
                visual_b_roll="Priya stares at her phone in disbelief.",
                on_screen_text="",
                audio_sfx="Gasp",
                emotion=emotion,
            ),
            SceneItem(
                scene_number=2,
                character="Rohan",
                dialogue="सच में यकीन नहीं हो रहा!",
                timestamp="0:03 - 0:06",
                visual_b_roll="Rohan drops his chai in shock.",
                on_screen_text="",
                audio_sfx="Clatter",
                emotion=emotion,
            ),
        ],
        word_count=10,
        max_words=20,
        target_duration_sec=10,
    )


# ---------------------------------------------------------------------------
# Frozen palette
# ---------------------------------------------------------------------------

def test_frozen_palette_exact_and_ordered():
    assert ALL_EMOTIONS == [
        "Anger", "Shock", "Joke", "Sorrow",
        "Curiosity", "Pride", "Fear", "Hope",
    ]


def test_palette_has_hindi_delivery_triggers():
    for emotion in ALL_EMOTIONS:
        assert EMOTION_HINDI[emotion], f"{emotion} missing Hindi name"
        assert EMOTION_DELIVERY[emotion], f"{emotion} missing delivery"
        assert EMOTION_TRIGGERS[emotion], f"{emotion} missing triggers"


def test_no_composite_marketing_phrases_in_palette():
    for emotion in ALL_EMOTIONS:
        assert "&" not in emotion
        assert len(emotion.split()) == 1


# ---------------------------------------------------------------------------
# get_emotion_instruction / emotion_to_angle
# ---------------------------------------------------------------------------

def test_emotion_instruction_carries_feeling_delivery_and_angle():
    directive = get_emotion_instruction(EMOTION_PRIDE)
    assert "EMOTION DIRECTIVE (Pride" in directive
    assert "गर्व" in directive
    assert "confident, celebratory, inspiring" in directive
    # derived angle merged in (same as the old vibe system)
    assert "Inspirational & Uplifting" in directive
    assert "70%" in directive
    assert "ZERO beats" in directive


def test_emotion_instruction_covers_all_palette():
    assert set(EMOTION_INSTRUCTIONS) == set(ALL_EMOTIONS)


def test_emotion_instruction_fails_loud():
    with pytest.raises(ValueError):
        get_emotion_instruction("Desi Swag")
    with pytest.raises(ValueError):
        get_emotion_instruction("")
    with pytest.raises(ValueError):
        get_emotion_instruction("Excited")  # not frozen


def test_emotion_to_angle_mapping():
    assert emotion_to_angle("Joke") == "Funny & Relatable"
    assert emotion_to_angle("Sorrow") == "Tragic & Heartbreaking"
    assert emotion_to_angle("Curiosity") == "Investigative Deep-Dive"
    assert emotion_to_angle("Pride") == "Inspirational & Uplifting"
    assert set(EMOTION_TO_ANGLE) == set(ALL_EMOTIONS)


def test_emotion_to_angle_fails_loud():
    with pytest.raises(ValueError):
        emotion_to_angle("Desi Swag")


# ---------------------------------------------------------------------------
# build_tailored_instruction
# ---------------------------------------------------------------------------

def test_tailored_instruction_uses_emotion():
    inst = build_tailored_instruction(
        topic="ISRO Gaganyaan launch",
        duration_sec=20,
        emotion="Pride",
        scene_style="Narration",
        character_count=1,
    )
    assert "EMOTION DIRECTIVE (Pride" in inst
    assert "ISRO Gaganyaan launch" in inst


def test_tailored_instruction_rejects_legacy_vibe_no_mapping():
    # #354: no artificial 1-to-1 legacy mapping — old vibe values fail loudly.
    with pytest.raises(ValueError):
        build_tailored_instruction(
            topic="ISRO Gaganyaan launch",
            duration_sec=20,
            emotion="Desi Swag",
            scene_style="Narration",
            character_count=1,
        )


def test_tailored_instruction_requires_emotion():
    with pytest.raises(ValueError):
        build_tailored_instruction(
            topic="ISRO Gaganyaan launch",
            duration_sec=20,
            scene_style="Narration",
            character_count=1,
        )


# ---------------------------------------------------------------------------
# SceneItem.emotion stamping (scene_director validation)
# ---------------------------------------------------------------------------

def test_scene_director_rejects_non_palette_tone():
    from agents.scene_director import scene_director
    from core.dual_engine import ModelGenerationError
    with pytest.raises(ModelGenerationError):
        scene_director.direct_scenes(
            news_topic="test",
            hook="hook",
            narration="narration",
            duration_sec=10,
            tone="Desi Swag",  # legacy vibe — not a frozen emotion
        )


# ---------------------------------------------------------------------------
# Screenplay delivery cues
# ---------------------------------------------------------------------------

def test_screenplay_renders_emotion_delivery_cues():
    formatted = format_industry_screenplay(_script_with_emotion("Shock"))
    assert 'PRIYA (Shock): "ये क्या हो रहा है!"' in formatted
    assert 'ROHAN (Shock): "सच में यकीन नहीं हो रहा!"' in formatted


def test_screenplay_fails_loud_without_emotion():
    script = _script_with_emotion("Shock")
    script.scenes[0].emotion = ""
    with pytest.raises(ValueError, match="no emotion"):
        format_industry_screenplay(script)


# ---------------------------------------------------------------------------
# Teleprompter feeling headers
# ---------------------------------------------------------------------------

def test_teleprompter_includes_feeling():
    text = format_teleprompter_text(_script_with_emotion("Anger"))
    assert "[PRIYA | Feeling: Anger — Part 1 (0:00 - 0:03)]" in text
    assert "[ROHAN | Feeling: Anger — Part 2 (0:03 - 0:06)]" in text


def test_teleprompter_fails_loud_without_emotion():
    script = _script_with_emotion("Anger")
    script.scenes[1].emotion = ""
    with pytest.raises(ValueError, match="no emotion"):
        format_teleprompter_text(script)


# ---------------------------------------------------------------------------
# 70% compliance gate names the emotion (not a vague 'tone')
# ---------------------------------------------------------------------------

def test_dialogue_prompt_names_emotion_compliance():
    src = (Path(__file__).resolve().parent.parent
           / "prompts" / "dialogue_writer" / "write_dialogue_batch.md").read_text(encoding="utf-8")
    assert "EMOTION COMPLIANCE" in src
    assert "TONE COMPLIANCE" not in src
    assert "written to be SPOKEN with this feeling" in src


def test_ai_judge_prompt_names_emotion_with_delivery():
    from agents import dialogue_writer
    ctx = dialogue_writer._emotion_judge_context("Sorrow")
    assert "REQUIRED EMOTION: Sorrow" in ctx
    assert "शोक" in ctx
    assert "quiet grief, respectful restraint, somber pauses" in ctx
