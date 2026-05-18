#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${NLM_AGENT_VENV:-$ROOT_DIR/.venv}"
WITH_BROWSER=0
FORCE_PLAYWRIGHT_BROWSER=0

detect_local_browser() {
  local candidates=(
    "google-chrome"
    "chromium"
    "chromium-browser"
    "microsoft-edge"
  )

  for browser in "${candidates[@]}"; do
    if command -v "$browser" >/dev/null 2>&1; then
      echo "$browser"
      return 0
    fi
  done

  local mac_paths=(
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    "/Applications/Chromium.app/Contents/MacOS/Chromium"
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
  )

  for browser_path in "${mac_paths[@]}"; do
    if [[ -x "$browser_path" ]]; then
      echo "$browser_path"
      return 0
    fi
  done

  return 1
}

for arg in "$@"; do
  case "$arg" in
    --browser)
      WITH_BROWSER=1
      ;;
    --force-playwright-browser)
      WITH_BROWSER=1
      FORCE_PLAYWRIGHT_BROWSER=1
      ;;
  esac
done

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -e "$ROOT_DIR"

if [[ "$WITH_BROWSER" -eq 1 ]]; then
  "$VENV_DIR/bin/python" -m pip install "notebooklm-py[browser]"

  if [[ "$FORCE_PLAYWRIGHT_BROWSER" -eq 1 ]]; then
    echo "Installing Playwright Chromium because --force-playwright-browser was requested."
    "$VENV_DIR/bin/python" -m playwright install chromium
  elif BROWSER_PATH="$(detect_local_browser)"; then
    echo "Detected local browser: $BROWSER_PATH"
    echo "Skipping Playwright browser download and preferring the installed local browser."
  else
    echo "No local Chrome/Chromium/Edge browser detected."
    echo "Installing Playwright Chromium as a fallback for browser-based login."
    "$VENV_DIR/bin/python" -m playwright install chromium
  fi
else
  "$VENV_DIR/bin/python" -m pip install "notebooklm-py"
fi

echo "Bootstrap complete."
echo "Virtualenv: $VENV_DIR"
echo "Try: $ROOT_DIR/bin/nlm-agent doctor"
