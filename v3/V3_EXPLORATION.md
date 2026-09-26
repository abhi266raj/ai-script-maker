# V3 Master Scriptwriting Specifications — Gap Analysis & Implementation Roadmap

> **Document Status:** Active Exploration & Architecture Specification  
> **Source Specification:** [`V3.md`](file:///Users/abhiraj/Documents/news/agent/v3/V3.md)  
> **Target:** Hindi Reel Studio (AI Script Maker Pipeline)

---

## 1. Executive Summary

The V3 specification outlined in [`V3.md`](file:///Users/abhiraj/Documents/news/agent/v3/V3.md) establishes a major leap in screenplay craftsmanship, video generation reliability, and cinematic pacing for 9:16 vertical reels. 

This document evaluates the existing codebase (v1.2 / multi-stage agent pipeline) against the master V3 guidelines, categorizing every requirement into:
- ✅ **Completed:** Fully implemented and verified in the current system.
- 🟡 **Partially Completed / In Conflict:** Exists partially or contradicts legacy prompt/validation logic.
- ❌ **Missing:** Not present in current models, prompts, formatters, or validators.
- 🚀 **What to Implement:** Exact technical actions, schema updates, prompt changes, and validator rules required.

---

## 2. Requirement-by-Requirement Audit & Gap Analysis

```
┌───────────────────────────────────────┬─────────────┬────────────────────────────────────────────────────────┐
│ V3 Specification Requirement          │ Status      │ Current Codebase Reality                               │
├───────────────────────────────────────┼─────────────┼────────────────────────────────────────────────────────┤
│ 1. Format & Language                  │             │                                                        │
│    • 9:16 vertical reel format        │ ✅ Complete │ Enforced across models, prompts & formatters           │
│    • Visual/camera cues in English    │ ✅ Complete │ Enforced in ScreenplayFormatter & Stage 4/5 prompts   │
│    • Spoken dialogue in Devanagari    │ ✅ Complete │ Natural Hindustani enforced via Stage 3 & validators   │
├───────────────────────────────────────┼─────────────┼────────────────────────────────────────────────────────┤
│ 2. Scene Scope & Duration             │             │                                                        │
│    • Dynamic scene count (arc/scope)  │ ❌ Missing  │ Hardcoded lookup in `metrics.py` based only on seconds │
│    • Cap scenes at max 10s            │ ❌ Missing  │ Pipeline operates on flat beats without scene max-cap  │
│    • Heading: `### SCENE X: [X Sec]`  │ ❌ Missing  │ Formatter uses flat `BEAT X:` or `[Time: ...]`; no sec │
├───────────────────────────────────────┼─────────────┼────────────────────────────────────────────────────────┤
│ 3. Timestamp Scoping & Precision      │             │                                                        │
│    • Reset timestamps to 0:00/scene   │ ❌ Missing  │ Timestamps are cumulative across entire reel           │
│    • Explicit [0:XX–0:XX] on dialogue │ ❌ Missing  │ Timestamps only at beat header level, not on lines/SFX │
├───────────────────────────────────────┼─────────────┼────────────────────────────────────────────────────────┤
│ 4. Shot Structure                     │             │                                                        │
│    • Plain `#### Shot X` headings     │ ❌ Missing  │ No Scene -> Shot hierarchy; flat list of SceneItems    │
│    • No timestamps in shot headings   │ ❌ Missing  │ Beat headings contain time brackets                    │
├───────────────────────────────────────┼─────────────┼────────────────────────────────────────────────────────┤
│ 5. Performance & Delivery Direction   │             │                                                        │
│    • Delivery & speed cadence cues    │ 🟡 Conflict │ Prompts explicitly BAN bracketed stage directions      │
│    • Words-per-second (~2.8 wps)      │ ❌ Missing  │ Only global speech rates exist, never per-line wps     │
├───────────────────────────────────────┼─────────────┼────────────────────────────────────────────────────────┤
│ 6. Seamless Scene-to-Scene Links      │             │                                                        │
│    • Direct Consequence               │ 🟡 Partial  │ Beat ping-pong exists, but not cross-scene consequence │
│    • Visual Anchors across cuts       │ ❌ Missing  │ No visual anchor continuity across cuts                │
│    • Audio Bleed (1-2s trailing SFX)  │ ❌ Missing  │ SFX are isolated per beat without cross-scene bleed    │
│    • Conversational Carryover         │ 🟡 Partial  │ Intra-scene dialogue pivots exist, not inter-scene     │
├───────────────────────────────────────┼─────────────┼────────────────────────────────────────────────────────┤
│ 7. Spatial Consistency & Cast Isol.   │             │                                                        │
│    • Unified physical setting         │ ✅ Complete │ `harmonize_setting_description` unifies locations      │
│    • Cast Isolation (rotate cast)     │ 🟡 Conflict │ Code does ping-pong with same cast in all beats        │
├───────────────────────────────────────┼─────────────┼────────────────────────────────────────────────────────┤
│ 8. Minimal Prop Execution             │             │                                                        │
│    • Facial reactions & gestures      │ 🟡 Partial  │ Physical action lines exist                            │
│    • Stationary minimal props only    │ 🟡 Conflict │ `screenplay_coherence.py` injects heavy prop handling  │
└───────────────────────────────────────┴─────────────┴────────────────────────────────────────────────────────┘
```

---

## 3. Deep Dive: What is Completed, Missing, and In Conflict

### 3.1. Format & Language
* **What is Completed:**
  * Script format is locked to 9:16 vertical in [`core/screenplay_formatter.py`](file:///Users/abhiraj/Documents/news/agent/core/screenplay_formatter.py) and [`core/models.py`](file:///Users/abhiraj/Documents/news/agent/core/models.py).
  * Strict language division: English for visual/camera/audio cues, Devanagari script for all spoken dialogue.
  * Common person's Hindustani vocabulary is enforced via deterministic code checks (`tests/test_common_hindi.py` banning formal Sanskritized terms).

---

### 3.2. Scene Scope & Duration
* **What is Missing:**
  1. **Dynamic Scene Count Determination:** Currently, scene count is calculated mechanically via `get_duration_budget()` in [`core/metrics.py`](file:///Users/abhiraj/Documents/news/agent/core/metrics.py) using fixed tables (e.g., 30s = 5 beats). V3 requires dynamically deriving scene count from the narrative arc, story complexity, or explicit user prompts.
  2. **10-Second Scene Cap:** Individual scenes must be capped at a maximum of 10 seconds. Currently, beats have word limits but no hard individual scene duration cap.
  3. **Standardized Scene Heading:** The required syntax `### SCENE X: Title [X Seconds]` (e.g. `### SCENE 1: The Escalation [8 Seconds]`) does not exist in the screenplay formatters or prompts.

---

### 3.3. Timestamp Scoping & Precision
* **What is Missing:**
  1. **Per-Scene Timestamp Reset:** In the current system, timestamps are cumulative across the entire script (`0:00 - 0:05`, `0:05 - 0:10`, `0:10 - 0:15`). V3 requires audio, dialogue, and SFX timestamps to **reset to `[0:00]` at the start of each scene**.
  2. **Direct Line-Level Timestamps:** Timestamps must be attached directly to dialogue lines and SFX cues:
     ```text
     Audio/SFX [0:00 – 0:02]: Ambient street hum + low drone
     KABIR [0:01 – 0:05] [Frantic delivery ~2.8 wps]: "यह फैसला सीधे हमारी जेब पर असर डालेगा!"
     ```
     Currently, timestamps exist only as beat headers (`[Time: 0:00 - 0:05]`).

---

### 3.4. Shot Structure
* **What is Missing:**
  1. **Two-Level Hierarchy (Scene → Shots):** Current pipeline flattens everything into a single list of `scenes` (which are really beats). V3 specifies distinct **Scenes** containing one or more **Shots**.
  2. **Shot Headings:** Shots within a scene must use clean, un-timestamped headings: `#### Shot 1`, `#### Shot 2`.

---

### 3.5. Performance & Delivery Direction
* **What is in Conflict:**
  * In current prompts ([`prompts/dialogue_writer/write_dialogue.md`](file:///Users/abhiraj/Documents/news/agent/prompts/dialogue_writer/write_dialogue.md#L28) and [`prompts/dialogue_writer/write_dialogue_batch.md`](file:///Users/abhiraj/Documents/news/agent/prompts/dialogue_writer/write_dialogue_batch.md#L165)), bracketed instructions are **strictly banned** (`"NO stage directions or brackets. Output ONLY pure spoken Hindi dialogue"`).
* **What is Missing:**
  * V3 requires every dialogue line to include emotional delivery energy and speed cadence:
    `[Frantic delivery ~2.8 wps]` or `[Deadpan comedic shrug ~2.0 wps]`.
  * The system needs speed calculation and cadence estimation based on syllable/word count and duration.

---

### 3.6. Seamless Scene-to-Scene Connectivity
* **What is Missing:**
  1. **Direct Consequence:** Enforcing that Scene $N+1$ opens with an immediate physical or verbal reaction to the event/climax of Scene $N$.
  2. **Visual Anchors across Cuts:** Ensuring focal objects, characters, or environmental elements from Scene $N$ remain visible in the background or edge of frame in Scene $N+1$.
  3. **Audio Bleed:** Trailing SFX or ambient sound from the tail of Scene $N$ must carry over into the first 1–2 seconds `[0:00 – 0:02]` of Scene $N+1$.
  4. **Conversational Carryover:** Opening dialogue of Scene $N+1$ must directly reference the specific event that concluded Scene $N$.

---

### 3.7. Spatial Consistency & Cast Isolation
* **What is Completed:**
  * Spatial consistency: `harmonize_setting_description` in [`core/script_analyzer.py`](file:///Users/abhiraj/Documents/news/agent/core/script_analyzer.py) preserves a single unified physical setting.
* **What is in Conflict / Missing:**
  * **Cast Isolation (Cast Rotation):** Current behavior features the same 2 characters talking throughout the entire reel. V3 mandates: **"Rotate the on-screen cast so that characters featured in one scene do not appear in the subsequent scene."**
  * Stage 2 and Stage 3 must support ensemble casting and enforce strict scene-by-scene character rotation:
    $$\text{Cast}(\text{Scene } N) \cap \text{Cast}(\text{Scene } N+1) = \emptyset$$

---

### 3.8. Minimal Prop Execution
* **What is in Conflict:**
  * [`agents/screenplay_coherence.py`](file:///Users/abhiraj/Documents/news/agent/agents/screenplay_coherence.py) currently forces characters to manipulate physical props (unfolding newspapers, picking up chai glasses, thrusting smartphones, pressing rubber stamps).
  * Video generation engines (Veo, Sora, Kling) frequently fail or produce morphing artifacts during complex object manipulation.
* **What is Missing:**
  * V3 requires **Minimal Prop Execution**: physical props must remain stationary within the environment. Action must be driven by facial expressions, exaggerated body language, vocal delivery, and environmental staging.

---

## 4. Implementation Roadmap (What to Implement)

### Phase 1: Data Model & Hierarchy Upgrades
1. **Hierarchical Screenplay Models (`core/models.py`):**
   - Create `ShotItem`:
     - `shot_number: int`
     - `heading: str` (`"#### Shot 1"`)
     - `camera_focus_and_action: str`
     - `visual_b_roll: str`
     - `video_prompt: Optional[VideoScenePrompt]`
   - Update `SceneItem` to represent an actual Scene (up to 10s):
     - `scene_number: int`
     - `title: str`
     - `duration_sec: int` (max 10s)
     - `heading: str` (`"### SCENE X: Title [X Seconds]"`)
     - `character: str`
     - `delivery_cue: str` (e.g. `"[Frantic delivery ~2.8 wps]"`)
     - `dialogue: str`
     - `dialogue_timestamp: str` (`"[0:01 – 0:05]"`)
     - `audio_sfx: str`
     - `audio_sfx_timestamp: str` (`"[0:00 – 0:02]"`)
     - `audio_bleed: Optional[str]`
     - `visual_anchor: Optional[str]`
     - `shots: List[ShotItem]`

### Phase 2: Prompt Engineering & Agent Refactoring
1. **Dialogue Writer Prompts (`prompts/dialogue_writer/`):**
   - Update `write_dialogue_batch.md` to remove the blanket ban on brackets for delivery cues.
   - Mandate cadence and tone tagging: `[Tone/Energy ~X.X wps]`.
   - Implement inter-scene conversational carryover and direct consequence rules.
2. **Hook Strategist & Character Finalization (`agents/hook_strategist.py`):**
   - Support ensemble generation for cast isolation (at least 2 distinct sets of characters across adjacent scenes).
3. **Scene Director (`agents/scene_director.py` & `prompts/scene_director/direct_scenes.md`):**
   - Enforce multi-shot structure (`#### Shot 1`, `#### Shot 2`) without timestamps.
   - Enforce Minimal Prop Execution: stationary props, expressive facial reactions, environmental staging.
   - Define Visual Anchors across scene cuts.
4. **Audio & Coherence Auditor (`agents/screenplay_coherence.py`):**
   - Implement Audio Bleed: carry over trailing SFX into the first 1-2s of subsequent scenes.
   - Replace active prop manipulation with stationary prop staging + character kinematics.

### Phase 3: Screenplay Formatter & Timers
1. **V3 Formatter (`core/screenplay_formatter.py`):**
   - Implement `format_v3_screenplay(script) -> str` producing canonical V3 markdown:
     ```markdown
     [Format Requirement: 9:16 Vertical Reel | All scene descriptions in English, Dialogues strictly in Hindi]

     SCENE DETAIL:
     ⚬ Studio apartment corridor, high noon tension

     CHARACTERS & CLOTHING:
     ⚬ AMIT: Navy blue delivery jacket, reflective strips
     ⚬ PRIYA: Crimson formal blazer, ID lanyard

     ### SCENE 1: The Delivery Confrontation [7 Seconds]

     #### Shot 1
     Camera Focus & Action: Dynamic push-in on Amit standing before the closed door. Minimal props: parcel resting stationary on the doorstep.
     Audio/SFX [0:00 – 0:02]: Muffled hallway echo + urgent doorbell chime
     Text Overlay: NEW POLICY ALERT

     ⚬ AMIT [Frantic] [0:01 – 0:04.5]:
       "यह नया नियम लागू होते ही हमारा इंसेंटिव आधा हो जाएगा!"

     ### SCENE 2: The Inside Reaction [8 Seconds]
     Visual Anchor: Amit's silhouette visible through the frosted glass door frame in the background.
     Audio Bleed: Muffled doorbell echo carries over from Scene 1 [0:00 – 0:02].

     #### Shot 1
     Camera Focus & Action: Reverse angle inside the office. Priya turns sharply from her desk with wide eyes.
     Audio/SFX [0:00 – 0:03]: Keyboard clatter cut short + tense ambient hum

     ⚬ PRIYA [Sharp] [0:02 – 0:06.5]:
       "कंपनी ने साफ कर दिया है, अब हर ऑर्डर पर नया टैक्स कटेगा!"
     ```
2. **Scene & Dialogue Time Scoping:**
   - Deterministic timestamp calculation resetting to `[0:00]` per scene.
   - Direct start-to-end `[0:XX – 0:XX]` computation for both dialogue lines and SFX.

### Phase 4: Deterministic Code Validators
1. **Scene Duration Cap Validator:** Verify every scene duration $\le 10$ seconds.
2. **Cast Isolation Validator:** Ensure $\text{Cast}(\text{Scene } N) \cap \text{Cast}(\text{Scene } N+1) = \emptyset$.
3. **Timestamp Scope Validator:** Verify every scene starts at `[0:00]`.
4. **Delivery Cue Validator:** Ensure presence of valid cadence `[... ~X.X wps]`.
5. **Minimal Prop Validator:** Flag active prop manipulation (e.g. drinking, unfolding, stamping) and enforce stationary staging.

---

## 5. Verification Checklist

- [ ] All 8 V3 guideline sections covered in automated tests (`tests/test_v3_specs.py`).
- [ ] Screenplay output matches sample format with 100% compliance.
- [ ] No regression on existing v1.2 continuous or step-wise workflows.
- [ ] Backward compatibility maintained for legacy scripts while supporting V3 execution.
