#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# scripts/create_branch.sh — Standardized Branch Creation for AI Agents & Devs
# ──────────────────────────────────────────────────────────────────────────────
# INSTRUCTION FOR AI AGENTS:
#   Do NOT run `git checkout -b` or manual branch creation commands directly.
#   Always invoke this script to start any new feature, bug fix, chore, or refactor.
#
#   Usage:
#     ./scripts/create_branch.sh <prefix>/<name>
#     or
#     ./scripts/create_branch.sh <prefix> <name>
#
#   Examples:
#     ./scripts/create_branch.sh feature/emotion-screenplay
#     ./scripts/create_branch.sh fix 354-vibe-to-emotion
#     ./scripts/create_branch.sh chore polish-guidelines
#
# WHAT THIS SCRIPT DOES (Step-by-Step):
#   1. Validates branch prefix against allowed naming conventions:
#      Allowed prefixes: feature, fix, chore, refactor, release
#   2. Verifies working tree: warns and fails if uncommitted tracked changes exist.
#   3. Checks out 'develop' branch.
#   4. Pulls latest updates from 'origin/develop' to guarantee branching off fresh code.
#   5. Creates and checks out the new branch '<prefix>/<name>'.
#   6. Displays diagnostic success status and next steps for the agent.
#
# FAIL-LOUD INVARIANTS:
#   - Fails immediately if branch prefix is invalid or not recognized.
#   - Fails if uncommitted tracked changes would be lost or dirtied.
#   - Fails if 'develop' cannot be checked out or synced with 'origin/develop'.
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# Step 1: Parse and validate input arguments
if [ "$#" -lt 1 ]; then
    echo "ERROR: Branch name or prefix missing." >&2
    echo "Usage: $0 <prefix>/<name>   OR   $0 <prefix> <name>" >&2
    echo "Allowed prefixes: feature, fix, chore, refactor, release" >&2
    exit 1
fi

PREFIX=""
NAME=""

if [ "$#" -eq 1 ]; then
    INPUT="$1"
    if [[ "$INPUT" =~ ^(feature|fix|chore|refactor|release)/(.+)$ ]]; then
        PREFIX="${BASH_REMATCH[1]}"
        NAME="${BASH_REMATCH[2]}"
    else
        echo "ERROR: Branch name '$INPUT' does not follow convention '<prefix>/<name>'." >&2
        echo "Allowed prefixes: feature, fix, chore, refactor, release" >&2
        echo "Example: $0 feature/emotion-engine" >&2
        exit 1
    fi
else
    PREFIX="$1"
    NAME="$2"
    # Strip leading/trailing slashes if user passed "feature/" "name"
    PREFIX="${PREFIX%/}"
    NAME="${NAME#/}"
    if [[ ! "$PREFIX" =~ ^(feature|fix|chore|refactor|release)$ ]]; then
        echo "ERROR: Invalid prefix '$PREFIX'." >&2
        echo "Allowed prefixes: feature, fix, chore, refactor, release" >&2
        exit 1
    fi
fi

# Sanitize branch name (replace spaces with hyphens, lowercase)
NAME="$(echo "$NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')"
FULL_BRANCH="${PREFIX}/${NAME}"

echo "==> Preparing to create branch: $FULL_BRANCH"

# Step 2: Ensure we are in a git repository
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "ERROR: Current directory is not a git repository." >&2
    exit 1
fi

# Step 3: Check for uncommitted tracked changes
if ! git diff-index --quiet HEAD --; then
    echo "ERROR: Uncommitted tracked changes detected in working tree." >&2
    echo "Please commit or stash your changes before creating a new branch." >&2
    git status --short
    exit 1
fi

# Step 4: Switch to develop and update from origin/develop
echo "==> Checking out 'develop' and syncing with 'origin/develop'..."
git checkout develop
git pull origin develop

# Step 5: Check if branch already exists
if git show-ref --verify --quiet "refs/heads/$FULL_BRANCH"; then
    echo "WARNING: Local branch '$FULL_BRANCH' already exists."
    git checkout "$FULL_BRANCH"
    echo "[OK] Switched to existing branch '$FULL_BRANCH'."
    exit 0
fi

# Step 6: Create and checkout new branch
echo "==> Creating branch '$FULL_BRANCH' from up-to-date 'develop'..."
git checkout -b "$FULL_BRANCH"

echo ""
echo "================================================================================"
echo " [OK] Dedicated branch '$FULL_BRANCH' created and checked out."
echo " INSTRUCTION FOR AGENT:"
# Print next steps for agent
echo " 1. Make your code changes following guidelines/workflows/${PREFIX}.md"
echo " 2. Verify changes with './runut' (or .venv/bin/python3 -m unittest discover tests)"
echo " 3. When complete, use './scripts/open_pr.sh' to push and create a Pull Request."
echo "================================================================================"
