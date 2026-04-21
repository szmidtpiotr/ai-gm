#!/usr/bin/env bash
# Point this repo at .githooks/ so pre-push runs prompt integrity tests.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
git config core.hooksPath .githooks
echo "✅ core.hooksPath=.githooks — pre-push will run: tests/test_prompt_integrity.py"
