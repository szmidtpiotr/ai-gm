<!-- last_updated: 2026-04-27 09:20 CEST | rev: 1 -->

# Phase 9A — Task 9A-7: CI/CD integration + Observability dashboards

> **Status: 🔴 PLANNED** | Branch: `phase-9a-ai-test-agent`  
> **Notion:** https://www.notion.so/AI-Test-Agent-34f8842467a880829674cb63bccef76a

---

## Cel

Automatyczne uruchamianie zestawu scenariuszy AI po każdym deployu (smoke suite) oraz dashboardy observability: Test Suite Health, Frontend Health (AI sessions), GM Decisions Analysis. Kompletna telemetria przez OpenTelemetry.

---

## Cursor Prompt

```
Zanim cokolwiek zaimplementujesz — przejrzyj cały projekt i odpowiedz:
1. Czy projekt ma już pipeline CI/CD (GitHub Actions, GitLab CI, Dockerfile, docker-compose)?
   Jakie pliki konfiguracyjne istnieją (`.github/workflows/`, `Makefile`, `docker-compose.yml`)?
2. Czy istnieje już jakikolwiek OTel collector lub serwis monitoringowy
   (Grafana, Prometheus, Jaeger, Sentry)? Szukaj w `docker-compose.yml`, `ops/`, `.env`.
3. Czy testy `pytest` są już uruchamiane w CI? Jaka jest aktualna struktura job-ów?
4. Czy `ai_test_agent/` ma już `requirements.txt` / `package.json` gotowe do zainstalowania w CI?
5. Czy wdrożenie nowych job-ów CI może zepsuć istniejące kroki (np. przez zmianę env vars,
   bazy danych, portów)?
Odpowiedz na te pytania, ZANIM zaczniesz kodować.

---

Zaimplementuj integrację CI/CD i stack observability:

### 1. GitHub Actions: smoke suite po deployu

Nowy plik: `.github/workflows/ai_test_smoke.yml`

```yaml
name: AI Test Smoke Suite

on:
  workflow_dispatch:          # ręczne uruchomienie
  push:
    branches: [phase-9a-ai-test-agent]

jobs:
  ai-smoke:
    runs-on: ubuntu-latest
    env:
      AI_TEST_MODE: "1"
      BASE_URL: ${{ secrets.TEST_SERVER_URL }}
      OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}

    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with: { python-version: '3.11' }

      - name: Install backend deps
        run: pip install -r backend/requirements.txt

      - name: Seed test environment
        run: python backend/scripts/seed_ai_test_env.py

      - name: Run backend unit tests
        run: pytest backend/tests/test_phase9a_*.py -v

      - name: Setup Node (Playwright)
        uses: actions/setup-node@v4
        with: { node-version: '20' }

      - name: Install Playwright deps
        run: cd ai_test_agent && npm ci && npx playwright install --with-deps chromium

      - name: Run PoC flow (sanity check)
        run: |
          cd ai_test_agent
          npx playwright test playwright/poc_manual_flow.spec.js --reporter=list

      - name: Run smoke scenarios (honest_player_flow)
        run: |
          cd ai_test_agent
          python -m agent.orchestrator \
            --scenario scenarios/honest_player_flow.yaml \
            --config ../backend/ai_test_config.json \
            --output results/smoke_run.json

      - name: Upload artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: ai-test-results
          path: |
            ai_test_agent/playwright-results/
            ai_test_agent/results/
          retention-days: 7
```

**Zasady CI:**
- Smoke suite używa TYLKO `honest_player_flow.yaml` (legalny flow — deterministyczny)
- Scenariusze "cheat" (cheat_gm_location, gm_manipulation_gold) uruchamiane TYLKO nocnym cronem
- Nightly cron: `cron: '0 2 * * *'` z pełnym zestawem 4 scenariuszy
- `main` branch — AI testy NIE są blokerem PR (tylko informacyjne)

### 2. OTel Collector (docker-compose)

Dodaj do `docker-compose.yml` (lub nowy `docker-compose.observability.yml`):

```yaml
otel-collector:
  image: otel/opentelemetry-collector-contrib:latest
  command: ["--config=/etc/otel-collector-config.yaml"]
  volumes:
    - ./ops/otel-collector-config.yaml:/etc/otel-collector-config.yaml
  ports:
    - "4317:4317"   # OTLP gRPC
    - "4318:4318"   # OTLP HTTP
    - "8888:8888"   # metrics
  networks: [app-network]

prometheus:
  image: prom/prometheus:latest
  volumes:
    - ./ops/prometheus.yml:/etc/prometheus/prometheus.yml
  ports: ["9090:9090"]
  networks: [app-network]

grafana:
  image: grafana/grafana:latest
  ports: ["3001:3000"]
  environment:
    GF_SECURITY_ADMIN_PASSWORD: "admin"
  volumes:
    - grafana_data:/var/lib/grafana
    - ./ops/grafana/dashboards:/etc/grafana/provisioning/dashboards
    - ./ops/grafana/datasources:/etc/grafana/provisioning/datasources
  networks: [app-network]
```

### 3. Konfiguracja OTel Collector: `ops/otel-collector-config.yaml`

```yaml
receivers:
  otlp:
    protocols:
      grpc: { endpoint: 0.0.0.0:4317 }
      http: { endpoint: 0.0.0.0:4318 }

