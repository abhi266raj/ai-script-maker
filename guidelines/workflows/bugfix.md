# Bug Fix & Regression Workflow

---

## 🚦 When to Apply & What to Expect

- **When to Apply:** Fixing crashes, defects, unit test failures (`UT failure`), CSS/UI drift, or pipeline regressions.
- **What to Expect:**
  - Input: Issue description, error traceback, or failing unit test.
  - Output: Reproducing test, minimal surgical patch, passing regression test suite, and user approval.

---

## 🛑 Rules & Invariants

1. **Root Cause First:** Reproduce and understand the true failure before editing. Never apply symptom-suppressing wrappers (e.g. silent try/catch).
2. **Surgical Scope:** Minimal code edits strictly targeted at the bug. No unrelated refactoring.
3. **HIG Warning Standards (#217):** Warnings (e.g. format mismatches) must render as `st.warning()`, never as fatal `st.error()`.
4. **Preserve Annotations:** Retain historical issue references (`#138`, `#207`, `#217`, `#338`, `#344`).

---

## 📋 Execution Protocol

1. **Reproduce & Branch:** Confirm failure on target test, then create fix branch:
   ```bash
   git checkout -b fix/<issue-number>-<short-description>
   ```
2. **Patch:** Apply surgical minimal fix addressing root cause.
3. **Verify:**
   ```bash
   # 1. Verify target test passes
   .venv/bin/python3 -m unittest tests/test_<target>.py
   # 2. Verify entire suite passes
   .venv/bin/python3 -m unittest discover tests
   ```
4. **User Review:** Present diff, root cause explanation, and test verification output for confirmation.
