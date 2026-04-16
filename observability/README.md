# AI GM Observability Stack

This directory contains ready-to-run files for a Proxmox VM observability setup.

## Included

- `docker-compose.yml` for Grafana + Loki + Promtail
- `loki/loki-config.yml` with 7-day retention
- `promtail/promtail-config.yml` with Docker log scraping and token redaction
- `grafana/provisioning/datasources/loki.yml` for default Loki datasource
- `grafana/provisioning/dashboards/dashboards.yml` for dashboard file provisioning
- prebuilt dashboards:
  - `llm-health-error-overview.json`
  - `turn-pipeline-stream-nonstream.json`
  - `top-error-signatures-24h.json`

## Quick start

```bash
cp -R observability /opt/ai-gm-observability
cd /opt/ai-gm-observability
export GRAFANA_ADMIN_PASSWORD='change-this-now'
docker compose up -d
docker compose ps
```

Grafana: `http://<VM_IP>:3000`  
Login: `admin` + your `GRAFANA_ADMIN_PASSWORD`.
