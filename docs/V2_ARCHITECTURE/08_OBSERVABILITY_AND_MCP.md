# AI-GM V2 — Observability, Admin Analytics & MCP Server

> Three connected systems:
> 1. Structured game event logging to DB (queryable, analytics-ready)
> 2. Admin panel analytics section (built-in, no Grafana required for common queries)
> 3. MCP server so AI agents (Claude) can query game data in natural language

---

## Current State

| Component | Status | Issue |
|-----------|--------|-------|
| Loki log aggregation | ✅ Running | Raw system logs only — not game-event aware |
| Grafana dashboards | ✅ Running | Requires knowing Grafana to use — not admin-friendly |
| Prometheus metrics | ✅ HTTP instrumentation | Request counts/latency only, no game metrics |
| `action_log` table | ✅ (planned V2) | Player actions per turn — good for turn-level audit |
| Game analytics in admin | ❌ | Nothing — admin can't see player behaviour without Grafana |
| AI-queryable logs | ❌ | No MCP server — Claude can't answer "how many players died this week?" |

---

## Part 1 — Game Event Logging (DB Layer)

### New Table: `game_events`

Structured game-level events. Different from `action_log` (which tracks every player action) — `game_events` captures meaningful milestones and system events worth monitoring.

```sql
CREATE TABLE IF NOT EXISTS game_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type      TEXT NOT NULL,
    -- Game events:
    --   combat_start | combat_victory | combat_fled | player_death
    --   beat_complete | campaign_end | dungeon_cleared
    --   fear_triggered | miscast | death_save_success | death_save_fail
    --   npc_killed | branch_generated | xp_granted
    -- System events:
    --   llm_call | llm_error | llm_slow_response
    --   session_start | session_end | long_rest

    severity        TEXT NOT NULL DEFAULT 'info'
        CHECK(severity IN ('debug','info','warning','error')),

    campaign_id     INTEGER REFERENCES campaigns(id),
    character_id    INTEGER REFERENCES characters(id),
    user_id         INTEGER REFERENCES users(id),

    event_data      TEXT NOT NULL DEFAULT '{}',
    -- JSON: event-type-specific payload (see schemas below)

    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_game_events_type_date
    ON game_events (event_type, created_at);

CREATE INDEX IF NOT EXISTS idx_game_events_campaign
    ON game_events (campaign_id, created_at);

CREATE INDEX IF NOT EXISTS idx_game_events_severity
    ON game_events (severity, created_at);
```

### Event Payload Schemas

```python
# combat_victory
{"enemies_killed": 3, "enemy_keys": ["goblin","goblin","wolf"], "xp_awarded": 45, "rounds": 4}

# player_death
{"cause": "goblin_scout", "campaign_act": 1, "hp_before": 0, "death_save_count": 3}

# beat_complete
{"beat_key": "tavern_job_offer", "act": 1, "xp_awarded": 30, "method": "persuasion"}

# llm_call (system event)
{"call_type": "narrator", "model": "claude-sonnet-4-6", "prompt_tokens": 850,
 "completion_tokens": 120, "latency_ms": 1240, "cache_hit": true}

# llm_error
{"call_type": "intent_parser", "error": "timeout", "retry_count": 1, "player_input": "..."}

# fear_triggered
{"enemy_key": "vampire_lord", "fear_dc": 16, "wis_roll": 11, "outcome": "frightened"}

# xp_granted
{"amount": 25, "source": "enemy_kill:goblin_scout", "total_xp_after": 145}
```

### New Table: `llm_call_log`

Dedicated LLM performance tracking — separate from game_events for volume reasons.

```sql
CREATE TABLE IF NOT EXISTS llm_call_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id     INTEGER REFERENCES campaigns(id),
    call_type       TEXT NOT NULL,
    -- intent_parser | narrator | identity_generation | campaign_plan
    -- npc_personality | branch_generation | chapter_summary | ideas_workshop

    model           TEXT NOT NULL,
    prompt_tokens   INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens    INTEGER GENERATED ALWAYS AS (prompt_tokens + completion_tokens) VIRTUAL,
    latency_ms      INTEGER NOT NULL,
    cache_hit       INTEGER NOT NULL DEFAULT 0,
    error           TEXT DEFAULT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_llm_log_type_date
    ON llm_call_log (call_type, created_at);
```

