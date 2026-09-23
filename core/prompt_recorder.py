"""Records rendered prompts per pipeline step for UI transparency.

The recorder is a no-op unless explicitly started. workflow.run_step_N
starts it around each stage so the app can show the exact input prompt
that was sent to the AI for every step ("View Input Prompt").
"""

import contextvars
from typing import Dict, List

_recording = contextvars.ContextVar("prompt_recording", default=None)


def start_recording() -> List[Dict[str, str]]:
    """Begin capturing rendered prompts in the current context."""
    rec: List[Dict[str, str]] = []
    _recording.set(rec)
    return rec


def stop_recording() -> None:
    """Stop capturing rendered prompts in the current context."""
    _recording.set(None)


def is_recording() -> bool:
    return _recording.get() is not None


def record(template: str, prompt: str) -> None:
    """Capture one rendered prompt (no-op when not recording)."""
    rec = _recording.get()
    if rec is not None:
        rec.append({"template": template or "", "prompt": prompt or ""})


def get_recorded() -> List[Dict[str, str]]:
    """Return a copy of everything recorded so far in this context."""
    return list(_recording.get() or [])
