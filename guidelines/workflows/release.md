# Release

Version bump, spec, audit, publish.

1. Approved `docs/REQUIREMENTS_vX.Y.md` (or `vX.Y_REQUIREMENTS.md`) and `vX.Y_IMPLEMENTATION_PLAN.md` before feature commits.
2. Version bumps: use `scripts/bump_version.sh <X.Y.Z>` (cuts branch, merges `main` in `--no-ff`, bumps `core/version.py`, opens PR).
3. Never squash version/release PRs: merge with `./merge_pr <num> --merge` (true merge) to keep history intact.
4. After `main` is tagged, start the next spec. Mark prior requirements done or not; ask user to abandon or defer incomplete items.

Steps: draft spec + plan → wait for approval → implement → bump via `scripts/bump_version.sh` → true-merge to develop → true-merge develop to `main` → tag `vX.Y.Z` → audit with user → seed next spec.
