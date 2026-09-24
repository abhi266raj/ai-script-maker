"""Prompt loader and template utility for agents and methods.

Loads agent system instructions and method prompt templates from external Markdown files
under prompts/<subagent_name>/<method_or_system>.md.
Includes template formatting and in-memory caching.

Contract: a declared prompt file MUST exist, be readable, and be non-empty.
Missing/unreadable/empty files fail loudly — they are never silently replaced
with a fallback. Callers that explicitly pass `default=` opt into a fallback
and get a logged warning when it is used.
"""

import logging
from pathlib import Path
from typing import Optional, Any
import string

logger = logging.getLogger(__name__)

# Base directory for prompt files
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

_PROMPT_CACHE: dict[str, str] = {}


class SafeFormatter(string.Formatter):
    """Formatter that leaves missing keys or unescaped braces intact without throwing KeyError."""

    def get_value(self, key, args, kwargs):
        if isinstance(key, str):
            return kwargs.get(key, "{" + key + "}")
        return super().get_value(key, args, kwargs)


_safe_formatter = SafeFormatter()


def load_prompt(agent_or_filename: str, default: Optional[str] = None) -> str:
    """
    Load an agent prompt file or method template from the prompts directory.

    Supported patterns:
      - Method template: 'prompts/<subagent_name>/<method_name>.md'
        e.g., load_prompt("hook_strategist/craft_hook.md") or load_prompt("hook_strategist/craft_hook")
      - Subdirectory format: 'prompts/<subagent_name>/prompt.md'
        e.g., load_prompt("news_validator") or load_prompt("news_validator/prompt.md")
      - Direct file format: 'prompts/<filename>.md' or 'prompts/<filename>.txt'

    Args:
        agent_or_filename: Subagent name, method path, or relative path
        default: Fallback string if file is missing or unreadable

    Returns:
        The prompt string trimmed of surrounding whitespace.
    """
    key = agent_or_filename.strip().replace("\\", "/")
    if key in _PROMPT_CACHE:
        return _PROMPT_CACHE[key]

    # Candidate file resolution paths in priority order:
    candidates = []

    # If it contains a slash, e.g. "hook_strategist/craft_hook" or "hook_strategist/craft_hook.md"
    if "/" in key:
        parts = key.split("/")
        subagent = parts[0]
        filename = "/".join(parts[1:])
        if not filename.endswith(".md"):
            candidates.append(PROMPTS_DIR / subagent / f"{filename}.md")
        candidates.append(PROMPTS_DIR / subagent / filename)
        candidates.append(PROMPTS_DIR / key)
    else:
        clean_name = key
        if clean_name.endswith((".md", ".txt")):
            stem = clean_name.rsplit(".", 1)[0]
        else:
            stem = clean_name

        # 1. prompts/<stem>/prompt.md
        candidates.append(PROMPTS_DIR / stem / "prompt.md")
        # 2. prompts/<stem>/<stem>.md
        candidates.append(PROMPTS_DIR / stem / f"{stem}.md")
        # 3. Exactly as specified if path provided
        candidates.append(PROMPTS_DIR / key)
        # 4. prompts/<stem>.md
        candidates.append(PROMPTS_DIR / f"{stem}.md")
        # 5. prompts/<stem>.txt
        candidates.append(PROMPTS_DIR / f"{stem}.txt")

    last_error: Optional[Exception] = None
    for candidate in candidates:
        try:
            if candidate.is_file():
                content = candidate.read_text(encoding="utf-8").strip()
                if not content:
                    # An empty prompt file is a broken contract, not a fallback trigger.
                    last_error = ValueError(f"Prompt file is empty: {candidate}")
                    break
                _PROMPT_CACHE[key] = content
                return content
        except (ValueError, OSError) as e:
            # Fail loudly: a present-but-unreadable prompt file is a broken
            # contract, never a reason to silently use a fallback.
            last_error = e
            break
        except Exception as e:  # defensive: keep read details for the error below
            last_error = e
            continue

    if default is not None:
        if last_error is not None:
            logger.warning(
                "Prompt file for %r unreadable (%s); using caller-supplied default.",
                agent_or_filename, last_error,
            )
        return default.strip()

    if last_error is not None:
        raise RuntimeError(
            f"Prompt file for '{agent_or_filename}' exists but could not be read: {last_error}"
        ) from last_error
    raise FileNotFoundError(
        f"Prompt file not found for '{agent_or_filename}'. "
        f"Searched under {PROMPTS_DIR}: {[str(c) for c in candidates]}"
    )


def render_prompt(prompt_path: str, default_template: Optional[str] = None, **kwargs: Any) -> str:
    """
    Load a method prompt template and render it with provided variables.

    Args:
        prompt_path: Path to template, e.g. 'hook_strategist/craft_hook.md'
        default_template: Fallback template string if file not found
        **kwargs: Variables to populate in the template

    Returns:
        The formatted prompt string ready for agent execution.
    """
    template = load_prompt(prompt_path, default=default_template)
    rendered = _safe_formatter.format(template, **kwargs)
    # Capture the exact input prompt when a step is being recorded (UI transparency).
    try:
        from core.prompt_recorder import record
        record(prompt_path, rendered)
    except Exception as e:
        # Recording is observability-only: log the failure, never break generation.
        logger.warning("Prompt recording failed for %s: %s", prompt_path, e)
    return rendered


def clear_prompt_cache() -> None:
    """Clear cached prompts (useful for live reloading or testing)."""
    _PROMPT_CACHE.clear()
