"""
AI-GM MCP Server — T50
Exposes game DB data as tools for AI assistants and external LLMs.
Read-only access to /data/ai_gm.db (SQLite, mounted as volume).

Transport: SSE on port 8400.
"""
import json
import math
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

from mcp.server.fastmcp import FastMCP

DB_PATH = os.environ.get("DB_PATH", "/data/ai_gm.db")
_HOST = os.environ.get("FASTMCP_HOST", "0.0.0.0")
_PORT = int(os.environ.get("FASTMCP_PORT", "8400"))

mcp = FastMCP("AI-GM Analytics", host=_HOST, port=_PORT)


def get_db() -> sqlite3.Connection:
    """Open a read-only connection to the game DB."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def rows_to_dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]


def parse_json_safe(text, default=None):
    if text is None:
        return default
    try:
        return json.loads(text)
    except Exception:
        return default


def ts_cutoff(hours_back: int | None = None, period: str | None = None) -> str:
    """Return ISO cutoff timestamp for filtering."""
    if period:
        mapping = {"24h": 24, "7d": 168, "30d": 720}
        hours_back = mapping.get(period, 24)
    if hours_back is None:
        hours_back = 24
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    return cutoff.strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Tool 1: query_game_events
# ---------------------------------------------------------------------------


@mcp.tool()
def query_game_events(
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    campaign_id: Optional[int] = None,
    character_id: Optional[int] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Query structured game events. Use for: player deaths, combat results, beat completions, fear triggers, XP grants, miscast events."""
    conn = get_db()
    try:
        clauses = []
        params: list = []

        if event_type:
            clauses.append("ge.event_type = ?")
            params.append(event_type)
        if severity:
            clauses.append("ge.severity = ?")
            params.append(severity)
        if campaign_id is not None:
            clauses.append("ge.campaign_id = ?")
            params.append(campaign_id)
        if character_id is not None:
            clauses.append("ge.character_id = ?")
            params.append(character_id)
        if from_date:
            clauses.append("ge.created_at >= ?")
            params.append(from_date)
        if to_date:
            clauses.append("ge.created_at <= ?")
            params.append(to_date)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"""
            SELECT
                ge.id,
                ge.event_type,
                ge.severity,
                ge.campaign_id,
                ge.character_id,
                ge.user_id,
                ge.event_data,
                ge.created_at,
                c.name  AS character_name,
                ca.title AS campaign_title
            FROM game_events ge
            LEFT JOIN characters c  ON c.id  = ge.character_id
            LEFT JOIN campaigns  ca ON ca.id = ge.campaign_id
            {where}
            ORDER BY ge.created_at DESC
            LIMIT ?
        """
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["data"] = parse_json_safe(d.pop("event_data"), {})
            result.append(d)
        return result
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tool 2: get_llm_performance
# ---------------------------------------------------------------------------


