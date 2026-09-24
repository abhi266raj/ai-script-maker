"""Agent 5: Scene & Visuals Director Agent."""

import re
from typing import List, Optional, Dict, Any, Tuple
from agents.base import BaseAgent
from core.models import SceneItem
from core.metrics import get_duration_budget
from core.dual_engine import ModelGenerationError
from core.prompt_loader import load_prompt, render_prompt

def clean_beat_action(text: str) -> str:
    """Strip camera framing and background setting preamble from running beat action."""
    if not text:
        return ""
    t = text.strip()
    # Match preamble ending with semicolon, e.g. "Handheld dynamic 9:16 shot at...; "
    t = re.sub(
        r"^(?:Handheld|Dynamic|Cinematic|Low-angle|Wide|Close-up|Medium|Tight|Seamless|Intimate|Aesthetic|High-energy|High-contrast|Over-the-shoulder|Reverse-angle|POV|Cut\s+to)?\s*(?:vertical\s*)?(?:\(?9:16\)?\s*)?(?:establishing\s*)?(?:hook\s*)?(?:shot|take|push-in|cut|tracking\s*shot|whip-pan|split-screen|opening\s*hook\s*tracking\s*shot)?\s*(?:at|on|outside|inside|in|near|with)?\s*[^;.]+;\s*",
        "",
        t,
        flags=re.IGNORECASE
    )
    # Match establishing shot sentence if followed by Character action
    t = re.sub(
        r"^(?:Low-angle|Wide|Close-up|Medium|Tight|Seamless|Handheld|Dynamic|Cinematic)\s*(?:vertical\s*)?(?:\(?9:16\)?\s*)?(?:establishing\s*)?(?:hook\s*)?shot\s+(?:at|outside|inside|in|near)\s+[^.]+\.\s+(?=[A-Z\u0900-\u097F])",
        "",
        t,
        flags=re.IGNORECASE
    )
    # Remove leading labels
    t = re.sub(r"^(?:VISUAL|ACTION|B-ROLL|CAMERA)\s*:\s*", "", t, flags=re.IGNORECASE)
    return t.strip()


SCENE_DIRECTOR_INSTRUCTIONS = load_prompt("scene_director/direct_scenes.md")


