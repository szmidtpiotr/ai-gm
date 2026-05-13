<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-27 -->

# PROMPT 2 — Phase 0.5: Observability DEV (Loki + Prometheus + Grafana)

> **Workflow tego pliku:**
> 1. ✅ Perplexity wygenerował prompt REV 1 z pytaniami blokującymi
> 2. ✅ Cursor odpowiedział na pytania blokujące
> 3. ✅ Perplexity przeanalizował odpowiedzi → REV 2 gotowe
> 4. ✅ Cursor implementuje wg REV 2
> 5. ✅ Cursor uzupełnił `## Co zostało zrobione`
> 6. ✅ Właściciel wkleił raport do Perplexity
> 7. ✅ Perplexity dopisał `## Notatki po implementacji` i zmienił STATUS na DONE
> 8. ✅ Plik przemianowany na `PROMPT 2 — Observability DEV_DONE.md`

---

## Cel

Uruchomić lokalny stack observability **tylko dla środowiska DEV** na maszynie `.61`:

- **Loki** — agregacja logów z kontenerów DEV
- **Promtail** — agent zbierający logi z Docker (przez Docker socket)
- **Prometheus** — gotowy na metryki FastAPI (na razie scraping pusty, bo `/metrics` = 404)
- **Grafana** — dashboardy: logi DEV + metryki w jednym panelu

**Nie dotyczy PROD** — stack prod observability jest na VM `ai-gm-observability` i nie jest zmieniany.

### Porty

| Serwis | Port |
|---|---|
| Grafana DEV | `3302` |
| Prometheus DEV | `9092` |
| Loki DEV | `3102` |
| Promtail DEV | wewnętrzny (brak) |

---

## Analiza odpowiedzi Cursora (REV 1 → decyzje projektowe)

| Pytanie | Wynik | Decyzja |
|---|---|---|
| Porty 3302/9092/3102 | WOLNE | ✅ kontynuujemy |
| `observability-dev/` | nie istnieje | ✅ tworzymy od zera |
| `observability/` (PROD) | istnieje, ma `docker-compose.yml`, `grafana/`, `loki/`, `promtail/` | ✅ wzorzec do zachowania spójności |
| Docker socket | dostępny, `piotrszmidt` w grupie `docker` | ✅ Promtail może go użyć |
| `/metrics` na DEV | 404 — brak | Prometheus wdrażamy, scrape backendu pusty. Komentarz w konfiguracji. |
| Label `service=backend-dev` | TAK | ✅ Promtail może filtrować po labelu |
| `git status` | dirty: `MD PROMPT 1…` | Krok 0: commit tego pliku przed implementacją |
| Wolne miejsce | 57 GB | ✅ wystarczy |
| Docker Compose | v5.1.3 | ✅ składnia `name:` obsługiwana |

---

## Odpowiedzi Cursora (REV 1)

```
1) Porty 3302/9092/3102: WOLNE.

2) observability-dev/: NIE ISTNIEJE.

3) observability/ (PROD):
   - Elementy: docker-compose.yml, game-host-promtail-compose.yml,
     game-host-promtail.yml, grafana/, loki/, promtail/, mcp/,
     README.md, install_on_ubuntu.sh, sync_story_db_to_observability.sh

4) Docker socket: dostepny, owner root:docker, piotrszmidt w grupie docker.

5) /metrics: BRAK (404).

6) Label service=backend-dev: TAK.

7) git status: dirty - MD "docs/Phase 0 - Prod Dev Environment/PROMPT 1 - Prod Dev Split.md"

8) Wolne miejsce: 57 GB free.

9) Docker Compose: v5.1.3
```

---

## Implementacja (REV 2) — Cursor wykonuje

> **Warunek startowy:** wykonaj Krok 0 zanim przejdziesz dalej.

---

### Krok 0 — Wyczyść git (warunek przed implementacją)

```bash
cd /home/piotrszmidt/ai-gm
git add -A
git commit -m "chore: update PROMPT 1 DONE file (workflow notes)"
git push origin main
git status
# Oczekiwane: nothing to commit, working tree clean
```