### Where Events Get Written

Events are written by the services that trigger them. No LLM involvement — purely mechanical:

```python
# In combat_service.py — after victory
write_game_event("combat_victory", campaign_id, character_id, user_id, {
    "enemies_killed": len(dead_enemies),
    "enemy_keys": [e.key for e in dead_enemies],
    "xp_awarded": total_xp,
    "rounds": round_count
})

# In solo_death_service.py — on death
write_game_event("player_death", campaign_id, character_id, user_id, {
    "cause": killing_enemy.key,
    "campaign_act": plan.active_act,
    "death_save_count": death_save_state.times_reached_zero
}, severity="warning")

# In llm_service.py — after every LLM call
write_llm_log(campaign_id, call_type, model, prompt_tokens, completion_tokens, latency_ms, cache_hit)
```

Helper function (new, in `app/services/event_logger.py`):
```python
def write_game_event(event_type, campaign_id, character_id, user_id, data, severity="info"):
    db.execute("""
        INSERT INTO game_events (event_type, severity, campaign_id, character_id, user_id, event_data)
        VALUES (?, ?, ?, ?, ?, ?)
    """, [event_type, severity, campaign_id, character_id, user_id, json.dumps(data)])
```

---

## Part 2 — Admin Panel Analytics Section

New section in admin panel: **"Statystyki i Logi"** (Statistics & Logs).

### Dashboard Cards (top-level KPIs)

```
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  Aktywne    │ │  Tury       │ │  Avg LLM    │ │  Błędy      │
│  kampanie   │ │  dziś       │ │  latency    │ │  24h        │
│     3       │ │    124      │ │   1.2s      │ │      1      │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

### Tab: Aktywność graczy

Table of recent sessions:
- Player name, character, campaign name
- Last active, turns in last session
- Deaths this campaign, XP total
- Sortable, filterable

### Tab: Zdarzenia gry (Game Events)

Live feed of game events — filterable by:
- Type (combat, death, beat, error...)
- Severity (info / warning / error)
- Campaign / player
- Date range

```
[Filter: all ▾] [Kampania: all ▾] [Od: 7 dni]

17:45 ⚔ combat_victory     Aldric | Goblin ×3 | 45 XP | Runda 4
17:44 📖 beat_complete      Aldric | tavern_job_offer | 30 XP
17:30 ⚠ player_death       Mira   | goblin_scout | Akt 1
17:28 💀 death_save_fail    Mira   | DC 10 | Próba 1
17:20 😱 fear_triggered     Aldric | vampire_lord | DC16 | frightened
```

Click any event → expand JSON payload.

### Tab: Wydajność LLM

```
Ostatnie 24h                    7 dni
Łączne wywołania: 847           5,234
Avg latency: 1.24s              1.31s
Cache hit rate: 34%             31%
Błędy: 2 (0.2%)                8 (0.15%)

Wg typu wywołania:
  narrator:         612  avg 0.9s  cache 41%
  intent_parser:    198  avg 0.3s  cache 28%
  campaign_plan:      8  avg 4.2s  cache 0%
  identity_gen:      12  avg 3.8s  cache 0%

Najwolniejsze wywołania (ostatnie 24h):
  17:32  campaign_plan  8.4s  (timeout retry)
  16:15  narrator       3.1s
```

### Tab: Logi błędów

Recent `severity=error` events from `game_events` + LLM errors from `llm_call_log`.

```
🔴 17:32  llm_error  intent_parser  timeout (retry: 1)
         "Rzucam się na łucznika przez zarośla"
         
🟡 16:45  campaign_plan  validation_fail  Pydantic error on act[1].key_beats
         Campaign 42, retried: success
         
🟡 14:20  llm_error  narrator  context_too_long  tokens: 12,400
```

### API Endpoints (new)

```
GET /api/admin/analytics/dashboard
    → KPI cards: active_campaigns, turns_today, avg_latency_ms, errors_24h

