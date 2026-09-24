# Release Notes — Hindi Reel Studio

## Date: 2026-09-24
## Branch: `fix/duplicate-element-key`

---

## 1. Critical Bug Fixes

### 🐛 Fixed Duplicate Key Exception (`live_5_st5_st5_vp_1_0_1`)
- **Root Cause**: During continuous pipeline streaming, `stage_output_box.container()` dynamically re-rendered stage and substep outputs within the same execution run. In Stage 5, the Veo video prompt was rendered using `st.text_area(..., disabled=True, key=...)`. As an interactive input widget, `st.text_area` registered its key in Streamlit's widget manager. When Stage 6 started, re-rendering Stage 5 within that same run caused Streamlit to re-register the identical widget key, raising a fatal `StreamlitDuplicateElementKey` crash.
- **Resolution**:
  - Replaced `st.text_area` with `st.caption` and `st.code(str(_vpa), language="text")` in `_render_storyboard_cards` and `_render_step_output`.
  - Display elements (`st.code`) do not create stateful widget keys in Streamlit, avoiding key collisions during dynamic streaming container updates.
  - Users retain built-in copy functionality via Streamlit's native code block copy button.

### 🐛 Fixed Stage 6 Output Repetition
- **Root Cause**: In Stage 6 (`_render_step_output(step_num=6)`), validation status and integration issues were rendered once inside the `6.2 Validation` expander, and then immediately repeated outside `6.2 Validation` in a second block (`if _s6_passed ... else: for _iss in _s6_errs ...`). Additionally, if validation passed, `"✅ All validation checks passed"` was printed twice in succession.
- **Resolution**:
  - Consolidated validation reporting strictly inside the `6.2 Validation` expander.
  - Removed the redundant duplicate validation blocks outside `6.2 Validation`.
  - Validation issues (errors/warnings) and pass statuses are now presented once clearly and accurately.

### 🐛 Fixed `IndexError` on Step 6 in Stepwise History
- **Root Cause**: In `Review Step-by-Step Outputs (Steps 1 to 6)`, `step_names_history` had only 5 entries for 6 pipeline steps. When evaluating step 6, `step_names_history[s_num - 1]` caused an `IndexError: list index out of range`.
- **Resolution**:
  - Added `"6. Integration & Final Validation"` as the 6th item in `step_names_history`.

### 🎙️ Fixed 3.1 Dialogue Display (No Raw JSON Truncation)
- **Root Cause**: When Stage 3.1 generated dialogue, `output_text` and `_emit_substep` sent the raw model string snippet `raw_output[:600]`. Since the model produces strict JSON, the first 600 characters only contained JSON object scaffolding (`{"scripts": [{"scene_lines": ...`), obscuring the actual Hindi dialogue. In `3.1 Generate Dialogue`, the output simply read "see below".
- **Resolution**:
  - Extracted parsed dialogue beats (`Character: “Dialogue”`) from `narrations` and formatted them as human-readable dialogue lines in `dialogue_writer.py`.
  - In `app.py`, `3.1 Generate Dialogue` now displays formatted character dialogue beats directly inside the 3.1 output card.

### 🔄 Added Validation & Retry Audit Details to Final Output Stage
- **New Feature**:
  - Inside Stage 6 (`6.2.2 Validation & Retry Audit Details`), added a comprehensive breakdown of retries across the pipeline (Stage 1 Wire Facts, Stage 3 Dialogue & Timing, Stage 5 Video Quality Gate).
  - Shows total retries resolved, pipeline health, and detailed self-healed agent actions.
  - On the final screenplay screen, added an expander displaying validation retry history and issues resolved across all agents.

### ⚡ Live Code Reloading Configuration (`runOnSave`)
- **Root Cause**: Streamlit defaulted to `server.runOnSave = false`, requiring manual browser refreshes or server restarts to reflect code changes.
- **Resolution**:
  - Configured `runOnSave = true` in `.streamlit/config.toml` so edits to `.py` scripts and prompts reload instantly.

---

## 2. Elimination of Nested Expanders ("Nesting Inside Nesting")

Streamlit discourages or improperly formats `st.expander` components nested inside other `st.expander` components, leading to double-nested boxes, misaligned chevrons, and UI friction. All nested expanders have been systematically replaced with clean inline markdown sections and dividers across the entire application:

