<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-27 -->

# PROMPT 3 — Phase 0.6: FastAPI /metrics + Dashboardy DEV

> **Workflow tego pliku:**
> 1. ✅ Perplexity wygenerował prompt REV 1 z pytaniami blokującymi
> 2. ✅ Cursor odpowiedział na pytania blokujące
> 3. ✅ Właściciel wkleił odpowiedzi Cursora do Perplexity
> 4. ✅ Implementacja wykonana bezpośrednio na podstawie REV 1 + odpowiedzi
> 5. ✅ Cursor uzupełnił `## Co zostało zrobione`
> 6. ✅ Właściciel wkleił raport do Perplexity
> 7. ✅ Perplexity dopisał `## Notatki po implementacji` i zmienił STATUS na DONE
> 8. ✅ Plik przemianowany na `PROMPT 3 — FastAPI Metrics DEV_DONE.md`

---

## Cel

Dwa powiązane cele wdrażane razem:

### Cel A — FastAPI `/metrics` na backendzie DEV
- Dodać `prometheus-fastapi-instrumentator` do backendu DEV
- Udostępnić endpoint `/metrics` (HTTP scraping przez Prometheus)
- Odkomentować job `ai-gm-backend-dev` w `observability-dev/prometheus/prometheus.yml`
- Weryfikacja: Prometheus scrape'uje backend DEV bez błędów

### Cel B — Rozbudowane dashboardy w Grafana DEV
- Skopiować i dostosować dashboardy z `observability/grafana/provisioning/dashboards/json/` (PROD) do DEV
- Dostosowanie: zmiana datasource UID na DEV, zmiana tytułów (sufiks `[DEV]`)
- Dashboardy do przeniesienia:
  - `llm-health-error-overview.json`
  - `chat-stream-combat-trace.json`
  - `turn-pipeline-stream-nonstream.json`
  - `top-error-signatures-24h.json`
  - `campaign-narrative-loki.json`
  - `campaign-story-reader.json`

**Nie dotyczy PROD** — `observability/` i `docker-compose.yml` są tylko do odczytu.

---

## Kontekst techniczny

| Element | Wartość |
|---|---|
| Backend DEV | `docker-compose.dev.yml`, serwis `backend`, port `8100` |
| Prometheus DEV | `observability-dev/prometheus/prometheus.yml`, port `9092` |
| Grafana DEV | `observability-dev/grafana/`, port `3302` |
| Dashboardy DEV | `observability-dev/grafana/dashboards/` |
| Dashboardy PROD (źródło) | `observability/grafana/provisioning/dashboards/json/` |
| Backend framework | FastAPI (Python) |
| Dostępny instrumentator | `prometheus-fastapi-instrumentator` (pip) |

### Pliki których NIE wolno ruszać
- `docker-compose.yml` (PROD)
- `observability/` (PROD observability)
- `data/ai_gm.db` (baza PROD)

---

## Odpowiedzi Cursora (REV 1)

```
1) `prometheus-fastapi-instrumentator` w zależnościach:
- `backend/requirements.txt` nie zawiera wpisów z `prometheus` ani `instrumentator`.
- Wniosek: biblioteka NIE jest jeszcze dodana.

2) `backend/app/main.py` (miejsce podpięcia):
- Plik startuje klasycznie od importow FastAPI/routerow, brak importu `Instrumentator`.
- W pierwszych ~80 liniach brak podpięcia `/metrics`.
- Wniosek: jest miejsce na dodanie instrumentacji, ale obecnie jej nie ma.

3) Aktualny stan `/metrics` na DEV:
- `curl http://localhost:8100/metrics` -> HTTP `404`.
- Zgodne z oczekiwaniem.

4) Prometheus DEV i status scrapingu:
- `http://localhost:9092/api/v1/targets` pokazuje targety ze stanem `health: "up"` (co najmniej self + loki).
- Brak targetu backendu DEV (bo job backendu jest nadal zakomentowany).

5) `docker-compose.dev.yml` backend `build:` czy `image:`:
- Backend używa `build:` (`context: ./backend`), nie `image:`.
- Port mapowany: `8100:8000` (wewnętrzny port kontenera 8000).

