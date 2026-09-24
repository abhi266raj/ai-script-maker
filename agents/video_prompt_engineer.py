"""Agent 6: Cinematic 9:16 Visual Prompt Engineer Agent."""

import re
from typing import List, Optional
from agents.base import BaseAgent
from core.models import VideoScenePrompt, SceneItem
from core.dual_engine import ModelGenerationError
from core.prompt_loader import load_prompt, render_prompt


def clean_prompt_text(text: str) -> str:
    """Ensure no internal model or vendor tokens appear in the cinematic prompt."""
    if not text:
        return ""
    t = text
    # Strip internal vendor tokens (Google Flow, Veo, Sora, etc.)
    t = re.sub(r"(?:for\s+)?Google\s+(?:Flow\s*(?:/|and|\+)?\s*)?Veo(?:\s*9:16)?\s*:\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"(?:for\s+)?Google\s+Flow\s*:\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"(?:for\s+)?(?:Veo|Sora)\s*:\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"^Cinematic\s+9:16\s+vertical\s+video\s*(?:for\s+[^:]+)?:\s*", "Cinematic 9:16 vertical shot: ", t, flags=re.IGNORECASE)
    if not t.lower().startswith("cinematic 9:16 vertical"):
        t = f"Cinematic 9:16 vertical shot: {t}"
    return t.strip()


VIDEO_PROMPT_INSTRUCTIONS = load_prompt("video_prompt_engineer/generate_prompts.md")


class AIVideoPromptAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="AI Video Prompt Engineer",
            role="Cinematic 9:16 Visual Prompt Synthesis",
            icon="🎥",
            instructions=VIDEO_PROMPT_INSTRUCTIONS,
            prompt_file="video_prompt_engineer/generate_prompts.md",
        )

    def generate_prompts(
        self,
        news_topic: str,
        scenes: List[SceneItem],
        tone: str = "",
        angle: str = "",
        verified_facts: Optional[List[str]] = None,
        sub_instruction: Optional[str] = None,
        engine_mode: str = "first_local_then_agy",
    ) -> List[VideoScenePrompt]:
        """Convert each scene into an ultra-detailed 9:16 cinematic video prompt with full dialogue-prop continuity."""
        # Visual-only scene descriptions: never quote dialogue verbatim.
        # The video prompter needs the beat's purpose and visible action, not the spoken words.
        scenes_desc = ""
        for s in scenes:
            scenes_desc += (
                f"Scene {s.scene_number}:\n"
                f"  Speaker: {s.character}\n"
                f"  Visual Action & Props: {s.visual_b_roll}\n"
                f"  On-Screen Text: {s.on_screen_text}\n\n"
            )

        sub_directive = f"\nChief Editor Directive for AI Video Prompts:\n{sub_instruction}\n" if sub_instruction else ""
        facts_text = "\n".join([f"- {f}" for f in (verified_facts or [])[:4]])
        # Fail loudly: video prompts must be grounded in Stage 1 verified facts.
        # Generating anyway without facts would produce ungrounded visuals.
        if not facts_text.strip():
            raise ModelGenerationError(
                "Stage 5 failed: no verified facts available to ground video prompts. "
                "Refusing to generate visuals without Stage 1 facts."
            )

        prompt = render_prompt(
            "video_prompt_engineer/generate_prompts.md",
            news_topic=news_topic,
            tone=tone,
            angle=angle,
            verified_facts=facts_text,
            sub_directive=sub_directive,
            scenes_desc=scenes_desc,
        )

        try:
            raw_output = self.execute(prompt, engine_mode=engine_mode)
        except ModelGenerationError:
            raise
        except Exception as e:
            # Fail loudly: never synthesize template prompts when the engine itself failed.
            raise ModelGenerationError(
                f"Stage 5 failed: video prompt engine error ({type(e).__name__}): {e}. "
                f"News topic: {news_topic[:200]!r}"
            ) from e

        video_prompts: List[VideoScenePrompt] = []
        blocks = re.split(r"SCENE\s*(\d+):", raw_output, flags=re.IGNORECASE)

        if len(blocks) > 1:
            for i in range(1, len(blocks), 2):
                s_num = int(blocks[i])
                block_content = blocks[i + 1]

                v_prompt = ""
                camera = ""
                lighting = ""
                motion = ""

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

                # Fail loudly: every required field must come from the model
                # output. Invented camera/lighting/motion defaults would put
                # words in the video generator's mouth.
                missing = [label for label, val in
                           (("PROMPT", v_prompt), ("CAMERA", camera),
                            ("LIGHTING", lighting), ("MOTION", motion))
                           if not val]
                if missing:
                    raise ModelGenerationError(
                        f"Stage 5 failed: scene {s_num} is missing required field(s) "
                        f"{', '.join(missing)} in the video-prompt model output. "
                        f"Raw scene block: {block_content[:300]!r}"
                    )
                video_prompts.append(
                    VideoScenePrompt(
                        scene_number=s_num,
                        timestamp=ts,
                        visual_prompt_ai=clean_prompt_text(v_prompt),
                        camera_movement=camera,
                        lighting_and_mood=lighting,
                        aspect_ratio="9:16",
                        motion_level=motion,
                        ai_engine="Google Flow / Veo",
                    )
                )

        # Fail loudly: never synthesize template prompts when the model did not
        # return a parseable prompt for every scene. Surface the exact shortfall.
        if len(video_prompts) < len(scenes):
            raise ModelGenerationError(
                f"Stage 5 failed: video prompt engineer parsed {len(video_prompts)} prompts "
                f"for {len(scenes)} scenes. "
                f"Raw output snippet: {(raw_output or '')[:500]!r}"
            )

        return video_prompts


video_prompt_engineer = AIVideoPromptAgent()