### 🔍 Stage 1 (Single Dropdown, Preserved Subsections)
- Consolidated all Stage 1 output inside **1 single outer dropdown** (`🔍 Step 1: Fact Validation & Story Dossier`).
- **Preserved all subsections without nested expanders**:
  - **1.1 Verify**: Headline/topic input, verified status, confidence score, and top wire facts.
  - **1.2 Validation**: `1.2.1 News Check` and `1.2.2 Confidence Check` rendered inline with input/output labels.
  - **1.3 Retry / 1.4 Re-validate**: Displayed when low-confidence query refinement is triggered.
  - **Story Dossier**: Full facts, props, locations, core conflict, and citations via `_render_verification_report(as_expander=False)`.
  - **Generated Sub-Instructions**: Displayed cleanly under an inline section.

### 🎭 Stage 2 (Single Dropdown, Preserved Subsections)
- Consolidated all Stage 2 output inside **1 single outer dropdown** (`🎭 Step 2: Character Finalisation`).
- **Preserved all subsections without nested expanders**:
  - **2.1 Generate Characters**: News & tone input, character count output.
  - **2.2 Validation**: `2.2.1 Count Check` and `2.2.2 Diversity Check` rendered inline with status badges.
  - **Cast Selection**: Group A vs Group B selection via radio buttons and side-by-side columns displaying attire, stance, and relationship dynamics.
  - **Raw JSON**: Displayed directly with `as_expander=False`.

### ✍️ Stage 3 Sequential Display Order & Validation Checks
- **Strict Sequential Order**: Sub-checks are displayed in strict numeric order so nothing is hidden or missing:
  - `3.1 Generate Dialogue` (AI generation)
  - `3.2 Validation Checks Overview` (overview of fail-fast gate)
  - `3.2.1 Structure Check` (code validator)
  - `3.2.2 Tone + News Check` (AI validator)
  - `3.2.3 Language Check` (code validator)
  - `3.2.4 Clothing Check` (code validator)
  - `3.2.5 SFX Check` (code validator)
  - `3.3 Retry Generation` (AI generation, if retried)
  - `3.4 Re-validate` (if retried)
- **Zero Nesting**: Rendered as independent top-level sibling expanders rather than hiding `3.2.1` and `3.2.2` inside `3.2`.
- In `Stage 3 Steps` history view, sub-checks are rendered inline with markdown and badges, eliminating nested expanders (`st.expander` inside `st.expander`).
- In `_render_live_tracker`, all substeps (including 3.2.1–3.2.5) are tracked in sequential numerical order with live badges and no nested expanders.

### 🎬 Stage 4 & 5 Validation Checks
- In Stage 4 (`4.2 Validation`), removed nested expander for `4.2.1 Connectivity Check`.
- In Stage 5 (`5.2 Validation`), removed nested expander for `5.2.1 Quality Gate`.

### ✅ Stage 6 Validation Checks
- In Stage 6 (`6.2 Validation`), removed nested expander for `6.2.1 Integration Checks`.

### 📥 AI Input Prompts & Live Tracker
- In `_render_input_prompts`: Removed inner expander per prompt and eliminated `st.text_area(disabled=True)`. Each prompt is presented with bold headers and `st.code`.
- In `_render_live_tracker`: Removed nested expanders for dynamic sub-checks (`subs`), rendering them inline under their parent step.
- In `_render_stage_output_card`: Removed nested AI input expander, rendering stage inputs directly inline.

---

## 3. Files Modified
- [`agents/dialogue_writer.py`](file:///Users/abhiraj/Documents/news/agent/agents/dialogue_writer.py):
  - Formatted spoken dialogue beats in 3.1 substep output instead of raw JSON string envelope.
- [`app.py`](file:///Users/abhiraj/Documents/news/agent/app.py):
  - Displayed dialogue beats in `3.1 Generate Dialogue`.
  - Added `6.2.2 Validation & Retry Audit Details` to Stage 6 output.
  - Added Validation Retry Details expander to final output completion view.
  - Converted Veo prompt display from `st.text_area` to `st.code`.
  - Restored full sub-sections in Stage 1 & Stage 2 under single outer dropdowns without nested expanders.
  - Inlined validation sub-checks in Stages 3, 4, 5, and 6 to eliminate nested expanders.
  - Eliminated Stage 6 duplicate validation rendering.
  - Added 6th step to `step_names_history` to prevent `IndexError`.
  - Flattened `_render_input_prompts`, `_render_live_tracker`, and `_render_stage_output_card`.
- [`.streamlit/config.toml`](file:///Users/abhiraj/Documents/news/agent/.streamlit/config.toml):
  - Configured `runOnSave = true`.
- [`.gitignore`](file:///Users/abhiraj/Documents/news/agent/.gitignore):
  - Added `.server.*` ignore pattern.
- [`RELEASE_NOTES.md`](file:///Users/abhiraj/Documents/news/agent/RELEASE_NOTES.md):
  - Documented root causes, architectural changes, and bug fixes.
