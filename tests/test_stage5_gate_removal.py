"""Stage 5 dead-AI-gate removal tests (2026-09-24).

The paid, always-pass, advisory AI quality gate
(`video_quality_gate.audit_prompts`) was fully removed from the Stage 5
path. These tests prove it stays removed and that the remaining blocking
check — the deterministic common-sense code validator — is labeled
honestly in the tracker events.

Run: python3 -m pytest tests/test_stage5_gate_removal.py -v
"""

import os
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import agents.chief_editor as ce_mod
from core.dual_engine import ModelGenerationError


# ---------------------------------------------------------------- helpers

def _make_verif():
    return SimpleNamespace(
        verified_facts=["Metro line approved", "Budget Rs 500 crore"],
        physical_props=["Helmet"],
        key_locations=["Metro site"],
        core_conflict_or_irony="Delay vs demand",
        tangible_actions=["Workers lift beams"],
    )


def _base_state(verif):
    return {
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
        "verification": verif,
        "max_retries": 3,
        "batch_size": 1,
        "budget": {"recommended_words": 60, "min_words": 40, "max_words": 80},
        "agent_audits": [],
        "finalized_characters": [SimpleNamespace(name="Rohan"), SimpleNamespace(name="Meena")],
        "derived_scenes_per_script": [
            [SimpleNamespace(location_name="Metro site", props=["Helmet"])],
        ],
    }


def _install_mocks(monkeypatch):
    """Mock the two AI generation calls + the dead gate (raising if called)."""
    def fake_direct_scenes(**kwargs):
        from core.models import SceneItem
        return [SceneItem(
            scene_number=1, character="Rohan", timestamp="0:00",
            visual_b_roll="Rohan gestures at the metro construction site",
            audio_sfx="Natural Scene Ambience",
            on_screen_text="Metro Update",
            scene_location="Metro construction site",
        )]

    dead_gate_calls = []

    def boom(*a, **k):
        dead_gate_calls.append((a, k))
        raise AssertionError("DEAD GATE CALLED: audit_prompts must never run")

    monkeypatch.setattr(ce_mod.scene_director, "direct_scenes", fake_direct_scenes)
    monkeypatch.setattr(ce_mod.video_prompt_engineer, "generate_prompts",
                        lambda **k: ["Cinematic vertical video prompt..."])
    monkeypatch.setattr(ce_mod.video_quality_gate, "audit_prompts", boom)
    # Keep persona sampling deterministic.
    monkeypatch.setattr(ce_mod, "get_character_personas",
                        lambda *a, **k: ["Rohan", "Meena"])
    return dead_gate_calls


# ---------------------------------------------------------------- tests

class TestDeadGateNeverCalled:
    def test_stage5_never_calls_audit_prompts(self, monkeypatch):
        dead_gate_calls = _install_mocks(monkeypatch)
        events = []
        ed = ce_mod.ChiefEditorCoordinatorAgent()
        out = ed.execute_stage_5(
            _base_state(_make_verif()), engine_mode="test",
            on_substep=events.append)
        assert dead_gate_calls == [], (
            "the removed AI quality gate must never be called")
        scripts = out.get("scripts") or []
        assert len(scripts) == 1
        # Honest default: gate did not run, so no verdict exists.
        assert scripts[0].video_verification is None

    def test_52_events_labeled_code_validator(self, monkeypatch):
        _install_mocks(monkeypatch)
        events = []
        ed = ce_mod.ChiefEditorCoordinatorAgent()
        ed.execute_stage_5(
            _base_state(_make_verif()), engine_mode="test",
            on_substep=events.append)
        subs_52 = [e for e in events if e.get("substep") == "5.2"]
        assert len(subs_52) >= 2, "5.2 must emit start + complete events"
        assert any(e.get("phase") == "start"
                   and e.get("name") == "Realism & coherence check"
                   and e.get("validator") == "code validator" for e in subs_52)
        assert any(e.get("phase") == "complete"
                   and e.get("status") == "pass"
                   and e.get("validator") == "code validator" for e in subs_52)
        assert not any("Quality gate" in str(e.get("name", "")) for e in events), (
            "no advisory quality-gate events may remain")


class TestStage5FailLoud:
    def test_persistent_common_sense_failure_raises(self, monkeypatch):
        _install_mocks(monkeypatch)
        from core import script_analyzer as sa_mod
        monkeypatch.setattr(
            sa_mod.common_sense_validator, "audit_screenplay",
            lambda script: (False, ["broken kinematics"], "broken kinematics"))
        monkeypatch.setattr(
            sa_mod.common_sense_validator, "heal_and_revalidate",
            lambda script, feedback="": (script, False, "still broken"))

        events = []
        ed = ce_mod.ChiefEditorCoordinatorAgent()
        raised = False
        try:
            ed.execute_stage_5(
                _base_state(_make_verif()), engine_mode="test",
                on_substep=events.append)
        except ModelGenerationError as exc:
            raised = True
            assert "Stage 5 failed" in str(exc)
        assert raised, "persistent failure must raise, never ship silently"
        fail_evts = [e for e in events if e.get("substep") == "5.2"
                     and e.get("phase") == "complete"
                     and e.get("status") == "fail"]
        assert len(fail_evts) == 1, "5.2 fail event must be emitted before raising"
        assert fail_evts[0].get("validator") == "code validator"
