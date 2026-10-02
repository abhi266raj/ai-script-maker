"""Unit tests for Continuous vs Step-Wise Generation & Per-Step Model Execution."""

import re
import unittest
from types import SimpleNamespace
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

        # Mock dual_engine.generate to simulate Local Apple FM responses without external network access.
        # The hooks-batch prompt (hook_strategist/craft_hooks_batch.md) carries
        # "ANGLE 1:" blocks and requires a parseable HOOK:/CTA: response —
        # Stage 2 now generates hooks via the model and fails loudly otherwise.
        _news_response = (
            "STATUS: VERIFIED\nCONFIDENCE SCORE: 90%\nSUMMARY: Verified news story.\n"
            "VERIFIED FACTS:\n- Fact 1\n- Fact 2\n"
            "CORE CONFLICT OR IRONY: Viral debate and controversy surrounding the announcement.\n"
            "TANGIBLE ACTIONS:\n- Inspecting items\nKEY LOCATIONS:\n- City square\nPHYSICAL PROPS:\n- Banner",
            "🍏 Local Apple FM (On-Device)"
        )
        _groups_response = (
            "GROUP A:\n"
            "CHARACTER 1:\nName: Rohan\nJob: News Anchor\nAttire: Blue blazer\nEmotion: Confident\nRelationship: Anchor\n"
            "CHARACTER 2:\nName: Priya\nJob: Field Reporter\nAttire: Yellow kurta\nEmotion: Excited\nRelationship: Reporter\n"
            "GROUP B:\n"
            "CHARACTER 1:\nName: Amit\nJob: Tech Analyst\nAttire: Grey shirt\nEmotion: Skeptical\nRelationship: Analyst\n"
            "CHARACTER 2:\nName: Neha\nJob: Student\nAttire: Casual hoodie\nEmotion: Curious\nRelationship: Student\n",
            "🍏 Local Apple FM (On-Device)"
        )
        _base_response = ("यह एक त्वरित हिंदी रील स्क्रिप्ट है। पूरी जानकारी यहाँ दी गई है।", "🍏 Local Apple FM (On-Device)")
        # Stage 3 now fails loudly on unparseable model output (no silent
        # synthetic scenes), and the merged ai_judge_script_quality issues
        # its own model call expecting TONE_VERDICT/NEWS_VERDICT. The fake
        # must therefore return parseable dialogue and a passing verdict.
        # The dialogue must ALSO pass the code validators: no formal/
        # bureaucratic Hindi tokens (see _FORMAL_HINDI_TOKENS), and short
        # enough for the timing auditor's word budget.
        _dialogue_lines = [
            "अरे यार, सुना तुमने? चाय के दाम फिर बढ़ गए!",
            "सच में? अब तो घर पर ही चाय बनानी पड़ेगी!",
        ]

        def _dialogue_response_for(prompt):
            # Stage 3 refuses invented speakers: the dialogue may only use
            # finalized Stage 2 characters. Read their names from the
            # prompt's "Characters in Scene" section (character_count
            # varies per test, so hardcoding names breaks some tests).
            names = []
            m = re.search(r"Characters in Scene[^\n]*\n((?:- [^\n]+\n?)+)", prompt or "")
            if m:
                for line in m.group(1).splitlines():
                    nm = re.match(r"-\s*([A-Za-z][\w ]*?)\s*\(", line.strip())
                    if nm:
                        names.append(nm.group(1).strip())
            names = names or ["Rohan"]
            # Always emit 2 beats; reuse the single character when only one
            # was finalized ("Dialogue" style has no speaker-alternation rule).
            beats = []
            for i in range(2):
                beats.append(
                    f"BEAT {i + 1}:\nCHARACTER: {names[i % len(names)]}"
                    f"\nDIALOGUE: \"{_dialogue_lines[i % len(_dialogue_lines)]}\""
                )
            return ("SCRIPT 1:\n" + "\n".join(beats) + "\n", "🍏 Local Apple FM (On-Device)")
        _judge_response = (
            "TONE_VERDICT: YES\nTONE_ISSUE: None\n"
            "NEWS_VERDICT: YES\nNEWS_REASON: mocked pass",
            "🍏 Local Apple FM (On-Device)",
        )
        # Stage 4 derives TWO scene sets (A and B, 2 scenes each) from the
        # dialogue and then generates per-scene 9:16 video prompts. Both
        # parsers fail loudly on unparseable output, so the fake must return
        # the expected block structure.
        _scene_options_response = (
            "SET A:\n"
            "SCENE 1:\nLocation: Neighborhood tea corner\nAtmosphere: Bustling morning crowd\n"
            "Lighting: Warm daylight\nProps: Kettle, glasses\nGrounded in beats: 1\n"
            "SCENE 2:\nLocation: Home kitchen\nAtmosphere: Cozy and familiar\n"
            "Lighting: Soft indoor light\nProps: Stove, pan\nGrounded in beats: 2\n"
            "SET B:\n"
            "SCENE 1:\nLocation: Office pantry\nAtmosphere: Busy workday break\n"
            "Lighting: Bright fluorescent\nProps: Cups, water cooler\nGrounded in beats: 1\n"
            "SCENE 2:\nLocation: Park bench\nAtmosphere: Relaxed evening\n"
            "Lighting: Golden hour\nProps: Bench, trees\nGrounded in beats: 2\n",
            "🍏 Local Apple FM (On-Device)",
        )
        _video_prompts_response = (
            "SCENE 1:\n"
            "PROMPT: Close-up of a kettle whistling on a stove, steam rising in warm morning light.\n"
            "CAMERA: Close-up, shallow depth of field\n"
            "LIGHTING: Warm daylight\n"
            "MOTION: Slow push-in\n"
            "SCENE 2:\n"
            "PROMPT: Wide shot of a cozy home kitchen, a person pouring chai into glasses.\n"
            "CAMERA: Wide shot, eye level\n"
            "LIGHTING: Soft indoor light\n"
            "MOTION: Gentle pan left\n",
            "🍏 Local Apple FM (On-Device)",
        )
        # Stage 5's scene director needs SCENE blocks with ACTION, CHARACTER
        # and SFX lines (timestamps are computed by code, dialogue comes from
        # the finalized Stage 3 output).
        _scene_director_response = (
            "SCENE 1:\n"
            "ACTION: Close-up of a whistling kettle on a stove, steam curling up.\n"
            "CHARACTER: Rohan\n"
            "TEXT: Chai prices rise again!\n"
            "SFX: Kettle whistle\n"
            "SCENE 2:\n"
            "ACTION: Wide shot of a cozy kitchen, chai being poured into glasses.\n"
            "CHARACTER: Rohan\n"
            "TEXT: Home-brewed to the rescue\n"
            "SFX: Pouring liquid\n",
            "🍏 Local Apple FM (On-Device)",
        )

        def _fake_generate(*args, **kwargs):
            prompt = kwargs.get("prompt", args[0] if args else "")
            if isinstance(prompt, str):
                pl = prompt.lower()
                # NB: dialogue/judge checks come first — the dialogue prompt
                # embeds verified-facts context that would otherwise match
                # the news-verification branch below.
                if "script quality validator" in pl:
                    return _judge_response
                if "scene synthesis strategist" in pl:
                    return _scene_options_response
                if "cinematic ai video generation prompt engineer" in pl:
                    return _video_prompts_response
                if "visionary video director, visual storyboard artist" in pl:
                    return _scene_director_response
                # The step-3 dialogue prompt's role identity varies by angle
                # ("FUNNY SCREENWRITER" vs "Voiceover Scriptwriter"), but its
                # mission line is stable: "Your sole job in the pipeline is
                # writing spoken-word Hindi narration".
                if ("spoken-word hindi narration" in pl
                        or "voiceover scriptwriter" in pl
                        or "refining a finalized hindi reel dialogue draft" in pl):
                    return _dialogue_response_for(prompt)
                if "GROUP A" in prompt or "CHARACTER 1" in prompt or "finalise_character_groups" in prompt or "character_group" in prompt.lower():
                    return _groups_response
                if "ANGLE 1:" in prompt or "craft_hooks" in prompt:
                    return ("ANGLE 1:\nHOOK: 🔥 बड़ी खबर!\nCTA: फॉलो करें!", "🍏 Local Apple FM (On-Device)")
                if "CONFIDENCE SCORE" in prompt or "FACTS:" in prompt or "CORE CONFLICT" in prompt or "News Verification" in prompt or "RESEARCH" in prompt or "verify" in prompt.lower():
                    return _news_response
            return _base_response

        self.patcher_generate = patch(
            "core.dual_engine.dual_engine.generate",
            side_effect=_fake_generate,
        )
        self.patcher_generate.start()

        # Hermetically mock external news search so tests never hit remote RSS or web sources.
        # The validator reads NewsArticle attributes (source/title/snippet).
        self.patcher_news = patch(
            "tools.news_fetcher.news_fetcher.search_news",
            return_value=[SimpleNamespace(title="Test Headline", snippet="Local test description", source="Local Wire")]
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
        self.assertIn("hooks", state2)
        self.assertEqual(len(state2["hooks"]), 1)
        hook = state2["hooks"][0]
        self.assertTrue(len(hook) > 0)
        self.assertIn(extra_hook_inst, state2["sub_instructions"]["hook_strategist"])
        # Verify Character & Scene Finalisation output (2X generation)
        self.assertIn("available_characters", state2)
        self.assertIn("available_scenes", state2)
        self.assertIn("finalized_characters", state2)
        self.assertIn("finalized_scenes", state2)
        self.assertIn("story_steps", state2)
        self.assertGreaterEqual(len(state2["available_characters"]), 2)
        # NB: available_scenes stays EMPTY after Step 2 by design — scenes are
        # derived FROM the finalized Stage 3 dialogue in Step 4 (see
        # chief_editor.execute_stage_2: "finalized_scenes stays EMPTY here by
        # design"). This assertion used to expect scenes here; it now pins the
        # current pipeline contract instead.
        self.assertEqual(len(state2["available_scenes"]), 0)
        self.assertGreaterEqual(len(state2["finalized_characters"]), 1)
        # Same as available_scenes above: finalized_scenes is derived in
        # Step 4 from the finalized dialogue, so it is empty after Step 2.
        self.assertEqual(len(state2["finalized_scenes"]), 0)
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
        # NB: Stage 3 deliberately does NOT persist the extra instruction into
        # sub_instructions["dialogue_writer"] — it is passed as feedback to
        # the refine prompt only, so re-runs never stack stale blocks (see
        # chief_editor.execute_stage_3). It IS recorded in
        # extra_instructions_history. This assertion pins that contract.
        self.assertIn(extra_dialogue_inst, state3["extra_instructions_history"])

    def test_step_4_scene_options_derived_from_dialogue(self):
        """Test that Step 4 derives two distinct scene option sets (A and B) from the finalized dialogue."""
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
        # NB: storyboards + 9:16 video prompts moved to Step 5
        # (execute_stage_5). Step 4's contract is deriving the two scene
        # option sets FROM the finalized dialogue; the user picks one.
        for key in ("scene_options_a_per_script", "scene_options_b_per_script",
                    "derived_scenes_per_script", "selected_scene_set"):
            self.assertIn(key, state4)
        self.assertEqual(state4["selected_scene_set"], "A")
        set_a = state4["scene_options_a_per_script"][0]
        set_b = state4["scene_options_b_per_script"][0]
        self.assertGreaterEqual(len(set_a), 1)
        self.assertGreaterEqual(len(set_b), 1)
        # The two sets must be genuinely different creative visions.
        locs_a = {s.location_name for s in set_a}
        locs_b = {s.location_name for s in set_b}
        self.assertTrue(locs_a.isdisjoint(locs_b))
        # Extra instruction is recorded for the re-run loop.
        self.assertIn(extra_visual_inst, state4["extra_instructions_history"])

    def test_step_5_storyboard_and_video_prompts(self):
        """Test that Step 5 directs scene beats and synthesizes 9:16 AI video prompts."""
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
        state4 = reel_workflow.run_step_4(state=state3, engine_mode="fm_only")
        state5 = reel_workflow.run_step_5(state=state4, engine_mode="fm_only")

        self.assertEqual(state5["step"], 5)
        self.assertIn("scripts", state5)
        self.assertEqual(len(state5["scripts"]), 1)
        sc = state5["scripts"][0]
        self.assertGreaterEqual(len(sc.scenes), 1)
        self.assertTrue(all(hasattr(scene, "video_prompt") for scene in sc.scenes))

    def test_step_6_signoff_and_final_batch_result(self):
        """Test that Step 6 performs the integration validation gate, packages ReelBatchResult, and signs off."""
        # NB: the final packaging (ReelBatchResult + audit report) moved to
        # Step 6 "Integration & Final Validation" (execute_stage_6); Step 5
        # now ends at storyboards + video prompts.
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
        self.assertIn("scripts", state5)

        state6 = reel_workflow.run_step_6(state=state5, engine_mode="fm_only")
        self.assertEqual(state6["step"], 6)
        self.assertIn("batch_result", state6)
        batch_result = state6["batch_result"]
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

        # Step 6 with fallback (final packaging lives in Step 6)
        state6 = reel_workflow.run_step_6(state=state5, engine_mode="fm_only")
        self.assertEqual(state6["step"], 6)
        self.assertIsInstance(state6["batch_result"], ReelBatchResult)

    def test_stepwise_rerun_step_with_refinement(self):
        """Test that re-running a step with updated instructions updates the state properly."""
        topic = "Chai prices increase across major metropolitan cities"
        state1 = reel_workflow.run_step_1(news_input=topic, scenario="Relatable comedy", batch_size=1, target_seconds=10, engine_mode="fm_only")
        
        # First attempt of Step 2
        state2_first = reel_workflow.run_step_2(state=state1, engine_mode="fm_only")
        hooks_first = list(state2_first["hooks"])

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

    def test_stage_5_correction_feedback_with_previous_scenes(self):
        """Test that re-running Stage 5 captures previous storyboard scenes for correction."""
        # NB: storyboard correction moved to Stage 5 with the scene_director
        # (execute_stage_5); Stage 4 now only derives scene option sets.
        topic = "New bullet train route announced"
        state1 = reel_workflow.run_step_1(news_input=topic, scenario="High tech", batch_size=1, target_seconds=10, engine_mode="fm_only")
        state2 = reel_workflow.run_step_2(state=state1, engine_mode="fm_only")
        state3 = reel_workflow.run_step_3(state=state2, engine_mode="fm_only")
        state4 = reel_workflow.run_step_4(state=state3, engine_mode="fm_only")
        state5_initial = reel_workflow.run_step_5(state=state4, engine_mode="fm_only")
        self.assertIn("scripts", state5_initial)

        state5_corrected = reel_workflow.run_step_5(
            state=state5_initial,
            engine_mode="fm_only",
            extra_instruction="Change camera angle to low angle tracking shot inside the cabin",
        )
        self.assertEqual(state5_corrected["step"], 5)
        self.assertIn("CORRECTION FEEDBACK ON PREVIOUS STORYBOARD SCENES", state5_corrected["sub_instructions"]["scene_director"])
        self.assertIn("low angle tracking shot", state5_corrected["sub_instructions"]["scene_director"])

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
