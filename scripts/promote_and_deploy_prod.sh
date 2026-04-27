#!/usr/bin/env bash
# =============================================================
# promote_and_deploy_prod.sh
# 1) Synchronizuje lokalne gałęzie z origin
# 2) Promuje develop -> main (merge --no-ff)
# 3) Pushuje main
# 4) Uruchamia deploy produkcji
# =============================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

PROMOTE_MESSAGE="${1:-chore: promote develop to main}"

echo "🔍 [1/8] Weryfikacja czystego repo..."
if [ -n "$(git status --porcelain)" ]; then
  echo "❌ BŁĄD: Repo ma niezacommitowane zmiany."
  echo "   Zacommituj/stashuj je i uruchom ponownie."
  exit 1
fi

echo "⬇️  [2/8] Pobieranie zmian z origin..."
git fetch origin

echo "🌿 [3/8] Aktualizacja lokalnego develop..."
git checkout develop
git pull --ff-only origin develop

echo "🌿 [4/8] Aktualizacja lokalnego main..."
git checkout main
git pull --ff-only origin main

echo "🧩 [5/8] Merge develop -> main..."
git merge --no-ff develop -m "$PROMOTE_MESSAGE"

echo "⬆️  [6/8] Push main..."
git push origin main

echo "🔁 [7/8] Aktualizacja develop do nowego main..."
git checkout develop
git merge --ff-only main
git push origin develop

echo "🚀 [8/8] Deploy produkcji..."
git checkout main
"$REPO_DIR/scripts/deploy_prod.sh"
