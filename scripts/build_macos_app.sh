#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# build_macos_app.sh — Hindi Reel Studio Standalone App & DMG Packager
# ──────────────────────────────────────────────────────────────────────
# Full standalone packaging with PyInstaller freeze + Cocoa WKWebView
# native window + DMG installer creation.
#
# Usage:
#   ./scripts/build_macos_app.sh            # Interactive menu (Dev or Release)
#   ./scripts/build_macos_app.sh --dev      # Build DEV variant directly
#   ./scripts/build_macos_app.sh --release  # Build RELEASE variant directly
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VERSION="1.3.0"

cd "$PROJECT_DIR"

# ─── Determine variant ───────────────────────────────────────────────
ENABLE_IPV4=false
DEV_MODE=""

for arg in "$@"; do
    case "$arg" in
        --dev)     DEV_MODE=true ;;
        --release) DEV_MODE=false ;;
        --ipv4)    ENABLE_IPV4=true ;;
        --ipv6)    ENABLE_IPV4=false ;;
        -h|--help)
            echo "Usage: $0 [--dev | --release] [--ipv4 | --ipv6]"
            exit 0
            ;;
    esac
done

choose_variant() {
    echo ""
    echo "┌────────────────────────────────────────────────────────┐"
    echo "│         Hindi Reel Studio — Build Menu                 │"
    echo "├────────────────────────────────────────────────────────┤"
    echo "│  1)  🛠️  DEV     standalone (IPv6 ::1 loopback)        │"
    echo "│  2)  🛠️  DEV     standalone (IPv4 127.0.0.1 fallback)  │"
    echo "│  3)  📦 RELEASE standalone (IPv6 ::1 loopback)        │"
    echo "│  4)  📦 RELEASE standalone (IPv4 127.0.0.1 fallback)  │"
    echo "└────────────────────────────────────────────────────────┘"
    echo ""
    read -rp "Choose option [1-4]: " choice
    case "$choice" in
        1|dev|DEV|d|D)             DEV_MODE=true;  ENABLE_IPV4=false ;;
        2|dev-ipv4|DEV-IPV4)       DEV_MODE=true;  ENABLE_IPV4=true  ;;
        3|release|RELEASE|r|R)     DEV_MODE=false; ENABLE_IPV4=false ;;
        4|release-ipv4|REL-IPV4)   DEV_MODE=false; ENABLE_IPV4=true  ;;
        *)
            echo "❌ Invalid choice. Please enter 1, 2, 3, or 4."
            exit 1
            ;;
    esac
}

if [ -z "$DEV_MODE" ]; then
    choose_variant
fi

if $ENABLE_IPV4; then
    SERVER_HOST="127.0.0.1"
else
    SERVER_HOST="::"
fi

# ─── Configure variant-specific values ───────────────────────────────
if $DEV_MODE; then
    APP_NAME="Hindi Reel Studio DEV"
    IDENTIFIER="com.hindireel.studio.dev"
    DMG_NAME="Hindi-Reel-Studio-DEV-v${VERSION}-macOS.dmg"
    ICON_SRC="AppIcon-Dev.icns"
    SERVER_PORT=8502
    echo "🛠️  Target: DEV variant"
    echo "   Bundle ID:  ${IDENTIFIER}"
    echo "   Port:       ${SERVER_PORT}"
    echo "   Host:       ${SERVER_HOST}"
    echo "   App Name:   ${APP_NAME}.app"
    echo "   DMG Name:   ${DMG_NAME}"
else
    APP_NAME="Hindi Reel Studio"
    IDENTIFIER="com.hindireel.studio"
    DMG_NAME="Hindi-Reel-Studio-v${VERSION}-macOS.dmg"
    ICON_SRC="AppIcon.icns"
    SERVER_PORT=8501
    echo "📦 Target: RELEASE variant"
    echo "   Bundle ID:  ${IDENTIFIER}"
    echo "   Port:       ${SERVER_PORT}"
    echo "   Host:       ${SERVER_HOST}"
    echo "   App Name:   ${APP_NAME}.app"
    echo "   DMG Name:   ${DMG_NAME}"