GET /api/admin/analytics/events
    ?event_type=&severity=&campaign_id=&from=&to=&limit=50
    → Paginated game events

GET /api/admin/analytics/llm
    ?period=24h|7d|30d
    → LLM performance stats by call_type

GET /api/admin/analytics/players
    → Recent player sessions with activity summary

GET /api/admin/analytics/errors
    ?limit=20
    → Recent errors (game_events severity=error + llm errors)
```

### Connection to Loki/Grafana

These admin panel analytics use the `game_events` and `llm_call_log` DB tables — no Loki dependency. Loki still runs for raw system logs (Python exceptions, HTTP request logs, Docker container logs). Admin panel analytics is for game-level data. Both coexist without conflict.

Admins who want deep system debugging still use Grafana/Loki. Admins who want to understand player behaviour use the built-in analytics.

---

## Part 3 — MCP Server

Allows AI agents (Claude Code, Claude Desktop, any MCP-compatible assistant) to query game data in natural language.

### Why MCP?

Without MCP, admin analysis requires:
1. Writing SQL queries manually
2. Understanding the DB schema
3. Opening Grafana for system metrics

With MCP:
```
Admin: "How many players died in dungeons last week?"
Claude: [calls query_game_events with event_type=player_death, from=7_days_ago]
Claude: "3 players died in dungeon content this week. The most common cause was 
        goblin_warchief (2 deaths). All 3 occurred in Act 1 of their campaigns, 
        suggesting the dungeon may be too hard for new characters."
```

### Architecture

**Python MCP server** using the `mcp` SDK from Anthropic. Runs as a separate process on the same host, connects directly to the SQLite DB (or via the backend API if we want auth).

```
Claude Code / Claude Desktop
         ↕ (MCP protocol, stdio or SSE)
ai-gm-mcp-server (Python)
         ↕ (direct SQLite or HTTP)
    Game DB / Backend API
```

### Server Setup

New file: `mcp_server/server.py`

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("AI-GM Analytics", instructions="""
You have access to the AI-GM game database.
Use these tools to answer questions about player behaviour, 
campaign analytics, LLM performance, and system health.
All dates are in UTC. The game language is Polish but event keys are English.
""")
```

### MCP Tools

```python
@mcp.tool()
def query_game_events(
    event_type: str | None = None,
    severity: str | None = None,
    campaign_id: int | None = None,
    character_id: int | None = None,
    from_date: str | None = None,  # ISO datetime
    to_date: str | None = None,
    limit: int = 50
) -> list[dict]:
    """Query structured game events. Use for: player deaths, combat results,
    beat completions, fear triggers, XP grants, miscast events."""
    ...

@mcp.tool()
def get_llm_performance(
    period: str = "24h",  # "24h" | "7d" | "30d"
    call_type: str | None = None
) -> dict:
    """LLM call statistics: latency, token usage, cache hit rate, error rate.
    Use for: monitoring AI performance, detecting regressions, cache analysis."""
    ...

@mcp.tool()
def get_player_stats(
    user_id: int | None = None,
    from_date: str | None = None
) -> list[dict]:
    """Player/character summary: campaigns played, deaths, XP earned, turns.
    Returns all players if user_id not specified."""
    ...

@mcp.tool()
def get_campaign_summary(campaign_id: int) -> dict:
    """Full summary for one campaign: current act, beats completed, deviations,
    key NPCs alive/dead, player XP and level, recent events."""
    ...

@mcp.tool()
def get_error_log(
    hours: int = 24,
    limit: int = 20
) -> list[dict]:
    """Recent errors: LLM failures, game event errors, validation failures.
    Use for: debugging, identifying systemic issues."""
    ...

@mcp.tool()
def get_world_analytics() -> dict:
    """World content stats: total locations, pending review count, most-used
    enemies, most-visited locations, Ideas Bank size and rating distribution."""
    ...

@mcp.tool()
def query_action_log(
    campaign_id: int,
    action_type: str | None = None,
    from_turn: int | None = None,
    to_turn: int | None = None,
    limit: int = 100
) -> list[dict]:
    """Low-level player action log: every ACTION tag resolved in a campaign.
    Use for: debugging a specific session, auditing mechanical decisions."""
    ...

@mcp.tool()
def get_system_health() -> dict:
    """Current system health: backend status, last LLM call latency,
    active campaigns, DB size, recent error count."""
    ...

@mcp.tool()
def search_events(
    query: str,
    from_date: str | None = None
) -> list[dict]:
    """Full-text search across game_events.event_data JSON.
    Use for: finding specific enemy keys, beat keys, NPC names in events."""
    ...
```

