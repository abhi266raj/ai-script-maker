# Release Governance & Requirement Lifecycle

---

## 🚦 When to Apply & What to Expect

- **When to Apply:** Version bumps, release requirement authoring, post-release audits, and release publishing.
- **What to Expect:**
  - Input: Current release scope or previous release tags.
  - Output: Bound requirements spec (`vX.Y_REQUIREMENTS.md`), implementation plan, audit decisions (abandoned vs deferred), and clean release tags.

---

## 🛑 Rules & Invariants

1. **Formal Binding:** Every release requires an approved requirements document (`docs/REQUIREMENTS_vX.Y.md` / `vX.Y_REQUIREMENTS.md`) and implementation plan (`vX.Y_IMPLEMENTATION_PLAN.md`).
2. **Commit Gate:** No autonomous feature commits without approved requirements and implementation plan.
3. **Version Increase ≠ Release:** Bumping the version number on develop is not a release. The release happens when develop is merged to main (true merge) and tagged.
4. **Never Squash Version/Release Merges:** Version-increase PRs into develop and release PRs into main are merged as TRUE merges (`--no-ff` / `gh pr merge --merge`). Squashing them destroys the merge history that proves what came from where.

## 📋 Version Increase Protocol

Automated: `scripts/bump_version.sh <X.Y.Z>`.

1. **Pull develop:** Fetch origin; cut `chore/version-<X.Y.Z>` from `origin/develop`.
2. **Merge main in:** `git merge --no-ff origin/main` into the version branch, so any main-only commits come along with history intact. On conflict: abort, resolve manually — never auto-resolve.
3. **Bump:** Update `core/version.py` (single source of truth), commit.
4. **PR → develop:** Push, open PR targeting develop (explicit `-b` body; auto-derive needs an issue ID).
5. **Merge after explicit user approval:** True merge — `./merge_pr <num> --merge`. NEVER squash. Delete the branch.
3. **Post-Release Requirement Audit Gate:**
   - Once a version is tagged on `main`, immediately start the next version spec.
   - Audit all previous requirements: classify as completed or uncompleted.
4. **User Decision Gate:** Explicitly ask user to decide fate of each incomplete item:
   - **Abandoned / Deprecated**, OR
   - **Carried Over / Deferred** to next release.

---

## 📋 Execution Protocol

1. **Author Spec & Plan:** Draft `vX.Y_REQUIREMENTS.md` and `vX.Y_IMPLEMENTATION_PLAN.md`.
2. **Commit Gate:** Await explicit user approval before feature code implementation.
3. **Tag & Release:** Once merged to `main`, tag the release (`git tag vX.Y.Z`).
4. **Transition Audit:** Audit previous requirements with user; seed next version specification.
