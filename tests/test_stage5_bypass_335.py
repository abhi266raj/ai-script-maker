"""Stage 5 no-facts bypass tests (issue #335).

The video-prompt gate refuses to generate when Stage 1 produced no verified
facts. #335 requires a bypass option on this failure: an explicit user
bypass must let generation proceed loudly (never silently), and a bypass
granted upstream (Stage 1 verification bypass, #316) must be honored
downstream instead of re-refusing (#334 — no double checking).

Run: python3 -m pytest tests/test_stage5_bypass_335.py -v
"""

import os
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest

import agents.chief_editor as ce_mod
from agents.video_prompt_engineer import video_prompt_engineer
from core.dual_engine import ModelGenerationError
from core.models import SceneItem


# ---------------------------------------------------------------- helpers

_FAKE_MODEL_OUTPUT = (
    "SCENE 1:\n"
    "PROMPT: [Rohan gestures at the metro construction site, cinematic]\n"
    "CAMERA: [slow push-in]\n"
    "LIGHTING: [warm golden hour]\n"
    "MOTION: [low]\n"
)


def _scene():
    return SceneItem(
        scene_number=1,
        character="Rohan",
        timestamp="0:00",
        visual_b_roll="Rohan gestures at the metro construction site",
        audio_sfx="Natural Scene Ambience",
        on_screen_text="Metro Update",
        scene_location="Metro construction site",
    )


def _empty_verif():
    # What execute_stage_1 produces after a #316 verification bypass:
    # a report with NO verified facts.
    return SimpleNamespace(
        verified_facts=[],
        physical_props=[],
        key_locations=[],
        core_conflict_or_irony="",
        tangible_actions=[],
    )


def _base_state(**overrides):
    state = {
        "script_dialogues": [{
            "idx": 0,
            "angle_tuple": ("Funny & Relatable", ""),
            "hook": "Suna kya?",
            "cta": "Follow!",
            "narration": "Rohan: Suna? Meena: Haan!",
            "scene_lines": [{"character": "Rohan", "dialogue": "Suna?"}],
            "attempt": 0, "retry_notes": [],
            "w_cnt": 50, "w_stat": "Pass", "e_dur": 25.0, "t_stat": "Pass",
            "clarity": 95, "audit_feedback": "all good",
        }],
        "news_input": "Metro news",
        "target_seconds": 30,
        "active_tone": "Joke",
        "active_angle": "Funny & Relatable",
        "scene_style": "Dialogue",
        "character_count": 2,
        "active_sample_story": "",
        "sub_instructions": {"scene_director": "sd", "video_prompt_engineer": "vp"},
        "verification": _empty_verif(),
        "verification_bypassed": False,
        "bypass_stage5_no_facts": False,
        "max_retries": 3,
        "batch_size": 1,
        "budget": {"recommended_words": 60, "min_words": 40, "max_words": 80},
        "agent_audits": [],
        "finalized_characters": [SimpleNamespace(name="Rohan"), SimpleNamespace(name="Meena")],
        "derived_scenes_per_script": [
            [SimpleNamespace(location_name="Metro site", props=["Helmet"])],
        ],
    }
    state.update(overrides)
    return state


def _install_mocks(monkeypatch):
    """Mock the model call inside generate_prompts (NOT generate_prompts
    itself — the bypass logic under test lives there)."""
    def fake_direct_scenes(**kwargs):
        return [_scene()]

    def fake_execute(prompt, engine_mode="first_local_then_agy"):
        return _FAKE_MODEL_OUTPUT

    monkeypatch.setattr(ce_mod.scene_director, "direct_scenes", fake_direct_scenes)
    monkeypatch.setattr(video_prompt_engineer, "execute", fake_execute)
    monkeypatch.setattr(ce_mod, "get_character_personas",
                        lambda *a, **k: ["Rohan", "Meena"])


# ---------------------------------------------------------------- tests

class TestGeneratePromptsBypass:
    def test_no_facts_without_bypass_raises(self):
        with pytest.raises(ModelGenerationError) as exc_info:
            video_prompt_engineer.generate_prompts(
                news_topic="Metro news",
                scenes=[_scene()],
                verified_facts=[],
            )
        assert "no verified facts available to ground video prompts" in str(exc_info.value)

    def test_no_facts_with_bypass_proceeds(self, monkeypatch):
        _install_mocks(monkeypatch)
        prompts = video_prompt_engineer.generate_prompts(
            news_topic="Metro news",
            scenes=[_scene()],
            verified_facts=[],
            bypass_no_facts=True,
        )
        assert len(prompts) == 1
        assert prompts[0].visual_prompt_ai  # ungrounded, but generated

    def test_facts_present_needs_no_bypass(self, monkeypatch):
        _install_mocks(monkeypatch)
        prompts = video_prompt_engineer.generate_prompts(
            news_topic="Metro news",
            scenes=[_scene()],
            verified_facts=["Metro line approved"],
        )
        assert len(prompts) == 1


class TestExecuteStage5HonorsBypass:
    def test_stage5_raises_without_any_bypass(self, monkeypatch):
        _install_mocks(monkeypatch)
        with pytest.raises(ModelGenerationError) as exc_info:
            ce_mod.ChiefEditorCoordinatorAgent().execute_stage_5(
                _base_state(), engine_mode="test", on_substep=lambda e: None)
        assert "no verified facts available to ground video prompts" in str(exc_info.value)

    def test_stage5_honors_verification_bypassed(self, monkeypatch):
        # #334: a Stage 1 bypass (#316) must not be re-checked at Stage 5.
        _install_mocks(monkeypatch)
        out = ce_mod.ChiefEditorCoordinatorAgent().execute_stage_5(
            _base_state(verification_bypassed=True),
            engine_mode="test", on_substep=lambda e: None)
        scripts = out.get("scripts") or []
        assert len(scripts) == 1
        assert scripts[0].scenes[0].video_prompt is not None

    def test_stage5_honors_direct_bypass_flag(self, monkeypatch):
        # #335: the failure-UI bypass button sets bypass_stage5_no_facts.
        _install_mocks(monkeypatch)
        out = ce_mod.ChiefEditorCoordinatorAgent().execute_stage_5(
            _base_state(bypass_stage5_no_facts=True),
            engine_mode="test", on_substep=lambda e: None)
        scripts = out.get("scripts") or []
        assert len(scripts) == 1
        assert scripts[0].scenes[0].video_prompt is not None
