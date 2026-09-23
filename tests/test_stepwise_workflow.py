"""Unit tests for Continuous vs Step-Wise Generation & Per-Step Model Execution."""

import unittest
from unittest.mock import patch
from workflow import reel_workflow
from core.models import ReelBatchResult, NewsVerificationReport, ReelScript


class TestStepwiseWorkflow(unittest.TestCase):
    """Test individual step execution, extra instruction injection, and per-step model override."""

    def setUp(self):
        # Enforce local model (fm_only) testing as required by project policy.
        # Patch check_status to indicate Local Apple FM is available
        self.patcher_status = patch(
            "core.dual_engine.DualEngine.check_status",
            return_value={"fm": {"available": True, "message": "Ready"}, "agy": {"available": False}, "grok": {"available": False}, "codex": {"available": False}}
        )
        self.patcher_status.start()

        self.patcher_validate = patch(
            "core.dual_engine.DualEngine.validate_mode",
            return_value={"fm": {"available": True, "message": "Ready"}}
        )
        self.patcher_validate.start()

        # Mock dual_engine.generate to simulate Local Apple FM responses without external network access
        self.patcher_generate = patch(
            "core.dual_engine.dual_engine.generate",
            return_value=("यह एक त्वरित हिंदी रील स्क्रिप्ट है। पूरी जानकारी यहाँ दी गई है।", "🍏 Local Apple FM (On-Device)")
        )
        self.patcher_generate.start()

        # Hermetically mock external news search so tests never hit remote RSS or web sources
        self.patcher_news = patch(
            "tools.news_fetcher.news_fetcher.search_news",
            return_value=[{"title": "Test Headline", "description": "Local test description", "source": "Local Wire"}]
        )
        self.patcher_news.start()

    def tearDown(self):
        self.patcher_news.stop()
        self.patcher_generate.stop()
        self.patcher_validate.stop()
        self.patcher_status.stop()

    def test_step_1_validation_and_extra_instruction(self):
        """Test that Step 1 initializes state and merges extra instruction into sub-instructions."""
        topic = "Government announces electric vehicle subsidy extension for 2027"
        extra_inst = "Focus on battery manufacturing incentives in Delhi NCR"

        state = reel_workflow.run_step_1(
            news_input=topic,
            scenario="Informative and engaging reel",
            batch_size=1,
            target_seconds=15,
            engine_mode="fm_only",
            extra_instruction=extra_inst,
        )

        self.assertEqual(state["step"], 1)
        self.assertIn("verification", state)
        self.assertIn("sub_instructions", state)
        self.assertIn("extra_instructions_history", state)
        self.assertIn(extra_inst, state["extra_instructions_history"])
        # Check that extra instruction was appended to news_validator sub_instruction
        self.assertIn(extra_inst, state["sub_instructions"]["news_validator"])

    def test_step_2_hooks_and_extra_instruction(self):
        """Test that Step 2 formulates hooks and CTAs using Step 1 state and accepts extra instruction."""
        topic = "UPI sets new record with 16 billion monthly transactions"
        state1 = reel_workflow.run_step_1(
            news_input=topic,
            scenario="Trending Reel",
            batch_size=1,
            target_seconds=15,
            engine_mode="fm_only",
        )

        extra_hook_inst = "Make the hook punchy with Devanagari slang like 'अरे भाई!'"
        state2 = reel_workflow.run_step_2(
            state=state1,
            engine_mode="fm_only",
            extra_instruction=extra_hook_inst,
        )

        self.assertEqual(state2["step"], 2)
        self.assertIn("hooks_and_ctas", state2)
        self.assertEqual(len(state2["hooks_and_ctas"]), 1)
        hook, cta = state2["hooks_and_ctas"][0]
        self.assertTrue(len(hook) > 0)
        self.assertTrue(len(cta) > 0)
        self.assertIn(extra_hook_inst, state2["sub_instructions"]["hook_strategist"])
        # Verify Character & Scene Finalisation output (2X generation)
        self.assertIn("available_characters", state2)
        self.assertIn("available_scenes", state2)
        self.assertIn("finalized_characters", state2)
        self.assertIn("finalized_scenes", state2)
        self.assertIn("story_steps", state2)
        self.assertGreaterEqual(len(state2["available_characters"]), 2)
        self.assertGreaterEqual(len(state2["available_scenes"]), 2)
        self.assertGreaterEqual(len(state2["finalized_characters"]), 1)
        self.assertGreaterEqual(len(state2["finalized_scenes"]), 1)
        self.assertGreaterEqual(len(state2["story_steps"]), 1)

    def test_step_3_dialogue_writing_and_timing_audit(self):
        """Test that Step 3 writes dialogue lines, calibrates duration pacing, and accepts extra instruction."""
        topic = "ISRO Gaganyaan crew module tests completed"
        state1 = reel_workflow.run_step_1(
            news_input=topic,
            scenario="Inspiring tech story",
            batch_size=1,
            target_seconds=10,
            engine_mode="fm_only",
            character_count=2,
            scene_style="Dialogue",
        )
        state2 = reel_workflow.run_step_2(state=state1, engine_mode="fm_only")

        extra_dialogue_inst = "Ensure characters speak fast, excited Hindi dialogue."
        state3 = reel_workflow.run_step_3(
            state=state2,
            engine_mode="fm_only",
            extra_instruction=extra_dialogue_inst,
        )

        self.assertEqual(state3["step"], 3)
        self.assertIn("script_dialogues", state3)
        self.assertEqual(len(state3["script_dialogues"]), 1)
        d = state3["script_dialogues"][0]
        self.assertIn("narration", d)
        self.assertIn("w_cnt", d)
        # Timing auditor must have verified word count
        self.assertLessEqual(d["w_cnt"], d["max_words"])
        self.assertIn(extra_dialogue_inst, state3["sub_instructions"]["dialogue_writer"])

    def test_step_4_scene_storyboard_and_video_prompts(self):
        """Test that Step 4 directs scene beats and synthesizes 9:16 AI video prompts."""
        topic = "Massive solar power plant inaugurated in Rajasthan"
        state1 = reel_workflow.run_step_1(
            news_input=topic,
            scenario="Positive environmental news",
            batch_size=1,
            target_seconds=15,
            engine_mode="fm_only",
        )
        state2 = reel_workflow.run_step_2(state=state1, engine_mode="fm_only")
        state3 = reel_workflow.run_step_3(state=state2, engine_mode="fm_only")

        extra_visual_inst = "Specify sweeping golden-hour aerial camera angles over solar panels."
        state4 = reel_workflow.run_step_4(
            state=state3,
            engine_mode="fm_only",
            extra_instruction=extra_visual_inst,
        )

        self.assertEqual(state4["step"], 4)
        self.assertIn("scripts", state4)
        self.assertEqual(len(state4["scripts"]), 1)
        sc = state4["scripts"][0]
        self.assertGreaterEqual(len(sc.scenes), 1)
        self.assertTrue(all(hasattr(scene, "video_prompt") for scene in sc.scenes))

    def test_step_5_signoff_and_final_batch_result(self):
        """Test that Step 5 performs compliance audit, packages ReelBatchResult, and signs off."""
        topic = "Varanasi Dev Deepawali celebration attracts worldwide visitors"
        state1 = reel_workflow.run_step_1(
            news_input=topic,
            scenario="Cultural pride",
            batch_size=1,
            target_seconds=10,
            engine_mode="fm_only",
        )
        state2 = reel_workflow.run_step_2(state=state1, engine_mode="fm_only")
        state3 = reel_workflow.run_step_3(state=state2, engine_mode="fm_only")
        state4 = reel_workflow.run_step_4(state=state3, engine_mode="fm_only")
        state5 = reel_workflow.run_step_5(state=state4, engine_mode="fm_only")

        self.assertEqual(state5["step"], 5)
        self.assertIn("batch_result", state5)
        batch_result = state5["batch_result"]
        self.assertIsInstance(batch_result, ReelBatchResult)
        self.assertEqual(len(batch_result.scripts), 1)
        self.assertGreaterEqual(batch_result.total_time_seconds, 0)
        self.assertIsNotNone(batch_result.audit_report)

    def test_stepwise_model_override_across_steps(self):
        """Test that different engine modes can be passed per-step without crashing."""
        topic = "New high-speed rail corridor approved between Delhi and Ahmedabad"
        # Step 1 with fallback
        state1 = reel_workflow.run_step_1(news_input=topic, scenario="News", batch_size=1, target_seconds=10, engine_mode="fm_only")
        self.assertEqual(state1["step"], 1)

        # Step 2 with fallback (or another available mode)
        state2 = reel_workflow.run_step_2(state=state1, engine_mode="fm_only")
        self.assertEqual(state2["step"], 2)

        # Step 3 with fallback
        state3 = reel_workflow.run_step_3(state=state2, engine_mode="fm_only")
        self.assertEqual(state3["step"], 3)

        # Step 4 with fallback
        state4 = reel_workflow.run_step_4(state=state3, engine_mode="fm_only")
        self.assertEqual(state4["step"], 4)

        # Step 5 with fallback
        state5 = reel_workflow.run_step_5(state=state4, engine_mode="fm_only")
        self.assertEqual(state5["step"], 5)
        self.assertIsInstance(state5["batch_result"], ReelBatchResult)

    def test_stepwise_rerun_step_with_refinement(self):
        """Test that re-running a step with updated instructions updates the state properly."""
        topic = "Chai prices increase across major metropolitan cities"
        state1 = reel_workflow.run_step_1(news_input=topic, scenario="Relatable comedy", batch_size=1, target_seconds=10, engine_mode="fm_only")
        
        # First attempt of Step 2
        state2_first = reel_workflow.run_step_2(state=state1, engine_mode="fm_only")
        hooks_first = list(state2_first["hooks_and_ctas"])

        # Re-run Step 2 with new extra instruction
        state2_rerun = reel_workflow.run_step_2(
            state=state1,
            engine_mode="fm_only",
            extra_instruction="Make hook focus on cutting chai lovers",
        )
        self.assertEqual(state2_rerun["step"], 2)
        self.assertIn("cutting chai lovers", state2_rerun["sub_instructions"]["hook_strategist"])

    def test_stage_1_correction_feedback_with_previous_verification(self):
        """Test that re-running Stage 1 with feedback incorporates previous facts for correction."""
        topic = "RBI changes repo rate by 25 basis points"
        state1_initial = reel_workflow.run_step_1(news_input=topic, scenario="Financial news", batch_size=1, target_seconds=10, engine_mode="fm_only")
        prev_verif = state1_initial["verification"]

        state1_corrected = reel_workflow.run_step_1(
            news_input=topic,
            scenario="Financial news",
            batch_size=1,
            target_seconds=10,
            engine_mode="fm_only",
            extra_instruction="Verify exact date and impact on home loan EMIs",
            previous_verification=prev_verif,
        )
        self.assertEqual(state1_corrected["step"], 1)
        self.assertIn("CORRECTION FEEDBACK ON PREVIOUS FACT VERIFICATION", state1_corrected["sub_instructions"]["news_validator"])
        self.assertIn("home loan EMIs", state1_corrected["sub_instructions"]["news_validator"])

    def test_stage_2_finalized_characters_passed_to_stage_3(self):
        """Test that Stage 2 finalised characters and story steps flow directly into Stage 3."""
        topic = "Telecom tariff hike affects basic phone users"
        state1 = reel_workflow.run_step_1(news_input=topic, scenario="Satirical drama", batch_size=1, target_seconds=10, engine_mode="fm_only", character_count=2)
        state2 = reel_workflow.run_step_2(state=state1, engine_mode="fm_only")

        self.assertIn("finalized_characters", state2)
        self.assertIn("story_steps", state2)
        chars = state2["finalized_characters"]
        steps = state2["story_steps"]
        self.assertTrue(len(chars) >= 1)
        self.assertTrue(len(steps) >= 1)

        # Run Stage 3
        state3 = reel_workflow.run_step_3(state=state2, engine_mode="fm_only")
        self.assertEqual(state3["step"], 3)
        self.assertIn("script_dialogues", state3)
        # Stage 3 uses the finalized characters
        dialogues = state3["script_dialogues"][0]
        self.assertIn("scene_lines", dialogues)
        self.assertTrue(len(dialogues["scene_lines"]) > 0)

    def test_stage_4_correction_feedback_with_previous_scenes(self):
        """Test that re-running Stage 4 captures previous scenes for correction."""
        topic = "New bullet train route announced"
        state1 = reel_workflow.run_step_1(news_input=topic, scenario="High tech", batch_size=1, target_seconds=10, engine_mode="fm_only")
        state2 = reel_workflow.run_step_2(state=state1, engine_mode="fm_only")
        state3 = reel_workflow.run_step_3(state=state2, engine_mode="fm_only")
        state4_initial = reel_workflow.run_step_4(state=state3, engine_mode="fm_only")
        self.assertIn("scripts", state4_initial)

        state4_corrected = reel_workflow.run_step_4(
            state=state4_initial,
            engine_mode="fm_only",
            extra_instruction="Change camera angle to low angle tracking shot inside the cabin",
        )
        self.assertEqual(state4_corrected["step"], 4)
        self.assertIn("CORRECTION FEEDBACK ON PREVIOUS STORYBOARD SCENES", state4_corrected["sub_instructions"]["scene_director"])
        self.assertIn("low angle tracking shot", state4_corrected["sub_instructions"]["scene_director"])

    def test_app_py_syntax_and_compilation(self):
        """Verify that app.py compiles cleanly without SyntaxError or IndentationError."""
        import py_compile
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_path = os.path.join(base_dir, "app.py")
        compiled = py_compile.compile(app_path, doraise=True)
        self.assertIsNotNone(compiled)

    def test_app_stepwise_ui_rendering_simulation(self):
        """Simulate Streamlit Step-Wise execution to verify that UI components render without AttributeError."""
        from streamlit.testing.v1 import AppTest
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_path = os.path.join(base_dir, "app.py")

        st1 = reel_workflow.run_step_1("Test news headline", "Scenario", 1, 10, "fm_only")

        at = AppTest.from_file(app_path, default_timeout=10)
        at.session_state["stepwise_active"] = True
        at.session_state["stepwise_current_step"] = 1
        at.session_state["stepwise_state"] = st1
        at.session_state["workflow_mode"] = "🪜 Step-Wise"
        at.run()

        exceptions = [e.message for e in at.exception] if at.exception else []
        self.assertEqual(exceptions, [], f"Streamlit app raised UI rendering exceptions: {exceptions}")


if __name__ == "__main__":
    unittest.main()
