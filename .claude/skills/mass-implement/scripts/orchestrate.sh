#!/usr/bin/env bash
# mass-implement v2 orchestrator — config-driven, robust, drop-in.
#
# Reads project invariants from .claude/mass-implement.json (no hardcode).
# Builds the child prompt from the built-in template (references/prompt-template.md)
# + the inline ZAKRES block in the task doc. Spawns ONE real, named, resumable
# `claude` session per task, sequentially.
#
# Usage: orchestrate.sh <file> [selector] [--list]
#   FAZA mode: <file> contains a "FAZA X" token; tasks from config.checklists.faza.file
#   LIST mode: otherwise; tasks from config.checklists.list.file
#   --list: print the plan and exit (spawn nothing)
#
# Preflight (fail-loud, not silent-wrong):
#   merge markers / unparseable region  -> REFUSE whole run
#   ambiguous task line in selected set -> SKIP + report (never silently drop)
#   per-task already-done               -> child emits DONE-ALREADY (handled here)
set -uo pipefail

# ── Locate repo root + config ────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATE="$SKILL_DIR/references/prompt-template.md"

ROOT="${MASS_ROOT:-$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null || echo "$PWD")}"
CONFIG="${MASS_CONFIG:-$ROOT/.claude/mass-implement.json}"

if [ ! -f "$CONFIG" ]; then
  echo "FATAL: brak configu $CONFIG" >&2
  echo "       Uruchom najpierw:  /mass-implement --init" >&2
  exit 2
fi
command -v jq >/dev/null || { echo "FATAL: brak 'jq' (wymagane do czytania configu)" >&2; exit 2; }
[ -f "$TEMPLATE" ] || { echo "FATAL: brak szablonu $TEMPLATE" >&2; exit 2; }

cfg() { jq -r "$1 // empty" "$CONFIG"; }

BRANCH="$(cfg '.branch')"
GH_OWNER="$(cfg '.github.owner')"; GH_REPO="$(cfg '.github.repo')"
GITHUB="$( [ -n "$GH_OWNER" ] && echo "${GH_OWNER}/${GH_REPO}" || echo "(brak GitHub)" )"
SPEC_FILES="$(jq -r '.child.spec_files | join(", ")' "$CONFIG")"
PIPELINE="$(jq -r '.child.pipeline | join(" → ")' "$CONFIG")"
RUN_TYPE="$(cfg '.run_host.type')"
RUN_HOST="$(cfg '.run_host.host')"; RUN_GITUSER="$(cfg '.run_host.git_user')"
RUN_REMOTE="$(cfg '.run_host.remote_root')"

STATE_DIR="$SKILL_DIR/.runs"; mkdir -p "$STATE_DIR"

# ── Args ─────────────────────────────────────────────────────────────────────
# Allow "faza X [sel]" with FAZA as a separate leading word: /mass-implement faza S
case "${1:-}" in [Ff][Aa][Zz][AaĄą]) shift ;; esac
FILE_ARG="${1:-}"; SELECTOR_ARG="${2:-}"; LIST_ONLY=0
for a in "$@"; do [ "$a" = "--list" ] && LIST_ONLY=1; done
[ "$SELECTOR_ARG" = "--list" ] && SELECTOR_ARG=""
[ -n "$FILE_ARG" ] || { echo "FATAL: brak pliku. Uzycie: orchestrate.sh <plik> [selektor] [--list]" >&2; exit 2; }

# arg1 may be a FILE (a list like fix_list.md, or a legacy prompt carrying a "FAZA X" token)
# OR a bare FAZA token: "L", "SF", "FAZA L", "faza:L".
FILE=""; FAZA_PREFIX=""
if [ -f "$FILE_ARG" ]; then FILE="$FILE_ARG"
elif [ -f "$ROOT/$FILE_ARG" ]; then FILE="$ROOT/$FILE_ARG"
else
  tok=$(echo "$FILE_ARG" | sed -E 's/^[Ff][Aa][Zz][AaĄą][: ]*//')
  if echo "$tok" | grep -qE '^[A-Z]{1,3}$'; then FAZA_PREFIX="$tok"
  else echo "FATAL: '$FILE_ARG' to nie plik ani token fazy (np. L, SF, 'FAZA L')." >&2; exit 2; fi
fi

# ── Mode detection ───────────────────────────────────────────────────────────
if [ -z "$FAZA_PREFIX" ] && [ -n "$FILE" ]; then
  FAZA_PREFIX=$(grep -oE 'FAZ[AĄ] [A-Z]{1,3}' "$FILE" 2>/dev/null | head -1 | sed -E 's/.* //')
