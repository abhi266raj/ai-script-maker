"""Unit test verifying end-to-end multi-agent context handoff and story coordination."""

import unittest
from core.models import NewsVerificationReport, SceneItem, VideoScenePrompt
from agents.news_validator import news_validator
from agents.hook_strategist import hook_strategist
from agents.dialogue_writer import dialogue_writer
from agents.scene_director import scene_director
from agents.video_prompt_engineer import video_prompt_engineer
from agents.video_quality_gate import video_quality_gate
from agents.chief_editor import chief_editor


class TestAgentCoordination(unittest.TestCase):
    def test_scene_director_prop_and_continuity_coordination(self):
        """Test that SceneDirector coordinates physical props and dialogue across 3 frames."""
        topic = "Indore Rahul Gandhi rally: 'Jhooth Ki Goonj' posters with QR code surface"
        hook = "इंदौर में राहुल गांधी के इवेंट से पहले हर तरफ 'झूठ की गूंज' वाले पोस्टर लग गए यार!"
        body = "सच में, मैंने फ्री पोहे का ऑफर समझकर QR कोड स्कैन कर दिया था!"
        scene_lines = [
            {"scene_number": 1, "character": "👩 Priya (प्रिया)", "dialogue": hook},
            {"scene_number": 2, "character": "🧑 Rahul (राहुल)", "dialogue": body},
            {"scene_number": 3, "character": "👩 Priya (प्रिया)", "dialogue": "इंदौरियों को पोहे का लालच देकर कुछ भी स्कैन करवा लो यार!"},
        ]

        scenes = scene_director.direct_scenes(
            news_topic=topic,
            hook=hook,
            narration=f"{hook} {body}",
            duration_sec=15,
            scene_lines=scene_lines,
            verified_facts=["Posters titled 'Jhooth Ki Goonj' with QR codes appeared across Indore walls"],
            tone="Funny & Relatable",
            angle="Funny & Relatable",
            scene_style="Dialogue",
            personas=["👩 Priya (प्रिया)", "🧑 Rahul (राहुल)"],
            engine_mode="fallback",
        )

        self.assertEqual(len(scenes), 3)
        # Verify Frame 1 introduces poster wall
        self.assertTrue(any(k in scenes[0].visual_b_roll.lower() for k in ["poster", "पोस्टर", "wall", "qr", "इंदौर"]))
        # Verify Frame 2 has smartphone viewfinder scanning QR code
        self.assertTrue(any(k in scenes[1].visual_b_roll.lower() for k in ["smartphone", "phone", "scan", "qr", "कैमरा"]))
        # Verify Frame 3 has public crowd / locals scanning
        self.assertTrue(any(k in scenes[2].visual_b_roll.lower() for k in ["locals", "students", "crowd", "street", "दुकान", "लोग"]))

    def test_video_prompt_engineer_coordination(self):
        """Test that AIVideoPromptAgent translates coordinated scenes into rich Veo 9:16 prompts."""
        topic = "'Jhooth Ki Goonj' QR Code Posters in Indore"
        scenes = [
            SceneItem(
                scene_number=1,
                character="👩 Priya",
                dialogue="इंदौर में पोस्टर लग गए यार!",
                timestamp="0:00 - 0:03",
                visual_b_roll="Handheld shot of wall with 'Jhooth Ki Goonj' posters featuring a large printed QR code",
                on_screen_text="झूठ की गूंज पोस्टर",
                audio_sfx="Whoosh",
            ),
            SceneItem(
                scene_number=2,
                character="🧑 Rahul",
                dialogue="मैंने फ्री पोहे का ऑफर समझकर QR कोड स्कैन कर दिया!",
                timestamp="0:03 - 0:10",
                visual_b_roll="Over-the-shoulder POV macro close-up of smartphone camera scanning the QR code on poster",
                on_screen_text="फ्री पोहा समझकर स्कैन",
                audio_sfx="QR Scan Beep",
            ),
        ]

        prompts = video_prompt_engineer.generate_prompts(
            news_topic=topic,
            scenes=scenes,
            tone="Funny & Relatable",
            angle="Funny & Relatable",
            engine_mode="fallback",
        )

        self.assertEqual(len(prompts), 2)
        # Check that Prompt 1 specifies poster & QR code
        self.assertTrue(any(k in prompts[0].visual_prompt_ai.lower() for k in ["poster", "qr code"]))
        # Check that Prompt 2 specifies smartphone scanning QR code
        self.assertTrue(any(k in prompts[1].visual_prompt_ai.lower() for k in ["smartphone", "phone", "qr code", "scan"]))
        self.assertIn("9:16", prompts[0].aspect_ratio)
        self.assertIn("Google Flow / Veo", prompts[0].ai_engine)
        # Ensure visual prompt text has zero internal vendor watermarks
        for p in prompts:
            self.assertNotIn("google flow/veo", p.visual_prompt_ai.lower())
            self.assertNotIn("vevo", p.visual_prompt_ai.lower())
            self.assertTrue(p.visual_prompt_ai.startswith("Cinematic 9:16 vertical shot:"))

    def test_video_quality_gate_audit(self):
        """Test that VideoQualityGate audits continuity and feasibility."""
        prompts = [
            VideoScenePrompt(
                scene_number=1,
                timestamp="0:00 - 0:03",
                visual_prompt_ai="Cinematic 9:16 vertical video: Handheld dynamic shot of poster wall with QR code, 4k 24fps.",
                camera_movement="Handheld push-in",
                lighting_and_mood="Golden hour",
                aspect_ratio="9:16",
                motion_level="High Dynamic",
            ),
            VideoScenePrompt(
                scene_number=2,
                timestamp="0:03 - 0:10",
                visual_prompt_ai="Cinematic 9:16 vertical video: Over-the-shoulder POV of smartphone scanning QR code, 4k 24fps.",
                camera_movement="Macro pull-focus",
                lighting_and_mood="Daylight",
                aspect_ratio="9:16",
                motion_level="Medium Fluid",
            ),
        ]

        audit = video_quality_gate.audit_prompts(prompts, engine_mode="fallback")
        self.assertTrue(audit.passed)
        self.assertGreaterEqual(audit.feasibility_score, 75)
        self.assertEqual(audit.temporal_consistency, "Passed")

    def test_news_validator_research_dossier_extraction(self):
        """Test that Agent 1 extracts physical props, locations, conflict, and actions."""
        topic = "Indore: 'Jhooth Ki Goonj' posters with QR code surface ahead of event"
        report = news_validator.validate_news(topic, engine_mode="fallback")
        self.assertTrue(report.is_verified)
        self.assertGreater(len(report.physical_props), 0)
        self.assertTrue(any("qr" in p.lower() or "poster" in p.lower() for p in report.physical_props))
        self.assertGreater(len(report.key_locations), 0)
        self.assertTrue(any("indore" in loc.lower() or "street" in loc.lower() for loc in report.key_locations))
        self.assertGreater(len(report.tangible_actions), 0)
        self.assertTrue(len(report.core_conflict_or_irony) > 0)

    def test_content_and_config_driven_scene_decision(self):
        """Test that Coordinator decides scenes based on researched content and active configuration."""
        topic = "Supreme Court issues historic order on EV charging infrastructure"
        report = news_validator.validate_news(topic, engine_mode="fallback")
        
        # Test 15s Debate Configuration
        scenes = scene_director.direct_scenes(
            news_topic=topic,
            hook="सुप्रीम कोर्ट का ऐतिहासिक फैसला!",
            narration="कोर्ट ने सभी हाईवे पर EV चार्जिंग स्टेशन अनिवार्य कर दिए हैं।",
            duration_sec=15,
            verified_facts=report.verified_facts,
            physical_props=report.physical_props,
            key_locations=report.key_locations,
            core_conflict_or_irony=report.core_conflict_or_irony,
            tangible_actions=report.tangible_actions,
            tone="Urgent & Breaking",
            angle="Investigative Deep-Dive",
            scene_style="Debate",
            personas=["👩 Advocate Sunita", "🧑 Expert Kabir"],
            engine_mode="fallback",
        )
        self.assertGreaterEqual(len(scenes), 2)
        # Should reflect court/legal and EV setting
        combined_visuals = " ".join([s.visual_b_roll.lower() for s in scenes])
        self.assertTrue(any(w in combined_visuals for w in ["court", "अदालत", "legal", "pillar", "brief", "document", "highway"]))

    def test_dynamic_single_scene_for_short_speech(self):
        """Test that a 5-second speech/monologue dynamically generates 1 continuous master shot."""
        topic = "Breaking: Finance Ministry announces tax rebate on green energy investments"
        scenes = scene_director.direct_scenes(
            news_topic=topic,
            hook="बड़ी खबर! ग्रीन एनर्जी पर टैक्स छूट का ऐलान!",
            narration="ग्रीन एनर्जी पर टैक्स छूट का बड़ा फैसला आ गया है।",
            duration_sec=5,
            scene_style="Speech",
            personas=["📢 Orator Devendra"],
            engine_mode="fallback",
        )
        self.assertEqual(len(scenes), 1)
        self.assertEqual(scenes[0].scene_number, 1)
        self.assertIn("0:00 - 0:05", scenes[0].timestamp)
        self.assertIn("Master Frame", scenes[0].act_name)
        self.assertTrue(any(w in scenes[0].visual_b_roll.lower() for w in ["continuous", "master", "push-in", "tracking"]))

    def test_dynamic_two_scenes_for_short_dialogue(self):
        """Test that a 10-second dialogue dynamically generates 2 scenes (setup and payoff)."""
        topic = "Indore: 'Jhooth Ki Goonj' posters with QR code surface"
        scenes = scene_director.direct_scenes(
            news_topic=topic,
            hook="इंदौर में 'झूठ की गूंज' वाले पोस्टर लग गए यार!",
            narration="मैंने फ्री पोहे का ऑफर समझकर QR कोड स्कैन कर दिया था!",
            duration_sec=10,
            scene_style="Dialogue",
            personas=["👩 Priya (प्रिया)", "🧑 Rahul (राहुल)"],
            engine_mode="fallback",
        )
        self.assertEqual(len(scenes), 2)
        self.assertEqual(scenes[0].scene_number, 1)
        self.assertEqual(scenes[1].scene_number, 2)
        self.assertIn("0:00 - 0:03", scenes[0].timestamp)
        self.assertIn("0:03 - 0:10", scenes[1].timestamp)
        self.assertIn("Frame 1", scenes[0].act_name)
        self.assertIn("Frame 2", scenes[1].act_name)

    def test_dynamic_four_scenes_for_long_investigative_story(self):
        """Test that a 45-second investigative story dynamically generates 4 scenes with continuous timestamps."""
        topic = "Massive financial fraud uncovered across multiple shell banking apps"
        scenes = scene_director.direct_scenes(
            news_topic=topic,
            hook="देश के करोड़ों रुपये गायब! बैंकिंग ऐप्स का महाघोटाला पकड़ा गया!",
            narration="जांच एजेंसियों ने छापेमारी कर फर्जी खातों का नेटवर्क उजागर किया है।",
            duration_sec=45,
            scene_style="Dialogue",
            personas=["👩 Presenter 1 Neha", "🧑 Presenter 2 Amit", "👵 Elder Witness", "👩‍💼 Analyst Lakshmi"],
            engine_mode="fallback",
            preferred_frames=4,
        )
        self.assertEqual(len(scenes), 4)
        for i, sc in enumerate(scenes, 1):
            self.assertEqual(sc.scene_number, i)
        # Verify boundary continuity (last timestamp ends at 0:45)
        self.assertTrue(scenes[0].timestamp.startswith("0:00"))
        self.assertTrue(scenes[3].timestamp.endswith("0:45"))

    def test_dialogue_writer_dynamic_scene_lines(self):
        """Test that dialogue writer dynamically generates scene lines matching requested scene counts."""
        report = NewsVerificationReport(
            is_verified=True,
            confidence_score=95,
            verified_facts=["Indore poster campaign featuring QR codes targeting political event"],
            physical_props=["posters", "QR code", "smartphone"],
            key_locations=["Indore street", "chai tapri"],
            core_conflict_or_irony="Locals thought QR code was for free poha but it linked to political video",
            tangible_actions=["pointing at poster", "scanning QR with phone"],
        )
        # 10s -> 2 scenes
        res_10s = dialogue_writer.write_dialogues_batch(
            news_input="Indore poster campaign",
            items=[{"angle": "Funny & Relatable", "hook": "इंदौर में पोस्टर लग गए!", "cta": "फॉलो करें!"}],
            tone="Funny & Relatable",
            duration_sec=10,
            verification=report,
            character_count=2,
            scene_style="Dialogue",
            engine_mode="fallback",
        )
        self.assertEqual(len(res_10s), 1)
        self.assertEqual(len(res_10s[0].scene_lines), 2)

        # 45s -> 4 scenes
        res_45s = dialogue_writer.write_dialogues_batch(
            news_input="Indore poster campaign",
            items=[{"angle": "Funny & Relatable", "hook": "इंदौर में पोस्टर लग गए!", "cta": "फॉलो करें!"}],
            tone="Funny & Relatable",
            duration_sec=45,
            verification=report,
            character_count=3,
            scene_style="Dialogue",
            num_scenes=4,
            engine_mode="fallback",
        )
        self.assertEqual(len(res_45s), 1)
        self.assertEqual(len(res_45s[0].scene_lines), 4)


if __name__ == "__main__":
    unittest.main()

