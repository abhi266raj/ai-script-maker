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
3. **No Auto-Tests on Branch Creation:** Do not run unit tests on branch creation unless requested. Run tests during verification before commit.
4. **User Confirmation Gate:** Never merge a Pull Request automatically. Present the PR link, diff summary, and test status for explicit user approval.

---

## 📋 Execution Protocol

### 1. Verify & Branch from Develop
```bash
git checkout develop && git pull origin develop
git checkout -b <prefix>/<descriptive-name>
```

### 2. Develop, Verify & Commit
```bash
# Verify test suite
.venv/bin/python3 -m unittest discover tests

# Stage and commit changes
git add <files>
git commit -m "<type>: <concise description>"
```

### 3. Push Branch & Open Pull Request
```bash
# Push dedicated branch to remote
git push -u origin <prefix>/<descriptive-name>

# Create Pull Request targeting develop
gh pr create --base develop --title "<type>: <description>" --body "## Summary\n<details of change>"
```

### 4. User Approval & PR Merge
- Present the Pull Request URL to the user for review.
- Once explicitly confirmed by the user, merge the PR:
  ```bash
  gh pr merge --squash --delete-branch
  ```
- Sync local develop:
  ```bash
  git checkout develop && git pull origin develop
  ```
