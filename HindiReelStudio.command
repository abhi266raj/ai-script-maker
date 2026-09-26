#!/usr/bin/env bash
# Hindi Reel Studio — self-healing launcher (double-click to run).
#
# Every launch runs four phases:
#   1. CLEAN    — kill stuck servers, free port 8501, drop stale pid/fingerprint
#   2. VALIDATE — venv python runs, required packages import, app.py compiles
#   3. REPAIR   — rebuild the venv / reinstall deps if validation failed
#   4. LAUNCH   — start Streamlit, wait until healthy, open the app window
#
# Fast path: if the server is already healthy AND the code hasn't changed
# since it started, the launcher just opens the browser (no restart).

set -u

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

PORT=8501
HOST="127.0.0.1"
URL="http://${HOST}:${PORT}"
LOG_FILE="${DIR}/.server.log"
FP_FILE="${DIR}/.server.fingerprint"
PID_FILE="${DIR}/.server.pid"
VENV="${DIR}/.venv"
PY="${VENV}/bin/python"
PIP="${VENV}/bin/pip"
ST="${VENV}/bin/streamlit"
REQ_FILE="${DIR}/requirements.txt"

step() { echo ""; echo "━━━ $1 ━━━"; }
ok()   { echo "✅ $1"; }
warn() { echo "⚠️  $1"; }
die()  { echo ""; echo "❌ $1"; if [ -n "${2:-}" ]; then echo "$2"; fi; exit 1; }

is_server_running() {
    curl -s --connect-timeout 2 --max-time 5 "${URL}/" > /dev/null 2>&1
}

open_app() {
    if [ -d "/Applications/Google Chrome.app" ]; then
        open -na "Google Chrome" --args --app="${URL}"
    elif [ -d "/Applications/Brave Browser.app" ]; then
        open -na "Brave Browser" --args --app="${URL}"
    elif [ -d "/Applications/Microsoft Edge.app" ]; then
        open -na "Microsoft Edge" --args --app="${URL}"
    else
        open "${URL}"
    fi
}

# Fingerprint of the app code: all .py files + prompt templates (*.md under
# prompts/). Excludes the venv, git metadata and caches.
code_fingerprint() {
    {
        find "${DIR}" \( -path "${DIR}/.venv" -o -path "${DIR}/.git" -o -name '__pycache__' \) -prune -o \
            -name '*.py' -print0 2>/dev/null | xargs -0 stat -f '%m %N' 2>/dev/null
        find "${DIR}/prompts" -name '*.md' -print0 2>/dev/null | xargs -0 stat -f '%m %N' 2>/dev/null
    } | md5 2>/dev/null
}

port_holder_pids() { lsof -ti:${PORT} 2>/dev/null; }

# A crashed run can leave a stuck process on the port that answers nothing
# (health check fails) yet blocks a new server ("Port 8501 is not available").
free_port() {
    local _pids
    _pids="$(port_holder_pids)"
    if [ -n "${_pids}" ]; then
        echo "🧹 Clearing stuck process on port ${PORT}..."
        # shellcheck disable=SC2086
        kill ${_pids} 2>/dev/null
        sleep 1
        _pids="$(port_holder_pids)"
        if [ -n "${_pids}" ]; then
            # shellcheck disable=SC2086
            kill -9 ${_pids} 2>/dev/null
            sleep 0.5
        fi
    fi
}

clean_all() {
    pkill -f "[s]treamlit run" 2>/dev/null
    free_port
    rm -f "${PID_FILE}" "${FP_FILE}"
}

