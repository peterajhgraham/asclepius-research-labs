#!/usr/bin/env bash
# Local development setup for the Asclepius backend.
#
# IMPORTANT: The shell alias `python` may point to system Python 3.9 even
# inside an activated venv on macOS. This script uses venv/bin/python and
# venv/bin/uvicorn explicitly so the right interpreter is always used.

set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "$0")/../asclepius/backend" && pwd)"

echo "==> Backend dir: $BACKEND_DIR"
cd "$BACKEND_DIR"

# Create venv if it doesn't exist
if [ ! -d "venv" ]; then
    echo "==> Creating virtualenv..."
    python3 -m venv venv
fi

echo "==> Installing dependencies..."
venv/bin/pip install --upgrade pip --quiet
venv/bin/pip install -r requirements.txt --quiet

# Copy .env if it doesn't exist
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    cp .env.example .env
    echo "==> Copied .env.example -> .env (fill in your API keys)"
fi

echo ""
echo "Setup complete. Start the backend with:"
echo ""
echo "  cd asclepius/backend"
echo "  venv/bin/uvicorn app.main:app --port 8000 --reload --reload-dir app"
echo ""
echo "Do NOT use bare 'python' or 'uvicorn' — the shell alias may resolve"
echo "to system Python 3.9 rather than the venv interpreter."
echo ""
echo "NOTE (Apple Silicon Macs): This installs x86_64 Python under Rosetta."
echo "Torch 2.4+ requires native arm64 Python. To get it:"
echo "  1. Install arm64 Homebrew: arch -arm64 /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
echo "  2. /opt/homebrew/bin/brew install python@3.11"
echo "  3. Re-run this script (it will use /opt/homebrew/bin/python3.11)"
