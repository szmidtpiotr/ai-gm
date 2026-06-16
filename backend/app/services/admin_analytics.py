import sqlite3
from datetime import datetime, timedelta, UTC

ADMIN_DB = "/data/ai_gm.db"


def _conn():
    c = sqlite3.connect(ADMIN_DB)
    c.row_factory = sqlite3.Row
    return c


def _date_from(days: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")


# ── Overview ──────────────────────────────────────────────────────────────────

def get_overview(days: int) -> dict:
    since = _date_from(days)
    conn = _conn()
    try:
        # Turns per day
        turns_rows = conn.execute(
            """SELECT date(created_at) AS day, COUNT(*) AS count
               FROM campaign_turns
               WHERE date(created_at) >= ?
               GROUP BY day ORDER BY day""",
            (since,),
        ).fetchall()

        # New campaigns per day
        camps_rows = conn.execute(
            """SELECT date(created_at) AS day, COUNT(*) AS count
               FROM campaigns
               WHERE date(created_at) >= ?
               GROUP BY day ORDER BY day""",
            (since,),
        ).fetchall()

        # New users per day
        users_rows = conn.execute(
            """SELECT date(created_at) AS day, COUNT(*) AS count
               FROM users
               WHERE date(created_at) >= ?
               GROUP BY day ORDER BY day""",
            (since,),
        ).fetchall()

        # Totals
        totals = conn.execute(
            """SELECT
               (SELECT COUNT(*) FROM campaign_turns WHERE date(created_at) >= ?) AS turns,
               (SELECT COUNT(*) FROM campaigns WHERE status='active') AS active_campaigns,
               (SELECT COUNT(*) FROM campaigns WHERE date(created_at) >= ?) AS new_campaigns,
               (SELECT COUNT(*) FROM users WHERE date(created_at) >= ?) AS new_users,
               (SELECT COUNT(*) FROM active_combat WHERE date(created_at) >= ?) AS combats
            """,
            (since, since, since, since),
        ).fetchone()

        return {
            "turns_per_day": [{"day": r["day"], "count": r["count"]} for r in turns_rows],
            "campaigns_per_day": [{"day": r["day"], "count": r["count"]} for r in camps_rows],
            "users_per_day": [{"day": r["day"], "count": r["count"]} for r in users_rows],
            "totals": {
                "turns": totals["turns"],
                "active_campaigns": totals["active_campaigns"],
                "new_campaigns": totals["new_campaigns"],
                "new_users": totals["new_users"],
                "combats": totals["combats"],
            },
        }
    finally:
        conn.close()


# ── Dice ──────────────────────────────────────────────────────────────────────

def get_dice(days: int) -> dict:
    since = _date_from(days)
    conn = _conn()
    try:
        rows = conn.execute(
            """SELECT roll_value, actor, COUNT(*) AS count
               FROM combat_turns
               WHERE roll_value IS NOT NULL
                 AND roll_value BETWEEN 1 AND 20
                 AND date(created_at) >= ?
               GROUP BY roll_value, actor""",
            (since,),
        ).fetchall()

        # Build distribution 1..20
        distribution = {i: {"player": 0, "enemy": 0, "total": 0} for i in range(1, 21)}
        for r in rows:
            v = r["roll_value"]
            actor = r["actor"]
            cnt = r["count"]
            if actor == "player":
                distribution[v]["player"] += cnt
            elif actor == "enemy":
                distribution[v]["enemy"] += cnt
            distribution[v]["total"] += cnt

        total_rolls = sum(d["total"] for d in distribution.values())
        crit_count = distribution[20]["total"]
        fumble_count = distribution[1]["total"]
        player_total = sum(d["player"] for d in distribution.values())
        enemy_total = sum(d["enemy"] for d in distribution.values())

        return {
            "distribution": [
                {
                    "value": i,
                    "player": distribution[i]["player"],
                    "enemy": distribution[i]["enemy"],
                    "total": distribution[i]["total"],
                }
                for i in range(1, 21)
            ],
            "total_rolls": total_rolls,
            "player_rolls": player_total,
            "enemy_rolls": enemy_total,
            "crit_count": crit_count,
            "fumble_count": fumble_count,
            "crit_rate": round(crit_count / total_rolls * 100, 1) if total_rolls else 0,
            "fumble_rate": round(fumble_count / total_rolls * 100, 1) if total_rolls else 0,
            "avg_roll": round(
                sum(i * distribution[i]["total"] for i in range(1, 21)) / total_rolls, 2
            ) if total_rolls else 0,
        }
    finally:
        conn.close()


# ── Combat ────────────────────────────────────────────────────────────────────

def get_combat(days: int) -> dict:
    since = _date_from(days)
    conn = _conn()
    try:
        # Combat outcomes
        outcome_rows = conn.execute(
            """SELECT ended_reason, COUNT(*) AS count
               FROM active_combat
               WHERE date(created_at) >= ?
               GROUP BY ended_reason""",
            (since,),
        ).fetchall()

        # Avg rounds per ended combat
        avg_row = conn.execute(
            """SELECT AVG(round) AS avg_rounds, MAX(round) AS max_rounds, COUNT(*) AS total
               FROM active_combat
               WHERE status='ended' AND date(created_at) >= ?""",
            (since,),
        ).fetchone()

        # Top enemies killed (death events where actor is not 'player' = enemy died)
        enemy_rows = conn.execute(
            """SELECT target_name, COUNT(*) AS kills
               FROM combat_turns
               WHERE event_type='death' AND actor != 'player' AND target_name IS NOT NULL
                 AND date(created_at) >= ?
               GROUP BY target_name
               ORDER BY kills DESC LIMIT 10""",
            (since,),
        ).fetchall()

        # Player deaths (death events where actor is 'player')
        player_death_rows = conn.execute(
            """SELECT COALESCE(target_name, actor) AS attacker, COUNT(*) AS count
               FROM combat_turns
               WHERE event_type='death' AND actor='player'
                 AND date(created_at) >= ?
               GROUP BY attacker
               ORDER BY count DESC LIMIT 5""",
            (since,),
        ).fetchall()

        # Total damage dealt / received
        damage_rows = conn.execute(
            """SELECT actor, SUM(damage) AS total_damage, AVG(damage) AS avg_damage
               FROM combat_turns
               WHERE event_type='attack' AND hit=1 AND damage IS NOT NULL
                 AND date(created_at) >= ?
               GROUP BY actor""",
            (since,),
        ).fetchall()

        outcomes = {r["ended_reason"]: r["count"] for r in outcome_rows}
        total_combats = sum(outcomes.values())

        damage_by_actor = {}
        for r in damage_rows:
            damage_by_actor[r["actor"]] = {
                "total": r["total_damage"] or 0,
                "avg": round(r["avg_damage"] or 0, 1),
            }

        return {
            "total_combats": total_combats,
            "outcomes": {
                "victory": outcomes.get("victory", 0),
                "player_dead": outcomes.get("player_dead", 0),
                "fled": outcomes.get("fled", 0),
                "other": sum(v for k, v in outcomes.items() if k not in ("victory", "player_dead", "fled", None)),
            },
            "avg_rounds": round(avg_row["avg_rounds"] or 0, 1),
            "max_rounds": avg_row["max_rounds"] or 0,
            "top_enemies_killed": [
                {"name": r["target_name"], "kills": r["kills"]} for r in enemy_rows
            ],
            "player_killers": [
                {"name": r["attacker"] or "Unknown", "count": r["count"]} for r in player_death_rows
            ],
            "damage": damage_by_actor,
        }
    finally:
        conn.close()


# ── Events feed (#587, extended O3 #705) ────────────────────────────────────

def get_events(
    days: int = 30,
    limit: int = 100,
    conn: sqlite3.Connection | None = None,
    event_type: str | None = None,
    severity: str | None = None,
    campaign_id: int | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> dict:
    """Recent structured game events for the Zdarzenia tab.

    Reads game_events (written best-effort by event_logger.write_game_event). Missing
    table or empty → {"events": []}, never raises.
    Supports optional filters: event_type, severity, campaign_id, from_date, to_date.
    """
    since = from_date or _date_from(days)
    _own = conn is None
    c = conn or _conn()
    try:
        query = (
            "SELECT event_type, severity, campaign_id, character_id, user_id,"
            " event_data, created_at"
            " FROM game_events"
            " WHERE date(created_at) >= ?"
        )
        params: list = [since]
        if to_date:
            query += " AND date(created_at) <= ?"
            params.append(to_date)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        if campaign_id is not None:
            query += " AND campaign_id = ?"
            params.append(campaign_id)
        query += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(limit)
        rows = c.execute(query, params).fetchall()
        return {"events": [dict(r) for r in rows]}
    except sqlite3.OperationalError:
        return {"events": []}
    finally:
        if _own:
            c.close()


# ── LLM usage (#587, extended O3 #705) ─────────────────────────────────────

_PERIOD_DAYS = {"24h": 1, "7d": 7, "30d": 30}


def get_llm(days: int = 1, period: str | None = None, conn: sqlite3.Connection | None = None) -> dict:
    """LLM call telemetry: aggregate by call_type + slowest calls.

    Reads llm_call_log (written best-effort by event_logger.write_llm_log). Missing
    table or empty → empty lists, never raises.
    period overrides days when provided; accepted values: 24h | 7d | 30d.
    """
    effective_days = _PERIOD_DAYS.get(period or "", days)
    since = _date_from(effective_days)
    _own = conn is None
    c = conn or _conn()
    try:
        by_type = c.execute(
            """SELECT call_type,
                      COUNT(*) AS n,
                      AVG(latency_ms) AS avg_ms,
                      SUM(cache_hit) AS cache_hits
               FROM llm_call_log
               WHERE date(created_at) >= ?
               GROUP BY call_type
               ORDER BY n DESC""",
            (since,),
        ).fetchall()
        slowest = c.execute(
            """SELECT call_type, model, latency_ms, created_at, error
               FROM llm_call_log
               WHERE date(created_at) >= ?
               ORDER BY latency_ms DESC
               LIMIT 10""",
            (since,),
        ).fetchall()
        return {
            "by_type": [
                {
                    "call_type": r["call_type"],
                    "n": r["n"],
                    "avg_ms": round(r["avg_ms"], 1) if r["avg_ms"] is not None else None,
                    "cache_hits": r["cache_hits"] or 0,
                }
                for r in by_type
            ],
            "slowest": [dict(r) for r in slowest],
        }
    except sqlite3.OperationalError:
        return {"by_type": [], "slowest": []}
    finally:
        if _own:
            c.close()


# ── Economy ───────────────────────────────────────────────────────────────────

def get_economy(days: int) -> dict:
    since = _date_from(days)
    conn = _conn()
    try:
        # Top items acquired
        item_rows = conn.execute(
            """SELECT item_key AS name, 'item' AS type, SUM(quantity) AS total
               FROM character_inventory
               WHERE item_key IS NOT NULL AND date(acquired_at) >= ?
               GROUP BY item_key
               UNION ALL
               SELECT weapon_key AS name, 'weapon' AS type, SUM(quantity) AS total
               FROM character_inventory
               WHERE weapon_key IS NOT NULL AND date(acquired_at) >= ?
               GROUP BY weapon_key
               UNION ALL
               SELECT consumable_key AS name, 'consumable' AS type, SUM(quantity) AS total
               FROM character_inventory
               WHERE consumable_key IS NOT NULL AND date(acquired_at) >= ?
               GROUP BY consumable_key
               ORDER BY total DESC LIMIT 15""",
            (since, since, since),
        ).fetchall()

        # Items by source
        source_rows = conn.execute(
            """SELECT COALESCE(source, 'unknown') AS src, COUNT(*) AS count
               FROM character_inventory
               WHERE date(acquired_at) >= ?
               GROUP BY src ORDER BY count DESC""",
            (since,),
        ).fetchall()

        # Total gold by campaign
        gold_rows = conn.execute(
            """SELECT c.title, ch.gold, ch.gold_gp
               FROM characters ch
               JOIN campaigns c ON c.id = ch.campaign_id
               WHERE ch.gold > 0 OR ch.gold_gp > 0
               ORDER BY (ch.gold + ch.gold_gp * 100) DESC LIMIT 10""",
        ).fetchall()

        # Totals
        totals = conn.execute(
            """SELECT
               COUNT(*) AS total_items,
               SUM(quantity) AS total_qty
               FROM character_inventory
               WHERE date(acquired_at) >= ?""",
            (since,),
        ).fetchone()

        return {
            "top_items": [
                {"name": r["name"], "type": r["type"], "total": r["total"]}
                for r in item_rows
            ],
            "by_source": [
                {"source": r["src"], "count": r["count"]} for r in source_rows
            ],
            "gold_leaders": [
                {
                    "campaign": r["title"],
                    "gold_sp": r["gold"],
                    "gold_gp": r["gold_gp"],
                }
                for r in gold_rows
            ],
            "totals": {
                "items_acquired": totals["total_items"] or 0,
                "quantity_total": totals["total_qty"] or 0,
            },
        }
    finally:
        conn.close()


# ── O3 (#705): Dashboard KPI, Players, Errors ────────────────────────────────

def get_dashboard(conn: sqlite3.Connection | None = None) -> dict:
    """KPI cards: active_campaigns, turns_today, avg_latency_ms, errors_24h."""
    _own = conn is None
    c = conn or _conn()
    try:
        active_campaigns = c.execute(
            "SELECT COUNT(*) FROM campaigns WHERE status='active'"
        ).fetchone()[0] or 0

        turns_today = c.execute(
            "SELECT COUNT(*) FROM campaign_turns WHERE date(created_at) = date('now')"
        ).fetchone()[0] or 0

        avg_row = c.execute(
            "SELECT AVG(latency_ms) FROM llm_call_log"
            " WHERE created_at >= datetime('now', '-1 day')"
        ).fetchone()
        avg_latency_ms = round(avg_row[0]) if avg_row and avg_row[0] is not None else None

        ge_errors = c.execute(
            "SELECT COUNT(*) FROM game_events"
            " WHERE severity='error' AND created_at >= datetime('now', '-1 day')"
        ).fetchone()[0] or 0
        llm_errors = c.execute(
            "SELECT COUNT(*) FROM llm_call_log"
            " WHERE error IS NOT NULL AND created_at >= datetime('now', '-1 day')"
        ).fetchone()[0] or 0

        return {
            "active_campaigns": active_campaigns,
            "turns_today": turns_today,
            "avg_latency_ms": avg_latency_ms,
            "errors_24h": ge_errors + llm_errors,
        }
    except sqlite3.OperationalError:
        return {"active_campaigns": 0, "turns_today": 0, "avg_latency_ms": None, "errors_24h": 0}
    finally:
        if _own:
            c.close()


def get_players(conn: sqlite3.Connection | None = None) -> dict:
    """Recent player activity summary — one row per character with an active campaign."""
    _own = conn is None
    c = conn or _conn()
    try:
        rows = c.execute(
            """SELECT u.id AS user_id, u.username, u.display_name,
                      ch.name AS character_name,
                      camps.title AS campaign_title,
                      MAX(ct.created_at) AS last_active,
                      COUNT(ct.id) AS turns_count
               FROM characters ch
               JOIN users u ON u.id = ch.user_id
               LEFT JOIN campaigns camps ON camps.id = ch.campaign_id
               LEFT JOIN campaign_turns ct ON ct.campaign_id = ch.campaign_id
               WHERE ch.campaign_id IS NOT NULL
                 AND ch.name NOT LIKE '[SBX] %'
               GROUP BY ch.id, u.id, u.username, u.display_name, ch.name, camps.title
               ORDER BY last_active DESC
               LIMIT 50"""
        ).fetchall()

        death_rows = c.execute(
            "SELECT user_id, COUNT(*) AS cnt FROM game_events"
            " WHERE event_type='player_death' GROUP BY user_id"
        ).fetchall()
        deaths_by_user = {r["user_id"]: r["cnt"] for r in death_rows}

        return {
            "players": [
                {
                    "username": r["username"],
                    "display_name": r["display_name"],
                    "character_name": r["character_name"],
                    "campaign_title": r["campaign_title"],
                    "last_active": r["last_active"],
                    "turns_count": r["turns_count"] or 0,
                    "deaths": deaths_by_user.get(r["user_id"], 0),
                }
                for r in rows
            ]
        }
    except sqlite3.OperationalError:
        return {"players": []}
    finally:
        if _own:
            c.close()


def get_errors(limit: int = 20, conn: sqlite3.Connection | None = None) -> dict:
    """Merged error feed: game_events severity=error + llm_call_log with error."""
    _own = conn is None
    c = conn or _conn()
    try:
        ge_rows = c.execute(
            "SELECT 'game_event' AS source, event_type, severity,"
            " campaign_id, event_data AS detail, created_at"
            " FROM game_events WHERE severity='error'"
            " ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        llm_rows = c.execute(
            "SELECT 'llm_error' AS source, call_type AS event_type, 'error' AS severity,"
            " campaign_id, error AS detail, created_at"
            " FROM llm_call_log WHERE error IS NOT NULL"
            " ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        merged = [dict(r) for r in ge_rows] + [dict(r) for r in llm_rows]
        merged.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return {"errors": merged[:limit]}
    except sqlite3.OperationalError:
        return {"errors": []}
    finally:
        if _own:
            c.close()
