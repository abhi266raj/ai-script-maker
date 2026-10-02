#!/usr/bin/env bash
# release_closing_keywords.sh — collect every fixed issue number from PRs merged
# into develop since the last release, so the release PR (develop → main) can
# carry "Closes #N" for each and GitHub auto-closes them on merge.
#
# GitHub only auto-closes issues when the PR with the closing keyword merges
# into the DEFAULT branch. Fix PRs target develop, so they never auto-close.
# The release PR body must carry the keywords instead.
#
# Usage: ./scripts/release_closing_keywords.sh [base-ref]
#   base-ref defaults to origin/main (the last release point).
# Output: one "Closes #N" line per fixed issue, sorted numerically.

set -euo pipefail

BASE="${1:-origin/main}"
# Use the full remote-tracking ref: a local branch named "origin/develop"
# exists in some checkouts and shadows the short name.
DEVELOP_REF="refs/remotes/origin/develop"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

git fetch -q origin main develop 2>/dev/null || true

declare -A ISSUES=()
declare -A PR_NUMS=()

# Squash-merge commit messages on develop since the base look like:
#   "fix: ... (#139) (#142)"             → issue #139, PR #142
#   "fix: ... (#133, #135, #136) (#137)" → issues #133/#135/#136, PR #137
#   "fix: ... (issues #107, #94) (#109)" → issues #107/#94, PR #109
# The PR number is always the LAST (#N); everything before it is an issue.
while IFS= read -r subject; do
  [ -z "$subject" ] && continue
  mapfile -t groups < <(printf '%s' "$subject" | grep -oE '\(#[0-9]+(, #[0-9]+)*\)' || true)
  [ "${#groups[@]}" -eq 0 ] && continue
  last_idx=$((${#groups[@]} - 1))
  # Record the PR number (last group) for the body fallback below.
  while IFS= read -r n; do
    [ -z "$n" ] && continue
    PR_NUMS["$n"]=1
  done < <(printf '%s' "${groups[$last_idx]}" | grep -oE '[0-9]+' || true)
  # All earlier groups are issue numbers.
  unset "groups[$last_idx]"
  for g in "${groups[@]}"; do
    while IFS= read -r n; do
      [ -z "$n" ] && continue
      ISSUES["$n"]=1
    done < <(printf '%s' "$g" | grep -oE '[0-9]+' || true)
  done
  # Also catch "issue #N" / "issues #N, #M" phrasing without parens.
  while IFS= read -r n; do
    [ -z "$n" ] && continue
    ISSUES["$n"]=1
  done < <(printf '%s' "$subject" | grep -oiE 'issues? #[0-9]+(, #[0-9]+)*' \
             | grep -oE '[0-9]+' || true)
done < <(git log --format=%s "$BASE".."$DEVELOP_REF" 2>/dev/null || true)

# Fallback: for PRs whose commit message lacks the issue number (e.g. PR #75),
# pull "Closes #N" from the PR body. One gh call for all PRs.
#
# Exclusion rule: a referenced number is skipped ONLY if it is a genuine PR
# number taken from the gh API response. The heuristic PR_NUMS above guesses
# PR numbers from squash-message suffixes; a custom squash message can leave
# an issue number in the last (#N) group, and excluding on that guess would
# silently drop a legitimate issue from the release notes. The API never lies.
if [ "${#PR_NUMS[@]}" -gt 0 ]; then
  pr_data="$(gh pr list --state merged --base develop --limit 200 \
               --json number,body \
               --jq '.[] | "\(.number)\t\(.body | gsub("\n"; " "))"' 2>/dev/null || true)"
  # Pass 1: authoritative PR numbers from the API.
  declare -A API_PRS=()
  while IFS=$'\t' read -r pr_num _rest; do
    [ -n "$pr_num" ] && API_PRS["$pr_num"]=1
  done <<< "$pr_data"
  # Pass 2: pull closing keywords from the bodies of in-range PRs.
  while IFS=$'\t' read -r pr_num body; do
    [ -z "$pr_num" ] && continue
    [ -z "${PR_NUMS[$pr_num]:-}" ] && continue
    while IFS= read -r n; do
      [ -z "$n" ] && continue
      # Skip genuine PR numbers (this covers the PR's own number too):
      # "Closes #N" can only ever close an issue, never a PR.
      [ -n "${API_PRS[$n]:-}" ] && continue
      ISSUES["$n"]=1
    done < <(printf '%s' "$body" | grep -oiE '(close[sd]?|fix(e[sd])?|resolve[sd]?) #[0-9]+' \
               | grep -oE '[0-9]+' || true)
  done <<< "$pr_data"
fi

if [ "${#ISSUES[@]}" -eq 0 ]; then
  echo "No fixed issues found since $BASE." >&2
  exit 1
fi

for n in $(printf '%s\n' "${!ISSUES[@]}" | sort -n); do
  echo "Closes #$n"
done
