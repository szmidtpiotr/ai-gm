#!/usr/bin/env bash
# =============================================================================
# AI-GM — one-shot deployment (new machine)
#
# Usage (from repo root, after git clone):
#   chmod +x install.sh && ./install.sh
#   ./install.sh --no-ollama              # use cloud OpenAI-compatible API (no local Ollama)
#   ./install.sh --keep-db                 # do not wipe ./data/ai_gm.db (upgrade / preserve data)
#   ./install.sh --skip-docker-install     # fail if Docker is missing (CI / strict env)
#   GRAFANA_ADMIN_PASSWORD='…' ./install.sh --with-observability
#       # same as default install, plus Grafana+Loki+Promtail+MCP (see observability/)
#
# One-liner clone + install:
#   git clone https://github.com/szmidtpiotr/ai-gm.git && cd ai-gm && chmod +x install.sh && ./install.sh
#
# This script:
#   - Optionally installs Docker Engine (Linux: get.docker.com; requires sudo)
#   - Builds and starts backend + frontend via docker compose (production file only — no dev override)
#   - Creates SQLite DB at ./data/ai_gm.db (bind-mount), applies SQL seeds, restarts backend so migrations run
#   - Prints URLs, demo login, LLM hints, and data path at the end
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Stable project name → predictable Compose container/network naming
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-ai-gm}"

COMPOSE_FILE="docker-compose.yml"
SUMMARY_FILE="${SCRIPT_DIR}/install-summary.txt"

NO_OLLAMA=false
FRESH_DB=true
INSTALL_DOCKER=true
SKIP_BUILD=false
WITH_OBSERVABILITY=false

usage() {
  sed -n '1,35p' "$0" | tail -n +2
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-ollama) NO_OLLAMA=true; shift ;;
    --keep-db) FRESH_DB=false; shift ;;
    --skip-docker-install) INSTALL_DOCKER=false; shift ;;
    --skip-build) SKIP_BUILD=true; shift ;;
    --with-observability) WITH_OBSERVABILITY=true; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1 (use --help)"; exit 1 ;;
  esac
done

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "❌ Run this script from the AI-GM repository root (missing $COMPOSE_FILE)."
  exit 1
fi

log() { echo "[install] $*"; }
ok() { echo "✅ $*"; }
warn() { echo "⚠️  $*"; }
bad() { echo "❌ $*"; exit 1; }

# Prompt template must pass tests before Docker build (same check as pre-push / server deploy).
# Requires: python3 -m pip install pytest   (skipped if pytest not importable)
if python3 -c 'import pytest' 2>/dev/null; then
  log "Running prompt integrity tests (tests/test_prompt_integrity.py)…"
  python3 -m pytest tests/test_prompt_integrity.py -q || bad "Prompt integrity tests failed — fix backend/prompts/system_prompt.txt"
  ok "Prompt integrity OK"
else
  warn "pytest not installed — skipping prompt integrity (pip install pytest). Production deploy should run: cd ~/ai-gm && python3 -m pytest tests/test_prompt_integrity.py -q"
fi

# --- LLM defaults (exported for docker compose variable substitution) ---
export DEFAULT_CAMPAIGN_LANGUAGE="${DEFAULT_CAMPAIGN_LANGUAGE:-pl}"
export GAME_LANG="${GAME_LANG:-pl-PL}"
export DATABASE_URL="${DATABASE_URL:-sqlite:////data/ai_gm.db}"

if [[ "$NO_OLLAMA" == true ]]; then
  export LLM_PROVIDER="${LLM_PROVIDER:-openai}"
  export LLM_BASE_URL="${LLM_BASE_URL:-https://api.openai.com/v1}"
  export LLM_MODEL="${LLM_MODEL:-gpt-4o-mini}"
  export LLM_API_KEY="${LLM_API_KEY:-}"
  LLM_MODE_LABEL="Cloud (OpenAI-compatible, no local Ollama)"
