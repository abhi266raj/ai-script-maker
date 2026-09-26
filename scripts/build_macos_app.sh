#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# build_macos_app.sh — Hindi Reel Studio macOS app compiler & packager
# ──────────────────────────────────────────────────────────────────────
# Usage:
#   ./scripts/build_macos_app.sh            # Interactive — asks dev or release
#   ./scripts/build_macos_app.sh --dev      # Build DEV variant directly
#   ./scripts/build_macos_app.sh --release  # Build RELEASE variant directly
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VERSION="1.3.0"

cd "$PROJECT_DIR"

# ─── Determine variant ───────────────────────────────────────────────
choose_variant() {
    echo ""
    echo "┌─────────────────────────────────────┐"
    echo "│   Hindi Reel Studio — Build Menu     │"
    echo "├─────────────────────────────────────┤"
    echo "│  1)  🛠️  DEV     build               │"
    echo "│  2)  📦 RELEASE build               │"
    echo "└─────────────────────────────────────┘"
    echo ""
    read -rp "Choose variant [1/2]: " choice
    case "$choice" in
        1|dev|DEV|d|D)     DEV_MODE=true  ;;
        2|release|RELEASE|r|R) DEV_MODE=false ;;
        *)
            echo "❌ Invalid choice. Please enter 1 (DEV) or 2 (RELEASE)."
            exit 1
            ;;
    esac
}

DEV_MODE=""
case "${1:-}" in
    --dev)     DEV_MODE=true  ;;
    --release) DEV_MODE=false ;;
    "")        choose_variant ;;
    *)
        echo "Usage: $0 [--dev | --release]"
        exit 1
        ;;
esac

# ─── Configure variant-specific values ───────────────────────────────
if $DEV_MODE; then
    APP_NAME="Hindi Reel Studio DEV"
    IDENTIFIER="com.hindireel.studio.dev"
    DMG_NAME="Hindi-Reel-Studio-DEV-v${VERSION}-macOS.dmg"
    ICON_SRC="AppIcon-Dev.icns"
    SERVER_PORT="8502"
    TEMPLATE_APP="Hindi Reel Studio DEV.app"
    echo ""
    echo "🛠️  Building DEV variant"
    echo "   Bundle ID:  ${IDENTIFIER}"
    echo "   Port:       ${SERVER_PORT}"
else
    APP_NAME="Hindi Reel Studio"
    IDENTIFIER="com.hindireel.studio"
    DMG_NAME="Hindi-Reel-Studio-v${VERSION}-macOS.dmg"
    ICON_SRC="Hindi Reel Studio.app/Contents/Resources/AppIcon.icns"
    SERVER_PORT="8501"
    TEMPLATE_APP="Hindi Reel Studio.app"
    echo ""
    echo "📦 Building RELEASE variant"
    echo "   Bundle ID:  ${IDENTIFIER}"
    echo "   Port:       ${SERVER_PORT}"
fi
echo ""

# ─── Phase 1: Verify tools ──────────────────────────────────────────
echo "━━━ 1/4  VERIFY — checking build tools ━━━"
command -v python3  >/dev/null 2>&1 || { echo "❌ python3 not found"; exit 1; }
command -v swiftc   >/dev/null 2>&1 || { echo "❌ swiftc not found (install Xcode CLI tools)"; exit 1; }
echo "✅ python3 found: $(python3 --version 2>&1)"
echo "✅ swiftc  found: $(swiftc --version 2>&1 | head -1)"

# ─── Phase 2: Compile Swift ─────────────────────────────────────────
echo ""
echo "━━━ 2/4  COMPILE — building native app_runner ━━━"

# Compile StudioWindow.swift → app_runner binary
swiftc -O \
    -o "${TEMPLATE_APP}/Contents/MacOS/app_runner" \
    macos/StudioWindow.swift \
    -framework Cocoa -framework WebKit

echo "✅ app_runner compiled ($(file "${TEMPLATE_APP}/Contents/MacOS/app_runner" | grep -o 'arm64\|x86_64' | tr '\n' '+' | sed 's/+$//'))"

# ─── Phase 3: Update bundle metadata ────────────────────────────────
echo ""
echo "━━━ 3/4  METADATA — updating bundle identity ━━━"

# Update Info.plist
/usr/libexec/PlistBuddy \
    -c "Set CFBundleIdentifier '${IDENTIFIER}'" \
    -c "Set CFBundleName '${APP_NAME}'" \
    -c "Set CFBundleDisplayName '${APP_NAME}'" \
    -c "Set CFBundleShortVersionString '${VERSION}'" \
    -c "Set CFBundleVersion '${VERSION}'" \
    "${TEMPLATE_APP}/Contents/Info.plist"

# Copy correct icon (skip if same file)
if [ "$(realpath "${ICON_SRC}" 2>/dev/null)" != "$(realpath "${TEMPLATE_APP}/Contents/Resources/AppIcon.icns" 2>/dev/null)" ]; then
    cp "${ICON_SRC}" "${TEMPLATE_APP}/Contents/Resources/AppIcon.icns"
fi

# Generate DEV icon if needed and not present
if $DEV_MODE && [ ! -f "AppIcon-Dev.icns" ]; then
    echo "   Generating DEV icon..."
    .venv/bin/python3 scripts/generate_dev_icon.py
fi

# Ad-hoc code sign
codesign --force --deep -s - "${TEMPLATE_APP}"

echo "✅ ${APP_NAME}"
echo "   Identifier:  ${IDENTIFIER}"
echo "   Version:      ${VERSION}"
echo "   Icon:         ${ICON_SRC}"
echo "   Signed:       ad-hoc ✓"

# ─── Phase 4: Verify ────────────────────────────────────────────────
echo ""
echo "━━━ 4/4  VERIFY — validating bundle ━━━"

# Validate plist
plutil -lint "${TEMPLATE_APP}/Contents/Info.plist" >/dev/null
echo "✅ Info.plist valid"

# Verify identity
BUILT_ID=$(/usr/libexec/PlistBuddy -c "Print CFBundleIdentifier" "${TEMPLATE_APP}/Contents/Info.plist")
BUILT_NAME=$(/usr/libexec/PlistBuddy -c "Print CFBundleDisplayName" "${TEMPLATE_APP}/Contents/Info.plist")
BUILT_VER=$(/usr/libexec/PlistBuddy -c "Print CFBundleVersion" "${TEMPLATE_APP}/Contents/Info.plist")

echo "✅ Bundle ID:   ${BUILT_ID}"
echo "✅ Display Name: ${BUILT_NAME}"
echo "✅ Version:      ${BUILT_VER}"

# ─── Done ────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ BUILD COMPLETE"
echo ""
echo "📦 App:  ${TEMPLATE_APP}"
ls -lhd "${TEMPLATE_APP}"
echo ""
echo "🚀 To launch:  open \"${TEMPLATE_APP}\""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
