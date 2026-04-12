#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-focus}"

ROOT="$(pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="ai-gm-dump-${MODE}-${STAMP}.txt"

EXCLUDES=(
  "./.git"
  "./.venv"
  "./venv"
  "./node_modules"
  "./__pycache__"
  "./dist"
  "./build"
  "./output"
  "./data"
)

should_skip_file() {
  local f="$1"

  case "$f" in
    ./.env|./.env.*|*.pem|*.key|*.crt|*.p12|*.pfx|*.sqlite|*.sqlite3|*.db|*.db-shm|*.db-wal|*.pyc|*.log|*.bak)
      return 0
      ;;
    ./*ai-gm-dump-*.txt|./ai-gm-project-dump.txt|./dump_project.sh)
      return 0
      ;;
  esac

  return 1
}

prune_args() {
  local first=1
  for p in "${EXCLUDES[@]}"; do
    if [ $first -eq 1 ]; then
      printf -- "-path '%s' -prune " "$p"
      first=0
    else
      printf -- "-o -path '%s' -prune " "$p"
    fi
  done
}

list_focus_files() {
  find . \
    \( -path './.git' -o -path './.venv' -o -path './venv' -o -path './node_modules' -o -path './__pycache__' -o -path './dist' -o -path './build' -o -path './output' -o -path './data' \) -prune -o \
    -type f \
    \( \
      -path './backend/app/api/*' -o \
      -path './backend/app/core/*' -o \
      -path './backend/app/services/*' -o \
      -path './backend/app/systems/*' -o \
      -path './backend/sql/*' -o \
      -path './frontend/js/*' -o \
      -path './frontend/i18n/*' -o \
      -path './frontend/index.html' -o \
      -path './frontend/styles.css' -o \
      -path './frontend/nginx.conf' -o \
      -path './docker-compose.yml' -o \
      -path './README.md' -o \
      -path './docs/*' \
    \) -print | sort
}

list_full_files() {
  find . \
    \( -path './.git' -o -path './.venv' -o -path './venv' -o -path './node_modules' -o -path './__pycache__' -o -path './dist' -o -path './build' -o -path './output' -o -path './data' \) -prune -o \
    -type f \
    \( \
      -name '*.py' -o \
      -name '*.js' -o \
      -name '*.html' -o \
      -name '*.css' -o \
      -name '*.json' -o \
      -name '*.md' -o \
      -name '*.sql' -o \
      -name '*.yml' -o \
      -name '*.yaml' -o \
      -name '*.conf' -o \
      -name '*.txt' \
    \) -print | sort
}

emit_file() {
  local f="$1"
  if should_skip_file "$f"; then
    return
  fi

  echo
  echo "===== FILE: $f ====="
  cat "$f"
  echo
  echo "===== END FILE: $f ====="
  echo
}

{
  echo "# AI-GM PROJECT DUMP"
  echo "# Generated: $(date -Iseconds)"
  echo "# Mode: ${MODE}"
  echo "# Root: ${ROOT}"
  echo

echo "## REPO INFO"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Branch: $(git branch --show-current || true)"
  echo "Commit: $(git rev-parse --short HEAD || true)"
  echo
  echo "### git status --short"
  git status --short || true
  echo
  echo "### git diff --stat"
  git diff --stat || true
  echo
  echo "### git diff -- backend frontend docker-compose.yml README.md"
  git diff -- backend frontend docker-compose.yml README.md || true
  echo
else
  echo "Not a git repo"
fi
echo

  echo "## TREE"
  find . \
    \( -path './.git' -o -path './.venv' -o -path './venv' -o -path './node_modules' -o -path './__pycache__' -o -path './dist' -o -path './build' -o -path './output' -o -path './data' \) -prune -o \
    -type f -print | sort | while read -r f; do
      if should_skip_file "$f"; then
        continue
      fi
      echo "$f"
    done
  echo

  if [ "$MODE" = "focus" ]; then
    echo "## FILE GROUP: FOCUSED PROJECT FILES"
    list_focus_files | while read -r f; do
      emit_file "$f"
    done
  else
    echo "## FILE GROUP: FULL PROJECT FILES"
    list_full_files | while read -r f; do
      emit_file "$f"
    done
  fi
} > "$OUT"

echo "Wrote $OUT"
wc -l "$OUT"
ls -lh "$OUT"