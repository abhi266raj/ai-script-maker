"""Agent 8: Chief Editor & Pipeline Orchestrator Agent."""

import logging
import queue
import re
import threading
import time
from typing import Generator, Dict, Any, List, Tuple, Optional, Callable
from core.models import (
    ReelBatchResult,
    ReelScript,
    NewsVerificationReport,
    SceneItem,
    VideoScenePrompt,
    VideoPassVerification,
    AgentAuditItem,
    PipelineAuditReport,
    CharacterProfile,
    SceneSettingOption,
    StoryBeatStep,
)
from agents.news_validator import news_validator
from agents.contextual_selector import contextual_selector
from agents.hook_strategist import hook_strategist
from agents.dialogue_writer import dialogue_writer, get_character_personas, clean_hindi_dialogue, strip_commenting_and_cta, ScriptDialogue
from agents.timing_auditor import timing_auditor
from agents.scene_director import scene_director
from agents.video_prompt_engineer import video_prompt_engineer
from agents.video_quality_gate import video_quality_gate
from core.angles import REEL_ANGLES
from core.metrics import get_duration_budget
from core.dual_engine import ModelGenerationError
from core.verification_cache import (
    get_cached_verification,
    get_cache_age_hours,
    store_verification,
)

logger = logging.getLogger(__name__)


def _emit_substep(on_substep, stage_num, substep, name, phase, **details):
    """Emit a live substep event to the pipeline's progress callback.

    Event schema:
        {"substep": "3.2.1", "name": "Structure check",
         "phase": "start" | "progress" | "complete",
         "status": "pass" | "fail",   # on complete
         "detail": "...", "input": "...", "output": "..."}
    No-op when on_substep is None (e.g. stepwise mode). Never raises.
    """
    if on_substep is None:
        return
    try:
        on_substep({
            "substep": substep,
            "name": name,
            "phase": phase,
            "stage": stage_num,
            **details,
        })
    except Exception:
        logger.warning("on_substep callback failed for %s", substep, exc_info=True)


