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

ISOLATED=1
ARGS=()
for arg in "$@"; do
  case "$arg" in
    --live) ISOLATED=0 ;;
    backend/tests/*) ARGS+=("tests/${arg#backend/tests/}") ;;
    *) ARGS+=("$arg") ;;
  esac
done
[[ ${#ARGS[@]} -eq 0 ]] && ARGS=(-q --tb=short tests/)

cd "$BACKEND_DIR"

if [[ $ISOLATED -eq 0 ]]; then
  echo "⚠️  --live: testy piszą do bazy wskazanej domyślnie (bez izolacji)." >&2
  echo "🧪 pytest (local) in $BACKEND_DIR …" >&2
  exec "$VENV_PYTHON" -m pytest "${ARGS[@]}"
fi

# #1487 Faza 2 — testy dostają własny plik bazy. Gdy w repo leży lokalna kopia DEV
# (data-dev/ai_gm.db), startujemy z jej kopii, żeby testy miały realne dane.
TEST_DB="$(mktemp -t aigm_test_XXXXXX.db)"
cleanup() { rm -f "$TEST_DB" "$TEST_DB-wal" "$TEST_DB-shm"; }
trap cleanup EXIT

SOURCE_DB="$REPO_DIR/data-dev/ai_gm.db"
if [[ -f "$SOURCE_DB" ]]; then
  cp "$SOURCE_DB" "$TEST_DB"
  echo "🧬 kopia $SOURCE_DB → $TEST_DB" >&2
else
  echo "🧬 brak lokalnej data-dev/ai_gm.db — testy dostają pusty plik $TEST_DB" >&2
fi

echo "🧪 pytest (local, izolowana baza) in $BACKEND_DIR …" >&2
set +e
AI_TEST_MODE=1 AI_TEST_DB_PATH="$TEST_DB" "$VENV_PYTHON" -m pytest "${ARGS[@]}"
rc=$?
set -e
exit $rc
