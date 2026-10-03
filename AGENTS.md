# Antigravity Agent Guidelines (Master Index)

Primary rule index for all agents. Identify task type below, read the referenced rule file, and follow its protocol.

---

## 🚦 Task Dispatch Matrix

| Task | When to Apply | What to Expect | Rule File |
| :--- | :--- | :--- | :--- |
| **New Feature** | Adding capabilities, UI controls, emotions, formats, prompts | Spec/plan approval $\rightarrow$ branch $\rightarrow$ fail-loud code $\rightarrow$ unit tests | [`guidelines/workflows/feature.md`](./guidelines/workflows/feature.md) |
| **Bug Fix** | Fixing crashes, test failures, UI/CSS bugs, regressions | Root cause analysis $\rightarrow$ fix branch $\rightarrow$ minimal diff $\rightarrow$ test pass | [`guidelines/workflows/bugfix.md`](./guidelines/workflows/bugfix.md) |
| **Git & Merging** | Any branch creation, testing, commit, or merge operation | Prohibition on main $\rightarrow$ branch naming $\rightarrow$ `--no-ff` merge on user OK | [`guidelines/workflows/git.md`](./guidelines/workflows/git.md) |
| **Release & Spec** | Version bumps, release audits, requirements lifecycle | Formal spec & plan $\rightarrow$ commit gate $\rightarrow$ post-release requirement audit | [`guidelines/workflows/release.md`](./guidelines/workflows/release.md) |

---

## 🤖 Engine & Model Execution Rules (`engines/`)

| Engine | When to Apply | What to Expect | Rule File |
| :--- | :--- | :--- | :--- |
| **Gemini** | Antigravity AGY / Google Gemini inference & pair-programming | High context, structured schemas, Streamlit HIG compliance | [`guidelines/engines/gemini.md`](./guidelines/engines/gemini.md) |
| **Grok** | xAI Grok CLI inference (`grok_low`, `grok_medium`, `grok_high`) | Max 2 req/s cap, exponential backoff on 429, effort levels | [`guidelines/engines/grok.md`](./guidelines/engines/grok.md) |
| **Muse** | Apple on-device Foundation Model inference (`fm respond`) | 100% private, on-device silicon inference, token-lean prompts | [`guidelines/engines/muse.md`](./guidelines/engines/muse.md) |

---

## 🛑 Universal Invariants (All Tasks)

1. **Main is Read-Only:** Never edit or commit on `main`. Verify via `git branch --show-current`. Branch immediately if on `main`.
2. **User Confirmation Gate:** Never commit or merge automatically. Present diff summary and test status for explicit user approval.
3. **Fail-Loud:** No silent fallbacks or invented defaults. Raise explicit errors with diagnostic details on invalid inputs.
4. **Preserve Documentation:** Retain all docstrings, comments, and issue references (`#138`, `#217`, `#344`).
5. **Clean Slate Protocol (Clear After Work, Re-Read When Needed):** Clear task-specific rules and assumptions upon completing each work unit. Never carry over stale task context. When starting any new task, re-identify the task type and re-read the required guideline file afresh.
