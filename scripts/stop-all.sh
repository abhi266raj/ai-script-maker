#!/usr/bin/env bash
# stop-all.sh — clean stop for Hindi Reel Studio (#125).
#
# Kills all Streamlit/app processes and clears stale runtime state so the
# next launch is a truly clean start. Safe to run when nothing is running.
#
# Usage: ./scripts/stop-all.sh
set -u

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIBRARY_ROOT="$HOME/Documents/HindiReelStudio"
stopped=0

kill_matching() {
    # $1 = grep pattern (bracket form to avoid matching ourselves), $2 = label
    local pattern="$1" label="$2" pids
    pids=$(pgrep -f "$pattern" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "Stopping $label (PIDs: $(echo "$pids" | tr '\n' ' '))"
        # shellcheck disable=SC2086
        kill $pids 2>/dev/null || true
        sleep 1
        # Force-kill stragglers.
        pids=$(pgrep -f "$pattern" 2>/dev/null || true)
        if [ -n "$pids" ]; then
            echo "Force-killing $label (PIDs: $(echo "$pids" | tr '\n' ' '))"
            # shellcheck disable=SC2086
            kill -9 $pids 2>/dev/null || true
        fi
        stopped=1
    else
        echo "No $label running."
    fi
}

echo "== Hindi Reel Studio — clean stop =="

# 1. Streamlit servers (any streamlit run, plus the app's own entry points).
kill_matching "[s]treamlit run" "Streamlit servers"
kill_matching "[a]pp.py" "app.py processes"
kill_matching "[m]ain.py" "main.py processes"

# 2. Stale runtime state.
warmup_mailbox="$LIBRARY_ROOT/fm_warmup.json"
if [ -f "$warmup_mailbox" ]; then
    rm -f "$warmup_mailbox" && echo "Cleared stale warmup state ($warmup_mailbox)"
    stopped=1
else
    echo "No stale warmup state."
fi

# 3. Stale Streamlit temp files for this app (best-effort).
tmp_cleared=0
for d in "$TMPDIR" /tmp; do
    [ -d "$d" ] || continue
    if ls "$d"/streamlit-* >/dev/null 2>&1; then
        rm -rf "$d"/streamlit-* 2>/dev/null && tmp_cleared=1
    fi
done
[ "$tmp_cleared" = "1" ] && echo "Cleared stale Streamlit temp files."

echo "== Done =="
if [ "$stopped" = "0" ]; then
    echo "Nothing was running — already clean."
else
    echo "All stopped. Start fresh with: streamlit run app.py"
    echo "(from $APP_DIR)"
fi
