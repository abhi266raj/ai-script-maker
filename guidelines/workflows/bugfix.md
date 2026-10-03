# Bug fix

Crash, UT fail, CSS/UI drift, pipeline regression. Reproduce first. Minimal diff. Keep issue refs (`#138`, `#217`).

1. Fix root cause. No silent try/catch wrappers.
2. No unrelated edits.
3. Warnings: `st.warning()`, never fatal `st.error()` (#217).

| Action | Target |
| :--- | :--- |
| Reproduce | `tests/test_<target>.py` via `./runut` |
| Branch | `./create_branch fix/<issue>-<name>` |
| Verify | `./runut` |
| PR & merge | [`git.md`](./git.md) |
