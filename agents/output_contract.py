"""Shared model-agnostic output contracts for the 6-stage reel pipeline.

Architecture decisions enforced here:

  AD-1: Every agent call declares its expected output format in the prompt
        input. The canonical per-stage specs live in STAGE_CONTRACTS and the
        prompt files that must carry an OUTPUT FORMAT section are listed in
        STAGE_PROMPT_FILES.
  AD-2: Output contracts are validated app-wide in CODE, deterministically,
        independent of the selected model ("on changing model"). Any mismatch
        raises ModelGenerationError with stage + field + raw-snippet detail so
        it flows into the normal retry flow. No silent parser drops, no
        synthetic fallbacks.
  AD-3: Machine-consumed stage outputs use JSON with a declared schema.
        Free-text-with-headers parsing is banned for machine-consumed outputs.
        One lightweight repair (strip markdown fences / leading-trailing junk)
        is allowed; invalid JSON or missing required keys then fail loudly.
  AD-4: Stage 3 outputs only the script beats (no SCENE DETAIL, no
        CHARACTERS & CLOTHING, no format-requirement line, no preamble).

Verification verdicts: after the cheap deterministic checks fail-fast, one AI
verification call per stage returns a single JSON verdict::

    {"verdict": "pass", "<aspect>": "pass"|"fail", ..., "reasons": [...]}

Aspect names per stage live in VERIFICATION_ASPECTS. ``validate_verdict``
checks the verdict JSON itself against the contract — a malformed verdict
fails loudly instead of slipping through.

This module is intentionally dependency-free (stdlib only) so it can be
imported by any stage without pulling in engines or agent code.
"""

import json
import re
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Canonical markers / constants
# ---------------------------------------------------------------------------

OUTPUT_FORMAT_MARKER = "OUTPUT FORMAT"
"""Every stage prompt template MUST contain this marker (case-insensitive)."""

DEFAULT_MAX_RETRIES = 3
"""Max generation/validation retry rounds per stage (FR-20.7).

Attempt 1 is the initial generation and is NEVER counted as a retry.
"""

VALID_VERDICTS = ("pass", "fail")


class ModelGenerationError(Exception):
    """Raised when model output violates its declared output contract.

    Carries the stage, what went wrong, what was expected, and a snippet of
    the raw model output so the failure is loud and debuggable. Handled by
    the normal per-stage retry loop (up to DEFAULT_MAX_RETRIES attempts).
    """

    def __init__(
        self,
        stage: str,
        reason: str,
        snippet: str = "",
        expected: str = "",
    ) -> None:
        self.stage = stage
        self.reason = reason
        self.snippet = snippet
        self.expected = expected
        parts = [f"[ModelGenerationError] stage={stage}", f"reason={reason}"]
        if expected:
            parts.append(f"expected={expected}")
        if snippet:
            parts.append(f"raw_snippet={snippet!r}")
        super().__init__(" | ".join(parts))


# ---------------------------------------------------------------------------
# Per-stage output contracts
# ---------------------------------------------------------------------------

_GENERIC_ATTIRE_BANS = [
    "everyday wear",
    "casual wear",
    "casual clothes",
    "t-shirt and jeans",
    "normal clothes",
]

