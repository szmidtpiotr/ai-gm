#!/usr/bin/env bash
# One-shot overlay refresh: GitHub issues -> badges, runtime DB -> heat, drift check.
# Safe to run from cron. Read-only against GitHub and the DB.
#
#   ./refresh.sh                  # issues + heat + drift, default repo
#   ARCHMAP_REPO=owner/name ./refresh.sh
#
# Cron example (nightly 03:30 on the host that has gh + repo, alongside backup_dev):
#   30 3 * * * cd /home/piotrszmidt/ai-gm/tools/archmap/overlay && ./refresh.sh >> refresh.log 2>&1
set -euo pipefail
cd "$(dirname "$0")"
REPO="${ARCHMAP_REPO:-szmidtpiotr/ai-gm}"

# Load GH_TOKEN from ~/.gh_token if not already set (needed in cron where env is stripped)
if [ -z "${GH_TOKEN:-}" ] && [ -f "${HOME:-/home/claude}/.gh_token" ]; then
    GH_TOKEN=$(cat "${HOME:-/home/claude}/.gh_token")
    export GH_TOKEN
fi

echo "== $(date -u +%FT%TZ) archmap overlay refresh =="
echo "-- issues -> badges"
python3 update_overlay.py --repo "$REPO" || echo "  (issues step failed — keeping previous badges)"
echo "-- runtime -> heat"
python3 update_heat.py || echo "  (heat step skipped — DB unreachable or Phase 11 tables absent)"
echo "-- drift check"
python3 drift_check.py || true
echo "== done =="