else
  export LLM_PROVIDER="${LLM_PROVIDER:-ollama}"
  export LLM_BASE_URL="${LLM_BASE_URL:-http://host.docker.internal:11434}"
  export LLM_MODEL="${LLM_MODEL:-gemma4:e4b}"
  export LLM_API_KEY="${LLM_API_KEY:-}"
  LLM_MODE_LABEL="Ollama on host (${LLM_BASE_URL})"
fi

# Run docker with the same privileges that work on this host (handles fresh install before newgrp/login).
_docker() {
  if docker info >/dev/null 2>&1; then
    docker "$@"
  elif sudo -n docker info >/dev/null 2>&1 || sudo docker info >/dev/null 2>&1; then
    sudo docker "$@"
  else
    bad "Docker is installed but this user cannot talk to the daemon. Log out and back in, run: newgrp docker, or use: sudo usermod -aG docker $USER"
  fi
}

compose() {
  _docker compose -f "$COMPOSE_FILE" "$@"
}

OBS_COMPOSE_FILE="${SCRIPT_DIR}/observability/docker-compose.yml"
OBS_PROJECT_NAME="${OBS_PROJECT_NAME:-ai-gm-obs}"

compose_obs() {
  [[ -f "$OBS_COMPOSE_FILE" ]] || bad "Missing $OBS_COMPOSE_FILE (clone full repo)."
  _docker compose -f "$OBS_COMPOSE_FILE" -p "$OBS_PROJECT_NAME" "$@"
}

# --- Host packages needed before get.docker.com (minimal cloud images often lack curl) ---
ensure_linux_prereqs_for_docker_install() {
  [[ "$(uname -s)" == "Linux" ]] || return 0
  command -v curl >/dev/null 2>&1 && return 0

  log "Installing curl and CA certificates (required to fetch Docker installer)…"
  if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    sudo apt-get update -qq
    sudo apt-get install -y ca-certificates curl gnupg
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y ca-certificates curl
  elif command -v yum >/dev/null 2>&1; then
    sudo yum install -y ca-certificates curl
  elif command -v zypper >/dev/null 2>&1; then
    sudo zypper install -y ca-certificates curl
  else
    bad "curl is not installed. Install curl (and ca-certificates), then re-run this script."
  fi
  ok "curl is available"
}

docker_engine_missing() { ! command -v docker >/dev/null 2>&1; }

# Returns 0 if docker exists but `docker compose` is not usable (plugin missing).
docker_compose_plugin_missing() {
  command -v docker >/dev/null 2>&1 || return 1
  if docker compose version >/dev/null 2>&1; then return 1; fi
  if sudo -n docker compose version >/dev/null 2>&1; then return 1; fi
  if sudo docker compose version >/dev/null 2>&1; then return 1; fi
  return 0
}

# --- Docker Engine + Compose v2 plugin ---
NEED_DOCKER_INSTALL=false
if docker_engine_missing; then
  NEED_DOCKER_INSTALL=true
elif docker_compose_plugin_missing; then
  NEED_DOCKER_INSTALL=true
  warn "Docker is present but Compose v2 (docker compose) is missing; will run the official Docker installer to add it."
fi

if [[ "$NEED_DOCKER_INSTALL" == true ]]; then
  if [[ "$INSTALL_DOCKER" != true ]]; then
    bad "Docker or docker compose plugin is missing. Install Docker Engine + compose plugin, or re-run without --skip-docker-install."
  fi
  if [[ "$(uname -s)" != "Linux" ]]; then
    bad "Please install Docker Desktop (includes Compose v2) on macOS/Windows, then re-run this script."
  fi
  ensure_linux_prereqs_for_docker_install
  log "Installing Docker Engine and Compose plugin (get.docker.com)…"
  curl -fsSL https://get.docker.com | sudo sh
  ok "Docker install script finished."
  if [[ "${EUID:-$(id -u)}" -ne 0 ]] && ! groups 2>/dev/null | grep -q '\bdocker\b'; then
    warn "Adding user $USER to group docker (requires sudo)…"
    sudo usermod -aG docker "$USER" || true
  fi
  warn "If docker commands fail with permission denied, log out and back in or run: newgrp docker"
