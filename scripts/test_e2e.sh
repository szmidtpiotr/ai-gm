#!/usr/bin/env bash
# UX tests (Playwright) — real browser, stub LLM. No SSH.
#
# Prefers an already-running backend (e.g. docker compose -f docker-compose.dev.yml).
# Otherwise starts the isolated e2e stack (docker-compose.e2e.yml).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

E2E_FRONTEND_PORT="${E2E_FRONTEND_PORT:-13002}"
E2E_BACKEND_PORT="${E2E_BACKEND_PORT:-18100}"
DEV_FRONTEND_PORT="${DEV_FRONTEND_PORT:-3002}"
DEV_BACKEND_PORT="${DEV_BACKEND_PORT:-8100}"

health_ok() {
  curl -sf "http://127.0.0.1:$1/api/healthz" >/dev/null 2>&1
}

if health_ok "$DEV_BACKEND_PORT"; then
  echo "=== Using existing DEV stack (:${DEV_BACKEND_PORT} / :${DEV_FRONTEND_PORT}) ==="
  export BASE_URL="http://127.0.0.1:${DEV_FRONTEND_PORT}"
  export BACKEND_URL="http://127.0.0.1:${DEV_BACKEND_PORT}"
  STACK_UP=0
else
  echo "=== Starting isolated E2E stack (:${E2E_BACKEND_PORT} / :${E2E_FRONTEND_PORT}) ==="
  export E2E_FRONTEND_PORT E2E_BACKEND_PORT
  export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-ai-gm-e2e}"
  export BASE_URL="http://127.0.0.1:${E2E_FRONTEND_PORT}"
  export BACKEND_URL="http://127.0.0.1:${E2E_BACKEND_PORT}"
  STACK_UP=1
fi

if [[ "${STACK_UP:-0}" == "1" ]]; then
  docker compose -f docker-compose.e2e.yml up -d --build --wait
fi

echo "→ Seeding AI test user/campaign (requires AI_TEST_MODE=1 on backend)…"
if [[ "$STACK_UP" == "1" ]]; then
  docker compose -f docker-compose.e2e.yml exec -T backend python3 scripts/seed_ai_test_env.py
  docker compose -f docker-compose.e2e.yml exec -T backend python3 -c "
import urllib.request
req = urllib.request.Request('http://127.0.0.1:8000/api/debug/reset_test_env', method='POST')
print(urllib.request.urlopen(req, timeout=30).read().decode())
"
else
  docker exec ai-gm-dev-backend-1 python3 scripts/seed_ai_test_env.py 2>/dev/null || \
    python3 backend/scripts/seed_ai_test_env.py
  curl -sf -X POST "${BACKEND_URL}/api/debug/reset_test_env" || {
    echo "❌ reset_test_env failed — is AI_TEST_MODE=1 set? Copy env.test.example → env.test and restart backend." >&2
    exit 1
  }
fi

AGENT_DIR="$REPO_DIR/ai_test_agent"
if [[ ! -d "$AGENT_DIR/node_modules/@playwright/test" ]]; then
  echo "→ npm ci in ai_test_agent…"
  (cd "$AGENT_DIR" && npm ci)
fi
if [[ "${E2E_INSTALL_BROWSERS:-1}" == "1" ]]; then
  (cd "$AGENT_DIR" && npx playwright install chromium 2>/dev/null || true)
fi

export AI_TEST_CONFIG_PATH="${AI_TEST_CONFIG_PATH:-$REPO_DIR/data-dev/ai_test_config.json}"
mkdir -p "$(dirname "$AI_TEST_CONFIG_PATH")"
if [[ "$STACK_UP" == "1" ]] && [[ ! -f "$AI_TEST_CONFIG_PATH" ]]; then
  docker compose -f docker-compose.e2e.yml exec -T backend cat /data/ai_test_config.json > "$AI_TEST_CONFIG_PATH"
fi

echo "→ API preflight (campaigns + heroes must work before browser tests)…"
BACKEND_URL="$BACKEND_URL" bash "$REPO_DIR/scripts/e2e_preflight.sh"

echo "→ Playwright UX suite (${BASE_URL})…"
cd "$AGENT_DIR"
npx playwright test --config=playwright/playwright.config.js "$@"
