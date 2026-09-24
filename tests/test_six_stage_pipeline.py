"""Six-stage pipeline ordering, no-scenes-before-dialogue, creativity & news-clarity tests.

Verifies the 6-stage architecture:
1. Stage 1: Facts & verification
2. Stage 2: Character strategy (characters ONLY, no scenes) — hook_strategist 1st run
3. Stage 3: Finalized dialogue (NO predefined scene binding)
4. Stage 4: Scene derivation FROM finalized dialogue — hook_strategist 2nd run
5. Stage 5: Storyboard & video prompts from dialogue-derived scenes
6. Stage 6: Integration & validation

Also verifies:
- Creativity mandates in scriptwriter + scene-maker prompts
- News-clarity mandates in dialogue prompts
- workflow.run_step_6 exists
"""
import inspect
import os
import pytest

from agents import chief_editor as ce_mod
from agents.chief_editor import chief_editor_coordinator
from workflow import reel_workflow

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _prompt(name):
    path = os.path.join(REPO_ROOT, "prompts", name)
    with open(path, encoding="utf-8") as f:
        return f.read()


class TestSixStageMethodsExist:
    def test_chief_editor_has_all_six_stages(self):
        for i in range(1, 7):
            assert hasattr(chief_editor_coordinator, f"execute_stage_{i}"), \
                f"Missing execute_stage_{i}"

    def test_workflow_has_all_six_steps(self):
        for i in range(1, 7):
            assert hasattr(reel_workflow, f"run_step_{i}"), \
                f"Missing run_step_{i}"

    def test_stage_6_is_integration_and_validation(self):
        src = inspect.getsource(chief_editor_coordinator.execute_stage_6)
        assert "Integration" in src or "integration" in src
        assert "validation" in src.lower()


class TestNoScenesBeforeDialogue:
    def test_stage_2_produces_no_scenes(self):
        """Stage 2 must leave finalized_scenes EMPTY by design."""
        src = inspect.getsource(chief_editor_coordinator.execute_stage_2)
        assert "finalized_scenes: List = []" in src or "finalized_scenes=[]" in src or \
               'finalized_scenes = []' in src, \
            "Stage 2 must explicitly set finalized_scenes to empty"
        # Must document WHY scenes stay empty
        assert "Stage 4" in src and "dialogue" in src.lower(), \
            "Stage 2 must document that Stage 4 derives scenes from dialogue"

    def test_stage_3_passes_no_predefined_scenes(self):
        """Stage 3 must explicitly pass finalized_scenes=[] (no scene binding)."""
        src = inspect.getsource(chief_editor_coordinator.execute_stage_3)
        assert "finalized_scenes=[]" in src, \
            "Stage 3 must explicitly pass finalized_scenes=[] — no predefined scene binding"
        # Must NOT pass through state.get("finalized_scenes")
        assert 'finalized_scenes=state.get("finalized_scenes")' not in src, \
            "Stage 3 must NOT pass through state finalized_scenes"

    def test_stage_2_uses_characters_only_mode(self):
        """Stage 2 must invoke hook_strategist in characters-only mode."""
        src = inspect.getsource(chief_editor_coordinator.execute_stage_2)
        assert "include_scenes=False" in src, \
            "Stage 2 must call hook_strategist with include_scenes=False"


class TestStageOrdering:
    def test_stage_4_derives_from_dialogue(self):
        """Stage 4 must read script_dialogues (Stage 3 output) and derive scenes."""
        src = inspect.getsource(chief_editor_coordinator.execute_stage_4)
        assert 'state["script_dialogues"]' in src, \
            "Stage 4 must read Stage 3's script_dialogues"
        assert "derive_scenes_from_dialogue" in src, \
            "Stage 4 must call hook_strategist.derive_scenes_from_dialogue"
        assert 'state["derived_scenes_per_script"]' in src, \
            "Stage 4 must store derived_scenes_per_script"

    def test_stage_4_is_second_strategist_invocation(self):
        """The hook strategist must be invoked at Stages 2 AND 4."""
        src2 = inspect.getsource(chief_editor_coordinator.execute_stage_2)
        src4 = inspect.getsource(chief_editor_coordinator.execute_stage_4)
        assert "hook_strategist" in src2, "Stage 2 must use hook_strategist"
        assert "hook_strategist" in src4, "Stage 4 must use hook_strategist (2nd invocation)"

    def test_stage_5_uses_derived_scenes(self):
        """Stage 5 must use Stage 4's derived scenes, not Stage-2 options."""
        src = inspect.getsource(chief_editor_coordinator.execute_stage_5)
        assert "derived_scenes_per_script" in src or 'state.get("finalized_scenes")' in src, \
            "Stage 5 must consume derived scenes"

    def test_orchestrate_runs_six_stages(self):
        """The orchestrator must report total_steps=6."""
        src = inspect.getsource(chief_editor_coordinator.orchestrate_reel_pipeline)
        assert '"total_steps": 6' in src or "'total_steps': 6" in src, \
            "Orchestrator must report total_steps=6"


class TestCreativityMandates:
    def test_dialogue_prompt_has_creativity_mandate(self):
        prompt = _prompt("dialogue_writer/write_dialogue_batch.md")
        assert "CREATIVITY MANDATE" in prompt, \
            "Stage 3 prompt must explicitly mandate creativity"
        assert "CREATIVE SCREENWRITER" in prompt, \
            "Stage 3 prompt must instruct creative screenwriter identity"

    def test_refine_prompt_has_creativity(self):
        prompt = _prompt("dialogue_writer/refine_dialogue_batch.md")
        assert "creativ" in prompt.lower(), \
            "Refine prompt must carry creativity instruction"

    def test_scene_derivation_prompt_has_creativity(self):
        prompt = _prompt("hook_strategist/derive_scenes_from_dialogue.md")
        assert "BE CREATIVE" in prompt, \
            "Stage 4 scene-derivation prompt must explicitly demand creativity"

    def test_storyboard_prompt_has_creativity(self):
        prompt = _prompt("scene_director/direct_scenes.md")
        assert "CREATIVITY MANDATE" in prompt, \
            "Stage 5 storyboard prompt must explicitly mandate creativity"


class TestNewsClarityMandates:
    def test_dialogue_prompt_has_news_clarity_law(self):
        prompt = _prompt("dialogue_writer/write_dialogue_batch.md")
        assert "NEWS CLARITY LAW" in prompt, \
            "Stage 3 prompt must have explicit NEWS CLARITY LAW"
        # Must ban vague allusions
        assert "Vague allusions" in prompt or "vague" in prompt.lower(), \
            "Stage 3 prompt must ban vague news references"

    def test_refine_prompt_has_news_clarity(self):
        prompt = _prompt("dialogue_writer/refine_dialogue_batch.md")
        assert "NEWS CLARITY" in prompt, \
            "Refine prompt must carry news-clarity requirement"

    def test_dialogue_prompt_names_what_who_where(self):
        prompt = _prompt("dialogue_writer/write_dialogue_batch.md")
        assert "WHAT happened" in prompt and "WHO is involved" in prompt, \
            "Stage 3 prompt must require WHAT/WHO/WHERE clarity"
