# Agent rules (code only; not app runtime)

Dispatch: re-read the matching file each task. Do not reuse prior-task assumptions.

| Task | File |
| :--- | :--- |
| Feature | `guidelines/workflows/feature.md` |
| Bug fix | `guidelines/workflows/bugfix.md` |
| Git / PR | `guidelines/workflows/git.md` |
| Test or script failure | `guidelines/workflows/failure.md` |
| Release | `guidelines/workflows/release.md` |
| Gemini | `guidelines/engines/gemini.md` |
| Grok | `guidelines/engines/grok.md` |
| Muse | `guidelines/engines/muse.md` |

1. **Branches:** `main` and `develop` reject direct push (`GH013`). Branch + PR (`./open_pr` or `gh pr create`). Never push those branches.
2. **Scripts:** Use `scripts/` shortcuts (`./sync_develop`, `./create_branch`, `./stash`, `./runut`, `./open_pr`, `./resolve_comment`, `./merge_pr`). See `guidelines/workflows/git.md`.
3. **Merge:** Never merge unprompted. Show PR link, diff, test status. Merge only after user says yes (`./merge_pr`).
4. **Fail-loud:** No silent fallbacks or invented defaults. Raise with input, expected, stage.
5. **Keep docs:** Docstrings, comments, issue refs (`#138`, `#217`, `#344`).
6. **UT gate:** `./runut` only if `.py` changed. Skip for `.md`, guidelines, prompts, docs.
7. **Script/test bugs:** If `scripts/` or `tests/` is wrong, do not patch it. `gh issue create`. See `guidelines/workflows/failure.md`.
8. **Tokens:** Fewest words in guidelines, comments, and terminal text.
9. **Workflows run from main:** `pull_request_target` workflows run from `main`, not `develop`. Fixes take effect after release merge to `main`.
