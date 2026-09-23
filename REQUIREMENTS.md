# System Requirements Specification (SRS)

## 📌 Feature: Continuous vs Step-Wise Script Generation with Per-Step Model Selection & Dynamic Instruction Refinement

**Status:** Implemented — refinements in progress (step-wise coordination hardening)  
**Target:** Hindi Reel Studio (AI Script Maker)  
**Architecture:** Multi-Agent Editorial Pipeline (Chief Editor, News Validator, Hook Strategist, Dialogue Writer, Timing Auditor, Scene Director, Video Prompt Engineer, Video Quality Gate)

---

### 1. Executive Summary & Objective

In production reel creation, users need both:
1. **Continuous Mode:** Rapid, one-click end-to-end execution of the full multi-agent pipeline from news validation to finalized screenplay.
2. **Step-Wise Mode:** An interactive, checkpointed workflow where creators review intermediate outputs at each stage, inject custom instructions or course-corrections via an interactive tickbox, and optionally switch the AI model/engine on a per-step basis before advancing to the final screenplay.

This architectural enhancement makes the generation pipeline modular, scalable, observable, and adaptable to complex creative directions.

---

### 2. User Stories & Functional Requirements

#### 2.1 Mode Selection (Continuous vs Step-Wise)
- **FR-1.1:** The user must be able to switch between **⚡ Continuous (Automated)** and **🪜 Step-Wise (Interactive)** generation modes from the Studio interface.
- **FR-1.2:** In **Continuous Mode**, the pipeline functions uninterrupted, streaming telemetry across all 5 stages and presenting the final screenplay upon completion.
- **FR-1.3:** In **Step-Wise Mode**, the pipeline pauses at the completion of each stage, rendering the stage's structured outputs and awaiting user review/instruction before proceeding.

#### 2.2 Per-Step Model / Engine Override
- **FR-2.1:** In Step-Wise mode, every individual stage provides a dedicated **Model / Engine selector** (`Local First Then Antigravity`, `Antigravity`, `Codex`, `Grok Low`, `Grok Medium`, `Grok High`, `On-device`).
- **FR-2.2:** The user can select different engines for different stages (e.g., *Codex* for Fact Checking, *Grok High* for Hook Writing, *Antigravity* for Screenplay Dialogue, *Local FM* for Scene Storyboards).
- **FR-2.3:** Engine selection for a step takes effect immediately for both initial execution and subsequent re-runs of that step.

#### 2.3 Dynamic Instruction Refinement via Tickbox
- **FR-3.1:** At each step, an optional tickbox/checkbox allows the creator to provide **Extra Instructions**:
  - `☑ Provide extra instruction for this step (re-run / refine)`
  - `☑ Provide extra instruction for next step`
- **FR-3.2:** When checked, an instruction text area expands, accepting natural-language guidance (e.g., *"Make tone more sarcastic", "Place in high court corridor", "Focus on consumer inflation"*).
- **FR-3.3:** The Chief Editor seamlessly merges the extra instruction into the specialized sub-instructions dispatched to the underlying sub-agent.
- **FR-3.4:** The user can re-run the current step with updated instructions and/or a new model, or proceed forward to the next step with queued guidance.
- **FR-3.5 (Same-Stage Output Feedback & Correction Loop):** When a stage is re-run with user feedback/corrections, the orchestrator MUST capture the previous output/draft of that exact stage and pass it back into the agent alongside the user's critique under a high-priority `REVISION & CORRECTION MODE` block. The agent treats the previous output as the baseline draft and **REFINES** it — keeping every beat, line, joke, and character moment that already works, and changing ONLY what the critique targets. It MUST NOT discard the draft to generate a brand-new unrelated output, and it MUST NOT drop the draft's established creativity, angle, or tone unless the feedback explicitly asks for it.
- **FR-3.6 (Feedback Replacement, Not Stacking):** Re-running a stage with new feedback REPLACES any stale feedback block on that stage's sub-instruction instead of appending alongside it, so the model always follows the LATEST feedback and never receives contradictory stacked critiques.
- **FR-3.7 (Step-by-Step Instruction Building):** Stage 1 builds ONLY its own (news validator) sub-instruction. Each subsequent stage builds its own agents' sub-instructions at the moment it runs, using the freshest upstream outputs (e.g. Stage 3/4 instructions reference the finalized Stage-2 character names, not generic placeholders). No stage pre-generates later stages' instructions in one shot.
- **FR-3.8 (Feedback Honored in Fallbacks):** If model generation fails inside a stage, the deterministic fallback MUST refine/carry forward the previous draft (when one exists) rather than generating unrelated placeholder content, and must record that the fallback preserved the prior output.

