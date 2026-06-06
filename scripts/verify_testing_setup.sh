#!/usr/bin/env bash
# Smoke-check TDD tooling (run from repo root on any machine with Docker + uv).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'
fail() { echo -e "${RED}FAIL:${NC} $*" >&2; exit 1; }
ok() { echo -e "${GREEN}OK:${NC} $*"; }

echo "=== 1. Scripts exist and are executable ==="
for s in scripts/test_local.sh scripts/test_dev.sh; do
  [[ -f "$s" ]] || fail "missing $s"
  [[ -x "$s" ]] || fail "not executable: $s (run: chmod +x $s)"
done
ok "scripts present"

echo "=== 2. Path rewrite (backend/tests → tests) ==="
# shellcheck source=/dev/null
source /dev/null
rewritten=$(bash -c '
  normalize() {
    for arg in "$@"; do
      case "$arg" in
        backend/tests/foo.py) echo "tests/foo.py" ;;
        *) echo "$arg" ;;
      esac
    done
  }
  normalize backend/tests/foo.py
')
[[ "$rewritten" == "tests/foo.py" ]] || fail "path rewrite got: $rewritten"
ok "path rewrite"

echo "=== 3. Local pytest (backend venv) ==="
./scripts/test_local.sh tests/test_gm_plan_schema.py tests/test_economy_service.py -q --tb=line \
  || fail "local smoke tests"

echo "=== 4. Docker image pytest (matches production container layout) ==="
if ! docker image inspect ai-gm-test-verify:latest >/dev/null 2>&1; then
  echo "   Building ai-gm-test-verify:latest from backend/Dockerfile …"
  docker build -t ai-gm-test-verify:latest backend/
fi
docker run --rm ai-gm-test-verify:latest python3 -m pytest \
  tests/test_gm_plan_schema.py tests/test_economy_service.py -q --tb=line \
  || fail "container smoke tests"

wrong=$(docker run --rm ai-gm-test-verify:latest python3 -m pytest backend/tests/test_gm_plan_schema.py -q 2>&1 || true)
echo "$wrong" | grep -q "file or directory not found" \
  || fail "expected backend/tests path to fail in container"
ok "container rejects wrong backend/tests/ path"

echo "=== 5. Docs and skill files ==="
for f in docs/GETTING_STARTED.md docs/TESTING.md scripts/e2e_preflight.sh scripts/test_e2e.sh .cursor/skills/ai-gm-tdd/SKILL.md backend/pytest.ini; do
  [[ -f "$f" ]] || fail "missing $f"
done
[[ -x scripts/e2e_preflight.sh ]] || fail "not executable: scripts/e2e_preflight.sh (chmod +x)"
ok "docs/skill/pytest.ini/e2e scripts"

if grep -q 'ssh piotrszmidt@192.168.1.61' docs/TESTING.md 2>/dev/null && \
   ! grep -q 'test_local.sh' docs/TESTING.md 2>/dev/null; then
  fail "docs/TESTING.md still SSH-only without test_local.sh"
fi
ok "docs mention local runner"

echo ""
echo -e "${GREEN}All verification steps passed.${NC}"