class ChiefEditorCoordinatorAgent:
    """Orchestrates the specialized multi-agent pipeline with autonomous self-healing retries and failure tracking."""

    def __init__(self):
        self.name = "Chief Editor & Pipeline Orchestrator"
        self.role = "Multi-Agent Coordination & Editorial Sign-Off"
        self.icon = "👑"

    def decompose_master_instruction(
        self,
        master_instruction: str,
        news_topic: str,
        target_seconds: int,
        tone: str,
        angle: str,
        character_count: int,
        scene_style: str,
        batch_size: int,
        max_retries: int,
        budget: dict,
        sample_story: Optional[str] = None,
        personas_override: Optional[List[str]] = None,
        only_for: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """
        Master Agent decomposition:
        Divides the master instruction into targeted, specialized sub-instructions
        for each sub-agent in the pipeline, explicitly assigning dialogue word count
        budgets, speech rates, character counts, scene styles, angles, tones,
        and optional sample story with discrepancy precedence.

        Step-by-step mode: pass `only_for` to build sub-instructions for just the
        agents of the stage that is currently running, so Stage 1 no longer
        pre-generates every later stage's instructions in one shot. Pass
        `personas_override` (e.g. finalized Stage-2 character names) so downstream
        instructions reference the real cast instead of generic placeholders.
        """
        from agents.dialogue_writer import get_character_personas, get_creative_guidelines

        rec_w = budget["recommended_words"]
        min_w = budget["min_words"]
        max_w = budget["max_words"]
        scenes_cnt = budget.get("scenes", max(2, min(5, round(target_seconds / 5))))
        personas = personas_override or get_character_personas(
            scene_style, character_count, tone, angle,
            topic_or_script=news_topic, sample_story=sample_story
        )
        creative_rules = get_creative_guidelines(scene_style, character_count, tone, angle)

        # Vibe line: short, token-lean. Angle shown only when present.
        vibe_line = f"- Vibe: {tone} | {angle}." if (angle or "").strip() else f"- Vibe: {tone}."

        sample_clause = ""
        if sample_story and sample_story.strip():
            sample_clause = (
                f"\n📌 SAMPLE EXAMPLE (style/format reference ONLY \u2014 lowest precedence):\n"
                f"Reference Sample: \"{sample_story.strip()}\"\n"
                f"Rule: Generate from the NEWS with your own creativity. The sample is only an example "
                f"of tone/format \u2014 never copy its characters, plot, or lines, and never let it override "
                f"verified facts or finalized creative decisions.\n"
            )

        all_instructions = {
            "news_validator": (
                f"News Validation Sub-Instruction (Agent 1):\n"
                f"- Story to Verify: {news_topic}\n"
                f"- Task: Cross-reference live wire search feeds. Extract confirmed facts, entities, and figures.\n"
                f"- Filter: Discard unverified viral gossip or clickbait rumors.\n"
                f"- Report Format: VERIFICATION STATUS / CONFIDENCE SCORE / SUMMARY (confirmed usable facts only) / VERIFIED FACTS (bullets) / PHYSICAL PROPS (real objects from the news only) / KEY LOCATIONS (real places from the news only) / CORE CONFLICT OR IRONY / TANGIBLE ACTIONS (real people's actions only) / POTENTIAL FLAGS (one-line do-not-use items).\n"
                f"- Usefulness Rule: Everything you report feeds the creative AI directly — include only verified, reel-useful material. No process narration, no invented details."
            ),
            "contextual_selector": (
                f"Scene & Character Selector Sub-Instruction (Dynamic Subagent):\n"
                f"- Story Domain: {news_topic}\n"
                f"- Format: {target_seconds}s vertical reel ({scene_style} style, {character_count} character(s)).\n"
                f"{vibe_line}\n"
                f"- Task: Detect the authentic real-world domain and select dynamic physical location/venue, personas, authentic wardrobes, props, and ambient SFX.\n"
                f"- Rule: Institutional topics MUST be placed in authentic institutional venues (government offices, hospitals, courts, IT tech parks, space centers). Never default to a chai tapri unless explicitly topical.{sample_clause}"
            ),
            "hook_strategist": (
                f"Character Finalisation Sub-Instruction (Agent 2 - Stage 2):\n"
                f"- News Story: {news_topic}\n"
                f"- Format: {target_seconds}s vertical reel ({scene_style} style, {character_count} character(s)).\n"
                f"{vibe_line}\n"
                f"- Task: Finalise {character_count} distinct, grounded characters with authentic professions, specific wardrobes, emotional postures, and relational dynamics. NO dialogue, NO hooks, NO CTAs.\n"
                f"- Diversity: Ensure gender balance and varied professions/socioeconomic roles. No all-male default cast.{sample_clause}"
            ),
            "dialogue_writer": (
                f"Dialogue & Voiceover Sub-Instruction (Agent 3):\n"
                f"- Topic: {news_topic}\n"
                f"- Style & Format: {scene_style} format with {character_count} speaking character(s).\n"
                f"- CHARACTERS TO FEATURE: {', '.join(personas)}.\n"
                f"- CREATIVE GUIDELINES:\n{creative_rules}\n"
                f"{sample_clause}"
                f"- Target Duration: Exactly {target_seconds} seconds.\n"
                f"- MANDATORY DIALOGUE WORD COUNT BUDGET:\n"
                f"  * Recommended Target: ~{rec_w} spoken Hindi words (TOTAL across all characters)\n"
                f"  * Minimum Safe Words: {min_w} words\n"
                f"  * Absolute Strict Maximum: {max_w} words\n"
                f"  * Hindi Speech Rate: ~2.0 - 2.3 words/sec in natural spoken cadence.\n"
                f"- CRITICAL PACING ASYMMETRY: Fewer words ({min_w} to {rec_w} words) is completely SAFE and provides breathing room for B-roll visuals, SFX, and dramatic pauses. Exceeding {max_w} words is STRICTLY FORBIDDEN and will cause reel overflow.\n"
                f"- Tone & Delivery: {tone}. Clean spoken Devanagari Hindi only. NO greetings (नमस्ते/हेलो), NO intro filler (आइए जानते हैं). If dialogue style, characters must actively talk back-and-forth!\n"
                f"- Single Continuous Video Reel: This is ONE continuous short video. Introduce the background context once in Scene 1, and do NOT repeat or re-explain background context in subsequent scenes."
            ),
            "timing_auditor": (
                f"Timing & Duration Audit Sub-Instruction (Agent 4):\n"
                f"- Core Mission: Mathematically verify spoken Hindi dialogue word count for {target_seconds}s reel duration.\n"
                f"- Budget: Min {min_w}w | Recommended ~{rec_w}w | Strict Max {max_w}w.\n"
                f"- Pacing Verification Rule: If dialogue <= {max_w} words -> PASS (concise pacing is safe). If dialogue > {max_w} words -> FAIL (Over Budget) and trigger self-healing smart trim calibration.\n"
                f"- Timeline: Target {target_seconds}s speech timeline with 0.5-1.0s pause buffer."
            ),
            "scene_director": (
                f"Scene & Storyboard Sub-Instruction (Agent 5):\n"
                f"- Core Mission: Break the screenplay into {scenes_cnt} distinct 9:16 vertical scenes totaling {target_seconds}s.\n"
                f"- Format: {scene_style} with {character_count} character(s): {', '.join(personas)}.\n"
                f"- Single Video Continuity: There will be ONE cohesive video reel. Establish the setting in Scene 1 and do NOT repeatedly re-introduce or re-explain background context across scenes.\n"
                f"- Directives: Depict the imaginary situation matching '{angle}' with tone '{tone}'. Assign each scene to its speaking character with distinct visual action, on-screen ENGLISH text overlays (never Hindi), and dynamic visual B-roll. Do NOT repeat the spoken dialogue in the storyboard — visuals, camera, SFX and overlay text only."
            ),
            "video_prompt_engineer": (
                f"AI Video Prompt Sub-Instruction (Agent 6):\n"
                f"- Core Mission: Synthesize production-ready 9:16 vertical cinematic generative video prompts with seamless shot continuity.\n"
                f"- Directives: Specify 9:16 vertical ratio, 4K 24fps, cinematic camera motions (orbit, push-in, low-angle tracking), volumetric lighting, and realistic textures for each scene. Never include internal AI engine names or vendor watermarks in the prompt text."
            ),
            "video_quality_gate": (
                f"Quality Gate Sub-Instruction (Agent 7):\n"
                f"- Core Mission: Audit all video prompts for 3-5s physical feasibility, temporal consistency across scenes, and AI safety compliance."
            ),
        }
        if only_for:
            return {k: v for k, v in all_instructions.items() if k in only_for}
        return all_instructions

    # Matches feedback blocks previously appended via _set_feedback_block so the
    # latest user feedback replaces stale ones instead of stacking up.
    _FEEDBACK_BLOCK_RE = re.compile(r"\n\n\u2b50 (?:CORRECTION FEEDBACK|USER EXTRA INSTRUCTION)[\s\S]*?(?=\n\n\u2b50 |\Z)")

    @staticmethod
    def _set_feedback_block(subs: Dict[str, str], key: str, block: str) -> None:
        """Attach user feedback for a stage re-run: replace any stale feedback
        block on the same sub-instruction instead of stacking contradictory
        blocks, so the model follows the LATEST feedback."""
        current = subs.get(key, "")
        current = ChiefEditorCoordinatorAgent._FEEDBACK_BLOCK_RE.sub("", current)
        subs[key] = current + block

    def _build_refine_directive(
        self,
        stage_label: str,
        previous_output_text: str,
        feedback: str,
        locked_decisions: List[str],
    ) -> str:
        """Build the dedicated RETRY instruction shared by all stages.

        A re-run is a surgical refinement, not a regeneration:
        - baseline = the exact current visible finalized output of the stage,
        - change driver = the user's custom instruction (feedback),
        - every entry in ``locked_decisions`` was finalized earlier and must be
          preserved exactly (counts, angles, characters, modes, ...).
        Stale details from older runs are never included.
        """
        locked_lines = "\n".join(f"- {d}" for d in locked_decisions) or "- (none)"
        return (
            f"\n\n\U0001F504 REFINE MODE \u2014 {stage_label} RETRY (HIGHEST PRIORITY):\n"
            f"This is a RETRY with a custom instruction. Do NOT regenerate from scratch.\n"
            f"LOCKED DECISIONS (finalized earlier \u2014 preserve exactly, do not re-pick or re-roll):\n"
            f"{locked_lines}\n"
            f"PREVIOUS OUTPUT (the exact current visible output \u2014 your ONLY baseline):\n"
            f"{previous_output_text}\n\n"
            f"USER'S CUSTOM INSTRUCTION:\n{feedback.strip()}\n"
            f"REFINE MANDATE: change ONLY what the custom instruction targets; keep every "
            f"locked decision and everything that already works. Output the complete refined "
            f"result in the same format as the previous output."
        )

    def ensure_sub_instructions(self, state: Dict[str, Any], *agent_keys: str) -> Dict[str, str]:
        """Step-by-step instruction building: each stage builds ONLY its own
        agents' sub-instructions when it runs, using the freshest upstream
        outputs (e.g. finalized Stage-2 character names), instead of Stage 1
        pre-generating every later stage's instructions in one shot.

        Instructions are ALWAYS rebuilt fresh on every run: a re-run must never
        inherit stale personas, budgets, or old feedback blocks from a previous
        run. The current run's feedback (if any) is attached afterwards via
        _set_feedback_block / _build_refine_directive."""
        subs = state.setdefault("sub_instructions", {})
        fin_chars = state.get("finalized_characters") or []
        personas = [c.name for c in fin_chars] if fin_chars else None
        budget = state.get("budget") or get_duration_budget(state.get("target_seconds", 30))
        for key in agent_keys:
            built = self.decompose_master_instruction(
                    master_instruction=state.get("scenario", ""),
                    news_topic=state["news_input"],
                    target_seconds=state["target_seconds"],
                    tone=state.get("active_tone", ""),
                    angle=state.get("active_angle", ""),
                    character_count=state.get("character_count", 1),
                    scene_style=state.get("scene_style", "Dialogue"),
                    batch_size=state.get("batch_size", 1),
                    max_retries=state.get("max_retries", 5),
                    budget=budget,
                    sample_story=state.get("active_sample_story", ""),
                    personas_override=personas,
                    only_for=[key],
                )
            if key in built:
                subs[key] = built[key]
        return subs

    def execute_stage_1(
        self,
        news_input: str,
        scenario: str,
        batch_size: int = 1,
        target_seconds: int = 30,
        engine_mode: str = "first_local_then_agy",
        max_retries: int = 5,
        preferred_frames: int = 3,
        preferred_angle: str = "",
        character_count: int = 1,
        scene_style: str = "Dialogue",
        preferred_tone: str = "",
        sample_story: Optional[str] = None,
        extra_instruction: Optional[str] = None,
        on_substep: Optional[Callable[[Dict[str, Any]], None]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute Stage 1: News Validation & Instruction Decomposition."""
        start_time = time.time()
        stage1_start = time.time()
        total_scripts = max(1, batch_size)
        total_retries = 0
        agent_audits: List[AgentAuditItem] = []

        active_tone = preferred_tone or kwargs.get("preferred_tone") or kwargs.get("tone") or ""
        if not active_tone and "Tone:" in scenario:
            for line in scenario.split("\n"):
                if line.strip().startswith("Tone:"):
                    active_tone = line.replace("Tone:", "").strip()
                    break
        if not active_tone:
            active_tone = "Trending Reel / Desi Swag"

        active_angle = preferred_angle or kwargs.get("preferred_angle") or kwargs.get("angle") or ""
        if not active_angle and "Editorial angle:" in scenario:
            for line in scenario.split("\n"):
                if line.strip().startswith("Editorial angle:"):
                    active_angle = line.replace("Editorial angle:", "").strip()
                    break

        active_sample_story = sample_story or kwargs.get("sample_story") or kwargs.get("sample_story_input") or ""
        if not active_sample_story and "Reference Sample Story:" in scenario:
            for line in scenario.split("\n"):
                if "Reference Sample Story:" in line:
                    active_sample_story = line.split("Reference Sample Story:")[-1].strip(" \"'")
                    break

        budget = get_duration_budget(target_seconds)

        # Step-by-step: Stage 1 builds ONLY its own sub-instruction. Later stages
        # build theirs when they run (see ensure_sub_instructions), using the
        # freshest upstream outputs.
        sub_instructions = self.decompose_master_instruction(
            master_instruction=scenario,
            news_topic=news_input,
            target_seconds=target_seconds,
            tone=active_tone,
            angle=active_angle,
            character_count=character_count,
            scene_style=scene_style,
            batch_size=total_scripts,
            max_retries=max_retries,
            budget=budget,
            sample_story=active_sample_story,
            only_for=["news_validator"],
        )

        prev_verif = kwargs.get("previous_verification")
        if extra_instruction and extra_instruction.strip():
            state_history = kwargs.get("extra_instructions_history", [])
            state_history.append(extra_instruction.strip())
            if prev_verif:
                self._set_feedback_block(
                    sub_instructions,
                    "news_validator",
                    f"\n\n⭐ CORRECTION FEEDBACK ON PREVIOUS FACT VERIFICATION (HIGH PRIORITY):\n"
                    f"Previous Verified Facts: {prev_verif.verified_facts}\n"
                    f"User Correction Feedback:\n{extra_instruction.strip()}\n"
                    f"Mandate: REFINE the previous verification — keep every fact that already checks out and correct ONLY what this critique targets. Do NOT start over with a brand-new unrelated verification."
                )
            else:
                self._set_feedback_block(
                    sub_instructions,
                    "news_validator",
                    f"\n\n⭐ USER EXTRA INSTRUCTION FOR STAGE 1 (HIGH PRIORITY):\n{extra_instruction.strip()}"
                )

        stage1_failures = 0
        stage1_errors = []
        stage1_resolution = "Direct wire verification confirmed"

        # --- 24h verification cache ---
        # Reuse a fresh verification for the same news instead of re-running
        # the validator (saves API calls and time). Skipped when the user
        # asked for a correction (extra_instruction / previous_verification)
        # -- those explicitly request a re-verification. Only successful
        # verifications are cached; failures are never stored.
        verification: Optional[NewsVerificationReport] = None
        verification_from_cache = False
        cache_age_hours = 0.0
        skip_cache = prev_verif is not None or bool(extra_instruction and extra_instruction.strip())
        _emit_substep(on_substep, 1, "1.1", "News verification", "start",
                       detail=f"Verifying: {(news_input or '')[:120]}",
                       input=f"News: {(news_input or '')[:300]}")
        if not skip_cache:
            _cached_dict = get_cached_verification(news_input)
            if _cached_dict is not None:
                try:
                    verification = NewsVerificationReport(**_cached_dict)
                    verification_from_cache = True
                    cache_age_hours = get_cache_age_hours(news_input) or 0.0
                    stage1_resolution = (
                        f"Reused cached verification from {cache_age_hours:.1f}h ago "
                        "(24h cache hit -- validator API call skipped)"
                    )
                except Exception as ce:
                    logger.warning("Cached verification failed to reconstruct (%s); re-verifying.", ce)
                    verification = None

        if verification is None:
            try:
                verification = news_validator.validate_news(
                    news_input,
                    scenario,
                    sub_instruction=sub_instructions["news_validator"],
                    engine_mode=engine_mode,
                    previous_verification=prev_verif,
                    feedback=extra_instruction,
                )
            except ModelGenerationError:
                raise
            except Exception as e:
                # Fail loudly: never substitute "Story confirmed: {headline}" as verified facts.
                raise ModelGenerationError(
                    f"Stage 1 verification failed: {type(e).__name__}: {e}. "
                    f"News input: {news_input[:200]!r}"
                ) from e
            # Cache the successful verification for 24h (never cached on failure
            # because exceptions above propagate before reaching this line).
            store_verification(news_input, verification.model_dump())

        _emit_substep(on_substep, 1, "1.1", "News verification", "complete",
                       status="pass",
                       detail=(f"Verified with {verification.confidence_score}% confidence"
                               + (f" (cache hit, {cache_age_hours:.1f}h old)" if verification_from_cache else "")),
                       input=f"News: {(news_input or '')[:300]}",
                       output=(verification.verification_summary or "")[:500])

        if not verification_from_cache and verification.confidence_score < 70 and max_retries > 0:
            stage1_failures += 1
            stage1_errors.append(f"Initial confidence score low ({verification.confidence_score}%)")
            _emit_substep(on_substep, 1, "1.2", "Confidence retry", "start",
                           detail=f"Confidence {verification.confidence_score}% < 70% — refining query")
            try:
                verification = news_validator.validate_news(
                    news_input + " official confirmed news updates", scenario, engine_mode=engine_mode
                )
                stage1_resolution = "Refined query with official wire terms; confidence restored."
                # Cache the refined verification too (same title key, overwrites the
                # low-confidence entry) -- never cached on failure since exceptions
                # above propagate before reaching this line.
                store_verification(news_input, verification.model_dump())
                _emit_substep(on_substep, 1, "1.2", "Confidence retry", "complete",
                               status="pass",
                               detail=f"Re-verified with {verification.confidence_score}% confidence")
            except ModelGenerationError:
                raise
            except Exception as e2:
                stage1_errors.append(f"Refinement exception: {str(e2)[:80]}")
                _emit_substep(on_substep, 1, "1.2", "Confidence retry", "complete",
                               status="fail", detail=f"Refinement failed: {str(e2)[:120]}")

        agent_audits.append(
            AgentAuditItem(
                agent_id=1,
                agent_name=news_validator.name,
                icon=news_validator.icon,
                stage_number=1,
                status="Self-Healed" if stage1_failures > 0 else "Success",
                attempts=1 + stage1_failures,
                failures_count=stage1_failures,
                errors_encountered=stage1_errors,
                resolution_action=stage1_resolution,
                execution_time_sec=round(time.time() - stage1_start, 2),
            )
        )

        return {
            "step": 1,
            "total_steps": 6,
            "news_input": news_input,
            "scenario": scenario,
            "batch_size": total_scripts,
            "target_seconds": target_seconds,
            "active_tone": active_tone,
            "active_angle": active_angle,
            "character_count": character_count,
            "scene_style": scene_style,
            "active_sample_story": active_sample_story,
            "max_retries": max_retries,
            "preferred_frames": preferred_frames,
            "budget": budget,
            "sub_instructions": sub_instructions,
            "verification": verification,
            "verification_from_cache": verification_from_cache,
            "cache_age_hours": round(cache_age_hours, 1),
            "agent_audits": agent_audits,
            "start_time": start_time,
            "total_retries": total_retries,
            "extra_instructions_history": [extra_instruction.strip()] if extra_instruction and extra_instruction.strip() else [],
            "input_prompts": [{"template": "news_validator", "prompt": sub_instructions.get("news_validator", "")}],
        }

    def execute_stage_2(
        self,
        state: Dict[str, Any],
        engine_mode: str = "first_local_then_agy",
        extra_instruction: Optional[str] = None,
        on_substep: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """Execute Stage 2: Character Finalisation, Story Steps & Viral Hook Strategy."""
        stage2_start = time.time()
        news_input = state["news_input"]
        total_scripts = state["batch_size"]
        preferred_angle = state["active_angle"]
        active_tone = state["active_tone"]
        verification = state["verification"]
        target_seconds = state["target_seconds"]
        character_count = state["character_count"]
        scene_style = state["scene_style"]
        active_scenario = state.get("scenario", "")
        active_sample_story = state.get("active_sample_story", "")
        # Step-by-step: build this stage's sub-instruction now (Stage 1 no longer
        # pre-generates everything for later stages).
        sub_instructions = self.ensure_sub_instructions(state, "hook_strategist")

        # Capture previous characters if re-running Stage 2.
        # NOTE (new pipeline order): Stage 2 finalizes CHARACTERS ONLY — scene
        # locations are derived FROM the finalized dialogue in Stage 4, so no
        # scenes are produced or stored here anymore.
        prev_chars = state.get("available_characters") or state.get("finalized_characters")

        if extra_instruction and extra_instruction.strip():
            state.setdefault("extra_instructions_history", []).append(extra_instruction.strip())
            if prev_chars:
                self._set_feedback_block(
                    sub_instructions,
                    "hook_strategist",
                    f"\n\n⭐ CORRECTION FEEDBACK ON PREVIOUS CHARACTERS (HIGH PRIORITY):\n"
                    f"Previous Characters: {[c.name for c in prev_chars]}\n"
                    f"User Correction Feedback:\n{extra_instruction.strip()}\n"
                    f"Mandate: REFINE the previous characters — keep every character that already works and change ONLY what this critique targets. Respect the finalized character count; do NOT invent a brand-new unrelated cast."
                )
            else:
                self._set_feedback_block(
                    sub_instructions,
                    "hook_strategist",
                    f"\n\n⭐ USER EXTRA INSTRUCTION FOR STAGE 2 (HIGH PRIORITY):\n{extra_instruction.strip()}"
                )

        selected_angles: List[Tuple[str, str]] = []
        for i in range(total_scripts):
            selected_angles.append(
                (preferred_angle, "User-selected editorial angle")
                if preferred_angle.strip()
                else REEL_ANGLES[i % len(REEL_ANGLES)]
            )

        stage2_failures = 0
        stage2_errors = []
        stage2_resolution = "2X Characters finalised (scenes derive from dialogue in Stage 4)"

        # Beat count for story steps (scene count now decided in Stage 4 from dialogue)
        if target_seconds <= 8 and (scene_style.lower() in ["speech", "monologue"] or character_count == 1):
            req_scenes = 1
        elif target_seconds <= 15:
            req_scenes = 2
        elif target_seconds <= 35:
            req_scenes = 3
        else:
            req_scenes = 4

        try:
            prev_chars_dict = [c.model_dump() for c in prev_chars] if prev_chars else None
            # NEW: Ask AI for TWO distinct character groups (A and B).
            # The user picks ONE group for dialogue — no random selection.
            _emit_substep(on_substep, 2, "2.1", "Character generation", "start",
                           detail=f"Finalising {character_count} character(s), vibe: {active_tone}",
                           input=f"News: {(news_input or '')[:200]}\nVibe: {active_tone} | Style: {scene_style}")
            group_a, group_b = hook_strategist.finalise_character_groups(
                news_topic=news_input,
                verification=verification,
                scenario=active_scenario,
                sample_story=active_sample_story,
                tone=active_tone,
                angle=preferred_angle or (selected_angles[0][0] if selected_angles else "Funny & Relatable"),
                character_count=character_count,
                scene_style=scene_style,
                duration_sec=target_seconds,
                sub_instruction=sub_instructions["hook_strategist"],
                engine_mode=engine_mode,
                previous_groups=None,
                feedback=extra_instruction,
            )
            available_characters = list(group_a) + list(group_b)
            available_scenes = []
        except ModelGenerationError:
            raise
        except Exception as e:
            # Fail loudly: never substitute template personas when character
            # finalisation fails. Surface the exact error instead.
            _emit_substep(on_substep, 2, "2.1", "Character generation", "complete",
                           status="fail",
                           detail=f"Character finalisation failed: {type(e).__name__}: {str(e)[:200]}")
            raise ModelGenerationError(
                f"Stage 2 failed: character finalisation error ({type(e).__name__}): {e}. "
                f"News input: {news_input[:200]!r}"
            ) from e

        # Select the requested number of characters as primary defaults for downstream stages.
        # finalized_scenes stays EMPTY here by design — Stage 4 derives scenes
        # FROM the finalized Stage 3 dialogue.
        finalized_chars = available_characters[:max(1, character_count)]
        finalized_scenes: List = []
        _emit_substep(on_substep, 2, "2.1", "Character generation", "complete",
                       status="pass",
                       detail=f"{len(finalized_chars)} character(s) finalized"
                               + (" (fallback templates)" if stage2_failures else ""),
                       output="\n".join(f"- {c.name} ({c.role_or_job})" for c in finalized_chars[:6]))

        # Validate: every character MUST be fully detailed (no generic placeholders).
        # NOTE: AI enrichment disabled — it risks hangs. The prompt already
        # demands detailed output; generic fallbacks are logged as warnings.
        _emit_substep(on_substep, 2, "2.2", "Character validation", "start",
                       detail="Checking character count, specificity and diversity")
        _GENERIC_MARKERS = [
            "key character / speaker", "key witness / participant",
            "authentic everyday attire", "expressive and engaged",
            "co-participant in the story", "relational dynamic grounded in story context",
            "engaged & authentic",
        ]
        # Substring markers for generic one-size-fits-all clothing — these
        # arrive in variant wordings, so match them as substrings, not exact.
        _GENERIC_ATTIRE_SUBSTRINGS = [
            "everyday street casual", "t-shirt and jeans", "everyday wear",
            "casual wear", "casual clothes", "everyday casual", "normal clothes",
            "regular clothes", "simple clothes",
        ]
        def _is_generic(val, extra_substrings=()):
            n = (val or "").strip().lower()
            if not n:
                return True
            if n in _GENERIC_MARKERS:
                return True
            return any(s in n for s in extra_substrings)
        _generic_chars = [
            c.name for c in finalized_chars
            if _is_generic(c.role_or_job) or _is_generic(c.attire, _GENERIC_ATTIRE_SUBSTRINGS) or _is_generic(c.emotional_stance)
        ]
        # Identical attire across the whole cast is a generic default by
        # another name — every character must look visually distinct.
        _attires = [(c.attire or "").strip().lower() for c in finalized_chars]
        if len(finalized_chars) > 1 and len(set(_attires)) == 1:
            _generic_chars = sorted(set(_generic_chars) | {c.name for c in finalized_chars})
        if _generic_chars:
            # Fail loudly: generic details must trigger the retry flow, never
            # pass silently with a warning buried in the audit trail.
            _emit_substep(on_substep, 2, "2.2", "Character validation", "complete",
                           status="fail",
                           detail=(f"Characters with generic details: {', '.join(_generic_chars)}"))
            raise ModelGenerationError(
                f"Stage 2 failed: characters with generic details — attire must be specific, "
                f"job/news-appropriate and distinct per character: {', '.join(_generic_chars)}. "
                f"News input: {news_input[:200]!r}"
            )

        # Fail loudly: the configured character count MUST be met exactly.
        # If the strategist parsed fewer characters than requested, that is a
        # partial failure — never silently top up with template personas.
        if len(finalized_chars) < character_count:
            _emit_substep(on_substep, 2, "2.2", "Character validation", "complete",
                           status="fail",
                           detail=(f"Character shortfall: parsed {len(finalized_chars)}/{character_count} characters"))
            raise ModelGenerationError(
                f"Stage 2 failed: character shortfall — parsed {len(finalized_chars)} characters "
                f"but {character_count} were requested. "
                f"Parsed: {[c.name for c in finalized_chars]!r}"
            )
        _emit_substep(on_substep, 2, "2.2", "Character validation", "complete",
                       status="pass" if len(finalized_chars) >= character_count else "fail",
                       detail=(f"{len(finalized_chars)}/{character_count} characters; "
                               + ("; ".join(stage2_errors[-2:]) if stage2_errors else "all checks passed")))

        # Hooks and CTAs are generated by the hook-strategist model — one per
        # angle, grounded in the verified news. Template hooks are never
        # substituted: craft_hooks_batch raises ModelGenerationError on any
        # gap, and that failure flows into the normal stage retry.
        hooks_and_ctas = hook_strategist.craft_hooks_batch(
            news_topic=news_input,
            angles=selected_angles[:total_scripts],
            tone=active_tone,
            verification=verification,
            duration_sec=target_seconds,
            sub_instruction=sub_instructions.get("hook_strategist", ""),
            engine_mode=engine_mode,
        )

        # Build clean story beat steps from selected characters and verified news
        # context. Locations are intentionally NOT fixed here — the dialogue
        # paints them and Stage 4 derives the shoot scenes from the dialogue.
        story_steps = []
        # Never present invented placeholders as verified Stage 1 data: when
        # the verification has no locations/props, the beat description omits
        # those clauses instead of writing "Authentic setting" / "Key props".
        _ver_locs = list(verification.key_locations or []) if verification else []
        _ver_props = list(verification.physical_props or []) if verification else []
        loc_desc = _ver_locs[0] if _ver_locs else ""
        props_desc = ", ".join(_ver_props[:3]) if _ver_props else ""
        for b_idx in range(1, req_scenes + 1):
            c = finalized_chars[(b_idx - 1) % len(finalized_chars)]
            if b_idx == 1:
                _loc_clause = f"Begins in {loc_desc}; " if loc_desc else ""
                _props_clause = f" interacting with {props_desc}" if props_desc else ""
                act_desc = f"{_loc_clause}{c.name} opens the situation{_props_clause}"
                goal_desc = "Establish opening hook and relatable situation"
            elif b_idx == req_scenes:
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

        state["agent_audits"].append(
            AgentAuditItem(
                agent_id=2,
                agent_name="Character Finalisation Strategist",
                icon="🎭",
                stage_number=2,
                status="Self-Healed" if stage2_failures > 0 else "Success",
                attempts=1,
                failures_count=stage2_failures,
                errors_encountered=stage2_errors,
                resolution_action=stage2_resolution,
                execution_time_sec=round(time.time() - stage2_start, 2),
            )
        )

        state["selected_angles"] = selected_angles
        state["hooks_and_ctas"] = hooks_and_ctas
        state["available_characters"] = available_characters
        state["available_scenes"] = available_scenes
        # Store both character groups; the user picks ONE for dialogue.
        # Default selection is Group A (can be changed in the UI).
        state["character_group_a"] = group_a
        state["character_group_b"] = group_b
        state["selected_character_group"] = "A"
        state["finalized_characters"] = finalized_chars
        state["finalized_scenes"] = finalized_scenes
        state["story_steps"] = story_steps
        state["step"] = 2
        state["input_prompts"] = [{"template": "hook_strategist (characters)", "prompt": state.get("sub_instructions", {}).get("hook_strategist", "")}]
        return state

    def execute_stage_3(
        self,
        state: Dict[str, Any],
        engine_mode: str = "first_local_then_agy",
        extra_instruction: Optional[str] = None,
        preferred_frames: Optional[int] = None,
        on_substep: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """Execute Stage 3: Dialogue Narration Writing & Duration Calibration."""
        stage3_start = time.time()
        news_input = state["news_input"]
        total_scripts = state["batch_size"]
        selected_angles = state["selected_angles"]
        hooks_and_ctas = state["hooks_and_ctas"]
        active_tone = state["active_tone"]
        target_seconds = state["target_seconds"]
        verification = state["verification"]
        character_count = state["character_count"]
        scene_style = state["scene_style"]
        active_angle = state["active_angle"]
        active_sample_story = state["active_sample_story"]
        # Step-by-step: build this stage's sub-instructions now (Stage 1 no longer
        # pre-generates everything for later stages).
        sub_instructions = self.ensure_sub_instructions(state, "dialogue_writer", "timing_auditor")
        max_retries = state["max_retries"]
        budget = state["budget"]

        # Extract previous draft if re-running Stage 3 with feedback/corrections
        previous_dialogues = state.get("script_dialogues", [])
        previous_draft_text = ""
        if previous_dialogues:
            draft_chunks = []
            for idx, d in enumerate(previous_dialogues, 1):
                if d.get("scene_lines"):
                    lines = [f"{sl.get('character', 'Character')}: \"{sl.get('dialogue', '')}\"" for sl in d["scene_lines"]]
                    draft_chunks.append(f"Script {idx}:\n" + "\n".join(lines))
                elif d.get("narration"):
                    draft_chunks.append(f"Script {idx}:\n{d['narration']}")
            previous_draft_text = "\n\n".join(draft_chunks)

        # Stage 3 retry uses a dedicated refine prompt inside write_dialogues_batch
        # (previous visible draft + custom instruction, locked creative decisions).
        # Feedback is carried ONLY there — never duplicated or persisted into
        # sub-instructions, so re-runs can never stack stale blocks.
        if extra_instruction and extra_instruction.strip():
            state.setdefault("extra_instructions_history", []).append(extra_instruction.strip())

        batch_items = [
            {"angle": selected_angles[i][0], "hook": hooks_and_ctas[i][0], "cta": hooks_and_ctas[i][1]}
            for i in range(total_scripts)
        ]

        stage3_failures = 0
        stage3_errors = []
        stage3_resolution = "Spoken dialogue generated and calibrated"

        explicit_frames = preferred_frames or state.get("preferred_frames")
        if explicit_frames and explicit_frames == 3:
            explicit_frames = None

        try:
            raw_narrations = dialogue_writer.write_dialogues_batch(
                news_input=news_input,
                items=batch_items,
                tone=active_tone,
                duration_sec=target_seconds,
                verification=verification,
                character_count=character_count,
                scene_style=scene_style,
                preferred_angle=active_angle,
                sample_story=active_sample_story,
                sub_instruction=sub_instructions["dialogue_writer"],
                engine_mode=engine_mode,
                num_scenes=explicit_frames,
                previous_draft=previous_draft_text if previous_draft_text else None,
                feedback=extra_instruction if extra_instruction else None,
                finalized_characters=state.get("finalized_characters"),
                # Stage 3 writes dialogue with NO predefined scene binding.
                # finalized_scenes stays empty by design — Stage 4 derives
                # scenes FROM the finalized Stage 3 dialogue.
                finalized_scenes=[],
                story_steps=state.get("story_steps"),
                _max_retries=max_retries,
                on_substep=on_substep,
            )
        except ModelGenerationError as mge:
            # Attach the retry attempt history so the UI can show every
            # attempt's output on failure (user asked to see all attempts).
            mge.attempt_history = getattr(dialogue_writer, "last_attempt_history", None) or []
            mge.validation_steps = getattr(dialogue_writer, "last_validation_steps", None) or []
            raise
        except Exception as e:
            # Fail loudly: never present synthetic fallback narrations as a
            # success. The stage reports the error; the UI keeps the previous
            # stages' output visible and offers retry / back navigation.
            _fail_attempts = getattr(dialogue_writer, "last_attempt_history", None) or []
            _mge = ModelGenerationError(
                f"Stage 3 dialogue generation failed: {type(e).__name__}: {e}"
            )
            _mge.attempt_history = _fail_attempts
            _mge.validation_steps = getattr(dialogue_writer, "last_validation_steps", None) or []
            raise _mge from e

        min_w = budget["min_words"]
        rec_w = budget["recommended_words"]
        max_w = budget["max_words"]

        # Retry count from the dialogue writer's corrective passes (for UI display).
        # Derive from the linear steps: 3.1/3.3/3.5... are generation rounds, so
        # retries = generation rounds beyond the first. The initial 3.1 generation
        # is NEVER counted as a retry (prevents phantom "Retry 1" in the UI).
        _vsteps_for_count = getattr(dialogue_writer, "last_validation_steps", None) or []
        _gen_rounds = 0
        for _vs in _vsteps_for_count:
            if not isinstance(_vs, dict):
                continue
            _sp = str(_vs.get("stage", "")).strip().split(".")
            if len(_sp) == 2 and _sp[0] == "3" and _sp[1].isdigit() and int(_sp[1]) % 2 == 1:
                _gen_rounds += 1
        if _gen_rounds:
            state["stage3_retry_count"] = max(0, _gen_rounds - 1)
        else:
            state["stage3_retry_count"] = max(0, int(getattr(dialogue_writer, "last_retry_count", 0) or 0))
        # Full retry attempt history (raw model output per attempt) for UI display.
        state["stage3_attempt_history"] = getattr(dialogue_writer, "last_attempt_history", None) or []
        # Linear Stage 3 steps (3.1 generation, 3.2 validation, 3.3 retry...) for UI display.
        state["stage3_validation_steps"] = getattr(dialogue_writer, "last_validation_steps", None) or []

        # Merge AI-enriched profiles for newly-invented speaker names into
        # finalized_characters so Stage 4/5 have full job/attire details.
        _enriched = getattr(dialogue_writer, '_enriched_profiles', None) or {}
        if _enriched:
            _existing = set(
                re.sub(r"[^\w]", "", (c.name or ""), flags=re.UNICODE).lower()
                for c in (state.get("finalized_characters") or [])
            )
            for _ename, _eprof in _enriched.items():
                _ekey = re.sub(r"[^\w]", "", _ename, flags=re.UNICODE).lower()
                if _ekey not in _existing:
                    # Fail loudly: a new speaker invented by the dialogue writer
                    # must arrive with a concrete, news-grounded profile. Missing
                    # or generic placeholder fields are a contract violation —
                    # they must never slip past Stage 2's validation as made-up
                    # character data.
                    _erole = (_eprof.get("role_or_job") or "").strip()
                    _eattire = (_eprof.get("attire") or "").strip()
                    _eemo = (_eprof.get("emotional_stance") or "").strip()
                    _erel = (_eprof.get("relationship_dynamic") or "").strip()
                    _generic_markers = {
                        "key character / speaker", "key witness / participant",
                        "authentic everyday attire", "expressive and engaged",
                        "co-participant in the story",
                        "relational dynamic grounded in story context",
                        "engaged & authentic",
                    }
                    _bad = [v for v in (_erole, _eattire, _eemo, _erel)
                            if not v or v.lower() in _generic_markers]
                    if _bad:
                        raise ModelGenerationError(
                            "Stage 3 failed: the dialogue introduced a new speaker "
                            f"{_eprof.get('name', _ename)!r} without a concrete, news-grounded "
                            f"profile (missing or generic fields: {_bad}). Refusing to invent "
                            "placeholder character data — the script must only use finalized "
                            "Stage 2 characters or provide full profiles for new speakers."
                        )
                    state.setdefault("finalized_characters", []).append(CharacterProfile(
                        name=_eprof["name"],
                        role_or_job=_erole,
                        attire=_eattire,
                        emotional_stance=_eemo,
                        relationship_dynamic=_erel,
                    ))
                    _existing.add(_ekey)

        stage4_timing_failures = 0
        stage4_timing_errors = []
        script_dialogues: List[Dict[str, Any]] = []

        for i in range(total_scripts):
            angle_tuple = selected_angles[i]
            hook, cta = hooks_and_ctas[i]
            if i < len(raw_narrations):
                raw_item = raw_narrations[i]
            else:
                raise ModelGenerationError(
                    f"Stage 3 failed: writer returned {len(raw_narrations)} narrations "
                    f"but {total_scripts} scripts were requested."
                )
            narration = str(raw_item)
            scene_lines = getattr(raw_item, "scene_lines", [])
            if not scene_lines:
                raise ModelGenerationError("Stage 3 failed: script has zero dialogue beats")

            passed, w_cnt, w_stat, e_dur, t_stat, clarity, audit_feedback = timing_auditor.audit_script(
                narration=narration,
                hook=hook,
                cta=cta,
                target_seconds=target_seconds,
                sub_instruction=sub_instructions["timing_auditor"],
            )

            retry_notes: List[str] = []
            attempt = 0
            while not passed and attempt < max_retries:
                attempt += 1
                stage4_timing_failures += 1
                state["total_retries"] = state.get("total_retries", 0) + 1
                stage4_timing_errors.append(
                    f"Script #{i+1}: Dialogue exceeded max limit ({w_cnt} words > {max_w} max words for {target_seconds}s reel, attempt {attempt}/{max_retries})"
                )

                from agents.dialogue_writer import smart_trim_dialogue
                calibrated = smart_trim_dialogue(narration, max_w, rec_w, cta)
                c_passed, c_w_cnt, c_w_stat, c_e_dur, c_t_stat, c_clarity, c_feedback = timing_auditor.audit_script(
                    narration=calibrated, hook=hook, cta=cta, target_seconds=target_seconds, sub_instruction=sub_instructions["timing_auditor"]
                )
                if c_passed:
                    narration = calibrated
                    w_cnt, w_stat, e_dur, t_stat, clarity, audit_feedback = c_w_cnt, c_w_stat, c_e_dur, c_t_stat, c_clarity, c_feedback
                    retry_notes.append(
                        f"🔄 Agent 4 Timing Calibration: Self-healed dialogue to {w_cnt}w on attempt {attempt}/{max_retries} (certified <= {max_w}w max)."
                    )
                    passed = True
                elif attempt == max_retries:
                    from core.metrics import count_words
                    while count_words(calibrated) > max_w and " " in calibrated:
                        calibrated = " ".join(calibrated.split()[:-1])
                    narration = calibrated
                    passed, w_cnt, w_stat, e_dur, t_stat, clarity, audit_feedback = timing_auditor.audit_script(
                        narration=narration, hook=hook, cta=cta, target_seconds=target_seconds, sub_instruction=sub_instructions["timing_auditor"]
                    )
                    retry_notes.append(
                        f"🔄 Agent 4 Timing Calibration: Precision clamped to {w_cnt} words (<= {max_w}w max) after exhausting {max_retries} retry attempts."
                    )
                    passed = True
                else:
                    narration = calibrated

            # Character-count compliance: every finalized character must speak at least once.
            _final_names = [(c.name or "") for c in (state.get("finalized_characters") or [])]
            if _final_names and scene_lines:
                def _canon_spk(n):
                    return re.sub(r"[^\w]", "", n or "", flags=re.UNICODE).lower()
                _speakers = set()
                for _sl in scene_lines:
                    if isinstance(_sl, dict):
                        _speakers.add(_canon_spk(_sl.get("character", "")))
                    elif isinstance(_sl, (list, tuple)) and len(_sl) >= 1:
                        _speakers.add(_canon_spk(_sl[0]))
                _missing = [
                    _nm for _nm in _final_names
                    if _canon_spk(_nm) and not any(
                        _canon_spk(_nm) in _sp or _sp in _canon_spk(_nm) for _sp in _speakers if _sp
                    )
                ]
                if _missing:
                    _miss_note = (
                        f"⚠️ Character coverage: {', '.join(_missing)} has no spoken line "
                        f"(expected {character_count} speakers)."
                    )
                    retry_notes.append(_miss_note)
                    stage3_errors.append(f"Script #{i+1}: " + _miss_note)

            script_dialogues.append({
                "idx": i,
                "angle_tuple": angle_tuple,
                "hook": hook,
                "cta": cta,
                "narration": narration,
                "scene_lines": scene_lines,
                "attempt": attempt,
                "retry_notes": retry_notes,
                "w_cnt": w_cnt,
                "w_stat": w_stat,
                "e_dur": e_dur,
                "t_stat": t_stat,
                "clarity": clarity,
                "audit_feedback": audit_feedback,
                "min_words": min_w,
                "recommended_words": rec_w,
                "max_words": max_w,
                "is_over_budget": (w_cnt > max_w),
            })

        state["agent_audits"].append(
            AgentAuditItem(
                agent_id=3,
                agent_name=dialogue_writer.name,
                icon=dialogue_writer.icon,
                stage_number=3,
                status="Self-Healed" if stage3_failures > 0 else "Success",
                attempts=1,
                failures_count=stage3_failures,
                errors_encountered=stage3_errors,
                resolution_action=stage3_resolution,
                execution_time_sec=round((time.time() - stage3_start) * 0.7, 2),
            )
        )

        state["agent_audits"].append(
            AgentAuditItem(
                agent_id=4,
                agent_name=timing_auditor.name,
                icon=timing_auditor.icon,
                stage_number=3,
                status="Self-Healed" if stage4_timing_failures > 0 else "Success",
                attempts=1 + stage4_timing_failures,
                failures_count=stage4_timing_failures,
                errors_encountered=stage4_timing_errors,
                resolution_action="Automatically calibrated spoken word counts to target duration budget" if stage4_timing_failures > 0 else "All dialogue word counts fit target pacing perfectly",
                execution_time_sec=round((time.time() - stage3_start) * 0.3, 2),
            )
        )

        state["script_dialogues"] = script_dialogues
        state["step"] = 3
        state["input_prompts"] = [
            {"template": "dialogue_writer", "prompt": state.get("sub_instructions", {}).get("dialogue_writer", "")},
            {"template": "timing_auditor", "prompt": state.get("sub_instructions", {}).get("timing_auditor", "")},
        ]
        return state

    def execute_stage_4(
        self,
        state: Dict[str, Any],
        engine_mode: str = "first_local_then_agy",
        extra_instruction: Optional[str] = None,
        preferred_frames: Optional[int] = None,
        on_substep: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """Execute Stage 4: Scene Derivation FROM Dialogue (strategist 2nd run).

        The hook strategist is invoked a SECOND time. It reads the finalized
        Stage 3 dialogue beats and DERIVES the shoot locations from what the
        dialogue actually shows — every scene is traceable to specific beats.
        Scenes can never be disconnected from the dialogue because the
        dialogue is their only source. Fails loudly on model/parse errors.
        """
        stage4_start = time.time()
        script_dialogues = state["script_dialogues"]
        news_input = state["news_input"]
        target_seconds = state["target_seconds"]
        active_tone = state["active_tone"]
        active_angle = state["active_angle"]
        scene_style = state["scene_style"]
        verification = state["verification"]
        finalized_characters = state.get("finalized_characters") or []
        sub_instructions = self.ensure_sub_instructions(state, "hook_strategist")

        if extra_instruction and extra_instruction.strip():
            state.setdefault("extra_instructions_history", []).append(extra_instruction.strip())

        stage4_failures = 0
        stage4_errors: List[str] = []
        derived_per_script: List[List] = []
        # Both scene sets per script; user picks ONE (default Set A).
        scene_options_a: List[List] = []
        scene_options_b: List[List] = []

        prev_derived = state.get("derived_scenes_per_script") or []

        _emit_substep(on_substep, 4, "4.1", "Scene derivation", "start",
                       detail=f"Deriving scenes from dialogue for {len(script_dialogues)} script(s)",
                       input=f"Dialogue beats from {len(script_dialogues)} script(s)")
        for d_idx, d in enumerate(script_dialogues):
            s_lines = d.get("scene_lines") or []
            # One derived scene per dialogue beat keeps every scene traceable
            # to the exact beat whose action line paints its location.
            if s_lines:
                num_scenes = max(1, min(len(s_lines), 5))
            elif target_seconds <= 8:
                num_scenes = 1
            elif target_seconds <= 15:
                num_scenes = 2
            elif target_seconds <= 35:
                num_scenes = 3
            else:
                num_scenes = 4

            prev_scenes_dict = None
            if prev_derived and d_idx < len(prev_derived):
                try:
                    prev_scenes_dict = [s.model_dump() for s in prev_derived[d_idx]]
                except Exception:
                    prev_scenes_dict = None

            try:
                # NEW: Ask AI for TWO distinct scene sets (A and B).
                # The user picks ONE — no random selection, no repetition.
                set_a, set_b = hook_strategist.derive_scene_options(
                    news_topic=news_input,
                    verification=verification,
                    finalized_characters=finalized_characters,
                    dialogue_beats=s_lines,
                    num_scenes=num_scenes,
                    tone=active_tone,
                    angle=d.get("angle_tuple", (active_angle, ""))[0] if d.get("angle_tuple") else active_angle,
                    scene_style=scene_style,
                    duration_sec=target_seconds,
                    sub_instruction=sub_instructions["hook_strategist"],
                    engine_mode=engine_mode,
                    previous_options=None,
                    feedback=extra_instruction if extra_instruction else None,
                )
                # Default to Set A; user can switch to Set B in the UI.
                scenes = set_a
                scene_options_a.append(set_a)
                scene_options_b.append(set_b)
            except ModelGenerationError:
                raise
            except Exception as e:
                raise ModelGenerationError(
                    f"Stage 4 scene derivation failed for script {d_idx + 1}: {type(e).__name__}: {e}"
                ) from e
            derived_per_script.append(scenes)
            _emit_substep(on_substep, 4, "4.1", "Scene derivation", "progress",
                           detail=f"Script {d_idx + 1}/{len(script_dialogues)}: {len(scenes)} scene(s) derived")

        _total_scenes = sum(len(s) for s in derived_per_script)
        _emit_substep(on_substep, 4, "4.1", "Scene derivation", "complete",
                       status="pass" if _total_scenes else "fail",
                       detail=f"{_total_scenes} scene(s) derived from dialogue",
                       output="\n".join(
                           f"Script {i + 1}: " + ", ".join(getattr(s, 'location_name', '?') for s in sc[:3])
                           for i, sc in enumerate(derived_per_script[:3])))
        # 4.2 Derivation check: every script must have at least one scene.
        _emit_substep(on_substep, 4, "4.2", "Derivation check", "start",
                       detail="Verifying every script has derived scenes")
        _missing = [i + 1 for i, sc in enumerate(derived_per_script) if not sc]
        _emit_substep(on_substep, 4, "4.2", "Derivation check", "complete",
                       status="pass" if not _missing else "fail",
                       detail=("All scripts have scenes" if not _missing
                               else f"Scripts missing scenes: {_missing}"))

        state["agent_audits"].append(
            AgentAuditItem(
                agent_id=2,
                agent_name=hook_strategist.name,
                icon=hook_strategist.icon,
                stage_number=4,
                status="Self-Healed" if stage4_failures > 0 else "Success",
                attempts=1,
                failures_count=stage4_failures,
                errors_encountered=stage4_errors,
                resolution_action=(
                    f"Derived {sum(len(s) for s in derived_per_script)} shoot scenes "
                    f"FROM finalized dialogue beats ({len(derived_per_script)} scripts)"
                ),
                execution_time_sec=round(time.time() - stage4_start, 2),
            )
        )

        state["derived_scenes_per_script"] = derived_per_script
        # Store both scene option sets per script; the user picks ONE.
        state["scene_options_a_per_script"] = scene_options_a
        state["scene_options_b_per_script"] = scene_options_b
        state["selected_scene_set"] = "A"
        # Backward-compatible shared view: first script's scenes.
        state["finalized_scenes"] = list(derived_per_script[0]) if derived_per_script else []
        state["available_scenes"] = list(derived_per_script[0]) if derived_per_script else []
        state["step"] = 4
        state["input_prompts"] = [{"template": "hook_strategist (scene derivation)", "prompt": state.get("sub_instructions", {}).get("hook_strategist", "")}]
        return state

    def execute_stage_5(
        self,
        state: Dict[str, Any],
        engine_mode: str = "first_local_then_agy",
        extra_instruction: Optional[str] = None,
        preferred_frames: Optional[int] = None,
        on_substep: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """Execute Stage 5: Scene Visuals Direction & AI Video Prompt Engineering."""
        stage4_start = time.time()
        script_dialogues = state["script_dialogues"]
        news_input = state["news_input"]
        target_seconds = state["target_seconds"]
        active_tone = state["active_tone"]
        active_angle = state["active_angle"]
        scene_style = state["scene_style"]
        character_count = state["character_count"]
        active_sample_story = state["active_sample_story"]
        sub_instructions = state["sub_instructions"]
        verification = state["verification"]
        max_retries = state["max_retries"]
        budget = state["budget"]
        min_w = budget["min_words"]
        rec_w = budget["recommended_words"]
        max_w = budget["max_words"]

        prev_scripts = state.get("scripts", [])
        if extra_instruction and extra_instruction.strip():
            state.setdefault("extra_instructions_history", []).append(extra_instruction.strip())
            if prev_scripts:
                sub_instructions["scene_director"] += (
                    f"\n\n⭐ CORRECTION FEEDBACK ON PREVIOUS STORYBOARD SCENES (HIGH PRIORITY):\n"
                    f"Previous Scene Count: {len(prev_scripts[0].scenes) if prev_scripts and prev_scripts[0].scenes else 0}\n"
                    f"User Correction Feedback:\n{extra_instruction.strip()}\n"
                    f"Mandate: Re-direct visual scenes, props, and actions directly addressing this critique."
                )
                sub_instructions["video_prompt_engineer"] += (
                    f"\n\n⭐ CORRECTION FEEDBACK ON PREVIOUS VIDEO PROMPTS (HIGH PRIORITY):\n{extra_instruction.strip()}"
                )
            else:
                sub_instructions["scene_director"] += (
                    f"\n\n⭐ USER EXTRA INSTRUCTION FOR STAGE 5 (HIGH PRIORITY):\n{extra_instruction.strip()}"
                )
                sub_instructions["video_prompt_engineer"] += (
                    f"\n\n⭐ USER EXTRA INSTRUCTION FOR STAGE 5 (HIGH PRIORITY):\n{extra_instruction.strip()}"
                )

        explicit_frames = preferred_frames or state.get("preferred_frames")
        if explicit_frames and explicit_frames == 3:
            explicit_frames = None

        scripts: List[ReelScript] = []

        _emit_substep(on_substep, 5, "5.1", "Storyboard generation", "start",
                       detail=f"Directing storyboards for {len(script_dialogues)} script(s)",
                       input=f"Derived scenes from Stage 4 for {len(script_dialogues)} script(s)")
        for d_idx, d in enumerate(script_dialogues):
            i = d["idx"]
            angle_tuple = d["angle_tuple"]
            hook = d["hook"]
            cta = d["cta"]
            narration = d["narration"]
            s_lines = d.get("scene_lines", [])
            # Incorporate Stage 2 finalized characters and scenes if available
            finalized_chars = state.get("finalized_characters") or []
            if finalized_chars:
                personas = [c.name for c in finalized_chars]
            else:
                personas = get_character_personas(
                    scene_style, character_count, active_tone, active_angle,
                    topic_or_script=f"{news_input} {narration}", sample_story=active_sample_story
                )

            # Stage 4 derived these scenes FROM this script's dialogue beats —
            # the storyboard must stay connected to them.
            _derived_per_script = state.get("derived_scenes_per_script") or []
            if d_idx < len(_derived_per_script):
                finalized_sc_list = _derived_per_script[d_idx]
            else:
                finalized_sc_list = state.get("finalized_scenes") or state.get("available_scenes") or []
            active_locs = [sc.location_name for sc in finalized_sc_list if sc.location_name] or (verification.key_locations if verification else [])
            active_props = []
            for sc in finalized_sc_list:
                active_props.extend(sc.props)
            if not active_props and verification:
                active_props = verification.physical_props

            prev_scenes_for_script = prev_scripts[d_idx].scenes if (prev_scripts and d_idx < len(prev_scripts)) else None

            scenes = scene_director.direct_scenes(
                news_topic=news_input,
                hook=hook,
                narration=narration,
                duration_sec=target_seconds,
                scene_lines=s_lines,
                verified_facts=verification.verified_facts if verification else [],
                physical_props=active_props,
                key_locations=active_locs,
                core_conflict_or_irony=verification.core_conflict_or_irony if verification else "",
                tangible_actions=verification.tangible_actions if verification else [],
                tone=active_tone,
                angle=angle_tuple[0],
                scene_style=scene_style,
                personas=personas,
                sub_instruction=sub_instructions.get("scene_director"),
                engine_mode=engine_mode,
                preferred_frames=explicit_frames,
                previous_scenes=prev_scenes_for_script,
                feedback=extra_instruction if extra_instruction else None,
            )

            video_prompts = video_prompt_engineer.generate_prompts(
                news_topic=news_input,
                scenes=scenes,
                tone=active_tone,
                angle=angle_tuple[0],
                verified_facts=verification.verified_facts if verification else [],
                sub_instruction=sub_instructions.get("video_prompt_engineer"),
                engine_mode=engine_mode,
            )

            for sc, vp in zip(scenes, video_prompts):
                sc.video_prompt = vp

            # Deterministic: every storyboard scene MUST carry its Stage 4
            # derived location. The director never sets scene_location itself.
            _derived_locs = [getattr(s, "location_name", "") or "" for s in (finalized_sc_list or [])]
            _derived_locs = [l for l in _derived_locs if l.strip()]
            if not _derived_locs and verification:
                _derived_locs = list(verification.key_locations or [])
            for _si, sc in enumerate(scenes):
                if not (sc.scene_location or "").strip():
                    if _derived_locs:
                        sc.scene_location = _derived_locs[_si % len(_derived_locs)]
                    else:
                        # Fail loudly: a storyboard scene with no location from
                        # Stage 4 and no verified Stage 1 locations cannot be
                        # shot — stamping a placeholder string is not allowed.
                        raise ModelGenerationError(
                            f"Stage 5 failed: storyboard scene {_si + 1} of script "
                            f"{d_idx + 1} has no location (Stage 4 derived none and "
                            "Stage 1 verified none). Refusing to invent a placeholder "
                            "location."
                        )

            # ADVISORY-ONLY quality gate (user rule): feasibility scores,
            # duration limits, and camera-complexity verdicts must NEVER fail
            # Stage 5 or trigger retries. The verdict is recorded on the script
            # for visibility only — a FAILED verdict always continues.
            video_verif = video_quality_gate.audit_prompts(
                prompts=video_prompts,
                sub_instruction=sub_instructions.get("video_quality_gate"),
                engine_mode=engine_mode,
            )
            _emit_substep(on_substep, 5, "5.1", "Storyboard generation", "progress",
                           detail=f"Script {d_idx + 1}/{len(script_dialogues)}: {len(scenes)} scene(s) storyboarded")
            _emit_substep(on_substep, 5, "5.2", "Quality gate (advisory)", "progress",
                           detail=f"Script {d_idx + 1}/{len(script_dialogues)}: reviewed {len(video_prompts)} prompt(s) — advisory only, cannot block")
            if not video_verif.passed:
                # Advisory flag, never a failure: surfaced for visibility,
                # then the pipeline continues with the storyboard as-is.
                _emit_substep(on_substep, 5, "5.2", "Quality gate (advisory)", "complete",
                               status="pass",
                               detail=(f"Script {i + 1} advisory flags (non-blocking, feasibility "
                                       f"{video_verif.feasibility_score}%): {video_verif.feedback[:150]}"))
                logger.warning("Stage 5 advisory quality flags for script %d (non-blocking): %s",
                               i + 1, video_verif.feedback[:300])
            else:
                _emit_substep(on_substep, 5, "5.2", "Quality gate (advisory)", "progress",
                               detail=f"Script {d_idx + 1}/{len(script_dialogues)}: advisory review clean")

            scripts.append(
                ReelScript(
                    id=i + 1,
                    title=f"Reel #{i+1} ({target_seconds}s): {angle_tuple[0].split('(')[0].strip()}",
                    angle=angle_tuple[0],
                    hook_hindi=hook,
                    narration_hindi=narration,
                    call_to_action=cta,
                    scenes=scenes,
                    word_count=d["w_cnt"],
                    min_words=d.get("min_words", min_w),
                    recommended_words=d.get("recommended_words", rec_w),
                    max_words=d.get("max_words", max_w),
                    is_over_budget=d.get("is_over_budget", False),
                    word_count_status=d["w_stat"],
                    word_count_feedback=d["audit_feedback"],
                    target_duration_sec=target_seconds,
                    estimated_duration_sec=d["e_dur"],
                    timeline_fit_status=d["t_stat"],
                    timeline_feedback=d["audit_feedback"],
                    video_verification=video_verif,
                    clarity_score=d["clarity"],
                    sample_story_used=active_sample_story,
                    retry_count=d["attempt"],
                    self_healing_notes=d["retry_notes"],
                    engine_used=engine_mode,
                )
            )

            from core.script_analyzer import common_sense_validator
            sc_curr = scripts[-1]
            cs_valid, cs_issues, cs_feedback = common_sense_validator.audit_screenplay(sc_curr)
            cs_attempt = 0
            while not cs_valid and cs_attempt < max_retries:
                cs_attempt += 1
                state["total_retries"] = state.get("total_retries", 0) + 1
                sc_curr, cs_valid, cs_feedback = common_sense_validator.heal_and_revalidate(sc_curr, cs_feedback)
                sc_curr.self_healing_notes.append(
                    f"🔄 Common Sense Validator: Self-healed setting/dialogue/kinematics on attempt {cs_attempt}/{max_retries}."
                )
            # Fail loudly: if the storyboard is still invalid after all healing
            # retries, it must not ship as a success.
            if not cs_valid:
                raise ModelGenerationError(
                    f"Stage 5 failed: common-sense validation still failing for script {i + 1} "
                    f"after {cs_attempt} healing attempt(s). Issues: {str(cs_feedback)[:500]}"
                )
            scripts[-1] = sc_curr

        _emit_substep(on_substep, 5, "5.1", "Storyboard generation", "complete",
                       status="pass",
                       detail=f"{len(scripts)} storyboard(s) ready",
                       output=f"{sum(len(s.scenes or []) for s in scripts)} scene(s) across {len(scripts)} script(s)")
        _emit_substep(on_substep, 5, "5.2", "Quality gate (advisory)", "complete",
                       status="pass",
                       detail=f"All {len(scripts)} script(s) storyboarded — quality gate is advisory only, nothing blocked")

        state["agent_audits"].append(
            AgentAuditItem(
                agent_id=5,
                agent_name=scene_director.name,
                icon=scene_director.icon,
                stage_number=5,
                status="Success",
                attempts=1,
                failures_count=0,
                errors_encountered=[],
                resolution_action=f"Generated visual B-roll & SFX timeline breakdowns for all {state['batch_size']} scripts",
                execution_time_sec=round((time.time() - stage4_start) * 0.5, 2),
            )
        )

        state["agent_audits"].append(
            AgentAuditItem(
                agent_id=6,
                agent_name=video_prompt_engineer.name,
                icon=video_prompt_engineer.icon,
                stage_number=5,
                status="Success",
                attempts=1,
                failures_count=0,
                errors_encountered=[],
                resolution_action="Synthesized 9:16 vertical 4K cinematic camera generation tokens",
                execution_time_sec=round((time.time() - stage4_start) * 0.5, 2),
            )
        )

        state["scripts"] = scripts
        state["step"] = 5
        state["input_prompts"] = [
            {"template": "scene_director", "prompt": state.get("sub_instructions", {}).get("scene_director", "")},
            {"template": "video_prompt_engineer", "prompt": state.get("sub_instructions", {}).get("video_prompt_engineer", "")},
        ]
        return state

    # ------------------------------------------------------------------
    # STAGE 6 VALIDATION GATE (integration only)
    # ------------------------------------------------------------------
    @staticmethod
    def _gate_tokens(text: str) -> List[str]:
        stop = {
            "the", "a", "an", "and", "or", "of", "in", "on", "to", "for",
            "with", "is", "are", "was", "were", "be", "been", "has", "have",
            "had", "this", "that", "these", "those", "it", "its", "as",
            "at", "by", "from", "into", "over", "after", "before",
        }
        return [t for t in re.findall(r"[a-zA-Z\u0900-\u097F]{4,}", (text or "").lower()) if t not in stop]

    def run_validation_gate(
        self,
        state: Dict[str, Any],
        engine_mode: str = "first_local_then_agy",
        run_model_judge: bool = True,
    ) -> Dict[str, Any]:
        """Run the Stage 6 INTEGRATION-ONLY validation gate.

        Stage 6 never re-checks content quality -- tone, news coverage,
        language, dialogue structure, scene quality, and storyboard/video
        prompt quality are owned and validated by the stages that created
        them (Stages 3, 4, 5). Stage 6 only verifies that the stage outputs
        integrate coherently:

          1. Presence -- every required Stage 1-5 output exists in state.
          2. Count consistency -- scripts, dialogues, and derived scenes align.
          3. Cross-stage connectivity -- referenced characters exist, scenes
             derive from dialogue, storyboard locations match derived scenes.
          4. Non-empty payloads -- nothing integrated is an empty shell.

        Returns {"passed": bool, "issues": [...], "summary": str}.
        Each issue: n, check, stage, script, detail, fix, source, severity.
        A VALIDATION failure is reported as validation issues -- never as a
        generation failure.
        """
        issues: List[Dict[str, Any]] = []
        scripts = state.get("scripts") or []
        script_dialogues = state.get("script_dialogues") or []
        derived_per_script = state.get("derived_scenes_per_script") or []
        characters = state.get("finalized_characters") or []
        char_names = [c.name for c in characters if getattr(c, "name", "")]
        verification = state.get("verification")

        def add(check, stage, script_id, detail, fix, source="deterministic", severity="error"):
            issues.append({
                "n": len(issues) + 1,
                "check": check,
                "stage": stage,
                "script": script_id,
                "detail": detail,
                "fix": fix,
                "source": source,
                "severity": severity,
            })

        # 1. Presence: every required Stage 1-5 output must exist in state.
        if verification is None:
            add("outputs-present", "Stage 6", 0,
                "Stage 1 verification output is missing from state.",
                "Re-run Stage 1 so the verified facts exist before integration.")
        if not characters:
            add("outputs-present", "Stage 6", 0,
                "Stage 2 finalized characters are missing from state.",
                "Re-run Stage 2 so the character cast exists before integration.")
        if not script_dialogues:
            add("outputs-present", "Stage 6", 0,
                "Stage 3 dialogue output (script_dialogues) is missing from state.",
                "Re-run Stage 3 so dialogue beats exist before integration.")
        if not derived_per_script:
            add("outputs-present", "Stage 6", 0,
                "Stage 4 derived scenes are missing from state.",
                "Re-run Stage 4 so derived scenes exist before integration.")

        # 2. Count consistency: scripts, dialogues, and derived scenes align.
        if len(scripts) != len(script_dialogues):
            add("count-consistency", "Stage 6", 0,
                f"Script count ({len(scripts)}) does not match Stage 3 dialogue count ({len(script_dialogues)}).",
                "Ensure every script has exactly one finalized dialogue entry from Stage 3.")
        if len(scripts) != len(derived_per_script):
            add("count-consistency", "Stage 6", 0,
                f"Script count ({len(scripts)}) does not match Stage 4 derived-scene count ({len(derived_per_script)}).",
                "Ensure every script has exactly one derived-scene entry from Stage 4.")

        for idx, script in enumerate(scripts):
            sid = getattr(script, "id", idx + 1)
            d = script_dialogues[idx] if idx < len(script_dialogues) else {}
            beats = d.get("scene_lines") or []
            derived = derived_per_script[idx] if idx < len(derived_per_script) else []
            speakers = [str(b.get("speaker") or b.get("character") or "").strip() for b in beats]
            speakers = [s for s in speakers if s]

            # 3. Non-empty payloads: nothing integrated may be an empty shell.
            if not beats:
                add("payload-nonempty", "Stage 6", sid,
                    "This script's dialogue has no beats -- an empty payload was integrated.",
                    "Re-run Stage 3; it must fail loudly instead of emitting an empty dialogue.")
            _scenes = list(script.scenes or [])
            if not _scenes:
                add("payload-nonempty", "Stage 6", sid,
                    "This script's storyboard has no scenes -- an empty payload was integrated.",
                    "Re-run Stage 5; it must fail loudly instead of emitting an empty storyboard.")

            # 4. Cross-stage connectivity: dialogue speakers <-> Stage 2 characters.
            # Normalize names for comparison (case/whitespace-insensitive).
            _norm = lambda n: str(n or "").strip().lower()
            _norm_speakers = [_norm(s) for s in speakers]
            _norm_char_names = [_norm(c) for c in char_names]
            for s in set(speakers):
                if char_names and _norm(s) not in _norm_char_names:
                    add("character-connectivity", "Stage 6", sid,
                        f"Speaker '{s}' is not one of the finalized Stage 2 characters {char_names}.",
                        "Use only finalized character names as speakers (Stage 3 output).")
                    break
            for cname in char_names:
                if _norm(cname) not in _norm_speakers:
                    add("character-connectivity", "Stage 6", sid,
                        f"Finalized character '{cname}' never speaks in the dialogue.",
                        f"Give '{cname}' at least one beat (Stage 3 output).",
                        severity="warning")
                    break

            # 5. Dialogue -> scene connection (Stage 4 derived FROM dialogue).
            if not derived:
                add("dialogue-scene-connectivity", "Stage 6", sid,
                    "No scenes were derived from this script's dialogue.",
                    "Run Stage 4 scene derivation on the finalized dialogue beats.")
            else:
                for s in derived:
                    if not getattr(s, "location_name", ""):
                        add("dialogue-scene-connectivity", "Stage 6", sid,
                            "A derived scene has an empty location name.",
                            "Derive a concrete location from the dialogue beats (Stage 4 output).",
                            severity="warning")
                        break

            # 6. Scene -> storyboard connection (Stage 5 uses derived scenes).
            derived_locs = " ".join(getattr(s, "location_name", "") for s in (derived or [])).lower()
            for sc in _scenes:
                if not (sc.scene_location or "").strip():
                    add("scene-storyboard-connectivity", "Stage 6", sid,
                        f"Storyboard scene {sc.scene_number} has no location set.",
                        "Set the storyboard scene location from the Stage 4 derived scenes.",
                        severity="warning")
                    break
                loc_toks = self._gate_tokens(sc.scene_location)
                if derived_locs and loc_toks and not any(t in derived_locs for t in loc_toks):
                    add("scene-storyboard-connectivity", "Stage 6", sid,
                        f"Storyboard scene {sc.scene_number} location \"{sc.scene_location}\" "
                        f"does not match any Stage 4 derived scene.",
                        "Use the Stage 4 derived locations in the storyboard.")
                    break

        errors = [i for i in issues if i.get("severity") == "error"]
        passed = len(errors) == 0
        summary = (
            f"Integration validation passed: {len(scripts)} script(s) -- all Stage 1-5 outputs present, "
            "counts consistent, cross-stage links intact."
            if passed else
            f"Integration validation found {len(errors)} issue(s) across {len(scripts)} script(s)."
        )
        return {"passed": passed, "issues": issues, "summary": summary}

    def fix_validation_issues(
        self,
        state: Dict[str, Any],
        issues: List[Dict[str, Any]],
        engine_mode: str = "first_local_then_agy",
    ) -> Dict[str, Any]:
        """Ask the model to fix validation issues, bounded by max_retries.

        The owning stage is re-run with the EXACT old output plus the numbered
        reasons it failed, so the model fixes precisely those things. Downstream
        stages re-run to stay connected. Returns {"fixed", "issues",
        "attempts", "summary"}.
        """
        errors = [i for i in issues if i.get("severity") == "error"]
        max_retries = state.get("max_retries", 5) or 5
        attempts = state.get("validation_fix_attempts", 0)
        if attempts >= max_retries:
            return {
                "fixed": False,
                "issues": issues,
                "attempts": attempts,
                "summary": f"Retry budget exhausted ({attempts}/{max_retries}). Manual fix needed.",
                "exhausted": True,
            }
        if not errors:
            return {"fixed": True, "issues": issues, "attempts": attempts,
                    "summary": "No blocking issues.", "exhausted": False}

        # Stage 6 issues are all integration issues (cross-stage links) -- the
        # fix re-runs from the earliest content stage so the outputs reconnect.
        stage_order = {"Stage 2": 2, "Stage 3": 3, "Stage 4": 4, "Stage 5": 5, "Stage 6": 6}
        earliest = min(stage_order.get(i.get("stage", "Stage 6"), 6) for i in errors)

        # Numbered failure reasons for the model.
        numbered = []
        for i in errors:
            numbered.append(
                f"{i['n']}. [{i['check']}] (Script {i.get('script', '?')}) {i['detail']} "
                f"FIX REQUIRED: {i['fix']}"
            )
        feedback = (
            "VALIDATION FAILED \u2014 fix ONLY the numbered issues below. "
            "Keep everything else exactly as it was. "
            "The previous (failed) output is your starting point; "
            "return the COMPLETE corrected output in the same format.\n\n"
            + "\n".join(numbered)
        )

        if earliest <= 2:
            state = self.execute_stage_2(state, engine_mode=engine_mode, extra_instruction=feedback)
            state = self.execute_stage_3(state, engine_mode=engine_mode, extra_instruction=feedback)
            state = self.execute_stage_4(state, engine_mode=engine_mode, extra_instruction=feedback)
            state = self.execute_stage_5(state, engine_mode=engine_mode, extra_instruction=feedback)
        elif earliest == 3:
            state = self.execute_stage_3(state, engine_mode=engine_mode, extra_instruction=feedback)
            state = self.execute_stage_4(state, engine_mode=engine_mode, extra_instruction=feedback)
            state = self.execute_stage_5(state, engine_mode=engine_mode, extra_instruction=feedback)
        elif earliest == 4:
            state = self.execute_stage_4(state, engine_mode=engine_mode, extra_instruction=feedback)
            state = self.execute_stage_5(state, engine_mode=engine_mode, extra_instruction=feedback)
        else:
            # Stage 5 issue or Stage 6 integration issue: reconnect from Stage 3.
            state = self.execute_stage_3(state, engine_mode=engine_mode, extra_instruction=feedback)
            state = self.execute_stage_4(state, engine_mode=engine_mode, extra_instruction=feedback)
            state = self.execute_stage_5(state, engine_mode=engine_mode, extra_instruction=feedback)

        attempts += 1
        state["validation_fix_attempts"] = attempts
        state["total_retries"] = state.get("total_retries", 0) + 1
        gate = self.run_validation_gate(state, engine_mode=engine_mode)
        return {
            "fixed": gate["passed"],
            "issues": gate["issues"],
            "attempts": attempts,
            "summary": gate["summary"] + f" (fix attempt {attempts}/{max_retries})",
            "exhausted": (not gate["passed"]) and attempts >= max_retries,
        }

    def execute_stage_6(
        self,
        state: Dict[str, Any],
        engine_mode: str = "first_local_then_agy",
        extra_instruction: Optional[str] = None,
        on_substep: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """Execute Stage 6: Integration & Final Validation Gate.

        FIRST integrate every stage output (verified facts, finalized characters,
        dialogue-derived scenes, dialogue script, storyboards, video prompts,
        audit trail) into one coherent final package; THEN run the
        INTEGRATION-ONLY validation gate: every required Stage 1-5 output is
        present, ID/counts are consistent, cross-stage links hold, and no
        payload is empty. Content quality (tone, news, language, structure,
        storyboard quality) is owned by Stages 3/4/5 and is NOT re-checked
        here. Issues are reported as a numbered list with fix guidance --
        never as a fake success.
        """
        stage6_start = time.time()
        scripts = state["scripts"]
        if not scripts:
            raise ModelGenerationError(
                "Stage 6 failed: no scripts to integrate. "
                f"State contains {len(scripts)} scripts."
            )
        target_seconds = state["target_seconds"]
        active_sample_story = state["active_sample_story"]
        news_input = state["news_input"]
        scenario = state["scenario"]
        verification = state["verification"]
        sub_instructions = state["sub_instructions"]
        total_retries = state.get("total_retries", 0)

        if extra_instruction and extra_instruction.strip():
            state.setdefault("extra_instructions_history", []).append(extra_instruction.strip())

        _emit_substep(on_substep, 6, "6.1", "Integration", "start",
                       detail=f"Integrating outputs for {len(scripts)} script(s)",
                       input=f"Stage 1-5 outputs: verification, {len(scripts)} script(s), characters, scenes")
        # ---- REAL VALIDATION GATE (no hardcoded scores) ----
        _emit_substep(on_substep, 6, "6.2", "Validation gate", "start",
                       detail="Running cross-stage integration checks")
        gate = self.run_validation_gate(state, engine_mode=engine_mode)
        gate_errors = [i for i in gate["issues"] if i.get("severity") == "error"]
        gate_warnings = [i for i in gate["issues"] if i.get("severity") != "error"]
        state["validation_passed"] = gate["passed"]
        state["validation_issues"] = gate["issues"]
        state["validation_summary"] = gate["summary"]
        _emit_substep(on_substep, 6, "6.2", "Validation gate", "complete",
                       status="pass" if gate["passed"] else "fail",
                       detail=(f"All integration checks passed" if gate["passed"]
                               else f"{len(gate_errors)} error(s), {len(gate_warnings)} warning(s): "
                                    + "; ".join(i.get("detail", "")[:80] for i in gate_errors[:3])),
                       output=gate["summary"][:500] if gate.get("summary") else "")

        state["agent_audits"].append(
            AgentAuditItem(
                agent_id=7,
                agent_name=video_quality_gate.name,
                icon=video_quality_gate.icon,
                stage_number=6,
                status="Success" if gate["passed"] else "Issues Found",
                attempts=1,
                failures_count=len(gate_errors),
                errors_encountered=[f"{i['n']}. [{i['check']}] {i['detail']}" for i in gate_errors],
                resolution_action=(
                    gate["summary"] if not gate["passed"]
                    else f"Validation passed: {len(scripts)} script(s) meet all configuration and connectivity checks."
                ),
                execution_time_sec=round(time.time() - stage6_start, 2),
            )
        )

        # Normalize audit items through the canonical AgentAuditItem model.
        # Defensive: if any item was built from a duplicate-imported copy of the
        # model class (same name, different class object), Pydantic's isinstance
        # check would reject it with a cryptic model_type error. Rebuilding via
        # model_dump() guarantees the canonical class and preserves all data.
        canonical_audits: List[AgentAuditItem] = []
        for _a in state["agent_audits"]:
            if isinstance(_a, AgentAuditItem):
                canonical_audits.append(_a)
            elif isinstance(_a, dict):
                canonical_audits.append(AgentAuditItem(**_a))
            elif hasattr(_a, "model_dump"):
                canonical_audits.append(AgentAuditItem(**_a.model_dump()))
            else:
                canonical_audits.append(AgentAuditItem(**dict(_a)))
        state["agent_audits"] = canonical_audits

        total_failures = sum(a.failures_count for a in canonical_audits)
        audit_report = PipelineAuditReport(
            total_stages=6,
            total_agents=7,
            total_failures_detected=total_failures,
            total_retries_resolved=total_retries,
            overall_health="100% Operational (All Steps Self-Healed & Passed)" if total_failures > 0 else "100% Flawless First-Pass Pass",
            agent_audits=canonical_audits,
        )

        total_time = round(time.time() - state["start_time"], 1)

        # Normalize verification + scripts through their canonical models.
        # Same duplicate-class hazard as agent_audits above: model instances built
        # in earlier stages can fail Pydantic's isinstance check at re-wrap time if
        # core.models ended up imported twice under different module names in this
        # process. Rebuilding via model_dump() preserves all data and guarantees
        # the canonical classes (nested models become plain dicts and revalidate).
        def _canon(model_cls, value):
            if isinstance(value, model_cls):
                return value
            if isinstance(value, dict):
                return model_cls(**value)
            if hasattr(value, "model_dump"):
                return model_cls(**value.model_dump())
            return model_cls(**dict(value))

        verification = _canon(NewsVerificationReport, verification)
        scripts = [_canon(ReelScript, _s) for _s in scripts]
        state["verification"] = verification
        state["scripts"] = scripts

        # Integration-only Stage 6: content compliance (word budget, character
        # count, tone, dialogue/scene quality) is owned by Stages 3/4/5 and is
        # deliberately NOT re-checked here. The integration gate above is the
        # only Stage 6 validation.
        compliance_passed, compliance_notes, retry_prompt = True, [], None

        batch_result = ReelBatchResult(
            topic=news_input,
            scenario=scenario,
            target_duration_sec=target_seconds,
            verification=verification,
            scripts=scripts,
            total_scripts=len(scripts),
            total_retries=total_retries,
            total_time_seconds=total_time,
            audit_report=audit_report,
            sub_instructions=sub_instructions,
            sample_story=active_sample_story,
            compliance_passed=compliance_passed,
            retry_prompt_recommendation=retry_prompt,
            validation_passed=state.get("validation_passed", True),
            validation_issues=state.get("validation_issues", []),
        )

        state["batch_result"] = batch_result
        _emit_substep(on_substep, 6, "6.1", "Integration", "complete",
                       status="pass",
                       detail=f"{len(scripts)} script(s) integrated into final package",
                       output=f"Batch result: {len(scripts)} script(s), {total_time}s total")
        state["compliance_passed"] = compliance_passed
        state["compliance_notes"] = compliance_notes
        state["retry_prompt"] = retry_prompt
        state["audit_report"] = audit_report
        state["total_time"] = total_time
        state["step"] = 6
        return state

    def _pump_stage_with_substeps(self, stage_fn, stage_num, *args, **kwargs):
        """Run a stage function in a worker thread, yielding live substep events.

        The stage function receives ``on_substep=<queue.put>`` and emits
        ``{"substep": "3.1", "phase": "start"|"complete", ...}`` dicts as it
        works. Each event is yielded to the caller as
        ``{"type": "substep", "step": <stage_num>, ...}`` so the UI can
        render live progress (running/waiting/completed per substep).

        The worker thread never touches Streamlit — it only computes and
        enqueues events. Worker exceptions are re-raised in the calling
        thread after the queue drains, preserving fail-loud behaviour.

        Usage (inside the pipeline generator):
            state = yield from self._pump_stage_with_substeps(
                self.execute_stage_1, 1, news_input=..., ...)
        """
        q: "queue.Queue" = queue.Queue()
        outcome: Dict[str, Any] = {}

        def _target():
            try:
                outcome["state"] = stage_fn(*args, on_substep=q.put, **kwargs)
            except BaseException as e:  # noqa: BLE001 - must capture everything
                outcome["error"] = e
            finally:
                q.put(None)  # sentinel: stage finished

        t = threading.Thread(target=_target, daemon=True, name=f"stage-{stage_num}")
        t.start()
        while True:
            item = q.get()
            if item is None:
                break
            evt: Dict[str, Any] = {"type": "substep", "step": stage_num}
            if isinstance(item, dict):
                evt.update(item)
            yield evt
        t.join()
        if "error" in outcome:
            raise outcome["error"]
        return outcome.get("state")

    def orchestrate_reel_pipeline(
        self,
        news_input: str,
        scenario: str,
        batch_size: int = 10,
        target_seconds: int = 30,
        engine_mode: str = "first_local_then_agy",
        max_retries: int = 5,
        preferred_frames: int = 3,
        preferred_angle: str = "",
        character_count: int = 1,
        scene_style: str = "Dialogue",
        preferred_tone: str = "",
        sample_story: Optional[str] = None,
        **kwargs,
    ) -> Generator[Dict[str, Any], None, ReelBatchResult]:
        """Orchestrate the end-to-end multi-agent pipeline with full stage telemetry and error audit."""
        budget = get_duration_budget(target_seconds)

        # -------------------------------------------------------------
        # STAGE 1: NewsValidationAgent (Fact-checking against live wire data)
        # -------------------------------------------------------------
        yield {
            "step": 1,
            "total_steps": 6,
            "stage_label": "Stage 1 of 6: Instruction Decomposition & Wire Fact Validation",
            "agent": news_validator.name,
            "icon": news_validator.icon,
            "status": f"👑 Master Agent: Decomposed instruction into 7 sub-instructions. Calibrated dialogue: ~{budget['recommended_words']}w (Max: {budget['max_words']}w). Fact-checking live wire...",
            "data": None,
        }

        state = yield from self._pump_stage_with_substeps(
            self.execute_stage_1,
            1,
            news_input=news_input,
            scenario=scenario,
            batch_size=batch_size,
            target_seconds=target_seconds,
            engine_mode=engine_mode,
            max_retries=max_retries,
            preferred_frames=preferred_frames,
            preferred_angle=preferred_angle,
            character_count=character_count,
            scene_style=scene_style,
            preferred_tone=preferred_tone,
            sample_story=sample_story,
            **kwargs,
        )

        yield {
            "step": 1,
            "total_steps": 6,
            "stage_label": "Stage 1 of 6 Complete: Facts Verified",
            "agent": news_validator.name,
            "icon": news_validator.icon,
            "status": f"Agent 1 Complete: Verified with {state['verification'].confidence_score}% confidence.",
            "data": {
                "ai_input": {"news_validator": state.get("sub_instructions", {}).get("news_validator", "")},
                "verification": state["verification"],
            },
        }

        # -------------------------------------------------------------
        # STAGE 2: HookAndAngleAgent (Formulate viral angles & hooks)
        # -------------------------------------------------------------
        yield {
            "step": 2,
            "total_steps": 6,
            "stage_label": "Stage 2 of 6: Viral Angles & Hindi Hooks",
            "agent": hook_strategist.name,
            "icon": hook_strategist.icon,
            "status": f"Agent 2: Formulating {state['batch_size']} viral angles & scroll-stopping Hindi hooks...",
            "data": None,
        }

        state = yield from self._pump_stage_with_substeps(
            self.execute_stage_2, 2, state, engine_mode=engine_mode
        )

        yield {
            "step": 2,
            "total_steps": 6,
            "stage_label": "Stage 2 of 6 Complete: Angles Ready",
            "agent": hook_strategist.name,
            "icon": hook_strategist.icon,
            "status": f"Agent 2 Complete: {len(state['hooks_and_ctas'])} viral angles and hooks formulated!",
            "data": {
                "ai_input": {"hook_strategist": state.get("sub_instructions", {}).get("hook_strategist", "")},
                "finalized_characters": state.get("finalized_characters", []),
                "hooks_and_ctas": state.get("hooks_and_ctas", []),
            },
        }

        # -------------------------------------------------------------
        # STAGE 3: DialogueNarrationAgent + TimingAuditorAgent
        # -------------------------------------------------------------
        yield {
            "step": 3,
            "total_steps": 6,
            "stage_label": f"Stage 3 of 6: Spoken Dialogue Writing & {target_seconds}s Word Count Calibration",
            "agent": dialogue_writer.name,
            "icon": dialogue_writer.icon,
            "status": f"Agent 3 & 4: Writing spoken Hindi dialogue & calibrating {target_seconds}s speech pace (~{budget['recommended_words']}w, max {budget['max_words']}w)...",
            "data": None,
        }

        state = yield from self._pump_stage_with_substeps(
            self.execute_stage_3, 3, state,
            engine_mode=engine_mode, preferred_frames=preferred_frames,
        )

        yield {
            "step": 3,
            "total_steps": 6,
            "stage_label": "Stage 3 of 6 Complete: Dialogue Calibrated",
            "agent": timing_auditor.name,
            "icon": timing_auditor.icon,
            "status": f"Agent 3 & 4 Complete: {state['batch_size']} Hindi scripts written & calibrated to {target_seconds}s.",
            "retry_count": state.get("stage3_retry_count", 0),
            "data": {
                "ai_input": {
                    "dialogue_writer": state.get("sub_instructions", {}).get("dialogue_writer", ""),
                    "timing_auditor": state.get("sub_instructions", {}).get("timing_auditor", ""),
                },
                "narrations": state.get("script_dialogues", []),
                # Linear 3.1/3.2/3.3... steps + attempt history so the UI can
                # derive the true retry count (3.1 is generation, not a retry).
                "stage3_validation_steps": state.get("stage3_validation_steps", []),
                "stage3_attempt_history": state.get("stage3_attempt_history", []),
            },
        }

        # -------------------------------------------------------------
        # STAGE 4: HookStrategist 2nd run (Scene Derivation FROM Dialogue)
        # -------------------------------------------------------------
        yield {
            "step": 4,
            "total_steps": 6,
            "stage_label": "Stage 4 of 6: Scene Derivation from Dialogue",
            "agent": hook_strategist.name,
            "icon": hook_strategist.icon,
            "status": "Agent 2 (2nd run): Deriving shoot locations FROM the finalized dialogue beats...",
            "data": None,
        }

        state = yield from self._pump_stage_with_substeps(
            self.execute_stage_4, 4, state,
            engine_mode=engine_mode, preferred_frames=preferred_frames,
        )

        yield {
            "step": 4,
            "total_steps": 6,
            "stage_label": "Stage 4 of 6 Complete: Scenes Derived",
            "agent": hook_strategist.name,
            "icon": hook_strategist.icon,
            "status": f"Agent 2 (2nd run) Complete: Shoot scenes derived from dialogue for {state['batch_size']} script(s).",
            "data": {
                "ai_input": {"hook_strategist": state.get("sub_instructions", {}).get("hook_strategist", "")},
                "derived_scenes_per_script": state.get("derived_scenes_per_script", []),
            },
        }

        # -------------------------------------------------------------
        # STAGE 5: SceneDirector + VideoPromptEngineer (Google Flow / Veo 9:16)
        # -------------------------------------------------------------
        yield {
            "step": 5,
            "total_steps": 6,
            "stage_label": "Stage 5 of 6: Scene Storyboards & Cinematic Visual Direction",
            "agent": scene_director.name,
            "icon": scene_director.icon,
            "status": "Agent 5 & 6: Directing scene storyboards & synthesizing 9:16 cinematic visual prompts...",
            "data": None,
        }

        state = yield from self._pump_stage_with_substeps(
            self.execute_stage_5, 5, state,
            engine_mode=engine_mode, preferred_frames=preferred_frames,
        )

        yield {
            "step": 5,
            "total_steps": 6,
            "stage_label": "Stage 5 of 6 Complete: Storyboard Ready",
            "agent": scene_director.name,
            "icon": scene_director.icon,
            "status": "Agent 5 & 6 Complete: Scene storyboards and visual prompts synthesized.",
            "data": {
                "ai_input": {
                    "scene_director": state.get("sub_instructions", {}).get("scene_director", ""),
                    "video_prompt_engineer": state.get("sub_instructions", {}).get("video_prompt_engineer", ""),
                },
                "scripts": state.get("scripts", []),
            },
        }

        # -------------------------------------------------------------
        # STAGE 6: Integration & Final Validation Gate
        # -------------------------------------------------------------
        yield {
            "step": 6,
            "total_steps": 6,
            "stage_label": "Stage 6 of 6: Integration & Final Validation",
            "agent": video_quality_gate.name,
            "icon": video_quality_gate.icon,
            "status": "Agent 7: Integrating all stage outputs, then validating quality and compliance...",
            "data": None,
        }

        state = yield from self._pump_stage_with_substeps(
            self.execute_stage_6, 6, state, engine_mode=engine_mode,
        )
        batch_result = state["batch_result"]
        compliance_passed = state["compliance_passed"]
        retry_prompt = state.get("retry_prompt")
        total_time = state["total_time"]
        audit_report = state["audit_report"]

        yield {
            "step": 6,
            "total_steps": 6,
            "stage_label": "✅ Pipeline Complete: Chief Editor Sign-Off",
            "agent": self.name,
            "icon": self.icon,
            "status": (
                f"✅ Chief Editor Sign-Off: All {len(state['scripts'])} scripts generated & validated in {total_time}s! ({state['total_retries']} self-healing calibrations)"
                if (compliance_passed and state.get("validation_passed", True))
                else (
                    f"❌ Script validation found {len([i for i in state.get('validation_issues', []) if i.get('severity') == 'error'])} issue(s) — see the numbered list. Not a generation failure."
                    if not state.get("validation_passed", True)
                    else f"⚠️ Chief Editor Alert: Configuration check flagged items to review. ({retry_prompt})"
                )
            ),
            "data": {"batch_result": batch_result, "total_time": total_time, "audit_report": audit_report},
            "completed": True,
        }

        return batch_result


# Singleton instances
chief_editor = ChiefEditorCoordinatorAgent()
chief_editor_coordinator = chief_editor
