"""Reel Writer Agent: Generates Hindi reel scripts with English angle titles and metadata."""

import re
from typing import List, Optional, Callable
from agents.base import BaseAgent
from core.models import ReelScript, SceneItem, NewsVerificationReport
from core.metrics import verify_word_count, verify_timeline_fit, evaluate_clarity, get_duration_budget


REEL_WRITER_INSTRUCTIONS = """You are a viral Short-Form Video Producer and Master Hindi Reel Scriptwriter.
You specialize in writing high-retention Instagram Reels and YouTube Shorts in natural, compelling Hindi.
Rules:
1. The script narration MUST be in fluent, impactful Hindi (Devanagari script) matching the requested tone (e.g., Funny & Relatable, Witty, Urgent, etc.).
2. The Hook must grab attention in the first 2-3 seconds with humor, curiosity, or relatability.
3. Keep the narration strictly calibrated to the target word budget for the chosen duration.
4. Provide vivid visual B-roll cues, SFX, and Hindi on-screen text overlays for each scene.
5. Treat the deliverable as a screenplay, not a mobile UI card. Every scene must contain a timestamp, visual direction, character name, and spoken dialogue.
6. The screenplay header format is: 9:16 VERTICAL | ~[target seconds] SECONDS.
7. Keep dialogue separate from visual direction so it can be read and performed directly."""

# 100% Clean English angle labels for tabs, titles, and exports
REEL_ANGLES = [
    ("1. Funny & Relatable", "Humorous everyday life perspective, light sarcasm and conversational idioms"),
    ("2. Witty & Sarcastic Meme", "Meme-worthy punchlines, witty irony and sharp commentary"),
    ("3. Urgent Breaking News Alert", "Fast-paced breaking news urgency and dramatic revelation"),
    ("4. Shocking Curiosity & Did You Know?", "Mind-bending fact that stops viewers from scrolling"),
    ("5. Everyday Pocket & Wallet Impact", "Common person monthly budget, groceries, petrol, and savings impact"),
    ("6. Fact vs Myth Reality Check", "Exposing viral fake claims with cold hard verified facts"),
    ("7. Cinematic Thriller & Suspense", "Suspenseful storytelling, ticking clock, dramatic opening"),
    ("8. Rapid 3-Point Explainer", "Crisp, fast-fire 3 key takeaways format"),
    ("9. Futuristic Sci-Fi & What Next", "Looking ahead at future technological and societal ripple effects"),
    ("10. Audience Debate & Engagement Poll", "Provocative open question inspiring heated comment debates"),
]


class ReelWriterAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Hindi Reel Script Producer",
            role="Scriptwriting, Hooks & Scene Direction (FM + AGY)",
            icon="🎬",
            instructions=REEL_WRITER_INSTRUCTIONS,
        )

    def generate_single_script(
        self,
        script_id: int,
        angle_tuple: tuple,
        news_input: str,
        scenario: str,
        verification: NewsVerificationReport,
        target_seconds: int = 30,
        engine_mode: str = "first_local_then_agy",
    ) -> ReelScript:
        """Generate one complete Reel script strictly calibrated to target_seconds."""
        t_sec = max(5, target_seconds)
        budget = get_duration_budget(t_sec)

        angle_name, angle_desc = angle_tuple

        prompt = f"""Target Duration: Exactly {t_sec} Seconds
Target Spoken Word Budget: {budget['words_str']} (Keep narration strictly within this word limit)
Recommended Structure: {budget['breakdown']}
Angle: {angle_name} ({angle_desc})
Tone/Scenario: {scenario}
News Item: {news_input}

Verified Facts to Base Script On:
{chr(10).join(['- ' + f for f in verification.verified_facts[:3]])}

Instructions:
1. Write spoken-word Hindi narration in Devanagari matching {budget['words_str']}.
2. Provide an ultra-catchy 0-3s Hook.
3. Provide scene breakdowns matching the {t_sec}s timeline.
4. Output format:

9:16 VERTICAL | ~{t_sec} SECONDS

# HOOK (0-3s):
[Catchy Hindi Hook with emojis]

# HINDI NARRATION:
[Spoken Hindi narration matching {budget['words_str']}]

# SCENE 1 (0-3s):
VISUAL: [Visual B-roll camera shot description in English]
CHARACTER: [Speaker name]
DIALOGUE: [Spoken Hindi dialogue for this scene]
TEXT: [Hindi text on screen]
SFX: [Audio cue / Sound effect]

# SCENE 2 (3-{t_sec}s):
VISUAL: [Visual B-roll description in English]
CHARACTER: [Speaker name]
DIALOGUE: [Spoken Hindi dialogue for this scene]
TEXT: [Hindi text on screen]
SFX: [Audio cue]

# CALL TO ACTION:
[Engaging Hindi CTA]"""

        raw_output = self.execute(prompt, engine_mode=engine_mode)

        hook = "अरे भाई! क्या आपको ये खबर पता है?"
        narration = ""
        cta = "फॉलो करें और दोस्तों को शेयर करना मत भूलना!"
        scenes: List[SceneItem] = []

        lines = raw_output.split("\n")
        current_sec = None
        current_scene_data = {}

        for line in lines:
            line_str = line.strip()
            if line_str.startswith("# HOOK"):
                current_sec = "hook"
            elif line_str.startswith("# HINDI NARRATION"):
                current_sec = "narration"
            elif line_str.startswith("# CALL TO ACTION"):
                current_sec = "cta"
            elif line_str.startswith("# SCENE"):
                current_sec = "scene"
                if current_scene_data:
                    scenes.append(
                        SceneItem(
                            scene_number=current_scene_data.get("num", len(scenes) + 1),
                            timestamp=current_scene_data.get("timestamp", "0:00 - 0:03"),
                            visual_b_roll=current_scene_data.get("visual", "Dramatic news footage"),
                            on_screen_text=current_scene_data.get("text", "बड़ी खबर"),
                            audio_sfx=current_scene_data.get("sfx", "Whoosh + Beat"),
                            narration_line="",
                        )
                    )
                    current_scene_data = {}

                match_num = re.search(r"SCENE\s*(\d+)", line_str)
                s_num = int(match_num.group(1)) if match_num else len(scenes) + 1
                current_scene_data["num"] = s_num
                match_ts = re.search(r"\(([^)]+)\)", line_str)
                if match_ts:
                    current_scene_data["timestamp"] = match_ts.group(1)
                else:
                    current_scene_data["timestamp"] = f"Scene {s_num}"
            else:
                if current_sec == "hook" and line_str and not line_str.startswith("#"):
                    hook = line_str.strip("[]\"'")
                elif current_sec == "narration" and line_str and not line_str.startswith("#"):
                    narration += line_str + " "
                elif current_sec == "cta" and line_str and not line_str.startswith("#"):
                    cta = line_str.strip("[]\"'")
                elif current_sec == "scene":
                    if line_str.startswith("VISUAL:"):
                        current_scene_data["visual"] = line_str.replace("VISUAL:", "").strip("[] ")
                    elif line_str.startswith("TEXT:"):
                        current_scene_data["text"] = line_str.replace("TEXT:", "").strip("[] ")
                    elif line_str.startswith("SFX:"):
                        current_scene_data["sfx"] = line_str.replace("SFX:", "").strip("[] ")

        if current_scene_data:
            scenes.append(
                SceneItem(
                    scene_number=current_scene_data.get("num", len(scenes) + 1),
                    timestamp=current_scene_data.get("timestamp", f"0:{max(1, t_sec-4)} - 0:{t_sec}"),
                    visual_b_roll=current_scene_data.get("visual", "Creator reaction"),
                    on_screen_text=current_scene_data.get("text", "कमेंट करें"),
                    audio_sfx=current_scene_data.get("sfx", "Outro chime"),
                    narration_line="",
                )
            )

        cleaned_narration = narration.strip() or f"{hook} {news_input}. {cta}"

        # Step 2: Verify Word Count
        w_count, w_status, w_feedback = verify_word_count(cleaned_narration, t_sec)

        # Step 3: Verify Timeline & Duration Fit
        est_duration, time_status, time_feedback = verify_timeline_fit(w_count, t_sec)

        # Step 4: Evaluate Clarity
        clarity = evaluate_clarity(cleaned_narration, hook, cta)

        return ReelScript(
            id=script_id,
            title=f"Reel #{script_id} ({t_sec}s): {angle_name.split('.')[1].strip() if '.' in angle_name else angle_name}",
            angle=angle_name,
            hook_hindi=hook,
            narration_hindi=cleaned_narration,
            call_to_action=cta,
            scenes=scenes,
            word_count=w_count,
            word_count_status=w_status,
            word_count_feedback=w_feedback,
            target_duration_sec=t_sec,
            estimated_duration_sec=est_duration,
            timeline_fit_status=time_status,
            timeline_feedback=time_feedback,
            clarity_score=clarity,
            music_vibe="Viral Trending Beat",
        )
