# Antigravity Agent Guidelines & Rules

## 🌿 Git Branching & Feature Workflow Rules

### 1. STRICT PROHIBITION: NO CODING OR COMMITTING ON MAIN
- **Agents are STRICTLY FORBIDDEN from writing, modifying, creating, or editing code files while on the `main` branch.**
- **Agents are STRICTLY FORBIDDEN from committing directly to the `main` branch.**
- Before editing or writing any code, the agent MUST verify the current branch using `git branch --show-current`.
- If the current branch is `main`, the agent MUST immediately switch to or create a feature branch (`git checkout -b feature/<name>`) BEFORE making any file modifications or edits.
- The `main` branch is reserved EXCLUSIVELY for clean integration merges of fully tested feature branches.

### 2. ALWAYS START BY CREATING A NEW FEATURE BRANCH
- When starting any new task, fix, or feature, the agent MUST create and switch to a dedicated feature branch from `main`:
  ```bash
  # Ensure main is up-to-date
  git checkout main
  git pull origin main

  # Create and switch to a new feature branch
  git checkout -b feature/<descriptive-feature-name>
  ```
- **DO NOT run unit tests automatically upon branching from `main` unless explicitly requested by the user.** Save test runs for feature verification and merging.
- Naming conventions for branches:
  - `feature/<feature-name>` for new capabilities, prompts, or agents.
  - `fix/<bug-name>` for bug fixes and patches.
  - `refactor/<refactor-name>` for code or prompt restructuring.

### 3. DEVELOPMENT & TESTING IN FEATURE BRANCH
- All edits, file creations, and iterations must take place within the active feature branch.
- **NEVER merge or commit without user review/verification.** Always present the proposed changes, test status, and diff summary to the user for explicit confirmation before finalizing commits or merging into `main`.
- Run and verify the test suite on the feature branch when ready:
  ```bash
  .venv/bin/python3 -m unittest discover tests
  ```

### 4. USER VERIFICATION & MERGE INTO MAIN
- **CRITICAL**: The agent must **NOT** merge the feature branch into `main` automatically. The agent must present the solution to the user, wait for user verification/approval, and only proceed with merging to `main` when explicitly confirmed by the user.
- Once the user verifies and approves merging:
  1. Switch to `main`:
     ```bash
     git checkout main
     ```
  2. Pull the latest upstream changes:
     ```bash
     git pull origin main
     ```
  3. Merge the feature branch into `main`:
     ```bash
     git merge --no-ff feature/<descriptive-feature-name> -m "Merge feature '<descriptive-feature-name>' into main"
     ```
  4. Verify the test suite on `main`:
     ```bash
     .venv/bin/python3 -m unittest discover tests
     ```
  5. Push the updated `main` and branch (if requested by user):
     ```bash
     git push origin main
     ```
  6. Optionally delete the local feature branch after a successful merge:
     ```bash
     git branch -d feature/<descriptive-feature-name>
     ```
