#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# publish_release.sh — Idempotent GitHub release publisher
# ──────────────────────────────────────────────────────────────────────
# Creates the GitHub release for a version (if missing) and uploads the
# release DMG asset (if missing). Safe to re-run: every step checks the
# current state first and reports "already done" instead of duplicating work.
#
# Runs on macOS and Linux (pure bash + gh CLI, no macOS-only tools).
# Requires: bash, gh (authenticated with repo write access).
#
# Usage:
#   ./scripts/publish_release.sh [--version X.Y.Z] [--dmg PATH]
#       [--notes-file PATH] [--publish] [--dry-run] [--repo OWNER/REPO]
#
# Examples:
#   ./scripts/publish_release.sh --version 1.5.4 \
#       --dmg dist/v1.5.4/Hindi-Reel-Studio-v1.5.4-macOS.dmg \
#       --notes-file /tmp/v154-notes.md
#   ./scripts/publish_release.sh --dry-run        # version + dmg auto-detected
#   ./scripts/publish_release.sh --publish        # also flip draft -> published
#
# Rules (fail loudly, never invent):
#   - Tag vX.Y.Z must already exist on the remote. This script NEVER creates
#     tags or bumps versions (repo rule: the bump lands via PR and the tag
#     points at the bump commit).
#   - A missing release is created as a DRAFT; --notes-file is required then.
#   - An asset with the same name but a different byte size aborts loudly.
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

REPO="abhi266raj/ai-script-maker"
VERSION=""
DMG_PATH=""
NOTES_FILE=""
PUBLISH=false
DRY_RUN=false

usage() {
  sed -n '2,/^# ─*$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

info() {
  echo "--> $*"
}

# Print the command in dry-run mode, execute it otherwise.
run() {
  if [ "$DRY_RUN" = true ]; then
    echo "[dry-run] would run: $*"
  else
    "$@"
  fi
}

# ─── Parse arguments ───────────────────────────────────────────────────
while [ $# -gt 0 ]; do
  case "$1" in
    --version)    VERSION="$2"; shift 2 ;;
    --dmg)        DMG_PATH="$2"; shift 2 ;;
    --notes-file) NOTES_FILE="$2"; shift 2 ;;
    --repo)       REPO="$2"; shift 2 ;;
    --publish)    PUBLISH=true; shift ;;
    --dry-run)    DRY_RUN=true; shift ;;
    -h|--help)    usage; exit 0 ;;
    *)            die "unknown argument: $1 (see --help)" ;;
  esac
done

# ─── 0. gh present and authenticated ───────────────────────────────────
command -v gh >/dev/null 2>&1 || die "gh CLI not found in PATH. Install it: https://cli.github.com/"
gh auth status --hostname github.com >/dev/null 2>&1 \
  || die "gh is not authenticated. Run: gh auth login"

# ─── 1. --repo must match this checkout's origin ───────────────────────
ORIGIN_URL="$(git -C "$PROJECT_DIR" config --get remote.origin.url 2>/dev/null || true)"
[ -n "$ORIGIN_URL" ] || die "no git remote 'origin' in $PROJECT_DIR"

normalize_remote() {
  local url="$1"
  url="${url%.git}"
  url="${url#https://github.com/}"
  url="${url#http://github.com/}"
  url="${url#git@github.com:}"
  url="${url#ssh://git@github.com/}"
  printf '%s' "$url"
}

ORIGIN_NORM="$(normalize_remote "$ORIGIN_URL")"
[ "$ORIGIN_NORM" = "$REPO" ] \
  || die "remote origin ($ORIGIN_URL) does not match --repo $REPO. Refusing to publish to the wrong repository."

# ─── Resolve version ──────────────────────────────────────────────────
if [ -z "$VERSION" ]; then
  VERSION="$(sed -n -E 's/^__version__[[:space:]]*=[[:space:]]*['"'"'\"]([^'"'"'\"]+)['"'"'\"].*/\1/p' \
    "$PROJECT_DIR/core/version.py" | head -n 1)"
  [ -n "$VERSION" ] || die "could not read __version__ from $PROJECT_DIR/core/version.py"
  info "version auto-detected from core/version.py: $VERSION"
fi
case "$VERSION" in
  [0-9]*.[0-9]*.[0-9]*) ;;
  *) die "--version must look like X.Y.Z, got: $VERSION" ;;
esac
TAG="v$VERSION"
TITLE="Hindi Reel Studio $VERSION (macOS Standalone)"

