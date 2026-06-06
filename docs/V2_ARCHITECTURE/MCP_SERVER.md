# AI-GM MCP Server

**Task T50 / O4 — implemented 2026-05-25**

An MCP (Model Context Protocol) server that exposes AI-GM game data as tools. Any MCP-compatible AI assistant can call these tools to query what's happening in campaigns, monitor LLM performance, analyze player behaviour, or get a full campaign dump for external analysis.

---

## Public Endpoint

The MCP server is exposed via the dev domain — no local network access needed:

```
https://aigm-dev.studio-colorbox.com/mcp
```

Transport: **Streamable HTTP** · Access: **Read-only**

---

## Quick Start

### Connect in Perplexity

1. Open Perplexity → Settings → MCP Servers → **Add MCP Server**
2. Fill in:
   - **Name:** `AI-GM`
   - **URL:** `https://aigm-dev.studio-colorbox.com/mcp`
   - **Type:** `Streamable HTTP` (or just `HTTP`)
3. Save and start a conversation. Perplexity will list available tools automatically.

Example prompts after connecting:
- _"Co się dzieje w kampanii 3? Oceń sytuację bohatera i plan MG."_
- _"Ile graczy zginęło w ostatnim tygodniu i z czego?"_
- _"Podaj pełny kontekst kampanii 1 do analizy."_
- _"Jakie są statystyki LLM za ostatnie 24h?"_

The `get_full_campaign_context` tool returns a Polish markdown report — paste it directly into any LLM for analysis.

---

### Connect in Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "ai-gm": {
      "url": "https://aigm-dev.studio-colorbox.com/mcp"
    }
  }
}
```

Restart Claude Desktop. You'll see **AI-GM Analytics** listed in the Tools panel.

### Connect in Claude Code

```bash
claude mcp add ai-gm --transport http https://aigm-dev.studio-colorbox.com/mcp
```

### Verify the server is running

```bash
curl -X POST -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1"}}}' \
  https://aigm-dev.studio-colorbox.com/mcp
# → event: message / data: {"result":{"serverInfo":{"name":"AI-GM Analytics",...}}}
```

### Direct container access (LAN only)

```bash
# Port 8400 on the DEV host (not exposed to internet)
curl -s -o /dev/null -w "%{http_code}\n" http://192.168.1.61:8400/
# → 200
```

---

## Architecture

```
Perplexity / Claude Desktop / Claude Code / any MCP client
         ↕  Streamable HTTP (HTTPS)
aigm-dev.studio-colorbox.com/mcp   (Nginx Proxy Manager → 192.168.1.61:8400)
         ↕
ai-gm-dev-mcp-server  (Docker container, port 8400)
         ↕  SQLite read-only
