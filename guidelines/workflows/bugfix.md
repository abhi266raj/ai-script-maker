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
# 1. Confirm failure on target test using runner
./runut tests/test_<target>.py

# 2. Branch off develop using standardized branch script
./scripts/create_branch.sh fix/<issue-number>-<short-description>
# Or via shortcut:
./create_branch fix/<issue-number>-<short-description>
```

### 2. Surgical Patch & Verify
```bash
# Apply fix, then verify target test passes
./runut tests/test_<target>.py

# Verify full suite passes
./runut
```

### 3. Commit & Open Pull Request
```bash
git add <files>
git commit -m "fix: <description> (#<issue-number>)"

# Push dedicated branch and open PR targeting develop
./scripts/open_pr.sh --title "fix: <description> (#<issue-number>)" --body "## Summary\n<details of root cause and fix>"
# Or via shortcut:
./open_pr -t "fix: <description> (#<issue-number>)" -b "## Summary\n<details of root cause and fix>"
```

### 4. User Review Gate
- Present PR URL, root cause explanation, and test verification output for explicit user review.
- Never merge without user approval.
- Once approved, merge using `./merge_pr <pr-number>`.
