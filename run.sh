#!/usr/bin/env bash
# Startup script for Apple FM Editorial Multi-Agent Newsroom

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    /opt/homebrew/bin/python3.11 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

HOST="${HRS_HOST:-localhost}"
PORT="${HRS_PORT:-8501}"
echo "🍏 Starting The Editorial Room (Apple Foundation Models Streamlit Web App on ${HOST}:${PORT})..."
streamlit run app.py --global.developmentMode false --server.address "${HOST}" --server.port "${PORT}"
