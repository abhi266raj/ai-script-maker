#!/usr/bin/env bash
# Registers Hindi Reel Studio as an auto-starting macOS LaunchAgent daemon

PLIST_PATH="${HOME}/Library/LaunchAgents/com.hindireel.studio.plist"
PROJECT_DIR="/Users/abhiraj/Documents/news/agent"

mkdir -p "${HOME}/Library/LaunchAgents"

cat <<EOF > "${PLIST_PATH}"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.hindireel.studio</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PROJECT_DIR}/.venv/bin/streamlit</string>
        <string>run</string>
        <string>${PROJECT_DIR}/app.py</string>
        <string>--server.headless</string>
        <string>true</string>
        <string>--server.address</string>
        <string>127.0.0.1</string>
        <string>--server.port</string>
        <string>8501</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${PROJECT_DIR}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${PROJECT_DIR}/.server.log</string>
    <key>StandardErrorPath</key>
    <string>${PROJECT_DIR}/.server.log</string>
</dict>
</plist>
EOF

launchctl unload "${PLIST_PATH}" >/dev/null 2>&1
launchctl load "${PLIST_PATH}"

echo "✅ Hindi Reel Studio registered as an automatic background service on Mac!"
echo "Server will now automatically stay running on http://127.0.0.1:8501"