STAGE_CONTRACTS: Dict[str, Dict[str, Any]] = {
    "stage_1": {
        "name": "Facts & Verification",
        "kind": "json",
        # Complete Stage 1 dossier schema (AD-3). Parsed fully with
        # json.loads; missing keys fail loudly — no partial field loss.
        "required_keys": [
            "verification_status",
            "confidence",
            "summary",
            "facts",
            "key_figures",
            "key_locations",
            "props",
            "conflict",
            "actions",
            "flags",
        ],
        "banned_lines": [
            "insufficiently verified",
            "supplied excerpts",
            "based on the provided sources",
        ],
        "description": (
            "Stage 1 returns the complete verification dossier as a single JSON "
            "object with keys: verification_status, confidence, summary, facts, "
            "key_figures, key_locations, props, conflict, actions, flags. "
            "No verification-process narration."
        ),
    },
    "stage_2": {
        "name": "Character Finalisation",
        "variants": {
            "groups": {
                "kind": "text",
                "required_markers": [
                    "GROUP A:",
                    "GROUP B:",
                    "CHARACTER 1:",
                    "Name:",
                    "Job:",
                    "Attire:",
                    "Emotion:",
                    "Relationship:",
                ],
                "banned_lines": _GENERIC_ATTIRE_BANS + ["**", "##"],
                "description": (
                    "Stage 2 (groups variant) returns exactly two character "
                    "groups (GROUP A, GROUP B) in plain text, each character "
                    "with Name/Job/Attire/Emotion/Relationship. No markdown, "
                    "no dialogue, no scenes, no generic attire."
                ),
            },
            "characters": {
                "kind": "text",
                "required_markers": [
                    "CHARACTER 1:",
                    "Name:",
                    "Job:",
                    "Attire:",
                    "Emotion:",
                    "Relationship:",
                ],
                "banned_lines": _GENERIC_ATTIRE_BANS + ["**", "##"],
                "description": (
                    "Stage 2 (characters variant) returns a flat character list "
                    "in plain text, each character with Name/Job/Attire/Emotion/"
                    "Relationship. No markdown, no dialogue, no scenes, no "
                    "generic attire."
                ),
            },
        },
    },
    "stage_3": {
        "name": "Dialogue",
        "kind": "json",
        # AD-4: beats ONLY. No SCENE DETAIL, no CHARACTERS & CLOTHING,
        # no [Format Requirement] line, no preamble.
        "required_keys": ["beats"],
        "beat_keys": ["beat", "speaker", "dialogue", "camera_action", "sfx", "overlay"],
        "banned_lines": [
            "[Format Requirement]",
            "SCENE DETAIL",
            "CHARACTERS & CLOTHING",
        ],
        "description": (
            "Stage 3 returns ONLY the script as JSON: "
            '{"beats": [{"beat": 1, "speaker": "...", "dialogue": "<Hindi '
            'Devanagari only>", "camera_action": "<English>", "sfx": '
            '"<English>", "overlay": "<English or empty>"}]}. No markdown '
            "fences, no preamble, no trailing prose."
        ),
    },
    "stage_4": {
        "name": "Scene Finalisation from Dialogue",
        "kind": "text",
        "required_markers": [
            "SCENE 1:",
            "Location:",
            "Atmosphere:",
            "Lighting:",
            "Props:",
            "Grounded in beats:",
        ],
        "banned_lines": ["DIALOGUE:", "TIME:", "[Time:"],
        "description": (
            "Stage 4 returns exactly the required scenes in plain text, each "
            "with Location/Atmosphere/Lighting/Props/Grounded in beats. "
            "Visual only — never quotes dialogue, never writes timestamps."
        ),
    },
    "stage_5": {
        "name": "Storyboards & AI Video Prompts",
        "variants": {
            "storyboard": {
                "kind": "text",
                "required_markers": [
                    "SCENE 1:",
                    "CHARACTER:",
                    "ACTION:",
                    "TEXT:",
                    "SFX:",
                ],
                "banned_lines": ["DIALOGUE:", "[Time:"],
                "description": (
                    "Stage 5 storyboards are visual only: per scene CHARACTER / "
                    "ACTION / TEXT (English) / SFX. Never quotes dialogue, "
                    "never writes timestamps."
                ),
            },
            "video_prompts": {
                "kind": "text",
                "required_markers": [
                    "SCENE 1:",
                    "PROMPT:",
                    "CAMERA:",
                    "LIGHTING:",
                    "MOTION:",
                    "Cinematic 9:16 vertical shot:",
                ],
                "banned_lines": ["Google Flow", "Veo", "Sora"],
                "description": (
                    "Stage 5 video prompts are pure cinematic visual prompts "
                    "starting with 'Cinematic 9:16 vertical shot:'. No vendor "
                    "names, no dialogue quotes."
                ),
            },
        },
    },
    "stage_6": {
        "name": "Integration & Final Validation",
        "kind": "json",
        # The stage-6 judge returns the standard verification verdict JSON.
        "is_verdict": True,
        "required_keys": ["verdict", "reasons"],
        "description": (
            "Stage 6 returns the integration validation verdict as JSON: "
            '{"verdict": "pass"|"fail", <aspect>: "pass"|"fail", '
            '"reasons": [...]} with one aspect per check in '
            "VERIFICATION_ASPECTS['stage_6']. Judge only — never rewrites."
        ),
    },
}

