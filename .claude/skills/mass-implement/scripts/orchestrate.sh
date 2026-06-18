#!/usr/bin/env bash
# mass-implement orchestrator
# Spawns ONE real, named, resumable `claude` session per task, sequentially.
# Each child runs a start-prompt scoped to exactly one task and ends with a
# MASS_STATUS marker. DONE -> next task. GATE/ERROR/missing -> stop the whole run.
#
# TWO MODES (auto-detected from arg1):
#
#  FAZA mode — arg1 is a FAZA start-prompt that contains a "FAZA X" token
#    Usage: orchestrate.sh <prompt_file> [range] [--list]
#      range: "B6-B10" | "B6" | "6-10" | "6" | empty(=all unchecked)
#    Tasks parsed from notes.md "## FAZA X". Child prompt = arg1 verbatim.
#
#  LIST mode — arg1 is a task-list file with no "FAZA X" token (e.g. fix_list.md)
#    Usage: orchestrate.sh <list_file> [selector] [--list]
#      selector: ""        -> all unchecked tasks
#                "#767"     -> the task for issue #767
#                "P0".."Pn" -> all unchecked tasks under "### P0" section
#                "5"        -> task with global index 5
#                "3-7"      -> tasks with global index 3..7
#    Tasks parsed from the "## KOLEJNOŚĆ IMPLEMENTACJI" region of arg1 (lines like
#    "- [ ] 5. #767 — ..."). Child prompt = prompt_fix_mass.md; task id = FIX<issue>.
#
#  --list: print the task plan and exit (no sessions spawned)
set -uo pipefail

ROOT="/home/claude/projects/DEV_AIGM"
NOTES="$ROOT/notes.md"
STATE_DIR="$ROOT/.claude/skills/mass-implement/.runs"
mkdir -p "$STATE_DIR"

FILE_ARG="${1:-}"
SELECTOR_ARG="${2:-}"
LIST_ONLY=0
for a in "$@"; do [ "$a" = "--list" ] && LIST_ONLY=1; done
[ "$SELECTOR_ARG" = "--list" ] && SELECTOR_ARG=""

if [ -z "$FILE_ARG" ]; then
  echo "FATAL: brak pliku. Uzycie: orchestrate.sh <prompt_b.md|fix_list.md> [zakres|#issue|P0] [--list]" >&2
  exit 2
fi

# Resolve file (accept bare name or path, relative to ROOT)
if [ -f "$FILE_ARG" ]; then FILE="$FILE_ARG"
elif [ -f "$ROOT/$FILE_ARG" ]; then FILE="$ROOT/$FILE_ARG"
else echo "FATAL: nie znaleziono pliku: $FILE_ARG" >&2; exit 2; fi

[ -f "$NOTES" ] || { echo "FATAL: brak $NOTES" >&2; exit 2; }

# Detect mode: a "FAZA X" token in the file => FAZA mode, else LIST mode.
FAZA_PREFIX=$(grep -oE 'FAZ[AĄ] [A-Z]{1,3}' "$FILE" | head -1 | sed -E 's/.* //')

PLAN=()           # ordered task ids to run (e.g. "B11" or "FIX767")
declare -A PLAN_LABEL   # tid -> human label for plan printout

if [ -n "$FAZA_PREFIX" ]; then
  # ────────────────────────────── FAZA mode ──────────────────────────────
  MODE="FAZA"
  PREFIX="$FAZA_PREFIX"
  BASE_PROMPT=$(cat "$FILE")

  echo "=== mass-implement (FAZA) ==="
  echo "Prompt   : $FILE"
  echo "FAZA     : $PREFIX"
  echo "Zakres   : ${SELECTOR_ARG:-(wszystkie niezaznaczone)}"
  echo "Tryb     : $( [ "$LIST_ONLY" = 1 ] && echo LIST || echo RUN )"
  echo

  # Extract the FAZA section from notes.md: from "## FAZA <PREFIX>" to next "## ".
  SECTION=$(awk -v p="$PREFIX" '
    $0 ~ "^## FAZA "p"( |—|-|$)" {f=1; next}
    /^## / && f {exit}
    f {print}
  ' "$NOTES")
  if [ -z "$SECTION" ]; then
    SECTION=$(awk -v p="$PREFIX" '
      $0 ~ "^## FAZA "p"[^A-Za-z0-9]" {f=1; next}
      /^## / && f {exit}
      f {print}
    ' "$NOTES")
  fi
  [ -z "$SECTION" ] && { echo "FATAL: nie znalazlem sekcji '## FAZA $PREFIX' w notes.md" >&2; exit 2; }

  # Parse range bounds (numeric). Empty => all.
  RMIN=""; RMAX=""
  if [ -n "$SELECTOR_ARG" ]; then
    rclean=$(echo "$SELECTOR_ARG" | tr 'a-z' 'A-Z' | sed -E 's/[A-Z]//g')
    if echo "$rclean" | grep -qE '^[0-9]+-[0-9]+$'; then
      RMIN=$(echo "$rclean" | cut -d- -f1); RMAX=$(echo "$rclean" | cut -d- -f2)
    elif echo "$rclean" | grep -qE '^[0-9]+$'; then
      RMIN="$rclean"; RMAX="$rclean"
    else
      echo "FATAL: nie rozumiem zakresu '$SELECTOR_ARG' (oczekuje np. B6-B10 albo B6)" >&2; exit 2
    fi
  fi

  while IFS= read -r line; do
    case "$line" in
      "- [ ] "*|"- [x] "*|"- [X] "*) : ;;
      *) continue ;;
    esac
    checked=0
    case "$line" in "- [x] "*|"- [X] "*) checked=1 ;; esac
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
    PLAN_LABEL[$tid]="$tid"
    echo "  [ ] $tid  -> w planie"
  done <<< "$SECTION"

