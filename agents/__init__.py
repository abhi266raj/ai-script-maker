"""Specialized Multi-Agent Pipeline package."""

from .base import BaseAgent
from .news_validator import NewsValidationAgent, news_validator
from .hook_strategist import HookAndAngleAgent, hook_strategist
from .dialogue_writer import DialogueNarrationAgent, dialogue_writer
from .timing_auditor import WordCountDurationAgent, timing_auditor
from .scene_director import SceneVisualsDirectorAgent, scene_director
from .video_prompt_engineer import AIVideoPromptAgent, video_prompt_engineer
from .video_quality_gate import VideoQualityGateAgent, video_quality_gate
from .chief_editor import ChiefEditorCoordinatorAgent, chief_editor_coordinator
from core.angles import REEL_ANGLES

__all__ = [
    "BaseAgent",
    "NewsValidationAgent",
    "news_validator",
    "HookAndAngleAgent",
    "hook_strategist",
    "DialogueNarrationAgent",
    "dialogue_writer",
    "WordCountDurationAgent",
    "timing_auditor",
    "SceneVisualsDirectorAgent",
    "scene_director",
    "AIVideoPromptAgent",
    "video_prompt_engineer",
    "VideoQualityGateAgent",
    "video_quality_gate",
    "ChiefEditorCoordinatorAgent",
    "chief_editor_coordinator",
    "REEL_ANGLES",
]