processors:
  batch: {}
  attributes:
    actions:
      - key: service.environment
        action: insert
        value: "test"

exporters:
  prometheus:
    endpoint: "0.0.0.0:8889"
  logging:
    loglevel: info
  # Opcjonalnie Jaeger/Tempo dla traces:
  # otlp/tempo:
  #   endpoint: tempo:4317

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [logging]
    metrics:
      receivers: [otlp]
      processors: [batch, attributes]
      exporters: [prometheus]
    logs:
      receivers: [otlp]
      processors: [batch]
      exporters: [logging]
```

### 4. Grafana Dashboards (provisioning)

**Dashboard 1: Test Suite Health** (`ops/grafana/dashboards/test_suite_health.json`)
Panele:
- Total runs / pass / fail (counter)
- Pass rate % (gauge, target > 80%)
- Średni czas trwania testu per scenariusz (bar chart)
- Timeline exploitów znalezionych (annotations)
- Tabelka: ostatnie 10 uruchomień z wynikiem

**Dashboard 2: Frontend Health — AI Sessions** (`ops/grafana/dashboards/frontend_health.json`)
Panele:
- JS errors per AI session (count)
- Czas odpowiedzi GM (p50, p95) podczas AI testów
- Web Vitals próbkowane podczas testu (LCP, INP)
- Heatmapa: akcje AI po typie (`send_chat`, `click`, `wait`) w czasie

**Dashboard 3: GM Decisions Analysis** (`ops/grafana/dashboards/gm_decisions.json`)
Panele:
- Decyzje GM: legal vs illegal (pie chart per scenariusz)
- Najczęstsze typy decyzji GM w testach cheaterskich
- Czas od wiadomości gracza do decyzji GM (latency)
- Wykres: które scenariusze najczęściej "przechodzą" (exploit znaleziony)

### 5. Custom metryki z Orchestratora

W `ai_test_agent/agent/orchestrator.py` po zakończeniu testu emituj OTel metryki:
```python
# Przez OTel SDK (Python)
meter.create_counter("ai_test.runs.total").add(1, {"scenario": name, "result": "pass/fail"})
meter.create_histogram("ai_test.steps.count").record(total_steps, {"scenario": name})
meter.create_histogram("ai_test.duration_seconds").record(elapsed, {"scenario": name})
meter.create_counter("ai_test.exploits.found").add(exploit_found, {"scenario": name})
```

### 6. Sampling w produkcji

W `frontend/js/otel_init.js` dodaj sampling rate:
```javascript
// AI test sessions: 100% sampling
// Normalni gracze (prod): 10% sampling
const samplingRate = window._isAiTestSession ? 1.0 : 0.1;
```

`window._isAiTestSession = true` ustawiany przez Playwright przed testem:
```javascript
await page.evaluate(() => { window._isAiTestSession = true; });
```

### 7. Testy: `backend/tests/test_phase9a_ci_observability.py`
- `test_otel_traces_endpoint_accepts_payload` — POST /api/otel/traces z sample payload
- `test_orchestrator_emits_metrics_after_run` — mock OTel meter, sprawdź emit

Uruchom testy na 192.168.1.61 po implementacji.
```

---

## Pliki do zmiany (oczekiwane)

| Plik | Zmiana |
|------|--------|
| `.github/workflows/ai_test_smoke.yml` | **NOWY** — CI smoke suite |
| `docker-compose.yml` | Dodaj: otel-collector, prometheus, grafana |
| `ops/otel-collector-config.yaml` | **NOWY** — konfiguracja OTel |
| `ops/prometheus.yml` | **NOWY** — scrape config |
| `ops/grafana/dashboards/test_suite_health.json` | **NOWY** — dashboard |
| `ops/grafana/dashboards/frontend_health.json` | **NOWY** — dashboard |
| `ops/grafana/dashboards/gm_decisions.json` | **NOWY** — dashboard |
| `ops/grafana/datasources/prometheus.yaml` | **NOWY** — datasource config |
| `ai_test_agent/agent/orchestrator.py` | Dodaj OTel metryki po zakończeniu testu |
| `frontend/js/otel_init.js` | Sampling rate (AI vs normalni gracze) |
| `backend/tests/test_phase9a_ci_observability.py` | **NOWY** — 2 testy |

---

## Kryteria ukończenia

- [ ] GitHub Actions `ai_test_smoke.yml` uruchamia się manualnie bez błędów
- [ ] Smoke scenariusz `honest_player_flow` przechodzi w CI
- [ ] OTel collector zbiera traces i metryki z Orchestratora
- [ ] Grafana dostępna na :3001 z 3 dashboardami
- [ ] Test Suite Health pokazuje wyniki ostatniego runu
- [ ] Sampling 100% dla AI sesji, 10% dla normalnych graczy
- [ ] Istniejące CI job-y nie są naruszone
- [ ] Testy 2/2 ✅ na 192.168.1.61

## Faza 9A UKOŃCZONA ✅

Po zrealizowaniu wszystkich tasków (9A-1 → 9A-7) zaktualizuj README.md:
- Status: `🟢 DONE`
- Uzupełnij tabelę tasków o statusy ✅
- Dodaj sekcję "Co zostało zrobione" wzorując się na plikach z Phase 8E
