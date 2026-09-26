# Development, Requirement & Release Workflow

This document establishes the official governance, branching model, and requirement lifecycle for Hindi Reel Studio. All human developers and AI pair-programming agents must strictly adhere to these rules.

---

## 1. Core Philosophy: Specification-First Engineering

1. **Every Requirement is Scoped to a Formal Release**:
   No ad-hoc or unmanaged features are introduced directly into code. Every feature, architectural shift, or pipeline extension must be bound to a formal release specification (`vX.Y_REQUIREMENTS.md` or `docs/REQUIREMENTS_vX.Y.md`).
2. **Commit Gate (Requirements & Plan Mandatory)**:
   The AI agent is **strictly forbidden from writing or committing feature code** without:
   - An approved requirements specification document (`vX.Y_REQUIREMENTS.md`).
   - An approved implementation plan document (`vX.Y_IMPLEMENTATION_PLAN.md`).
3. **AI Permitted vs Prohibited Scope**:
   - **Permitted**: Writing and updating documentation, authoring technical specifications, formulating requirements, and writing bug fixes/patches on dedicated branches.
   - **Prohibited**: Autonomous feature coding without prior requirement and implementation plan approval.

---

## 2. Git Branching & Merge Lifecycle

```
main (stable, release-only)
  │
  ├── feature/<feature-name> ──► verify ──► user approve ──► merge --no-ff ──► main
  ├── fix/<bug-name>         ──► verify ──► user approve ──► merge --no-ff ──► main
  └── refactor/<name>        ──► verify ──► user approve ──► merge --no-ff ──► main
```

### Rule 1: Strict Prohibition Against Coding or Committing on Main
- **No direct commits on `main` under any circumstances.**
- Before modifying or creating code files, verify the active branch with `git branch --show-current`.
- If on `main`, immediately switch to or create a dedicated feature branch.

### Rule 2: Start Every Task with a Dedicated Feature Branch
```bash
# 1. Ensure main is up-to-date
git checkout main
git pull origin main

# 2. Branch out
git checkout -b feature/<descriptive-name>
# (use fix/<name> for bugs, refactor/<name> for restructuring)
```
*Note: Do not run tests automatically upon branching; save test executions for verification.*

### Rule 3: Develop, Test, and Verify on Feature Branch
- Perform all work, iterations, and unit tests inside the feature branch:
  ```bash
  .venv/bin/python3 -m unittest discover tests
  ```
- **Never merge or commit without explicit user review**: Always present the diff summary, changes made, and test status to the user.

### Rule 4: User Approval Gate & Integration into Main
- Wait for the user's explicit confirmation before merging into `main`.
- Once confirmed:
  ```bash
  git checkout main
  git pull origin main
  git merge --no-ff feature/<descriptive-name> -m "Merge feature '<descriptive-name>' into main"
  git push origin main
  git branch -d feature/<descriptive-name>
  ```

---

## 3. Post-Release Transition & Requirement Audit Gate

Once a release is tagged and finalized on `main`:

```
Release vX.Y Finalized & Tagged on main
  │
  ├── 1. Branch: feature/vX.(Y+1)-requirements
  │
  ├── 2. Audit Previous Release Requirements:
  │      • Verify completed & tested items
  │      • Identify uncompleted / deferred items
  │
  ├── 3. User Prompt Gate:
  │      "For each uncompleted item, confirm if it is:
  │       [A] Abandoned / Deprecated, or
  │       [B] Carried Over into vX.(Y+1)"
  │
  └── 4. Author vX.(Y+1)_REQUIREMENTS.md with User Decisions Recorded
```

1. **Immediate Transition to Next Version**:
   The AI agent immediately initiates work on the requirements document for the next version (`vX.(Y+1)_REQUIREMENTS.md`).
2. **Previous Requirement Audit**:
   Before finalizing the new requirements, systematically audit every item from the previous release:
   - Identify which requirements were completely implemented and verified.
   - Flag any uncompleted, partially completed, or unverified requirements.
3. **Explicit User Decision Gate**:
   The AI agent MUST prompt the user directly regarding each uncompleted item to confirm whether it should be:
   - **Abandoned / Deprecated**, or
   - **Carried Over / Deferred** into the upcoming release.
4. **Recording & Action**:
   Document the decisions in the new requirements specification and act strictly according to the user's instructions.

---

## 4. Release Packaging & Version Standards

1. **Single Source of Truth for Version**:
   All modules, UI elements, build scripts, and metadata import their version string directly from `core/version.py`:
   ```python
   __version__ = "X.Y.Z"
   VERSION = __version__
   ```
2. **Build Outputs & Separation**:
   - **DEV Builds**: Output to `dev/vX.Y.Z/Hindi Reel Studio DEV.app` (Port `8502`, bundle ID `com.hindireel.studio.dev`, red DEV icon badge).
   - **RELEASE Builds**: Output to `dist/vX.Y.Z/Hindi-Reel-Studio-vX.Y.Z-macOS.dmg` (Port `8501`, bundle ID `com.hindireel.studio`, clean icon). Intermediate loose `.app` bundles in `dist/` are automatically removed so `dist/` contains strictly the DMG installer.
3. **Version Control Protection**:
   All `.app` bundles, `dev/`, `dist/`, and `build/` directories are strictly excluded from git tracking via `.gitignore`.
4. **Network Protocol Standard**:
   Dual-stack simultaneous IPv6 (`[::1]`) and IPv4 (`127.0.0.1`) loopback server support bound on `::`.
