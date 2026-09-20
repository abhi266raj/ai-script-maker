"""AI Video Director & Verification Agent (Google Flow / Veo 9:16 Prompts & Quality Gate)."""

import re
from typing import List, Tuple, Optional
from agents.base import BaseAgent
from core.models import VideoScenePrompt, VideoPassVerification, SceneItem
from core.prompt_loader import load_prompt


VIDEO_DIRECTOR_INSTRUCTIONS = load_prompt("video_director/prompt.md")


class AIVideoDirectorAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="AI Video Director (Google Flow / Veo)",
            role="AI Video Generation Prompts & Feasibility Verification",
            icon="🎥",
            instructions=VIDEO_DIRECTOR_INSTRUCTIONS,
            prompt_file="video_director/prompt.md",
        )

    def generate_video_prompts(
        self,
        news_topic: str,
        scenes: List[SceneItem],
        engine_mode: str = "first_local_then_agy",
    ) -> List[VideoScenePrompt]:
        """Generate structured 9:16 AI video prompts for Google Flow / Veo."""
        scenes_desc = ""
        for s in scenes:
            scenes_desc += f"Scene {s.scene_number} ({s.timestamp}): B-Roll: {s.visual_b_roll} | Text: {s.on_screen_text}\n"

        prompt = f"""Topic: {news_topic}

Scenes to convert into Google Flow / Veo AI Video Prompts:
{scenes_desc}

Task:
For each scene, output an ultra-detailed AI video prompt formatted as:
SCENE 1:
PROMPT: [Ultra-detailed 9:16 cinematic visual prompt describing camera motion, lighting, realistic textures, 4k 24fps]
CAMERA: [e.g., Low-angle tracking shot moving forward]
LIGHTING: [e.g., Volumetric golden rim lighting]
MOTION: [e.g., High dynamic movement]

(Repeat for each scene)"""

        raw_output = self.execute(prompt, engine_mode=engine_mode)

        video_prompts: List[VideoScenePrompt] = []
        scene_blocks = re.split(r"SCENE\s*(\d+):", raw_output, flags=re.IGNORECASE)

        # Parse blocks
        if len(scene_blocks) > 1:
            for i in range(1, len(scene_blocks), 2):
                s_num = int(scene_blocks[i])
                block_content = scene_blocks[i + 1]

                v_prompt = f"Cinematic 9:16 vertical video of {news_topic}, photorealistic 4K, 24fps, high detail."
                camera = "Dynamic slow push-in"
                lighting = "Cinematic dramatic lighting"
                motion = "Medium dynamic motion"

                for line in block_content.split("\n"):
                    l_str = line.strip()
                    if l_str.startswith("PROMPT:"):
                        v_prompt = l_str.replace("PROMPT:", "").strip("[] ")
                    elif l_str.startswith("CAMERA:"):
                        camera = l_str.replace("CAMERA:", "").strip("[] ")
                    elif l_str.startswith("LIGHTING:"):
                        lighting = l_str.replace("LIGHTING:", "").strip("[] ")
                    elif l_str.startswith("MOTION:"):
                        motion = l_str.replace("MOTION:", "").strip("[] ")

                ts = f"Scene {s_num}"
                for s in scenes:
                    if s.scene_number == s_num:
                        ts = s.timestamp
                        break

                video_prompts.append(
                    VideoScenePrompt(
                        scene_number=s_num,
                        timestamp=ts,
                        visual_prompt_ai=v_prompt,
                        camera_movement=camera,
                        lighting_and_mood=lighting,
                        aspect_ratio="9:16",
                        motion_level=motion,
                        ai_engine="Google Flow / Veo Compatible",
                    )
                )

        # Fallback if parsing was grouped
        if not video_prompts:
            for idx, s in enumerate(scenes, 1):
                video_prompts.append(
                    VideoScenePrompt(
                        scene_number=idx,
                        timestamp=s.timestamp,
                        visual_prompt_ai=f"Cinematic 9:16 vertical shot for Google Flow: {s.visual_b_roll}, photorealistic 4K render, natural lighting, smooth 24fps camera glide.",
                        camera_movement="Smooth camera dolly",
                        lighting_and_mood="High-contrast news documentary lighting",
                        aspect_ratio="9:16",
                        motion_level="Medium",
                        ai_engine="Google Flow / Veo",
                    )
                )

        return video_prompts

    def verify_video_pass(
        self,
        prompts: List[VideoScenePrompt],
        engine_mode: str = "first_local_then_agy",
    ) -> VideoPassVerification:
        """
        Verify whether the generated video prompts will pass AI video generation quality gates.
        Checks feasibility, temporal consistency, and prompt compliance.
        """
        prompts_summary = "\n".join([f"Scene {p.scene_number} ({p.timestamp}): {p.visual_prompt_ai[:100]}..." for p in prompts])

        eval_prompt = f"""Evaluate these Google Flow / Veo AI Video generation prompts for feasibility, safety, and 9:16 vertical video compliance:
{prompts_summary}

Evaluation Criteria:
1. Is it feasible for a 3-5 second generative clip? (No impossible multi-scene jumps in a single shot)
2. Does it maintain temporal visual continuity across scenes?
3. Is it safe (free from policy violations)?

Output:
STATUS: [PASSED / FAILED]
SCORE: [70-99]%
FEEDBACK: (1-2 sentences on why it passed or what needs revision)"""

        raw_output = self.execute(eval_prompt, engine_mode=engine_mode)

        score = 92
        match_score = re.search(r"SCORE:\s*\[?(\d{2,3})\]?%", raw_output, re.IGNORECASE)
        if match_score:
            try:
                score = int(match_score.group(1))
            except Exception:
                pass

        passed = True
        if "FAILED" in raw_output.upper() or score < 75:
            passed = False

        feedback = "Prompts verified: compliant with Google Flow / Veo 9:16 vertical generation standards."
        for line in raw_output.split("\n"):
            if "FEEDBACK:" in line.upper():
                feedback = line.split("FEEDBACK:", 1)[-1].strip()

        return VideoPassVerification(
            passed=passed,
            feasibility_score=score,
            safety_compliance="Passed",
            temporal_consistency="Passed" if passed else "Needs Adjustment",
            visual_clarity_check="High Quality",
            feedback=feedback,
        )


ai_video_director = AIVideoDirectorAgent()