fi
if [ -n "$FAZA_PREFIX" ]; then MODE="FAZA"; else MODE="LIST"; fi

# ── Preflight: refuse on structural corruption ───────────────────────────────
preflight_refuse() {
  local f="$1"
  if grep -qnE '^(<<<<<<<|=======|>>>>>>>)' "$f"; then
    echo "FATAL (preflight): plik $f ma NIEROZWIĄZANY konflikt merge:" >&2
    grep -nE '^(<<<<<<<|=======|>>>>>>>)' "$f" | head -6 | sed 's/^/  linia /' >&2
    echo "  → Napraw konflikt i odpal ponownie. NIC nie uruchomiono." >&2
    exit 2
  fi
}

PLAN=(); declare -A PLAN_LABEL; SKIPPED=()

# Determine which checklist file holds the task statuses for this mode.
if [ "$MODE" = "FAZA" ]; then
  CL_FILE="$ROOT/$(jq -r '.checklists.faza.file' "$CONFIG")"
  SECTION_PREFIX="$(jq -r '.checklists.faza.section_prefix // "## FAZA"' "$CONFIG")"
  ID_PAT="$(jq -r '.checklists.faza.id_pattern // "{PREFIX}[0-9]+[a-z]?"' "$CONFIG" | sed "s/{PREFIX}/$FAZA_PREFIX/")"
  PREFIX="$FAZA_PREFIX"
else
  CL_FILE="$ROOT/$(jq -r '.checklists.list.file' "$CONFIG")"
  REGION_PREFIX="$(jq -r '.checklists.list.region_prefix // "## KOLEJNOŚĆ"' "$CONFIG")"
  PREFIX="$(jq -r '.checklists.list.id_prefix // "FIX"' "$CONFIG")"
  RENUM="$(jq -r '.checklists.list.renumber_script // empty' "$CONFIG")"
fi
[ -f "$CL_FILE" ] || { echo "FATAL: brak pliku checklisty $CL_FILE (z configu)" >&2; exit 2; }
preflight_refuse "$CL_FILE"
[ -n "$FILE" ] && [ "$FILE" != "$CL_FILE" ] && preflight_refuse "$FILE"

echo "=== mass-implement v2 ($MODE) ==="
echo "Repo     : $ROOT"
echo "Plik     : $FILE"
echo "Checklist: $CL_FILE"
echo "Selektor : ${SELECTOR_ARG:-(wszystkie niezaznaczone)}"
echo "Tryb     : $( [ "$LIST_ONLY" = 1 ] && echo LIST || echo RUN )"
echo

# ── Parse tasks ──────────────────────────────────────────────────────────────
if [ "$MODE" = "FAZA" ]; then
  SECTION=$(awk -v p="$SECTION_PREFIX $FAZA_PREFIX" '
    index($0, p)==1 {f=1; next}
    /^## / && f {exit}
    f {print}' "$CL_FILE")
  [ -z "$SECTION" ] && { echo "FATAL: nie znalazłem sekcji '$SECTION_PREFIX $FAZA_PREFIX' w $CL_FILE" >&2; exit 2; }

  RMIN=""; RMAX=""
  if [ -n "$SELECTOR_ARG" ]; then
    rclean=$(echo "$SELECTOR_ARG" | tr 'a-z' 'A-Z' | sed -E 's/[A-Z]//g')
    if echo "$rclean" | grep -qE '^[0-9]+-[0-9]+$'; then RMIN=${rclean%-*}; RMAX=${rclean#*-}
    elif echo "$rclean" | grep -qE '^[0-9]+$'; then RMIN="$rclean"; RMAX="$rclean"
    else echo "FATAL: nie rozumiem zakresu '$SELECTOR_ARG'" >&2; exit 2; fi
  fi

  while IFS= read -r line; do
    case "$line" in "- [ ] "*|"- [x] "*|"- [X] "*) : ;; *) continue ;; esac
    checked=0; case "$line" in "- [x] "*|"- [X] "*) checked=1 ;; esac
    rest=$(echo "$line" | sed -E 's/^- \[[ xX]\] +//' | sed -E 's/^\[#?[0-9]+\][^—]*—[[:space:]]*//')
    tid=$(echo "$rest" | grep -oE "^$ID_PAT" | head -1)
    if [ -z "$tid" ]; then
      [ "$checked" = 0 ] && SKIPPED+=("niejednoznaczna linia: ${line:0:60}")
      continue
    fi
    num=$(echo "$tid" | grep -oE '[0-9]+' | head -1)
    if [ -n "$RMIN" ]; then [ "$num" -lt "$RMIN" ] && continue; [ "$num" -gt "$RMAX" ] && continue; fi
    if [ "$checked" = 1 ]; then echo "  [x] $tid  (zrobione — pomijam)"; continue; fi
    PLAN+=("$tid"); PLAN_LABEL[$tid]="$tid"; echo "  [ ] $tid  -> w planie"
  done <<< "$SECTION"