6) Aktualna zawartość `observability-dev/grafana/dashboards/`:
- Obecnie tylko:
  - `ai-gm-dev-overview.json`

7) UID datasources Loki/Prometheus w Grafana DEV:
- Nie udało się odczytać przez API Grafany:
  - `GET /api/datasources` z `admin:admin` zwraca `401 Unauthorized`.
- Bloker: hasło było inne niż `admin:admin`.

8) `git status` przed implementacją:
- Branch: `main`
- Working tree: czyste.

Blokery przed implementacją:
- Jedyny bloker: brak dostępu do API Grafany DEV na `admin:admin` (401).
- Pozostałe punkty technicznie gotowe do wdrożenia REV 2.
```

---

## Co zostało zrobione *(Cursor — 2026-04-27)*

```
Data: 2026-04-27 — DONE

Zakres wykonany:
1) Backend FastAPI DEV (`/metrics`):
- Dodano zależność `prometheus-fastapi-instrumentator>=6.1.0` do `backend/requirements.txt`.
- Dodano instrumentację w `backend/app/main.py`:
  - import `Instrumentator`
  - podpięcie `Instrumentator().instrument(app).expose(app)`
- Rebuild/restart backendu DEV wykonany:
  - `docker compose -f docker-compose.dev.yml up -d --build backend`
- Weryfikacja:
  - `GET http://localhost:8100/metrics` -> HTTP 200
  - endpoint zwraca metryki Prometheus (`python_gc_*`, itd.).

2) Prometheus DEV:
- Zmieniono `observability-dev/prometheus/prometheus.yml`:
  - dodano job `ai-gm-backend-dev`
  - scrape target: `host.docker.internal:8100`
  - `metrics_path: /metrics`
- Dodatkowo (naprawa runtime):
  - w `observability-dev/docker-compose.observability.dev.yml` dodano dla serwisu `prometheus`:
    `extra_hosts: ["host.docker.internal:host-gateway"]`
  - bez tego Prometheus nie rozwiązywał hosta (`no such host`).
- Restart observability:
  - `docker compose -f observability-dev/docker-compose.observability.dev.yml restart prometheus grafana`
- Weryfikacja:
  - target `ai-gm-backend-dev` przechodzi do `health=up`.

3) Dashboardy Grafana DEV:
- Skopiowano i dostosowano 6 dashboardów z `observability/grafana/provisioning/dashboards/json/`
  do `observability-dev/grafana/dashboards/`:
  - `llm-health-error-overview.json`
  - `chat-stream-combat-trace.json`
  - `turn-pipeline-stream-nonstream.json`
  - `top-error-signatures-24h.json`
  - `campaign-narrative-loki.json`
  - `campaign-story-reader.json`
- Modyfikacje:
  - tytuły z sufiksem `[DEV]`
  - UID dashboardów z sufiksem `-dev`
  - datasource UID podmienione wg Grafana DEV API:
    - Loki DEV: `PD5A68A3BD6F8BA56`
    - Prometheus DEV: `PFB84F690C9252D4E`
- Weryfikacja:
  - `GET /api/search` Grafany pokazuje wszystkie dashboardy `[DEV]` + `AI-GM DEV Overview`.

4) Git / release:
- commit: `011f574`
- message: `feat: Phase 0.6 — FastAPI metrics DEV + dashboards DEV`
- push: `origin/main` (OK)
- tag: `v0.3-metrics-dashboards-dev` (push OK)
- Uwaga: brak PR (commit bezpośrednio na `main` — brak gałęzi źródłowej).

5) Testy:
- Próba uruchomienia `pytest -q` na `.61` zakończona błędem środowiska:
  - `pytest: command not found`
