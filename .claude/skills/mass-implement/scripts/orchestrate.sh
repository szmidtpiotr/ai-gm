#!/usr/bin/env bash
# mass-implement orchestrator
# Spawns ONE real, named, resumable `claude` session per FAZA task, sequentially.
# Each child runs the FAZA start-prompt scoped to exactly one task and ends with a
# MASS_STATUS marker. DONE -> next task. GATE/ERROR/missing -> stop the whole run.
#
# Usage: orchestrate.sh <prompt_file> [range] [--list]
#   range: "B6-B10" | "B6" | "6-10" | "6" | empty(=all unchecked)
#   --list: print the task plan and exit (no sessions spawned)
set -uo pipefail

ROOT="/home/claude/projects/DEV_AIGM"
NOTES="$ROOT/notes.md"
STATE_DIR="$ROOT/.claude/skills/mass-implement/.runs"
mkdir -p "$STATE_DIR"

PROMPT_FILE_ARG="${1:-}"
RANGE_ARG="${2:-}"
LIST_ONLY=0
for a in "$@"; do [ "$a" = "--list" ] && LIST_ONLY=1; done
[ "$RANGE_ARG" = "--list" ] && RANGE_ARG=""

if [ -z "$PROMPT_FILE_ARG" ]; then
  echo "FATAL: brak pliku z promptem. Uzycie: orchestrate.sh prompt_b.md [B6-B10] [--list]" >&2
  exit 2
fi

# Resolve prompt file (accept bare name or path, relative to ROOT)
if [ -f "$PROMPT_FILE_ARG" ]; then PROMPT_FILE="$PROMPT_FILE_ARG"
elif [ -f "$ROOT/$PROMPT_FILE_ARG" ]; then PROMPT_FILE="$ROOT/$PROMPT_FILE_ARG"
else echo "FATAL: nie znaleziono pliku promptu: $PROMPT_FILE_ARG" >&2; exit 2; fi

[ -f "$NOTES" ] || { echo "FATAL: brak $NOTES" >&2; exit 2; }

# Derive FAZA prefix from first "FAZA X" / "FAZĄ X" token in the prompt file.
PREFIX=$(grep -oE 'FAZ[AĄ] [A-Z]{1,3}' "$PROMPT_FILE" | head -1 | sed -E 's/.* //')
[ -z "$PREFIX" ] && { echo "FATAL: nie wykryto fazy (FAZA X) w $PROMPT_FILE" >&2; exit 2; }

echo "=== mass-implement ==="
echo "Prompt   : $PROMPT_FILE"
echo "FAZA     : $PREFIX"
echo "Zakres   : ${RANGE_ARG:-(wszystkie niezaznaczone)}"
echo "Tryb     : $( [ "$LIST_ONLY" = 1 ] && echo LIST || echo RUN )"
echo

# Extract the FAZA section from notes.md: from "## FAZA <PREFIX>" to next "## ".
# NOTE: anchor "FAZA <p>" right after "## " (no ".*"). A greedy ".*FAZA L" used to
# also match a TRAILING mention like "... następna: CAŁA FAZA L" in another phase's
# header (e.g. FAZA S line), locking onto the wrong section and reporting 0 tasks.
SECTION=$(awk -v p="$PREFIX" '
  $0 ~ "^## FAZA "p"( |—|-|$)" {f=1; next}
  /^## / && f {exit}
  f {print}
' "$NOTES")

if [ -z "$SECTION" ]; then
  # fallback: looser header match (e.g. "## FAZA HI — ... [7/7]")
  SECTION=$(awk -v p="$PREFIX" '
    $0 ~ "^## FAZA "p"[^A-Za-z0-9]" {f=1; next}
    /^## / && f {exit}
    f {print}
  ' "$NOTES")
fi
[ -z "$SECTION" ] && { echo "FATAL: nie znalazlem sekcji '## FAZA $PREFIX' w notes.md" >&2; exit 2; }

# Parse range bounds (numeric). Empty => all.
RMIN=""; RMAX=""
if [ -n "$RANGE_ARG" ]; then
  rclean=$(echo "$RANGE_ARG" | tr 'a-z' 'A-Z' | sed -E "s/$PREFIX//g")
  if echo "$rclean" | grep -qE '^[0-9]+-[0-9]+$'; then
    RMIN=$(echo "$rclean" | cut -d- -f1); RMAX=$(echo "$rclean" | cut -d- -f2)
  elif echo "$rclean" | grep -qE '^[0-9]+$'; then
    RMIN="$rclean"; RMAX="$rclean"
  else
    echo "FATAL: nie rozumiem zakresu '$RANGE_ARG' (oczekuje np. B6-B10 albo B6)" >&2; exit 2
  fi
fi

# Build task plan: ordered list of UNCHECKED task ids in range.
# Checklist lines look like:  "- [ ] B11 — ..."  or  "- [x] [#658](url) — B12 — ..."
PLAN=()
while IFS= read -r line; do
  case "$line" in
    "- [ ] "*|"- [x] "*|"- [X] "*) : ;;
    *) continue ;;
  esac
  checked=0
  case "$line" in "- [x] "*|"- [X] "*) checked=1 ;; esac
  # Task id = token at the START of the line, after the checkbox and an optional
  # leading issue link "[#NNN](url) — ". Anchoring avoids grabbing numbers from
  # prose ("playtest B13", "wymaga #595") or sub-task suffixes ("B6a").
  rest=$(echo "$line" | sed -E 's/^- \[[ xX]\] +//')
  rest=$(echo "$rest" | sed -E 's/^\[#?[0-9]+\][^—]*—[[:space:]]*//')
  tid=$(echo "$rest" | grep -oE "^${PREFIX}[0-9]+[a-z]?" | head -1)
  [ -z "$tid" ] && continue
  num=$(echo "$tid" | sed -E "s/^$PREFIX//" | grep -oE '^[0-9]+')
  if [ -n "$RMIN" ]; then
    [ "$num" -lt "$RMIN" ] && continue
    [ "$num" -gt "$RMAX" ] && continue
  fi
  if [ "$checked" = 1 ]; then
    echo "  [x] $tid  (zrobione — pomijam)"
    continue
  fi
  PLAN+=("$tid")
  echo "  [ ] $tid  -> w planie"
