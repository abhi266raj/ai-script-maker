# Operational Coding Guidelines Index

Canonical rule repository governing **how AI agents author, modify, test, and integrate code** in this repository.  
*(Note: These rules apply strictly to code generation and development workflows, NOT application runtime output).*

---

## 🚦 Task Dispatch Matrix (`workflows/`)

| Task Category | When to Apply | What to Expect | Rule File |
| :--- | :--- | :--- | :--- |
| **New Feature** | Writing new capabilities, UI components, data models, or prompts | Spec approval $\rightarrow$ `feature/` branch $\rightarrow$ fail-loud code $\rightarrow$ test pass | [`workflows/feature.md`](./workflows/feature.md) |
| **Bug Fix** | Fixing crashes, test failures, UI/CSS bugs, regressions | Root cause $\rightarrow$ `fix/` branch $\rightarrow$ minimal diff $\rightarrow$ regression test pass | [`workflows/bugfix.md`](./workflows/bugfix.md) |
| **Git & PR Workflow** | Branching, testing, committing, opening Pull Requests | No direct push $\rightarrow$ dedicated branch $\rightarrow$ `gh pr create` $\rightarrow$ user approval | [`workflows/git.md`](./workflows/git.md) |
| **Test Failure & Bug** | Test runner failures, triage, script defects | Root cause triage $\rightarrow$ code fix OR GitHub bug report for test defects | [`workflows/failure.md`](./workflows/failure.md) |
| **Release & Spec** | Version bumps, release audits, requirements lifecycle | Spec/plan gate $\rightarrow$ commit gate $\rightarrow$ post-release requirement audit | [`workflows/release.md`](./workflows/release.md) |

---

## 🤖 Model-Specific Code Generation Rules (`engines/`)

| Model / Agent | When to Apply | Code Generation Standards | Rule File |
| :--- | :--- | :--- | :--- |
| **Gemini** | When Gemini writes/edits code in this repo | Python 3.11 type hints, surgical edits, Streamlit HIG compliance | [`engines/gemini.md`](./engines/gemini.md) |
| **Grok** | When Grok writes/edits code in this repo | Idiomatic Python, no unapproved dependencies, contract fidelity | [`engines/grok.md`](./engines/grok.md) |
| **Muse** | When the Muse assistant works on this repo | Assistant operating notes: repo-scoped GitHub token handling | [`engines/muse.md`](./engines/muse.md) |

---

## 🛑 Universal Coding Invariants (All Tasks)

1. **Protected Branches (Main & Develop):** Direct pushes to `main` and `develop` are **strictly blocked** by GitHub branch rules (`GH013`). Never attempt direct pushes. All changes MUST be submitted via a dedicated branch and Pull Request (`gh pr create` or `./open_pr`).
2. **Standardized Scripts First:** Agents must run reusable workflow scripts in `scripts/` (see [`workflows/git.md`](./workflows/git.md)) instead of raw git commands.
3. **User Confirmation Gate:** Never merge Pull Requests automatically. Present the PR link, diff summary, and test status for explicit user approval before calling `./merge_pr`.
4. **Fail-Loud:** No silent fallbacks or invented defaults in generated code. Raise explicit errors with diagnostic details on invalid inputs.
5. **Preserve Documentation:** Retain all docstrings, comments, and issue references (`#138`, `#217`, `#344`).
6. **Clean Slate Protocol (Clear After Work, Re-Read When Needed):** Clear task-specific rules and assumptions upon completing each work unit. Never carry over stale task context. When starting any new task, re-identify the task type and re-read the required guideline file afresh.
7. **Strict Unit Test Gate (Code-Only):** Run unit tests (`./runut`) **ONLY** when executable code (`.py`) is touched. Strictly **DO NOT** run unit tests when only instructions, guidelines, documentation, or Markdown files (`.md`) are modified.
8. **Master Failure & Script Defect Policy (Agent Task Scripts & Tests):** When a script fails (whether an Agent Task Script in `scripts/` or a test verification script in `tests/`), diagnose the root cause. If the script itself contains a bug or is outdated, agents are **strictly forbidden** from silently hacking or altering the script unilaterally—agents **MUST raise a GitHub bug report** (`gh issue create`) documenting the script defect.
9. **Token-Lean Conciseness (Avoid Redundancy):** Use as few words as possible across all guidelines, code comments, and terminal messages. Eliminate filler, verbosity, and redundant explanations. Keep instructions concise, punchy, and direct to conserve agent context.
10. **Workflow Files Execute from Main:** `pull_request_target` workflows (e.g. `label-merged-prs.yml`) run the file as it exists on the default branch (`main`), not on `develop`. A workflow fix merged only into `develop` does **not** take effect until a release merges it to `main`.
