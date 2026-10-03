# Git / PR

Any code change. Start from `origin/develop`. End: branch pushed, PR open, merge only after user approval.

1. No push or merge to `main` or `develop` (`GH013`). PR only.
2. Branch names: `feature/<name>`, `fix/<issue>-<name>`, `refactor/<name>`, `chore/<name>`.
3. Scripts, not raw multi-step git:

| Task | Command |
| :--- | :--- |
| Sync develop | `./sync_develop` |
| Branch | `./create_branch <prefix>/<name> [--stash]` |
| Stash | `./stash [push [msg] \| pop \| list \| drop]` |
| Tests | `./runut` |
| PR | `./open_pr -t "..." [-b "..."] [--ai "..."]` |
| Resolve review | `./resolve_comment <pr> [reply] [--ai "..."]` |
| Merge | `./merge_pr <num>` |

4. No `./runut` on branch create. Run before commit, and only if `.py` changed. `.md` / guidelines / prompts / docs: skip tests.
5. Test fail: [`failure.md`](./failure.md). Do not edit a broken script or test; `gh issue create`.
6. PR body: omit `-b` to auto-derive from commit subjects with `(#N)` (#359).
7. Read-only fallback: produce prefilled compare/issue links if `gh` lacks write access.
8. Attribution: pass `--ai "<name>"` (or `AI_NAME="<name>"`) to `./open_pr` / `./resolve_comment`.
9. Review threads: fix, push, then `./resolve_comment <pr> "Addressed in <sha>: <summary>"`. Never resolve only in the GitHub UI.
10. Stop before merge. Show PR URL, diff, tests. `./merge_pr` only after user approval.

```bash
./create_branch <prefix>/<name> [--stash]
./runut   # .py only
git add <files>
git commit -m "<type>: <desc>"
./open_pr -t "<type>: <desc>" -b "## Summary\n<details>"
```
