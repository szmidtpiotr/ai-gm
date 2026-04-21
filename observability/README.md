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
  - `campaign-story-reader.json` (SQLite snapshot)
  - `campaign-narrative-loki.json` (near-live `narrative_turn` logs)
- alert rules provisioning:
  - `grafana/provisioning/alerting/rules.yml`
- Perplexity tutorial:
  - `PERPLEXITY_LOG_ACCESS_TUTORIAL.md`
- SQLite story reader:
  - `grafana/provisioning/datasources/sqlite-story.yml`
  - `SQL_CAMPAIGN_STORY_READER.md`
  - `sync_story_db_to_observability.sh`

## Quick start

```bash
cp -R observability /opt/ai-gm-observability
cd /opt/ai-gm-observability
export GRAFANA_ADMIN_PASSWORD='change-this-now'
# Optional: if you cannot create /var/lib/ai-gm-db (needs root), use a user-writable dir:
# export AI_GM_STORY_DB_DIR="$HOME/ai-gm-story-db" && mkdir -p "$AI_GM_STORY_DB_DIR"
docker compose up -d
docker compose ps
```

Grafana: `http://<VM_IP>:3000`  
Login: `admin` + your `GRAFANA_ADMIN_PASSWORD`.

### Dashboard JSON updates (repo → running Grafana)

File provisioning reads `grafana/provisioning/dashboards/json/*.json` (see `dashboards.yml`). After you `git pull` or copy a newer `campaign-narrative-loki.json` onto the VM:

1. Ensure the bind mount still includes `./grafana/provisioning:/etc/grafana/provisioning:ro` (see `docker-compose.yml`).
2. Wait up to **30s** (`updateIntervalSeconds`) or run **`docker compose restart grafana`** in the observability directory.
3. Hard-refresh the Grafana UI (folder **AI-GM**). If the dashboard never updates, the remote host may be using a different path — copy the file to the path Grafana actually mounts, or use `scripts/sync-grafana-dashboard.sh` from the repo root with `GRAFANA_SSH` and `GRAFANA_REMOTE_JSON` set.

## Game host log shipping

If **Grafana+Loki+Promtail** from `observability/docker-compose.yml` already run on the same Docker host as the game stack, **do nothing extra** — bundled Promtail ships logs to Loki.

Use `game-host-promtail-compose.yml` only when the **game** runs on a **different** machine than Loki. Edit `game-host-promtail.yml` → `clients[0].url` to your Loki push URL (example: `http://192.168.1.61:3100/loki/api/v1/push`), then:

```bash
docker compose -f observability/game-host-promtail-compose.yml up -d
docker compose -f observability/game-host-promtail-compose.yml ps
```

Promtail health is bound to `127.0.0.1:9081` on that host.

## Reverse proxy (public HTTPS)

See `reverse-proxy.nginx.example.conf` for TLS server blocks pointing at the observability VM (Grafana `:3000`, Loki `:3100`, MCP `:8001`).

## Story DB sync (Strategy B)

Canonical story reader uses SQLite datasource on observability VM.
Sync current app DB snapshot to VM:

```bash
chmod +x observability/sync_story_db_to_observability.sh
./observability/sync_story_db_to_observability.sh
```

## Perplexity custom connector (MCP)
Observability VM can expose a small read-only MCP server for external log/story analysis.

MCP server (inside the VM):
- HTTP endpoint (Streamable HTTP): `http://127.0.0.1:8001/mcp`
- Tools:
  - `loki_query(query, since_minutes, limit)`
  - `campaign_story(campaign_id, limit_turns)`

Recommended Nginx Proxy Manager (create a new Proxy Host):
- Domain: `aigm-mcp.studio-colorbox.com`
- Scheme: `http`
- Forward Host/IP: `<observability VM LAN IP>` (e.g. `192.168.1.61`)
- Forward Port: `8001`
- Enable SSL

Perplexity Web UI → Add Custom connector:
- Transport: `Streamable HTTP`
- Authentication: `None`
- MCP Server URL: `https://aigm-mcp.studio-colorbox.com/mcp`
