# Operational Guidelines Index

Canonical rule repository for all agents. Classify your task below and execute the linked protocol.

---

## 🚦 Task Dispatch Matrix (`workflows/`)

| Task Category | When to Apply | What to Expect | Rule File |
| :--- | :--- | :--- | :--- |
| **New Feature** | Adding capabilities, UI components, emotions, formats, prompts | Spec approval $\rightarrow$ `feature/` branch $\rightarrow$ fail-loud code $\rightarrow$ test pass | [`workflows/feature.md`](./workflows/feature.md) |
| **Bug Fix** | Fixing crashes, test failures, UI/CSS bugs, regressions | Root cause $\rightarrow$ `fix/` branch $\rightarrow$ minimal diff $\rightarrow$ regression test pass | [`workflows/bugfix.md`](./workflows/bugfix.md) |
| **Git & Merging** | Branching, testing, committing, merging | No main commits $\rightarrow$ branch naming $\rightarrow$ user approval $\rightarrow$ `--no-ff` merge | [`workflows/git.md`](./workflows/git.md) |
| **Release & Spec** | Version bumps, release audits, requirements lifecycle | Spec/plan gate $\rightarrow$ commit gate $\rightarrow$ post-release requirement audit | [`workflows/release.md`](./workflows/release.md) |

---

## 🤖 Engine & Model Execution Rules (`engines/`)

| Engine | When to Apply | What to Expect | Rule File |
| :--- | :--- | :--- | :--- |
| **Gemini** | Antigravity AGY / Google Gemini inference & pair-programming | High context, structured schemas, Streamlit HIG compliance | [`engines/gemini.md`](./engines/gemini.md) |
| **Grok** | xAI Grok CLI inference (`grok_low`, `grok_medium`, `grok_high`) | Max 2 req/s cap, exponential backoff on 429, effort levels | [`engines/grok.md`](./engines/grok.md) |
| **Muse** | Apple on-device Foundation Model inference (`fm respond`) | 100% private, on-device silicon inference, token-lean prompts | [`engines/muse.md`](./engines/muse.md) |

---

## 🛑 Universal Invariants (All Tasks)

1. **Main is Read-Only:** Never edit/commit on `main`. Branch immediately if on `main`.
2. **User Confirmation Gate:** Never commit or merge automatically. Always present diff and test results.
3. **Fail-Loud:** No silent fallbacks or invented defaults. Raise explicit errors with context.
4. **Preserve Documentation:** Keep all docstrings, comments, and issue references (`#138`, `#217`, `#344`).
5. **Clean Slate Protocol (Clear After Work, Re-Read When Needed):** Clear task-specific rules and assumptions upon completing each work unit. Never carry over stale task context. When starting any new task, re-identify the task type and re-read the required guideline file afresh.
