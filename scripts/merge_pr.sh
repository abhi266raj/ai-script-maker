#!/usr/bin/env bash
# Usage: ./merge_pr <pr_number> [--merge]
# Merges PR (squash by default), pulls latest develop, and cleans up local branch.
# --merge: true merge, no squash — for version-increase and release PRs where
# history must be preserved (see guidelines/workflows/release.md).
# Gate: Run ONLY after explicit user confirmation.
set -euo pipefail

[ "$#" -ge 1 ] && [[ "$1" =~ ^[0-9]+$ ]] || { echo "ERROR: Numeric PR number required. Usage: $0 <num> [--merge]" >&2; exit 1; }
PR_NUM="$1"
MERGE_MODE="--squash"
[ "${2:-}" = "--merge" ] && MERGE_MODE="--merge"
[ -n "${2:-}" ] && [ "${2:-}" != "--merge" ] && { echo "ERROR: Unknown option '$2'. Usage: $0 <num> [--merge]" >&2; exit 1; }

command -v gh >/dev/null 2>&1 || { echo "ERROR: gh CLI not installed." >&2; exit 1; }

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
echo "Merging PR #$PR_NUM ($MERGE_MODE)..."
gh pr merge "$PR_NUM" "$MERGE_MODE" --delete-branch

echo "Syncing develop..."
git checkout develop
git pull --prune origin develop

if [ "$CURRENT_BRANCH" != "develop" ] && [ "$CURRENT_BRANCH" != "main" ]; then
    git branch -D "$CURRENT_BRANCH" 2>/dev/null || true
fi

echo "PR #$PR_NUM merged. Develop is up to date."
