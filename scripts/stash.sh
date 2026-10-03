#!/usr/bin/env bash
# Usage: ./stash [push [message] | pop | list | drop]
# Safe, token-lean shortcut for git stash operations.
set -euo pipefail

ACTION="${1:-push}"

case "$ACTION" in
    pop)
        git stash pop
        ;;
    list)
        git stash list
        ;;
    drop)
        TARGET="${2:-stash@{0}}"
        git stash drop "$TARGET"
        ;;
    push|save)
        MSG="${2:-stash-$(date +%s)}"
        if git diff-index --quiet HEAD -- && [ -z "$(git ls-files --others --exclude-standard)" ]; then
            echo "Nothing to stash: working tree clean."
            exit 0
        fi
        git stash push -u -m "$MSG"
        echo "Stashed changes as: $MSG"
        ;;
    *)
        # Default: treat argument as push message
        MSG="$1"
        if git diff-index --quiet HEAD -- && [ -z "$(git ls-files --others --exclude-standard)" ]; then
            echo "Nothing to stash: working tree clean."
            exit 0
        fi
        git stash push -u -m "$MSG"
        echo "Stashed changes as: $MSG"
        ;;
esac