- Brak uruchomienia testów automatycznych backendu (brak binarki `pytest` na hoście).
```

---

## Notatki po implementacji *(Perplexity — 2026-04-27)*

### ✅ Ocena wdrożenia

Phase 0.6 zakończona pomyślnie. Oba cele osiągnięte:
- `/metrics` na backendzie DEV działa (HTTP 200)
- Prometheus DEV scrape'uje backend (`health=up`)
- 6 dashboardów DEV dostępnych w Grafana DEV (`[DEV]` suffix, właściwe datasource UID)
- Git czysty, tag `v0.3-metrics-dashboards-dev` na miejscu

---

### 🔴 Fix: `extra_hosts: host.docker.internal:host-gateway` — analiza

**Przyczyna:** Prometheus działa w sieci `observability-dev` (izolowany bridge), natomiast backend DEV jest w sieci `ai-gm-dev`. Wewnątrz kontenera Prometheusa adres `backend:8000` nie istnieje (inne sieci Docker). Scrape target został skonfigurowany jako `host.docker.internal:8100` (przez port hosta), ale ta nazwa DNS nie istnieje automatycznie na Linuksie (tylko na macOS/Windows Desktop Docker).

**Fix:** `extra_hosts: ["host.docker.internal:host-gateway"]` w sekcji `prometheus` w compose informuje Docker że `host.docker.internal` ma wskazywać na gateway hosta (IP maszyny od strony Dockera). To standardowe obejście dla Linuks-based Docker hosts.

**Alternatywa do rozważenia w przyszłości:** podłączenie Prometheusa do sieci `ai-gm-dev` przez `networks:` w compose. Pozwoliłoby to używać wewnętrznej nazwy `backend:8000` zamiast `host.docker.internal:8100`. Podejście to jest czystsze architektonicznie, ale wymaga zmiany w `docker-compose.dev.yml` lub dodania external network.

---

### 🔴 Bloker: `pytest: command not found` na hoście

**Przyczyna:** `pytest` nie jest zainstalowany globalnie na maszynie `.61`. Testy backendu są zależnością Pythona wewnątrz kontenera, nie na hoście.

**Poprawne uruchomienie testów backendu DEV:**
```bash
# Wejście do kontenera i uruchomienie pytest wewnątrz
docker compose -f docker-compose.dev.yml exec backend pytest -q

# lub jednolinijkowo bez wchodzenia do kontenera
docker compose -f docker-compose.dev.yml exec backend python -m pytest -q
```

**Zalecenie — PROMPT 4:** dodać do `scripts/deploy_dev.sh` (lub osobnego skryptu `scripts/test_dev.sh`) wywołanie `docker compose exec backend pytest` jako opcjonalny krok weryfikacyjny po deployu.

---

### 🟡 Otwarte punkty (następne kroki)

| # | Co | Priorytet | Kiedy |
|---|---|---|---|
| 1 | Uruchomić testy backendu wewnątrz kontenera DEV (`docker exec ... pytest`) | 🔴 HIGH | PROMPT 4 |
| 2 | Zmienić hasło Grafany DEV z domyślnego na coś nietrywialnego + zaktualizować w docs | 🟡 MED | PROMPT 4 |
| 3 | Rozważyć podłączenie Prometheusa do sieci `ai-gm-dev` zamiast `host.docker.internal` | 🟢 LOW | opcjonalnie |
| 4 | Skrypt `scripts/test_dev.sh` uruchamiający pytest wewnątrz kontenera | 🟡 MED | PROMPT 4 |
| 5 | Weryfikacja czy metryki FastAPI są widoczne w dashboardach DEV (po wejściu w Grafanę) | 🟡 MED | ręcznie przy okazji |

---

### 📋 Stan stosu po Phase 0.6

```
.61 DEV Stack
├── docker-compose.dev.yml          ← aplikacja DEV (backend :8100 + frontend :3002)
└── observability-dev/
    └── docker-compose.observability.dev.yml
        ├── Grafana  :3302   ← 7 dashboardów (1 overview + 6 z PROD [DEV])
        ├── Prometheus :9092 ← scrape: self + loki + backend-dev (UP)
        ├── Loki      :3102  ← logi z backend-dev + frontend-dev
        └── Promtail  (wewn.) ← Docker socket

Datasource UIDs (Grafana DEV):
  Loki DEV:       PD5A68A3BD6F8BA56
  Prometheus DEV: PFB84F690C9252D4E

Następny krok → PROMPT 4: testy backendu + skrypt test_dev.sh
```
