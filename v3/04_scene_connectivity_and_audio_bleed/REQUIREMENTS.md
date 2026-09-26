# Sub-Feature 04: Scene Connectivity & Audio Bleed Specification

> **Parent Specification:** [`V3.md`](file:///Users/abhiraj/Documents/news/agent/V3.md) — *Seamless Scene-to-Scene Connectivity*  
> **Status:** Pending Implementation  
> **Feature Branch:** `feature/v3-04-connectivity-audio-bleed`

---

## 1. Objective & Scope

Establish four distinct mechanisms for seamless visual and acoustic continuity across scene transitions:
1. **Direct Consequence:** Open subsequent scenes with immediate physical or verbal reactions to the outcome of the preceding scene.
2. **Visual Anchors:** Retain primary subjects, key environmental focal points, or focal character states from the earlier scene visible in the background or adjacent space across cuts.
3. **Audio Bleed:** Carry over prominent trailing sound effects or background ambiances from the end of one scene into the opening 1–2 seconds `[0:00 – 0:02]` of the following scene.
4. **Conversational Carryover:** Direct opening dialogue of a new scene to reference or pivot from the exact event that concluded the previous scene.

---

## 2. Functional Requirements & User Stories

### FR-04.1: Cross-Scene Direct Consequence
- Scene $N+1$ cannot reset the emotional or narrative state.
- The opening shot of Scene $N+1$ MUST portray the immediate aftermath of the climax/revelation of Scene $N$.
- Example: If Scene 1 ends with a shocking price revelation on a phone screen, Scene 2 must open with a second character's jaw dropped in direct reaction to that revelation.

### FR-04.2: Visual Anchors Across Cuts
- The Scene Director MUST explicitly designate a **Visual Anchor** for every cut boundary ($N \to N+1$):
  - Example: "Amit's silhouette remains visible through the open doorway in the background", or "The stationary red tea kettle from Scene 1 remains visible on the counter edge".
- Format in screenplay:
  ```markdown
  ### SCENE 2: The Counter-Argument [8 Seconds]
  Visual Anchor: Stationary cutting chai glass from Scene 1 visible on the corner table in the background.
  ```

### FR-04.3: Audio Bleed Transitions
- The trailing 1–2 seconds of SFX/ambiance from Scene $N$ are preserved and carried into the opening of Scene $N+1$ `[0:00 – 0:02]`:
  ```markdown
  Audio Bleed: Muffled market siren from Scene 1 trails into [0:00 – 0:02] under the opening beat.
  ```
- This bridges the cut, eliminating abrupt acoustic drop-offs between shots.

### FR-04.4: Conversational Carryover
- The opening dialogue line of Scene $N+1$ must latch onto the specific keyword, decision, or revelation of Scene $N$'s final line.
- Banned: generic independent topic switches at scene openings.

---

## 3. Screenplay Formatter Rendering Example

```markdown
### SCENE 1: The New Gazette Order [8 Seconds]

#### Shot 1
Camera Focus & Action: Push-in on Vikram looking down at the official circular lying flat on the wooden desk.
Audio/SFX [0:00 – 0:03]: Office fan whir + heavy paper stamp echo in corridor
VIKRAM [0:01 – 0:06] [Shocked disbelief ~2.7 wps]:
"इस गजट नोटिफिकेशन के बाद पुराने सारे लाइसेंस रद्द हो चुके हैं!"

### SCENE 2: The Immediate Fallout [7 Seconds]
Visual Anchor: Vikram still visible through the glass cabin partition in the background.
Audio Bleed: Corridor echo of the stamp thud fades out across [0:00 – 0:02].

#### Shot 1
Camera Focus & Action: Reverse angle outside the cabin. Meera spins around with an urgent reaction.
Audio/SFX [0:00 – 0:02]: Stamp thud echo bleed + rapid keyboard stop
MEERA [0:01 – 0:05] [Frantic reaction ~2.9 wps]:
"रद्द? मतलब कल सुबह से हमारी सारी डिलीवरी गाड़ियां सील हो जाएंगी?"
```

---

## 4. Deterministic Code Validators

1. **`validate_audio_bleed_continuity(scene_n, scene_n1)`:**
   - Verifies Scene $N+1$ specifies an `audio_bleed` referencing a sound element from Scene $N$.
   - Verifies the bleed duration is specified within `[0:00 – 0:02]`.
2. **`validate_visual_anchor_presence(scene_n1)`:**
   - Verifies all scenes after Scene 1 define a `visual_anchor` connecting to the prior space/subject.
3. **`validate_conversational_carryover(last_dialogue, next_dialogue)`:**
   - Employs semantic/keyword overlap check to ensure the opening line references the prior topic or emotional trigger.

---

## 5. Acceptance Criteria & Test Plan

- [ ] Unit tests in `tests/test_v3_scene_connectivity.py` verify that `visual_anchor` and `audio_bleed` fields are generated for scenes $N \ge 2$.
- [ ] Test validator flags missing audio bleed in multi-scene reels.
- [ ] Test screenplay formatter renders visual anchor and audio bleed lines cleanly.
