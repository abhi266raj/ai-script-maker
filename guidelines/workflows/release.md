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
