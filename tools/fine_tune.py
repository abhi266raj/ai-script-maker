"""Iterative LLM fine-tuning of a story's script (issue #105).

The user gives a natural-language instruction ("make it funnier"); the LLM
surgically refines the current script and the result replaces the story's
script. Every turn is recorded in the story's frontmatter (see
``story_library.get_fine_tune_history`` / ``record_fine_tune_turn``) so the
conversation carries across turns — and so the script-versioning feature
(#104) can later adopt the history as versions.

Fail-loud contract: blank inputs, LLM errors, and blank LLM output all raise
``FineTuneError``. A failed turn never silently keeps the old script and
never records a turn that didn't happen.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Sequence


class FineTuneError(Exception):
    """A fine-tune turn could not be completed. Never silent."""


# System instructions for the refining model. Mirrors the tone-compliance
# rules of prompts/dialogue_writer (an unfollowed tone requirement is a bug),
# but generalized: the script being refined may be the final screenplay
# format, not just the dialogue batch.
FINE_TUNE_SYSTEM_INSTRUCTIONS = """You are refining a finalized Hindi reel script from the user's own library, based on their change instruction. This is a SURGICAL REFINEMENT — not a fresh generation.

REFINE MANDATE
- Change ONLY what the user's instruction targets. Keep every line, beat, joke, and character moment that already works.
- The user's instruction is the HIGHEST PRIORITY. Follow it exactly — but stay inside the script's existing structure and format.
- TONE (NON-NEGOTIABLE): the script's tone is "{tone}". The instruction may ask for a different tone or mood — when it does, apply the NEW tone consistently. Whichever tone governs the result: at least 70% of beats must clearly embody it and ZERO beats may contradict it. Funny → every funny beat carries a REAL joke (setup + punchline), with laughter where humor lands. Somber → no jokes, no laughter anywhere. A tone shift never licenses dropping the news facts.
- Keep the news grounded: the refined script must still carry the story's key event, people/entities, and verified facts — woven into the characters' voices, never as a lecture.
- Dialogue stays in pure spoken Hindi (Devanagari), matching the current draft's voice. Never quote the instruction back; just apply it.
- Keep the current script's length and structure (same sections, same beats) unless the instruction explicitly asks to add, remove, or restructure.

OUTPUT
- Emit the COMPLETE refined script, in exactly the same format and structure as the current script.
- Output bans (a violation fails the output): never print word counts, timings, metadata, emojis, bracketed instructions, or explanations of what you changed. Only the refined script."""


def _default_generate(prompt: str, instructions: str, mode: str) -> str:
    """Default LLM call: the same dual-engine path script generation uses.

    ``mode`` is the user's selected engine mode (#210) — it is required.
    A falsy mode means AI is disabled ("None" in the toolbar dropdown) and
    raises loudly: fine-tune must never silently fall back to the default
    engine and never silently no-op.
    """
    from core.dual_engine import dual_engine

    if not mode:
        raise FineTuneError(
            "AI is disabled — select an engine in the toolbar AI dropdown "
            "to fine-tune.")
    response, _engine_used = dual_engine.generate(
        prompt=prompt, instructions=instructions, mode=mode)
    return response


def build_fine_tune_prompt(
    current_script: str,
    instruction: str,
    story_context: str = "",
    history: Sequence[Dict[str, str]] = (),
    tone: str = "",
) -> str:
    """Assemble the refinement prompt: context + script + history + instruction."""
    history_lines: List[str] = []
    for i, turn in enumerate(history or (), 1):
        turn_instruction = (turn.get("instruction") or "").strip()
        turn_script = (turn.get("script") or "").strip()
        history_lines.append(
            f"--- Turn {i} ---\n"
            f"Instruction: {turn_instruction}\n"
            f"Refined script:\n{turn_script}")
    history_block = "\n\n".join(history_lines) if history_lines else \
        "(none yet — this is the first turn)"

    return (
        f"STORY CONTEXT\n{(story_context or '').strip() or '(none)'}\n\n"
        f"TONE\n{(tone or '').strip() or '(keep the tone already established in the current draft)'}\n\n"
        f"CURRENT SCRIPT — the exact visible script; your ONLY baseline\n{current_script}\n\n"
        f"PREVIOUS FINE-TUNE TURNS (oldest first — the last turn produced the current script above)\n{history_block}\n\n"
        f"USER'S NEW INSTRUCTION (HIGHEST PRIORITY)\n{instruction}\n\n"
        f"Refine the current script now, following the mandate. Output only the refined script."
    )


def fine_tune_script(
    current_script: str,
    instruction: str,
    story_context: str = "",
    history: Sequence[Dict[str, str]] = (),
    tone: str = "",
    generate_fn: Callable[[str, str], str] | None = None,
    engine_mode: str | None = None,
) -> str:
    """Refine ``current_script`` per ``instruction`` via the LLM.

    Args:
        current_script: the exact current script text (the baseline).
        instruction: what the user wants changed (e.g. "make it funnier").
        story_context: story title / topic / headline for grounding.
        history: prior turns, oldest first — each ``{"instruction", "script"}``.
        tone: the script's tone (from the story meta); carried into the
            system instructions so tone compliance stays non-negotiable.
        generate_fn: ``(prompt, instructions) -> str``; defaults to the
            dual-engine path. Injectable for tests.
        engine_mode: the user's selected engine mode (#210), threaded to
            ``dual_engine.generate``. Required on the real LLM path: a
            falsy mode (AI disabled — "None" in the toolbar dropdown)
            raises loudly instead of silently falling back to the default
            engine. Ignored when ``generate_fn`` is injected.

    Returns the refined script text.

    Raises:
        FineTuneError: blank script/instruction, AI disabled, LLM failure,
            or blank LLM output. Never returns the unmodified script as a
            "result".
    """
    script = (current_script or "").strip()
    if not script:
        raise FineTuneError("There is no script to refine — the current script is empty.")
    instruction_text = (instruction or "").strip()
    if not instruction_text:
        raise FineTuneError("Describe what to change first — e.g. \"make it funnier\".")
    if generate_fn is None and not engine_mode:
        raise FineTuneError(
            "AI is disabled — select an engine in the toolbar AI dropdown "
            "to fine-tune.")

    instructions = FINE_TUNE_SYSTEM_INSTRUCTIONS.format(
        tone=(tone or "").strip() or "as established in the current draft")
    prompt = build_fine_tune_prompt(
        current_script=script,
        instruction=instruction_text,
        story_context=story_context or "",
        history=history or (),
        tone=tone or "",
    )
    generate = generate_fn or (lambda p, i: _default_generate(p, i, engine_mode))
    try:
        refined = generate(prompt, instructions)
    except Exception as e:
        raise FineTuneError(f"The model failed to refine the script: {e}") from e
    refined_text = (refined or "").strip()
    if not refined_text:
        raise FineTuneError(
            "The model returned an empty refinement — the script was left unchanged.")
    return refined_text
