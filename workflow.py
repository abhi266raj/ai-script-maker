"""Multi-Agent Hindi Reel Generation Workflow delegating to ChiefEditorCoordinatorAgent.

Core workflow implementation lives in core.workflow.
"""

from core.workflow import ReelWorkflow, reel_workflow, _capture_prompts

__all__ = ["ReelWorkflow", "reel_workflow", "_capture_prompts"]
