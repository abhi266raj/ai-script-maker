# V3 Sub-Features Matrix: Status, Difficulty & Side Effects Analysis

> **Specification Source:** [`v3/V3.md`](file:///Users/abhiraj/Documents/news/agent/v3/V3.md)  
> **Gap Analysis:** [`v3/V3_EXPLORATION.md`](file:///Users/abhiraj/Documents/news/agent/v3/V3_EXPLORATION.md)  
> **Execution Roadmap:** [`v3/README.md`](file:///Users/abhiraj/Documents/news/agent/v3/README.md)  
> **Target Architecture:** Multi-Agent Editorial Pipeline (9:16 Vertical Reel Studio)

---

## 📊 Master Sub-Features Summary Matrix

| # | Sub-Feature | Status | Difficulty | Side Effects & Blast Radius | Key Files Touched |
|---|---|---|---|---|---|
| **01** | [**Scene & Shot Hierarchy**](file:///Users/abhiraj/Documents/news/agent/v3/01_scene_and_shot_hierarchy/REQUIREMENTS.md) | 📋 Planned | 🟡 **Medium** | • Breaks flat `script.scenes` iteration if not aliased.<br>• May fail existing unit tests expecting 1 beat = 1 scene.<br>• Requires recalculation of word budgets per sub-shot. | [`core/models.py`](file:///Users/abhiraj/Documents/news/agent/core/models.py)<br>[`core/metrics.py`](file:///Users/abhiraj/Documents/news/agent/core/metrics.py)<br>[`core/screenplay_formatter.py`](file:///Users/abhiraj/Documents/news/agent/core/screenplay_formatter.py) |
| **02** | [**Timestamp Scoping & Cadence**](file:///Users/abhiraj/Documents/news/agent/v3/02_timestamp_scoping_and_cadence/REQUIREMENTS.md) | 📋 Planned | 🟡 **Medium** | • Inverting the prompt rule that previously banned bracketed instructions.<br>• AI models may hallucinate inaccurate wps math without code fallback calibration.<br>• Audio teleprompter timestamp parsers might misread per-scene `[0:00]` as restart errors. | [`prompts/dialogue_writer/`](file:///Users/abhiraj/Documents/news/agent/prompts/dialogue_writer/)<br>[`agents/dialogue_writer.py`](file:///Users/abhiraj/Documents/news/agent/agents/dialogue_writer.py)<br>[`core/screenplay_formatter.py`](file:///Users/abhiraj/Documents/news/agent/core/screenplay_formatter.py) |
| **03** | [**Minimal Props & Visual Staging**](file:///Users/abhiraj/Documents/news/agent/v3/03_minimal_props_and_visual_generation/REQUIREMENTS.md) | 📋 Planned | 🟢 **Low** | • Changing [`screenplay_coherence.py`](file:///Users/abhiraj/Documents/news/agent/agents/screenplay_coherence.py) affects existing chai/paper/phone action rules.<br>• Low blast radius: improves Veo/Sora visual generation stability by eliminating limb/object morphing. | [`agents/screenplay_coherence.py`](file:///Users/abhiraj/Documents/news/agent/agents/screenplay_coherence.py)<br>[`prompts/scene_director/`](file:///Users/abhiraj/Documents/news/agent/prompts/scene_director/)<br>[`agents/video_prompt_engineer.py`](file:///Users/abhiraj/Documents/news/agent/agents/video_prompt_engineer.py) |
| **04** | [**Scene Connectivity & Audio Bleed**](file:///Users/abhiraj/Documents/news/agent/v3/04_scene_connectivity_and_audio_bleed/REQUIREMENTS.md) | 📋 Planned | 🔴 **High** | • Cross-scene dependencies make isolated stage retries more complex: regenerating Scene 1 requires updating Scene 2's visual anchor & audio bleed.<br>• In Stepwise mode, user edits to Scene 1 must trigger cascade re-alignment. | [`agents/scene_director.py`](file:///Users/abhiraj/Documents/news/agent/agents/scene_director.py)<br>[`agents/screenplay_coherence.py`](file:///Users/abhiraj/Documents/news/agent/agents/screenplay_coherence.py)<br>[`agents/dialogue_writer.py`](file:///Users/abhiraj/Documents/news/agent/agents/dialogue_writer.py) |
| **05** | [**Cast Isolation & Rotation**](file:///Users/abhiraj/Documents/news/agent/v3/05_cast_isolation_and_rotation/REQUIREMENTS.md) | 📋 Planned | 🔴 **High** | • Breaks the 2-character conversational ping-pong paradigm.<br>• Requires Stage 2 to generate larger ensembles (3–4 characters or distinct pairs).<br>• Increases prompt token usage in Stage 2/3.<br>• High risk of validation retry loops if model defaults to 2 characters arguing. | [`agents/hook_strategist.py`](file:///Users/abhiraj/Documents/news/agent/agents/hook_strategist.py)<br>[`agents/dialogue_writer.py`](file:///Users/abhiraj/Documents/news/agent/agents/dialogue_writer.py)<br>[`core/models.py`](file:///Users/abhiraj/Documents/news/agent/core/models.py) |
| **06** | [**Integration, Formatter & Gate**](file:///Users/abhiraj/Documents/news/agent/v3/06_integration_and_v3_formatter/REQUIREMENTS.md) | 📋 Planned | 🟡 **Medium** | • Modifies Stage 6 integration gate.<br>• UI changes in Streamlit ([`app.py`](file:///Users/abhiraj/Documents/news/agent/app.py)) need backward compatibility so legacy scripts still render correctly without crashes.<br>• New deterministic validator suite must not fail non-V3 runs. | [`core/screenplay_formatter.py`](file:///Users/abhiraj/Documents/news/agent/core/screenplay_formatter.py)<br>[`agents/chief_editor.py`](file:///Users/abhiraj/Documents/news/agent/agents/chief_editor.py)<br>[`app.py`](file:///Users/abhiraj/Documents/news/agent/app.py)<br>[`tests/`](file:///Users/abhiraj/Documents/news/agent/tests/) |

---

## 🔍 Detailed Sub-Feature Analysis & Mitigation Plans

### Sub-Feature 01: Scene & Shot Hierarchy
* **Difficulty Justification:** Medium. Involves introducing a two-level nested model (`Scene` $\to$ `ShotItem`) while preserving legacy code compatibility with `ReelScript.scenes`.
* **Side Effects & Risks:**
  1. *Downstream Breakage:* Any downstream agent or test directly accessing `scene.visual_b_roll` or `scene.dialogue` will fail if `SceneItem` is abruptly refactored without backward-compatible property accessors.
  2. *Duration Recalculation:* Dynamic scene calculation disrupts the fixed word budget lookup table in [`core/metrics.py`](file:///Users/abhiraj/Documents/news/agent/core/metrics.py).
* **Mitigation Strategy:**
  - Implement `ShotItem` as a component within `SceneItemV3`, while retaining alias getters on `SceneItem` so existing formatters and legacy tests continue working without exceptions.
  - Make dynamic narrative scene derivation additive (active when V3 mode is requested, falling back cleanly to duration formulas if unspecified).

---

### Sub-Feature 02: Timestamp Scoping & Cadence
* **Difficulty Justification:** Medium. Requires modifying prompt contracts in Stage 3 to allow bracketed delivery cues while keeping spoken Hindi dialogue strictly clean in Devanagari.
* **Side Effects & Risks:**
  1. *Prompt Rule Contradiction:* For months, the prompt insisted `"NO stage directions or brackets"`. Changing this might cause the model to leak bracketed English words into spoken Devanagari dialogue lines.
  2. *WPS Math Errors:* LLMs frequently miscalculate speech rates (e.g. claiming 25 words in 3 seconds is `~2.0 wps`).
* **Mitigation Strategy:**
  - Clearly delineate the delivery cue tag `[Emotion ~X.X wps]` outside the spoken quote string: `CHAR [0:01 – 0:06] [Frantic delivery ~2.8 wps]: "Devanagari dialogue"`.
  - Implement deterministic code calibration: compute the real word count in Python, calculate actual $\text{wps} = \text{word\_count} / \text{duration}$, and automatically correct/calibrate the tag if the model's estimate deviates by $>0.5\text{ wps}$.

---

### Sub-Feature 03: Minimal Props & Visual Staging
* **Difficulty Justification:** Low. Simplifies visual complexity, making it safer and easier for AI video generators (Veo, Sora, Kling) to generate clean video.
* **Side Effects & Risks:**
  1. *Coherence Regression:* Existing tests for [`agents/screenplay_coherence.py`](file:///Users/abhiraj/Documents/news/agent/agents/screenplay_coherence.py) (`tests/test_character_and_creative_scenes.py`) assert that chai/paper/phone triggers specific action verbs. Refactoring those regex rules could break legacy test assertions.
* **Mitigation Strategy:**
  - Update the coherence rules to assert stationary placement instead of active manipulation.
  - Update test fixtures simultaneously to check for stationary props and actor kinematics.

---

### Sub-Feature 04: Scene Connectivity & Audio Bleed
* **Difficulty Justification:** High. Creates cross-scene state coupling. In earlier versions, each beat was relatively independent. Now, Scene $N+1$ directly depends on the outcome, audio tail, and visual layout of Scene $N$.
* **Side Effects & Risks:**
  1. *Cascade Invalidation in Step-Wise Mode:* In Step-Wise mode, if a user re-runs Scene 1 with new instructions, Scene 2 becomes temporally and visually orphaned unless re-synthesized or patched.
  2. *Audio Bleed SFX Collisions:* If Scene 2 already has an intense sound effect, an audio bleed from Scene 1 could clutter the acoustic mix.
* **Mitigation Strategy:**
  - Store `visual_anchor` and `audio_bleed` as explicit fields on the scene metadata.
  - In Chief Editor retry loops, pass the prior scene's closing state explicitly into the refinement prompt of the subsequent scene.

---

### Sub-Feature 05: Cast Isolation & Rotation
* **Difficulty Justification:** High. Fundamentally alters character generation and dialogue attribution. Standard comedic reels heavily rely on 2 actors having a rapid back-and-forth debate in the same room.
* **Side Effects & Risks:**
  1. *Cast Starvation:* In a 3-scene reel with 2 characters, rotating cast means Character A (Scene 1) $\to$ Character B (Scene 2) $\to$ Character A (Scene 3). In a 4-scene reel, 2 characters alone cannot create dynamic multi-party interaction without feeling repetitive.
  2. *Stage 2 Group Selection Reshuffling:* The current Stage 2 generates Group A (2 characters) and Group B (2 characters). To support rotation, Stage 2 must finalize 3–4 characters or structured subgroups.
* **Mitigation Strategy:**
  - Expand Stage 2 character group generation to support 3–4 coherent ensemble characters when target duration $>15$s.
  - Provide a deterministic validator that checks `set(scene[i].characters) & set(scene[i+1].characters) == set()`.

---

### Sub-Feature 06: Integration, Canonical Formatter & Validation Gate
* **Difficulty Justification:** Medium. Orchestration, formatting, and UI presentation.
* **Side Effects & Risks:**
  1. *Streamlit UI Clutter:* Adding multi-shot nested expanders could overload the UI layout.
  2. *Copy-Paste Disruption:* Creators using automated tools or teleprompters may expect the legacy format.
* **Mitigation Strategy:**
  - Add a dedicated **"V3 Master Screenplay"** tab in Streamlit, keeping the legacy views accessible.
  - Implement a dedicated `format_v3_screenplay()` without replacing or deleting `format_industry_screenplay()` until full deprecation.

---

## 🎯 Recommended Next Step

Begin implementation with **Sub-Feature 01: Scene & Shot Hierarchy** ([`v3/01_scene_and_shot_hierarchy/REQUIREMENTS.md`](file:///Users/abhiraj/Documents/news/agent/v3/01_scene_and_shot_hierarchy/REQUIREMENTS.md)) on a clean sub-branch `feature/v3-01-scene-shot-hierarchy`.
