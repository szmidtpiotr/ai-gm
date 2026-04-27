<!-- STATUS: IN_PROGRESS -->
<!-- REV: 2 | DATE: 2026-04-27 -->

# PROMPT 1 — Phase 0: Rozdzielenie środowisk Prod / Dev

> **Workflow tego pliku:**
> 1. ✅ Perplexity generował prompt (REV 1) i zadawał pytania blokujące
> 2. ✅ Cursor odpowiedział → właściciel wkleił odpowiedzi poniżej
> 3. ✅ Perplexity przeanalizował odpowiedzi → wygenerował REV 2 z planem odblokowania
> 4. ⏸️ Cursor wykonał check — STOP (brudne drzewo git)
> 5. ✅ Bloker zidentyfikowany i rozwiązany: `docs/` usuniete celowo, commit potrzebny
> 6. 🔴 **NASTĘPNY KROK:** Cursor commituje usunięcia i przechodzi do Kroku 1
> 7. Cursor uzupełnia sekcję `## Co zostało zrobione` raportem końcowym
> 8. Właściciel wkleja raport do Perplexity
> 9. Perplexity finalizuje notatki i zmienia STATUS na DONE
> 10. Plik zostaje przemianowany na `PROMPT 1 — Prod Dev Split_DONE.md`

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
- Istnieje też: `docker-compose.override.yml` (zachować!)

---

## Odpowiedzi Cursora (REV 1)

```
1. Ścieżka projektu: /home/piotrszmidt/ai-gm

2. Gałąź develop: NIE istnieje ani lokalnie, ani na origin.
   Widoczne branche: main, phase-3.2-roll-system, inne.
   → Trzeba utworzyć.

3. Porty 3002 i 8100: WOLNE. Brak wpisów w ss -tlnp.

4. docker-compose.dev.yml: NIE istnieje.
   Obecne: docker-compose.yml, docker-compose.override.yml

5. data-dev/: NIE istnieje. Jest tylko data/ z ai_gm.db.

6. DNS subdomeny dev: NIEZNANY — brak danych o nazwie subdomeny.

7. git status: BRUDNE drzewo robocze — wiele plików w docs/
   oznaczonych jako usunięte (D ...). To jest bloker.
```

---

## Analiza blokerów (Perplexity REV 2)

### Bloker 1 — Brudne working tree ✅ ROZWIĄZANY

**Diagnoza:** Pliki w `docs/Phase 8A/`, `docs/Phase 8B/`, `docs/figma-handoff/` były przechowywane tylko lokalnie na `.61` i nie ma ich na GitHubie. Właściciel potwierdził: **te pliki mają być usunięte z śledzenia git** — nie muszą być na GitHubie. Wybrana Opcja B: commit usunięć.

**Komenda do wykonania przed Krokiem 1:**
```bash
cd /home/piotrszmidt/ai-gm
git add -A
git commit -m "chore: remove local-only docs from git tracking (Phase 8A/8B, figma-handoff)"
git push origin main
git status  # powinno pokazać: nothing to commit, working tree clean
```

### Bloker 2 — DNS subdomeny dev

**Decyzja:** Nie blokuje. Stack dev działa na `IP:3002` bez subdomeny. DNS później.

---

## Implementacja (REV 2) — Cursor wykonuje

> **UWAGA dla Cursora:** Zanim zaczniesz Krok 1, wykonaj commit usunięć opisany w sekcji "Bloker 1" powyżej.

### Krok 0 — Commit usunięć (odblokowanie git)

```bash
cd /home/piotrszmidt/ai-gm
git add -A
git commit -m "chore: remove local-only docs from git tracking (Phase 8A/8B, figma-handoff)"
git push origin main
# Weryfikacja:
git status
# Oczekiwane: nothing to commit, working tree clean
```

### Krok 1 — Backup + tag bezpieczeństwa

```bash
git tag -a v0.0-pre-phase0 -m "Backup before prod/dev split"
git push origin v0.0-pre-phase0
```

### Krok 2 — Utwórz branch `develop`