fi

if docker_engine_missing; then bad "Docker CLI still not found after install step."; fi
if docker_compose_plugin_missing; then
  bad "docker compose (Compose v2 plugin) is still missing. Try: sudo apt-get install -y docker-compose-plugin (Debian/Ubuntu) or re-run after fixing Docker packages."
fi

if ! _docker compose version >/dev/null 2>&1; then bad "docker compose is not usable (daemon or permissions)."; fi
ok "Docker and Docker Compose are available"

# --- Stop stack; optional clean SQLite on host (bind-mount ./data) ---
if [[ "$FRESH_DB" == true ]]; then
  log "Stopping stack and removing anonymous volumes…"
  compose down -v 2>/dev/null || true
  log "Removing host database file (if any): ${SCRIPT_DIR}/data/ai_gm.db"
  rm -f "${SCRIPT_DIR}/data/ai_gm.db" 2>/dev/null || true
  ok "Clean database path (or stack was not running)"
else
  log "Stopping stack (keeping ./data/ai_gm.db)…"
  compose down 2>/dev/null || true
fi

mkdir -p "${SCRIPT_DIR}/data" "${SCRIPT_DIR}/backups"

# --- Build & start backend (production compose only — avoids docker-compose.override dev bind mounts) ---
if [[ "$SKIP_BUILD" != true ]]; then
  log "Building images…"
  compose build backend frontend
fi

log "Starting backend…"
compose up -d backend

log "Waiting for backend container…"
sleep 6

log "Initializing SQLite database (schema + seeds)…"
compose exec -T backend sh -lc '
  set -e
  rm -f /data/ai_gm.db
  sqlite3 /data/ai_gm.db < /app/sql/schema.sql
  sqlite3 /data/ai_gm.db < /app/sql/002_turn_engine.sql
  sqlite3 /data/ai_gm.db < /app/sql/003_campaign_language.sql 2>/dev/null || true
  sqlite3 /data/ai_gm.db < /app/sql/004_campaign_turns.sql
  sqlite3 /data/ai_gm.db < /app/sql/seed.sql
' || bad "Database initialization failed inside container."

ok "SQL schema and seed applied"

log "Restarting backend (applies Python migrations: RAW_MIGRATIONS + admin config)…"
compose restart backend
sleep 4

log "Starting frontend…"
compose up -d frontend

if [[ "$WITH_OBSERVABILITY" == true ]]; then
  if [[ -z "${GRAFANA_ADMIN_PASSWORD:-}" ]]; then
    bad "Set GRAFANA_ADMIN_PASSWORD before using --with-observability (Grafana admin password)."
  fi
  export GRAFANA_ADMIN_PASSWORD
  export AI_GM_STORY_DB_DIR="${AI_GM_STORY_DB_DIR:-${SCRIPT_DIR}/observability-data/story-db}"
  log "Preparing SQLite snapshot directory: ${AI_GM_STORY_DB_DIR}"
  mkdir -p "${AI_GM_STORY_DB_DIR}"
  log "Starting observability stack (Grafana, Loki, Promtail, MCP)…"
  compose_obs pull
  compose_obs build mcp-server
  compose_obs up -d
  ok "Observability stack is up (project: ${OBS_PROJECT_NAME})"
  warn "On this host, do not also run observability/game-host-promtail-compose.yml — the bundled Promtail already ships Docker logs to Loki."
  warn "Point reverse proxy (see observability/reverse-proxy.nginx.example.conf) at this machine for ports 3000 / 3100 / 8001."
fi

log "Waiting for API health…"
HEALTH_OK=""
for _ in $(seq 1 24); do
  if curl -fsS --max-time 3 "http://127.0.0.1:8000/api/health" >/dev/null 2>&1; then
    HEALTH_OK=1
    break
  fi
  sleep 2
