<!-- STATUS: PENDING -->
<!-- REV: 1 | DATE: 2026-04-27 -->

# PROMPT 1 — Phase 0: Rozdzielenie środowisk Prod / Dev

> **Workflow tego pliku:**
> 1. Perplexity generuje prompt (REV 1) i zadaje pytania blokujące
> 2. Cursor odpowiada → właściciel wkleja odpowiedzi poniżej sekcji `## Odpowiedzi Cursora`
> 3. Perplexity poprawia prompt (REV 2) → daje zielone światło
> 4. Cursor implementuje
> 5. Cursor uzupełnia sekcję `## Co zostało zrobione` na końcu tego pliku
> 6. Właściciel wkleja odpowiedź Cursora do Perplexity
> 7. Perplexity dopisuje `## Notatki po implementacji` i zmienia STATUS na DONE
> 8. Plik zostaje przemianowany na `PROMPT 1 — Prod Dev Split_DONE.md`

---

## Cel

Rozdzielić środowisko na maszynie `.61` na **produkcję** (port 3001, branch `main`) i **development** (port 3002, branch `develop`), bez naruszania istniejącego stacku produkcyjnego. Przygotować skrypty deployu i dokumentację procedury awansu kodu z dev na prod.

---

## Kontekst techniczny

- Repo: `szmidtpiotr/ai-gm`
- Obecny stack prod: `docker-compose.yml`, frontend `:3001`, backend `:8000`
- Baza danych: `data/ai_gm.db` (SQLite)
- CI: brak (ręczny deploy przez SSH)
- Istniejące skrypty: `scripts/backup.sh`, `scripts/restore.sh`, `scripts/db-autosync.sh`

---

## ⛔ PRZED IMPLEMENTACJĄ — Cursor odpowiada na pytania blokujące

Zanim zaczniesz cokolwiek zmieniać, **przeczytaj poniższe pytania i odpowiedz na każde z nich**. Dopiero po moim potwierdzeniu przechodzisz do implementacji.

1. **Ścieżka projektu na serwerze** — jaka jest pełna ścieżka katalogu projektu na maszynie `.61`? (np. `/home/ubuntu/ai-gm`)
2. **Gałąź `develop`** — czy branch `develop` już istnieje lokalnie lub na GitHubie? Wykonaj: `git branch -a | grep develop`
3. **Konflikty portów** — czy porty `3002` i `8100` są już zajęte na maszynie? Wykonaj: `ss -tlnp | grep -E '3002|8100'`
4. **Istniejący `docker-compose.dev.yml`** — czy plik `docker-compose.dev.yml` już istnieje w katalogu projektu? Wykonaj: `ls -la docker-compose*.yml`
5. **Katalog `data-dev/`** — czy istnieje osobny katalog na bazę dev? Wykonaj: `ls -la data*/`
6. **Subdomena dev** — czy DNS dla subdomeny dev jest już skonfigurowany i wskazuje na maszynę `.61`?
7. **Czy cokolwiek w `docker-compose.yml` było niedawno edytowane lokalnie (unstaged changes)?** Wykonaj: `git status`

**Jeśli którakolwiek odpowiedź wskazuje na bloker (zajęty port, istniejący plik z inną treścią, brudne working tree) — NIE implementuj i powiedz mi o tym zanim cokolwiek zmienisz.**

---

## Implementacja (REV 1 — do zatwierdzenia po odpowiedziach)

### 1. Backup obecnego stanu

```bash
git add -A
git commit -m "chore: backup before Phase 0 prod/dev split" --allow-empty
git push origin main
git tag -a v0.0-pre-phase0 -m "Backup before prod/dev split"
git push origin v0.0-pre-phase0
```

### 2. Utwórz branch `develop`

```bash
git checkout -b develop
git push origin develop
git checkout main
```

### 3. Stwórz `docker-compose.dev.yml`

Utwórz plik `docker-compose.dev.yml` w katalogu głównym projektu:

```yaml
# DEV environment — frontend: :3002, backend: :8100
# DO NOT use on production. Use docker-compose.yml for prod.
name: ai-gm-dev

services:
  backend:
    build:
      context: ./backend
    restart: unless-stopped
    healthcheck:
      test:
        [
          "CMD",
          "python3",
          "-c",
          "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/healthz', timeout=5).read()",
        ]
      interval: 15s
      timeout: 6s
      retries: 5
      start_period: 90s
    ports:
      - "8100:8000"
    environment:
      - OLLAMA_LOAD_TIMEOUT=300s
      - OLLAMA_TIMEOUT=240
      - LLM_PROVIDER=${LLM_PROVIDER:-ollama}
      - LLM_BASE_URL=${LLM_BASE_URL:-http://host.docker.internal:11434}
      - LLM_MODEL=${LLM_MODEL:-gemma4:e4b}
      - LLM_API_KEY=${LLM_API_KEY:-}
      - DEFAULT_CAMPAIGN_LANGUAGE=${DEFAULT_CAMPAIGN_LANGUAGE:-pl}
      - GAME_LANG=${GAME_LANG:-pl-PL}
      - DATABASE_URL=${DATABASE_URL:-sqlite:////data/ai_gm_dev.db}
    extra_hosts:
      - "host.docker.internal:host-gateway"
    volumes:
      - ./data-dev:/data
    labels:
      - service=backend-dev
    networks:
      - ai-gm-dev

  frontend:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "3002:80"
    volumes:
      - ./frontend:/usr/share/nginx/html:ro
      - ./frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - backend
    networks:
      - ai-gm-dev

networks:
  ai-gm-dev:
    driver: bridge
```

