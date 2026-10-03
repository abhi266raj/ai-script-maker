# Feature Development Workflow

---

## 🚦 When to Apply & What to Expect

- **When to Apply:** Adding new capabilities, UI components, emotions, formats, prompts, or models.
- **What to Expect:**
  - Input: Approved requirement specification or user feature request.
  - Output: Isolated `feature/` branch, fail-loud implementation, backward-compatible models, passing unit tests, and user approval.

---

## 🛑 Rules & Invariants

1. **Commit Gate:** No autonomous feature code without an approved requirement specification (`docs/REQUIREMENTS_vX.Y.md` / GitHub issue) and implementation plan.
2. **Fail-Loud:** No silent fallbacks or invented defaults. Missing data must raise explicit errors with diagnostic details.
3. **Layer Separation:**
   - Enums & Constants $\rightarrow$ [`core/constants.py`](file:///Users/abhiraj/Documents/news/agent/core/constants.py)
   - Data Models $\rightarrow$ [`core/models.py`](file:///Users/abhiraj/Documents/news/agent/core/models.py)
   - Prompt Directives $\rightarrow$ [`core/prompt_matrix.py`](file:///Users/abhiraj/Documents/news/agent/core/prompt_matrix.py) & [`prompts/`](file:///Users/abhiraj/Documents/news/agent/prompts/)
   - Streamlit UI $\rightarrow$ [`app.py`](file:///Users/abhiraj/Documents/news/agent/app.py)
4. **Backward Compatibility:** Saved stories and previous schema payloads must continue to load without data loss.

---

## 📋 Execution Protocol

1. **Plan & Branch:** Ensure requirement scope is defined. Switch to branch:
   ```bash
   git checkout -b feature/<descriptive-feature-name>
   ```
2. **Implement:** Write code adhering to fail-loud architecture and separation of concerns.
3. **Test:** Add and run unit tests:
   ```bash
   .venv/bin/python3 -m unittest discover tests
   ```
4. **User Review:** Present diff summary and test output for user confirmation before merging.