fi
echo ""

APP_BUNDLE="dist/${APP_NAME}.app"

# ─── Phase 1: Verify tools & environment ─────────────────────────────
echo "━━━ 1/5  VERIFY — checking build tools & dependencies ━━━"
command -v python3 >/dev/null 2>&1 || { echo "❌ python3 not found"; exit 1; }
command -v swiftc  >/dev/null 2>&1 || { echo "❌ swiftc not found (install Xcode CLI tools: xcode-select --install)"; exit 1; }

PYTHON_EXEC=".venv/bin/python3"
PIP_EXEC=".venv/bin/pip"

if [ ! -x "$PYTHON_EXEC" ]; then
    echo "⚠️  .venv not found. Creating virtualenv..."
    python3 -m venv .venv
    "$PIP_EXEC" install --upgrade pip
    "$PIP_EXEC" install -r requirements.txt
fi

if ! "$PYTHON_EXEC" -c "import PyInstaller" 2>/dev/null; then
    echo "📦 Installing PyInstaller in .venv..."
    "$PIP_EXEC" install pyinstaller
fi

if ! "$PYTHON_EXEC" -c "from PIL import Image" 2>/dev/null; then
    echo "📦 Installing Pillow in .venv..."
    "$PIP_EXEC" install pillow
fi

echo "✅ Python:    $("$PYTHON_EXEC" --version 2>&1)"
echo "✅ Swift:     $(swiftc --version 2>&1 | head -1)"
echo "✅ Tooling:   PyInstaller & Pillow available"

# ─── Phase 2: Ensure Icon Assets ─────────────────────────────────────
echo ""
echo "━━━ 2/5  ICONS — preparing app icon ━━━"
if [ ! -f "AppIcon.icns" ]; then
    if [ -d "AppIcon.iconset" ]; then
        echo "   Generating AppIcon.icns from AppIcon.iconset..."
        iconutil -c icns AppIcon.iconset -o AppIcon.icns
    elif [ -f "Hindi Reel Studio.app/Contents/Resources/AppIcon.icns" ]; then
        cp "Hindi Reel Studio.app/Contents/Resources/AppIcon.icns" AppIcon.icns
    fi
fi

if $DEV_MODE; then
    if [ ! -f "AppIcon-Dev.icns" ]; then
        echo "   Generating AppIcon-Dev.icns with DEV banner..."
        "$PYTHON_EXEC" scripts/generate_dev_icon.py
    fi
    ACTUAL_ICON="AppIcon-Dev.icns"
else
    ACTUAL_ICON="AppIcon.icns"
fi
echo "✅ Using icon: ${ACTUAL_ICON}"

# ─── Phase 3: PyInstaller Freeze ─────────────────────────────────────
echo ""
echo "━━━ 3/5  FREEZE — freezing runtime via PyInstaller ━━━"
# We freeze into dist/run_standalone directory
rm -rf build/run_standalone dist/run_standalone

"$PYTHON_EXEC" -m PyInstaller \
    --noconfirm \
    --onedir \
    --name run_standalone \
    --add-data "prompts:prompts" \
    --add-data "core:core" \
    --add-data "agents:agents" \
    --add-data "tools:tools" \
    --add-data ".streamlit:_streamlit" \
    --add-data "app.py:." \
    --collect-all streamlit \
    --copy-metadata streamlit \
    --hidden-import streamlit \
    --hidden-import pydantic \
    --hidden-import httpx \
    --hidden-import feedparser \
    --hidden-import bs4 \
    scripts/run_standalone.py

if [ ! -x "dist/run_standalone/run_standalone" ]; then
    echo "❌ PyInstaller freeze failed: executable not found"
    exit 1
fi
echo "✅ PyInstaller standalone runtime built successfully"

