#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${1:-8000}"
echo "Serving web-app at http://0.0.0.0:${PORT}"
python3 -m http.server "${PORT}" --directory web-app