#### 2.4 Intermediate Stage Outputs & Telemetry
- **FR-4.1 Stage 1 (News Validation & Dossier Extraction):**
  - Displays: Verified facts, confidence score, physical props extracted, key locations, core conflict/irony, and this stage's own sub-instruction. (Stage 1 does NOT pre-generate later stages' instructions — see FR-3.7.)
  - Same-stage revision: Captures previous facts and summary to refine directly upon retry.
- **FR-4.2 Stage 2 (Character Finalisation & Viral Hooks):**
  - Role: Grounded in Stage 1 news dossier and scenario, finalizes specific actors/characters (names, professions/jobs, attire, emotional stance, and relational dynamic) and sequential story beat steps (action and speech objective).
  - Displays: Finalized characters (occupations, wardrobes, emotional stances), story beat actions, formulated Devanagari hooks (0-3s), and closing CTAs.
  - Upstream Hand-off: Passes finalized characters AND finalized scene options (location, atmosphere, lighting, props, source) directly to Stages 3 and 4 to prevent generic persona/location drift. Stage 4 selects from these scene options per dialogue beat.
- **FR-4.3 Stage 3 (Spoken Dialogue Writing, Interconnectedness & Timing Audit):**
  - Uses exact Stage 2 finalized characters and story steps to craft spoken Hindi dialogue lines.
  - **Hidden Continuity Knowledge:** Stage 3 receives full character profiles (role, attire, emotional stance) and per-beat scene plans (location, atmosphere, lighting, props) as system knowledge for continuity. The dialogue MUST NOT redundantly describe character appearance, attire, or location — that knowledge stays attached internally and flows into the final output instead of being spoken aloud.
  - **Creativity Preservation:** The user-selected editorial angle and tone (especially humor) MUST survive in every output, including deterministic fallbacks. New creative details produced at this stage (beat actions, SFX/music hints) MUST be captured and carried forward, never silently dropped.
  - **Configured Character Count:** Exactly the configured number of characters may speak; no extra speaking characters may be introduced by the model or by fallbacks.
  - **Dialogue-Type Enforcement:** The output MUST honor the selected dialogue type — Interview (strict host/guest Q&A), Debate (claim + rebuttal), Argument (heated clash), Speech/Monologue (solo direct address), Lament (somber, no jokes), or standard Dialogue (natural ping-pong).
  - Displays: Character dialogue lines, speech word count, recommended word budget, strict max limit, and timing audit calibration status.
  - **Dialogue Interconnectedness Standard:** Characters must NOT deliver isolated monologues. Every line (Beat 2 onwards) must directly answer, counter, or rebut the previous speaker using reactive connectors, echo-and-pivot keyword callbacks, and natural Hindi conversational ping-pong.
  - Same-stage revision: Captures previous dialogue draft to resolve critiques directly upon retry.
- **FR-4.4 Stage 4 (Dialogue-Aware Scene Selection, Storyboards & AI Video Prompts):**
  - **Scene Selection (Not Scene Invention):** For each dialogue beat, Stage 4 interprets the dialogue's meaning, action, and emotion, then SELECTS the most appropriate scene from the finalized Stage-2 scene options (matching location, atmosphere, lighting, and props). Only if NO supplied option fits the beat may it create a NEW scene grounded in the news — explicitly marked as newly created. It MUST NOT blindly cycle scene options and MUST NOT re-describe characters or locations (already known from Stage 2).
  - **Action & Emotion Focus:** The dialogue is used INTERNALLY to infer physical action, gesture, facial expression/emotion, prop interaction, and reaction to the previous line. The storyboard and final visual presentation emphasize action, emotion, and visual direction — they do not restate the dialogue. Spoken lines are carried verbatim from Stage 3.
  - **Character Count:** All actors are restricted to the finalized characters within the configured count; fallbacks must not introduce extra speaking characters.
  - **Music/SFX:** Every beat gets an appropriate, emotion-matched music/SFX cue — never a one-size-fits-all default.
  - **No Hardcoded Defaults:** Scene/visual fallbacks must be news-grounded (prefer verified key locations); hardcoded generic venues are forbidden as defaults.
  - **Video Prompts:** Carry character appearance/attire and selected scene location metadata WITHOUT quoting dialogue.
  - Displays: 9:16 vertical scene beats with per-beat action, emotion, selected (or newly created) scene, music/SFX cues, and generative video prompts (Google Flow / Veo).
  - Same-stage revision: Captures previous storyboard scenes to refine camera framing, actions, and music upon retry.
