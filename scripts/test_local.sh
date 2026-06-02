#!/usr/bin/env bash
# Run pytest on your machine (local clone). No SSH, no remote server.
#
# Usage (from repo root):
#   ./scripts/test_local.sh
#   ./scripts/test_local.sh tests/test_gm_plan_schema.py -v
#   ./scripts/test_local.sh backend/tests/test_gm_plan_schema.py -v
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$REPO_DIR/backend"
VENV_PYTHON="$BACKEND_DIR/.venv/bin/python"

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Creating venv and installing deps in backend/.venv …" >&2
  command -v uv >/dev/null || { echo "❌ Need 'uv' or pre-create backend/.venv with pytest installed." >&2; exit 1; }
  (cd "$BACKEND_DIR" && uv venv .venv && uv pip install -r requirements.txt)
fi

ARGS=()
if [[ $# -eq 0 ]]; then
  ARGS=(-q --tb=short tests/)
else
  for arg in "$@"; do
    case "$arg" in
      backend/tests/*) ARGS+=("tests/${arg#backend/tests/}") ;;
      *) ARGS+=("$arg") ;;
    esac
  done
fi

echo "🧪 pytest (local) in $BACKEND_DIR …" >&2
cd "$BACKEND_DIR"
exec "$VENV_PYTHON" -m pytest "${ARGS[@]}"