---

### Krok 1 — Utwórz strukturę katalogów

```bash
mkdir -p observability-dev/loki
mkdir -p observability-dev/promtail
mkdir -p observability-dev/prometheus
mkdir -p observability-dev/grafana/provisioning/datasources
mkdir -p observability-dev/grafana/provisioning/dashboards
mkdir -p observability-dev/grafana/dashboards
mkdir -p observability-dev/grafana/data
mkdir -p observability-dev/loki/data
```

---

### Krok 2 — `observability-dev/loki/loki-config.yml`

```yaml
auth_enabled: false

server:
  http_listen_port: 3100
  grpc_listen_port: 9096

common:
  instance_addr: 127.0.0.1
  path_prefix: /loki/data
  storage:
    filesystem:
      chunks_directory: /loki/data/chunks
      rules_directory: /loki/data/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory

query_range:
  results_cache:
    cache:
      embedded_cache:
        enabled: true
        max_size_mb: 100

schema_config:
  configs:
    - from: 2024-01-01
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: loki_index_
        period: 24h

limits_config:
  retention_period: 168h  # 7 dni

compactor:
  working_directory: /loki/data/compactor
  retention_enabled: true
  delete_request_store: filesystem

ruler:
  alertmanager_url: http://localhost:9093

analytics:
  reporting_enabled: false
```

---

### Krok 3 — `observability-dev/promtail/promtail-config.yml`

```yaml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

client:
  url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: ai-gm-dev-docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 5s
        filters:
          - name: label
            values: ["service=backend-dev", "service=frontend-dev"]
    relabel_configs:
      - source_labels: ["__meta_docker_container_name"]
        target_label: container
      - source_labels: ["__meta_docker_container_label_service"]
        target_label: service
      - replacement: ai-gm-dev
        target_label: job
      - source_labels: ["__meta_docker_container_log_stream"]
        target_label: stream
    pipeline_stages:
      - docker: {}
```

---

### Krok 4 — `observability-dev/prometheus/prometheus.yml`

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  # Backend DEV - /metrics zwraca 404 (brak eksportera).
  # Konfiguracja gotowa - odkomentuj gdy dodasz prometheus-fastapi-instrumentator.
  # - job_name: 'ai-gm-backend-dev'
  #   static_configs:
  #     - targets: ['backend:8000']
  #   metrics_path: /metrics

  # Prometheus sam siebie monitoruje
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # Loki metryki
  - job_name: 'loki'
    static_configs:
      - targets: ['loki:3100']
```

---

### Krok 5 — `observability-dev/grafana/provisioning/datasources/datasources.yml`

```yaml
apiVersion: 1

datasources:
  - name: Loki DEV
    type: loki
    access: proxy
    url: http://loki:3100
    isDefault: true
    editable: false
    jsonData:
      maxLines: 1000

  - name: Prometheus DEV
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    editable: false
    jsonData:
      timeInterval: 15s
```

---

### Krok 6 — `observability-dev/grafana/provisioning/dashboards/dashboards.yml`

```yaml
apiVersion: 1

