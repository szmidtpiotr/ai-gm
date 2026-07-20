#!/usr/bin/env bash
# Run pytest inside the backend Docker container (local or any host with the dev stack).
# No SSH — only Docker.
#
#   docker compose -f docker-compose.dev.yml up -d --build backend
#   ./scripts/test_dev.sh
#   ./scripts/test_dev.sh tests/test_gm_plan_schema.py -v
#   ./scripts/test_dev.sh --live tests/test_foo.py   # świadomy wyjątek: żywa baza DEV
#
# #1487 Faza 2 — DOMYŚLNIE testy dostają KOPIĘ bazy. Żywa DEV DB jest wtedy
# nietykalna: pytest startuje z AI_TEST_DB_PATH na kopię, a wszystkie moduły
# czytają ścieżkę przez resolve_db_path() (Faza 1). Kopia ginie po przebiegu.
set -euo pipefail

CONTAINER="${AIGM_DEV_BACKEND:-ai-gm-dev-backend-1}"
WORKDIR="${AIGM_PYTEST_WORKDIR:-/app}"
LIVE_DB="${AIGM_LIVE_DB:-/data/ai_gm.db}"

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

if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
  echo "❌ Container not found: $CONTAINER" >&2
  echo "   docker compose -f docker-compose.dev.yml up -d --build backend" >&2
  echo "   Or: ./scripts/test_local.sh (no Docker)" >&2
  exit 1
fi

if [[ $ISOLATED -eq 0 ]]; then
  echo "⚠️  --live: testy piszą do ŻYWEJ bazy DEV ($LIVE_DB)." >&2
  echo "🧪 pytest in $CONTAINER (workdir $WORKDIR)…" >&2
  exec docker exec -w "$WORKDIR" "$CONTAINER" python3 -m pytest "${ARGS[@]}"
fi

TEST_DB="/tmp/aigm_test_$$_$(date +%s).db"
cleanup() { docker exec "$CONTAINER" rm -f "$TEST_DB" "$TEST_DB-wal" "$TEST_DB-shm" 2>/dev/null || true; }
trap cleanup EXIT

echo "🧬 kopia bazy → $TEST_DB (żywa $LIVE_DB tylko do odczytu)…" >&2
docker exec "$CONTAINER" sqlite3 "$LIVE_DB" ".backup '$TEST_DB'"

echo "🧪 pytest in $CONTAINER (workdir $WORKDIR, izolowana baza)…" >&2
set +e
docker exec -w "$WORKDIR" -e AI_TEST_MODE=1 -e AI_TEST_DB_PATH="$TEST_DB" \
  "$CONTAINER" python3 -m pytest "${ARGS[@]}"
rc=$?
set -e
exit $rc
