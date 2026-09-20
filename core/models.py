"""Data models for Hindi Reel Script Generation with AI Video Generation & Self-Healing Retries."""

from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class NewsArticle(BaseModel):
    """Raw or parsed news item fetched from web/RSS."""
    title: str
    link: str
    source: str
    snippet: str = ""
    published: str = ""


class NewsVerificationReport(BaseModel):
    """Step 1: News Verification Report & Story Research Dossier."""
    is_verified: bool = True
    confidence_score: int = 90  # 0 to 100
    verification_summary: str = ""
    verified_facts: List[str] = Field(default_factory=list)
    flagged_claims: List[str] = Field(default_factory=list)
    sources: List[NewsArticle] = Field(default_factory=list)
    # Story Research & Visual Props Dossier
    physical_props: List[str] = Field(default_factory=list)
    key_locations: List[str] = Field(default_factory=list)
    core_conflict_or_irony: str = ""
    tangible_actions: List[str] = Field(default_factory=list)



class VideoScenePrompt(BaseModel):
    """AI Video Generation Prompt (Google Veo / Flow / AI Video Engine)."""
    scene_number: int
    timestamp: str  # e.g. "0:00 - 0:03"
    visual_prompt_ai: str  # Highly detailed prompt for Google Veo/Flow
    camera_movement: str = "Dynamic push-in"
    lighting_and_mood: str = "Cinematic golden hour / high contrast"
    aspect_ratio: str = "9:16"
    motion_level: str = "Medium-High"
    ai_engine: str = "Google Flow / Veo"


class VideoPassVerification(BaseModel):
    """Feasibility & Quality Gate Verification for AI Video Generation."""
    passed: bool = True
    feasibility_score: int = 95  # 0-100
    safety_compliance: str = "Passed"
    temporal_consistency: str = "Passed"
    visual_clarity_check: str = "Passed"
    feedback: str = "Prompt complies with AI video generation guidelines."


class SceneItem(BaseModel):
    """Timestamped 9:16 screenplay scene with visual direction and spoken dialogue."""
    scene_number: int
    act_name: str = "Act 1: Hook"
    character: str = "🎙️ Presenter (मुख्य वक्ता)"
    dialogue: str = ""
    timestamp: str
    visual_b_roll: str
    on_screen_text: str  # Hindi text overlay
    audio_sfx: str
    video_prompt: Optional[VideoScenePrompt] = None


class ReelScript(BaseModel):
    """Complete reel script with multi-step verifications and self-healing logs."""
    id: int
    title: str
    angle: str
    hook_hindi: str
    narration_hindi: str
    call_to_action: str
    scenes: List[SceneItem] = Field(default_factory=list)

    # Step 2: Spoken Dialogue Word Count Verification (Narration Only)
    word_count: int = 0
    min_words: int = 4
    recommended_words: int = 10
    max_words: int = 11
    is_over_budget: bool = False
    word_count_status: str = "Optimal"
    word_count_feedback: str = ""

    # Step 3: Timeline & Duration Fit
    target_duration_sec: int = 30
    estimated_duration_sec: float = 0.0
    timeline_fit_status: str = "Fits Timeline"
    timeline_feedback: str = ""

    # Step 4: AI Video Generation & Pass Verification
    video_verification: VideoPassVerification = Field(default_factory=VideoPassVerification)

    # Step 5: Clarity & Self-Healing Retry Tracking
    clarity_score: int = 95
    music_vibe: str = "Trending High-Energy Beat"
    retry_count: int = 0
    self_healing_notes: List[str] = Field(default_factory=list)
    engine_used: str = "Local FM"

    # Step 6: Configuration Compliance & Acceptance Gate
    configuration_compliance: bool = True
    compliance_notes: List[str] = Field(default_factory=list)
    sample_story_used: Optional[str] = None


class AgentAuditItem(BaseModel):
    """Audit entry tracking failures, retries, and errors per agent."""
    agent_id: int
    agent_name: str
    icon: str
    stage_number: int
    status: str = "Success"  # "Success", "Self-Healed", "Warning", "Fallback"
    attempts: int = 1
    failures_count: int = 0
    errors_encountered: List[str] = Field(default_factory=list)
    resolution_action: str = "Passed on initial run"
    execution_time_sec: float = 0.0


class PipelineAuditReport(BaseModel):
    """Comprehensive failure and error telemetry across all 7 agents."""
    total_stages: int = 5
    total_agents: int = 7
    total_failures_detected: int = 0
    total_retries_resolved: int = 0
    overall_health: str = "100% Operational"
    agent_audits: List[AgentAuditItem] = Field(default_factory=list)


class ReelBatchResult(BaseModel):
    """Batch output containing multiple of 10 scripts with full audit telemetry."""
    topic: str
    scenario: str
    target_duration_sec: int = 30
    verification: NewsVerificationReport
    scripts: List[ReelScript] = Field(default_factory=list)
    total_scripts: int = 10
    total_retries: int = 0
    total_time_seconds: float = 0.0
    audit_report: Optional[PipelineAuditReport] = None
    sub_instructions: dict = Field(default_factory=dict)
    sample_story: Optional[str] = None
    compliance_passed: bool = True
    retry_prompt_recommendation: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().strftime("%B %d, %Y - %H:%M"))