providers:
  - name: ai-gm-dev
    orgId: 1
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
```

---

### Krok 7 — `observability-dev/grafana/dashboards/ai-gm-dev-overview.json`

Utwórz plik o tej zawartości (podstawowy dashboard logów DEV):

```json
{
  "title": "AI-GM DEV Overview",
  "uid": "ai-gm-dev-overview",
  "schemaVersion": 38,
  "version": 1,
  "refresh": "10s",
  "time": { "from": "now-1h", "to": "now" },
  "panels": [
    {
      "id": 1,
      "title": "Backend DEV — Logi",
      "type": "logs",
      "gridPos": { "x": 0, "y": 0, "w": 24, "h": 12 },
      "datasource": { "type": "loki", "uid": "" },
      "targets": [
        {
          "datasource": { "type": "loki" },
          "expr": "{job=\"ai-gm-dev\", service=\"backend-dev\"}",
          "refId": "A"
        }
      ],
      "options": {
        "showTime": true,
        "showLabels": false,
        "sortOrder": "Descending",
        "wrapLogMessage": true
      }
    },
    {
      "id": 2,
      "title": "Frontend DEV — Logi nginx",
      "type": "logs",
      "gridPos": { "x": 0, "y": 12, "w": 24, "h": 8 },
      "datasource": { "type": "loki", "uid": "" },
      "targets": [
        {
          "datasource": { "type": "loki" },
          "expr": "{job=\"ai-gm-dev\", service=\"frontend-dev\"}",
          "refId": "A"
        }
      ],
      "options": {
        "showTime": true,
        "showLabels": false,
        "sortOrder": "Descending",
        "wrapLogMessage": true
      }
    }
  ]
}
```

---

### Krok 8 — `observability-dev/docker-compose.observability.dev.yml`

```yaml
# Observability stack dla DEV — Loki + Promtail + Prometheus + Grafana
# Porty: Grafana :3302, Prometheus :9092, Loki :3102
# NIE MODYFIKUJE stosu prod ani docker-compose.dev.yml
name: ai-gm-observability-dev

services:

  loki:
    image: grafana/loki:2.9.8
    restart: unless-stopped
    ports:
      - "3102:3100"
    volumes:
      - ./loki/loki-config.yml:/etc/loki/local-config.yaml:ro
      - ./loki/data:/loki/data
    command: -config.file=/etc/loki/local-config.yaml
    networks:
      - observability-dev

  promtail:
    image: grafana/promtail:2.9.8
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./promtail/promtail-config.yml:/etc/promtail/config.yml:ro
    command: -config.file=/etc/promtail/config.yml
    depends_on:
      - loki
    networks:
      - observability-dev

  prometheus:
    image: prom/prometheus:v2.51.2
    restart: unless-stopped
    ports:
      - "9092:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=7d'
      - '--web.enable-lifecycle'
    networks:
      - observability-dev

  grafana:
    image: grafana/grafana:10.4.2
    restart: unless-stopped
    ports:
      - "3302:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_AUTH_ANONYMOUS_ENABLED=false
      - GF_SERVER_ROOT_URL=http://localhost:3302
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
      - ./grafana/dashboards:/var/lib/grafana/dashboards:ro
      - ./grafana/data:/var/lib/grafana
    depends_on:
      - loki
      - prometheus
    networks:
      - observability-dev

networks:
  observability-dev:
    driver: bridge
```

> **Uwaga:** stack observability DEV jest celowo **izolowany** od sieci `ai-gm-dev`. Promtail zbiera logi przez Docker socket (globalny), nie przez sieć Dockera — dlatego połączenie sieciowe nie jest potrzebne.

---

### Krok 9 — Uzupełnij `.gitignore`

```bash
cd /home/piotrszmidt/ai-gm
cat >> .gitignore << 'EOF'

# Observability DEV — dane runtime (nie commitujemy)
observability-dev/loki/data/
observability-dev/grafana/data/
EOF
```

---

### Krok 10 — Dodaj label `service=frontend-dev` do `docker-compose.dev.yml`

W pliku `docker-compose.dev.yml` znajdź sekcję `frontend:` i dodaj labels:

```yaml
  frontend:
    # ... istniejąca konfiguracja ...
    labels:
      - service=frontend-dev    # <-- dodaj tę linię
```

Następnie zrestartuj frontend DEV:
```bash
docker compose -f docker-compose.dev.yml up -d frontend
```

---

### Krok 11 — Uruchom stack observability

```bash
cd /home/piotrszmidt/ai-gm
docker compose -f observability-dev/docker-compose.observability.dev.yml up -d
```

---

### Krok 12 — Weryfikacja

```bash
# Status kontenerów
docker compose -f observability-dev/docker-compose.observability.dev.yml ps

# Healthcheck Loki
curl -sf http://localhost:3102/ready && echo "LOKI OK" || echo "LOKI FAIL"

# Healthcheck Prometheus
curl -sf http://localhost:9092/-/healthy && echo "PROMETHEUS OK" || echo "PROMETHEUS FAIL"

