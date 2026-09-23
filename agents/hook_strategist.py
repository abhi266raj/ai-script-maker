"""Agent 2: Character Finalisation Strategist Agent (formerly Hook & Angle Strategist)."""

import re
from typing import Tuple, List, Optional, Dict, Any
from agents.base import BaseAgent
from core.models import NewsVerificationReport, CharacterProfile, SceneSettingOption, StoryBeatStep
from core.dual_engine import ModelGenerationError
from core.prompt_loader import load_prompt, render_prompt

CHARACTER_FINALISER_INSTRUCTIONS = load_prompt("hook_strategist/finalise_characters.md")


class CharacterFinaliserAgent(BaseAgent):
    """
    Lead Character & Scene Finalisation Strategist.
    Analyzes Stage 1 news dossier and produces a rich 2X pool of grounded characters
    and 2X pool of grounded scene locations for downstream selection.
    """
    def __init__(self):
        super().__init__(
            name="Character Finalisation Strategist",
            role="Character & Scene Location Finalisation",
            icon="🎭",
            instructions=CHARACTER_FINALISER_INSTRUCTIONS,
            prompt_file="hook_strategist/finalise_characters.md",
        )

    def craft_hook(
        self,
        news_topic: str,
        angle_name: str,
        angle_desc: str,
        tone: str,
        verification: NewsVerificationReport,
        duration_sec: int = 30,
        sub_instruction: Optional[str] = None,
        engine_mode: str = "first_local_then_agy",
    ) -> Tuple[str, str]:
        """Generate a viral 0-3s Hindi hook and an engaging Call-To-Action (CTA)."""
        cta_guidance = (
            "Keep CTA ultra-short (1-2 words e.g. 'फॉलो करें!') because reel is very short."
            if duration_sec <= 10 else
            "Keep CTA concise (3-5 words e.g. 'फॉलो करें और राय बताएं!')."
        )
        sub_directive = f"\nChief Editor Directive:\n{sub_instruction}\n" if sub_instruction else ""
        prompt = render_prompt(
            "hook_strategist/craft_hook.md",
            news_topic=news_topic,
            angle_name=angle_name,
            angle_desc=angle_desc,
            tone=tone,
            duration_sec=duration_sec,
            cta_guidance=cta_guidance,
            sub_directive=sub_directive,
            verification_summary=verification.verification_summary,
        )

        try:
            raw_output = self.execute(prompt, engine_mode=engine_mode)
        except ModelGenerationError:
            raise
        except Exception:
            raw_output = ""

        hook = f"🔥 अरे सुनिए! {news_topic[:40]} को लेकर बड़ा अपडेट आ गया है!"
        cta = "फॉलो करें!" if duration_sec <= 10 else "फॉलो करें और अपनी राय कमेंट में बताएं!"

        for line in raw_output.split("\n"):
            line_str = line.strip()
            if line_str.startswith("HOOK:"):
                hook = line_str.replace("HOOK:", "").strip("[] \"'")
            elif line_str.startswith("CTA:"):
                cta = line_str.replace("CTA:", "").strip("[] \"'")

        return hook, cta

    def craft_hooks_batch(
        self,
        news_topic: str,
        angles: List[Tuple[str, str]],
        tone: str,
        verification: NewsVerificationReport,
        duration_sec: int = 30,
        sub_instruction: Optional[str] = None,
        engine_mode: str = "first_local_then_agy",
    ) -> List[Tuple[str, str]]:
        """Generate viral hooks and CTAs for multiple angles in a single optimized inference call."""
        angles_text = "\n".join([f"ANGLE {i+1}: {a[0]} ({a[1]})" for i, a in enumerate(angles)])
        cta_guidance = (
            f"Because reel is {duration_sec}s, keep CTA strictly 1 to 3 words (e.g. 'फॉलो करें!' or 'शेयर करें!')."
            if duration_sec <= 10 else
            f"Keep CTA concise (under 6 words)."
        )
        sub_directive = f"\nChief Editor Directive for Hooks & Angles:\n{sub_instruction}\n" if sub_instruction else ""
        facts_text = "\n".join([f"- {f}" for f in (verification.verified_facts if verification else [])[:3]])
        prompt = render_prompt(
            "hook_strategist/craft_hooks_batch.md",
            news_topic=news_topic,
            tone=tone,
            duration_sec=duration_sec,
            cta_guidance=cta_guidance,
            sub_directive=sub_directive,
            facts_text=facts_text or news_topic,
            verification_summary=verification.verification_summary if verification else news_topic,
            angles_text=angles_text,
        )

        try:
            raw_output = self.execute(prompt, engine_mode=engine_mode)
        except ModelGenerationError:
            raise
        except Exception:
            raw_output = ""

        results: List[Tuple[str, str]] = []
        blocks = re.split(r"ANGLE\s*(\d+):", raw_output, flags=re.IGNORECASE)

        parsed_map = {}
        if len(blocks) > 1:
            for i in range(1, len(blocks), 2):
                idx = int(blocks[i]) - 1
                content = blocks[i + 1]
                h = None
                c = None
                for line in content.split("\n"):
                    ls = line.strip()
                    if ls.startswith("HOOK:"):
                        h = ls.replace("HOOK:", "").strip("[] \"'")
                    elif ls.startswith("CTA:"):
                        c = ls.replace("CTA:", "").strip("[] \"'")
                if h and c:
                    parsed_map[idx] = (h, c)

        default_c = "फॉलो करें!" if duration_sec <= 10 else "शेयर करें और अपनी राय नीचे कमेंट में बताएं!"
        for i, a in enumerate(angles):
            if i in parsed_map:
                results.append(parsed_map[i])
            else:
                default_h = f"🔥 {a[0].split('(')[0].strip()}: क्या आपको ये खबर पता चली?"
                results.append((default_h, default_c))

        return results

    def finalise_characters_and_scenes(
        self,
        news_topic: str,
        verification: NewsVerificationReport,
        scenario: str = "",
        sample_story: Optional[str] = None,
        tone: str = "Relatable Comedy",
        angle: str = "Funny & Relatable",
        character_count: int = 2,
        num_scenes: int = 3,
        scene_style: str = "Dialogue",
        duration_sec: int = 30,
        sub_instruction: Optional[str] = None,
        engine_mode: str = "first_local_then_agy",
        previous_characters: Optional[List[Dict[str, Any]]] = None,
        previous_scenes: Optional[List[Dict[str, Any]]] = None,
        feedback: Optional[str] = None,
    ) -> Tuple[List[CharacterProfile], List[SceneSettingOption]]:
        """
        Stage 2: Finalize 2X character profiles and 2X scene setting options.
        Focuses strictly on grounded imagination of characters and locations.
        """
        from agents.dialogue_writer import get_character_personas
        from core.screenplay_formatter import get_character_attire
        import json

        # Request 2X characters and 2X scene options
        target_char_count = max(2, character_count * 2)
        target_scene_count = max(2, num_scenes * 2)

        facts_text = "\n".join([f"- {f}" for f in (verification.verified_facts if verification else [])[:4]])
        props_text = ", ".join(verification.physical_props) if (verification and verification.physical_props) else ""
        locs_text = ", ".join(verification.key_locations) if (verification and verification.key_locations) else ""
        conflict_text = verification.core_conflict_or_irony if (verification and verification.core_conflict_or_irony) else ""

        scenario_directive = f"Creative Scenario / Guidance:\n{scenario}\n" if scenario and scenario.strip() else ""
        sub_directive = f"Chief Editor Directive:\n{sub_instruction}\n" if sub_instruction and sub_instruction.strip() else ""

        revision_directive = ""
        if (previous_characters or previous_scenes) and feedback and feedback.strip():
            prev_chars_str = json.dumps(previous_characters or [], ensure_ascii=False, indent=2)
            prev_scenes_str = json.dumps(previous_scenes or [], ensure_ascii=False, indent=2)
            revision_directive = (
                f"\n# 🔄 REVISION & CORRECTION MODE (HIGH PRIORITY):\n"
                f"You are REVISING previously finalized characters and scene locations based on user feedback.\n\n"
                f"PREVIOUS CHARACTERS:\n{prev_chars_str}\n\n"
                f"PREVIOUS SCENES:\n{prev_scenes_str}\n\n"
                f"USER CORRECTION FEEDBACK:\n{feedback.strip()}\n\n"
                f"CORRECTION MANDATE:\n"
                f"- Directly update characters (names, jobs, attire) and scene locations to resolve the user's critique.\n"
            )

        prompt = render_prompt(
            "hook_strategist/finalise_characters.md",
            news_topic=news_topic,
            duration_sec=duration_sec,
            tone=tone,
            angle=angle,
            scene_style=scene_style,
            requested_char_count=character_count,
            target_char_count=target_char_count,
            requested_scene_count=num_scenes,
            target_scene_count=target_scene_count,
            setting_location=locs_text or "Public Indian street / workplace setting",
            physical_props=props_text or "Smartphones, documents, daily tools",
            core_conflict=conflict_text or news_topic,
            facts_text=facts_text or f"- {news_topic}",
            scenario_directive=scenario_directive,
            sub_directive=sub_directive,
            revision_directive=revision_directive,
        )

        try:
            raw_output = self.execute(prompt, engine_mode=engine_mode)
        except ModelGenerationError:
            raise
        except Exception:
            raw_output = ""

        # Parse Characters
        characters: List[CharacterProfile] = []
        char_blocks = re.split(r"CHARACTER\s*\d+\s*:", raw_output, flags=re.IGNORECASE)
        if len(char_blocks) > 1:
            for b in char_blocks[1:]:
                # Stop parsing if we hit SCENES
                body = re.split(r"(?:SCENES|SCENE\s*\d+\s*:)", b, flags=re.IGNORECASE)[0]
                name = ""
                job = ""
                attire = ""
                emotion = ""
                rel = ""
                for line in body.split("\n"):
                    ls = line.strip()
                    if ls.lower().startswith("name:"):
                        name = ls.split(":", 1)[-1].strip("[] \"'*")
                    elif ls.lower().startswith("job:") or ls.lower().startswith("role:"):
                        job = ls.split(":", 1)[-1].strip("[] \"'*")
                    elif ls.lower().startswith("attire:") or ls.lower().startswith("clothing:"):
                        attire = ls.split(":", 1)[-1].strip("[] \"'*")
                    elif ls.lower().startswith("emotion:") or ls.lower().startswith("stance:"):
                        emotion = ls.split(":", 1)[-1].strip("[] \"'*")
                    elif ls.lower().startswith("relationship:"):
                        rel = ls.split(":", 1)[-1].strip("[] \"'*")
                if name:
                    characters.append(CharacterProfile(
                        name=name,
                        role_or_job=job or "Key Witness / Participant",
                        attire=attire or "Authentic everyday attire",
                        emotional_stance=emotion or "Expressive and engaged",
                        relationship_dynamic=rel or "Co-participant in the story",
                    ))

        # Parse Scene Locations
        scenes: List[SceneSettingOption] = []
        scene_blocks = re.split(r"SCENE\s*(\d+)\s*:", raw_output, flags=re.IGNORECASE)
        if len(scene_blocks) > 1:
            for i in range(1, len(scene_blocks), 2):
                s_num = int(scene_blocks[i])
                s_body = scene_blocks[i + 1]
                loc_name = ""
                atmos = ""
                light = ""
                props_list: List[str] = []
                for line in s_body.split("\n"):
                    ls = line.strip()
                    if ls.lower().startswith("location:"):
                        loc_name = ls.split(":", 1)[-1].strip("[] \"'*")
                    elif ls.lower().startswith("atmosphere:") or ls.lower().startswith("setting:"):
                        atmos = ls.split(":", 1)[-1].strip("[] \"'*")
                    elif ls.lower().startswith("lighting:") or ls.lower().startswith("mood:"):
                        light = ls.split(":", 1)[-1].strip("[] \"'*")
                    elif ls.lower().startswith("props:"):
                        props_raw = ls.split(":", 1)[-1].strip("[] \"'*")
                        props_list = [p.strip() for p in props_raw.split(",") if p.strip()]

                if loc_name or atmos:
                    scenes.append(SceneSettingOption(
                        scene_option_number=s_num,
                        location_name=loc_name or f"Setting Option {s_num}",
                        atmosphere=atmos or "Authentic Indian setting atmosphere",
                        lighting_mood=light or "Cinematic natural lighting",
                        props=props_list or (verification.physical_props[:3] if verification and verification.physical_props else ["Key props"]),
                    ))

        # Deterministic domain-grounded fallback if LLM returned insufficient characters
        if len(characters) < target_char_count:
            raw_personas = get_character_personas(
                scene_style=scene_style,
                character_count=target_char_count,
                tone=tone,
                angle=angle,
                topic_or_script=news_topic,
                sample_story=sample_story or scenario,
            )
            existing_names = {c.name.lower() for c in characters}
            for p in raw_personas:
                if len(characters) >= target_char_count:
                    break
                clean_p = p.split("(")[0].strip()
                if clean_p.lower() not in existing_names:
                    role = "Primary Speaker" if "1" in p or "Neha" in p or "Priya" in p else "Counterpart / Witness"
                    characters.append(CharacterProfile(
                        name=p,
                        role_or_job=role,
                        attire=get_character_attire(clean_p, locs_text),
                        emotional_stance="Engaged & authentic",
                        relationship_dynamic="Relational counterparts debating the news development",
                    ))
                    existing_names.add(clean_p.lower())

        # Fallback scene options if LLM returned insufficient scenes
        if len(scenes) < target_scene_count:
            known_locs = (verification.key_locations if verification and verification.key_locations else [])
            if not known_locs:
                known_locs = [
                    "Bustling roadside street food stall / tea tapri",
                    "Modern executive corner office overlooking city skyline",
                    "Cozy living room with news playing on television",
                    "Government administrative office corridor with notice board"
                ]
            while len(scenes) < target_scene_count:
                idx = len(scenes) + 1
                base_loc = known_locs[(idx - 1) % len(known_locs)]
                scenes.append(SceneSettingOption(
                    scene_option_number=idx,
                    location_name=f"{base_loc} (Option {idx})",
                    atmosphere=f"Vibrant and realistic ambient setting for {tone}",
                    lighting_mood="Cinematic natural lighting with high dynamic contrast",
                    props=verification.physical_props[:3] if verification and verification.physical_props else ["Key story props"],
                ))

        return characters, scenes

    def finalise_characters_and_story(
        self,
        news_topic: str,
        verification: NewsVerificationReport,
        scenario: str = "",
        sample_story: Optional[str] = None,
        tone: str = "Relatable Comedy",
        angle: str = "Funny & Relatable",
        character_count: int = 2,
        scene_style: str = "Dialogue",
        duration_sec: int = 30,
        sub_instruction: Optional[str] = None,
        engine_mode: str = "first_local_then_agy",
        previous_characters: Optional[List[Dict[str, Any]]] = None,
        previous_story_steps: Optional[List[Dict[str, Any]]] = None,
        feedback: Optional[str] = None,
    ) -> Tuple[List[CharacterProfile], List[StoryBeatStep], Tuple[str, str]]:
        """
        Backwards-compatible wrapper returning (characters, story_steps, (hook, cta)).
        """
        num_scenes = 1 if duration_sec <= 8 else (2 if duration_sec <= 15 else 3)
        characters, scenes = self.finalise_characters_and_scenes(
            news_topic=news_topic,
            verification=verification,
            scenario=scenario,
            sample_story=sample_story,
            tone=tone,
            angle=angle,
            character_count=character_count,
            num_scenes=num_scenes,
            scene_style=scene_style,
            duration_sec=duration_sec,
            sub_instruction=sub_instruction,
            engine_mode=engine_mode,
            previous_characters=previous_characters,
            previous_scenes=None,
            feedback=feedback,
        )

        # Build story steps from chosen characters and scene settings
        story_steps: List[StoryBeatStep] = []
        loc_desc = scenes[0].location_name if scenes else "Authentic setting"
        props_desc = ", ".join(scenes[0].props) if scenes and scenes[0].props else "Key props"

        for b_idx in range(1, num_scenes + 1):
            c = characters[(b_idx - 1) % len(characters)]
            if b_idx == 1:
                act_desc = f"Begins in {loc_desc}; {c.name} opens the situation interacting with {props_desc}"
                goal_desc = "Establish opening hook and relatable situation"
            elif b_idx == num_scenes:
                act_desc = f"{c.name} delivers final reaction and punchline payoff"
                goal_desc = "Deliver punchline or resolution"
            else:
                act_desc = f"{c.name} examines evidence and reacts to the verified news facts"
                goal_desc = "Reveal and challenge key facts"
            story_steps.append(StoryBeatStep(
                beat_number=b_idx,
                character_name=c.name,
                action_step=act_desc,
                speech_objective=goal_desc,
            ))

        default_cta = "फॉलो करें!" if duration_sec <= 10 else "शेयर करें और अपनी राय बताएं!"
        hook_cta = (f"🔥 {news_topic[:45]} को लेकर बड़ा अपडेट आ गया है!", default_cta)
        return characters, story_steps, hook_cta


# Export canonical class and backwards-compatible alias
HookAndAngleAgent = CharacterFinaliserAgent
character_finaliser = CharacterFinaliserAgent()
hook_strategist = character_finaliser
