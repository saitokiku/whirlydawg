#!/usr/bin/env bash
# Idempotent CAD environment bootstrap. Safe to run on every session start.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then
  uv venv .venv --python 3.12 >/dev/null
fi
if ! .venv/bin/python -c "import build123d, agentcad" 2>/dev/null || [ requirements.txt -nt .venv/.installed ]; then
  uv pip install --python .venv/bin/python -r requirements.txt >/dev/null
  touch .venv/.installed
fi
[ -f build/agentcad.json ] || .venv/bin/agentcad init --name "$(basename "$PWD")" >/dev/null 2>&1 || true
echo "CAD env ready: $(.venv/bin/python -c 'import build123d;print("build123d",build123d.__version__)')"
