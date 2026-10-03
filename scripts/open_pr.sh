#!/usr/bin/env bash
# Usage: ./open_pr -t "<title>" [-b "<body>"] [--ai "<name>"]
# Protected-branch guard, pushes dedicated branch, opens PR targeting develop.
# -b omitted: body is auto-derived from branch commits (issue #359) — commit
# subjects listed under "## Summary", plus "#N fixed" per unique (#N) found.
# AI attribution: --ai "<name>" (or AI_NAME env) appends "_Raised by <name>_" to the PR body.
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
AI_NAME="${AI_NAME:-}"
while [[ "$#" -gt 0 ]]; do
    case "$1" in
        -t|--title) PR_TITLE="$2"; shift 2 ;;
        -b|--body)  PR_BODY="$2"; shift 2 ;;
        -a|--ai)    AI_NAME="$2"; shift 2 ;;
        *) echo "ERROR: Unknown option '$1'. Use -t, -b, --ai." >&2; exit 1 ;;
    esac
done

[ -n "$PR_TITLE" ] || { echo "ERROR: -t/--title is required." >&2; exit 1; }

if [ -z "$PR_BODY" ]; then
    # Auto-derive the PR body from branch commit messages (issue #359).
    git fetch origin develop --quiet 2>/dev/null || true
    if ! git rev-parse --verify --quiet origin/develop >/dev/null; then
        echo "ERROR: Cannot resolve origin/develop. Fetch it or pass -b with an explicit body." >&2
        exit 1
    fi
    COMMITS="$(git log --format='- %s' origin/develop..HEAD)"
    if [ -z "$COMMITS" ]; then
        echo "ERROR: No commits in origin/develop..HEAD — nothing to derive a PR body from. Pass -b with an explicit body." >&2
        exit 1
    fi
    ISSUE_IDS="$(printf '%s\n' "$COMMITS" | grep -oE '\(#[0-9]+\)' | grep -oE '[0-9]+' | sort -nu || true)"
    if [ -z "$ISSUE_IDS" ]; then
        echo "ERROR: No issue ID (#N) found in commit subjects. Include (#N) in a commit message or pass -b with an explicit body." >&2
        exit 1
    fi
    PR_BODY="## Summary"$'\n'"${COMMITS}"
    for ID in $ISSUE_IDS; do
        PR_BODY="${PR_BODY}"$'\n\n'"#${ID} fixed"
    done
fi
if [ -n "$AI_NAME" ]; then
    PR_BODY="${PR_BODY}"$'\n\n'"_Raised by ${AI_NAME}_"
fi

command -v gh >/dev/null 2>&1 || { echo "ERROR: gh CLI not installed." >&2; exit 1; }

echo "Pushing $CURRENT_BRANCH..."
git push -u origin "$CURRENT_BRANCH"

EXISTING_PR="$(gh pr list --head "$CURRENT_BRANCH" --base develop --json url --jq '.[0].url // empty')"
if [ -n "$EXISTING_PR" ]; then
    PR_URL="$EXISTING_PR"
    PR_NUM="$(echo "$PR_URL" | grep -oE '[0-9]+$')"
    echo "PR already exists: $PR_URL"
else
    PR_URL="$(gh pr create --base develop --head "$CURRENT_BRANCH" --title "$PR_TITLE" --body "$PR_BODY")"
    PR_NUM="$(echo "$PR_URL" | grep -oE '[0-9]+$')"
    echo "PR opened: $PR_URL"
fi

echo ""
echo "=== Pull Request Details (Rule 3) ==="
echo "- GitHub URL: $PR_URL"
echo "- Merge Command: ./merge_pr $PR_NUM"
echo "- Diff Summary:"
git diff --stat origin/develop..HEAD
echo ""
echo "STOP HERE: Do not merge unprompted. Show GitHub PR URL, diff, and run './merge_pr $PR_NUM' only after explicit user approval."
