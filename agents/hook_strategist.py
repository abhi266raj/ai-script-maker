"""Agent 2: Character Finalisation Strategist Agent (formerly Hook & Angle Strategist)."""

import re
from typing import Tuple, List, Optional, Dict, Any
from agents.base import BaseAgent
from core.models import NewsVerificationReport, CharacterProfile, SceneSettingOption, StoryBeatStep
from core.dual_engine import ModelGenerationError
from core.prompt_loader import load_prompt, render_prompt

CHARACTER_FINALISER_INSTRUCTIONS = load_prompt("hook_strategist/finalise_characters.md")


# ---------------------------------------------------------------------------
# Deterministic Stage 2 tapri guard.
# A tea-stall / chai-tapri location may only survive Stage 2 when the news
# itself is genuinely about a tea stall. Otherwise the location is neutralized
# to a story-grounded fallback. This runs on the FINALIZED scenes, so even a
# model that ignores the prompt ban cannot leak a tapri default downstream.
# ---------------------------------------------------------------------------
_TAPRI_LOCATION_RE = re.compile(
    r"tapri|tea[\s-]*(stall|shop|cart)|chai[\s-]*(tapri|stall|shop)|\u091f\u092a\u0930\u0940|\u091a\u093e\u092f\u0935\u093e\u0932\u093e",
    re.IGNORECASE,
)
_TAPRI_TOPICAL_RE = re.compile(
    r"\b(chai|tapri|chaiwala|chaywala|tea stall|tea vendor|tea shop|tea cart)\b|\u091a\u093e\u092f|\u091f\u092a\u0930\u0940",
    re.IGNORECASE,
)


def sanitize_scene_location(
    location_name: str,
    news_topic: str = "",
    sample_story: Optional[str] = None,
    fallback_location: str = "",
) -> str:
    """Return a tapri-free location.

    Keeps the location unchanged when it has no tapri reference, or when the
    news/sample is genuinely about a tea stall. Otherwise replaces it with
    ``fallback_location`` (a verified news location). Fails loudly when a
    non-topical tapri reference has no news-grounded replacement — inventing
    a neutral placeholder location is not allowed.
    """
    if not location_name or not _TAPRI_LOCATION_RE.search(location_name):
        return location_name
    combined = f"{news_topic or ''} {sample_story or ''}"
    if _TAPRI_TOPICAL_RE.search(combined):
        return location_name
    clean_fallback = (fallback_location or "").strip()
    if not clean_fallback:
        raise ModelGenerationError(
            "Scene location was a non-topical tea-stall/tapri reference and no "
            "news-grounded replacement location was available. Refusing to invent "
            f"a placeholder location. News topic: {(news_topic or '')[:200]!r}. "
            f"Original location: {location_name[:200]!r}"
        )
    return clean_fallback


def validate_scene_locations(
    scenes: List["SceneSettingOption"],
    news_topic: str = "",
    sample_story: Optional[str] = None,
    fallback_location: str = "",
) -> Tuple[List["SceneSettingOption"], int]:
    """Sanitize every finalized scene; returns (scenes, replaced_count)."""
    cleaned: List["SceneSettingOption"] = []
    replaced = 0
    for s in scenes:
        loc = getattr(s, "location_name", "") or ""
        clean_loc = sanitize_scene_location(loc, news_topic, sample_story, fallback_location)
        if clean_loc != loc:
            replaced += 1
            try:
                s = s.model_copy(update={"location_name": clean_loc})
            except Exception:
                s = SceneSettingOption(
                    scene_option_number=getattr(s, "scene_option_number", 1),
                    location_name=clean_loc,
                    atmosphere=getattr(s, "atmosphere", ""),
                    lighting_mood=getattr(s, "lighting_mood", ""),
                    props=list(getattr(s, "props", []) or []),
                )
        cleaned.append(s)
    return cleaned, replaced


