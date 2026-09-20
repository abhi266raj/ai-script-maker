"""Prompt loader utility for agents.

Loads agent system prompts/instructions from external Markdown files under prompts/<subagent_name>/prompt.md.
Includes in-memory caching and optional default fallback if file cannot be read.
"""

from pathlib import Path
from typing import Optional

# Base directory for prompt files
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

_PROMPT_CACHE: dict[str, str] = {}


def load_prompt(agent_or_filename: str, default: Optional[str] = None) -> str:
    """
    Load an agent prompt file from the prompts directory.

    Supported patterns:
      - Subdirectory format (Preferred): 'prompts/<subagent_name>/prompt.md'
        e.g., load_prompt("news_validator") or load_prompt("news_validator/prompt.md")
      - Direct file format: 'prompts/<filename>.md' or 'prompts/<filename>.txt'

    Args:
        agent_or_filename: Subagent name (e.g. 'news_validator') or relative path
        default: Fallback string if file is missing or unreadable

    Returns:
        The prompt string trimmed of surrounding whitespace.
    """
    key = agent_or_filename.strip().replace("\\", "/")
    if key in _PROMPT_CACHE:
        return _PROMPT_CACHE[key]

    # Candidate file resolution paths in priority order:
    candidates = []

    clean_name = key.rstrip("/").split("/")[-1]
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

    for candidate in candidates:
        try:
            if candidate.is_file():
                content = candidate.read_text(encoding="utf-8").strip()
                _PROMPT_CACHE[key] = content
                return content
        except Exception:
            continue

    if default is not None:
        return default.strip()

    raise FileNotFoundError(f"Prompt file not found for '{agent_or_filename}' in {PROMPTS_DIR}")


def clear_prompt_cache() -> None:
    """Clear cached prompts (useful for live reloading or testing)."""
    _PROMPT_CACHE.clear()
