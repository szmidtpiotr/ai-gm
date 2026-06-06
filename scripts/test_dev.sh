#!/usr/bin/env bash
# Run pytest inside the backend Docker container (local or any host with the dev stack).
# No SSH — only Docker.
#
#   docker compose -f docker-compose.dev.yml up -d --build backend
#   ./scripts/test_dev.sh
#   ./scripts/test_dev.sh tests/test_gm_plan_schema.py -v
set -euo pipefail

CONTAINER="${AIGM_DEV_BACKEND:-ai-gm-dev-backend-1}"
WORKDIR="${AIGM_PYTEST_WORKDIR:-/app}"

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

if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
  echo "❌ Container not found: $CONTAINER" >&2
  echo "   docker compose -f docker-compose.dev.yml up -d --build backend" >&2
  echo "   Or: ./scripts/test_local.sh (no Docker)" >&2
  exit 1
fi

echo "🧪 pytest in $CONTAINER (workdir $WORKDIR)…" >&2
exec docker exec -w "$WORKDIR" "$CONTAINER" python3 -m pytest "${ARGS[@]}"
