#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${NLM_AGENT_VENV:-$ROOT_DIR/.venv}"
WITH_BROWSER=0

if [[ "${1:-}" == "--browser" ]]; then
  WITH_BROWSER=1
fi

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -e "$ROOT_DIR"

if [[ "$WITH_BROWSER" -eq 1 ]]; then
  "$VENV_DIR/bin/python" -m pip install "notebooklm-py[browser]"
else
  "$VENV_DIR/bin/python" -m pip install "notebooklm-py"
fi

echo "Bootstrap complete."
echo "Virtualenv: $VENV_DIR"
echo "Try: $ROOT_DIR/bin/nlm-agent doctor"
