# Bug Fix & Regression Workflow

---

## 🚦 When to Apply & What to Expect

- **When to Apply:** Fixing crashes, defects, unit test failures (`UT failure`), CSS/UI drift, or pipeline regressions.
- **What to Expect:**
  - Input: Issue description, error traceback, or failing unit test.
  - Output: Reproducing test, minimal surgical patch, passing regression test suite, and GitHub Pull Request.

---

## 🛑 Rules & Invariants

1. **Root Cause First:** Reproduce and understand the true failure before editing. Never apply symptom-suppressing wrappers (e.g. silent try/catch).
2. **Surgical Scope:** Minimal code edits strictly targeted at the bug. No unrelated refactoring or stylistic churn.
3. **HIG Warning Standards (#217):** Warnings (e.g. format mismatches) must render as `st.warning()`, never as fatal `st.error()`.
4. **Preserve Annotations:** Retain historical issue references (`#138`, `#207`, `#217`, `#338`, `#344`).

---

## 📋 Execution Protocol

### 1. Reproduce & Branch from Develop
```bash
# 1. Confirm failure on target test
.venv/bin/python3 -m unittest tests/test_<target>.py

# 2. Branch off develop
git checkout develop && git pull origin develop
git checkout -b fix/<issue-number>-<short-description>
```

### 2. Surgical Patch & Verify
```bash
# Apply fix, then verify target test passes
.venv/bin/python3 -m unittest tests/test_<target>.py

# Verify full suite passes
.venv/bin/python3 -m unittest discover tests
```

### 3. Commit & Open Pull Request
```bash
git add <files>
git commit -m "fix: <description> (#<issue-number>)"
git push -u origin fix/<issue-number>-<short-description>
gh pr create --base develop --title "fix: <description> (#<issue-number>)" --body "## Summary\n<details of root cause and fix>"
```

### 4. User Review Gate
- Present PR URL, root cause explanation, and test verification output for explicit user review.
- Never merge without user approval.
