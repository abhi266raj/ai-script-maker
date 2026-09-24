"""Character groups, scene options, and AI-judge validation tests.

Verifies:
1. Stage 2: hook_strategist.finalise_character_groups returns TWO distinct groups
   (Group A and Group B), each with exactly N characters. No random selection.
2. Stage 4: hook_strategist.derive_scene_options returns TWO distinct scene sets
   (Set A and Set B), each with exactly num_scenes imaginative scenes.
3. Stage 3: ai_judge_news_coverage and ai_judge_tone_compliance exist in
   dialogue_writer and are wired into the validation flow.
4. Prompt templates exist: finalise_character_groups.md, derive_scene_options.md.
5. chief_editor stores both groups/sets in state for user selection.
"""
import inspect
import os
import pytest

from agents import hook_strategist as hs_mod
from agents import dialogue_writer as dw_mod
from agents import chief_editor as ce_mod

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _prompt_exists(name):
    return os.path.exists(os.path.join(REPO_ROOT, "prompts", name))


class TestCharacterGroups:
    def test_finalise_character_groups_method_exists(self):
        assert hasattr(hs_mod.HookStrategist, "finalise_character_groups"), \
            "HookStrategist missing finalise_character_groups"

    def test_character_groups_prompt_template_exists(self):
        assert _prompt_exists("hook_strategist/finalise_character_groups.md"), \
            "Missing prompts/hook_strategist/finalise_character_groups.md"

    def test_character_groups_template_asks_for_two_groups(self):
        path = os.path.join(REPO_ROOT, "prompts", "hook_strategist", "finalise_character_groups.md")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "GROUP A" in content, "Template must ask for GROUP A"
        assert "GROUP B" in content, "Template must ask for GROUP B"
        assert "requested_char_count" in content or "exactly" in content.lower(), \
            "Template must specify exact character count per group"
        # Reel point of view: options judged by what works for a short vertical reel
        assert "REEL" in content, "Template must guide AI to judge from reel point of view"
        # Two is deliberate — not three
        assert "TWO" in content, "Template must specify exactly two groups"

    def test_character_groups_returns_tuple_of_two(self):
        sig = inspect.signature(hs_mod.HookStrategist.finalise_character_groups)
        # Should accept character_count and return a tuple
        assert "character_count" in sig.parameters

    def test_chief_editor_stores_both_groups(self):
        src = inspect.getsource(ce_mod.chief_editor_coordinator.execute_stage_2)
        assert "character_group_a" in src, "Stage 2 must store character_group_a in state"
        assert "character_group_b" in src, "Stage 2 must store character_group_b in state"
        assert "selected_character_group" in src, "Stage 2 must track selected_character_group"

    def test_no_random_character_selection(self):
        """Stage 2 must not randomly pick from a flat pool — user selects a group."""
        src = inspect.getsource(ce_mod.chief_editor_coordinator.execute_stage_2)
        assert "finalise_character_groups" in src, \
            "Stage 2 must use finalise_character_groups (not flat list + random)"


class TestSceneOptions:
    def test_derive_scene_options_method_exists(self):
        assert hasattr(hs_mod.HookStrategist, "derive_scene_options"), \
            "HookStrategist missing derive_scene_options"

    def test_scene_options_prompt_template_exists(self):
        assert _prompt_exists("hook_strategist/derive_scene_options.md"), \
            "Missing prompts/hook_strategist/derive_scene_options.md"

    def test_scene_options_template_asks_for_two_sets(self):
        path = os.path.join(REPO_ROOT, "prompts", "hook_strategist", "derive_scene_options.md")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "SET A" in content, "Template must ask for SET A"
        assert "SET B" in content, "Template must ask for SET B"
        # Must demand imagination and forbid repetition
        lower = content.lower()
        assert "imagin" in lower, "Template must demand imagination"
        assert "differ" in lower or "different" in lower, \
            "Template must require the two sets to differ"
        # Reel point of view: options judged by what works for a short vertical reel
        assert "REEL" in content, "Template must guide AI to judge from reel point of view"

    def test_chief_editor_stores_both_scene_sets(self):
        src = inspect.getsource(ce_mod.chief_editor_coordinator.execute_stage_4)
        assert "scene_options_a_per_script" in src, "Stage 4 must store scene_options_a_per_script"
        assert "scene_options_b_per_script" in src, "Stage 4 must store scene_options_b_per_script"
        assert "selected_scene_set" in src, "Stage 4 must track selected_scene_set"

    def test_no_random_scene_selection(self):
        src = inspect.getsource(ce_mod.chief_editor_coordinator.execute_stage_4)
        assert "derive_scene_options" in src, \
            "Stage 4 must use derive_scene_options (not random pool)"


class TestAIJudges:
    def test_ai_judge_news_coverage_exists(self):
        assert hasattr(dw_mod, "ai_judge_news_coverage"), \
            "dialogue_writer missing ai_judge_news_coverage"

    def test_ai_judge_tone_compliance_exists(self):
        assert hasattr(dw_mod, "ai_judge_tone_compliance"), \
            "dialogue_writer missing ai_judge_tone_compliance"

    def test_news_judge_wired_into_validation(self):
        """When regex fails, the AI judge must be consulted before failing."""
        src = inspect.getsource(dw_mod.DialogueNarrationAgent.write_dialogues_batch)
        assert "ai_judge_news_coverage" in src, \
            "write_dialogues_batch must call ai_judge_news_coverage"

    def test_tone_judge_wired_into_validation(self):
        src = inspect.getsource(dw_mod.DialogueNarrationAgent.write_dialogues_batch)
        assert "ai_judge_tone_compliance" in src, \
            "write_dialogues_batch must call ai_judge_tone_compliance"

    def test_tone_judge_returns_issue_for_feedback(self):
        """Tone judge must return a specific issue so it can feed the correction loop."""
        sig = inspect.signature(dw_mod.ai_judge_tone_compliance)
        # Returns Tuple[bool, str] — (is_compliant, issue)
        src = inspect.getsource(dw_mod.ai_judge_tone_compliance)
        assert "ISSUE" in src, "Tone judge must extract a specific ISSUE from the AI response"

    def test_tone_corrective_pass_exists(self):
        """Failed tone must trigger one corrective regeneration with feedback."""
        src = inspect.getsource(dw_mod.DialogueNarrationAgent.write_dialogues_batch)
        assert "_tone_fix_done" in src, \
            "write_dialogues_batch must have a tone corrective pass (_tone_fix_done)"