# ─── Phase 4: Assemble & Sign macOS .app Bundle ──────────────────────
echo ""
echo "━━━ 4/5  ASSEMBLE — constructing ${APP_NAME}.app ━━━"
rm -rf "${APP_BUNDLE}"
mkdir -p "${APP_BUNDLE}/Contents/MacOS"
mkdir -p "${APP_BUNDLE}/Contents/Resources"

# 1. Copy frozen runtime into Contents/Resources/runtime
echo "   Copying standalone runtime into app bundle..."
cp -R "dist/run_standalone" "${APP_BUNDLE}/Contents/Resources/runtime"

# 2. Compile native Cocoa/WKWebView runner
echo "   Compiling native Swift Cocoa wrapper..."
swiftc -O \
    -o "${APP_BUNDLE}/Contents/MacOS/app_runner" \
    macos/StudioWindow.swift \
    -framework Cocoa -framework WebKit

# 3. Copy Icon
cp "${ACTUAL_ICON}" "${APP_BUNDLE}/Contents/Resources/AppIcon.icns"

# 4. Generate Info.plist
cat > "${APP_BUNDLE}/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>app_runner</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon.icns</string>
    <key>CFBundleIdentifier</key>
    <string>${IDENTIFIER}</string>
    <key>CFBundleName</key>
    <string>${APP_NAME}</string>
    <key>CFBundleDisplayName</key>
    <string>${APP_NAME}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>${VERSION}</string>
    <key>CFBundleVersion</key>
    <string>${VERSION}</string>
    <key>HRSServerPort</key>
    <integer>${SERVER_PORT}</integer>
    <key>HRSServerHost</key>
    <string>${SERVER_HOST}</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSAppTransportSecurity</key>
    <dict>
        <key>NSAllowsLocalNetworking</key>
        <true/>
    </dict>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.productivity</string>
</dict>
</plist>
PLIST

# 5. Validate Info.plist
plutil -lint "${APP_BUNDLE}/Contents/Info.plist" >/dev/null

# 6. Ad-hoc code sign the entire bundle
echo "   Code signing app bundle (ad-hoc)..."
codesign --force --deep -s - "${APP_BUNDLE}"

echo "✅ App bundle assembled: ${APP_BUNDLE}"

# ─── Phase 5: Package Apple Disk Image (.dmg) ────────────────────────
echo ""
echo "━━━ 5/5  DMG — generating ${DMG_NAME} ━━━"
DMG_PATH="dist/${DMG_NAME}"
rm -f "${DMG_PATH}"

if command -v create-dmg >/dev/null 2>&1; then
    echo "   Packaging with create-dmg..."
    create-dmg \
        --volname "${APP_NAME}" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon "${APP_NAME}.app" 150 190 \
        --app-drop-link 450 190 \
        "${DMG_PATH}" \
        "${APP_BUNDLE}" >/dev/null
else
    echo "   create-dmg not found — using native macOS hdiutil..."
    STAGING_DIR="dist/dmg_staging_${SERVER_PORT}"
    rm -rf "${STAGING_DIR}"
    mkdir -p "${STAGING_DIR}"
    
    cp -R "${APP_BUNDLE}" "${STAGING_DIR}/"
    ln -s /Applications "${STAGING_DIR}/Applications"
    
    hdiutil create \
        -volname "${APP_NAME}" \
        -srcfolder "${STAGING_DIR}" \
        -ov \
        -format UDZO \
        "${DMG_PATH}" >/dev/null
        
    rm -rf "${STAGING_DIR}"
fi

echo "✅ Disk image created: ${DMG_PATH}"

# ─── Summary ─────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 BUILD COMPLETE: ${APP_NAME} (v${VERSION})"
echo ""
echo "📦 App Bundle:  ${APP_BUNDLE}"
ls -lhd "${APP_BUNDLE}"
echo ""
echo "💿 Disk Image:  ${DMG_PATH}"
ls -lh "${DMG_PATH}"
echo ""
echo "🚀 To test DMG: open \"${DMG_PATH}\""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
