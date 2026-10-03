#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# scripts/open_pr.sh — Push Dedicated Branch & Open GitHub Pull Request
# ──────────────────────────────────────────────────────────────────────────────
# INSTRUCTION FOR AI AGENTS:
#   Do NOT run raw `git push` or manual `gh pr create` commands directly.
#   Always invoke this script when you are ready to submit your work for review:
#
#   Usage:
#     ./scripts/open_pr.sh --title "<PR Title>" --body "<PR Summary Markdown>"
#     or
#     ./scripts/open_pr.sh -t "<PR Title>" -b "<PR Summary Markdown>"
#
#   Example:
#     ./scripts/open_pr.sh -t "feat: add emotion selector" -b "## Summary\n- Adds emotion model"
#
# WHAT THIS SCRIPT DOES (Step-by-Step):
#   1. Protected Branch Guard: Fails loud if run from 'main' or 'develop'.
#   2. Validates working tree: Warns if uncommitted tracked changes exist.
#   3. GitHub CLI Check: Ensures 'gh' is installed and authenticated.
#   4. Pushes the dedicated branch to 'origin' with upstream tracking.
#   5. Submits a Pull Request targeting the 'develop' branch.
#   6. Displays the PR URL and prints instructions for the User Review Gate.
#
# FAIL-LOUD INVARIANTS:
#   - Fails immediately if executed on 'main' or 'develop' (GH013 compliance).
#   - Fails if uncommitted tracked changes remain unstaged/uncommitted.
#   - Fails if '--title' or PR title argument is omitted.
#   - Fails if GitHub CLI fails or is not logged in.
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# Step 1: Ensure inside git repository
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "ERROR: Current directory is not a git repository." >&2
    exit 1
fi

# Step 2: Protected Branch Check
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "$CURRENT_BRANCH" = "main" ] || [ "$CURRENT_BRANCH" = "develop" ]; then
    echo "ERROR: Direct operations and PR creation from '$CURRENT_BRANCH' are forbidden." >&2
    echo "You must work on a dedicated branch (feature/*, fix/*, chore/*, refactor/*)." >&2
    exit 1
fi

# Step 3: Check for uncommitted tracked changes
if ! git diff-index --quiet HEAD --; then
    echo "ERROR: Uncommitted tracked changes detected in working tree." >&2
    echo "Please commit your changes before opening a Pull Request:" >&2
    git status --short
    exit 1
fi

# Step 4: Parse options (--title, --body)
PR_TITLE=""
PR_BODY=""

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        -t|--title)
            PR_TITLE="$2"
            shift 2
            ;;
        -b|--body)
            PR_BODY="$2"
            shift 2
            ;;
        *)
            echo "ERROR: Unrecognized argument '$1'." >&2
            echo "Usage: $0 --title \"<PR Title>\" --body \"<PR Body Markdown>\"" >&2
            exit 1
            ;;
    esac
done

if [ -z "$PR_TITLE" ]; then
    echo "ERROR: PR title is required." >&2
    echo "Usage: $0 --title \"<PR Title>\" --body \"<PR Body Markdown>\"" >&2
    exit 1
fi

if [ -z "$PR_BODY" ]; then
    PR_BODY="## Summary\nAutomated PR opened for branch \`$CURRENT_BRANCH\`."
fi

# Step 5: Check GitHub CLI availability
if ! command -v gh >/dev/null 2>&1; then
    echo "ERROR: GitHub CLI ('gh') is not installed or not found on PATH." >&2
    exit 1
fi

# Step 6: Push current branch to origin
echo "==> Pushing branch '$CURRENT_BRANCH' to origin..."
git push -u origin "$CURRENT_BRANCH"

# Step 7: Check if PR already exists for this branch
EXISTING_PR="$(gh pr list --head "$CURRENT_BRANCH" --base develop --json number,url --jq '.[0].url // empty')"
if [ -n "$EXISTING_PR" ]; then
    echo ""
    echo "================================================================================"
    echo " [NOTE] A Pull Request already exists for this branch:"
    echo " $EXISTING_PR"
    echo " Your latest commits have been pushed and reflected in the PR."
    echo "================================================================================"
    exit 0
fi

# Step 8: Create Pull Request targeting develop
echo "==> Creating Pull Request targeting 'develop'..."
PR_URL="$(gh pr create --base develop --head "$CURRENT_BRANCH" --title "$PR_TITLE" --body "$PR_BODY")"

echo ""
echo "================================================================================"
echo " [OK] Pull Request created successfully!"
echo " PR URL: $PR_URL"
echo ""
echo " INSTRUCTION FOR AGENT (Universal Coding Invariant #2):"
echo " 1. STOP HERE. Do NOT merge this Pull Request automatically."
echo " 2. Present the PR URL, diff summary, and test verification status to the user."
echo " 3. Await explicit user approval before calling './scripts/merge_pr.sh'."
echo "================================================================================"