# ---------------------------------------------------------------------------
# Verification-verdict aspects (one AI verification call per stage)
# ---------------------------------------------------------------------------

VERIFICATION_ASPECTS: Dict[str, List[str]] = {
    "stage_1": ["verification_status", "facts_complete", "news_grounded"],
    "stage_2": ["character_grounding", "attire_specificity", "distinctness"],
    "stage_3": ["voice", "tone", "news_coverage", "language"],
    "stage_4": ["scene_count", "dialogue_grounding"],
    # Stage 5 enforced checks are deterministic (visual-only prompts, no
    # dialogue, well-formed/complete). The AI video-prompt audit
    # (prompts/video_quality_gate/audit_prompts.md) is ADVISORY ONLY and
    # cannot fail the stage (FR-20.8).
    "stage_5": ["visual_only", "no_dialogue", "well_formed"],
    "stage_6": [
        "tone_70",
        "style_fidelity",
        "news_intelligibility",
        "dialogue_scene_connection",
        "scene_storyboard_connection",
        "continuity",
    ],
}

# ---------------------------------------------------------------------------
# Stage prompt files that must declare their OUTPUT FORMAT (AD-1)
# ---------------------------------------------------------------------------

STAGE_PROMPT_FILES: Dict[str, List[str]] = {
    "stage_1": [
        "prompts/news_validator/validate_news.md",
    ],
    "stage_2": [
        "prompts/hook_strategist/finalise_character_groups.md",
        "prompts/hook_strategist/finalise_characters_only.md",
    ],
    "stage_3": [
        "prompts/dialogue_writer/write_dialogue_batch.md",
        "prompts/dialogue_writer/refine_dialogue_batch.md",
    ],
    "stage_4": [
        "prompts/hook_strategist/derive_scenes_from_dialogue.md",
    ],
    "stage_5": [
        "prompts/scene_director/direct_scenes.md",
        "prompts/video_prompt_engineer/generate_prompts.md",
        "prompts/video_quality_gate/audit_prompts.md",
    ],
    "stage_6": [
        "prompts/video_quality_gate/validate_integration.md",
    ],
}


# ---------------------------------------------------------------------------
# Helpers

# ---------------------------------------------------------------------------


def _normalize_stage(stage: Any) -> str:
    """Normalize 3 / "3" / "stage_3" / "Stage 3" to the "stage_3" key."""
    if isinstance(stage, int):
        key = f"stage_{stage}"
    else:
        s = str(stage).strip().lower().replace(" ", "_").replace("-", "_")
        key = s if s.startswith("stage_") else f"stage_{s}"
    if key not in STAGE_CONTRACTS:
        raise ValueError(
            f"Unknown stage {stage!r}; expected one of {sorted(STAGE_CONTRACTS)}"
        )
    return key


def _snippet(raw_text: str, limit: int = 300) -> str:
    text = (raw_text or "").strip().replace("\n", " ")
    return text[:limit] + ("…" if len(text) > limit else "")


def strip_json_fences(raw_text: str) -> str:
    """One lightweight repair (AD-3): strip markdown fences / surrounding junk.

    Removes ```json ... ``` / ``` ... ``` wrappers, then trims any leading or
    trailing non-JSON junk by slicing from the first '{' to the last '}'.
    Anything still unparseable after this fails loudly in the caller.
    """
    text = (raw_text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1].strip()
    return text


