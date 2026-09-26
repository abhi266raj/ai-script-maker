# Sub-Feature 03: Minimal Prop Execution & AI Video Staging

> **Parent Specification:** [`V3.md`](file:///Users/abhiraj/Documents/news/agent/V3.md) — *Minimal Prop Execution*  
> **Status:** Pending Implementation  
> **Feature Branch:** `feature/v3-03-minimal-props-staging`

---

## 1. Objective & Scope

Refactor visual action directions, storyboards, and screen coherence logic to guarantee high generative video fidelity:
1. **Stationary Props:** Restrict physical props to minimal, simple, stationary environmental elements (e.g. newspaper lying flat on table, phone resting on counter, tea cup already placed).
2. **Eliminate Complex Manipulations:** Remove active prop handling (unfolding sheets, clinking cups, handing over cash, stamping papers) that trigger AI video artifacts (morphing hands, phantom limbs).
3. **Focus on Kinematics:** Drive scenes through expressive facial reactions, exaggerated gestures, dynamic vocal delivery, posture shifts, and environmental camera blocking.

---

## 2. Functional Requirements & User Stories

### FR-03.1: Refactoring Screenplay Coherence Sub-Agent ([`agents/screenplay_coherence.py`](file:///Users/abhiraj/Documents/news/agent/agents/screenplay_coherence.py))
- Deprecate regex rules that forcibly inject active prop interactions (e.g. `sharply unfolds the morning Hindi newspaper`, `takes a steaming sip from the cutting chai glass`, `firmly pressing official ink stamp`).
- Replace with stationary prop rules:
  - Chai: "standing beside the stationary chai kettle on the wooden counter, gesturing with animated hands".
  - Paper/News: "leaning over the newspaper lying flat on the wooden table, pointing down with wide-eyed disbelief".
  - Phone: "leaning forward with expressive frustration while the phone lies face-up on the desk".

### FR-03.2: Scene Director Prompt Rules ([`prompts/scene_director/direct_scenes.md`](file:///Users/abhiraj/Documents/news/agent/prompts/scene_director/direct_scenes.md))
- Mandate rule: **"MINIMAL STATIONARY PROPS ONLY"**.
- Visual actions must focus on:
  - Eyebrow raises, jaw drops, sarcastic side-eyes, furrowed brows.
  - Physical pacing, abrupt halts, leaning over thresholds, backing away.
  - Vocal projection kinematics (chest rise, animated hand emphasis).
  - Background environmental realism (rain on glass, buzzing fluorescent light, dust motes).

### FR-03.3: Video Prompt Engineer Integration ([`agents/video_prompt_engineer.py`](file:///Users/abhiraj/Documents/news/agent/agents/video_prompt_engineer.py))
- Prompts passed to Google Veo / Flow / AI Video models must explicitly specify stationary props to prevent generative distortion:
  - Example: `"A 35-year-old Indian clerk in a government office, expressive sarcastic facial reaction, shaking his head. A stack of files remains stationary on the desk."`

---

## 3. Deterministic Code Validators

1. **`validate_minimal_props(action_text)`:**
   - Detects banned high-risk interaction verbs: `["sips", "drinking", "unfolds", "flaps", "counts notes", "passes envelope", "stamps", "types on phone"]`.
   - Replaces or flags them for regeneration with stationary equivalents.
2. **`validate_actor_kinematics(action_text)`:**
   - Ensures the action contains at least one expressive facial reaction or bodily posture cue (e.g. `eyes widen`, `leans back`, `smirks`, `gestures with palm`, `freezes in place`).

---

## 4. Acceptance Criteria & Test Plan

- [ ] Unit tests in `tests/test_v3_minimal_props.py` verify that banned prop manipulation verbs are flagged.
- [ ] Test that stationary staging prompts generate without error.
- [ ] Benchmark prompt quality against generative video artifacts.