validate_env() {
    local bad=0 _mod
    if [ -x "${PY}" ] && "${PY}" --version >/dev/null 2>&1; then
        ok "venv python: $("${PY}" --version 2>&1)"
        for _mod in streamlit pydantic httpx feedparser bs4; do
            if "${PY}" -c "import ${_mod}" >/dev/null 2>&1; then
                ok "module '${_mod}' importable"
            else
                echo "❌ module '${_mod}' missing or broken"
                bad=1
            fi
        done
        if "${PY}" -m py_compile "${DIR}/app.py" >/dev/null 2>&1; then
            ok "app.py compiles"
        else
            echo "❌ app.py has a syntax error"
            bad=1
        fi
    else
        echo "❌ venv python missing or broken: ${PY}"
        bad=1
        if command -v python3 >/dev/null 2>&1 && python3 -m py_compile "${DIR}/app.py" >/dev/null 2>&1; then
            ok "app.py compiles (checked with system python3)"
        else
            echo "❌ app.py has a syntax error (or no python3 available to check with)"
            bad=1
        fi
    fi
    return $bad
}

repair_env() {
    echo "🔧 Validation failed — repairing the environment..."
    if [ ! -x "${PY}" ] || ! "${PY}" --version >/dev/null 2>&1; then
        echo "🔧 Recreating the virtualenv (old one removed)..."
        rm -rf "${VENV}"
        python3 -m venv "${VENV}" \
            || die "Could not create the virtualenv." "Install Xcode command line tools first:  xcode-select --install"
        ok "virtualenv recreated"
    fi
    echo "🔧 Installing dependencies — this can take a few minutes..."
    "${PIP}" install --quiet --upgrade pip 2>&1 | tail -2
    if [ -f "${REQ_FILE}" ]; then
        echo "   from ${REQ_FILE}"
        "${PIP}" install -r "${REQ_FILE}" \
            || die "Dependency install failed." "Check your internet connection, then double-click the launcher again."
    else
        warn "requirements.txt not found — installing core packages"
        "${PIP}" install streamlit pydantic httpx feedparser beautifulsoup4 \
            || die "Dependency install failed." "Check your internet connection, then double-click the launcher again."
    fi
    echo "🔧 Re-validating..."
    validate_env \
        || die "Repair finished but the environment is still broken." "Please send the full output above to your assistant."
    ok "environment repaired"
}

start_server() {
    echo "🍏 Starting the Hindi Reel Studio server on ${URL}..."
    nohup "${ST}" run "${DIR}/app.py" \
        --server.headless true \
        --server.address "${HOST}" \
        --server.port ${PORT} < /dev/null > "${LOG_FILE}" 2>&1 &
    echo $! > "${PID_FILE}"
    code_fingerprint > "${FP_FILE}" 2>/dev/null

    # Cold boot can take a while (heavy imports); wait up to ~40s before
    # concluding the server failed — opening the browser too early shows a
    # permanent-looking "Please wait..." page.
    local i
    for i in $(seq 1 80); do
        if is_server_running; then
            ok "server online"
            return 0
        fi
        sleep 0.5
    done
    echo ""
    echo "❌ Server did not come up. Last log lines:"
    tail -25 "${LOG_FILE}" 2>/dev/null
    die "Startup failed." "Fix the error above (or send it to your assistant), then double-click the launcher again."
}

# ---------------- main ----------------

echo "🎬 Hindi Reel Studio launcher"

if is_server_running; then
    _old_fp="$(cat "${FP_FILE}" 2>/dev/null)"
    _new_fp="$(code_fingerprint)"
    if [ -n "${_old_fp}" ] && [ -n "${_new_fp}" ] && [ "${_old_fp}" = "${_new_fp}" ]; then
        ok "server already running with the latest code — opening it"
        open_app
        exit 0
    fi
    echo "🔄 Server is up but the code changed — doing a clean restart..."
fi

step "1/4  CLEAN — stopping stuck servers, freeing port ${PORT}"
clean_all
ok "port ${PORT} free, stale state removed"

step "2/4  VALIDATE — checking python, packages, app.py"
if validate_env; then
    ok "environment healthy — no repair needed"
else
    step "3/4  REPAIR — rebuilding what is broken"
    repair_env
fi

step "4/4  LAUNCH — starting the server"
start_server

echo ""
echo "🚀 Opening Hindi Reel Studio..."
open_app
echo "   Done — you can close this Terminal window."