# ─── Resolve DMG ──────────────────────────────────────────────────────
DMG_NAME="Hindi-Reel-Studio-v${VERSION}-macOS.dmg"
if [ -z "$DMG_PATH" ]; then
  info "looking for $DMG_NAME under $PROJECT_DIR/dist ..."
  MATCHES="$(find "$PROJECT_DIR/dist" -maxdepth 3 -type f -name "$DMG_NAME" 2>/dev/null || true)"
  COUNT="$(printf '%s\n' "$MATCHES" | grep -c '[^[:space:]]' || true)"
  [ "$COUNT" -eq 1 ] || die "expected exactly 1 DMG named $DMG_NAME under dist/, found $COUNT. Pass --dmg explicitly."
  DMG_PATH="$MATCHES"
  info "DMG auto-detected: $DMG_PATH"
fi
[ -f "$DMG_PATH" ] || die "DMG not found: $DMG_PATH"
DMG_BASENAME="$(basename "$DMG_PATH")"
# gh uploads under the file's local basename, so enforce the canonical name
# to keep release assets consistent.
[ "$DMG_BASENAME" = "$DMG_NAME" ] \
  || die "DMG basename must be $DMG_NAME, got: $DMG_BASENAME. Rename the file first (gh release upload keeps the local basename)."
# wc -c is portable across macOS and Linux (stat flags differ).
DMG_SIZE="$(wc -c < "$DMG_PATH" | tr -d '[:space:]')"

info "repo=$REPO tag=$TAG title=\"$TITLE\""
info "dmg=$DMG_PATH ($DMG_SIZE bytes) dry_run=$DRY_RUN publish=$PUBLISH"

# ─── 2. Tag must already exist on the remote ───────────────────────────
info "checking tag $TAG exists on remote ..."
TAG_LINE="$(git -C "$PROJECT_DIR" ls-remote --tags origin "refs/tags/$TAG" 2>/dev/null \
  | grep -E "refs/tags/$TAG\$" || true)"
[ -n "$TAG_LINE" ] || die "tag $TAG does not exist on remote 'origin'. This script never creates tags: land the version bump via PR and tag the bump commit first (see repo release rule)."

# ─── 3. Release: create as draft if missing ────────────────────────────
if gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
  info "release $TAG already exists."
  RELEASE_CREATED=false
else
  info "release $TAG does not exist — will create it as a draft."
  [ -n "$NOTES_FILE" ] \
    || die "release $TAG does not exist and --notes-file was not given. Refusing to invent release notes."
  [ -f "$NOTES_FILE" ] \
    || die "notes file not found: $NOTES_FILE"
  run gh release create "$TAG" --repo "$REPO" --title "$TITLE" \
    --notes-file "$NOTES_FILE" --draft
  RELEASE_CREATED=true
fi

# ─── 4. Asset: upload if missing ───────────────────────────────────────
REMOTE_SIZE="$(gh release view "$TAG" --repo "$REPO" --json assets \
  --jq ".assets[] | select(.name == \"$DMG_BASENAME\") | .size" 2>/dev/null || true)"

if [ -n "$REMOTE_SIZE" ]; then
  if [ "$REMOTE_SIZE" = "$DMG_SIZE" ]; then
    info "asset $DMG_BASENAME already uploaded ($DMG_SIZE bytes) — nothing to do."
  else
    MSG="asset $DMG_BASENAME already exists on release $TAG with a DIFFERENT size (remote: $REMOTE_SIZE bytes, local: $DMG_SIZE bytes). Refusing to overwrite. Delete the bad asset first: gh release delete-asset $TAG \"$DMG_BASENAME\" --repo $REPO"
    if [ "$DRY_RUN" = true ]; then
      echo "[dry-run] would abort: $MSG"
    else
      die "$MSG"
    fi
  fi
else
  info "asset $DMG_BASENAME not on release $TAG — uploading."
  run gh release upload "$TAG" "$DMG_PATH" --repo "$REPO"
fi

# ─── 5. Publish if asked ───────────────────────────────────────────────
if [ "$PUBLISH" = true ]; then
  info "publishing release $TAG (draft -> published)."
  run gh release edit "$TAG" --repo "$REPO" --draft=false
fi

if [ "$RELEASE_CREATED" = true ] && [ "$DRY_RUN" = false ]; then
  info "done: release $TAG created (draft) and asset uploaded."
elif [ "$DRY_RUN" = true ]; then
  info "dry-run complete — nothing was changed."
else
  info "done."
fi
