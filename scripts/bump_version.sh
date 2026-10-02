#!/usr/bin/env bash
# bump_version.sh — bump the app version and generate the release task.
#
# Usage: ./scripts/bump_version.sh <new-version>
#   e.g. ./scripts/bump_version.sh 1.8.0
#
# What it does:
#   1. Validates the version (semver X.Y.Z).
#   2. Aborts if the working tree is dirty (it switches branches).
#   3. Cuts branch chore/version-<v> from refs/remotes/origin/develop.
#   4. Updates the single source of truth: core/version.py
#      (build/packaging scripts resolve it dynamically — nothing else to edit).
#   5. Writes scripts/tasks/release-<v>.md: the release task with the steps
#      for this version. The full release rule lives in ADO; the template
#      points there instead of duplicating it.
#
# The generated task file is then used to create the tracked release task
# (Goals tab), which carries the work from PR to published DMG.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

die() { echo "error: $*" >&2; exit 1; }

VERSION="${1:-}"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] \
  || die "usage: $0 <new-version>   (semver X.Y.Z, e.g. 1.8.0)"

[ -f core/version.py ] || die "core/version.py not found — run from the repo root"

CURRENT="$(sed -n -E 's/^__version__[[:space:]]*=[[:space:]]*["'"'"']([^"'"'"']+)["'"'"'].*/\1/p' core/version.py)"
[ -n "$CURRENT" ] || die "could not read current version from core/version.py"
[ "$CURRENT" = "$VERSION" ] && die "already at $VERSION — nothing to do"

[ -z "$(git status --porcelain | grep -v '^??')" ] \
  || die "working tree has uncommitted changes to tracked files — commit or stash first (this script switches branches)"

BRANCH="chore/version-${VERSION}"
git fetch -q origin develop 2>/dev/null || true
git checkout -q -B "$BRANCH" refs/remotes/origin/develop
echo "branch: $BRANCH (from refs/remotes/origin/develop)"

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

TASK_DIR="scripts/tasks"
mkdir -p "$TASK_DIR"
TASK_FILE="${TASK_DIR}/release-${VERSION}.md"
DATE="$(date -u +%Y-%m-%d)"
cat > "$TASK_FILE" <<EOF
# Release $VERSION — release task

Generated $DATE by scripts/bump_version.sh.
Full release rule lives in ADO (version release process) — this file only
carries the per-version state and the checklist.

State: version bumped $CURRENT -> $VERSION in core/version.py
on branch $BRANCH (cut from refs/remotes/origin/develop, not yet pushed).

## Do
1. Push $BRANCH and open PR → develop (body follows repo convention).
2. Evaluate the "code completed" labeling automation in this PR: after the
   merge, confirm the workflow tags the PR and every open issue it
   references. If it still doesn't fire, fix the workflow first.
3. Verify mergeable/clean → squash-merge into develop → delete the branch.
4. Release PR develop → main with Closes keywords
   (scripts/release_closing_keywords.sh), true-merge.
5. Tag v$VERSION; confirm Actions builds Hindi-Reel-Studio-v$VERSION-macOS.dmg;
   publish the GitHub release; share via Telegram.
EOF

echo "task template: $TASK_FILE"
echo "next: use $TASK_FILE to create the tracked release task."
