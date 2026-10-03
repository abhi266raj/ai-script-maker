#!/usr/bin/env bash
# Usage: ./create_branch <feature|fix|chore|refactor|release>/<name> [--stash]
# Syncs fresh develop, validates prefix, and checks out dedicated branch.
set -euo pipefail

STASH_FLAG=0
RAW_ARGS=()
for arg in "$@"; do
    if [[ "$arg" == "--stash" || "$arg" == "-s" ]]; then
        STASH_FLAG=1
    else
        RAW_ARGS+=("$arg")
    fi
done
set -- "${RAW_ARGS[@]}"

if [ "$#" -lt 1 ]; then
    echo "ERROR: Branch missing. Usage: $0 <prefix>/<name> [--stash]" >&2
    echo "Allowed prefixes: feature, fix, chore, refactor, release" >&2
    exit 1
fi

if [[ "$1" =~ ^(feature|fix|chore|refactor|release)/(.+)$ ]]; then
    PREFIX="${BASH_REMATCH[1]}"
    NAME="${BASH_REMATCH[2]}"
elif [ "$#" -ge 2 ] && [[ "$1" =~ ^(feature|fix|chore|refactor|release)$ ]]; then
    PREFIX="$1"
    NAME="$2"
else
    echo "ERROR: Invalid branch format '$1'. Expected: <prefix>/<name>" >&2
    exit 1
fi

NAME="$(echo "$NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')"
FULL_BRANCH="${PREFIX}/${NAME}"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "ERROR: Not a git repo" >&2; exit 1; }

DID_STASH=0
if ! git diff-index --quiet HEAD --; then
    if [ "$STASH_FLAG" -eq 1 ]; then
        echo "Stashing uncommitted changes before branch switch..."
        git stash push -u -m "create_branch-auto-stash-$(date +%s)"
        DID_STASH=1
    else
        echo "ERROR: Uncommitted tracked changes present. Use './stash' or pass '--stash' to carry changes." >&2
        exit 1
    fi
fi

echo "Syncing develop..."
git checkout develop
git pull origin develop

if git show-ref --verify --quiet "refs/heads/$FULL_BRANCH"; then
    git checkout "$FULL_BRANCH"
    echo "Switched to existing branch '$FULL_BRANCH'."
else
    git checkout -b "$FULL_BRANCH"
    echo "Created branch '$FULL_BRANCH' from develop."
fi

if [ "$DID_STASH" -eq 1 ]; then
    echo "Restoring stashed changes onto '$FULL_BRANCH'..."
    git stash pop
fi
