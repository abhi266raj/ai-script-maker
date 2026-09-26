# Sub-Feature 01: Scene & Shot Hierarchy Specification

> **Parent Specification:** [`v3/V3.md`](file:///Users/abhiraj/Documents/news/agent/v3/V3.md) — *Scene Scope & Duration* & *Shot Structure*  
> **Status:** Pending Implementation  
> **Feature Branch:** `feature/v3-01-scene-shot-hierarchy`

---

## 1. Objective & Scope

Establish a true two-level narrative hierarchy (**Scene $\to$ Shot**) for 9:16 vertical reels:
1. Replace flat beat sequences with structured scenes dynamically derived from narrative complexity or user constraints.
2. Enforce a strict ceiling of **10 seconds maximum per individual scene** (flexible minimum).
3. **Eliminate Rigid Word Limits:** Scenes are bounded by runtime ($\le 10\text{s}$) and natural speech velocity (2 to 3 wps), not rigid integer word budgets.
4. Standardize scene headings to: `### SCENE X: Title [X Seconds]`.
5. Standardize shot headings within scenes to clean numbered headings without timestamps: `#### Shot 1`, `#### Shot 2`.

---

## 2. Functional Requirements & User Stories

### FR-01.1: Dynamic Scene Count Derivation
- The pipeline MUST dynamically determine the number of scenes based on the story arc (e.g. setup, escalation, twist/resolution), the news scope, or explicit user requests.
- Scene count MUST NOT be locked to arbitrary 5-second integer buckets unless no narrative guidance is provided.

### FR-01.2: Maximum 10-Second Scene Cap (No Rigid Word Limits)
- No single scene may exceed 10.0 seconds in runtime.
- For reels with total duration $> 10$ seconds (e.g. 15s, 30s, 60s), the orchestrator must divide the narrative across at least $\lceil \text{target\_seconds} / 10 \rceil$ distinct scenes.
- Rigid word count limits per beat/scene (e.g. max 11 words) are removed. The 10s duration ceiling is the authoritative physical boundary.

### FR-01.3: Standardized Scene Headings
- Every scene heading MUST strictly follow the syntax:
  ```markdown
  ### SCENE X: <Descriptive Title> [<Duration> Seconds]
  ```
- Example: `### SCENE 1: The Escalation [8 Seconds]`.
- Fabricating missing headings or omitting the runtime bracket `[X Seconds]` is a validation failure.

### FR-01.4: Plain Shot Headings
- Each scene consists of one or more visual shots.
- Shot headings MUST use clean markdown H4 without timestamps:
  ```markdown
  #### Shot 1
  #### Shot 2
  ```
- Timestamps are BANNED from shot headings (timestamps belong only to scene headers, dialogue lines, and SFX cues).

---

## 3. Data Model Changes ([`core/models.py`](file:///Users/abhiraj/Documents/news/agent/core/models.py))

```python
class ShotItem(BaseModel):
    """V3 Plain numbered shot within a scene."""
    shot_number: int  # 1, 2, 3...
    heading: str = ""  # "#### Shot 1"
    camera_focus_and_action: str
    on_screen_text: Optional[str] = None
    video_prompt: Optional[VideoScenePrompt] = None

class SceneItem(BaseModel):
    """V3 Clean-Break Master Scene (max 10 seconds)."""
    scene_number: int  # 1, 2, 3...
    title: str  # Short descriptive title
    duration_sec: float  # <= 10.0 seconds
    heading: str = ""  # "### SCENE 1: The Escalation [8 Seconds]"
    character: str
    dialogue: str
    dialogue_timestamp: str  # "[0:01 – 0:04.5]"
    tone: str  # e.g. "Frantic", "Sarcastic"
    audio_sfx: str
    audio_sfx_timestamp: str  # "[0:00 – 0:02]"
    visual_anchor: Optional[str] = None
    audio_bleed: Optional[str] = None
    shots: List[ShotItem] = Field(default_factory=list)
```

---

## 4. Deterministic Code Validators

1. **`validate_scene_duration_cap(script)`:**
   - Evaluates `scene.duration_sec <= 10` for every scene.
   - Raises `ModelGenerationError` if any scene exceeds 10 seconds.
2. **`validate_scene_heading_syntax(heading)`:**
   - Regex matches `r"^### SCENE \d+:\s*.+\s*\[\d+\s*Seconds\]$"`.
3. **`validate_shot_heading_syntax(shot_heading)`:**
   - Regex matches `r"^#### Shot \d+$"`.
   - Raises if timestamps or extra text appear in the shot heading.

---

## 5. Acceptance Criteria & Test Plan

- [ ] Unit tests in `tests/test_v3_scene_hierarchy.py` verify model serialization and parsing.
- [ ] Test scene duration validator rejects scenes $>10$s.
- [ ] Test heading validator accepts valid V3 scene headings and rejects non-compliant formats.
- [ ] Integration with `core/screenplay_formatter.py` renders compliant `### SCENE X` and `#### Shot X` structures.
