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
    age_hours: Optional[float] = None
    time_label: str = ""


class NewsVerificationReport(BaseModel):
    """Step 1: News Verification Report & Story Research Dossier."""
    headline: str = ""
    # Fail-loud: no default "verified" — the Stage 1 validator must always
    # supply these explicitly. A missing verdict must raise, never read True/90.
    is_verified: bool
    confidence_score: int  # 0 to 100
    verification_summary: str = ""
    verified_facts: List[str] = Field(default_factory=list)
    flagged_claims: List[str] = Field(default_factory=list)
    sources: List[NewsArticle] = Field(default_factory=list)
    # Story Research & Visual Props Dossier
    physical_props: List[str] = Field(default_factory=list)
    key_locations: List[str] = Field(default_factory=list)
    core_conflict_or_irony: str = ""
    tangible_actions: List[str] = Field(default_factory=list)


class CharacterProfile(BaseModel):
    """Step 2: Finalized Character Profile (Actor, Occupation, Attire, Persona)."""
    name: str
    role_or_job: str
    attire: str = ""
    emotional_stance: str = ""
    relationship_dynamic: str = ""


class StoryBeatStep(BaseModel):
    """Step 2: Story Beat Action Step."""
    beat_number: int
    character_name: str
    action_step: str
    speech_objective: str


class SceneSettingOption(BaseModel):
    """Step 2: Finalized Scene Setting / Location Option (for downstream 9:16 scene selection)."""
    scene_option_number: int = 1
    location_name: str
    atmosphere: str = ""
    lighting_mood: str = ""
    props: List[str] = Field(default_factory=list)


class VideoScenePrompt(BaseModel):
    """AI Video Generation Prompt (Google Veo / Flow / AI Video Engine)."""
    scene_number: int
    timestamp: str  # e.g. "0:00 - 0:03"
    visual_prompt_ai: str  # Highly detailed prompt for Google Veo/Flow
    # Fail-loud: no invented camera/lighting/motion/engine defaults — the video
    # prompt engineer must supply every field from the model output.
    camera_movement: str
    lighting_and_mood: str
    aspect_ratio: str
    motion_level: str
    ai_engine: str


class VideoPassVerification(BaseModel):
    """Feasibility & Quality Gate Verification for AI Video Generation."""
    # Fail-loud: no default "passed" — the gate must always supply its verdict
    # explicitly. A missing verdict must raise, never read as passed/95.
    passed: bool
    feasibility_score: int  # 0-100
    safety_compliance: str = "Passed"
    temporal_consistency: str = "Passed"
    visual_clarity_check: str = "Passed"
    feedback: str = ""


class SceneItem(BaseModel):
    """Timestamped 9:16 screenplay scene with visual direction and spoken dialogue."""
    scene_number: int
    # Fail-loud: no invented act/persona — neutral empties, never a fake identity.
    act_name: str = ""
    character: str = ""
    dialogue: str = ""
    timestamp: str
    visual_b_roll: str
    on_screen_text: str  # Hindi text overlay
    audio_sfx: str
    video_prompt: Optional[VideoScenePrompt] = None
    # Step-4 coordination: per-beat direction + Step 2 system-knowledge pass-through.
    # The character bible (role/attire/emotion) and the selected scene setting flow
    # from the system into the final output — they are never re-invented per beat.
    emotion: str = ""  # character's emotional expression while delivering this beat
    character_role: str = ""  # from Step 2 character bible
    character_attire: str = ""  # from Step 2 character bible
    scene_location: str = ""  # selected (or newly created) location for this beat
    scene_atmosphere: str = ""
    scene_lighting: str = ""
    scene_props: List[str] = Field(default_factory=list)
    scene_source: str = ""  # "supplied" (selected from Step 2 options) | "new" (created in Step 4)


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
    # Optional since 2026-09-24: the advisory AI quality gate was removed, so
    # no verdict is produced anymore. None = gate did not run (honest), never
    # a default "passed" — see VideoPassVerification's fail-loud fields.
    video_verification: Optional[VideoPassVerification] = None

    # Step 5: Clarity & Self-Healing Retry Tracking
    clarity_score: int = 95
    # Fail-loud: no invented soundtrack — neutral empty until a real pick exists.
    music_vibe: str = ""
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
    # Fail-loud: no default "Success" — the pipeline must record the real outcome.
    status: str = ""  # "Success", "Self-Healed", "Warning", "Fallback"
    attempts: int = 1
    failures_count: int = 0
    errors_encountered: List[str] = Field(default_factory=list)
    resolution_action: str = ""
    execution_time_sec: float = 0.0


class PipelineAuditReport(BaseModel):
    """Comprehensive failure and error telemetry across all 7 agents."""
    total_stages: int = 5
    total_agents: int = 7
    total_failures_detected: int = 0
    total_retries_resolved: int = 0
    # Fail-loud: no default "100% Operational" — health is computed, never assumed.
    overall_health: str = ""
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
    validation_passed: bool = True
    validation_issues: list = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().strftime("%B %d, %Y - %H:%M"))
