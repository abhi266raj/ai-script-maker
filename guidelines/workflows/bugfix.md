# Bug fix

Crash, UT fail, CSS/UI drift, pipeline regression. Reproduce first. Minimal diff. Keep issue refs (`#138`, `#207`, `#217`, `#338`, `#344`).

1. Fix the cause. No silent try/catch wrappers.
2. No unrelated edits.
3. Warnings: `st.warning()`, never fatal `st.error()` (#217).

```bash
./runut tests/test_<target>.py
./create_branch fix/<issue>-<name>
# patch, then:
./runut tests/test_<target>.py
./runut
git add <files>
```

Then PR per [`git.md`](./git.md).
