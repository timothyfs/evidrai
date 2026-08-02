#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "$ROOT"

"$PYTHON_BIN" -m compileall api evidrai -q
"$PYTHON_BIN" -m pytest tests -q

cd "$ROOT/web"
npm ci
npm run build
