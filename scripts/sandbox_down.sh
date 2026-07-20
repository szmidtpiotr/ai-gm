#!/usr/bin/env bash
# Zatrzymaj sandbox testów UI (#1488). Dane zostają w wolumenie `e2e-data`,
# więc kolejny `sandbox_up.sh` wstaje szybciej. Pełne czyszczenie: --wipe.
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ "${1:-}" == "--wipe" ]]; then
  echo "=== Sandbox: stop + kasowanie danych ==="
  docker compose -f docker-compose.e2e.yml down -v
else
  echo "=== Sandbox: stop (dane zachowane) ==="
  docker compose -f docker-compose.e2e.yml down
fi