def prompt_has_output_format(prompt_text: str) -> bool:
    """Check a prompt template declares its OUTPUT FORMAT (AD-1)."""
    return OUTPUT_FORMAT_MARKER.lower() in (prompt_text or "").lower()


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def _check_banned(stage_label: str, spec: Dict[str, Any], raw_text: str) -> None:
    lowered = raw_text.lower()
    for banned in spec.get("banned_lines", []):
        if banned.lower() in lowered:
            raise ModelGenerationError(
                stage=stage_label,
                reason=f"Banned content in model output: {banned!r}",
                snippet=_snippet(raw_text),
                expected=spec.get("description", ""),
            )


def _check_markers(stage_label: str, spec: Dict[str, Any], raw_text: str) -> None:
    markers = spec.get("required_markers", [])
    missing = [m for m in markers if m not in raw_text]
    if missing:
        raise ModelGenerationError(
            stage=stage_label,
            reason=f"Missing required output sections: {missing}",
            snippet=_snippet(raw_text),
            expected=spec.get("description", ""),
        )
    # Required sections must appear in the declared order.
    positions = [raw_text.index(m) for m in markers]
    if positions != sorted(positions):
        raise ModelGenerationError(
            stage=stage_label,
            reason="Required output sections are out of order",
            snippet=_snippet(raw_text),
            expected=f"Sections in order: {markers}",
        )


