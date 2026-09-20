"""Core package for Dual-Engine Hindi Reel System."""
from .dual_engine import dual_engine, DualEngine
from .fm_engine import fm_engine, FMEngine
from .models import (
    NewsArticle,
    NewsVerificationReport,
    SceneItem,
    ReelScript,
    ReelBatchResult,
)
from .metrics import (
    count_words,
    verify_word_count,
    verify_timeline_fit,
    evaluate_clarity,
    get_duration_budget,
)
from .prompt_loader import load_prompt, PROMPTS_DIR

__all__ = [
    "dual_engine",
    "DualEngine",
    "fm_engine",
    "FMEngine",
    "NewsArticle",
    "NewsVerificationReport",
    "SceneItem",
    "ReelScript",
    "ReelBatchResult",
    "count_words",
    "verify_word_count",
    "verify_timeline_fit",
    "evaluate_clarity",
    "get_duration_budget",
    "load_prompt",
    "PROMPTS_DIR",
]
