# Contributing & Agent Development Workflow

All contributors, human developers, and AI agents (including Antigravity, Claude, Copilot, Cursor, etc.) must adhere to the branching and commit rules specified below.

## 🌿 Git Branching & Feature Workflow Rules

### 1. STRICT PROHIBITION: NO CODING OR COMMITTING ON MAIN
- **Agents and developers are STRICTLY FORBIDDEN from writing, modifying, creating, or editing code files while on the `main` branch.**
- **Direct commits to `main` are blocked and strictly prohibited.**
- Always check the active branch before editing or writing code:
  ```bash
  git branch --show-current
  ```
- If on `main`, immediately checkout a new feature branch before touching any files.

### 2. ALWAYS START BY CREATING A NEW FEATURE BRANCH
- When beginning any new capability, fix, prompt, or refactor:
  ```bash
  git checkout main
  git pull origin main
  git checkout -b feature/<descriptive-feature-name>
  ```
- Branch naming prefixes:
  - `feature/<name>` for new features or capabilities.
  - `fix/<name>` for bug fixes and patches.
  - `refactor/<name>` for refactoring code, prompts, or tests.

### 3. DEVELOPMENT & TESTING IN FEATURE BRANCH
- Perform all coding, prompt authoring, and file changes in the feature branch.
- Verify tests before merging:
  ```bash
  .venv/bin/python3 -m unittest discover tests
  ```

### 4. MERGE INTO MAIN UPON COMPLETION
- Merge cleanly into `main` after all tests pass:
  ```bash
  git checkout main
  git pull origin main
  git merge --no-ff feature/<descriptive-feature-name> -m "Merge feature '<descriptive-feature-name>' into main"
  .venv/bin/python3 -m unittest discover tests
  git push origin main
  git branch -d feature/<descriptive-feature-name>
  ```
