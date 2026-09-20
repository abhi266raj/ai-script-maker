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
        expected_subagents = [
            "news_validator",
            "hook_strategist",
            "dialogue_writer",
            "scene_director",
            "video_prompt_engineer",
            "video_quality_gate",
            "contextual_selector",
            "screenplay_coherence",
            "reel_writer",
            "news_verifier",
            "video_director",
            "fact_checker",
            "researcher",
            "editor",
            "writer",
        ]
        for subagent in expected_subagents:
            md_path = PROMPTS_DIR / subagent / "prompt.md"
            self.assertTrue(md_path.is_file(), f"Expected markdown file {md_path} to exist")

            text_by_name = load_prompt(subagent)
            text_by_path = load_prompt(f"{subagent}/prompt.md")
            self.assertEqual(text_by_name, text_by_path)
            self.assertTrue(len(text_by_name) > 20, f"Prompt {subagent} should have content")

    def test_agents_use_loaded_prompts(self):
        agent1 = NewsValidationAgent()
        self.assertEqual(agent1.instructions, load_prompt("news_validator/prompt.md"))

        agent2 = HookAndAngleAgent()
        self.assertEqual(agent2.instructions, load_prompt("hook_strategist/prompt.md"))

        agent3 = DialogueNarrationAgent()
        self.assertEqual(agent3.instructions, load_prompt("dialogue_writer/prompt.md"))

        agent5 = SceneVisualsDirectorAgent()
        self.assertEqual(agent5.instructions, load_prompt("scene_director/prompt.md"))

        agent6 = AIVideoPromptAgent()
        self.assertEqual(agent6.instructions, load_prompt("video_prompt_engineer/prompt.md"))

        agent7 = VideoQualityGateAgent()
        self.assertEqual(agent7.instructions, load_prompt("video_quality_gate/prompt.md"))

        agent_ctx = ContextualSceneCharacterSelectorAgent()
        self.assertEqual(agent_ctx.instructions, load_prompt("contextual_selector/prompt.md"))

        agent_coh = ScreenplayCoherenceAgent()
        self.assertEqual(agent_coh.instructions, load_prompt("screenplay_coherence/prompt.md"))


if __name__ == "__main__":
    unittest.main()
