#!/bin/bash
# Commit all current work in this repo. Usage:
#   bash commit_all.sh "your commit message"
# If no message is given, a default checkpoint message is used.
set -e
cd "$(dirname "$0")"

git add -A

MSG="${1:-chore: checkpoint commit of all work till now}"

if git diff --cached --quiet; then
  echo "Nothing new to commit — working tree is clean."
else
  git commit -m "$MSG"
  echo "Committed on branch: $(git branch --show-current)"
fi

git status --short
