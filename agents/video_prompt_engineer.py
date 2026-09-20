"""Agent 6: Cinematic 9:16 Visual Prompt Engineer Agent."""

import re
from typing import List, Optional
from agents.base import BaseAgent
from core.models import VideoScenePrompt, SceneItem
from core.dual_engine import ModelGenerationError
from core.prompt_loader import load_prompt


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


VIDEO_PROMPT_INSTRUCTIONS = load_prompt("video_prompt_engineer/prompt.md")


class AIVideoPromptAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="AI Video Prompt Engineer",
            role="Cinematic 9:16 Visual Prompt Synthesis",
            icon="🎥",
            instructions=VIDEO_PROMPT_INSTRUCTIONS,
            prompt_file="video_prompt_engineer/prompt.md",
        )

    def generate_prompts(
        self,
        news_topic: str,
        scenes: List[SceneItem],
        tone: str = "",
        angle: str = "",
        sub_instruction: Optional[str] = None,
        engine_mode: str = "first_local_then_agy",
    ) -> List[VideoScenePrompt]:
        """Convert each scene into an ultra-detailed 9:16 cinematic video prompt with full dialogue-prop continuity."""
        scenes_desc = ""
        for s in scenes:
            scenes_desc += (
                f"Scene {s.scene_number} ({s.timestamp}):\n"
                f"  Speaker: {s.character}\n"
                f"  Spoken Dialogue: \"{s.dialogue}\"\n"
                f"  Visual Action & Props: {s.visual_b_roll}\n"
                f"  On-Screen Text: {s.on_screen_text}\n\n"
            )

        sub_directive = f"\nChief Editor Directive for AI Video Prompts:\n{sub_instruction}\n" if sub_instruction else ""

        prompt = f"""Topic: {news_topic}
Tone: {tone} | Angle: {angle}
{sub_directive}
Storyboard Scenes to translate into Cinematic 9:16 AI Video Prompts:
{scenes_desc}

Task:
For each scene, output:
SCENE 1:
PROMPT: [Ultra-detailed 9:16 cinematic visual prompt starting with 'Cinematic 9:16 vertical shot:' describing camera motion, actor action, physical props, specular reflections, volumetric lighting, photorealistic 4k 24fps. Do NOT include vendor/engine names.]
CAMERA: [e.g., Handheld dynamic low-angle push-in]
LIGHTING: [e.g., Warm golden late-afternoon street sunlight]
MOTION: [e.g., High dynamic movement]

(Repeat for each scene)"""

        raw_output = ""
        try:
            raw_output = self.execute(prompt, engine_mode=engine_mode)
        except ModelGenerationError:
            raise
        except Exception:
            raw_output = ""

        video_prompts: List[VideoScenePrompt] = []
        blocks = re.split(r"SCENE\s*(\d+):", raw_output, flags=re.IGNORECASE)

        if len(blocks) > 1:
            for i in range(1, len(blocks), 2):
                s_num = int(blocks[i])
                block_content = blocks[i + 1]

                v_prompt = ""
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

                if v_prompt:
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

        # Fallback / Synthesizer ensuring high-fidelity, prop-aware prompts for every scene
        if len(video_prompts) < len(scenes):
            video_prompts = self._synthesize_coordinated_prompts(news_topic, scenes, tone, angle)

        return video_prompts

    def _synthesize_coordinated_prompts(
        self,
        news_topic: str,
        scenes: List[SceneItem],
        tone: str,
        angle: str,
    ) -> List[VideoScenePrompt]:
        """Synthesize cinematic, prop-aware 9:16 prompts with camera kinematics, shot progression, and realistic lighting."""
        combined_vibe = f"{tone} {angle}".lower()
        is_sad = any(w in combined_vibe for w in ["sad", "heartbreak", "tragedy", "lament", "grief"])
        is_funny = any(w in combined_vibe for w in ["funny", "comedy", "sarcasm", "ह्यूमर", "देसी", "मजाकिया", "roast", "relatable"])
        is_culture = any(w in combined_vibe for w in ["culture", "heritage", "pride", "गौरव"])

        prompts: List[VideoScenePrompt] = []

        for sc in scenes:
            b_roll = sc.visual_b_roll
            b_roll_lower = b_roll.lower()

            has_qr = any(k in b_roll_lower for k in ["qr", "कोड", "स्कैन", "scan", "poster", "पोस्टर"])
            has_phone = any(k in b_roll_lower for k in ["phone", "smartphone", "screen", "मोबाइल", "स्क्रीन"])

            if has_qr and sc.scene_number == 1:
                cam = "Handheld tracking push-in focusing on poster wall"
                light = "Warm golden late-afternoon street sunlight with soft ambient bounce"
                prompt_text = (
                    f"Cinematic 9:16 vertical shot: Handheld dynamic shot in authentic Indian city street near a chai tapri; "
                    f"brick wall plastered with bold political posters featuring a high-contrast printed QR code and sharp Hindi typography; "
                    f"{sc.character} gesturing toward the posters with expressive reaction. "
                    f"Photorealistic 4K, 24fps, volumetric natural lighting, shallow depth of field, ultra-detailed textures, realistic physics."
                )
            elif has_qr and sc.scene_number == 2:
                cam = "Macro over-the-shoulder POV pull-focus to smartphone screen"
                light = "High-contrast daylight with subtle phone screen glow reflections"
                prompt_text = (
                    f"Cinematic 9:16 vertical shot: Cut to over-the-shoulder POV macro close-up; person holding a smartphone, "
                    f"camera viewfinder reticle actively framing and locking onto the printed QR code on wall poster; screen flashes and reveals "
                    f"an unexpected video page; person laughs in disbelief showing screen to camera. "
                    f"Photorealistic 4K, 24fps, ultra-detailed glass reflections, sharp UI overlay, realistic physics."
                )
            elif has_qr and sc.scene_number == 3:
                cam = "Dynamic smooth gimbal tracking down street to wide duo two-shot"
                light = "Vibrant outdoor street ambience, natural warm daylight"
                prompt_text = (
                    f"Cinematic 9:16 vertical shot: Cut to dynamic street tracking shot; group of curious Indian college youth and locals "
                    f"gathered along the poster-covered wall, holding up their smartphones to scan the QR codes and laughing together; "
                    f"cuts to two friends in foreground sharing a witty laugh. "
                    f"Photorealistic 4K, 24fps, cinematic composition, volumetric atmospheric lighting, realistic crowds."
                )
            else:
                cam = (
                    "Slow intimate push-in with shallow depth of field" if is_sad and sc.scene_number == 1
                    else "Gentle slow pan capturing tearful expressions" if is_sad and sc.scene_number == 2
                    else "Quick handheld push-in with comedic reaction" if is_funny and sc.scene_number == 1
                    else "Dynamic over-the-shoulder conversation pan" if is_funny and sc.scene_number == 2
                    else "Smooth low-angle dolly forward" if sc.scene_number == 1
                    else "Dynamic slow orbit tracking"
                )
                light = (
                    "Low-key melancholic lighting, soft desaturated shadows, warm amber candle glow" if is_sad
                    else "Vibrant warm daylight, colorful lively street aesthetic" if is_funny
                    else "Golden warm temple glow, atmospheric oil-lamp rim lighting" if is_culture
                    else "Volumetric golden rim lighting, high contrast dramatic mood"
                )
                # Ensure transitions avoid repeating the entire background setup
                shot_prefix = "Cinematic 9:16 vertical shot: "
                if sc.scene_number > 1 and not any(b_roll.lower().startswith(p) for p in ["cut to", "tight", "close-up", "medium", "tracking"]):
                    b_roll_clean = f"Cut to {b_roll[0].lower() + b_roll[1:] if b_roll else ''}"
                else:
                    b_roll_clean = b_roll

                prompt_text = (
                    f"{shot_prefix}{b_roll_clean}. "
                    f"Photorealistic 4K, 24fps, volumetric cinematic lighting, shallow depth of field, "
                    f"ultra-detailed textures, realistic physics."
                )

            prompts.append(
                VideoScenePrompt(
                    scene_number=sc.scene_number,
                    timestamp=sc.timestamp,
                    visual_prompt_ai=clean_prompt_text(prompt_text),
                    camera_movement=cam,
                    lighting_and_mood=light,
                    aspect_ratio="9:16",
                    motion_level="High Dynamic" if sc.scene_number == 1 else "Medium Fluid",
                    ai_engine="Google Flow / Veo",
                )
            )

        return prompts


video_prompt_engineer = AIVideoPromptAgent()
