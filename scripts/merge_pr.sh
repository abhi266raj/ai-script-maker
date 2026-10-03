#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# scripts/merge_pr.sh — Safe Pull Request Merging & Local Develop Synchronization
# ──────────────────────────────────────────────────────────────────────────────
# INSTRUCTION FOR AI AGENTS:
#   CRITICAL: Universal Coding Invariant #2 (User Confirmation Gate) applies:
#   NEVER run this script autonomously or without explicit user permission.
#   Only execute this script AFTER the user has explicitly confirmed that the
#   PR can be merged.
#
#   Usage:
#     ./scripts/merge_pr.sh <pr-number>
#
#   Example:
#     ./scripts/merge_pr.sh 357
#
# WHAT THIS SCRIPT DOES (Step-by-Step):
#   1. Validates the PR number provided by the agent.
#   2. Executes squash merge via GitHub CLI: `gh pr merge <num> --squash --delete-branch`.
#   3. Switches the local workspace to the 'develop' branch.
#   4. Pulls the latest changes from 'origin/develop' with prune.
#   5. Deletes local tracking branch if it still exists.
#   6. Displays status confirming clean sync on 'develop'.
#
# FAIL-LOUD INVARIANTS:
#   - Fails immediately if PR number is missing or not a positive integer.
#   - Fails if GitHub CLI merge fails (e.g. merge conflicts, required status checks).
#   - Fails if git pull origin develop fails.
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# Step 1: Ensure inside git repository
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "ERROR: Current directory is not a git repository." >&2
    exit 1
fi

# Step 2: Validate PR number
if [ "$#" -lt 1 ]; then
    echo "ERROR: PR number is required." >&2
    echo "Usage: $0 <pr-number>" >&2
    echo "Example: $0 357" >&2
    exit 1
fi

PR_NUM="$1"
if [[ ! "$PR_NUM" =~ ^[0-9]+$ ]]; then
    echo "ERROR: Invalid PR number '$PR_NUM'. Must be an integer." >&2
    exit 1
fi

# Step 3: Check GitHub CLI availability
if ! command -v gh >/dev/null 2>&1; then
    echo "ERROR: GitHub CLI ('gh') is not installed or not found on PATH." >&2
    exit 1
fi

# Step 4: Identify current branch before merge
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"

echo "==> Merging PR #$PR_NUM with squash and deleting remote branch..."
gh pr merge "$PR_NUM" --squash --delete-branch

echo "==> Switching local workspace to 'develop'..."
git checkout develop

echo "==> Pulling latest changes from 'origin/develop'..."
git pull --prune origin develop

# Step 5: Clean up local branch if it's not develop or main
if [ "$CURRENT_BRANCH" != "develop" ] && [ "$CURRENT_BRANCH" != "main" ]; then
    if git show-ref --verify --quiet "refs/heads/$CURRENT_BRANCH"; then
        echo "==> Deleting merged local branch '$CURRENT_BRANCH'..."
        git branch -D "$CURRENT_BRANCH" || true
    fi
fi

echo ""
echo "================================================================================"
echo " [OK] PR #$PR_NUM successfully merged into develop!"
echo " Workspace is on up-to-date 'develop'."
echo " INSTRUCTION FOR AGENT:"
echo " - Apply Clean Slate Protocol: Clear stale task context before taking on new work."
echo "================================================================================"