# Healthcheck Grafana
curl -sf http://localhost:3302/api/health | grep -q '"database": "ok"' && echo "GRAFANA OK" || echo "GRAFANA FAIL"

# Sprawdź czy Promtail zbiera logi (po ~30s od startu)
curl -s "http://localhost:3102/loki/api/v1/labels" | python3 -m json.tool | head -20
```

Grafana dostępna pod: http://192.168.1.61:3302  
Login: `admin` / Hasło: `admin`

---

### Krok 13 — Commit + push + tag

```bash
cd /home/piotrszmidt/ai-gm
git add -A
git commit -m "feat: Phase 0.5 — observability DEV stack

- Add observability-dev/ (Loki + Promtail + Prometheus + Grafana)
- Ports: Grafana :3302, Prometheus :9092, Loki :3102
- Promtail scrapes Docker socket filtering service=backend-dev/frontend-dev
- Prometheus ready for FastAPI metrics (endpoint pending)
- Grafana pre-provisioned with Loki+Prometheus datasources + AI-GM DEV dashboard
- Add frontend-dev label to docker-compose.dev.yml
- Gitignore runtime data dirs"
git push origin main
git tag -a v0.2-observability-dev -m "Phase 0.5: DEV observability stack"
git push origin v0.2-observability-dev
```

---

### Komendy operacyjne (do użytku po wdrożeniu)

```bash
# Start
docker compose -f observability-dev/docker-compose.observability.dev.yml up -d

# Stop (bez usuwania danych)
docker compose -f observability-dev/docker-compose.observability.dev.yml stop

# Restart
docker compose -f observability-dev/docker-compose.observability.dev.yml restart

# Logi Promtail (diagnoza jeśli logi nie spływają)
docker compose -f observability-dev/docker-compose.observability.dev.yml logs promtail --tail=30

# Logi Loki
docker compose -f observability-dev/docker-compose.observability.dev.yml logs loki --tail=30
```

---

## Co zostało zrobione *(Cursor — 2026-04-27)*

```
Data: 2026-04-27 — DONE (REV 2)

Wykonane kroki:
1) Krok 0 (git clean):
   - commit: `845efe1`
   - msg: `chore: update PROMPT 1 DONE file (workflow notes)`
   - push: `origin/main`
   - status po kroku: working tree clean

2) Kroki 1-8 (implementacja plików i konfiguracji):
   - utworzono strukturę `observability-dev/`
   - dodano konfiguracje:
     - `observability-dev/loki/loki-config.yml`
     - `observability-dev/promtail/promtail-config.yml`
     - `observability-dev/prometheus/prometheus.yml`
     - `observability-dev/grafana/provisioning/datasources/datasources.yml`
     - `observability-dev/grafana/provisioning/dashboards/dashboards.yml`
     - `observability-dev/grafana/dashboards/ai-gm-dev-overview.json`
     - `observability-dev/docker-compose.observability.dev.yml`
   - uzupełniono `.gitignore` o:
     - `observability-dev/loki/data/`
     - `observability-dev/grafana/data/`
   - dodano label `service=frontend-dev` do `docker-compose.dev.yml`

3) Krok 11 (start stacku observability):
   - `docker compose -f observability-dev/docker-compose.observability.dev.yml up -d`

4) Problem i naprawa podczas wdrożenia:
   - Loki i Grafana wpadały w restart z powodu uprawnień do katalogów data.
   - Naprawa: korekta uprawnień katalogów runtime i restart usług.
   - Po naprawie wszystkie serwisy działają poprawnie.

5) Krok 12 (weryfikacja):
   - `docker compose -f observability-dev/docker-compose.observability.dev.yml ps` -> wszystkie kontenery `Up`
   - `curl http://localhost:3102/ready` -> HTTP 200
   - `curl http://localhost:9092/-/healthy` -> HTTP 200 (`Prometheus Server is Healthy.`)
   - `curl http://localhost:3302/api/health` -> `{"database":"ok","version":"10.4.2",...}`
   - `curl http://localhost:3102/loki/api/v1/labels` -> `{"status":"success"}`

