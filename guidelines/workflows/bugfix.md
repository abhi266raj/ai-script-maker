# Bug fix

Crash, UT fail, CSS/UI drift, pipeline regression. Reproduce first. Minimal diff. Keep issue refs (`#138`, `#217`).

1. Fix root cause. No silent try/catch wrappers.
2. No unrelated edits.
3. Warnings: `st.warning()`, never fatal `st.error()` (#217).
4. Reopening: if the bug carries the `code completed` tag, remove it on reopen — the work wasn't actually complete, and the tag hides the bug from triage.

| Action | Target |
| :--- | :--- |
| Reproduce | `tests/test_<target>.py` via `./runut` |
| Branch | `./create_branch fix/<issue>-<name>` |
| Verify | `./runut` |
| PR & merge | [`git.md`](./git.md) |
