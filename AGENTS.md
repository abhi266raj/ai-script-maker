# AI Coding Agent Guidelines (Master Index)

This repository index governs **how AI agents author, modify, test, and integrate code** in this codebase.  
*(Note: These rules apply strictly to code generation and development workflows, NOT application runtime output).*

---

## 🚦 Task Dispatch Matrix (`guidelines/workflows/`)

| Task Category | When to Apply | What to Expect | Rule File |
| :--- | :--- | :--- | :--- |
| **New Feature** | Writing new capabilities, UI controls, models, or prompt matrices | Spec/plan gate $\rightarrow$ branch $\rightarrow$ fail-loud code $\rightarrow$ unit tests | [`guidelines/workflows/feature.md`](./guidelines/workflows/feature.md) |
| **Bug Fix** | Fixing crashes, defects, test failures, or UI regressions | Root cause analysis $\rightarrow$ fix branch $\rightarrow$ surgical minimal diff $\rightarrow$ test pass | [`guidelines/workflows/bugfix.md`](./guidelines/workflows/bugfix.md) |
| **Git & PR Workflow** | Branch creation, commit gates, test execution, opening Pull Requests | Prohibition on direct push to main/develop $\rightarrow$ PR creation $\rightarrow$ user approval | [`guidelines/workflows/git.md`](./guidelines/workflows/git.md) |
| **Release & Spec** | Version bumps, release audits, requirements lifecycle | Formal spec & plan $\rightarrow$ commit gate $\rightarrow$ post-release requirement audit | [`guidelines/workflows/release.md`](./guidelines/workflows/release.md) |

---

## 🤖 Model-Specific Code Generation Rules (`guidelines/engines/`)

| Model / Agent | When to Apply | Code Generation Standards | Rule File |
| :--- | :--- | :--- | :--- |
| **Gemini** | When Gemini writes/edits code in this repo | Python 3.11 type hints, surgical edits, Streamlit HIG compliance | [`guidelines/engines/gemini.md`](./guidelines/engines/gemini.md) |
| **Grok** | When Grok writes/edits code in this repo | Idiomatic Python, no unapproved dependencies, contract fidelity | [`guidelines/engines/grok.md`](./guidelines/engines/grok.md) |
| **Muse** | When Muse writes/edits code in this repo | Token-lean patches, local macOS compatibility, fail-loud handling | [`guidelines/engines/muse.md`](./guidelines/engines/muse.md) |

---

## 🛑 Universal Coding Invariants (All Tasks)

1. **Protected Branches (Main & Develop):** Direct pushes to `main` and `develop` are **strictly blocked** by GitHub branch rules (`GH013`). Never attempt direct pushes. All changes MUST be submitted via a dedicated branch and Pull Request (`gh pr create`).
2. **User Confirmation Gate:** Never merge Pull Requests automatically. Present the PR link, diff summary, and test status for explicit user approval.
3. **Fail-Loud:** No silent fallbacks or invented defaults in generated code. Raise explicit errors with diagnostic details on invalid inputs.
4. **Preserve Documentation:** Retain all docstrings, comments, and issue references (`#138`, `#217`, `#344`).
5. **Clean Slate Protocol (Clear After Work, Re-Read When Needed):** Clear task-specific rules and assumptions upon completing each work unit. Never carry over stale task context. When starting any new task, re-identify the task type and re-read the required guideline file afresh.
