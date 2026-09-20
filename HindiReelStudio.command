#!/usr/bin/env bash
# Native Desktop Web App Launcher for Hindi Reel Studio

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

PORT=8501
HOST="127.0.0.1"
URL="http://${HOST}:${PORT}"
LOG_FILE="${DIR}/.server.log"

is_server_running() {
    curl -s --connect-timeout 1 "${URL}/" > /dev/null 2>&1
}

# Auto-start server in background if not already alive
if ! is_server_running; then
    echo "🍏 Auto-starting Hindi Reel Studio Server on ${URL}..."
    nohup "${DIR}/.venv/bin/streamlit" run "${DIR}/app.py" \
        --server.headless true \
        --server.address "${HOST}" \
        --server.port ${PORT} < /dev/null > "${LOG_FILE}" 2>&1 &

    for i in {1..16}; do
        if is_server_running; then
            echo "✅ Server online!"
            break
        fi
        sleep 0.5
    done
fi

echo "🚀 Opening Hindi Reel Studio as a standalone desktop app..."

if [ -d "/Applications/Google Chrome.app" ]; then
    open -na "Google Chrome" --args --app="${URL}"
elif [ -d "/Applications/Brave Browser.app" ]; then
    open -na "Brave Browser" --args --app="${URL}"
elif [ -d "/Applications/Microsoft Edge.app" ]; then
    open -na "Microsoft Edge" --args --app="${URL}"
else
    open "${URL}"
fi
