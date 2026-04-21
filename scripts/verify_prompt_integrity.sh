#!/usr/bin/env bash
# Run from repo root (or via .githooks/pre-push).
# Server one-liner:  cd ~/ai-gm && python3 -m pytest tests/test_prompt_integrity.py -q
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"
if [[ ! -f tests/test_prompt_integrity.py ]]; then
  echo "verify_prompt_integrity: missing tests/test_prompt_integrity.py" >&2
  exit 1
fi
exec python3 -m pytest tests/test_prompt_integrity.py -q