### Example Queries AI Can Answer

| Admin question | Tools used |
|---|---|
| "How many players died last week and to what?" | `query_game_events(event_type=player_death, from=7d)` |
| "What's our LLM cache hit rate?" | `get_llm_performance(period=7d)` |
| "Which beats do players skip most often?" | `query_game_events(event_type=beat_complete)` + analysis |
| "How many times has the Fear mechanic triggered?" | `query_game_events(event_type=fear_triggered)` |
| "What's the average combat duration in rounds?" | `query_game_events(event_type=combat_victory)` |
| "Show me all LLM errors in the last hour" | `get_error_log(hours=1)` |
| "What's the XP distribution across players?" | `get_player_stats()` |
| "Is campaign 42 on track?" | `get_campaign_summary(campaign_id=42)` |
| "How many pending world entries need review?" | `get_world_analytics()` |
| "What did Aldric do in the last session?" | `query_action_log(campaign_id=42, from_turn=80)` |

### Docker Integration

New service in `docker-compose.dev.yml`:

```yaml
ai-gm-mcp-server:
  build:
    context: .
    dockerfile: mcp_server/Dockerfile
  volumes:
    - ./data-dev:/data:ro          # Read-only access to game DB
  environment:
    - DB_PATH=/data/ai_gm_dev.db
    - MCP_TRANSPORT=stdio          # or sse for remote access
  ports:
    - "8400:8400"                  # Only if using SSE transport
```

### Connection for Claude Code / Claude Desktop

Add to Claude settings:
```json
{
  "mcpServers": {
    "ai-gm": {
      "command": "ssh",
      "args": ["claude@192.168.1.61", "docker exec -i ai-gm-mcp-server python mcp_server/server.py"],
      "transport": "stdio"
    }
  }
}
```

Or if running locally with SSE transport:
```json
{
  "mcpServers": {
    "ai-gm": {
      "url": "http://192.168.1.61:8400/sse"
    }
  }
}
```

---

## Implementation Notes

### Phase placement

This is a new **Phase 11 — Observability** (after Phase 10 Polish):

| Task | Description |
|------|-------------|
| 11-01 | `game_events` and `llm_call_log` DB tables + `event_logger.py` service |
| 11-02 | Write events from all relevant services (combat, death, beat, LLM calls) |
| 11-03 | Admin panel analytics section (dashboard + events + LLM + errors tabs) |
| 11-04 | MCP server: server.py + Docker service + 9 tools |
| 11-05 | Test MCP with Claude Code: verify all 10 example queries work |

### Data retention

`game_events`: keep all (small rows, high value for analytics)
`llm_call_log`: keep 90 days rolling (higher volume, prune with a scheduled job)
`action_log`: keep all (audit trail)

### No LLM in the logging path

Event writing is always synchronous, pure Python. Never calls LLM. Never blocks the game loop.

```python
# CORRECT: fire-and-forget in background
asyncio.create_task(write_game_event(...))

# or SYNC in tests/simple cases:
write_game_event(...)
```

### Loki relationship

Loki continues to receive raw structlog JSON (Python exceptions, HTTP requests, container stdout). The game_events DB table handles game-level analytics. They complement each other:

- Loki: "Why did the server crash at 3am?" (system logs)
- game_events: "How many players completed the vampire campaign?" (game analytics)
- MCP: "Answer either question in natural language" (AI-queryable layer)
