#!/usr/bin/env bash
# Usage: ./open_pr -t "<title>" -b "<body>"
# Protected-branch guard, pushes dedicated branch, opens PR targeting develop.
set -euo pipefail

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "$CURRENT_BRANCH" = "main" ] || [ "$CURRENT_BRANCH" = "develop" ]; then
    echo "ERROR: Cannot open PR from protected branch '$CURRENT_BRANCH'." >&2
    exit 1
fi

if ! git diff-index --quiet HEAD --; then
    echo "ERROR: Uncommitted tracked changes present. Commit first." >&2
    exit 1
fi

PR_TITLE=""
PR_BODY=""
while [[ "$#" -gt 0 ]]; do
    case "$1" in
        -t|--title) PR_TITLE="$2"; shift 2 ;;
        -b|--body)  PR_BODY="$2"; shift 2 ;;
        *) echo "ERROR: Unknown option '$1'. Use -t and -b." >&2; exit 1 ;;
    esac
done

[ -n "$PR_TITLE" ] || { echo "ERROR: -t/--title is required." >&2; exit 1; }
PR_BODY="${PR_BODY:-## Summary\nPR for $CURRENT_BRANCH}"

command -v gh >/dev/null 2>&1 || { echo "ERROR: gh CLI not installed." >&2; exit 1; }

echo "Pushing $CURRENT_BRANCH..."
git push -u origin "$CURRENT_BRANCH"

EXISTING_PR="$(gh pr list --head "$CURRENT_BRANCH" --base develop --json url --jq '.[0].url // empty')"
if [ -n "$EXISTING_PR" ]; then
    echo "PR already exists: $EXISTING_PR"
    exit 0
fi

PR_URL="$(gh pr create --base develop --head "$CURRENT_BRANCH" --title "$PR_TITLE" --body "$PR_BODY")"
echo "PR opened: $PR_URL"
echo "Awaiting user approval before merge."
