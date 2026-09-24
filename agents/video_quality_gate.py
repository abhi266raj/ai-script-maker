"""Agent 7: AI Video Quality Gate & Feasibility Auditor Agent."""

import re
from typing import List, Optional, Dict, Any
from agents.base import BaseAgent
from core.models import VideoScenePrompt, VideoPassVerification
from core.dual_engine import ModelGenerationError
from core.prompt_loader import load_prompt, render_prompt

QUALITY_GATE_INSTRUCTIONS = load_prompt("video_quality_gate/audit_prompts.md")
VALIDATE_INTEGRATION_PROMPT = "video_quality_gate/validate_integration.md"


class VideoQualityGateAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Video Quality Gate Auditor",
            role="AI Video Feasibility & Quality Gate Verification",
            icon="🛡️",
            instructions=QUALITY_GATE_INSTRUCTIONS,
            prompt_file="video_quality_gate/audit_prompts.md",
        )

    def audit_prompts(
        self,
        prompts: List[VideoScenePrompt],
        sub_instruction: Optional[str] = None,
        engine_mode: str = "first_local_then_agy",
    ) -> VideoPassVerification:
        """Advisory-only audit of video prompts. Never fails a run (user requirement 2026-09-24)."""
        prompts_summary = "\n".join([f"Scene {p.scene_number} ({p.timestamp}): {p.visual_prompt_ai[:110]}..." for p in prompts])
        sub_directive = f"\nChief Editor Quality Gate Directive:\n{sub_instruction}\n" if sub_instruction else ""

        prompt = render_prompt(
            "video_quality_gate/audit_prompts.md",
            sub_directive=sub_directive,
            prompts_summary=prompts_summary,
        )

        # ADVISORY ONLY (user requirement 2026-09-24): the Stage 5 gate must
        # NEVER fail a run. Judge outages return an advisory pass.
        try:
            raw_output = self.execute(prompt, engine_mode=engine_mode)
        except Exception as e:
            return VideoPassVerification(
                passed=True,
                feasibility_score=0,
                safety_compliance="advisory",
                temporal_consistency="advisory",
                visual_clarity_check="advisory",
                feedback=(
                    "Advisory: quality-gate judge unavailable "
                    f"({type(e).__name__}: {e}). Prompts ship as-is."
                ),
            )

        # Lenient parse. No score threshold: the gate never fails a run.
        # Missing/unparseable fields are advisory, not fatal.
        status_match = re.search(r"STATUS:\s*\[?\s*(PASSED|FAILED)\s*\]?", raw_output or "", re.IGNORECASE)
        status = status_match.group(1).upper() if status_match else "UNKNOWN"
        score_match = re.search(r"SCORE:\s*\[?(\d{2,3})\]?%", raw_output or "", re.IGNORECASE)
        try:
            score = int(score_match.group(1)) if score_match else 0
        except (ValueError, IndexError):
            score = 0
        # Advisory only: passed is always True.
        passed = True

        # Lenient field extraction. Missing fields default to "unknown".
        def _judge_field(label: str) -> str:
            for line in (raw_output or "").split("\n"):
                if line.strip().upper().startswith(label):
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        val = parts[1].strip("[] \"'"
                        )
                        if val:
                            return val
            return "unknown"

        safety = _judge_field("SAFETY:")
        temporal = _judge_field("TEMPORAL:")
        clarity = _judge_field("CLARITY:")

        feedback = ""
        for line in (raw_output or "").split("\n"):
            if "FEEDBACK:" in line.upper():
                feedback = line.split("FEEDBACK:", 1)[-1].strip()
                break
        if not feedback:
            feedback = "Advisory: judge returned no structured feedback."
        # Surface the judge's verdict as advisory notes, never as a blocker.
        feedback = f"[Advisory] Judge status: {status}, score: {score}%. {feedback}"

        return VideoPassVerification(
            passed=passed,
            feasibility_score=score,
            safety_compliance=safety,
            temporal_consistency=temporal,
            visual_clarity_check=clarity,
            feedback=feedback,
        )

    def validate_integration(
        self,
        package_summary: str,
        scene_style: str,
        tone: str,
        angle: str,
        characters: List[str],
        target_seconds: int,
        min_words: int,
        max_words: int,
        script_id: int = 0,
        engine_mode: str = "first_local_then_agy",
    ) -> List[Dict[str, Any]]:
        """Judge one finished script package against its config and cross-stage
        connectivity. Returns a list of issue dicts (empty when clean).
        Raises ModelGenerationError if the judge model itself fails."""
        prompt = render_prompt(
            VALIDATE_INTEGRATION_PROMPT,
            scene_style=scene_style,
            tone=tone,
            angle=angle or "High-retention viral perspective",
            characters=", ".join(characters) if characters else "(none finalized)",
            target_seconds=target_seconds,
            min_words=min_words,
            max_words=max_words,
            package_summary=package_summary,
        )
        raw_output = self.execute(prompt, engine_mode=engine_mode)
        return self.parse_validation_issues(raw_output, script_id=script_id)

    # Deterministic check → stage mapping. The model's stage attribution is
    # unreliable (e.g. it says "Stage 2" for dialogue tone issues), so we
    # override it based on the check type. Detection is always Stage 6.
    CHECK_TO_STAGE = {
        "tone-70": "Stage 3",
        "style-fidelity": "Stage 3",
        "news-intelligibility": "Stage 3",
        "dialogue-scene-connection": "Stage 4",
        "scene-storyboard-connection": "Stage 5",
        "continuity": "Stage 5",
    }

    @staticmethod
    def parse_validation_issues(raw_output: str, script_id: int = 0) -> List[Dict[str, Any]]:
        """Parse the strict ISSUE-block format into issue dicts. Pure function.

        Fails loudly: an empty judge output is a judge outage, not a clean
        bill of health; an incomplete ISSUE block is a contract violation.
        Only an explicit NO ISSUES verdict means "no issues".
        """
        issues: List[Dict[str, Any]] = []
        text = (raw_output or "").strip()
        if not text:
            raise ModelGenerationError(
                "Stage 6 failed: integration judge returned empty output. "
                "An empty verdict is a judge failure, not 'no issues'."
            )
        if text.upper().startswith("NO ISSUES"):
            return issues
        blocks = re.split(r"(?im)^ISSUE:\s*$", text)
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            check = stage = detail = fix = ""
            for line in block.split("\n"):
                low = line.strip().lower()
                if low.startswith("check:"):
                    check = line.split(":", 1)[1].strip()
                elif low.startswith("stage:"):
                    stage = line.split(":", 1)[1].strip()
                elif low.startswith("detail:"):
                    detail = line.split(":", 1)[1].strip()
                elif low.startswith("fix:"):
                    fix = line.split(":", 1)[1].strip()
            missing = [label for label, val in
                       (("CHECK", check), ("STAGE", stage),
                        ("DETAIL", detail), ("FIX", fix))
                       if not val]
            if missing:
                raise ModelGenerationError(
                    "Stage 6 failed: integration judge returned an incomplete ISSUE block "
                    f"(missing: {', '.join(missing)}). "
                    f"Block snippet: {block[:300]!r}"
                )
            _check_key = check.strip().lower()
            _stage = VideoQualityGateAgent.CHECK_TO_STAGE.get(_check_key, stage)
            issues.append({
                "check": check,
                "stage": _stage,
                "detail": detail,
                "fix": fix,
                "script": script_id,
                "source": "model",
            })
        if not issues:
            raise ModelGenerationError(
                "Stage 6 failed: integration judge returned no parseable ISSUE blocks "
                "and no explicit NO ISSUES verdict. "
                f"Raw output snippet: {text[:400]!r}"
            )
        return issues


video_quality_gate = VideoQualityGateAgent()
