# V3 Sub-Features Matrix: Status, Difficulty & Side Effects Analysis

> **Specification Source:** [`v3/V3.md`](file:///Users/abhiraj/Documents/news/agent/v3/V3.md)  
> **Gap Analysis:** [`v3/V3_EXPLORATION.md`](file:///Users/abhiraj/Documents/news/agent/v3/V3_EXPLORATION.md)  
> **Execution Roadmap:** [`v3/README.md`](file:///Users/abhiraj/Documents/news/agent/v3/README.md)  
> **Target Architecture:** Multi-Agent Editorial Pipeline (9:16 Vertical Reel Studio)

---

## 🏛 Architectural Decision Record (ADR): Clean Break to V3 (No Backward Compatibility)

- **Decision:** The Studio app will make a **clean break directly to V3**. Backward compatibility for legacy v1.2 script schemas, dual prompt sets, and legacy formatters is **explicitly eliminated**.
- **Rationale:**
  1. *No Persistent Historical Database:* The app generates scripts in-memory per session (`st.session_state`). No historical screenplay database exists that requires schema migration.
  2. *Zero External API Consumers:* No external microservices or third-party clients consume the internal data models.
  3. *Elimination of Technical Debt:* Bypasses the need for dual models (`SceneItem` vs `SceneItemV3`), complex alias getters, dual prompt trees, and confusing UI toggles.
  4. *Faster Development & Maximum Pacing:* Development velocity is 2–3x faster. Directly refactors models, agents, and formatters to V3 standards. Tests are directly updated to assert V3 contracts.

---

## 📊 Master Sub-Features Summary Matrix (Clean Break)

| # | Sub-Feature | Status | Difficulty | Depends On | Execution Readiness | Side Effects & Scope of Change | Key Files Touched |
|---|---|---|---|---|---|---|---|
| **01** | [**Scene & Shot Hierarchy**](file:///Users/abhiraj/Documents/news/agent/v3/01_scene_and_shot_hierarchy/REQUIREMENTS.md) | 📋 Planned | 🟢 **Low** | None *(Foundation)* | 🟢 **Ready to Execute** | • Cleanly refactors `SceneItem` to represent true 10s scenes with nested `ShotItem`s.<br>• Replaces fixed duration lookup in `metrics.py` with narrative arc derivation.<br>• Unit tests updated directly to V3 scene contracts. | [`core/models.py`](file:///Users/abhiraj/Documents/news/agent/core/models.py)<br>[`core/metrics.py`](file:///Users/abhiraj/Documents/news/agent/core/metrics.py)<br>[`core/screenplay_formatter.py`](file:///Users/abhiraj/Documents/news/agent/core/screenplay_formatter.py) |
| **02** | [**Timestamp Scoping & Cadence**](file:///Users/abhiraj/Documents/news/agent/v3/02_timestamp_scoping_and_cadence/REQUIREMENTS.md) | 📋 Planned | 🟡 **Medium** | Sub-Feature 01 | 🟡 Blocked by 01 | • Replaces global cumulative timestamps with per-scene `[0:00]` resets.<br>• Updates Stage 3 prompt to allow delivery cues `[... ~X.X wps]` outside the Devanagari spoken line.<br>• Code validator calibrates/corrects AI wps math deterministically. | [`prompts/dialogue_writer/`](file:///Users/abhiraj/Documents/news/agent/prompts/dialogue_writer/)<br>[`agents/dialogue_writer.py`](file:///Users/abhiraj/Documents/news/agent/agents/dialogue_writer.py)<br>[`core/screenplay_formatter.py`](file:///Users/abhiraj/Documents/news/agent/core/screenplay_formatter.py) |
| **03** | [**Minimal Props & Visual Staging**](file:///Users/abhiraj/Documents/news/agent/v3/03_minimal_props_and_visual_generation/REQUIREMENTS.md) | 📋 Planned | 🟢 **Low** | Sub-Feature 01 | 🟡 Blocked by 01 | • Eliminates active prop manipulation rules (sipping, unfolding, stamping) in [`screenplay_coherence.py`](file:///Users/abhiraj/Documents/news/agent/agents/screenplay_coherence.py).<br>• Replaces with stationary prop placement and facial/bodily kinematics.<br>• Massively reduces AI video generation artifacts (Veo / Sora). | [`agents/screenplay_coherence.py`](file:///Users/abhiraj/Documents/news/agent/agents/screenplay_coherence.py)<br>[`prompts/scene_director/`](file:///Users/abhiraj/Documents/news/agent/prompts/scene_director/)<br>[`agents/video_prompt_engineer.py`](file:///Users/abhiraj/Documents/news/agent/agents/video_prompt_engineer.py) |
| **04** | [**Scene Connectivity & Audio Bleed**](file:///Users/abhiraj/Documents/news/agent/v3/04_scene_connectivity_and_audio_bleed/REQUIREMENTS.md) | 📋 Planned | 🔴 **High** | Sub-Features 01, 02, 03 | 🟡 Blocked by 01, 02, 03 | • Links consecutive scenes: Scene $N+1$ depends on the outcome and audio tail of Scene $N$.<br>• In Stepwise mode, re-running Scene 1 prompts recalculation of Scene 2's visual anchor & audio bleed.<br>• Trailing SFX carryover `[0:00 – 0:02]` implemented in Stage 4/6. | [`agents/scene_director.py`](file:///Users/abhiraj/Documents/news/agent/agents/scene_director.py)<br>[`agents/screenplay_coherence.py`](file:///Users/abhiraj/Documents/news/agent/agents/screenplay_coherence.py)<br>[`agents/dialogue_writer.py`](file:///Users/abhiraj/Documents/news/agent/agents/dialogue_writer.py) |
| **05** | [**Cast Isolation & Rotation**](file:///Users/abhiraj/Documents/news/agent/v3/05_cast_isolation_and_rotation/REQUIREMENTS.md) | 📋 Planned | 🔴 **High** | Sub-Feature 01 | 🟡 Blocked by 01 | • Replaces 2-person ping-pong with strict cast rotation across cuts ($\text{Cast}(N) \cap \text{Cast}(N+1) = \emptyset$).<br>• Requires Stage 2 to generate ensembles of 3–4 characters or distinct pairs.<br>• Code validator enforces non-overlapping character sets across consecutive scenes. | [`agents/hook_strategist.py`](file:///Users/abhiraj/Documents/news/agent/agents/hook_strategist.py)<br>[`agents/dialogue_writer.py`](file:///Users/abhiraj/Documents/news/agent/agents/dialogue_writer.py)<br>[`core/models.py`](file:///Users/abhiraj/Documents/news/agent/core/models.py) |
| **06** | [**Integration, Formatter & Gate**](file:///Users/abhiraj/Documents/news/agent/v3/06_integration_and_v3_formatter/REQUIREMENTS.md) | 📋 Planned | 🟢 **Low** | Sub-Features 01 – 05 | 🟡 Blocked by 01–05 | • Refactors `screenplay_formatter.py` directly into the canonical V3 markdown output.<br>• Replaces legacy Stage 6 integration checks with the unified V3 deterministic validation gate.<br>• Updates Streamlit UI ([`app.py`](file:///Users/abhiraj/Documents/news/agent/app.py)) to display V3 scenes and copyable V3 scripts. | [`core/screenplay_formatter.py`](file:///Users/abhiraj/Documents/news/agent/core/screenplay_formatter.py)<br>[`agents/chief_editor.py`](file:///Users/abhiraj/Documents/news/agent/agents/chief_editor.py)<br>[`app.py`](file:///Users/abhiraj/Documents/news/agent/app.py)<br>[`tests/`](file:///Users/abhiraj/Documents/news/agent/tests/) |

---

## 🔍 Detailed Sub-Feature Analysis & Clean Implementation Plan

### Sub-Feature 01: Scene & Shot Hierarchy
* **Difficulty:** Low *(reduced from Medium due to Clean Break)*.
* **Scope of Change:**
  - Directly update [`core/models.py`](file:///Users/abhiraj/Documents/news/agent/core/models.py): `SceneItem` becomes the scene container (max 10s, title, duration, heading), containing `shots: List[ShotItem]`.
  - Update `core/metrics.py` to derive scene count dynamically from story scope/beats rather than rigid 5s buckets.
  - Update unit tests in `tests/` to construct and assert the new hierarchical models directly.

---

### Sub-Feature 02: Timestamp Scoping & Cadence
* **Difficulty:** Medium.
* **Scope of Change:**
  - Shift all timing generation to per-scene `[0:00]` start.
  - **Complete Elimination of Strict Word Counts:** Remove legacy rigid word budgets (e.g. `max_words = 11`, `recommended_words = 10`). Replace with dynamic pacing (2 to 3 wps) relative to the scene's timestamp window ($\le 10$s).
  - Update `prompts/dialogue_writer/write_dialogue_batch.md` to instruct the model to output canonical lines:
    `⚬ CHARACTER [Tone] [0:XX – 0:XX]: "हिंदी संवाद"`
  - Implement a deterministic post-processor in Python: calculate actual words in the line, compute $\text{wps} = \text{words} / \text{duration}$, and validate against natural conversational speech velocity ($2.0 \le \text{wps} \le 3.2$).

---

### Sub-Feature 03: Minimal Props & Visual Staging
* **Difficulty:** Low.
* **Scope of Change:**
  - Update [`agents/screenplay_coherence.py`](file:///Users/abhiraj/Documents/news/agent/agents/screenplay_coherence.py) regex handlers: eliminate active prop verbs (`sips`, `unfolds`, `holds phone`, `presses stamp`).
  - Replace with stationary staging: props rest on surfaces, characters express reaction through posture, gestures, and facial expressions.
  - Direct benefit: immediately stabilizes video generation outputs for AI engines (Veo / Sora).

---

### Sub-Feature 04: Scene Connectivity & Audio Bleed
* **Difficulty:** High.
* **Scope of Change:**
  - Introduce cross-scene dependency metadata on `SceneItem`: `visual_anchor: str` and `audio_bleed: str`.
  - Scene Director prompt requires defining a visual anchor for every scene $N \ge 2$ (e.g. subject or environmental element from Scene $N$ visible across cut).
  - Trailing sound effects from Scene $N$ are explicitly carried over into the first 1–2 seconds `[0:00 – 0:02]` of Scene $N+1$.

---

### Sub-Feature 05: Cast Isolation & Rotation
* **Difficulty:** High.
* **Scope of Change:**
  - Update Stage 2 (`agents/hook_strategist.py`) to generate an ensemble of 3–4 characters or distinct character pairs.
  - Update Stage 3 (`agents/dialogue_writer.py`) to allocate dialogue ensuring no character appears in consecutive scenes.
  - Add deterministic code validator: `assert set(scene[i].characters) & set(scene[i+1].characters) == set()`.

---

### Sub-Feature 06: Integration, Canonical Formatter & Validation Gate
* **Difficulty:** Low *(reduced from Medium due to Clean Break)*.
* **Scope of Change:**
  - Refactor `format_industry_screenplay()` in `core/screenplay_formatter.py` to directly output canonical V3 markdown:
    `### SCENE X: Title [X Seconds]`, `#### Shot X`, line timestamps, cadence cues, visual anchors, and audio bleed.
  - Update Stage 6 validation gate in `agents/chief_editor.py` to verify all 11 V3 deterministic rules.
  - Update `app.py` script display and copy-to-clipboard functionality to show the V3 script.