done <<< "$SECTION"

echo
if [ "${#PLAN[@]}" -eq 0 ]; then
  echo "Brak niezaznaczonych zadan w zakresie. Nic do zrobienia."
  exit 0
fi
echo "Plan (${#PLAN[@]}): ${PLAN[*]}"
echo

if [ "$LIST_ONLY" = 1 ]; then
  echo "(--list: nie odpalam sesji)"
  exit 0
fi

# Run log + session map for this run
TS=$(date +%Y%m%d_%H%M%S)
RUN_LOG="$STATE_DIR/run_${PREFIX}_${TS}.log"
SUMMARY="$STATE_DIR/run_${PREFIX}_${TS}.summary"
: > "$SUMMARY"
echo "Run log : $RUN_LOG"
echo "Summary : $SUMMARY"
echo

BASE_PROMPT=$(cat "$PROMPT_FILE")

for tid in "${PLAN[@]}"; do
  uuid=$(uuidgen)
  sess_name="TASK ${PREFIX}-${tid#$PREFIX}"
  child_log="$STATE_DIR/task_${tid}_${TS}.log"

  echo "▶ $tid  | sesja: \"$sess_name\"  | id: $uuid" | tee -a "$RUN_LOG"

  child_prompt=$(cat <<EOF
[MASS-IMPLEMENT — sterowanie automatyczne]
Twoje JEDNO zadanie w tej sesji to DOKŁADNIE: ${tid}.
ZIGNORUJ krok promptu "znajdź pierwsze niezaznaczone [ ]" — pracuj wyłącznie nad ${tid}.
Pracuj w trybie auto (bez pytań pośrednich), zgodnie z poniższym promptem.

BRAMKI (jeśli trafisz którąkolwiek — NIE wdrażaj na siłę, zatrzymaj się):
- prompt wymaga decyzji Piotra (np. D2/D3 lub inna nierozstrzygnięta decyzja),
- sprzeczność kod ↔ design/opis,
- zadanie typu "kamień"/playtest/SMOKE bez cyklu TDD,
- twarda zależność niegotowa (np. #595).

OBOWIĄZKOWE: jako OSTATNIA linia outputu wypisz dokładnie jeden marker:
  MASS_STATUS: DONE          — wdrożone, testy zielone, notes.md zaktualizowany ([x] + [#NNN])
  MASS_STATUS: GATE — <krótki powód po polsku>
  MASS_STATUS: ERROR — <krótki powód po polsku>

──────────────────────────────────────────────────────────
$BASE_PROMPT
EOF
)

  cd "$ROOT" || { echo "MASS_STATUS_RUN: ERROR cd" ; break; }
  # setsid + </dev/null: child runs in its own process group so a SIGHUP to the
  #   launching (parent) Claude session — e.g. when Piotr resumes/closes it — does
  #   NOT reap the child mid-startup (the bug that left "TASK B-N" staged-but-idle).
  # env -u CLAUDE*: strip the inherited Claude Code context so the child boots as a
  #   clean top-level session instead of a stalled nested sub-agent.
  # setsid waits for the child to exit, so sequential semantics + rc are preserved.
  setsid env \
      -u CLAUDECODE \
      -u CLAUDE_CODE_ENTRYPOINT \
      -u CLAUDE_CODE_SESSION_ID \
      -u CLAUDE_CODE_CHILD_SESSION \
      -u CLAUDE_CODE_EXECPATH \
      -u AI_AGENT \
    claude -p \
      --name "$sess_name" \
      --session-id "$uuid" \
      --add-dir "$ROOT" \
      --dangerously-skip-permissions \
      --output-format text \
      "$child_prompt" </dev/null > "$child_log" 2>&1
  rc=$?

  status=$(grep -oE 'MASS_STATUS: (DONE|GATE|ERROR)[^\n]*' "$child_log" | tail -1)
  [ -z "$status" ] && status="MASS_STATUS: ERROR — brak markera (rc=$rc); zobacz $child_log"

  echo "  $tid -> $status" | tee -a "$RUN_LOG"
  echo "$tid | $sess_name | $uuid | $status | $child_log" >> "$SUMMARY"

  case "$status" in
    *"MASS_STATUS: DONE"*)
      echo "  ✔ dalej" | tee -a "$RUN_LOG"
      ;;
    *)
      echo "  ⛔ STOP — bramka/blad na $tid. Reszta planu wstrzymana." | tee -a "$RUN_LOG"
      echo "STOPPED_AT=$tid" >> "$SUMMARY"
      echo
      echo "=== KONIEC (zatrzymano na $tid) ==="
      echo "Wznow sesje do dokonczenia/weryfikacji:  claude --resume $uuid"
      exit 3
      ;;
  esac
  echo
done

echo "=== KONIEC — wszystkie zaplanowane zadania DONE ==="
echo "Sesje (do weryfikacji w panelu / --resume):"
cat "$SUMMARY"
exit 0
