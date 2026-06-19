#!/usr/bin/env bash
# mass-implement v2 — init helpers.
# The conversational part of `--init` is driven by the AGENT (see SKILL.md):
# it runs `detect`, asks the user for the gaps, writes .claude/mass-implement.json,
# then runs `validate`. This script only does the deterministic bits.
#
# Usage:
#   init.sh detect     # print auto-detected hints as JSON (repo, branch, owner, checklist candidates)
#   init.sh validate   # check .claude/mass-implement.json + that referenced files exist
set -uo pipefail

ROOT="${MASS_ROOT:-$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null || echo "$PWD")}"
CONFIG="${MASS_CONFIG:-$ROOT/.claude/mass-implement.json}"
SUB="${1:-detect}"

detect() {
  local branch owner repo remote
  branch="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"
  remote="$(git -C "$ROOT" remote get-url origin 2>/dev/null || echo '')"
  # owner/repo from git@github.com:owner/repo.git or https://github.com/owner/repo(.git)
  owner="$(echo "$remote" | sed -E 's#.*[:/]([^/]+)/[^/]+(\.git)?$#\1#')"
  repo="$(echo "$remote"  | sed -E 's#.*[:/][^/]+/([^/]+)(\.git)?$#\1#; s#\.git$##')"
  # checklist candidates: markdown files with task checkboxes "- [ ]"
  local cands=()
  while IFS= read -r f; do cands+=("\"${f#$ROOT/}\""); done < <(
    grep -rlE '^- \[[ xX]\] ' "$ROOT" --include='*.md' 2>/dev/null | grep -v '/.claude/' | head -10)
  local cj; cj=$(IFS=,; echo "${cands[*]:-}")
  cat <<JSON
{
  "repo_root": "$ROOT",
  "branch": "${branch}",
  "github": { "owner": "${owner}", "repo": "${repo}" },
  "checklist_candidates": [ ${cj} ]
}
JSON
}

validate() {
  [ -f "$CONFIG" ] || { echo "BŁĄD: brak $CONFIG — najpierw zapisz config." >&2; exit 2; }
  command -v jq >/dev/null || { echo "BŁĄD: brak jq." >&2; exit 2; }
  jq empty "$CONFIG" 2>/dev/null || { echo "BŁĄD: $CONFIG to niepoprawny JSON." >&2; exit 2; }
  local errs=0
  for req in '.version' '.run_host.type' '.branch' '.child.spec_files' '.child.pipeline'; do
    [ "$(jq -r "$req // empty" "$CONFIG")" = "" ] && { echo "BŁĄD: brak wymaganego pola $req"; errs=$((errs+1)); }
  done
  if [ "$(jq -r '.checklists.faza // empty' "$CONFIG")" = "" ] && \
     [ "$(jq -r '.checklists.list // empty' "$CONFIG")" = "" ]; then
    echo "BŁĄD: musi być co najmniej jedno z checklists.faza / checklists.list"; errs=$((errs+1))
  fi
  for key in faza list; do
    local f; f="$(jq -r ".checklists.$key.file // empty" "$CONFIG")"
    [ -n "$f" ] && [ ! -f "$ROOT/$f" ] && { echo "BŁĄD: checklists.$key.file '$f' nie istnieje"; errs=$((errs+1)); }
  done
  for sf in $(jq -r '.child.spec_files[]? ' "$CONFIG"); do
    [ ! -f "$ROOT/$sf" ] && echo "OSTRZEŻENIE: spec_file '$sf' nie istnieje (child go nie przeczyta)"
  done
  if [ "$errs" -eq 0 ]; then
    echo "OK: config poprawny. Następny krok:  /mass-implement <plik> [selektor] --list"
  else
    echo "Znaleziono $errs błąd(ów) — popraw config i waliduj ponownie."; exit 1
  fi
}

case "$SUB" in
  detect)   detect ;;
  validate) validate ;;
  *) echo "Uzycie: init.sh [detect|validate]" >&2; exit 2 ;;
esac
