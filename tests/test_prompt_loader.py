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

    def test_method_prompts_exist_and_render(self):
        from core.prompt_loader import render_prompt
        expected_method_prompts = [
            ("news_validator/validate_news.md", {"headline": "Test Headline", "category": "Tech"}),
            ("hook_strategist/craft_hook.md", {"headline": "Test Headline", "category": "Tech", "tone": "Funny", "duration": 15, "angle": "Sarcastic"}),
            ("hook_strategist/craft_hooks_batch.md", {"headline": "Test Headline", "category": "Tech", "tone": "Funny", "duration": 15, "angle": "Sarcastic", "batch_count": 2}),
            ("dialogue_writer/write_dialogue.md", {"selected_hook": "Hook", "headline": "Headline", "category": "Tech", "tone": "Funny", "duration": 15, "rec_words": 30, "min_words": 15, "max_words": 35, "wps": 2.2, "character_context_prompt": "", "character_count": 1, "scene_style": "Monologue", "angle": "Humorous"}),
            ("dialogue_writer/write_dialogue_batch.md", {"selected_hook": "Hook", "headline": "Headline", "category": "Tech", "tone": "Funny", "duration": 15, "rec_words": 30, "min_words": 15, "max_words": 35, "wps": 2.2, "character_context_prompt": "", "character_count": 1, "scene_style": "Monologue", "angle": "Humorous", "batch_count": 2}),
            ("scene_director/direct_scenes.md", {"dialogue": "Narration", "duration": 15, "angle": "Humorous", "tone": "Funny", "frame_count": 3, "character_context_prompt": ""}),
            ("video_prompt_engineer/generate_prompts.md", {"storyboard_details": "Story", "tone": "Funny", "style": "9:16", "duration": 15, "aspect_ratio": "9:16", "resolution": "4K", "fps": "24fps", "camera_style": "Cinematic", "lighting_style": "Warm", "motion_style": "Smooth", "negative_prompt": "Blur", "characters_summary": "None"}),
            ("video_quality_gate/audit_prompts.md", {"video_prompts_text": "Prompt 1", "tone": "Funny", "duration": 15, "aspect_ratio": "9:16", "resolution": "4K", "fps": "24fps"}),
            ("reel_writer/generate_single_script.md", {"topic": "AI", "angle": "Tech", "tone": "Funny", "category": "Tech", "duration": 15, "fact_check_summary": "Verified", "reliability_score": 95, "character_context_prompt": ""}),
            ("news_verifier/verify.md", {"topic": "AI"}),
            ("video_director/generate_video_prompts.md", {"topic": "AI", "article_content": "Content", "tone": "Informative"}),
            ("video_director/verify_prompts_quality.md", {"prompts_data": "Prompts"}),
            ("fact_checker/audit.md", {"topic": "AI", "key_findings": "Findings", "sources_text": "Source 1"}),
            ("researcher/analyze.md", {"topic": "AI", "sources_text": "Source 1"}),
            ("writer/write.md", {"topic": "AI", "research_findings": "Findings", "target_word_count": 500, "fact_check_score": 90, "fact_check_notes": "Good"}),
            ("editor/review_and_publish.md", {"topic": "AI", "draft_headline": "Headline", "draft_subheadline": "Subheadline", "draft_content": "Content", "reliability_score": 90, "audit_summary": "Passed"}),
        ]

        for rel_path, kwargs in expected_method_prompts:
            file_path = PROMPTS_DIR / rel_path
            self.assertTrue(file_path.is_file(), f"Method prompt file {file_path} should exist")
            rendered = render_prompt(rel_path, **kwargs)
            self.assertTrue(len(rendered) > 10, f"Rendered prompt for {rel_path} should not be empty")


if __name__ == "__main__":
    unittest.main()