else
  # ────────────────────────────── LIST mode ──────────────────────────────
  MODE="LIST"
  PREFIX="FIX"
  CHILD_PROMPT_FILE="$ROOT/prompt_fix_mass.md"
  [ -f "$CHILD_PROMPT_FILE" ] || { echo "FATAL: brak $CHILD_PROMPT_FILE (prompt dziecka dla LIST mode)" >&2; exit 2; }
  BASE_PROMPT=$(cat "$CHILD_PROMPT_FILE")

  # Self-heal: keep the global 1..n numbering fresh & visible in the file.
  if [ -x "$ROOT/scripts/renumber_fix_list.sh" ]; then
    bash "$ROOT/scripts/renumber_fix_list.sh" "$FILE" >/dev/null 2>&1 || true
  fi

  # Classify selector once.
  SEL="$SELECTOR_ARG"
  selkind="all"; selval=""; smin=""; smax=""
  case "$SEL" in
    "")            selkind="all" ;;
    \#[0-9]*)      selkind="issue";   selval=$(echo "$SEL" | tr -d '#') ;;
    [Pp][0-9]*)    selkind="section"; selval=$(echo "$SEL" | tr 'a-z' 'A-Z') ;;
    [0-9]*-[0-9]*) selkind="range";   smin=${SEL%-*}; smax=${SEL#*-} ;;
    [0-9]*)        selkind="index";   selval="$SEL" ;;
    *) echo "FATAL: nie rozumiem selektora '$SEL' (oczekuje: #767 | P0 | 5 | 3-7 | puste)" >&2; exit 2 ;;
  esac

  echo "=== mass-implement (LIST) ==="
  echo "Lista    : $FILE"
  echo "Prompt   : $CHILD_PROMPT_FILE"
  echo "Selektor : ${SEL:-(wszystkie niezaznaczone)}  [$selkind]"
  echo "Tryb     : $( [ "$LIST_ONLY" = 1 ] && echo LIST || echo RUN )"
  echo

  # Region = "## KOLEJNOŚĆ IMPLEMENTACJI" up to the next "## " heading.
  REGION=$(awk '
    /^## KOLEJNOŚĆ/ {f=1; print; next}
    /^## / && f {exit}
    f {print}
  ' "$FILE")
  [ -z "$REGION" ] && { echo "FATAL: brak sekcji '## KOLEJNOŚĆ IMPLEMENTACJI' w $FILE" >&2; exit 2; }

  section=""
  while IFS= read -r line; do
    case "$line" in
      "### "*) section=$(echo "$line" | grep -oE '^### P[0-9]+' | sed 's/^### //'); continue ;;
    esac
    case "$line" in
      "- [ ] "*|"- [x] "*|"- [X] "*) : ;;
      *) continue ;;
    esac
    checked=0
    case "$line" in "- [x] "*|"- [X] "*) checked=1 ;; esac
    idx=$(echo "$line" | sed -E 's/^- \[[ xX]\] +//' | grep -oE '^[0-9]+' | head -1)
    issue=$(echo "$line" | grep -oE '#[0-9]+' | head -1 | tr -d '#')
    [ -z "$issue" ] && continue

    include=0
    case "$selkind" in
      all)     include=1 ;;
      issue)   [ "$issue" = "$selval" ] && include=1 ;;
      section) [ "$section" = "$selval" ] && include=1 ;;
      index)   [ -n "$idx" ] && [ "$idx" = "$selval" ] && include=1 ;;
      range)   [ -n "$idx" ] && [ "$idx" -ge "$smin" ] 2>/dev/null && [ "$idx" -le "$smax" ] 2>/dev/null && include=1 ;;
    esac
    [ "$include" = 1 ] || continue

    if [ "$checked" = 1 ]; then
      echo "  [x] ${idx:-?}. #$issue  (zrobione — pomijam)"
      continue
    fi
    tid="FIX${issue}"
    PLAN+=("$tid")
    PLAN_LABEL[$tid]="${idx:-?}. #$issue  (${section:-?})"
    echo "  [ ] ${idx:-?}. #$issue  -> w planie  (${section:-?})"
  done <<< "$REGION"
fi

echo
if [ "${#PLAN[@]}" -eq 0 ]; then
  echo "Brak niezaznaczonych zadan w zakresie/selektorze. Nic do zrobienia."
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

for tid in "${PLAN[@]}"; do
  uuid=$(uuidgen)
  sess_name="TASK ${PREFIX}-${tid#$PREFIX}"
  child_log="$STATE_DIR/task_${tid}_${TS}.log"

  echo "▶ ${PLAN_LABEL[$tid]:-$tid}  | sesja: \"$sess_name\"  | id: $uuid" | tee -a "$RUN_LOG"

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
  MASS_STATUS: DONE          — wdrożone, testy zielone, lista zaktualizowana ([x] + [#NNN])
  MASS_STATUS: GATE — <krótki powód po polsku>
  MASS_STATUS: ERROR — <krótki powód po polsku>

──────────────────────────────────────────────────────────
$BASE_PROMPT
EOF
)

  cd "$ROOT" || { echo "MASS_STATUS_RUN: ERROR cd" ; break; }
  # setsid + </dev/null: child runs in its own process group so a SIGHUP to the
  #   launching (parent) Claude session — e.g. when Piotr resumes/closes it — does
  #   NOT reap the child mid-startup (the bug that left "TASK X-N" staged-but-idle).
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
