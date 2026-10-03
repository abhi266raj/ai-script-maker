# Gemini Agent & Engine Rules

---

## 🚦 When to Apply & What to Expect

- **When to Apply:** Generating scripts via Gemini (AGY) or operating as a Gemini assistant in Google Antigravity.
- **What to Expect:** Large context reasoning, structured JSON schemas, tool-based codebase edits, and strict Apple HIG / Streamlit compliance.

---

## 🛑 Rules & Invariants

1. **Environment & Runtime:**
   - Operating in macOS `zsh`. PAGER is set to `cat`.
   - Always run unit tests using the project virtual environment: `.venv/bin/python3 -m unittest discover tests` or `scripts/runut`.
2. **Fail-Loud Output Contract:**
   - Adhere strictly to declared output schemas in `agents/output_contract.py`. Never emit conversational preambles when machine JSON is expected.
3. **Streamlit UI Standards:**
   - Warnings must render via `st.warning()`, never as fatal `st.error()` (#217).
   - Avoid hardcoded colors that break Streamlit light/dark themes (#207).
4. **Mandatory File Linking:**
   - Format all file references and symbols as clickable GitHub-style markdown links using the `file://` scheme (e.g. [`core/models.py`](file:///Users/abhiraj/Documents/news/agent/core/models.py)).
