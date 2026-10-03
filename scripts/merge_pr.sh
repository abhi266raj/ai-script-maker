#!/usr/bin/env bash
# Usage: ./merge_pr <pr_number>
# Merges PR via squash, pulls latest develop, and cleans up local branch.
# Gate: Run ONLY after explicit user confirmation.
set -euo pipefail

[ "$#" -ge 1 ] && [[ "$1" =~ ^[0-9]+$ ]] || { echo "ERROR: Numeric PR number required. Usage: $0 <num>" >&2; exit 1; }
PR_NUM="$1"

command -v gh >/dev/null 2>&1 || { echo "ERROR: gh CLI not installed." >&2; exit 1; }

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
echo "Merging PR #$PR_NUM..."
gh pr merge "$PR_NUM" --squash --delete-branch

echo "Syncing develop..."
git checkout develop
git pull --prune origin develop

if [ "$CURRENT_BRANCH" != "develop" ] && [ "$CURRENT_BRANCH" != "main" ]; then
    git branch -D "$CURRENT_BRANCH" 2>/dev/null || true
fi

echo "PR #$PR_NUM merged. Develop is up to date."