class CharacterFinaliserAgent(BaseAgent):
    """
    Lead Character & Scene Finalisation Strategist.
    Analyzes Stage 1 news dossier and produces a rich 2X pool of grounded characters
    and 2 freshly imagined scene locations for this story (never a generic pool).
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
        except Exception as e:
            # Fail loudly: never substitute a template hook when the engine itself failed.
            raise ModelGenerationError(
                f"Stage 2 failed: hook generation engine error ({type(e).__name__}): {e}. "
                f"News topic: {news_topic[:200]!r}"
            ) from e

        hook = ""
        cta = ""

        for line in raw_output.split("\n"):
            line_str = line.strip()
            if line_str.startswith("HOOK:"):
                hook = line_str.replace("HOOK:", "").strip("[] \"'\"")
            elif line_str.startswith("CTA:"):
                cta = line_str.replace("CTA:", "").strip("[] \"'\"")

        if not hook:
            raise ModelGenerationError(
                "Stage 2 failed: hook model returned no parseable HOOK: line. "
                f"News topic: {news_topic[:200]!r}. Raw output snippet: {(raw_output or '')[:300]!r}"
            )
        if not cta:
            raise ModelGenerationError(
                "Stage 2 failed: hook model returned no parseable CTA: line. "
                f"News topic: {news_topic[:200]!r}. Raw output snippet: {(raw_output or '')[:300]!r}"
            )

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
        except Exception as e:
            # Fail loudly: never substitute template hooks when the engine itself failed.
            raise ModelGenerationError(
                f"Stage 2 failed: hooks batch generation engine error ({type(e).__name__}): {e}. "
                f"News topic: {news_topic[:200]!r}"
            ) from e

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
                        h = ls.replace("HOOK:", "").strip("[] \"'\"")
                    elif ls.startswith("CTA:"):
                        c = ls.replace("CTA:", "").strip("[] \"'\"")
                if h and c:
                    parsed_map[idx] = (h, c)

        # Fail loudly: every angle must get a model-generated hook/CTA.
        # Never substitute template hooks for angles the model skipped.
        missing = [i for i in range(len(angles)) if i not in parsed_map]
        if missing:
            raise ModelGenerationError(
                f"Stage 2 failed: hooks batch model returned no parseable HOOK/CTA for angle(s) "
                f"{[i + 1 for i in missing]} of {len(angles)}. "
                f"Raw output snippet: {(raw_output or '')[:400]!r}"
            )
        results = [parsed_map[i] for i in range(len(angles))]

        return results

    def finalise_characters_and_scenes(
        self,
        news_topic: str,
        verification: NewsVerificationReport,
        scenario: str = "",
        sample_story: Optional[str] = None,
        tone: str = "Joke",
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
        include_scenes: bool = True,
    ) -> Tuple[List[CharacterProfile], List[SceneSettingOption]]:
        """
        Stage 2: Finalize 2X character profiles and (optionally) 2 freshly
        imagined scene locations.

        When include_scenes=False (new pipeline order), only characters are
        finalized — scene locations are NOT imagined upfront. They are derived
        FROM the finalized dialogue afterwards by derive_scenes_from_dialogue,
        so scenes can never be disconnected from what the dialogue shows.
        """
        import json

        # Request 2X characters; exactly 2 imagined scene locations per story.
        target_char_count = max(2, character_count * 2)
        target_scene_count = 2

        facts_text = "\n".join([f"- {f}" for f in (verification.verified_facts if verification else [])[:4]])
        props_text = ", ".join(verification.physical_props) if (verification and verification.physical_props) else ""
        locs_text = ", ".join(verification.key_locations) if (verification and verification.key_locations) else ""
        conflict_text = verification.core_conflict_or_irony if (verification and verification.core_conflict_or_irony) else ""

        scenario_directive = f"Creative Scenario / Guidance:\n{scenario}\n" if scenario and scenario.strip() else ""
        sub_directive = f"Chief Editor Directive:\n{sub_instruction}\n" if sub_instruction and sub_instruction.strip() else ""

        revision_directive = ""
        if (previous_characters or (previous_scenes and include_scenes)) and feedback and feedback.strip():
            prev_chars_str = json.dumps(previous_characters or [], ensure_ascii=False, indent=2)
            prev_scenes_str = json.dumps(previous_scenes or [], ensure_ascii=False, indent=2)
            revision_directive = (
                f"\n# 🔄 REVISION & CORRECTION MODE (HIGH PRIORITY):\n"
                f"You are REVISING previously finalized characters"
                f"{' and scene locations' if include_scenes else ''} based on user feedback.\n\n"
                f"PREVIOUS CHARACTERS:\n{prev_chars_str}\n\n"
                + (f"PREVIOUS SCENES:\n{prev_scenes_str}\n\n" if include_scenes else "")
                + f"USER CORRECTION FEEDBACK:\n{feedback.strip()}\n\n"
                f"CORRECTION MANDATE:\n"
                f"- Directly update characters (names, jobs, attire)"
                f"{' and scene locations' if include_scenes else ''} to resolve the user's critique.\n"
            )

        prompt = render_prompt(
            "hook_strategist/finalise_characters_only.md" if not include_scenes else "hook_strategist/finalise_characters.md",
            news_topic=news_topic,
            duration_sec=duration_sec,
            tone=tone,
            angle=angle,
            scene_style=scene_style,
            requested_char_count=character_count,
            target_char_count=target_char_count,
            requested_scene_count=num_scenes,
            target_scene_count=target_scene_count,
            setting_location=locs_text or "(none verified)",
            physical_props=props_text or "(none verified)",
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
        except Exception as e:
            # Fail loudly: never parse empty output into template characters.
            raise ModelGenerationError(
                f"Stage 2 failed: character finalisation engine error ({type(e).__name__}): {e}. "
                f"News topic: {news_topic[:200]!r}"
            ) from e

        # --- Robust parsing: normalize common model formatting quirks first ---
        norm_output = raw_output or ""
        # Models often emit markdown bold/italics (e.g. **Name:**) — strip them.
        norm_output = norm_output.replace("**", "").replace("__", "")
        # Strip markdown heading markers at line starts ("### CHARACTER 1:" -> "CHARACTER 1:")
        norm_output = re.sub(r"(?m)^\s*#{1,6}\s*", "", norm_output)

        # Split the output into a characters region and a scenes region so that a
        # "scene 2" mention inside a character description can never corrupt parsing.
        scenes_header = re.search(r"(?im)^\s*SCENES\b.*$", norm_output)
        if scenes_header:
            chars_region = norm_output[:scenes_header.start()]
            scenes_region = norm_output[scenes_header.end():]
        else:
            chars_region, scenes_region = norm_output, norm_output

        def _clean_field_line(line: str) -> str:
            """Remove list/emphasis markers so '• **Name:** X' parses like 'Name: X'."""
            ls = line.strip()
            ls = re.sub(r"^[\s>*•\-–—]+", "", ls)  # bullets / quote markers
            ls = re.sub(r"^\d+[.)]\s*", "", ls)     # '1.' / '1)' prefixes
            return ls.strip("*_`").strip()

        def _field_value(ls: str) -> str:
            return ls.split(":", 1)[-1].strip("[] \"'*").strip()

        # Parse Characters
        characters: List[CharacterProfile] = []
        char_blocks = re.split(r"CHARACTER\s*\d+\s*[:\-–—]", chars_region, flags=re.IGNORECASE)
        if len(char_blocks) > 1:
            for b in char_blocks[1:]:
                name = ""
                job = ""
                attire = ""
                emotion = ""
                rel = ""
                for line in b.split("\n"):
                    ls = _clean_field_line(line)
                    low = ls.lower()
                    if low.startswith("name:"):
                        name = _field_value(ls)
                    elif low.startswith("job:") or low.startswith("role:"):
                        job = _field_value(ls)
                    elif low.startswith("attire:") or low.startswith("clothing:") or low.startswith("appearance:"):
                        attire = _field_value(ls)
                    elif low.startswith("emotion:") or low.startswith("stance:") or low.startswith("attitude:"):
                        emotion = _field_value(ls)
                    elif low.startswith("relationship:") or low.startswith("relation:") or low.startswith("dynamic:"):
                        rel = _field_value(ls)
                if name:
                    if not job:
                        raise ModelGenerationError(
                            "Stage 2 failed: character finalisation returned a character "
                            f"({name!r}) with no Job/Role, but the output contract requires "
                            "a specific profession/role for every character. "
                            f"Character block snippet: {b[:300]!r}"
                        )
                    characters.append(CharacterProfile(
                        name=name,
                        role_or_job=job,
                        attire=(attire or "").strip(),
                        emotional_stance=emotion or "",
                        relationship_dynamic=rel or "",
                    ))

        # Parse Scene Locations — skipped entirely when include_scenes=False
        # (new pipeline order: scenes are derived FROM the finalized dialogue).
        scenes: List[SceneSettingOption] = []
        scene_blocks = (
            re.split(r"SCENE\s*(\d+)\s*[:\-–—]", scenes_region, flags=re.IGNORECASE)
            if include_scenes
            else []
        )
        if len(scene_blocks) > 1:
            for i in range(1, len(scene_blocks), 2):
                s_num = int(scene_blocks[i])
                s_body = scene_blocks[i + 1]
                loc_name = ""
                atmos = ""
                light = ""
                props_list: List[str] = []
                for line in s_body.split("\n"):
                    ls = _clean_field_line(line)
                    low = ls.lower()
                    if low.startswith("location:"):
                        loc_name = _field_value(ls)
                    elif low.startswith("atmosphere:") or low.startswith("setting:"):
                        atmos = _field_value(ls)
                    elif low.startswith("lighting:") or low.startswith("mood:"):
                        light = _field_value(ls)
                    elif low.startswith("props:"):
                        props_raw = _field_value(ls)
                        props_list = [p.strip(" *") for p in props_raw.split(",") if p.strip(" *")]

                if loc_name or atmos:
                    scenes.append(SceneSettingOption(
                        scene_option_number=s_num,
                        location_name=loc_name or f"Setting Option {s_num}",
                        atmosphere=atmos or "",
                        lighting_mood=light or "",
                        props=props_list or (verification.physical_props[:3] if verification and verification.physical_props else []),
                    ))

        # Fail loudly: never top up with template personas when the model
        # returned fewer characters than requested. Surface the shortfall.
        if len(characters) < target_char_count:
            raise ModelGenerationError(
                f"Stage 2 failed: character finalisation parsed {len(characters)} characters "
                f"but {target_char_count} were requested. "
                f"Raw output snippet: {(raw_output or '')[:500]!r}"
            )

        # Fail loudly: attire is a required field — never dress characters in a
        # silent generic default when the model omits it.
        _missing_attire = [c.name for c in characters if not (c.attire or "").strip()]
        if _missing_attire:
            raise ModelGenerationError(
                f"Stage 2 failed: characters missing attire — {', '.join(_missing_attire)}. "
                "Every character must have specific, job/news-appropriate clothing. "
                f"Raw output snippet: {(raw_output or '')[:500]!r}"
            )

        # Fail loudly: never substitute template scenes when the model returned
        # fewer scenes than requested. Surface the exact shortfall instead.
        if include_scenes and len(scenes) < target_scene_count:
            raise ModelGenerationError(
                f"Stage 2 failed: scene finalisation parsed {len(scenes)} scenes "
                f"but {target_scene_count} were requested. "
                f"Raw output snippet: {(raw_output or '')[:500]!r}"
            )

        # Deterministic Stage 2 guard: neutralize any tapri/tea-stall location
        # that is not genuinely topical to this news story.
        # Skipped when include_scenes=False (no scenes to guard).
        if include_scenes:
            ver_fallback = ""
            try:
                if verification and getattr(verification, "key_locations", None):
                    ver_fallback = (verification.key_locations or [""])[0] or ""
            except Exception:
                ver_fallback = ""
            scenes, _tapri_replaced = validate_scene_locations(
                scenes,
                news_topic=news_topic,
                sample_story=sample_story,
                fallback_location=ver_fallback,
            )

        return characters, scenes

    def finalise_character_groups(
        self,
        news_topic: str,
        verification: NewsVerificationReport,
        scenario: str = "",
        sample_story: Optional[str] = None,
        tone: str = "Joke",
        angle: str = "Funny & Relatable",
        character_count: int = 2,
        scene_style: str = "Dialogue",
        duration_sec: int = 30,
        sub_instruction: Optional[str] = None,
        engine_mode: str = "first_local_then_agy",
        previous_groups: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        feedback: Optional[str] = None,
    ) -> Tuple[List[CharacterProfile], List[CharacterProfile]]:
        """Stage 2: Propose TWO DISTINCT character groups (A and B).

        The user picks ONE group for dialogue — no random selection.
        Each group is a complete, coherent cast of `character_count` characters.
        The groups must be distinctly different (professions, perspectives, dynamics).
        """
        import json

        facts_text = "\n".join([f"- {f}" for f in (verification.verified_facts if verification else [])[:4]])
        props_text = ", ".join(verification.physical_props) if (verification and verification.physical_props) else ""
        locs_text = ", ".join(verification.key_locations) if (verification and verification.key_locations) else ""
        conflict_text = verification.core_conflict_or_irony if (verification and verification.core_conflict_or_irony) else ""

        scenario_directive = f"Creative Scenario / Guidance:\n{scenario}\n" if scenario and scenario.strip() else ""
        sub_directive = f"Chief Editor Directive:\n{sub_instruction}\n" if sub_instruction and sub_instruction.strip() else ""

        revision_directive = ""
        if previous_groups and feedback and feedback.strip():
            prev_str = json.dumps(previous_groups, ensure_ascii=False, indent=2)
            revision_directive = (
                f"\n# 🔄 REVISION & CORRECTION MODE (HIGH PRIORITY):\n"
                f"You are REVISING the previously proposed character groups based on user feedback.\n\n"
                f"PREVIOUS GROUPS:\n{prev_str}\n\n"
                f"USER CORRECTION FEEDBACK:\n{feedback.strip()}\n\n"
                f"CORRECTION MANDATE:\n"
                f"- Directly update the groups to resolve the user's critique.\n"
                f"- Keep what works; change only what the feedback targets.\n"
            )

        prompt = render_prompt(
            "hook_strategist/finalise_character_groups.md",
            news_topic=news_topic,
            duration_sec=duration_sec,
            tone=tone,
            angle=angle,
            scene_style=scene_style,
            requested_char_count=character_count,
            setting_location=locs_text or "(none verified)",
            physical_props=props_text or "(none verified)",
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
        except Exception as e:
            # Fail loudly: never substitute template personas when the engine itself failed.
            raise ModelGenerationError(
                f"Stage 2 failed: character groups generation engine error ({type(e).__name__}): {e}. "
                f"News topic: {news_topic[:200]!r}"
            ) from e

        # --- Robust parsing: normalize common model formatting quirks ---
        norm_output = (raw_output or "").replace("**", "").replace("__", "")
        norm_output = re.sub(r"(?m)^\s*#{1,6}\s*", "", norm_output)

        # Split into GROUP A and GROUP B sections
        group_a_match = re.search(r"(?im)^\s*GROUP\s*A\s*[:\-–—]?\s*$", norm_output)
        group_b_match = re.search(r"(?im)^\s*GROUP\s*B\s*[:\-–—]?\s*$", norm_output)

        def _parse_group(section_text: str) -> List[CharacterProfile]:
            chars: List[CharacterProfile] = []
            char_blocks = re.split(r"CHARACTER\s*\d+\s*[:\-–—]", section_text, flags=re.IGNORECASE)
            for b in char_blocks[1:]:
                name = job = attire = emotion = rel = ""
                for line in b.split("\n"):
                    ls = line.strip()
                    ls = re.sub(r"^[\s>*•\-–—]+", "", ls)
                    ls = re.sub(r"^\d+[.)]\s*", "", ls)
                    ls = ls.strip("*_`").strip()
                    low = ls.lower()
                    if ":" not in ls:
                        continue
                    val = ls.split(":", 1)[-1].strip("[] \"'*").strip()
                    if low.startswith("name:"):
                        name = val
                    elif low.startswith("job:") or low.startswith("role:"):
                        job = val
                    elif low.startswith("attire:") or low.startswith("clothing:") or low.startswith("appearance:"):
                        attire = val
                    elif low.startswith("emotion:") or low.startswith("stance:") or low.startswith("attitude:"):
                        emotion = val
                    elif low.startswith("relationship:") or low.startswith("relation:") or low.startswith("dynamic:"):
                        rel = val
                if name:
                    if not job:
                        raise ModelGenerationError(
                            "Stage 2 failed: character finalisation returned a character "
                            f"({name!r}) with no Job/Role, but the output contract requires "
                            "a specific profession/role for every character. "
                            f"Character block snippet: {b[:300]!r}"
                        )
                    chars.append(CharacterProfile(
                        name=name,
                        role_or_job=job,
                        attire=(attire or "").strip(),
                        emotional_stance=emotion or "",
                        relationship_dynamic=rel or "",
                    ))
            return chars

        group_a: List[CharacterProfile] = []
        group_b: List[CharacterProfile] = []
        if group_a_match and group_b_match:
            a_start = group_a_match.end()
            b_start = group_b_match.start()
            b_end = group_b_match.end()
            group_a = _parse_group(norm_output[a_start:b_start])
            group_b = _parse_group(norm_output[b_end:])
        elif group_a_match:
            # Only Group A found — parse it, leave B empty for fallback
            group_a = _parse_group(norm_output[group_a_match.end():])

        # Fail loudly: never substitute template personas when the model output
        # cannot be parsed into complete character groups.
        if not group_a or not group_b:
            raise ModelGenerationError(
                f"Stage 2 failed: character groups parsing failed — got {len(group_a)} characters "
                f"in Group A and {len(group_b)} in Group B (need {character_count} each). "
                f"Raw output snippet: {(raw_output or '')[:500]!r}"
            )

        # Fail loudly: attire is a required field — never dress characters in a
        # silent generic default when the model omits it.
        _missing_attire = [c.name for c in (group_a + group_b) if not (c.attire or "").strip()]
        if _missing_attire:
            raise ModelGenerationError(
                f"Stage 2 failed: characters missing attire — {', '.join(_missing_attire)}. "
                "Every character must have specific, job/news-appropriate clothing. "
                f"Raw output snippet: {(raw_output or '')[:500]!r}"
            )

        return group_a[:character_count], group_b[:character_count]

    def derive_scenes_from_dialogue(
        self,
        news_topic: str,
        verification: NewsVerificationReport,
        finalized_characters: List[CharacterProfile],
        dialogue_beats: List[Dict[str, Any]],
        num_scenes: int = 2,
        tone: str = "Joke",
        angle: str = "Funny & Relatable",
        scene_style: str = "Dialogue",
        duration_sec: int = 30,
        sub_instruction: Optional[str] = None,
        engine_mode: str = "first_local_then_agy",
        previous_scenes: Optional[List[Dict[str, Any]]] = None,
        feedback: Optional[str] = None,
    ) -> List[SceneSettingOption]:
        """
        SECOND strategist invocation (new Stage 4).

        Derives shoot locations FROM the finalized Stage 3 dialogue beats -
        every scene must be traceable to specific beats. This is what keeps
        scenes connected to the dialogue instead of being imagined upfront
        and disconnected. Fails loudly (ModelGenerationError) when the model
        call fails or the output cannot be parsed - never falls back to
        silent generic scenes.
        """
        import json

        if not dialogue_beats:
            raise ModelGenerationError(
                "Stage 4 failed (hook_strategist.derive_scenes_from_dialogue): "
                "cannot derive scenes — no finalized dialogue beats were provided. "
                "Stage 3 must complete before scene derivation."
            )

        beat_lines: List[str] = []
        for i, b in enumerate(dialogue_beats, start=1):
            speaker = b.get("speaker") or b.get("character") or f"Speaker {i}"
            dialogue = b.get("dialogue") or b.get("spoken") or ""
            action = b.get("action") or b.get("camera_action") or b.get("camera_focus_action") or ""
            beat_lines.append(
                f"BEAT {i} | {speaker}: \"{dialogue}\""
                + (f" | Camera/Action: {action}" if action else "")
            )
        dialogue_text = "\n".join(beat_lines)

        chars_text = "\n".join(
            f"- {c.name} ({c.role_or_job}): {c.attire}; stance: {c.emotional_stance}"
            for c in (finalized_characters or [])
        ) or "- (no characters finalized)"

        locs_text = ", ".join(verification.key_locations) if verification and verification.key_locations else ""
        props_text = ", ".join(verification.physical_props) if verification and verification.physical_props else ""

        sub_directive = ""
        if sub_instruction and sub_instruction.strip():
            sub_directive = f"\n# CHIEF EDITOR SUB-INSTRUCTION (authoritative):\n{sub_instruction.strip()}\n"

        revision_directive = ""
        if previous_scenes and feedback and feedback.strip():
            prev_str = json.dumps(previous_scenes, ensure_ascii=False, indent=2)
            revision_directive = (
                f"\n# REVISION & CORRECTION MODE (HIGH PRIORITY):\n"
                f"You are REVISING previously derived scenes based on user feedback.\n\n"
                f"PREVIOUS SCENES:\n{prev_str}\n\n"
                f"USER CORRECTION FEEDBACK:\n{feedback.strip()}\n\n"
                f"CORRECTION MANDATE:\n"
                f"- Keep every scene grounded in the dialogue beats; fix what the user flagged.\n"
            )

        prompt = render_prompt(
            "hook_strategist/derive_scenes_from_dialogue.md",
            news_topic=news_topic,
            num_scenes=num_scenes,
            tone=tone,
            angle=angle,
            scene_style=scene_style,
            characters_text=chars_text,
            physical_props=props_text or "(none verified)",
            key_locations=locs_text or "(none verified)",
            dialogue_text=dialogue_text,
            sub_directive=sub_directive,
            revision_directive=revision_directive,
        )

        try:
            raw_output = self.execute(prompt, engine_mode=engine_mode)
        except ModelGenerationError:
            raise
        except Exception as e:
            raise ModelGenerationError(
                "Stage 4 failed (hook_strategist.derive_scenes_from_dialogue): "
                f"model call failed while deriving scenes from dialogue: {type(e).__name__}: {e}"
            ) from e

        norm_output = (raw_output or "").replace("**", "").replace("__", "")
        norm_output = re.sub(r"(?m)^\s*#{1,6}\s*", "", norm_output)

        def _clean(line: str) -> str:
            ls = line.strip()
            ls = re.sub(r"^[\s>*•\-–—]+", "", ls)
            ls = re.sub(r"^\d+[.)]\s*", "", ls)
            return ls.strip("*_`").strip()

        def _val(ls: str) -> str:
            return ls.split(":", 1)[-1].strip("[] \"'*").strip()

        scenes: List[SceneSettingOption] = []
        scene_blocks = re.split(r"SCENE\s*(\d+)\s*[:\-–—]", norm_output, flags=re.IGNORECASE)
        if len(scene_blocks) > 1:
            for i in range(1, len(scene_blocks), 2):
                s_num = int(scene_blocks[i])
                s_body = scene_blocks[i + 1]
                loc_name = ""
                atmos = ""
                light = ""
                props_list: List[str] = []
                beats_ref = ""
                for line in s_body.split("\n"):
                    ls = _clean(line)
                    low = ls.lower()
                    if low.startswith("location:"):
                        loc_name = _val(ls)
                    elif low.startswith("atmosphere:") or low.startswith("setting:"):
                        atmos = _val(ls)
                    elif low.startswith("lighting:") or low.startswith("mood:"):
                        light = _val(ls)
                    elif low.startswith("props:"):
                        props_list = [p.strip(" *") for p in _val(ls).split(",") if p.strip(" *")]
                    elif low.startswith("grounded in beats:"):
                        beats_ref = _val(ls)
                if loc_name or atmos:
                    scenes.append(SceneSettingOption(
                        scene_option_number=s_num,
                        location_name=loc_name or f"Dialogue-derived setting {s_num}",
                        atmosphere=atmos or "",
                        lighting_mood=light or "",
                        props=props_list or (verification.physical_props[:3] if verification and verification.physical_props else []),
                    ))

        if len(scenes) < num_scenes:
            snippet = (raw_output or "")[:600]
            raise ModelGenerationError(
                "Stage 4 failed (hook_strategist.derive_scenes_from_dialogue): "
                f"model returned {len(scenes)} parseable scenes (needed {num_scenes}). "
                f"Raw output snippet: {snippet!r}"
            )

        scenes = scenes[:num_scenes]

        ver_fallback = ""
        try:
            if verification and getattr(verification, "key_locations", None):
                ver_fallback = (verification.key_locations or [""])[0] or ""
        except Exception:
            ver_fallback = ""
        scenes, _tapri_replaced = validate_scene_locations(
            scenes,
            news_topic=news_topic,
            sample_story=None,
            fallback_location=ver_fallback,
        )
        return scenes

    def derive_scene_options(
        self,
        news_topic: str,
        verification: NewsVerificationReport,
        finalized_characters: List[CharacterProfile],
        dialogue_beats: List[Dict[str, Any]],
        num_scenes: int = 2,
        tone: str = "Joke",
        angle: str = "Funny & Relatable",
        scene_style: str = "Dialogue",
        duration_sec: int = 30,
        sub_instruction: Optional[str] = None,
        engine_mode: str = "first_local_then_agy",
        previous_options: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        feedback: Optional[str] = None,
    ) -> Tuple[List[SceneSettingOption], List[SceneSettingOption]]:
        """Stage 4: Derive TWO DISTINCT scene sets (A and B) from dialogue.

        The user picks ONE set — no random selection, no repetition.
        Each set is very imaginative, grounded in the dialogue's story.
        The two sets must be genuinely different creative visions.
        """
        import json

        if not dialogue_beats:
            raise ModelGenerationError(
                "Stage 4 scene derivation requires finalized dialogue beats — none provided."
            )

        # Build dialogue text for the prompt
        dialogue_text = "\n".join(
            f"Beat {i+1} ({b.get('character', '?')}): {b.get('dialogue', '')[:120]}"
            f"\n  Action: {b.get('action', '')[:120]}"
            for i, b in enumerate(dialogue_beats)
        )
        characters_text = "\n".join(
            f"- {c.name} ({c.role_or_job}): {c.emotional_stance}"
            for c in (finalized_characters or [])
        )
        props_text = ", ".join(verification.physical_props[:5]) if (verification and verification.physical_props) else ""
        locs_text = ", ".join(verification.key_locations[:3]) if (verification and verification.key_locations) else ""
        facts_text = "\n".join([f"- {f}" for f in (verification.verified_facts if verification else [])[:4]])

        sub_directive = f"Chief Editor Directive:\n{sub_instruction}\n" if sub_instruction and sub_instruction.strip() else ""
        revision_directive = ""
        if previous_options and feedback and feedback.strip():
            prev_str = json.dumps(previous_options, ensure_ascii=False, indent=2)
            revision_directive = (
                f"\n# 🔄 REVISION MODE:\nPrevious scene sets:\n{prev_str}\n\n"
                f"USER FEEDBACK:\n{feedback.strip()}\n\n"
                f"Revise the sets to address the feedback. Keep what works.\n"
            )

        prompt = render_prompt(
            "hook_strategist/derive_scene_options.md",
            news_topic=news_topic,
            tone=tone,
            angle=angle,
            scene_style=scene_style,
            num_scenes=num_scenes,
            characters_text=characters_text or "(none provided)",
            physical_props=props_text or "(none verified)",
            key_locations=locs_text or "(none verified)",
            verified_facts=facts_text or "No verified facts available",
            dialogue_text=dialogue_text,
            sub_directive=sub_directive,
            revision_directive=revision_directive,
        )

        try:
            raw_output = self.execute(prompt, engine_mode=engine_mode)
        except ModelGenerationError:
            raise
        except Exception as e:
            raise ModelGenerationError(f"Stage 4 scene options generation failed: {e}")

        # Parse SET A and SET B
        norm_output = (raw_output or "").replace("**", "").replace("__", "")
        norm_output = re.sub(r"(?m)^\s*#{1,6}\s*", "", norm_output)

        set_a_match = re.search(r"(?im)^\s*SET\s*A\s*[:\-–—]?\s*$", norm_output)
        set_b_match = re.search(r"(?im)^\s*SET\s*B\s*[:\-–—]?\s*$", norm_output)

        def _parse_set(section_text: str) -> List[SceneSettingOption]:
            scenes: List[SceneSettingOption] = []
            scene_blocks = re.split(r"SCENE\s*(\d+)\s*[:\-–—]", section_text, flags=re.IGNORECASE)
            for i in range(1, len(scene_blocks), 2):
                try:
                    s_num = int(scene_blocks[i])
                except (ValueError, IndexError):
                    s_num = len(scenes) + 1
                s_body = scene_blocks[i + 1]
                loc = atmos = light = ""
                props: List[str] = []
                beats_ref = ""
                for line in s_body.split("\n"):
                    ls = line.strip()
                    ls = re.sub(r"^[\s>*•\-–—]+", "", ls).strip("*_`").strip()
                    low = ls.lower()
                    if ":" not in ls:
                        continue
                    val = ls.split(":", 1)[-1].strip("[] \"'*").strip()
                    if low.startswith("location:"):
                        loc = val
                    elif low.startswith("atmosphere:"):
                        atmos = val
                    elif low.startswith("lighting:"):
                        light = val
                    elif low.startswith("props:"):
                        props = [p.strip() for p in val.split(",") if p.strip()]
                    elif low.startswith("grounded in beats:") or low.startswith("beats:"):
                        beats_ref = val
                if loc or atmos:
                    scenes.append(SceneSettingOption(
                        scene_option_number=s_num,
                        location_name=loc or f"Scene {s_num}",
                        atmosphere=atmos or "",
                        lighting_mood=light or "",
                        props=props or [],
                    ))
            return scenes

        set_a: List[SceneSettingOption] = []
        set_b: List[SceneSettingOption] = []
        if set_a_match and set_b_match:
            set_a = _parse_set(norm_output[set_a_match.end():set_b_match.start()])
            set_b = _parse_set(norm_output[set_b_match.end():])
        elif set_a_match:
            set_a = _parse_set(norm_output[set_a_match.end():])

        if not set_a or not set_b:
            raise ModelGenerationError(
                f"Stage 4 scene options parsing failed: got {len(set_a)} scenes in Set A, "
                f"{len(set_b)} in Set B (need {num_scenes} each). Raw output snippet: {(raw_output or '')[:200]}"
            )

        return set_a[:num_scenes], set_b[:num_scenes]

# Export canonical class and backwards-compatible alias
HookAndAngleAgent = CharacterFinaliserAgent
character_finaliser = CharacterFinaliserAgent()
hook_strategist = character_finaliser