```bash
git checkout -b develop
git push origin develop
git checkout main
```

### Krok 3 — Stwórz `docker-compose.dev.yml`

Utwórz plik `docker-compose.dev.yml` w katalogu głównym projektu.

> ⚠️ Uwaga: istnieje `docker-compose.override.yml` — **nie ruszaj go**.

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

### Krok 4 — Katalog `data-dev/` + kopia bazy

```bash
mkdir -p data-dev
cp data/ai_gm.db data-dev/ai_gm_dev.db
# Dodaj do .gitignore jeśli jeszcze nie ma:
grep -qxF 'data-dev/' .gitignore || echo 'data-dev/' >> .gitignore
```

### Krok 5 — Stwórz `scripts/deploy_prod.sh`

```bash
cat > scripts/deploy_prod.sh << 'EOF'
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
EOF
```

### Krok 6 — Stwórz `scripts/deploy_dev.sh`

```bash
cat > scripts/deploy_dev.sh << 'EOF'
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
EOF
```

### Krok 7 — Nadaj uprawnienia

```bash
chmod +x scripts/deploy_prod.sh scripts/deploy_dev.sh
```

### Krok 8 — Commit całości i tagi

```bash
git add -A
git commit -m "feat: Phase 0 — prod/dev environment split

- Add docker-compose.dev.yml (dev stack, ports 3002/8100)
- Add scripts/deploy_prod.sh with pre-deploy DB backup + healthcheck
- Add scripts/deploy_dev.sh
- Add data-dev/ dir + initial DB copy (gitignored)
- Preserve docker-compose.override.yml untouched"
git push origin main
git push origin develop
git tag -a v0.1-phase0-complete -m "Phase 0: prod/dev environment implemented"
git push origin v0.1-phase0-complete
```

### Krok 9 — Weryfikacja

```bash
# Uruchom dev stack
docker compose -f docker-compose.dev.yml up -d

# Sprawdź oba stacki
docker compose ps
docker compose -f docker-compose.dev.yml ps

# Healthchecks
curl -sf http://localhost:8000/api/healthz && echo "PROD OK"
curl -sf http://localhost:8100/api/healthz && echo "DEV OK"
```

---

## Co zostało zrobione *(uzupełnia Cursor po implementacji)*

```
Data: 2026-04-27 — STOP (REV 2, iteracja 1)

Wykonane:
- Zweryfikowano warunek startowy: git status pokazuje brudne drzewo
- Zidentyfikowane usunięcia: docs/Phase 8A/, docs/Phase 8B/, docs/figma-handoff/
- Właściciel potwierdził: pliki lokalne, nie muszą być na GitHubie
- Wybrana Opcja B: commit usunięć

NIE wykonano:
- żadnych zmian produkcyjnych
- Docker nie był ruszany

Następny krok:
- Wykonać Krok 0 (commit usunięć) i kontynuować od Kroku 1
```

---

## Notatki po implementacji *(Perplexity — 2026-04-27)*

**Bloker git — ostateczna diagnoza i decyzja:**

Usunięte pliki to lokalna dokumentacja robocza z Phase 8A/8B i figma-handoff, która nigdy nie była pushowana na GitHub. Właściciel decyzja: te pliki **nie idą do repozytorium**. Prawidłowe rozwiązanie: **Opcja B — commit usunięć**.

**Gotowe komendy do wklejenia na `.61` zanim dasz plik Cursorowi:**

```bash
cd /home/piotrszmidt/ai-gm
git add -A
git commit -m "chore: remove local-only docs from git tracking"
git push origin main
git status
# Powinno: nothing to commit, working tree clean
```

**Po tym:** wklej ten plik do Cursora — Cursor zaczyna od Kroku 0 (który jest już gotowy do wykonania) i idzie dalej bez zatrzymań.

**Zaplanowane po Phase 0:**
- Phase 0.5 — Observability DEV (Loki + Prometheus + Grafana, porty `:3302`/`:9092`/`:3102`)
- Konfiguracja DNS subdomeny dev
