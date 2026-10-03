#!/usr/bin/env bash
# Usage: ./sync_develop
# Checks out develop and pulls origin/develop with prune.
set -euo pipefail

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "ERROR: Not a git repo" >&2; exit 1; }

if ! git diff-index --quiet HEAD --; then
    echo "ERROR: Uncommitted tracked changes present. Commit or stash first." >&2
    exit 1
fi

echo "Syncing develop..."
git checkout develop
git pull --prune origin develop
echo "develop synced with origin/develop."
