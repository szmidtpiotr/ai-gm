<!-- STATUS: PENDING -->
<!-- REV: 1 | DATE: 2026-04-27 -->

# PROMPT 3 — Phase 0.6: FastAPI /metrics + Dashboardy DEV

> **Workflow tego pliku:**
> 1. ✅ Perplexity wygenerował prompt REV 1 z pytaniami blokującymi
> 2. 🔴 **TERAZ:** Cursor odpowiada na pytania blokujące (NIE implementuje)
> 3. Właściciel wkleja odpowiedzi Cursora do Perplexity
> 4. Perplexity analizuje odpowiedzi → REV 2 gotowe
> 5. Cursor implementuje wg REV 2
> 6. Cursor uzupełnia `## Co zostało zrobione`
> 7. Właściciel wkleja raport do Perplexity
> 8. Perplexity dopisuje `## Notatki po implementacji` i zmienia STATUS na DONE
> 9. Plik zostaje przemianowany na `PROMPT 3 — FastAPI Metrics DEV_DONE.md`

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

## ⛔ PRZED IMPLEMENTACJĄ — pytania blokujące (REV 1)

Cursor odpowiada na każde pytanie przed przejściem do implementacji.

**1. Sprawdź czy `prometheus-fastapi-instrumentator` jest już w zależnościach:**
```bash
cat backend/requirements.txt | grep -i prometheus
# lub
cat backend/requirements.txt | grep -i instrumentator
```

**2. Sprawdź jak wygląda `main.py` backendu (miejsce podpięcia instrumentatora):**
```bash
head -60 backend/app/main.py
```

**3. Sprawdź aktualny stan endpointu `/metrics` na DEV:**
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8100/metrics
# Oczekiwane: 404
```

**4. Sprawdź czy Prometheus DEV działa i jaki ma aktualny status scrapingu:**
```bash
curl -s http://localhost:9092/api/v1/targets | python3 -m json.tool | grep -A5 'health'
```

**5. Sprawdź czy `docker-compose.dev.yml` używa `build:` czy `image:` dla backendu:**
```bash
grep -A5 'backend:' docker-compose.dev.yml | head -20
```

**6. Sprawdź aktualną zawartość `observability-dev/grafana/dashboards/` (co jest teraz):**
```bash
ls -la observability-dev/grafana/dashboards/
```

**7. Sprawdź UID datasources Loki i Prometheus w Grafana DEV (potrzebne do dashboardów):**
```bash
curl -s -u admin:admin http://localhost:3302/api/datasources | python3 -m json.tool | grep -E '"uid"|"name"'
```

**8. Sprawdź git status przed implementacją:**
```bash
git status
git branch --show-current
```

---

## Implementacja (REV 1 — szkic, do zatwierdzenia po odpowiedziach)

> ⚠️ Cursor NIE wykonuje tych kroków przed zatwierdzoniem przez Perplexity (REV 2).
> Ten blok to szkic — może się zmienić po analizie odpowiedzi.

### Szkic Krok A1 — Dodaj instrumentator do `requirements.txt`
```
prometheus-fastapi-instrumentator>=6.1.0
```

### Szkic Krok A2 — Podpięcie w `main.py`
```python
from prometheus_fastapi_instrumentator import Instrumentator

# po stworzeniu `app = FastAPI(...)`
Instrumentator().instrument(app).expose(app)
```

### Szkic Krok A3 — Odkomentuj job w `prometheus.yml`
```yaml
- job_name: 'ai-gm-backend-dev'
  static_configs:
    - targets: ['backend:8000']  # port wewnętrzny kontenera
  metrics_path: /metrics
```

> ⚠️ Port w targets to port **wewnętrzny** kontenera (zazwyczaj 8000), nie port hosta (8100).
> Cursor weryfikuje to na podstawie odpowiedzi na pytanie 5.

### Szkic Krok A4 — Rebuild backendu DEV
```bash
docker compose -f docker-compose.dev.yml build backend
docker compose -f docker-compose.dev.yml up -d backend
```

### Szkic Krok B1 — Skopiuj i dostosuj dashboardy z PROD
Dla każdego pliku JSON z `observability/grafana/provisioning/dashboards/json/`:
- Skopiuj do `observability-dev/grafana/dashboards/`
- Zmień `"title"` dodając sufiks ` [DEV]`
- Zamień UID datasources na wartości z Grafana DEV (z pytania 7)
- Zmień `"uid"` dashboardu (dodaj sufiks `-dev`)

### Szkic Krok B2 — Restart Grafana DEV (hot-reload dashboardów)
```bash
docker compose -f observability-dev/docker-compose.observability.dev.yml restart grafana
```

### Szkic Krok B3 — Weryfikacja
```bash
# Metrics endpoint
curl -s http://localhost:8100/metrics | head -20

# Prometheus scrape status
curl -s http://localhost:9092/api/v1/targets | python3 -m json.tool | grep -E 'health|job'

# Dashboardy w Grafana
curl -s -u admin:admin http://localhost:3302/api/search | python3 -m json.tool | grep title
```

### Szkic Krok B4 — Commit + push + tag
```bash
git add -A
git commit -m "feat: Phase 0.6 — FastAPI metrics DEV + dashboards DEV

- Add prometheus-fastapi-instrumentator to backend requirements
- Expose /metrics endpoint on FastAPI DEV
- Uncomment Prometheus scrape job for backend-dev
- Copy and adapt PROD dashboards to DEV (6 dashboards, [DEV] suffix)
- Rebuild backend-dev container"
git push origin main
git tag -a v0.3-metrics-dashboards-dev -m "Phase 0.6: FastAPI metrics + DEV dashboards"
git push origin v0.3-metrics-dashboards-dev
```

---

## Odpowiedzi Cursora (REV 1)

```
1) `prometheus-fastapi-instrumentator` w zależnościach:
- `backend/requirements.txt` nie zawiera wpisów z `prometheus` ani `instrumentator`.
- Wniosek: biblioteka NIE jest jeszcze dodana.

2) `backend/app/main.py` (miejsce podpięcia):
- Plik startuje klasycznie od importów FastAPI/routerów, brak importu `Instrumentator`.
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
  - `GET /api/datasources` z `admin:admin` zwraca `401 Unauthorized` (`Invalid username or password`).
- To bloker dla automatycznej podmiany UID w dashboardach z PROD.

8) `git status` przed implementacją:
- Branch: `main`
- `git status --short --branch`: `## main...origin/main` (brak lokalnych zmian)
- Working tree: czyste.

Blokery przed implementacją:
- Jedyny bloker: brak dostępu do API Grafany DEV na `admin:admin` (401), więc nie da się potwierdzić UID datasource automatycznie.
- Pozostałe punkty technicznie gotowe do wdrożenia REV 2.
```

---

## Co zostało zrobione *(uzupełnia Cursor po implementacji)*

```
Data: 2026-04-27 — DONE (implementacja REV 1 na podstawie Twojej decyzji)

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
- Skopiowano i dostosowano 6 dashboardów z `observability/grafana/provisioning/dashboards/json/` do `observability-dev/grafana/dashboards/`:
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

5) Testy:
- Próba uruchomienia `pytest -q` na `.61` zakończona błędem środowiska:
  - `pytest: command not found`
- Brak uruchomienia testów automatycznych backendu (brak binarki `pytest` na hoście).
```

---

## Notatki po implementacji *(uzupełnia Perplexity)*

```
[MIEJSCE NA NOTATKI PERPLEXITY]
```