6) Krok 13 (commit + push + tag):
   - commit: `f77c853`
   - msg: `feat: Phase 0.5 — observability DEV stack`
   - push: `origin/main`
   - tag: `v0.2-observability-dev` (push OK)

Linki dostępu po wdrożeniu:
- Grafana DEV: `http://192.168.1.61:3302` (admin/admin)
- Prometheus DEV: `http://192.168.1.61:9092`
- Loki DEV: `http://192.168.1.61:3102`

Uwaga:
- Endpoint backendu DEV `/metrics` nadal zwraca 404 (zgodnie z założeniem REV 2),
  więc Prometheus jest gotowy, ale nie scrape'uje jeszcze metryk aplikacji FastAPI.
```

---

## Notatki po implementacji *(Perplexity — 2026-04-27)*

### ✅ Ocena wdrożenia

Phase 0.5 zakończona pomyślnie. Wszystkie cele REV 2 zostały osiągnięte:
- Stack uruchomiony, wszystkie 4 serwisy `Up`
- Healthchecki przeszły (Loki, Prometheus, Grafana)
- Loki zbiera logi z kontenerów DEV przez Promtail (Docker socket)
- Grafana pre-provisionowana z datasources + dashboard `AI-GM DEV Overview`
- Git czysty, tag `v0.2-observability-dev` na miejscu

---

### 🔴 Problem z uprawnieniami Loki/Grafana — analiza i fix

**Przyczyna:** Domyślnie Docker montuje katalogi host-side (`./loki/data`, `./grafana/data`) jako `root:root`. Kontenery Loki (UID 10001) i Grafana (UID 472) nie mogą pisać do katalogów posiadanych przez root bez jawnego `chown` lub ustawienia `user:` w compose.

**Zastosowany fix:** korekta uprawnień katalogów runtime przed/po starcie. To poprawne podejście dla środowiska DEV.

**Zalecenie na przyszłość:** aby uniknąć tego problemu przy kolejnych `rm -rf` + `up -d`, warto dodać do `docker-compose.observability.dev.yml`:

```yaml
  loki:
    user: "10001:10001"

  grafana:
    user: "472:472"
```

Ewentualnie skrypt `init-permissions.sh`:
```bash
#!/bin/bash
mkdir -p observability-dev/loki/data observability-dev/grafana/data
sudo chown -R 10001:10001 observability-dev/loki/data
sudo chown -R 472:472 observability-dev/grafana/data
```

---

### 🟡 Otwarte punkty (następne kroki)

| # | Co | Priorytet | Kiedy |
|---|---|---|---|
| 1 | Dodać `prometheus-fastapi-instrumentator` do backendu DEV i odkomentować job w `prometheus.yml` | 🔴 HIGH | PROMPT 3 |
| 2 | Zmienić hasło Grafany z `admin/admin` na coś silniejszego (nawet DEV) | 🟡 MED | przy okazji PROMPT 3 |
| 3 | Dodać alert Grafana na błędy poziomu `ERROR` w logach backendu DEV | 🟡 MED | po wdrożeniu metryk |
| 4 | Rozważyć dodanie `user:` do compose aby wyeliminować problem uprawnień przy reinicjalizacji | 🟢 LOW | opcjonalnie |
| 5 | Dashboard `AI-GM DEV Overview` ma puste `uid` dla datasources w JSON — warto uzupełnić po pierwszym wejściu w Grafanę | 🟢 LOW | przy pierwszym używaniu |

---

### 📋 Stan stosu po Phase 0.5

```
.61 DEV Stack
├── docker-compose.dev.yml          ← aplikacja DEV (backend + frontend)
└── observability-dev/
    └── docker-compose.observability.dev.yml  ← Loki + Promtail + Prometheus + Grafana

Dostęp:
  Grafana:    http://192.168.1.61:3302   (logi + metryki)
  Prometheus: http://192.168.1.61:9092   (metryki — scrape backendu pending)
  Loki:       http://192.168.1.61:3102   (API logów)

Następny krok → PROMPT 3: FastAPI /metrics endpoint
```
