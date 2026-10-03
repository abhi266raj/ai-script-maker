#!/usr/bin/env bash
# Usage: ./resolve_comment <pr-number> [reply-message]
#        ./resolve_comment <thread-id>
# Resolves GitHub PR review comment threads via GitHub CLI / GraphQL.
set -euo pipefail

command -v gh >/dev/null 2>&1 || { echo "ERROR: gh CLI not installed." >&2; exit 1; }

if [ "$#" -lt 1 ]; then
    echo "ERROR: Missing argument. Usage: $0 <pr-number> [reply-message] OR $0 <thread-id>" >&2
    exit 1
fi

TARGET="$1"
REPLY_MSG="${2:-}"

# Direct resolution by Thread ID
if [[ "$TARGET" =~ ^PRRT_ ]]; then
    gh api graphql -f query='
    mutation($threadId: ID!) {
      resolveReviewThread(input: {threadId: $threadId}) { thread { id isResolved } }
    }' -F threadId="$TARGET" >/dev/null
    echo "Review thread $TARGET resolved."
    exit 0
fi

# PR Number resolution
if [[ ! "$TARGET" =~ ^[0-9]+$ ]]; then
    echo "ERROR: Target must be a numeric PR number or thread ID (PRRT_...)." >&2
    exit 1
fi

REPO_INFO="$(gh repo view --json owner,name --jq '.owner.login + " " + .name')"
OWNER="$(echo "$REPO_INFO" | cut -d' ' -f1)"
REPO="$(echo "$REPO_INFO" | cut -d' ' -f2)"

THREADS_JSON="$(gh api graphql -f query='
query($owner: String!, $repo: String!, $pr: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviewThreads(first: 50) {
        nodes {
          id
          isResolved
        }
      }
    }
  }
}' -F owner="$OWNER" -F repo="$REPO" -F pr="$TARGET")"

UNRESOLVED="$(echo "$THREADS_JSON" | jq -r '.data.repository.pullRequest.reviewThreads.nodes[]? | select(.isResolved == false) | .id')"

if [ -z "$UNRESOLVED" ]; then
    echo "No unresolved review threads on PR #$TARGET."
    exit 0
fi

for TID in $UNRESOLVED; do
    if [ -n "$REPLY_MSG" ]; then
        gh api graphql -f query='
        mutation($threadId: ID!, $body: String!) {
          addPullRequestReviewThreadReply(input: {pullRequestReviewThreadId: $threadId, body: $body}) {
            comment { id }
          }
        }' -F threadId="$TID" -F body="$REPLY_MSG" >/dev/null 2>&1 || true
    fi
    gh api graphql -f query='
    mutation($threadId: ID!) {
      resolveReviewThread(input: {threadId: $threadId}) { thread { id isResolved } }
    }' -F threadId="$TID" >/dev/null
    echo "Resolved review thread $TID on PR #$TARGET."
done
