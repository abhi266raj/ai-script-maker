#!/usr/bin/env bash
# Reinstall the project venv from requirements.txt — fail loudly.
#
# Usage:  bash script.sh
# Env overrides: REPO=/path/to/repo  VENV=/path/to/.venv
set -euo pipefail

REPO="${REPO:-$HOME/Documents/news/agent}"
VENV="${VENV:-$REPO/.venv}"
REQ="$REPO/requirements.txt"

echo "Repo:         $REPO"
echo "Venv:         $VENV"
echo "Requirements: $REQ"

command -v python3 >/dev/null || { echo "ERROR: python3 not found on PATH" >&2; exit 1; }
[ -f "$REQ" ] || { echo "ERROR: requirements.txt not found at $REQ" >&2; exit 1; }

if [ -d "$VENV" ]; then
    echo "Removing old venv: $VENV"
    rm -rf "$VENV"
fi

echo "Creating fresh venv..."
python3 -m venv "$VENV"

echo "Upgrading pip and installing requirements (takes a few minutes)..."
"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/python" -m pip install -r "$REQ"

echo "Verifying against the pin..."
PIN="$(grep -E '^streamlit==' "$REQ" | sed -E 's/^streamlit==//; s/#.*//; s/[[:space:]]//g')"
INSTALLED="$("$VENV/bin/python" -c 'import streamlit; print(streamlit.__version__)')"
echo "Pinned:    $PIN"
echo "Installed: $INSTALLED"
[ -n "$PIN" ] || { echo "ERROR: could not parse streamlit pin from $REQ" >&2; exit 1; }
[ "$INSTALLED" = "$PIN" ] || { echo "ERROR: installed streamlit ($INSTALLED) != pin ($PIN)" >&2; exit 1; }

echo "OK: venv reinstalled at $VENV with streamlit $INSTALLED"
