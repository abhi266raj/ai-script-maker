#!/usr/bin/env bash
# bump_version.sh — version increase (NOT a release).
#
# Usage: ./scripts/bump_version.sh <new-version>
#   e.g. ./scripts/bump_version.sh 1.8.1
#
# Flow (guidelines/workflows/release.md — Version Increase Protocol):
#   1. Validates the version (semver X.Y.Z); aborts if already at it.
#   2. Aborts if the working tree is dirty (it switches branches).
#   3. Fetches origin; cuts branch chore/version-<v> from origin/develop
#      (i.e. pulls the latest develop).
#   4. Merges origin/main into the branch (true merge, --no-ff) so any
#      main-only commits come along with history intact. On conflict the
#      merge is aborted and the script dies loudly — resolve manually.
#   5. Bumps the single source of truth: core/version.py
#      (build/packaging scripts resolve it dynamically — nothing else to edit).
#   6. Commits the bump.
#
# Then: push, open PR → develop, and after explicit user approval merge with
# a TRUE merge (never squash): ./merge_pr <num> --merge
#
# A version increase is not a release. The release happens when develop is
# merged to main (true merge) and tagged.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

die() { echo "error: $*" >&2; exit 1; }

VERSION="${1:-}"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] \
  || die "usage: $0 <new-version>   (semver X.Y.Z, e.g. 1.8.1)"

[ -f core/version.py ] || die "core/version.py not found — run from the repo root"

CURRENT="$(sed -n -E 's/^__version__[[:space:]]*=[[:space:]]*["'"'"']([^"'"'"']+)["'"'"'].*/\1/p' core/version.py)"
[ -n "$CURRENT" ] || die "could not read current version from core/version.py"
[ "$CURRENT" = "$VERSION" ] && die "already at $VERSION — nothing to do"

[ -z "$(git status --porcelain | grep -v '^??')" ] \
  || die "working tree has uncommitted changes to tracked files — commit or stash first (this script switches branches)"

git fetch origin develop main \
  || die "could not fetch origin — check network access and retry"
git rev-parse --verify --quiet refs/remotes/origin/develop >/dev/null \
  || die "refs/remotes/origin/develop not found after fetch"
git rev-parse --verify --quiet refs/remotes/origin/main >/dev/null \
  || die "refs/remotes/origin/main not found after fetch"

BRANCH="chore/version-${VERSION}"
git checkout -q -B "$BRANCH" refs/remotes/origin/develop
echo "branch: $BRANCH (from refs/remotes/origin/develop)"

if git merge --no-ff -q -m "Merge origin/main into $BRANCH" refs/remotes/origin/main; then
  echo "merged: origin/main into $BRANCH (true merge)"
else
  git merge --abort 2>/dev/null || true
  die "origin/main conflicts with develop — merge aborted, $BRANCH left clean. Bypass: merge manually (git checkout $BRANCH && git merge --no-ff refs/remotes/origin/main), resolve, commit, then bump core/version.py to $VERSION by hand."
fi

# Portable version edit (BSD sed needs -i '', so use python3).
python3 - "$VERSION" <<'EOF'
import re, sys
v = sys.argv[1]
p = "core/version.py"
s = open(p).read()
s2 = re.sub(r'^__version__\s*=\s*".*"$', '__version__ = "%s"' % v,
            s, count=1, flags=re.M)
if s2 == s:
    sys.exit("version line not found in core/version.py")
open(p, "w").write(s2)
EOF

NEW="$(sed -n -E 's/^__version__[[:space:]]*=[[:space:]]*["'"'"']([^"'"'"']+)["'"'"'].*/\1/p' core/version.py)"
[ "$NEW" = "$VERSION" ] || die "bump failed (core/version.py still $NEW)"
echo "bumped: core/version.py $CURRENT -> $NEW"

# Sanity: downstream tooling resolves the version dynamically.
RESOLVED="$(python3 -c "import sys; sys.path.insert(0, '.'); from core.version import __version__; print(__version__)" 2>/dev/null || true)"
[ "$RESOLVED" = "$VERSION" ] && echo "verified: core.version resolves to $RESOLVED"

git add core/version.py
git commit -q -m "chore: bump version to $VERSION"
echo "committed: chore: bump version to $VERSION"

cat <<EOF
next:
  git push -u origin $BRANCH
  ./open_pr -t "chore: bump version to $VERSION" -b "## Summary
- Merge origin/main into $BRANCH (true merge)
- chore: bump version to $VERSION

Version increase, not a release." --ai Muse
  # after explicit user approval, true merge (never squash):
  ./merge_pr <pr-number> --merge
EOF