def calculate_scene_timestamps(duration_sec: int, num_scenes: int) -> List[str]:
    """
    Dynamically calculate non-overlapping, continuous timestamp intervals for N scenes.
    Ensures seamless temporal continuity for Google Flow / Veo generative clips (~3-6s each).
    """
    d = max(3, duration_sec)
    n = max(1, min(num_scenes, 5))
    if n == 1:
        return [f"0:00 - 0:{d:02d}"]

    # Hook duration (Scene 1) is calibrated to 2-3s for reels (the crucial 0-3s hook window)
    t_hook = min(3, max(2, d // 3))
    if n == 2:
        return [f"0:00 - 0:{t_hook:02d}", f"0:{t_hook:02d} - 0:{d:02d}"]

    # Allocate intermediate intervals proportionally
    rem_time = d - t_hook
    rem_scenes = n - 1
    step = rem_time / rem_scenes

    times = [f"0:00 - 0:{t_hook:02d}"]
    prev = t_hook
    for i in range(1, rem_scenes):
        curr = int(t_hook + i * step)
        times.append(f"0:{prev:02d} - 0:{curr:02d}")
        prev = curr
    times.append(f"0:{prev:02d} - 0:{d:02d}")
    return times


class SceneVisualsDirectorAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Scene & Visuals Director",
            role="Scene Breakdown, Visual B-Roll & SFX Direction",
            icon="🎬",
            instructions=SCENE_DIRECTOR_INSTRUCTIONS,
            prompt_file="scene_director/direct_scenes.md",
        )

    def direct_scenes(
        self,
        news_topic: str,
        hook: str,
        narration: str,
        duration_sec: int,
        scene_lines: Optional[List[Dict[str, str]]] = None,
        verified_facts: Optional[List[str]] = None,
        physical_props: Optional[List[str]] = None,
        key_locations: Optional[List[str]] = None,
        core_conflict_or_irony: str = "",
        tangible_actions: Optional[List[str]] = None,
        tone: str = "Funny & Relatable",
        angle: str = "Funny & Relatable",
        scene_style: str = "Dialogue",
        personas: Optional[List[str]] = None,
        sub_instruction: Optional[str] = None,
        engine_mode: str = "first_local_then_agy",
        preferred_frames: Optional[int] = None,
        previous_scenes: Optional[List[SceneItem]] = None,
        feedback: Optional[str] = None,
    ) -> List[SceneItem]:
        """
        Direct and break down the narration into visual scenes with strict prop and dialogue coordination.
        Scene count is completely dynamic (1 to 5 scenes) driven by content complexity,
        story structure, upstream dialogue beats, and generative video clip feasibility.
        """
        # Dynamic scene allocation:
        # 1. User/caller explicit preference (1..5)
        # 2. Upstream dialogue scene count (scene_lines)
        # 3. Pacing budget based on target duration & style
        if preferred_frames is not None and 1 <= preferred_frames <= 5:
            target_frames = preferred_frames
        elif scene_lines and len(scene_lines) > 0:
            target_frames = min(len(scene_lines), 5)
        else:
            budget = get_duration_budget(duration_sec)
            target_frames = budget.get("scenes", 3)
            # Short 5-8s reels with speech/monologue naturally work best as 1 continuous dynamic master shot
            if duration_sec <= 8 and (scene_style.lower() in ["speech", "monologue"] or (personas and len(personas) == 1)):
                target_frames = 1

        # Format upstream context from previous agents
        facts_summary = "\n".join([f"- {f}" for f in (verified_facts or [])[:3]])
        # Never present invented placeholders as researched/verified Stage 1 data:
        # an empty field is rendered as an explicit "(none verified)" marker.
        props_text = ", ".join(physical_props) if physical_props else "(none verified)"
        locs_text = ", ".join(key_locations) if key_locations else "(none verified)"
        actions_text = ", ".join(tangible_actions) if tangible_actions else "(none verified)"

        # Beat-purpose summaries for visual alignment — NEVER verbatim dialogue quotes.
        # Stage 4 is visual-only; the director needs to know what each beat
        # accomplishes (hook/fact/punchline) and the visible action, not the words.
        lines_summary = ""
        if scene_lines:
            for idx, line in enumerate(scene_lines, 1):
                c = line.get("character", f"Character {idx}")
                a = (line.get("action") or "").strip()
                # Purpose label from beat position: first=hook, last=payoff, else story advance
                if idx == 1:
                    purpose = "hook — grabs attention"
                elif idx == len(scene_lines):
                    purpose = "payoff — memorable closing beat"
                else:
                    purpose = "story advance — moves the narrative forward"
                beat_desc = f"Scene {idx} ({c}): {purpose}"
                if a:
                    beat_desc += f"; visible action: {a[:120]}"
                lines_summary += beat_desc + "\n"
        else:
            lines_summary = f"Full Narration: {narration}"

        sub_directive = f"\nChief Editor Directive for Scene Direction:\n{sub_instruction}\n" if sub_instruction else ""

        revision_directive = ""
        if previous_scenes:
            # Visual-only revision context: no timestamps (computed by code),
            # no dialogue (Stage 4 never handles spoken lines).
            prev_scenes_text = "\n\n".join([
                f"SCENE {sc.scene_number}:\nCHARACTER: {sc.character}\nACTION: {sc.visual_b_roll}"
                for sc in previous_scenes
            ])
            fb = feedback.strip() if feedback and feedback.strip() else (sub_instruction or "Improve scene visual framing and continuity.")
            revision_directive = (
                f"\n# 🔄 REVISION & CORRECTION MODE (HIGH PRIORITY):\n"
                f"You are REVISING existing storyboard scenes based on user feedback.\n"
                f"PREVIOUS SCENES:\n{prev_scenes_text}\n\n"
                f"USER CORRECTION FEEDBACK:\n{fb}\n\n"
                f"MANDATE: Directly address the user's critique. Refine the actor actions, prop interactions, and visual framing accordingly.\n"
            )

        timestamps_text = ", ".join(calculate_scene_timestamps(duration_sec, target_frames))

        prompt = render_prompt(
            "scene_director/direct_scenes.md",
            news_topic=news_topic,
            hook=hook,
            narration=narration,
            duration_sec=duration_sec,
            target_frames=target_frames,
            timestamps_text=timestamps_text,
            props_text=props_text,
            locs_text=locs_text,
            actions_text=actions_text,
            lines_summary=lines_summary,
            sub_directive=sub_directive,
            revision_directive=revision_directive,
        )

        try:
            raw_output = self.execute(prompt, engine_mode=engine_mode)
        except ModelGenerationError:
            raise
        except Exception as e:
            # Fail loudly: never synthesize template scenes when the engine itself failed.
            raise ModelGenerationError(
                f"Stage 5 failed: scene direction engine error ({type(e).__name__}): {e}. "
                f"News topic: {news_topic[:200]!r}"
            ) from e

        scenes: List[SceneItem] = []
        blocks = re.split(r"SCENE\s*(\d+):", raw_output, flags=re.IGNORECASE)

        # Deterministic timestamps: the model never writes timing (it botches clock
        # arithmetic). SceneItem timestamps come from code, not from model output.
        computed_timestamps = calculate_scene_timestamps(duration_sec, target_frames)

        # Stage 3 finalized dialogue, indexed by scene number. Stage 4 is
        # visual-only and must NEVER author dialogue — the spoken lines come
        # from the finalized Stage 3 output.
        stage3_dialogue = {}
        if scene_lines:
            for _idx, _line in enumerate(scene_lines, 1):
                stage3_dialogue[_idx] = (_line.get("dialogue") or "").strip()

        if len(blocks) > 1:
            for i in range(1, len(blocks), 2):
                s_num = int(blocks[i])
                content = blocks[i + 1]

                visual = ""
                character = ""
                text = ""
                sfx = ""

                for line in content.split("\n"):
                    l_str = line.strip()
                    if l_str.startswith("ACTION:"):
                        visual = l_str.replace("ACTION:", "").strip("[] ")
                    elif l_str.startswith("VISUAL:"):
                        visual = l_str.replace("VISUAL:", "").strip("[] ")
                    elif l_str.startswith("CHARACTER:"):
                        character = l_str.replace("CHARACTER:", "").strip("[] ")
                    elif l_str.startswith("TEXT:"):
                        text = l_str.replace("TEXT:", "").strip("[] \"' ")
                    elif l_str.startswith("SFX:"):
                        sfx = l_str.replace("SFX:", "").strip("[] ")
                    # NOTE: TIME: and DIALOGUE: are deliberately NOT parsed.
                    # Stage 4 output is visual-only; timestamps are computed and
                    # dialogue comes from finalized Stage 3 scene_lines.

                if visual:
                    cleaned_act = clean_beat_action(visual)
                    # Fail loudly: required fields must come from the model output,
                    # never from invented defaults ("Natural Scene Ambience",
                    # "Creator", "Scene N"). Surface the exact gap instead.
                    missing_fields = []
                    if not sfx:
                        missing_fields.append("SFX")
                    char = character or (personas[(s_num - 1) % len(personas)] if personas else "")
                    if not char:
                        missing_fields.append("CHARACTER")
                    if not (0 < s_num <= len(computed_timestamps)):
                        missing_fields.append("TIMESTAMP")
                    if missing_fields:
                        raise ModelGenerationError(
                            f"Stage 5 failed: scene {s_num} is missing required field(s) "
                            f"{', '.join(missing_fields)} in the scene-director model output. "
                            f"Raw scene block: {content[:300]!r}"
                        )
                    scenes.append(
                        SceneItem(
                            scene_number=s_num,
                            character=char,
                            dialogue=stage3_dialogue.get(s_num, ""),
                            timestamp=computed_timestamps[s_num - 1],
                            visual_b_roll=cleaned_act or visual,
                            # On-screen popup text is ALWAYS English — never fall back to Hindi dialogue.
                            on_screen_text=text,
                            audio_sfx=sfx,
                        )
                    )

        # Fail loudly: never synthesize template scenes when the model did not
        # return enough parseable scenes. Surface the exact shortfall instead.
        if len(scenes) < target_frames:
            raise ModelGenerationError(
                f"Stage 5 failed: scene director parsed {len(scenes)} scenes "
                f"but {target_frames} were required. "
                f"Raw output snippet: {(raw_output or '')[:500]!r}"
            )

        from core.script_analyzer import audit_and_heal_dialogue_targets, audit_and_enhance_visual_kinematics
        scenes = audit_and_heal_dialogue_targets(scenes)
        scenes = audit_and_enhance_visual_kinematics(scenes)
        return scenes


scene_director = SceneVisualsDirectorAgent()
