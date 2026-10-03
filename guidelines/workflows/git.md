# Git Branching & Workflow Rules

---

## 🚦 When to Apply & What to Expect

- **When to Apply:** Any task that modifies code, creates branches, runs verification tests, or merges changes.
- **What to Expect:**
  - Input: Current git state on `main` or `develop`.
  - Output: Isolated feature/fix branch, green test run, explicit user review, and `--no-ff` merge on approval.

---

## 🛑 Rules & Invariants

1. **Main is Read-Only:** Zero direct coding or commits on `main`. Check with `git branch --show-current`. Switch immediately if on `main`.
2. **Dedicated Branch:** Always branch from active trunk (`develop` or `main`).
   - `feature/<name>`: New capabilities or prompts.
   - `fix/<issue>-<name>`: Bug fixes and regressions.
   - `refactor/<name>`: Code restructuring without functional change.
   - `chore/<name>`: Maintenance, version bumps, workflow scripts.
3. **No Auto-Tests on Branching:** Do not run unit tests on branch creation unless requested. Run tests only during verification.
4. **User Confirmation Gate:** Never commit or merge without explicit user confirmation of diff and test results.

---

## 📋 Execution Protocol

1. **Verify & Branch:**
   ```bash
   git checkout <base-branch> && git pull origin <base-branch>
   git checkout -b <prefix>/<descriptive-name>
   ```
2. **Develop & Verify:**
   ```bash
   .venv/bin/python3 -m unittest discover tests
   ```
3. **User Approval:** Present diff and test status. Await confirmation.
4. **Integration Merge (on User OK):**
   ```bash
   git checkout <base-branch> && git pull origin <base-branch>
   git merge --no-ff <prefix>/<descriptive-name> -m "Merge '<prefix>/<descriptive-name>' into <base-branch>"
   .venv/bin/python3 -m unittest discover tests
   ```
