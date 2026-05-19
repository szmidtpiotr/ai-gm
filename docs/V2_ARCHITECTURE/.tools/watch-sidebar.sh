#!/usr/bin/env bash
# Watch V2_ARCHITECTURE for .md changes and regenerate _sidebar.md.
# Debounces bursts of events so batched file ops only trigger one regen.
set -u

ROOT="/home/piotrszmidt/ai-gm/docs/V2_ARCHITECTURE"
GEN="$ROOT/.tools/gen-sidebar.py"
DEBOUNCE=1

[[ -x "$GEN" ]] || { echo "missing $GEN"; exit 1; }

run_gen() {
  if out=$("$GEN" 2>&1); then
    echo "[$(date +%H:%M:%S)] $out"
  else
    echo "[$(date +%H:%M:%S)] generator failed: $out" >&2
  fi
}

# initial run on startup
run_gen

# Recursive monitor. Exclude .tools/, hidden files, and _sidebar.md to avoid self-loop.
inotifywait -m -r -q \
  -e create -e delete -e moved_to -e moved_from \
  --exclude '(^|/)\.tools(/|$)|(^|/)_sidebar\.md$|(^|/)\.[^/]+$' \
  "$ROOT" |
while read -r line; do
  case "$line" in
    *.md|*\ CREATE,ISDIR\ *|*\ DELETE,ISDIR\ *|*\ MOVED_TO,ISDIR\ *|*\ MOVED_FROM,ISDIR\ *)
      # drain any further events arriving within DEBOUNCE seconds
      while read -r -t "$DEBOUNCE" extra; do :; done
      run_gen
      ;;
  esac
done
