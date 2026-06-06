#!/usr/bin/env bash
# Fail fast before Playwright if the E2E backend cannot serve the critical UX APIs.
set -euo pipefail

BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:18100}"

curl -sf "${BACKEND_URL}/api/healthz" >/dev/null || {
  echo "❌ healthz failed at ${BACKEND_URL}" >&2
  exit 1
}

reset_body=$(curl -sf -X POST "${BACKEND_URL}/api/debug/reset_test_env" || true)
if ! echo "$reset_body" | grep -qE '"reset"[[:space:]]*:[[:space:]]*true'; then
  echo "❌ reset_test_env failed (AI_TEST_MODE=1?): ${reset_body}" >&2
  exit 1
fi

campaigns_code=$(curl -s -o /tmp/aigm_e2e_campaigns.json -w "%{http_code}" "${BACKEND_URL}/api/campaigns")
if [[ "$campaigns_code" != "200" ]]; then
  echo "❌ GET /api/campaigns → ${campaigns_code} (required for campaign list UX)" >&2
  cat /tmp/aigm_e2e_campaigns.json 2>/dev/null || true
  exit 1
fi
if ! grep -q 'AI Test Campaign' /tmp/aigm_e2e_campaigns.json 2>/dev/null; then
  echo "❌ seeded campaign missing from /api/campaigns — run seed_ai_test_env.py" >&2
  cat /tmp/aigm_e2e_campaigns.json
  exit 1
fi

heroes_code=$(curl -s -o /tmp/aigm_e2e_heroes.json -w "%{http_code}" "${BACKEND_URL}/api/heroes?user_id=1")
if [[ "$heroes_code" != "200" ]]; then
  echo "❌ GET /api/heroes → ${heroes_code}" >&2
  exit 1
fi
if ! grep -q 'TestPlayer' /tmp/aigm_e2e_heroes.json 2>/dev/null; then
  echo "❌ TestPlayer missing from /api/heroes" >&2
  cat /tmp/aigm_e2e_heroes.json
  exit 1
fi

chars_code=$(curl -s -o /tmp/aigm_e2e_chars.json -w "%{http_code}" "${BACKEND_URL}/api/campaigns/1/characters")
if [[ "$chars_code" != "200" ]]; then
  echo "❌ GET /api/campaigns/1/characters → ${chars_code} (required to enter game)" >&2
  cat /tmp/aigm_e2e_chars.json 2>/dev/null || true
  exit 1
fi
if ! grep -q 'TestPlayer' /tmp/aigm_e2e_chars.json 2>/dev/null; then
  echo "❌ TestPlayer missing from campaign characters" >&2
  cat /tmp/aigm_e2e_chars.json
  exit 1
fi

ui_code=$(curl -s -o /dev/null -w "%{http_code}" "${BACKEND_URL}/api/ui/texts")
if [[ "$ui_code" != "200" ]]; then
  echo "❌ GET /api/ui/texts → ${ui_code}" >&2
  exit 1
fi

echo "✓ E2E preflight OK (${BACKEND_URL})"
