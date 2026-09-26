# Sub-Feature 05: Cast Isolation & Spatial Rotation Specification

> **Parent Specification:** [`V3.md`](file:///Users/abhiraj/Documents/news/agent/V3.md) — *Spatial Consistency & Cast Isolation*  
> **Status:** Pending Implementation  
> **Feature Branch:** `feature/v3-05-cast-isolation-rotation`

---

## 1. Objective & Scope

Implement spatial consistency combined with strict cast rotation across scenes:
1. **Unified Setting:** Maintain a single, shared physical setting viewed from adjacent perspectives, reverse angles, or spatial thresholds (doorways, windows, counter partitions).
2. **Cast Isolation:** Rotate the on-screen cast so that characters featured in one scene do not appear in the immediately subsequent scene:
   $$\text{Cast}(\text{Scene } N) \cap \text{Cast}(\text{Scene } N+1) = \emptyset$$
3. **Multi-Character Ensemble Support:** Stage 2 must finalize sufficient characters (at least 2 distinct pairs or an ensemble of 3–4 actors) to allow rotation without characters overlapping adjacent scenes.

---

## 2. Functional Requirements & User Stories

### FR-05.1: Shared Spatial Geography
- The reel occurs in ONE physical environment (e.g. court corridor, regional tax office, roadside dhaba, studio apartment).
- Cuts between scenes represent angle shifts (reverse angle, doorway perspective, threshold view, outside looking in) — NOT teleporting to an unrelated location.
- Stored and unified via `derive_scene_detail` and setting harmonization.

### FR-05.2: Strict Cast Isolation & Rotation
- If Character A is on-screen in Scene 1, Character A MUST NOT appear on-screen in Scene 2.
- Scene 2 features Character B (or Character C/D), reacting from an adjacent vantage point in the same space.
- Character A may reappear in Scene 3 (if applicable), but never back-to-back in consecutive scenes.

### FR-05.3: Stage 2 Ensemble Finalization ([`agents/hook_strategist.py`](file:///Users/abhiraj/Documents/news/agent/agents/hook_strategist.py))
- Stage 2 character generation must produce an ensemble that supports rotation:
  - Minimum 2 distinct speaking roles with distinct physical staging positions.
  - For 3+ scene reels, finalize at least 3 characters or alternate perspectives (e.g. Actor A inside the cabin, Actor B at the counter outside, Actor C at the entrance).

### FR-05.4: Stage 3 Spoken Dialogue Allocation ([`agents/dialogue_writer.py`](file:///Users/abhiraj/Documents/news/agent/agents/dialogue_writer.py))
- When assigning dialogue to scenes, Stage 3 allocates speaking lines adhering to the non-overlap rule.
- A character who delivers dialogue in Scene $N$ cannot deliver dialogue in Scene $N+1$.

---

## 3. Screenplay Formatter Rendering Example

```markdown
CHARACTERS & CLOTHING:
⚬ RAJESH: Middle-aged accountant, half-sleeve khadi shirt, wireframe spectacles
⚬ SUNITA: Senior auditor, crisp green cotton saree, brass watch
⚬ KUNAL: Young junior clerk, blue lanyard, rolled-up white formal shirt

### SCENE 1: The Audit Discovery [8 Seconds]
(On-screen cast: RAJESH)
...
RAJESH [0:01 – 0:06] [Tense shock ~2.5 wps]:
"इस फाइल में पिछले तीन महीने का कोई हिसाब दर्ज ही नहीं है!"

### SCENE 2: The Hallway Reaction [8 Seconds]
(On-screen cast: SUNITA & KUNAL — RAJESH does NOT appear)
Visual Anchor: The frosted glass cabin door where Rajesh is sitting remains visible in the background.
...
SUNITA [0:01 – 0:05] [Stern whisper ~2.7 wps]:
"साफ बात है, ऑडिट टीम आने से पहले सारा रिकॉर्ड गायब कर दिया गया!"
```

---

## 4. Deterministic Code Validators

1. **`validate_cast_isolation(script)`:**
   - Compares the set of characters appearing in `scene[i]` against `scene[i+1]`.
   - If `set(chars_i) & set(chars_i_plus_1) != set()`, raises `ModelGenerationError("Cast isolation breach: Character X appears in consecutive scenes")`.
2. **`validate_spatial_consistency(script)`:**
   - Verifies all scenes share the same primary root location and vary only in spatial perspective/threshold.

---

## 5. Acceptance Criteria & Test Plan

- [ ] Unit tests in `tests/test_v3_cast_isolation.py` verify that cast isolation validator catches consecutive character appearances.
- [ ] Stage 2 ensemble generation generates distinct character sets capable of alternating scenes.
- [ ] End-to-end screenplay generation passes cast rotation check on multi-scene scripts.
