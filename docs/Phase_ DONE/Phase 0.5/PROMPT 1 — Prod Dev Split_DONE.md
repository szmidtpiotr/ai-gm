<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-27 -->

# PROMPT 1 — Phase 0: Rozdzielenie środowisk Prod / Dev

> **Workflow tego pliku:**
> 1. ✅ Perplexity generował prompt (REV 1) i zadawał pytania blokujące
> 2. ✅ Cursor odpowiedział → właściciel wkleił odpowiedzi poniżej
> 3. ✅ Perplexity przeanalizował odpowiedzi → wygenerował REV 2 z planem odblokowania
> 4. ✅ Cursor wykonał check — STOP (brudne drzewo git)
> 5. ✅ Bloker rozwiązany: commit usunięć lokalnych doców
> 6. ✅ Cursor zaimplementował pełną Phase 0
> 7. ✅ Incydent 502/503 na DEV — zdiagnozowany i naprawiony
> 8. ✅ Perplexity wpisał notatki końcowe
> 9. ✅ **STATUS: DONE**

---

## Cel

Rozdzielić środowisko na maszynie `.61` na **produkcję** (port 3001, branch `main`) i **development** (port 3002, branch `develop`), bez naruszania istniejącego stacku produkcyjnego. Przygotować skrypty deployu i dokumentację procedury awansu kodu z dev na prod.

**OSIAGNIĘTE** — oba środowiska działają niezależnie, healthchecki przechodzą.

---

## Środowiska — Adresy dostępowe

### PROD (branch `main`)

| Serwis | URL |
|---|---|
| Frontend | http://192.168.1.61:3001/ |
| Panel admin | http://192.168.1.61:3001/panel/ |
| API (przez proxy) | http://192.168.1.61:3001/api/ |
| Backend bezpośrednio | http://192.168.1.61:8000/ |
| Healthcheck | http://192.168.1.61:8000/api/healthz |
| Frontend (domena) | https://aigm-prod.studio-colorbox.com/ |
| Panel admin (domena) | https://aigm-prod.studio-colorbox.com/panel/ |
| API (domena) | https://aigm-prod.studio-colorbox.com/api/ |

### DEV (branch `develop`)

| Serwis | URL |
|---|---|
| Frontend | http://192.168.1.61:3002/ |
| Panel admin | http://192.168.1.61:3002/panel/ |
| API (przez proxy) | http://192.168.1.61:3002/api/ |
| Backend bezpośrednio | http://192.168.1.61:8100/ |
| Healthcheck | http://192.168.1.61:8100/api/healthz |
| Frontend (domena) | https://aigm-dev.studio-colorbox.com/ |
| Panel admin (domena) | https://aigm-dev.studio-colorbox.com/panel/ |
| API (domena) | https://aigm-dev.studio-colorbox.com/api/ |

### Observability (Phase 0.5 — planowane)

| Serwis | URL |
|---|---|
| Grafana DEV | http://192.168.1.61:3302/ (po wdrożeniu) |
| Grafana PROD | do ustalenia podczas wdrożenia |

---

## Komendy operacyjne — Cheatsheet

### PROD (porty 3001 / 8000)

```bash
# Rebuild + restart
cd /home/piotrszmidt/ai-gm && docker compose -f docker-compose.yml up -d --build --remove-orphans

# Tylko restart (bez rebuildu)
cd /home/piotrszmidt/ai-gm && docker compose -f docker-compose.yml restart backend frontend

# Weryfikacja
cd /home/piotrszmidt/ai-gm && docker compose -f docker-compose.yml ps && curl -sf http://localhost:8000/api/healthz && echo "PROD OK"

# Logi
docker compose -f docker-compose.yml logs backend --tail=50
```

### DEV (porty 3002 / 8100)

```bash
# Rebuild + restart
cd /home/piotrszmidt/ai-gm && docker compose -f docker-compose.dev.yml up -d --build --remove-orphans

# Tylko restart (bez rebuildu)
cd /home/piotrszmidt/ai-gm && docker compose -f docker-compose.dev.yml restart backend frontend

# Weryfikacja
cd /home/piotrszmidt/ai-gm && docker compose -f docker-compose.dev.yml ps && curl -sf http://localhost:8100/api/healthz && echo "DEV OK"

# Logi
docker compose -f docker-compose.dev.yml logs backend --tail=50
```

---

## Kontekst techniczny

- Repo: `szmidtpiotr/ai-gm`
- Stack prod: `docker-compose.yml` + `docker-compose.override.yml`, frontend `:3001`, backend `:8000`
- Stack dev: `docker-compose.dev.yml`, frontend `:3002`, backend `:8100`
- Baza prod: `data/ai_gm.db`
- Baza dev: `data-dev/ai_gm.db` (kopia prod z momentu wdrożenia, nie synchronizuje się automatycznie)
- Branch prod: `main` | Branch dev: `develop`
- Skrypty deploy: `scripts/deploy_prod.sh`, `scripts/deploy_dev.sh`

