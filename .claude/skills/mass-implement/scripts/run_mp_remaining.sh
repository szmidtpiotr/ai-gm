#!/usr/bin/env bash
# Run the 9 remaining (non-review) Multiplayer (Faza 5) issues, one orchestrate
# invocation per issue, sequentially. A gate/error on one issue is logged but does
# NOT halt the rest — these features are independent.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ORCH="$HERE/orchestrate.sh"
ISSUES=(796 804 806 807 808 809 810 811 813)
DRV_LOG="$HERE/.runs/mp_remaining_$(date +%Y%m%d_%H%M%S).driver.log"
: > "$DRV_LOG"
echo "=== MP remaining driver — ${#ISSUES[@]} issues: ${ISSUES[*]} ===" | tee -a "$DRV_LOG"
for n in "${ISSUES[@]}"; do
  echo "" | tee -a "$DRV_LOG"
  echo ">>>>> ISSUE #$n  ($(date +%H:%M:%S)) >>>>>" | tee -a "$DRV_LOG"
  bash "$ORCH" @Multiplayer "#$n" </dev/null >>"$DRV_LOG" 2>&1
  rc=$?
  echo "<<<<< ISSUE #$n  rc=$rc <<<<<" | tee -a "$DRV_LOG"
done
echo "" | tee -a "$DRV_LOG"
echo "=== DRIVER DONE — wszystkie ${#ISSUES[@]} issue przetworzone ===" | tee -a "$DRV_LOG"
echo "Log: $DRV_LOG"
