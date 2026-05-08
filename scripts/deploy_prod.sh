#!/usr/bin/env bash
# =============================================================
# deploy_prod.sh — manual deployment on the dedicated PROD host
# Expected target host: 192.168.1.63
# Expected branch: main
# =============================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

_docker() {
  if docker info >/dev/null 2>&1; then
    docker "$@"
  elif sudo -n docker info >/dev/null 2>&1 || sudo docker info >/dev/null 2>&1; then
    sudo docker "$@"
  else
    echo "❌ BŁĄD: Docker jest niedostępny dla bieżącego użytkownika."
    echo "   Zaloguj się ponownie po dodaniu do grupy docker albo uruchom przez sudo."
    exit 1
  fi
}

compose() {
  _docker compose -f docker-compose.yml "$@"
}

echo "🔍 [1/5] Weryfikacja hosta i repo..."
HOST_IPS="$(hostname -I 2>/dev/null || true)"
if [[ " ${HOST_IPS} " == *" 192.168.1.61 "* ]]; then
  echo "❌ BŁĄD: Ten skrypt nie powinien być uruchamiany na hoście DEV (.61)."
  echo "   Produkcja ma być wdrażana na dedykowanej maszynie PROD (.63)."
  exit 1
fi

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [[ "$CURRENT_BRANCH" != "main" ]]; then
  echo "❌ BŁĄD: Jesteś na '$CURRENT_BRANCH', a nie 'main'."
  echo "   Wykonaj: git checkout main && git pull --ff-only origin main"
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "❌ BŁĄD: Masz niezacommitowane zmiany."
  echo "   Zacommituj/stashuj je przed deployem."
  exit 1
fi

if [[ ! -f data/ai_gm.db ]]; then
  echo "❌ BŁĄD: Brak pliku bazy 'data/ai_gm.db'."
  echo "   Dla świeżej maszyny użyj najpierw ./install.sh (lub przywróć DB), a potem ponów deploy."
  exit 1
fi

echo "📦 [2/5] Backup bazy danych..."
BACKUP_FILE="backups/ai_gm_pre_deploy_$(date +%Y%m%d_%H%M%S).db"
mkdir -p backups
cp data/ai_gm.db "$BACKUP_FILE"
echo "   Backup: $BACKUP_FILE"

echo "⬇️  [3/5] Aktualizacja kodu z origin/main..."
git fetch origin
git pull --ff-only origin main

echo "🐳 [4/5] Restart kontenerów PROD..."
compose up -d --build --remove-orphans

echo "⏳ [5/5] Healthcheck backendu (max 120s)..."
for i in $(seq 1 24); do
  if curl -sf http://localhost:8000/api/healthz > /dev/null; then
    echo "✅ Deployment zakończony sukcesem!"
    echo "   Prod UI: http://localhost:3001"
    echo "   Prod API: http://localhost:8000/api"
    echo "   Voice: http://localhost:8300/voice/healthz"
    exit 0
  fi
  echo "   Próba $i/24 — czekam 5s..."
  sleep 5
done

echo "❌ Backend nie odpowiada po 120s."
echo "   Sprawdź: docker compose -f docker-compose.yml logs backend --tail=50"
exit 1