### 4. Stwórz katalog `data-dev/` i przenieś kopię bazy

```bash
mkdir -p data-dev
cp data/ai_gm.db data-dev/ai_gm_dev.db
```

### 5. Utwórz `scripts/deploy_prod.sh`

```bash
#!/usr/bin/env bash
# =============================================================
# deploy_prod.sh — Deployment PRODUKCJA (port 3001 / 8000)
# Wywołaj TYLKO po zmergowaniu develop → main
# =============================================================
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

echo "🔍 [1/5] Sprawdzanie gałęzi..."
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "main" ]; then
  echo "❌ BŁĄD: Jesteś na '$CURRENT_BRANCH', a nie 'main'."
  echo "   Wykonaj: git checkout main && git pull origin main"
  exit 1
fi

echo "📦 [2/5] Backup bazy danych..."
BACKUP_FILE="backups/ai_gm_pre_deploy_$(date +%Y%m%d_%H%M%S).db"
mkdir -p backups
cp data/ai_gm.db "$BACKUP_FILE"
echo "   Backup: $BACKUP_FILE"

echo "⬇️  [3/5] Pull z main..."
git fetch origin
git pull origin main

echo "🐳 [4/5] Restart kontenerów prod..."
docker compose -f docker-compose.yml up -d --build --remove-orphans

echo "⏳ [5/5] Healthcheck (max 60s)..."
for i in $(seq 1 12); do
  if curl -sf http://localhost:8000/api/healthz > /dev/null; then
    echo "✅ Deployment zakończony sukcesem!"
    echo "   Prod: http://localhost:3001"
    exit 0
  fi
  echo "   Próba $i/12 — czekam 5s..."
  sleep 5
done
echo "❌ Backend nie odpowiada po 60s."
echo "   docker compose logs backend --tail=50"
exit 1
```

### 6. Utwórz `scripts/deploy_dev.sh`

```bash
#!/usr/bin/env bash
# =============================================================
# deploy_dev.sh — Deployment DEV (port 3002 / 8100)
# =============================================================
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

echo "⬇️  [1/3] Pull z develop..."
git fetch origin
git checkout develop
git pull origin develop

echo "🐳 [2/3] Restart kontenerów dev..."
docker compose -f docker-compose.dev.yml up -d --build --remove-orphans

echo "⏳ [3/3] Healthcheck dev (max 60s)..."
for i in $(seq 1 12); do
  if curl -sf http://localhost:8100/api/healthz > /dev/null; then
    echo "✅ Dev deployment zakończony!"
    echo "   Dev: http://localhost:3002"
    exit 0
  fi
  echo "   Próba $i/12 — czekam 5s..."
  sleep 5
done
echo "❌ Dev backend nie odpowiada."
echo "   docker compose -f docker-compose.dev.yml logs backend --tail=50"
exit 1
```

### 7. Nadaj uprawnienia do skryptów

```bash
chmod +x scripts/deploy_prod.sh scripts/deploy_dev.sh
```

### 8. Utwórz dokumentację

Utwórz pliki:
- `docs/Phase 0 - Prod Dev Environment/README.md`
- `docs/Phase 0 - Prod Dev Environment/DEPLOYMENT_PROCEDURE.md`

Treści tych plików znajdziesz w plikach `README.md` i `DEPLOYMENT_PROCEDURE.md` w tym samym folderze.

### 9. Commit całości

```bash
git add -A
git commit -m "feat: Phase 0 — prod/dev environment split

- Add docker-compose.dev.yml (dev stack, ports 3002/8100)
- Add scripts/deploy_prod.sh with pre-deploy DB backup + healthcheck
- Add scripts/deploy_dev.sh
- Add data-dev/ with initial copy of prod DB
- Add docs/Phase 0 - Prod Dev Environment/"
git push origin main
git tag -a v0.1-phase0-complete -m "Phase 0: prod/dev environment implemented"
git push origin v0.1-phase0-complete
```

---

## Odpowiedzi Cursora (REV 1)

> *(Wklej tutaj odpowiedzi Cursora na pytania blokujące z sekcji "PRZED IMPLEMENTACJĄ")*

```
[MIEJSCE NA ODPOWIEDZI CURSORA]
```

---

## Co zostało zrobione *(uzupełnia Cursor po implementacji)*

> *(Cursor uzupełnia tę sekcję po zakończeniu implementacji. Należy wymienić: jakie pliki zostały stworzone/zmodyfikowane, jakie komendy wykonano, czy healthcheck przeszedł, czy tagi zostały wypchnięte.)*

```
[MIEJSCE NA RAPORT CURSORA]
```

---

## Notatki po implementacji *(uzupełnia Perplexity)*

> *(Ta sekcja zostanie uzupełniona przez Perplexity po wklejeniu raportu Cursora. Nie edytuj ręcznie.)*

```
[MIEJSCE NA NOTATKI PERPLEXITY]
```
