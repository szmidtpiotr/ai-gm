#!/usr/bin/env bash
# Detached launcher: starts the orchestrator fully decoupled (setsid + /dev/null +
# own log) and returns immediately, so the caller's stream closes cleanly while the
# run keeps going independently of any session/turn.
set -u
ROOT=/home/claude/projects/DEV_AIGM
SEL="${1:-799-805}"
RUNS="$ROOT/.claude/skills/mass-implement/scripts/.runs"
mkdir -p "$RUNS"
OUT="$RUNS/resume_$(echo "$SEL" | tr -d ' ').out"
cd "$ROOT" || exit 1
setsid bash "$ROOT/.claude/skills/mass-implement/scripts/orchestrate.sh" "@Multiplayer" "$SEL" \
  </dev/null >"$OUT" 2>&1 &
PID=$!
disown 2>/dev/null || true
echo "launched orchestrator pid=$PID  sel=$SEL  out=$OUT"
