# Gemini Code Generation Guidelines

Operational standards when **Gemini models** generate, edit, or refactor code in this repository.

---

## 🚦 When to Apply & What to Expect

- **When to Apply:** Any task where Gemini is authoring code, modifying files, debugging, or creating tests.
- **What to Expect:** Clean Python 3.11 code, strict Pydantic models, fail-loud error handling, and zero hallucinated dependencies.

---

## 🛑 Code Generation Invariants

1. **Python 3.11 & Typing:**
   - Use standard library `typing` (`Optional`, `List`, `Dict`, `Tuple`, `Any`).
   - All function signatures must include parameter and return type hints.
2. **Fail-Loud (No Silent Defaults):**
   - Never invent fallback defaults or wrap errors in silent `try/except: pass`.
   - Raise explicit `ValueError` or custom domain exceptions with full diagnostic context (input value, expected values, stage name).
3. **Surgical Edits:**
   - Modify existing files with targeted, contiguous block edits. Never rewrite an entire file to change a few lines.
   - Retain all existing docstrings, rationale comments, and historical issue annotations (`#138`, `#207`, `#217`, `#338`, `#344`).
4. **Streamlit UI Code Rules:**
   - Adhere to Streamlit theme invariants: never inject hardcoded colors or raw CSS that breaks light/dark mode (#207, #219).
   - Render warnings as `st.warning()`, never as fatal `st.error()` (#217).
5. **Mandatory Clickable Links in Responses:**
   - Always reference modified files and symbols with clickable markdown links using the `file://` scheme (e.g. [`core/models.py`](file:///Users/abhiraj/Documents/news/agent/core/models.py)).
