"""Multi-Agent Hindi Reel Generation Workflow delegating to ChiefEditorCoordinatorAgent."""

from typing import Generator, Dict, Any, Optional
from core.models import ReelBatchResult
from core.dual_engine import dual_engine
from agents.chief_editor import chief_editor_coordinator


class ReelWorkflow:
    """Delegates to ChiefEditorCoordinatorAgent for specialized multi-agent pipeline execution."""

    def run_stream(
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
        **kwargs,
    ) -> Generator[Dict[str, Any], None, ReelBatchResult]:
        """Execute the multi-agent pipeline."""
        # Validate the user's selected model before fetching news or starting
        # any agent work. This keeps failures fast and prevents fallback or
        # synthetic output from being presented as a completed script.
        dual_engine.validate_mode(engine_mode)
        return chief_editor_coordinator.orchestrate_reel_pipeline(
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


reel_workflow = ReelWorkflow()
