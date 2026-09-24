"""Tests for prompt loading and agent prompt decoupling using Markdown subdirectories."""

import unittest
from pathlib import Path
from core.prompt_loader import load_prompt, clear_prompt_cache, PROMPTS_DIR
from agents.news_validator import NewsValidationAgent
from agents.hook_strategist import HookAndAngleAgent
from agents.dialogue_writer import DialogueNarrationAgent
from agents.scene_director import SceneVisualsDirectorAgent
from agents.video_prompt_engineer import AIVideoPromptAgent
from agents.video_quality_gate import VideoQualityGateAgent
from agents.contextual_selector import ContextualSceneCharacterSelectorAgent
from agents.screenplay_coherence import ScreenplayCoherenceAgent


class TestPromptLoader(unittest.TestCase):
    def test_prompts_directory_exists(self):
        self.assertTrue(PROMPTS_DIR.is_dir(), "prompts directory should exist")

    def test_load_all_core_prompts_from_subdirectories(self):
        expected_agents = [
            ("news_validator", "validate_news.md"),
            ("hook_strategist", "craft_hook.md"),
            ("dialogue_writer", "write_dialogue.md"),
            ("scene_director", "direct_scenes.md"),
            ("video_prompt_engineer", "generate_prompts.md"),
            ("video_quality_gate", "audit_prompts.md"),
            ("contextual_selector", "contextual_selector.md"),
            ("screenplay_coherence", "screenplay_coherence.md"),
        ]
        for subagent, filename in expected_agents:
            md_path = PROMPTS_DIR / subagent / filename
            self.assertTrue(md_path.is_file(), f"Expected markdown file {md_path} to exist")

            text_by_path = load_prompt(f"{subagent}/{filename}")
            self.assertTrue(len(text_by_path) > 20, f"Prompt {subagent}/{filename} should have content")

    def test_agents_use_loaded_prompts(self):
        agent1 = NewsValidationAgent()
        self.assertEqual(agent1.instructions, load_prompt("news_validator/validate_news.md"))

        agent2 = HookAndAngleAgent()
        self.assertEqual(agent2.instructions, load_prompt("hook_strategist/finalise_characters.md"))

        agent3 = DialogueNarrationAgent()
        self.assertEqual(agent3.instructions, load_prompt("dialogue_writer/write_dialogue.md"))

        agent5 = SceneVisualsDirectorAgent()
        self.assertEqual(agent5.instructions, load_prompt("scene_director/direct_scenes.md"))

        agent6 = AIVideoPromptAgent()
        self.assertEqual(agent6.instructions, load_prompt("video_prompt_engineer/generate_prompts.md"))

        agent7 = VideoQualityGateAgent()
        self.assertEqual(agent7.instructions, load_prompt("video_quality_gate/audit_prompts.md"))

        agent_ctx = ContextualSceneCharacterSelectorAgent()
        self.assertEqual(agent_ctx.instructions, load_prompt("contextual_selector/contextual_selector.md"))

        agent_coh = ScreenplayCoherenceAgent()
        self.assertEqual(agent_coh.instructions, load_prompt("screenplay_coherence/screenplay_coherence.md"))

    def test_method_prompts_exist_and_render(self):
        from core.prompt_loader import render_prompt
        expected_method_prompts = [
            ("news_validator/validate_news.md", {"news_input": "Test Headline", "scenario": "Tech", "sub_directive": "", "sources_count": 0, "sources_text": ""}),
            ("hook_strategist/craft_hook.md", {"news_topic": "Test Headline", "angle_name": "Sarcastic", "angle_desc": "Sharp", "tone": "Funny", "duration_sec": 15, "cta_guidance": "Follow", "sub_directive": "", "verification_summary": "Verified"}),
            ("hook_strategist/craft_hooks_batch.md", {"news_topic": "Test Headline", "tone": "Funny", "duration_sec": 15, "cta_guidance": "Follow", "sub_directive": "", "facts_text": "", "verification_summary": "Verified", "angles_text": "Angle 1"}),
            ("dialogue_writer/write_dialogue.md", {"news_input": "Story", "hook": "Hook", "duration_sec": 15, "rec_words": 30, "min_words": 15, "max_words": 35, "sub_directive": "", "guidance": "", "tone": "Funny", "cta": "Follow", "correction_note": "", "facts_list": ""}),
            ("dialogue_writer/write_dialogue_batch.md", {"news_input": "Story", "duration_sec": 15, "actual_scenes": 3, "rec_words": 30, "min_words": 15, "max_words": 35, "per_scene_words": 10, "per_scene_max": 12, "narrative_name": "Fun First", "narrative_desc": "Humor then news", "character_count": 2, "personas_list": "P1, P2", "setting_location": "Tapri", "physical_props": "Chai", "core_conflict": "Irony", "facts_text": "Facts", "creative_rules": "", "sample_directive": "", "sub_directive": "", "guidance": "", "items_desc": "Script 1", "sample_scenes": "Scene 1"}),
            ("scene_director/direct_scenes.md", {"news_topic": "Topic", "hook": "Hook", "narration": "Narration", "duration_sec": 15, "target_frames": 3, "timestamps_text": "0:00 - 0:05", "props_text": "Chai", "locs_text": "Street", "actions_text": "Sip", "lines_summary": "Lines", "sub_directive": ""}),
            ("video_prompt_engineer/generate_prompts.md", {"news_topic": "Topic", "tone": "Funny", "angle": "Sarcastic", "sub_directive": "", "scenes_desc": "Scenes"}),
            ("video_quality_gate/audit_prompts.md", {"sub_directive": "", "prompts_summary": "Prompts"}),
        ]

        for rel_path, kwargs in expected_method_prompts:
            file_path = PROMPTS_DIR / rel_path
            self.assertTrue(file_path.is_file(), f"Method prompt file {file_path} should exist")
            rendered = render_prompt(rel_path, **kwargs)
            self.assertTrue(len(rendered) > 10, f"Rendered prompt for {rel_path} should not be empty")


if __name__ == "__main__":
    unittest.main()
