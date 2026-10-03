#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# scripts/sync_develop.sh — Workspace Reset & Develop Synchronization for Agents
# ──────────────────────────────────────────────────────────────────────────────
# INSTRUCTION FOR AI AGENTS:
#   Use this script to reset your workspace to the latest clean 'develop' branch
#   before starting a new task or after finishing a previous unit of work.
#
#   Usage:
#     ./scripts/sync_develop.sh
#
# WHAT THIS SCRIPT DOES (Step-by-Step):
#   1. Checks for uncommitted tracked changes and warns if stash/commit is needed.
#   2. Switches local git checkout to 'develop'.
#   3. Pulls latest changes from 'origin/develop' with '--prune' to clear dead tracking.
#   4. Displays git status confirming workspace readiness.
#
# FAIL-LOUD INVARIANTS:
#   - Fails if uncommitted tracked changes would conflict with checking out develop.
#   - Fails if git pull origin develop encounters network or merge errors.
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# Step 1: Ensure inside git repository
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "ERROR: Current directory is not a git repository." >&2
    exit 1
fi

# Step 2: Check for uncommitted tracked changes
if ! git diff-index --quiet HEAD --; then
    echo "ERROR: Uncommitted tracked changes detected in working tree." >&2
    echo "Please commit or stash your changes before syncing develop." >&2
    git status --short
    exit 1
fi

# Step 3: Switch to develop branch
echo "==> Switching to 'develop' branch..."
git checkout develop

# Step 4: Pull latest changes
echo "==> Pulling latest changes from 'origin/develop'..."
git pull --prune origin develop

echo ""
echo "================================================================================"
echo " [OK] Local workspace is synchronized with latest 'origin/develop'."
echo " You are ready to create a new branch using './scripts/create_branch.sh'."
echo "================================================================================"