def _parse_json(stage_label: str, spec: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(strip_json_fences(raw_text))
    except (json.JSONDecodeError, ValueError) as exc:
        raise ModelGenerationError(
            stage=stage_label,
            reason=f"Invalid JSON: {exc}",
            snippet=_snippet(raw_text),
            expected=spec.get("description", ""),
        ) from exc
    if not isinstance(parsed, dict):
        raise ModelGenerationError(
            stage=stage_label,
            reason=f"Top-level JSON must be an object, got {type(parsed).__name__}",
            snippet=_snippet(raw_text),
            expected=spec.get("description", ""),
        )
    return parsed


def validate_output(
    stage: Any,
    raw_text: str,
    parsed: Optional[Dict[str, Any]] = None,
    variant: Optional[str] = None,
) -> bool:
    """Validate one stage's raw model output against its declared contract.

    Fully deterministic and model-agnostic (AD-2). Raises ModelGenerationError
    (stage + reason + raw snippet + expectation) on ANY mismatch so the
    failure flows into the normal retry loop. Returns True when valid.

    Args:
        stage: 3, "3", "stage_3" or "Stage 3".
        raw_text: the raw model output string.
        parsed: optional already-parsed JSON (skips re-parsing for json kinds).
        variant: required for stages with variants (stage_2: "groups" /
            "characters"; stage_5: "storyboard" / "video_prompts").
    """
    key = _normalize_stage(stage)
    contract = STAGE_CONTRACTS[key]
    if "variants" in contract:
        variants = contract["variants"]
        if not variant:
            raise ValueError(
                f"Stage {key} requires variant= one of {sorted(variants)}"
            )
        if variant not in variants:
            raise ValueError(
                f"Unknown variant {variant!r} for {key}; "
                f"expected one of {sorted(variants)}"
            )
        spec = variants[variant]
        label = f"{key}/{variant}"
    else:
        spec = contract
        label = key

    raw_text = raw_text or ""
    if not raw_text.strip():
        raise ModelGenerationError(
            stage=label,
            reason="Empty model output",
            snippet="",
            expected=spec.get("description", ""),
        )
    _check_banned(label, spec, raw_text)

    if spec.get("kind", "text") == "json":
        data = parsed if isinstance(parsed, dict) else _parse_json(label, spec, raw_text)
        missing = [k for k in spec.get("required_keys", []) if k not in data]
        if missing:
            raise ModelGenerationError(
                stage=label,
                reason=f"Missing required JSON keys: {missing}",
                snippet=_snippet(raw_text),
                expected=spec.get("description", ""),
            )
        # AD-4: Stage 3 beats must be a non-empty list of complete beat dicts.
        if key == "stage_3":
            beats = data.get("beats")
            if not isinstance(beats, list) or not beats:
                raise ModelGenerationError(
                    stage=label,
                    reason="Stage 3 'beats' must be a non-empty list",
                    snippet=_snippet(raw_text),
                    expected=spec.get("description", ""),
                )
            for i, beat in enumerate(beats):
                if not isinstance(beat, dict):
                    raise ModelGenerationError(
                        stage=label,
                        reason=f"Beat {i + 1} is not a JSON object",
                        snippet=_snippet(raw_text),
                        expected=spec.get("description", ""),
                    )
                missing_keys = [k for k in spec.get("beat_keys", []) if k not in beat]
                if missing_keys:
                    raise ModelGenerationError(
                        stage=label,
                        reason=f"Beat {i + 1} missing keys: {missing_keys}",
                        snippet=_snippet(raw_text),
                        expected=spec.get("description", ""),
                    )
        if spec.get("is_verdict"):
            validate_verdict(key, raw_text, parsed=data)
    else:
        _check_markers(label, spec, raw_text)
    return True


def validate_verdict(
    stage: Any,
    raw_text: str,
    parsed: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate one stage's AI verification-verdict JSON against its contract.

    Expected shape (FR-20.5)::

        {"verdict": "pass", "<aspect>": "pass"|"fail", ..., "reasons": [...]}

    Rules enforced: verdict and every aspect in VERIFICATION_ASPECTS[stage]
    must be "pass"/"fail"; reasons must be a list; verdict "pass" requires all
    aspects "pass"; verdict "fail" requires at least one failing aspect and a
    non-empty reasons list. Extra keys are allowed and ignored. A well-formed
    "fail" verdict does NOT raise here — it is valid output; the retry flow
    handles it. Anything malformed raises ModelGenerationError.
    """
    key = _normalize_stage(stage)
    aspects = VERIFICATION_ASPECTS.get(key, [])
    data = parsed if isinstance(parsed, dict) else _parse_json(key, {"description": "verification verdict JSON"}, raw_text or "")

    verdict = data.get("verdict")
    if verdict not in VALID_VERDICTS:
        raise ModelGenerationError(
            stage=key,
            reason=f"Verdict 'verdict' must be 'pass' or 'fail', got {verdict!r}",
            snippet=_snippet(raw_text),
            expected='{"verdict": "pass"|"fail", <aspect>: "pass"|"fail", "reasons": [...]}',
        )
    if "reasons" not in data or not isinstance(data["reasons"], list):
        raise ModelGenerationError(
            stage=key,
            reason="Verdict 'reasons' must be a list",
            snippet=_snippet(raw_text),
            expected='{"verdict": "pass"|"fail", <aspect>: "pass"|"fail", "reasons": [...]}',
        )
    for aspect in aspects:
        value = data.get(aspect, "__missing__")
        if value not in VALID_VERDICTS:
            raise ModelGenerationError(
                stage=key,
                reason=f"Verdict aspect {aspect!r} must be 'pass' or 'fail', got {value!r}",
                snippet=_snippet(raw_text),
                expected=f"Aspects for {key}: {aspects}",
            )
    failing = [a for a in aspects if data.get(a) == "fail"]
    if verdict == "pass" and failing:
        raise ModelGenerationError(
            stage=key,
            reason=f"Verdict is 'pass' but aspects failed: {failing}",
            snippet=_snippet(raw_text),
            expected="verdict 'pass' requires every aspect 'pass'",
        )
    if verdict == "fail" and not failing:
        raise ModelGenerationError(
            stage=key,
            reason="Verdict is 'fail' but no aspect failed",
            snippet=_snippet(raw_text),
            expected="verdict 'fail' requires at least one failing aspect",
        )
    if verdict == "fail" and not data["reasons"]:
        raise ModelGenerationError(
            stage=key,
            reason="Failing verdict must list reasons",
            snippet=_snippet(raw_text),
            expected="verdict 'fail' requires a non-empty 'reasons' list",
        )
    return data