else
  [ -n "${RENUM:-}" ] && [ -x "$ROOT/$RENUM" ] && bash "$ROOT/$RENUM" "$FILE" >/dev/null 2>&1 || true
  SEL="$SELECTOR_ARG"; selkind="all"; selval=""; smin=""; smax=""
  case "$SEL" in
    "")            selkind="all" ;;
    \#[0-9]*)      selkind="issue";   selval=${SEL#\#} ;;
    [Pp][0-9]*)    selkind="section"; selval=$(echo "$SEL" | tr 'a-z' 'A-Z') ;;
    [0-9]*-[0-9]*) selkind="range";   smin=${SEL%-*}; smax=${SEL#*-} ;;
    [0-9]*)        selkind="index";   selval="$SEL" ;;
    *) echo "FATAL: nie rozumiem selektora '$SEL' (#767 | P0 | 5 | 3-7 | puste)" >&2; exit 2 ;;
  esac

  REGION=$(awk -v p="$REGION_PREFIX" '
    index($0,p)==1 {f=1; print; next}
    /^## / && f {exit}
    f {print}' "$FILE")
  [ -z "$REGION" ] && { echo "FATAL: brak sekcji '$REGION_PREFIX' w $FILE" >&2; exit 2; }

  section=""
  while IFS= read -r line; do
    case "$line" in "### "*) section=$(echo "$line" | grep -oE '^### P[0-9]+' | sed 's/^### //'); continue ;; esac
    case "$line" in "- [ ] "*|"- [x] "*|"- [X] "*) : ;; *) continue ;; esac
    checked=0; case "$line" in "- [x] "*|"- [X] "*) checked=1 ;; esac
    idx=$(echo "$line" | sed -E 's/^- \[[ xX]\] +//' | grep -oE '^[0-9]+' | head -1)
    issue=$(echo "$line" | grep -oE '#[0-9]+' | head -1 | tr -d '#')
    if [ -z "$issue" ]; then
      [ "$checked" = 0 ] && SKIPPED+=("brak #issue: ${line:0:60}")
      continue
    fi
    include=0
    case "$selkind" in
      all) include=1 ;;
      issue) [ "$issue" = "$selval" ] && include=1 ;;
      section) [ "$section" = "$selval" ] && include=1 ;;
      index) [ -n "$idx" ] && [ "$idx" = "$selval" ] && include=1 ;;
      range) [ -n "$idx" ] && [ "$idx" -ge "$smin" ] 2>/dev/null && [ "$idx" -le "$smax" ] 2>/dev/null && include=1 ;;
    esac
    [ "$include" = 1 ] || continue
    if [ "$checked" = 1 ]; then echo "  [x] ${idx:-?}. #$issue  (zrobione — pomijam)"; continue; fi
    tid="${PREFIX}${issue}"; PLAN+=("$tid")
    PLAN_LABEL[$tid]="${idx:-?}. #$issue  (${section:-?})"
    echo "  [ ] ${idx:-?}. #$issue  -> w planie  (${section:-?})"
  done <<< "$REGION"
fi

# ── Extract inline ZAKRES from the section ──────────────────────────────────
extract_zakres() {
  awk '/<!-- MASS-ZAKRES:START -->/{f=1;next} /<!-- MASS-ZAKRES:END -->/{f=0} f' "$1" | head -200
}
ZAKRES="$(extract_zakres "$CL_FILE")"
[ -z "$ZAKRES" ] && [ -n "$FILE" ] && ZAKRES="$(extract_zakres "$FILE")"
if [ -z "$ZAKRES" ]; then
  ZAKRES="(brak bloku MASS-ZAKRES — działam na samym opisie zadania i zasadach projektu)"
  echo "  ⚠ uwaga: brak bloku ZAKRES w checkliście — child użyje tylko opisu zadania."
