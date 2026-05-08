#!/usr/bin/env bash
# =============================================================
# promote_and_deploy_prod.sh
# Legacy convenience helper:
# 1) Synchronizuje lokalne gałęzie z origin
# 2) Promuje develop -> main (merge --no-ff)
# 3) Pushuje main
# 4) Uruchamia lokalny deploy produkcji
#
# For the dedicated PROD model prefer:
# - promote develop -> main from workstation / GitHub
# - run ./scripts/deploy_prod.sh only on the dedicated PROD host
# =============================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

PROMOTE_MESSAGE="${1:-chore: promote develop to main}"

HOST_IPS="$(hostname -I 2>/dev/null || true)"
if [[ " ${HOST_IPS} " == *" 192.168.1.63 "* ]]; then
  echo "❌ BŁĄD: Nie uruchamiaj promote_and_deploy_prod.sh bezpośrednio na dedykowanym hoście PROD (.63)."
  echo "   Najpierw wypromuj develop -> main poza hostem produkcyjnym, a na .63 użyj tylko ./scripts/deploy_prod.sh."
  exit 1
fi

echo "⚠️  Uwaga: to jest skrypt legacy. W nowym modelu preferowany jest osobny promote + osobny deploy na .63."

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