/data/ai_gm.db  (bind-mounted from ./data-dev)
```

- **Transport:** Streamable HTTP (`/mcp` endpoint, proxied via NPM)
- **Access:** Read-only — cannot modify the DB
- **Language:** Returns data with Polish text as-is (same as the game); tool names and descriptions are in English
- **Container:** `ai-gm-dev-mcp-server` on DEV, port `8400`

---

## 9 Tools

### 1. `query_game_events`

Query the structured game event log.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `event_type` | str \| None | Filter by type (see Event Types below) |
| `severity` | str \| None | `info` / `warning` / `error` |
| `campaign_id` | int \| None | Filter to one campaign |
| `character_id` | int \| None | Filter to one character |
| `from_date` | str \| None | ISO datetime lower bound |
| `to_date` | str \| None | ISO datetime upper bound |
| `limit` | int | Max results (default 50) |

**Returns:** List of events with `event_type`, `severity`, `campaign_id`, `character_id`, `character_name`, `campaign_title`, `data` (parsed JSON), `created_at`.

**Event types currently wired:**
| Type | Trigger | Key data fields |
|------|---------|-----------------|
| `combat_victory` | Enemy dies | `enemies_killed`, `xp_awarded`, `rounds` |
| `player_death` | HP 0 + 3 failed saves | `cause`, `death_save_count` |
| `long_rest` | POST /rest long | `hp_restored`, `mana_restored`, `xp_unlocked` |

**Example questions this answers:**
- "How many players died this week?"
- "Show all combat victories in campaign 5"
- "What events happened in the last hour?"

---

### 2. `get_llm_performance`

LLM call statistics by period and type.

**Parameters:**
| Name | Type | Default |
|------|------|---------|
| `period` | `"24h"` \| `"7d"` \| `"30d"` | `"24h"` |
| `call_type` | str \| None | All types |

**Returns:**
```json
{
  "total_calls": 847,
  "avg_latency_ms": 1240.5,
  "cache_hit_rate_pct": 34.2,
  "error_count": 2,
  "error_rate_pct": 0.24,
  "by_call_type": [
    {"call_type": "narrator", "count": 612, "avg_latency_ms": 920, "cache_hits": 251, "errors": 1}
  ],
  "slowest_10": [...]
}
```

**Call types logged:**
`narrator` · `intent_parser` · `identity_generation` · `campaign_plan` · `chapter_summary` · `dual_summary`

---

### 3. `get_player_stats`

Per-user/character activity summary.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `user_id` | int \| None | One user (all users if omitted) |
| `from_date` | str \| None | Count turns from this date |

**Returns:** List of `{username, user_id, characters: [{name, archetype, level, xp_lifetime_earned, campaigns_played, total_turns, deaths, active_campaign_title, status, gold}]}`

---

### 4. `get_campaign_summary` ★ Most important

Full snapshot of everything about one campaign.

**Parameters:**
| Name | Type |
|------|------|
| `campaign_id` | int |

**Returns a rich dict with these sections:**

| Section | Contains |
|---------|---------|
| `campaign` | id, title, status, created_at, ended_at, death_reason, epitaph, model_id, language |
| `character` | name, archetype, level, HP, mana, XP (available/pending/lifetime), conditions, stats (STR/DEX/CON/INT/WIS/CHA/LCK), stat_modifiers, skills, gold, short_rests_used |
| `identity` | personality, flaw, bond, secret, backstory, bonds[] |
| `current_location` | label, location_type, safe_for_rest, biome, location_subtype |
| `session` | ingame_hours, ingame_time (human-readable), session_flags |
| `gm_plan` | active_arc, active_scene, active_beat, arcs_summary[], key_npcs[], key_locations[], hooks[] |
| `recent_turns` | Last 8 turns with turn_number, route, user_text, assistant_text |
| `recent_events` | Last 15 game events for this campaign |
| `inventory` | All items/weapons/consumables with type, label, quantity, equipped, slot |
| `known_npcs` | NPCs from catalog: name, role, relationship, is_alive, notes |
| `ai_summary` | Latest AI-generated summaries for `player` and `gm` audiences |
| `stats` | total_turns, narrative_turns, combat_turns, deaths, xp_events_count |
| `character_history` | Past campaigns: outcome, xp_earned, chapter_summary |

---

### 5. `get_error_log`

Recent warnings and errors combined from `game_events` + `llm_call_log`.

**Parameters:**
| Name | Default |
|------|---------|
| `hours` | 24 |
| `limit` | 20 |

**Returns:** Sorted list of `{source, id, category, severity, detail, created_at}` — `source` is `"game_event"` or `"llm_call"`.

---

### 6. `get_world_analytics`

World content statistics.

**Returns:**
```json
{
  "total_locations": 142,
  "canonical_count": 34,
  "pending_review_count": 7,
  "gm_runtime_count": 89,
  "admin_count": 18,
  "seed_count": 35,
  "most_visited": [...],
  "top_enemies": [...],
  "pending_weapons_count": 3,
  "ideas_bank_count": 12,
  "ideas_bank_avg_rating": 3.8,
  "total_hexes": 256,
  "discovered_hexes": 41
}
```

---

### 7. `query_action_log`

Paginated campaign turn log.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `campaign_id` | int | Required |
| `route` | str \| None | `narrative` / `combat` / `skill` / `rest` |
| `from_turn` | int \| None | Start turn number |
| `to_turn` | int \| None | End turn number |
| `limit` | int | Max results (default 50) |

**Returns:** List of `{turn_number, route, user_text (truncated 200), assistant_text (truncated 300), created_at}`

---

### 8. `get_system_health`

Quick system health check.

**Returns:**
```json
{
  "status": "ok",
  "active_campaigns": 3,
  "total_campaigns": 24,
  "total_users": 8,
  "total_characters": 15,
  "db_size_mb": 12.4,
  "last_llm_call": {"latency_ms": 843, "model": "...", "created_at": "..."},
  "recent_errors_1h": 0,
  "game_events_today": 47,
  "llm_calls_today": 183
}
```

---

### 9. `get_full_campaign_context` — For Perplexity / ChatGPT / any LLM

Structured dump of everything about a campaign, formatted for pasting into any external LLM.

**Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `campaign_id` | int | — | Required |
| `format` | `"text"` \| `"json"` | `"text"` | `text` = Polish markdown report; `json` = raw dict |

**`format="text"` output** (Polish markdown, paste directly into Perplexity/ChatGPT):

```markdown
# Kampania: Cienie Północy (ID: 5)
**Status:** active | **Model:** claude-sonnet-4-6 | **Język:** pl
**Stworzona:** 2026-05-20