- **FR-4.5 Stage 5 (Chief Editor Review & Final Packaging):**
  - Displays: Full configuration compliance audit, common-sense validation, and the final production screenplay package.

#### 2.5 Final Production Deliverables
- **FR-5.1:** Upon completing Step 5, the studio provides the identical full production outputs as Continuous mode:
  - 🎬 Industry-Standard Vertical Screenplay (Markdown)
  - 🎙️ Devanagari Voiceover / Teleprompter Script
  - 📝 Plain Script (Clean Text)
  - 🎥 AI Video Generation Prompts (Google Flow / Veo 9:16)
#### 2.6 Default Testing Isolation Policy
- **FR-6.1 (Local Model Testing Standard):** Default testing must execute strictly on the local on-device model (`fm_only` / local inference bridge). All standard test runs and CI checks default exclusively to this local model.
- **FR-6.2 (Isolation from Remote Sources):** Default automated tests must NOT query or execute against external remote sources or live cloud endpoints (e.g., unmocked Grok, Codex, remote Antigravity services, or live external RSS feeds). All default tests verifying pipeline flow and agent handoffs must either run against the local model or employ deterministic local mocks to avoid network flakiness, rate limiting, and credential dependencies.
- **FR-6.3 (Conditional Testing for Other Models - Bug Finding & Diagnostics Only):** Tests for external/alternative models (such as Grok, Codex, or AGY cloud APIs) must **ONLY** be run when specifically needed—such as when investigating a bug report, verifying a regression fix in that specific engine adapter, or during manual diagnostic triage. They must NOT be part of default test discovery or routine validation runs.

---

### 3. Technical Architecture & Data Flow

```mermaid
sequenceDiagram
    autonumber
    actor User as 👤 Creator / Editor
    participant UI as 💻 Streamlit Studio (app.py)
    participant WF as ⚡ ReelWorkflow (workflow.py)
    participant CE as 👑 ChiefEditorCoordinator (chief_editor.py)
    participant SubAgents as 🤖 Sub-Agent Roster (Agents 1-7)

    alt Continuous Mode
        User->>UI: Click "Generate Script"
        UI->>WF: run_stream(...)
        WF->>CE: orchestrate_reel_pipeline(...)
        CE->>SubAgents: Execute Stages 1 -> 5 continuously
        SubAgents-->>CE: Pipeline outputs
        CE-->>UI: Stream progress events & yield ReelBatchResult
        UI-->>User: Display Final Screenplay & Downloads
    else Step-Wise Mode
        User->>UI: Select Step-Wise & Click "Start Step-Wise"
        loop Stage by Stage (Steps 1 to 5)
            User->>UI: Configure Step Model & Optional Extra Instruction (Tickbox)
            UI->>WF: run_step_X(state, engine_mode, extra_instruction)
            WF->>CE: run_step_X(...)
            CE->>SubAgents: Execute specific Sub-Agent
            SubAgents-->>CE: Intermediate Stage Result
            CE-->>UI: Updated State & Step Data
            UI-->>User: Render Step Output & Action Controls (Proceed / Re-run)
        end
        UI-->>User: Display Final Screenplay, Multi-Tab Output & Downloads
    end
```

---

### 4. Non-Functional & Scalability Requirements

- **NFR-1 (State Isolation & Scalability):** Intermediate pipeline state is encapsulated in a pure Python dictionary structure, enabling pause, resume, re-execution, and potential multi-user session serialization.
- **NFR-2 (Backward Compatibility):** Existing tests, CLI runners, and continuous mode behavior remain 100% backward compatible without breaking changes.
- **NFR-3 (Failure Resilience):** If any individual step fails or encounters model rate limits, only that step fails gracefully, allowing the user to select an alternative model (e.g. switch to Antigravity or Local FM) and re-try that exact step without losing progress.