done
[[ -n "$HEALTH_OK" ]] || warn "Health check did not pass in time — check: docker compose -f docker-compose.yml logs backend"

# --- Summary (stdout + file) ---
HOST_IP=""
if command -v hostname >/dev/null 2>&1; then
  HOST_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
fi

{
  echo "=========================================="
  echo "AI-GM — installation summary"
  echo "Generated: $(date -Iseconds 2>/dev/null || date)"
  echo "=========================================="
  echo ""
  echo "LLM mode: $LLM_MODE_LABEL"
  echo "  LLM_PROVIDER=$LLM_PROVIDER"
  echo "  LLM_BASE_URL=$LLM_BASE_URL"
  echo "  LLM_MODEL=$LLM_MODEL"
  echo ""
  echo "URLs (this machine):"
  echo "  Player UI:     http://localhost:3001"
  echo "  Backend API:   http://localhost:8000/api"
  echo "  Swagger docs:  http://localhost:8000/docs"
  echo "  Health:        http://localhost:8000/api/health"
  if [[ -n "$HOST_IP" && "$HOST_IP" != "127.0.0.1" ]]; then
    echo "  Player (LAN):  http://${HOST_IP}:3001"
  fi
  if [[ "$WITH_OBSERVABILITY" == true ]]; then
    echo ""
    echo "Observability (same machine):"
    echo "  Grafana:       http://localhost:3000  (admin + GRAFANA_ADMIN_PASSWORD)"
    echo "  Loki ready:    http://localhost:3100/ready"
    echo "  MCP (local):   http://127.0.0.1:8001/mcp"
    if [[ -n "$HOST_IP" && "$HOST_IP" != "127.0.0.1" ]]; then
      echo "  Grafana (LAN): http://${HOST_IP}:3000"
    fi
    echo "  Story DB dir:  ${AI_GM_STORY_DB_DIR:-${SCRIPT_DIR}/observability-data/story-db}  (sync: scripts/db-autosync.sh, set REMOTE_DB_DIR if non-default)"
    echo "  Nginx example: ${SCRIPT_DIR}/observability/reverse-proxy.nginx.example.conf"
  fi
  echo ""
  echo "Database:"
  echo "  Engine: SQLite on host (bind-mounted into backend)"
  echo "  Host path:         ${SCRIPT_DIR}/data/ai_gm.db"
  echo "  Path in container: /data/ai_gm.db"
  echo "  Backups:           ${SCRIPT_DIR}/backups/ (see ./scripts/backup.sh)"
  echo ""
  echo "Demo login (from seed):"
  echo "  Username: demo"
  echo "  Password: demo"
  echo ""
  if [[ "$NO_OLLAMA" == true ]]; then
    echo "Next step (cloud LLM):"
    echo "  Open Settings in the UI and set your API provider, URL, model, and API key,"
    echo "  OR set environment variables and run compose again, e.g.:"
    echo "    export LLM_API_KEY=sk-..."
    echo "    docker compose -f docker-compose.yml up -d backend"
    echo ""
  else
    echo "Next step (Ollama on host):"
    echo "  Install Ollama: https://ollama.com/download"
    echo "  Then on the host run (example):"
    echo "    ollama pull ${LLM_MODEL}"
    echo "  Backend reaches Ollama at host.docker.internal:11434 (see docker-compose.yml)."
    echo ""
  fi
  echo "Useful commands:"
  echo "  docker compose -f docker-compose.yml ps"
  echo "  docker compose -f docker-compose.yml logs -f backend"
  echo "  docker compose -f docker-compose.yml down"
  echo "=========================================="
} | tee "$SUMMARY_FILE"

ok "Summary written to $SUMMARY_FILE"
echo ""
curl -sS "http://127.0.0.1:8000/api/health" 2>/dev/null | head -c 500 || true
echo ""
exit 0