fi
if [ "$RUN_TYPE" = "ssh" ] && [ -n "$RUN_HOST" ]; then
  ZAKRES="**Środowisko:** komendy runtime/git przez SSH \`$RUN_HOST\` (repo \`$RUN_REMOTE\`, git jako \`$RUN_GITUSER\`).

$ZAKRES"
fi

echo
[ "${#SKIPPED[@]}" -gt 0 ] && { echo "POMINIĘTE (niejednoznaczne, ${#SKIPPED[@]}):"; printf '  • %s\n' "${SKIPPED[@]}"; echo; }
if [ "${#PLAN[@]}" -eq 0 ]; then echo "Brak niezaznaczonych zadań w zakresie. Nic do zrobienia."; exit 0; fi
echo "Plan (${#PLAN[@]}): ${PLAN[*]}"
echo
[ "$LIST_ONLY" = 1 ] && { echo "(--list: nie odpalam sesji)"; exit 0; }

# ── Build child prompt from template ─────────────────────────────────────────
BASE_TEMPLATE="$(cat "$TEMPLATE")"
fill() { local t="$1"; t="${t//\{ID\}/$2}"; t="${t//\{SPEC_FILES\}/$SPEC_FILES}";
  t="${t//\{PIPELINE\}/$PIPELINE}"; t="${t//\{GITHUB\}/$GITHUB}"; t="${t//\{BRANCH\}/$BRANCH}";
  t="${t//\{ZAKRES\}/$ZAKRES}"; printf '%s' "$t"; }

TS=$(date +%Y%m%d_%H%M%S)
RUN_LOG="$STATE_DIR/run_${PREFIX}_${TS}.log"; SUMMARY="$STATE_DIR/run_${PREFIX}_${TS}.summary"; : > "$SUMMARY"
echo "Run log : $RUN_LOG"; echo "Summary : $SUMMARY"; echo
[ "${#SKIPPED[@]}" -gt 0 ] && printf 'SKIPPED-AMBIGUOUS | %s\n' "${SKIPPED[@]}" >> "$SUMMARY"

for tid in "${PLAN[@]}"; do
  uuid=$(uuidgen); sess_name="TASK ${PREFIX}-${tid#$PREFIX}"; child_log="$STATE_DIR/task_${tid}_${TS}.log"
  echo "▶ ${PLAN_LABEL[$tid]:-$tid}  | sesja: \"$sess_name\"  | id: $uuid" | tee -a "$RUN_LOG"

  child_prompt="[MASS-IMPLEMENT — sterowanie automatyczne]
Twoje JEDNO zadanie w tej sesji to DOKŁADNIE: ${tid}. Pracuj tylko nad nim, w trybie auto.

$(fill "$BASE_TEMPLATE" "$tid")"

  cd "$ROOT" || { echo "ERROR cd"; break; }
  setsid env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT -u CLAUDE_CODE_SESSION_ID \
      -u CLAUDE_CODE_CHILD_SESSION -u CLAUDE_CODE_EXECPATH -u AI_AGENT \
    claude -p --name "$sess_name" --session-id "$uuid" --add-dir "$ROOT" \
      --dangerously-skip-permissions --output-format text \
      "$child_prompt" </dev/null > "$child_log" 2>&1
  rc=$?

  status=$(grep -oE 'MASS_STATUS: (DONE-ALREADY|DONE|GATE|ERROR)[^\n]*' "$child_log" | tail -1)
  [ -z "$status" ] && status="MASS_STATUS: ERROR — brak markera (rc=$rc); zobacz $child_log"
  echo "  $tid -> $status" | tee -a "$RUN_LOG"
  echo "$tid | $sess_name | $uuid | $status | $child_log" >> "$SUMMARY"

  case "$status" in
    *"MASS_STATUS: DONE-ALREADY"*) echo "  ✔ już zrobione (odhaczone) — dalej" | tee -a "$RUN_LOG" ;;
    *"MASS_STATUS: DONE"*)         echo "  ✔ dalej" | tee -a "$RUN_LOG" ;;
    *) echo "  ⛔ STOP — bramka/błąd na $tid. Reszta wstrzymana." | tee -a "$RUN_LOG"
       echo "STOPPED_AT=$tid" >> "$SUMMARY"
       echo; echo "=== KONIEC (zatrzymano na $tid) ==="
       echo "Wznów sesję:  claude --resume $uuid"; exit 3 ;;
  esac
  echo
done

echo "=== KONIEC — wszystkie zaplanowane zadania DONE ==="
cat "$SUMMARY"; exit 0
