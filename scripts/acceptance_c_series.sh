#!/usr/bin/env bash
# Acceptance runner for the C1–C19 series (FAZA 1 core loop).
#
# Runs BOTH layers and writes a combined per-task report:
#   1. pytest mechanical  → backend/tests/acceptance/test_c_series_acceptance.py
#   2. Playwright LLM-play → ai_test_agent/playwright/ux/acceptance/ (c01..c19, one file per task)
#
# Run ON the DEV host (.61):
#   ./scripts/acceptance_c_series.sh
#
# Output: ACCEPTANCE_C_SERIES_REPORT.md (repo root) + raw logs in /tmp.
set -uo pipefail

REPO="${REPO:-/home/piotrszmidt/ai-gm}"
BE="ai-gm-dev-backend-1"
TA="ai-gm-dev-test-agent-1"
PYLOG=/tmp/acc_c_pytest.log
PWLOG=/tmp/acc_c_playwright.log
REPORT="$REPO/ACCEPTANCE_C_SERIES_REPORT.md"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "▶ Reset test env…"
docker exec "$BE" curl -s -X POST http://localhost:8100/api/debug/reset_test_env >/dev/null

echo "▶ pytest mechanical acceptance…"
docker exec "$BE" pytest tests/acceptance/test_c_series_acceptance.py -v --no-header -p no:cacheprovider \
  > "$PYLOG" 2>&1
PY_RC=$?

echo "▶ Playwright LLM-play acceptance (real LLM, ≤30 turns/test)…"
docker exec "$TA" npx playwright test playwright/ux/acceptance/ \
  --config=playwright/playwright.config.js --reporter=list > "$PWLOG" 2>&1
PW_RC=$?

# ── assemble report ─────────────────────────────────────────────────────────
status_in () { # $1 = log file, $2 = C-code regex → ✅ / ❌ / ⊘ skip / —
  local log="$1" re="$2"
  if grep -qiE "(FAILED|ERROR).*($re)|✘.*($re)|✗.*($re)" "$log" 2>/dev/null; then
    echo "❌"
  elif grep -qiE "PASSED.*($re)|✓.*($re)" "$log" 2>/dev/null; then
    echo "✅"
  elif grep -qiE "SKIP.*($re)|skipped.*($re)|-.*($re).*skipped" "$log" 2>/dev/null; then
    echo "⊘"
  else
    echo "—"
  fi
}

declare -A TASK=(
  [C1]="355|c01|C01" [C2]="356|c02|C02" [C3]="357|c03|C03" [C4]="360|c04|C04"
  [C5]="358|c05|C05" [C6]="359|c06|C06" [C7]="361|c07|C07" [C8]="362|c08|C08"
  [C9]="363|c09|C09" [C10]="364|c10|C10" [C11]="365|c11|C11" [C12]="366|c12|C12"
  [C13]="367|c13|C13" [C14]="368|c14|C14" [C15]="369|c15|C15" [C16]="370|c16|C16"
  [C17]="373|c17|C17" [C18]="374|c18|C18" [C19]="375|c19|C19"
)

{
  echo "# Acceptance Report — C1–C19 (FAZA 1)"
  echo ""
  echo "_Generated: $TS · pytest rc=$PY_RC · playwright rc=$PW_RC_"
  echo ""
  echo "Layers: **pytest** = deterministic backend truth · **E2E** = Playwright play-with-LLM / UI."
  echo "Legend: ✅ pass · ❌ fail · ⊘ skipped (not observable in that layer) · — not covered."
  echo ""
  echo "| Task | pytest | E2E | "
  echo "|------|--------|-----|"
  for n in $(seq 1 19); do
    c="C$n"
    re="${TASK[$c]}"
    echo "| $c (#${re%%|*}) | $(status_in "$PYLOG" "$re") | $(status_in "$PWLOG" "$re") |"
  done
  echo ""
  echo "## Raw — pytest"
  echo '```'
  tail -40 "$PYLOG"
  echo '```'
  echo ""
  echo "## Raw — Playwright"
  echo '```'
  tail -50 "$PWLOG"
  echo '```'
} > "$REPORT"

echo "✓ Report → $REPORT"
echo "  pytest rc=$PY_RC  playwright rc=$PW_RC"
