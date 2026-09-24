#!/usr/bin/env bash
# Native Desktop Web App Launcher for Hindi Reel Studio

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

PORT=8501
HOST="127.0.0.1"
URL="http://${HOST}:${PORT}"
LOG_FILE="${DIR}/.server.log"

FP_FILE="${DIR}/.server.fingerprint"
PID_FILE="${DIR}/.server.pid"

is_server_running() {
    curl -s --connect-timeout 1 "${URL}/" > /dev/null 2>&1
}

# Fingerprint of the app code: all .py files + prompt templates (*.md under
# prompts/). Excludes the venv, git metadata and caches. If the code changed
# since the server was started, the running server is stale and must restart
# — otherwise the browser keeps showing the OLD version of the app.
code_fingerprint() {
    {
        find "${DIR}" \( -path "${DIR}/.venv" -o -path "${DIR}/.git" -o -name '__pycache__' \) -prune -o \
            -name '*.py' -print0 2>/dev/null | xargs -0 stat -f '%m %N' 2>/dev/null
        find "${DIR}/prompts" -name '*.md' -print0 2>/dev/null | xargs -0 stat -f '%m %N' 2>/dev/null
    } | md5 2>/dev/null
}

# Stale when the code changed since server start — or when we have no record
# of what the server started with (first run of this launcher version).
server_is_stale() {
    [ -f "${FP_FILE}" ] || return 0
    _old_fp="$(cat "${FP_FILE}" 2>/dev/null)"
    [ -n "${_old_fp}" ] || return 0
    _new_fp="$(code_fingerprint)"
    [ -n "${_new_fp}" ] || return 1
    [ "${_old_fp}" != "${_new_fp}" ]
}

stop_server() {
    if [ -f "${PID_FILE}" ]; then
        kill "$(cat "${PID_FILE}" 2>/dev/null)" 2>/dev/null
    fi
    pkill -f "[s]treamlit run" 2>/dev/null
    # Wait until the port is actually free before starting a new server.
    for _i in $(seq 1 10); do
        is_server_running || break
        sleep 0.5
    done
}

start_server() {
    echo "🍏 Starting Hindi Reel Studio Server on ${URL}..."
    nohup "${DIR}/.venv/bin/streamlit" run "${DIR}/app.py" \
        --server.headless true \
        --server.address "${HOST}" \
        --server.port ${PORT} < /dev/null > "${LOG_FILE}" 2>&1 &
    echo $! > "${PID_FILE}"
    code_fingerprint > "${FP_FILE}" 2>/dev/null

    for i in {1..16}; do
        if is_server_running; then
            echo "✅ Server online!"
            break
        fi
        sleep 0.5
    done
}

if is_server_running; then
    if server_is_stale; then
        echo "🔄 App code changed since the server started — restarting to load the latest version..."
        stop_server
        start_server
    else
        echo "✅ Server already running with the latest code."
    fi
else
    # Auto-start server in background if not already alive
    start_server
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