@mcp.tool()
def get_llm_performance(
    period: str = "24h",
    call_type: Optional[str] = None,
) -> dict:
    """LLM call statistics: latency, token usage, cache hit rate, error rate."""
    conn = get_db()
    try:
        cutoff = ts_cutoff(period=period)
        base_where = "WHERE created_at >= ?"
        base_params: list = [cutoff]

        type_clause = ""
        if call_type:
            base_where += " AND call_type = ?"
            base_params.append(call_type)

        # Overall stats
        overall = conn.execute(
            f"""
            SELECT
                COUNT(*)                                   AS total_calls,
                COALESCE(AVG(latency_ms), 0)               AS avg_latency_ms,
                CAST(SUM(cache_hit) AS REAL)
                    / NULLIF(COUNT(*), 0) * 100            AS cache_hit_rate_pct,
                SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) AS error_count
            FROM llm_call_log
            {base_where}
            """,
            base_params,
        ).fetchone()

        total = overall["total_calls"] or 0
        error_count = overall["error_count"] or 0

        # By call_type breakdown
        by_type_rows = conn.execute(
            f"""
            SELECT
                call_type,
                COUNT(*)                                   AS count,
                COALESCE(AVG(latency_ms), 0)               AS avg_latency_ms,
                SUM(cache_hit)                             AS cache_hits,
                SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) AS errors
            FROM llm_call_log
            {base_where}
            GROUP BY call_type
            ORDER BY count DESC
            """,
            base_params,
        ).fetchall()

        # Slowest 10 calls
        slowest = conn.execute(
            f"""
            SELECT id, call_type, model, latency_ms, created_at
            FROM llm_call_log
            {base_where}
            ORDER BY latency_ms DESC
            LIMIT 10
            """,
            base_params,
        ).fetchall()

        return {
            "period": period,
            "total_calls": total,
            "avg_latency_ms": round(overall["avg_latency_ms"] or 0, 1),
            "cache_hit_rate_pct": round(overall["cache_hit_rate_pct"] or 0, 1),
            "error_count": error_count,
            "error_rate_pct": round(error_count / total * 100, 1) if total else 0.0,
            "by_call_type": rows_to_dicts(by_type_rows),
            "slowest_10": rows_to_dicts(slowest),
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tool 3: get_player_stats
# ---------------------------------------------------------------------------


@mcp.tool()
def get_player_stats(
    user_id: Optional[int] = None,
    from_date: Optional[str] = None,
) -> list[dict]:
    """Player and character statistics: activity, level progression, deaths per character."""
    conn = get_db()
    try:
        user_clause = "WHERE u.id = ?" if user_id else ""
        user_params: list = [user_id] if user_id else []

        users = conn.execute(
            f"SELECT id, username FROM users {user_clause} ORDER BY id",
            user_params,
        ).fetchall()

        result = []
        for u in users:
            uid = u["id"]

            # Fetch characters for this user
            chars = conn.execute(
                "SELECT id, name, sheet_json, campaign_id, gold, status FROM characters WHERE user_id = ? ORDER BY id",
                [uid],
            ).fetchall()

            char_list = []
            for ch in chars:
                sheet = parse_json_safe(ch["sheet_json"], {})
                cid = ch["id"]

                # Campaigns played count
                camp_count = conn.execute(
                    "SELECT COUNT(DISTINCT campaign_id) FROM campaign_turns WHERE character_id = ?",
                    [cid],
                ).fetchone()[0]

                # Total turns
                turn_filter = " AND created_at >= ?" if from_date else ""
                turn_params = [cid] + ([from_date] if from_date else [])
                total_turns = conn.execute(
                    f"SELECT COUNT(*) FROM campaign_turns WHERE character_id = ? {turn_filter}",
                    turn_params,
                ).fetchone()[0]

                # Deaths
                deaths = conn.execute(
                    "SELECT COUNT(*) FROM game_events WHERE character_id = ? AND event_type = 'player_death'",
                    [cid],
                ).fetchone()[0]

                # Active campaign title
                active_title = None
                if ch["campaign_id"]:
                    row = conn.execute(
                        "SELECT title FROM campaigns WHERE id = ?",
                        [ch["campaign_id"]],
                    ).fetchone()
                    if row:
                        active_title = row["title"]

                char_list.append(
                    {
                        "id": cid,
                        "name": ch["name"],
                        "archetype": sheet.get("archetype") or sheet.get("class"),
                        "level": sheet.get("level", 1),
                        "xp_lifetime_earned": sheet.get("xp_lifetime_earned", 0),
                        "campaigns_played": camp_count,
                        "total_turns": total_turns,
                        "deaths": deaths,
                        "active_campaign_title": active_title,
                        "status": ch["status"],
                        "gold": ch["gold"],
                    }
                )

            result.append(
                {
                    "user_id": uid,
                    "username": u["username"],
                    "characters": char_list,
                }
            )
        return result
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tool 4: get_campaign_summary  (MOST IMPORTANT)
# ---------------------------------------------------------------------------


@mcp.tool()
def get_campaign_summary(campaign_id: int) -> dict:
    """
    Comprehensive campaign summary: character sheet, GM plan, recent turns,
    inventory, known NPCs, AI summary, and stats. Most important tool.
    """
    conn = get_db()
    try:
        # Campaign row
        camp_row = conn.execute(
            "SELECT * FROM campaigns WHERE id = ?", [campaign_id]
        ).fetchone()
        if not camp_row:
            return {"error": f"Campaign {campaign_id} not found"}
        camp = dict(camp_row)

        # Character (primary — by campaign_id + most recent)
        char_row = conn.execute(
            """
            SELECT * FROM characters
            WHERE campaign_id = ?
            ORDER BY created_at DESC LIMIT 1
            """,
            [campaign_id],
        ).fetchone()

        character_out = {}
        identity_out = {}
        char_id = None

        if char_row:
            char_id = char_row["id"]
            sheet = parse_json_safe(char_row["sheet_json"], {})
            stat_mods = sheet.get("stat_modifiers", {})
            skills_raw = sheet.get("skills", [])
            conditions = sheet.get("conditions", [])

            character_out = {
                "id": char_id,
                "name": char_row["name"],
                "archetype": sheet.get("archetype") or sheet.get("class"),
                "level": sheet.get("level", 1),
                "current_hp": sheet.get("current_hp"),
                "max_hp": sheet.get("max_hp"),
                "current_mana": sheet.get("current_mana"),
                "max_mana": sheet.get("max_mana"),
                "xp_available": sheet.get("xp_available", 0),
                "xp_lifetime_earned": sheet.get("xp_lifetime_earned", 0),
                "pending_xp": sheet.get("pending_xp", 0),
                "conditions": conditions,
                "gold": char_row["gold"],
                "short_rests_used": sheet.get("short_rests_used", 0),
                "stats": {
                    k: sheet.get(k)
                    for k in ("STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK")
                },
                "stat_modifiers": stat_mods,
                "skills": skills_raw,
            }

            identity_out = {
                "personality": char_row.get("personality"),
                "flaw": sheet.get("flaw"),
                "bond": sheet.get("bond"),
                "secret": sheet.get("secret"),
                "bonds": sheet.get("bonds", []),
                "backstory": char_row.get("backstory"),
            }

        # Current location (from game_sessions)
        session_row = conn.execute(
            "SELECT * FROM game_sessions WHERE campaign_id = ? ORDER BY created_at DESC LIMIT 1",
            [campaign_id],
        ).fetchone()
        location_out = {}
        session_out = {}
        if session_row:
            session_flags = parse_json_safe(session_row["session_flags"], {})
            ingame = session_row["ingame_hours"] or 0
            day = ingame // 24 + 1
            hour = ingame % 24
            session_out = {
                "ingame_hours": ingame,
                "ingame_time": f"Dzień {day}, {hour:02d}:00",
                "session_flags": session_flags,
            }
            loc_id = session_row["current_location_id"]
            if loc_id:
                loc_row = conn.execute(
                    "SELECT label, location_type, safe_for_rest, biome, location_subtype FROM game_locations WHERE id = ?",
                    [loc_id],
                ).fetchone()
                if loc_row:
                    location_out = dict(loc_row)

        # GM plan
        gm_plan_raw = parse_json_safe(camp.get("gm_plan_json"), {})
        gm_plan_out = {}
        try:
            arcs = gm_plan_raw.get("arcs", [])
            active_arc_id = gm_plan_raw.get("active_arc_id")
            active_scene_id = gm_plan_raw.get("active_scene_id")
            active_beat_id = gm_plan_raw.get("active_beat_id")

            active_arc = next((a for a in arcs if a.get("id") == active_arc_id), None)
            active_scene = None
            active_beat = None
            if active_arc:
                scenes = active_arc.get("scenes", [])
                active_scene = next((s for s in scenes if s.get("id") == active_scene_id), None)
                if active_scene:
                    beats = active_scene.get("beats", [])
                    active_beat = next((b for b in beats if b.get("id") == active_beat_id), None)

            all_hooks = []
            for arc in arcs:
                for s in arc.get("scenes", []):
                    all_hooks.extend(s.get("hooks", []))

            gm_plan_out = {
                "active_arc": active_arc.get("title") if active_arc else None,
                "active_scene": active_scene.get("title") if active_scene else None,
                "active_beat": active_beat.get("description") if active_beat else None,
                "arcs_summary": [
                    {
                        "id": a.get("id"),
                        "title": a.get("title"),
                        "is_active": a.get("id") == active_arc_id,
                        "is_completed": a.get("is_completed", False),
                    }
                    for a in arcs
                ],
                "key_npcs": gm_plan_raw.get("key_npcs", []),
                "key_locations": gm_plan_raw.get("key_locations", []),
                "hooks": all_hooks[:10],
            }
        except Exception:
            gm_plan_out = {"raw_keys": list(gm_plan_raw.keys()) if gm_plan_raw else []}

        # Recent turns (last 8 narrative)
        turn_rows = conn.execute(
            """
            SELECT turn_number, route, user_text, assistant_text, created_at
            FROM campaign_turns
            WHERE campaign_id = ?
            ORDER BY turn_number DESC LIMIT 8
            """,
            [campaign_id],
        ).fetchall()
        recent_turns = list(reversed(rows_to_dicts(turn_rows)))

        # Recent events (last 15)
        event_rows = conn.execute(
            """
            SELECT event_type, severity, event_data, created_at
            FROM game_events WHERE campaign_id = ?
            ORDER BY created_at DESC LIMIT 15
            """,
            [campaign_id],
        ).fetchall()
        recent_events = []
        for r in event_rows:
            d = dict(r)
            d["data"] = parse_json_safe(d.pop("event_data"), {})
            recent_events.append(d)
        recent_events = list(reversed(recent_events))

        # Inventory
        inv_rows = conn.execute(
            """
            SELECT ci.id, ci.item_key, ci.weapon_key, ci.consumable_key,
                   ci.quantity, ci.equipped, ci.slot, ci.label,
                   COALESCE(ci.label, gw.label, gi.label, gc.label) AS resolved_label
            FROM character_inventory ci
            LEFT JOIN game_config_weapons     gw ON gw.key = ci.weapon_key
            LEFT JOIN game_config_items       gi ON gi.key = ci.item_key
            LEFT JOIN game_config_consumables gc ON gc.key = ci.consumable_key
            WHERE ci.character_id = ?
            ORDER BY ci.equipped DESC, ci.id
            """,
            [char_id] if char_id else [-1],
        ).fetchall()
        inventory = []
        for r in inv_rows:
            d = dict(r)
            item_type = (
                "weapon" if d.get("weapon_key") else
                "item" if d.get("item_key") else
                "consumable"
            )
            inventory.append({
                "id": d["id"],
                "type": item_type,
                "key": d.get("weapon_key") or d.get("item_key") or d.get("consumable_key"),
                "label": d["resolved_label"],
                "quantity": d["quantity"],
                "equipped": bool(d["equipped"]),
                "slot": d["slot"],
            })

        # Known NPCs from campaign_catalog_entities (entity_type='npc')
        npc_rows = conn.execute(
            """
            SELECT entity_key, payload_json
            FROM campaign_catalog_entities
            WHERE campaign_id = ? AND entity_type = 'npc'
            ORDER BY updated_at DESC
            """,
            [campaign_id],
        ).fetchall()
        known_npcs = []
        for r in npc_rows:
            payload = parse_json_safe(r["payload_json"], {})
            known_npcs.append({
                "key": r["entity_key"],
                "name": payload.get("name") or payload.get("label") or r["entity_key"],
                "role": payload.get("role") or payload.get("npc_type"),
                "relationship": payload.get("relationship"),
                "is_alive": payload.get("is_alive", True),
                "notes": payload.get("notes") or payload.get("description"),
            })

        # AI summary (most recent, both audiences)
        ai_summaries = {}
        for audience in ("player", "gm"):
            row = conn.execute(
                """
                SELECT summary_text, created_at FROM campaign_ai_summaries
                WHERE campaign_id = ? AND audience = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                [campaign_id, audience],
            ).fetchone()
            if row:
                ai_summaries[audience] = {
                    "summary_text": row["summary_text"],
                    "created_at": row["created_at"],
                }

        # Stats
        total_turns = conn.execute(
            "SELECT COUNT(*) FROM campaign_turns WHERE campaign_id = ?",
            [campaign_id],
        ).fetchone()[0]
        narrative_turns = conn.execute(
            "SELECT COUNT(*) FROM campaign_turns WHERE campaign_id = ? AND route = 'narrative'",
            [campaign_id],
        ).fetchone()[0]
        combat_turns = conn.execute(
            "SELECT COUNT(*) FROM campaign_turns WHERE campaign_id = ? AND route = 'combat'",
            [campaign_id],
        ).fetchone()[0]
        deaths = conn.execute(
            "SELECT COUNT(*) FROM game_events WHERE campaign_id = ? AND event_type = 'player_death'",
            [campaign_id],
        ).fetchone()[0]
        xp_events = conn.execute(
            "SELECT COUNT(*) FROM game_events WHERE campaign_id = ? AND event_type LIKE '%xp%'",
            [campaign_id],
        ).fetchone()[0]

        # Character history
        char_history = []
        if char_id:
            history_rows = conn.execute(
                """
                SELECT cch.campaign_id, cch.outcome, cch.xp_earned, cch.chapter_summary, cch.completed_at,
                       ca.title AS campaign_title
                FROM character_campaign_history cch
                LEFT JOIN campaigns ca ON ca.id = cch.campaign_id
                WHERE cch.character_id = ?
                ORDER BY cch.completed_at DESC
                """,
                [char_id],
            ).fetchall()
            char_history = rows_to_dicts(history_rows)

        return {
            "campaign": {
                "id": camp["id"],
                "title": camp["title"],
                "status": camp["status"],
                "created_at": camp["created_at"],
                "ended_at": camp.get("ended_at"),
                "death_reason": camp.get("death_reason"),
                "epitaph": camp.get("epitaph"),
                "model_id": camp.get("model_id"),
                "language": camp.get("language"),
            },
            "character": character_out,
            "identity": identity_out,
            "current_location": location_out,
            "session": session_out,
            "gm_plan": gm_plan_out,
            "recent_turns": recent_turns,
            "recent_events": recent_events,
            "inventory": inventory,
            "known_npcs": known_npcs,
            "ai_summary": ai_summaries,
            "stats": {
                "total_turns": total_turns,
                "narrative_turns": narrative_turns,
                "combat_turns": combat_turns,
                "deaths": deaths,
                "xp_events_count": xp_events,
            },
            "character_history": char_history,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tool 5: get_error_log
# ---------------------------------------------------------------------------


@mcp.tool()
def get_error_log(hours: int = 24, limit: int = 20) -> list[dict]:
    """Recent warnings and errors from game_events and llm_call_log combined."""
    conn = get_db()
    try:
        cutoff = ts_cutoff(hours_back=hours)

        game_rows = conn.execute(
            """
            SELECT 'game_event' AS source, id, event_type AS category,
                   severity, event_data AS detail, created_at
            FROM game_events
            WHERE severity IN ('warning','error') AND created_at >= ?
            """,
            [cutoff],
        ).fetchall()

        llm_rows = conn.execute(
            """
            SELECT 'llm_call' AS source, id, call_type AS category,
                   'error' AS severity, error AS detail, created_at
            FROM llm_call_log
            WHERE error IS NOT NULL AND created_at >= ?
            """,
            [cutoff],
        ).fetchall()

        combined = []
        for r in game_rows:
            d = dict(r)
            d["detail"] = parse_json_safe(d["detail"], d["detail"])
            combined.append(d)
        for r in llm_rows:
            combined.append(dict(r))

        combined.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return combined[:limit]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tool 6: get_world_analytics
# ---------------------------------------------------------------------------


@mcp.tool()
def get_world_analytics() -> dict:
    """World content analytics: locations, enemies, hexes, ideas bank, pending reviews."""
    conn = get_db()
    try:
        # Location stats
        loc_stats = conn.execute(
            """
            SELECT
                COUNT(*) AS total_locations,
                SUM(CASE WHEN canonical = 1 THEN 1 ELSE 0 END) AS canonical_count,
                SUM(CASE WHEN review_status = 'pending_review' THEN 1 ELSE 0 END) AS pending_review_count,
                SUM(CASE WHEN created_by = 'gm_runtime' THEN 1 ELSE 0 END) AS gm_runtime_count,
                SUM(CASE WHEN created_by = 'admin_manual' THEN 1 ELSE 0 END) AS admin_count,
                SUM(CASE WHEN created_by = 'seed' THEN 1 ELSE 0 END) AS seed_count
            FROM game_locations WHERE is_active = 1
            """
        ).fetchone()

        # Most visited locations
        most_visited = conn.execute(
            """
            SELECT key, label, usage_count, location_type, biome
            FROM game_locations
            WHERE is_active = 1
            ORDER BY usage_count DESC LIMIT 10
            """
        ).fetchall()

        # Top enemies from game_events combat_victory
        top_enemies = conn.execute(
            """
            SELECT json_extract(event_data, '$.enemy_key') AS enemy_key, COUNT(*) AS victory_count
            FROM game_events
            WHERE event_type = 'combat_victory' AND json_extract(event_data, '$.enemy_key') IS NOT NULL
            GROUP BY enemy_key ORDER BY victory_count DESC LIMIT 10
            """
        ).fetchall()

        # Pending weapons (review_status = 'pending_review')
        pending_weapons = conn.execute(
            "SELECT COUNT(*) FROM game_config_weapons WHERE review_status = 'pending_review'"
        ).fetchone()[0]

        # Ideas bank
        ideas_stats = conn.execute(
            "SELECT COUNT(*) AS cnt, AVG(quality_rating) AS avg_rating FROM campaign_ideas WHERE is_active = 1"
        ).fetchone()

        # Hex stats
        hex_total = conn.execute("SELECT COUNT(*) FROM world_hexes WHERE is_active = 1").fetchone()[0]
        hex_discovered = conn.execute(
            "SELECT COUNT(*) FROM world_hexes WHERE is_active = 1 AND discovered_in_campaign_id IS NOT NULL"
        ).fetchone()[0]

        return {
            "total_locations": loc_stats["total_locations"],
            "canonical_count": loc_stats["canonical_count"],
            "pending_review_count": loc_stats["pending_review_count"],
            "gm_runtime_count": loc_stats["gm_runtime_count"],
            "admin_count": loc_stats["admin_count"],
            "seed_count": loc_stats["seed_count"],
            "most_visited": rows_to_dicts(most_visited),
            "top_enemies": rows_to_dicts(top_enemies),
            "pending_weapons_count": pending_weapons,
            "ideas_bank_count": ideas_stats["cnt"] or 0,
            "ideas_bank_avg_rating": round(ideas_stats["avg_rating"] or 0, 2),
            "total_hexes": hex_total,
            "discovered_hexes": hex_discovered,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tool 7: query_action_log
# ---------------------------------------------------------------------------


@mcp.tool()
def query_action_log(
    campaign_id: int,
    route: Optional[str] = None,
    from_turn: Optional[int] = None,
    to_turn: Optional[int] = None,
    limit: int = 50,
) -> list[dict]:
    """Query campaign action log (turns). Routes: narrative, combat, skill, rest."""
    conn = get_db()
    try:
        clauses = ["campaign_id = ?"]
        params: list = [campaign_id]

        if route:
            clauses.append("route = ?")
            params.append(route)
        if from_turn is not None:
            clauses.append("turn_number >= ?")
            params.append(from_turn)
        if to_turn is not None:
            clauses.append("turn_number <= ?")
            params.append(to_turn)

        where = "WHERE " + " AND ".join(clauses)
        sql = f"""
            SELECT turn_number, route,
                   SUBSTR(user_text, 1, 200)      AS user_text,
                   SUBSTR(assistant_text, 1, 300)  AS assistant_text,
                   created_at
            FROM campaign_turns
            {where}
            ORDER BY turn_number DESC LIMIT ?
        """
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return list(reversed(rows_to_dicts(rows)))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tool 8: get_system_health
# ---------------------------------------------------------------------------


@mcp.tool()
def get_system_health() -> dict:
    """System health overview: active campaigns, DB size, recent LLM calls, error count."""
    conn = get_db()
    try:
        active_campaigns = conn.execute(
            "SELECT COUNT(*) FROM campaigns WHERE status = 'active'"
        ).fetchone()[0]
        total_campaigns = conn.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0]
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_characters = conn.execute("SELECT COUNT(*) FROM characters").fetchone()[0]

        # DB size
        db_size_mb = 0.0
        try:
            db_size_mb = round(os.path.getsize(DB_PATH) / (1024 * 1024), 2)
        except Exception:
            pass

        # Last LLM call
        last_llm = conn.execute(
            "SELECT latency_ms, model, created_at FROM llm_call_log ORDER BY created_at DESC LIMIT 1"
        ).fetchone()

        # Recent errors (1h)
        one_hour_ago = ts_cutoff(hours_back=1)
        recent_errors = conn.execute(
            """
            SELECT COUNT(*) FROM game_events
            WHERE severity IN ('warning','error') AND created_at >= ?
            """,
            [one_hour_ago],
        ).fetchone()[0]

        # Events today
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        events_today = conn.execute(
            "SELECT COUNT(*) FROM game_events WHERE created_at >= ?",
            [today],
        ).fetchone()[0]

        llm_calls_today = conn.execute(
            "SELECT COUNT(*) FROM llm_call_log WHERE created_at >= ?",
            [today],
        ).fetchone()[0]

        return {
            "status": "ok",
            "active_campaigns": active_campaigns,
            "total_campaigns": total_campaigns,
            "total_users": total_users,
            "total_characters": total_characters,
            "db_size_mb": db_size_mb,
            "last_llm_call": dict(last_llm) if last_llm else None,
            "recent_errors_1h": recent_errors,
            "game_events_today": events_today,
            "llm_calls_today": llm_calls_today,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tool 9: get_full_campaign_context
# ---------------------------------------------------------------------------


@mcp.tool()
def get_full_campaign_context(campaign_id: int, format: str = "text") -> str | dict:
    """
    Comprehensive campaign dump for pasting into any external LLM (Perplexity, ChatGPT, etc.).
    format='text' returns a structured Polish markdown report.
    format='json' returns raw dict identical to get_campaign_summary output.
    """
    data = get_campaign_summary(campaign_id)

    if format == "json":
        return data

    if "error" in data:
        return f"Błąd: {data['error']}"

    camp = data.get("campaign", {})
    char = data.get("character", {})
    identity = data.get("identity", {})
    loc = data.get("current_location", {})
    session = data.get("session", {})
    gm_plan = data.get("gm_plan", {})
    turns = data.get("recent_turns", [])
    events = data.get("recent_events", [])
    inventory = data.get("inventory", [])
    ai_sum = data.get("ai_summary", {})
    stats = data.get("stats", {})
    char_history = data.get("character_history", [])
    known_npcs = data.get("known_npcs", [])

    # --- Character section ---
    stat_mods = char.get("stat_modifiers", {})
    stats_str = ", ".join(
        f"{k} {('+' if v >= 0 else '')}{v}"
        for k, v in stat_mods.items()
        if v is not None
    )
    conditions_str = ", ".join(char.get("conditions", [])) or "brak"
    skills_list = char.get("skills", [])
    skills_str = (
        ", ".join(
            f"{s['name']} R{s.get('rank', 1)}" if isinstance(s, dict) else str(s)
            for s in skills_list
        )
        if skills_list
        else "brak"
    )
    inv_str = (
        "\n".join(
            f"  - [{i['type'].upper()}] {i.get('label') or i.get('key')} x{i['quantity']}"
            + (" (wyposażony)" if i.get("equipped") else "")
            for i in inventory
        )
        or "  (pusty)"
    )

    # --- Turns section ---
    turns_str_parts = []
    for t in turns[-6:]:
        tn = t.get("turn_number", "?")
        ut = (t.get("user_text") or "")[:300]
        at = (t.get("assistant_text") or "")[:600]
        turns_str_parts.append(f"[Tura {tn}] Gracz: {ut}\n[Tura {tn}] MG: {at}")
    turns_str = "\n\n".join(turns_str_parts) or "(brak tur)"

    # --- Events section ---
    events_str_parts = []
    for e in events[-10:]:
        ts = e.get("created_at", "")[:16]
        etype = e.get("event_type", "")
        d = e.get("data", {})
        d_str = json.dumps(d, ensure_ascii=False)[:120] if d else ""
        events_str_parts.append(f"- {ts} [{etype}] {d_str}")
    events_str = "\n".join(events_str_parts) or "(brak zdarzeń)"

    # --- NPC section ---
    npc_str = (
        ", ".join(
            f"{n.get('name', n.get('key', '?'))} ({n.get('role', '?')}{', MARTWY' if not n.get('is_alive', True) else ''})"
            for n in known_npcs[:10]
        )
        or "brak"
    )

    # --- GM plan section ---
    gm_sum = ai_sum.get("gm", {}).get("summary_text", "(brak podsumowania MG)")

    # --- History section ---
    history_str = (
        "\n".join(
            f"- {h.get('campaign_title', 'Kampania ' + str(h.get('campaign_id')))} | "
            f"Wynik: {h.get('outcome', '?')} | XP: {h.get('xp_earned', 0)}"
            for h in char_history
        )
        or "(brak historii)"
    )

    hp_str = f"{char.get('current_hp', '?')}/{char.get('max_hp', '?')}"
    mana_str = (
        f"{char.get('current_mana', '?')}/{char.get('max_mana', '?')}"
        if char.get("max_mana") is not None
        else "N/D"
    )

    report = f"""# Kampania: {camp.get('title', 'N/D')} (ID: {camp.get('id', '?')})
**Status:** {camp.get('status', '?')} | **Model:** {camp.get('model_id', '?')} | **Język:** {camp.get('language', '?')}
**Stworzona:** {camp.get('created_at', '?')[:10] if camp.get('created_at') else '?'}

## Bohater: {char.get('name', 'Nieznany')}
**Archetyp:** {char.get('archetype', '?')} | **Poziom:** {char.get('level', '?')} | **HP:** {hp_str} | **Mana:** {mana_str}
**Statystyki:** {stats_str}
**Stan:** {conditions_str}
**XP:** {char.get('xp_available', 0)} dostępnych, {char.get('pending_xp', 0)} w oczekiwaniu, {char.get('xp_lifetime_earned', 0)} łącznie
**Umiejętności:** {skills_str}
**Złoto:** {char.get('gold', 0)} szt.
**Krótkie odpoczynki:** {char.get('short_rests_used', 0)}/2

### Ekwipunek
{inv_str}

### Tożsamość
**Osobowość:** {identity.get('personality') or 'brak'}
**Wada:** {identity.get('flaw') or 'brak'}
**Więź:** {identity.get('bond') or 'brak'}
**Sekret:** {identity.get('secret') or 'brak'}

## Bieżąca sesja
**Lokacja:** {loc.get('label', 'Nieznana')} ({loc.get('location_type', '?')}, biom: {loc.get('biome', '?')})
**Czas gry:** {session.get('ingame_time', 'N/D')}
**Bezpieczna lokacja:** {'Tak' if loc.get('safe_for_rest') else 'Nie'}

## Plan MG (skrót)
**Akt:** {gm_plan.get('active_arc') or 'N/D'}
**Scena:** {gm_plan.get('active_scene') or 'N/D'}
**Cel bieżącej sceny:** {gm_plan.get('active_beat') or 'N/D'}
**Znani NPC:** {npc_str}
**Akty kampanii:** {', '.join(a.get('title', '?') + (' [AKTYWNY]' if a.get('is_active') else '') + (' [UKOŃCZONY]' if a.get('is_completed') else '') for a in gm_plan.get('arcs_summary', [])) or 'N/D'}

## Ostatnie tury (ostatnie 6)
{turns_str}

## Ostatnie zdarzenia (ostatnie 10)
{events_str}

## Statystyki kampanii
- Łącznie tur: {stats.get('total_turns', 0)} (narracyjne: {stats.get('narrative_turns', 0)}, walki: {stats.get('combat_turns', 0)})
- Zgony: {stats.get('deaths', 0)}

## Podsumowanie AI (widok MG)
{gm_sum}

## Historia bohatera
{history_str}
"""
    return report.strip()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # host/port are passed to FastMCP() constructor above, driven by
    # FASTMCP_HOST (default 0.0.0.0) and FASTMCP_PORT (default 8400) env vars.
    mcp.run(transport="sse")
