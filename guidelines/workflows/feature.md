# Feature Development Workflow

---

## 🚦 When to Apply & What to Expect

- **When to Apply:** Authoring new capabilities, UI components, data models, emotions, formats, or prompts.
- **What to Expect:**
  - Input: Approved requirement specification or user feature request.
  - Output: Dedicated `feature/` branch, fail-loud implementation, backward-compatible models, passing unit tests, and GitHub Pull Request.

---

## 🛑 Rules & Invariants

1. **Commit Gate:** No autonomous feature code without an approved requirement specification (`docs/REQUIREMENTS_vX.Y.md` / GitHub issue) and implementation plan.
2. **Fail-Loud Architecture:** No silent fallbacks or invented defaults. Missing data must raise explicit errors with diagnostic details.
3. **Layer Separation:**
   - Enums & Constants $\rightarrow$ [`core/constants.py`](file:///Users/abhiraj/Documents/news/agent/core/constants.py)
   - Data Models $\rightarrow$ [`core/models.py`](file:///Users/abhiraj/Documents/news/agent/core/models.py)
   - Prompt Directives $\rightarrow$ [`core/prompt_matrix.py`](file:///Users/abhiraj/Documents/news/agent/core/prompt_matrix.py) & [`prompts/`](file:///Users/abhiraj/Documents/news/agent/prompts/)
   - Streamlit UI $\rightarrow$ [`app.py`](file:///Users/abhiraj/Documents/news/agent/app.py)
4. **Backward Compatibility:** Saved stories and previous schema payloads must continue to load without data loss.

---

## 📋 Execution Protocol

### 1. Plan & Branch from Develop
Use the standardized script to ensure a clean branch off fresh develop:
```bash
./scripts/create_branch.sh feature/<descriptive-feature-name>
# Or via shortcut:
./create_branch feature/<descriptive-feature-name>
```

### 2. Implement & Verify
```bash
# Implement changes adhering to fail-loud architecture
# Verify with standardized test runner
./runut
```

### 3. Commit & Open Pull Request
```bash
git add <files>
git commit -m "feat: <description>"

# Push dedicated branch and open PR targeting develop
./scripts/open_pr.sh --title "feat: <description>" --body "## Summary\n<details>"
# Or via shortcut:
./open_pr -t "feat: <description>" -b "## Summary\n<details>"
```

### 4. User Review Gate
- Present PR URL, diff summary, and test verification output for explicit user review.
- Never merge without user approval.
- Once approved, merge using `./merge_pr <pr-number>`.
