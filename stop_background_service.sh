#!/usr/bin/env bash
# Unregisters the background daemon

PLIST_PATH="${HOME}/Library/LaunchAgents/com.hindireel.studio.plist"

if [ -f "${PLIST_PATH}" ]; then
    launchctl unload "${PLIST_PATH}" >/dev/null 2>&1
    rm -f "${PLIST_PATH}"
    echo "🛑 Background service stopped and removed."
else
    echo "No background service found."
fi

# Kill any running streamlit instance
pkill -f "streamlit run app.py" >/dev/null 2>&1 || true
echo "Streamlit server process terminated."
