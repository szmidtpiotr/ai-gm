#!/usr/bin/env bash
# Copy the repo Grafana dashboard JSON to a host that provisions dashboards from a folder.
# Example:
#   export GRAFANA_SSH="deploy@obs.example.com"
#   export GRAFANA_REMOTE_JSON="/opt/ai-gm/observability/grafana/provisioning/dashboards/json/campaign-narrative-loki.json"
#   ./scripts/sync-grafana-dashboard.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${1:-$ROOT/observability/grafana/provisioning/dashboards/json/campaign-narrative-loki.json}"
HOST="${GRAFANA_SSH:?Set GRAFANA_SSH to user@host}"
DEST="${GRAFANA_REMOTE_JSON:?Set GRAFANA_REMOTE_JSON to absolute path on the server}"
scp "$SRC" "${HOST}:${DEST}"
echo "Uploaded $(basename "$SRC") -> ${HOST}:${DEST}"
echo "Reload Grafana provisioning or restart the stack if dashboards are baked in."
