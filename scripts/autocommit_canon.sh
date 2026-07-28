#!/usr/bin/env bash
# #1551 — auto-commit kanonu mapy po „Pieczętuj kanon" (admin→Mapa).
#
# Uruchamiany przez systemd path unit (aigm-canon-autocommit.path) gdy zmienią
# się pliki data/regions/. Działa jako piotrszmidt (tożsamość git repo), więc
# Piotr nie musi prosić o commit po każdej pieczęci.
#
# Bezpieczeństwo: commituje WYŁĄCZNIE pliki kanonu (data/regions + legacy seed),
# nigdy nie sweepuje innych zmian roboczych.
set -euo pipefail

REPO=/home/piotrszmidt/ai-gm
cd "$REPO"

# Pojedyncza instancja — systemd path retriggeruje per plik; flock serializuje,
# a batch (sleep) zbiera cały snapshot „wszystkie krainy" w jeden commit.
exec 200>/tmp/aigm_canon_autocommit.lock
flock -n 200 || exit 0

sleep 4   # poczekaj aż endpoint dopisze wszystkie region_*.json

PATHS=(data/regions docs/world/world_map_seed.json)

# Nic do zrobienia?
if git diff --quiet -- "${PATHS[@]}" 2>/dev/null \
   && git diff --cached --quiet -- "${PATHS[@]}" 2>/dev/null; then
  exit 0
fi

git add -- "${PATHS[@]}"
if git diff --cached --quiet -- "${PATHS[@]}"; then
  exit 0   # add nic nie dodał (np. same ignorowane zmiany)
fi

TS="$(date '+%Y-%m-%d %H:%M')"
git commit -m "chore(map): auto-snapshot kanonu [$TS]" \
  -m "Auto-commit po Pieczętuj kanon (admin→Mapa, #1551)." \
  -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>" || exit 0

# Push best-effort — brak zdalnego auth nie może wywalić commita lokalnego.
git push origin develop >/dev/null 2>&1 || true
