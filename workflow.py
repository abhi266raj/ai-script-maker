"""Multi-Agent Hindi Reel Generation Workflow delegating to ChiefEditorCoordinatorAgent."""

from typing import Generator, Dict, Any, Optional, Callable
from core.models import ReelBatchResult
from core.dual_engine import dual_engine
from core.prompt_recorder import start_recording, stop_recording, get_recorded
from agents.chief_editor import chief_editor_coordinator


def _capture_prompts(fn: Callable[..., Dict[str, Any]], *args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Run a stage while recording every rendered prompt, then attach them
    to the returned state as ``input_prompts`` so the UI can show the exact
    input prompt sent to the AI for that step."""
    start_recording()
    try:
        result = fn(*args, **kwargs)
    finally:
        prompts = get_recorded()
        stop_recording()
    if isinstance(result, dict):
        result["input_prompts"] = prompts
    return result


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

    def run_step_1(
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
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute Step 1 of the pipeline (News Validation & Decomposition)."""
        dual_engine.validate_mode(engine_mode)
        return _capture_prompts(
            chief_editor_coordinator.execute_stage_1,
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
            extra_instruction=extra_instruction,
            **kwargs,
        )

    def run_step_2(
        self,
        state: Dict[str, Any],
        engine_mode: str = "first_local_then_agy",
        extra_instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute Step 2 of the pipeline (Viral Angles & Hooks Formulation)."""
        dual_engine.validate_mode(engine_mode)
        return _capture_prompts(
            chief_editor_coordinator.execute_stage_2,
            state=state,
            engine_mode=engine_mode,
            extra_instruction=extra_instruction,
        )

    def run_step_3(
        self,
        state: Dict[str, Any],
        engine_mode: str = "first_local_then_agy",
        extra_instruction: Optional[str] = None,
        preferred_frames: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Execute Step 3 of the pipeline (Dialogue Writing & Duration Calibration)."""
        dual_engine.validate_mode(engine_mode)
        return _capture_prompts(
            chief_editor_coordinator.execute_stage_3,
            state=state,
            engine_mode=engine_mode,
            extra_instruction=extra_instruction,
            preferred_frames=preferred_frames,
        )

    def run_step_4(
        self,
        state: Dict[str, Any],
        engine_mode: str = "first_local_then_agy",
        extra_instruction: Optional[str] = None,
        preferred_frames: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Execute Step 4 of the pipeline (Scene Finalisation from Finalized Dialogue)."""
        dual_engine.validate_mode(engine_mode)
        return _capture_prompts(
            chief_editor_coordinator.execute_stage_4,
            state=state,
            engine_mode=engine_mode,
            extra_instruction=extra_instruction,
            preferred_frames=preferred_frames,
        )

    def run_step_5(
        self,
        state: Dict[str, Any],
        engine_mode: str = "first_local_then_agy",
        extra_instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute Step 5 of the pipeline (Scene Storyboard & AI Video Prompts)."""
        dual_engine.validate_mode(engine_mode)
        return _capture_prompts(
            chief_editor_coordinator.execute_stage_5,
            state=state,
            engine_mode=engine_mode,
            extra_instruction=extra_instruction,
        )

    def run_step_6(
        self,
        state: Dict[str, Any],
        engine_mode: str = "first_local_then_agy",
        extra_instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute Step 6 of the pipeline (Integration & Final Validation)."""
        dual_engine.validate_mode(engine_mode)
        return _capture_prompts(
            chief_editor_coordinator.execute_stage_6,
            state=state,
            engine_mode=engine_mode,
            extra_instruction=extra_instruction,
        )


reel_workflow = ReelWorkflow()
