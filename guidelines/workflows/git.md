# Git Branching & Pull Request Workflow

---

## 🚦 When to Apply & What to Expect

- **When to Apply:** Any task that modifies code, creates branches, runs verification tests, or submits changes.
- **What to Expect:**
  - Input: Current clean git state on `develop`.
  - Output: Dedicated branch pushed to origin, GitHub Pull Request created (`gh pr create`), and merged into `develop` only after explicit user approval.

---

## 🛑 Rules & Invariants

1. **Protected Branches (Main & Develop):**
   - Direct pushes to `develop` and `main` are **strictly blocked** by GitHub repository rules (`GH013: Changes must be made through a pull request`).
   - Agents are **strictly forbidden** from attempting direct pushes or merges into `main` or `develop`.
   - **All code changes MUST be submitted via Pull Requests.**
2. **Dedicated Branch Naming:** Always branch from `origin/develop`:
   - `feature/<name>`: New capabilities or prompts.
   - `fix/<issue>-<name>`: Bug fixes and regressions.
   - `refactor/<name>`: Code restructuring without functional change.
   - `chore/<name>`: Maintenance, version bumps, workflow scripts, documentation.
3. **Standardized Scripts:** Agents must invoke standardized scripts in `scripts/` (or via root shortcuts) instead of executing manual multi-step git commands.
4. **No Auto-Tests on Branch Creation:** Do not run unit tests on branch creation unless requested. Run tests during verification before commit.
5. **User Confirmation Gate:** Never merge a Pull Request automatically. Present the PR link, diff summary, and test status for explicit user approval before running `./merge_pr`.

---

## 📋 Execution Protocol

### 1. Verify & Branch from Develop
```bash
./create_branch <prefix>/<descriptive-name>
```

### 2. Develop, Verify & Commit
- **Strict UT Gate:** Run `./runut` **ONLY** if executable code (`.py`) was touched.
  - If only Markdown (`.md`), guidelines, prompts, or docs were changed, **SKIP unit tests**.
- **Failure Protocol:** If any test fails, follow [`guidelines/workflows/failure.md`](./failure.md):
  - Diagnose regression vs. baseline vs. script defect.
  - If script/test itself needs changes, **DO NOT modify script**; file bug report via `gh issue create`.

```bash
# Verify test suite (ONLY if .py code was touched)
./runut

# Stage and commit changes
git add <files>
git commit -m "<type>: <concise description>"
```

### 3. Push Dedicated Branch & Open Pull Request
```bash
./open_pr -t "<type>: <description>" -b "## Summary\n<details of change>"
```

### 4. User Approval & PR Merge Gate
- **STOP HERE:** Present PR URL to user for explicit review and confirmation.
- Once approved, merge PR:
  ```bash
  ./merge_pr <pr-number>
  ```