---

## Odpowiedzi Cursora (REV 1)

```
1. Ścieżka projektu: /home/piotrszmidt/ai-gm
2. Gałąź develop: NIE istniała → utworzona w Kroku 2
3. Porty 3002 i 8100: WOLNE
4. docker-compose.dev.yml: NIE istniał → stworzony w Kroku 3
5. data-dev/: NIE istniał → stworzony w Kroku 4
6. DNS subdomeny dev: NIEZNANY → następnie uruchomiona aigm-dev.studio-colorbox.com
7. git status: BRUDNE drzewo → odblokowane przez commit usunięć (Krok 0)
```

---

## Co zostało zrobione *(Cursor — 2026-04-27)*

```
Data: 2026-04-27 — DONE (REV 2, iteracja 2)

1) Odblokowanie git (Krok 0, Opcja B):
   - commit: 397e26f
   - msg: "chore: uporzadkowanie docs przed Phase 0"
   - push: origin/main

2) Krok 1 (tag bezpieczeństwa):
   - tag: v0.0-pre-phase0, push OK

3) Krok 2 (branch develop):
   - utw. branch `develop`, push: origin/develop

4) Kroki 3-7:
   - dodano docker-compose.dev.yml
   - dodano scripts/deploy_prod.sh
   - dodano scripts/deploy_dev.sh
   - utworzono data-dev/ + kopia data/ai_gm.db -> data-dev/ai_gm_dev.db
   - dopisano data-dev/ do .gitignore
   - chmod +x dla skryptów deploy

5) Krok 8 (commit + push + tag):
   - commit: a90ab3b
   - msg: "feat: Phase 0 — prod/dev environment split"
   - push: origin/main i origin/develop
   - tag: v0.1-phase0-complete, push OK

6) Krok 9 (weryfikacja):
   - docker compose ps (prod) -> kontenery up/healthy
   - docker compose -f docker-compose.dev.yml ps (dev) -> up
   - curl localhost:8000/api/healthz -> PROD OK
   - curl localhost:8100/api/healthz -> FAIL (incydent 502/503)

7) Incydent 502/503 na DEV + naprawa:
   - Obj.: backend dev w pętli restartów
   - Log: sqlite3.OperationalError: no such table: characters
   - Przyczyna: app szuka /data/ai_gm.db, a w data-dev/ była tylko ai_gm_dev.db
   - Fix: cp data/ai_gm.db data-dev/ai_gm.db + restart DEV
   - Wynik: healthcheck DEV OK, proxy 3002 odpowiada JSON
```

---

## Notatki po implementacji *(Perplexity — 2026-04-27)*

### Ocena implementacji

Phase 0 **zakończona sukcesem**. Oba środowiska działają niezależnie, healthchecki przechodzą, skrypty deploy są gotowe, dokumentacja uzupełniona.

### Post-mortem incydentu 502/503 na DEV

**Przyczyna:** `docker-compose.dev.yml` montuje wolumin `./data-dev:/data`, a aplikacja FastAPI otwiera bazę jako `/data/ai_gm.db`. Tymczasem w Kroku 4 kopia bazy trafiła pod nazwę `data-dev/ai_gm_dev.db` (inna nazwa pliku). Docker widział pusty katalog bez `ai_gm.db`, migracje nie mogły się uruchomić.

**Fix:** skopiowanie bazy pod właściwą nazwę `data-dev/ai_gm.db`.

**Korekta do implementacji na przyszłość:** W Kroku 4 prawidłowa komenda to:
```bash
mkdir -p data-dev
cp data/ai_gm.db data-dev/ai_gm.db   # <-- nazwa musi być ai_gm.db, nie ai_gm_dev.db
```

### Znany issue — branch `develop` bez żadnych commitów roznicowych

PR `develop → main` zakończył się błędem `No commits between main and develop`. To normalne — `develop` został stworzony z `main` i nie ma jeszcze żadnych własnych commitów. Pierwszy feature commit na `develop` automatycznie odblikuje ten flow.

### Aktualny stan repo

| Element | Stan |
|---|---|
| Branch `main` | aktywny prod, tag `v0.1-phase0-complete` |
| Branch `develop` | pusty (równy main), gotowy na pierwszy feature |
| Tag `v0.0-pre-phase0` | backup przed Phase 0 |
| Tag `v0.1-phase0-complete` | stan po Phase 0 |
| `docker-compose.dev.yml` | w repo, działa |
| `scripts/deploy_prod.sh` | w repo, działa |
| `scripts/deploy_dev.sh` | w repo, działa |
| `data-dev/` | lokalnie na .61, gitignored |

### Następne kroki

- **Phase 8A** (aktywna) — Combat System Backend — pierwsza gałąź robocza z `develop`
- **Phase 0.5** (planowana) — Observability DEV: Loki + Prometheus + Grafana na portach `:3302`/`:9092`/`:3102`
- Konfiguracja DNS `aigm-dev.studio-colorbox.com` — **już działa** (potwierdzono)
