# Operational Coding Guidelines Index

Canonical rule repository governing **how AI agents author, modify, test, and integrate code** in this repository.  
*(Note: These rules apply strictly to code generation and development workflows, NOT application runtime output).*

---

## 🚦 Task Dispatch Matrix (`workflows/`)

| Task Category | When to Apply | What to Expect | Rule File |
| :--- | :--- | :--- | :--- |
| **New Feature** | Writing new capabilities, UI components, data models, or prompts | Spec approval $\rightarrow$ `feature/` branch $\rightarrow$ fail-loud code $\rightarrow$ test pass | [`workflows/feature.md`](./workflows/feature.md) |
| **Bug Fix** | Fixing crashes, test failures, UI/CSS bugs, regressions | Root cause $\rightarrow$ `fix/` branch $\rightarrow$ minimal diff $\rightarrow$ regression test pass | [`workflows/bugfix.md`](./workflows/bugfix.md) |
| **Git & Merging** | Branching, testing, committing, merging | No main commits $\rightarrow$ branch naming $\rightarrow$ user approval $\rightarrow$ `--no-ff` merge | [`workflows/git.md`](./workflows/git.md) |
| **Release & Spec** | Version bumps, release audits, requirements lifecycle | Spec/plan gate $\rightarrow$ commit gate $\rightarrow$ post-release requirement audit | [`workflows/release.md`](./workflows/release.md) |

---

## 🤖 Model-Specific Code Generation Rules (`engines/`)

| Model / Agent | When to Apply | Code Generation Standards | Rule File |
| :--- | :--- | :--- | :--- |
| **Gemini** | When Gemini writes/edits code in this repo | Python 3.11 type hints, surgical edits, Streamlit HIG compliance | [`engines/gemini.md`](./engines/gemini.md) |
| **Grok** | When Grok writes/edits code in this repo | Idiomatic Python, no unapproved dependencies, contract fidelity | [`engines/grok.md`](./engines/grok.md) |
| **Muse** | When Muse writes/edits code in this repo | Token-lean patches, local macOS compatibility, fail-loud handling | [`engines/muse.md`](./engines/muse.md) |

---

## 🛑 Universal Coding Invariants (All Tasks)

1. **Main is Read-Only:** Never edit/commit on `main`. Branch immediately if on `main`.
2. **User Confirmation Gate:** Never commit or merge automatically. Always present diff and test results.
3. **Fail-Loud:** No silent fallbacks or invented defaults in generated code. Raise explicit errors with context.
4. **Preserve Documentation:** Keep all docstrings, comments, and issue references (`#138`, `#217`, `#344`).
5. **Clean Slate Protocol (Clear After Work, Re-Read When Needed):** Clear task-specific rules and assumptions upon completing each work unit. Never carry over stale task context. When starting any new task, re-identify the task type and re-read the required guideline file afresh.