## Bohater: Aldric
**Archetyp:** warrior | **Poziom:** 3 | **HP:** 18/24 | **Mana:** N/D
**Statystyki:** STR +3, DEX +1, CON +2, INT 0, WIS +1, CHA 0, LCK +1
**Stan:** frightened
**XP:** 45 dostępnych, 0 w oczekiwaniu, 145 łącznie
...

## Plan MG (skrót)
**Akt:** Tajemnica zamku
**Scena:** Spotkanie z wampirem
**Cel bieżącej sceny:** Gracz musi odkryć prawdziwą tożsamość hrabiego
...

## Ostatnie tury (ostatnie 6)
[Tura 23] Gracz: Wchodzę do komnaty...
[Tura 23] MG: Drzwi otwierają się z cichym...
...

## Podsumowanie AI (widok MG)
Bohater jest w połowie Aktu II...
```

**Use case:** Call this tool, copy the output, paste into Perplexity with the question "What's happening in this campaign? What should the GM watch out for?"

---

## Example Queries

| Question | Tool to call |
|----------|-------------|
| "How many players died last week?" | `query_game_events(event_type="player_death", from_date="7 days ago")` |
| "What's our LLM cache hit rate?" | `get_llm_performance(period="7d")` |
| "Is campaign 5 on track?" | `get_campaign_summary(campaign_id=5)` |
| "Show all LLM errors in the last hour" | `get_error_log(hours=1)` |
| "What's the average combat duration?" | `query_game_events(event_type="combat_victory")` → analyze `data.rounds` |
| "How many pending review entries?" | `get_world_analytics()` → `.pending_review_count` |
| "Give me everything about campaign 5 for Perplexity" | `get_full_campaign_context(campaign_id=5)` |
| "Show me what player X did in their last session" | `query_action_log(campaign_id=N, from_turn=80)` |
| "Is the server healthy?" | `get_system_health()` |

---

## Docker / Operations

### Container name (DEV)
`ai-gm-dev-mcp-server`

### Restart
```bash
ssh claude@192.168.1.61 "cd /home/piotrszmidt/ai-gm && docker compose -f docker-compose.dev.yml restart ai-gm-dev-mcp-server"
```

### Rebuild (after code changes)
```bash
ssh claude@192.168.1.61 "cd /home/piotrszmidt/ai-gm && docker compose -f docker-compose.dev.yml up -d --build ai-gm-dev-mcp-server"
```

### Logs
```bash
ssh claude@192.168.1.61 "docker logs ai-gm-dev-mcp-server --tail=50"
```

### Environment variables
| Variable | Default | Description |
|----------|---------|-------------|
| `DB_PATH` | `/data/ai_gm.db` | Path to SQLite DB inside container |
| `FASTMCP_HOST` | `0.0.0.0` | Bind host |
| `FASTMCP_PORT` | `8400` | Bind port |

---

## Files

| File | Description |
|------|-------------|
| `mcp_server/server.py` | Main MCP server — all 9 tools |
| `mcp_server/Dockerfile` | `python:3.11-slim`, installs `mcp>=1.0.0` |
| `mcp_server/requirements.txt` | `mcp>=1.0.0` |
| `docker-compose.dev.yml` | `ai-gm-dev-mcp-server` service definition |

---

## Adding New Tools

1. Add a `@mcp.tool()` function in `mcp_server/server.py`
2. Connect to DB via `get_db()` inside a `try/finally conn.close()` block
3. Use `sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)` — read-only
4. Rebuild: `docker compose -f docker-compose.dev.yml up -d --build ai-gm-dev-mcp-server`

The tool is automatically registered and exposed to MCP clients on next connection.

---

## Security

- **Read-only DB access** — the container mounts `./data-dev:/data:ro`. No writes possible.
- **No auth** on port 8400 — only expose on the local network (LAN). Do not expose to the internet.
- **No PROD equivalent** — MCP server is DEV-only. PROD observability uses Grafana/Loki.
