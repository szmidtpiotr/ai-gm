"""
AI-GM MCP Server — T50
Exposes game DB data as tools for AI assistants and external LLMs.
Read-only analytics: direct SQLite access.
Read/write player tools: HTTP API calls to the game backend.

Transport: streamable-http on port 8400 (legacy SSE also supported via MCP_TRANSPORT=sse).
"""
import json
import math
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

DB_PATH = os.environ.get("DB_PATH", "/data/ai_gm.db")
_HOST = os.environ.get("FASTMCP_HOST", "0.0.0.0")
_PORT = int(os.environ.get("FASTMCP_PORT", "8400"))

# ---------------------------------------------------------------------------
# Player session — HTTP API (write tools)
# ---------------------------------------------------------------------------

_GAME_API_URL = os.environ.get("GAME_API_URL", "http://backend:8000/api")
_TEST_USERNAME = os.environ.get("TEST_USERNAME", "")
_TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "")

_session_token: Optional[str] = None
_session_user_id: Optional[int] = None
_session_campaign_id: Optional[int] = None
_session_character_id: Optional[int] = None


def _api_headers() -> dict:
    h = {"Content-Type": "application/json"}
    if _session_token:
        h["Authorization"] = f"Bearer {_session_token}"
    return h


def _api_get(path: str, params: dict | None = None) -> dict:
    with httpx.Client(timeout=30) as c:
        r = c.get(f"{_GAME_API_URL}{path}", headers=_api_headers(), params=params)
        r.raise_for_status()
        return r.json()


def _api_post(path: str, body: dict | None = None, timeout: float = 120) -> dict:
    with httpx.Client(timeout=timeout) as c:
        r = c.post(f"{_GAME_API_URL}{path}", json=body or {}, headers=_api_headers())
        r.raise_for_status()
        return r.json()

import random as _random
import re as _re

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


def hero_level(sheet: dict) -> int:
    """Mirror of backend's xp_service.get_hero_level — derives level from
    xp_lifetime_earned when sheet.level is missing (issue #38)."""
    raw = sheet.get("level") if isinstance(sheet, dict) else None
    try:
        lvl = int(raw) if raw is not None else 0
    except (TypeError, ValueError):
        lvl = 0
    if 1 <= lvl <= 10:
        return lvl
    return min(10, int(sheet.get("xp_lifetime_earned") or 0) // 100 + 1)


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
                        "level": hero_level(sheet),
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
                "level": hero_level(sheet),
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

            char_dict = dict(char_row)
            identity_out = {
                "personality": char_dict.get("personality"),
                "flaw": sheet.get("flaw"),
                "bond": sheet.get("bond"),
                "secret": sheet.get("secret"),
                "bonds": sheet.get("bonds", []),
                "backstory": char_dict.get("backstory"),
            }

        # Active combat — override HP/conditions from live combat state if running
        active_combat_out = None
        try:
            ac_row = conn.execute(
                "SELECT id, combatants, current_turn, round FROM active_combat "
                "WHERE campaign_id = ? AND status = 'active' LIMIT 1",
                [campaign_id],
            ).fetchone()
            if ac_row:
                combatants = parse_json_safe(ac_row["combatants"], [])
                player_cb = next((c for c in combatants if c.get("type") == "player"), None)
                if player_cb and character_out:
                    character_out["current_hp"] = player_cb.get("hp_current", character_out["current_hp"])
                    character_out["conditions"] = player_cb.get("conditions", character_out["conditions"])
                enemies = [
                    {"name": c.get("name"), "key": c.get("enemy_key"), "hp": c.get("hp_current"),
                     "max_hp": c.get("hp_max"), "zone": c.get("zone", "engaged")}
                    for c in combatants if c.get("type") != "player" and (c.get("hp_current") or 0) > 0
                ]
                active_combat_out = {
                    "combat_id": ac_row["id"],
                    "round": ac_row["round"],
                    "current_turn": ac_row["current_turn"],
                    "alive_enemies": enemies,
                }
        except Exception:
            pass

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

        # Recent events (last 15) — table may not exist on older DB snapshots
        recent_events = []
        try:
            event_rows = conn.execute(
                """
                SELECT event_type, severity, event_data, created_at
                FROM game_events WHERE campaign_id = ?
                ORDER BY created_at DESC LIMIT 15
                """,
                [campaign_id],
            ).fetchall()
            for r in event_rows:
                d = dict(r)
                d["data"] = parse_json_safe(d.pop("event_data"), {})
                recent_events.append(d)
            recent_events = list(reversed(recent_events))
        except Exception:
            pass

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
        deaths = 0
        xp_events = 0
        try:
            deaths = conn.execute(
                "SELECT COUNT(*) FROM game_events WHERE campaign_id = ? AND event_type = 'player_death'",
                [campaign_id],
            ).fetchone()[0]
            xp_events = conn.execute(
                "SELECT COUNT(*) FROM game_events WHERE campaign_id = ? AND event_type LIKE '%xp%'",
                [campaign_id],
            ).fetchone()[0]
        except Exception:
            pass

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
            "active_combat": active_combat_out,
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

        # Last LLM call — table may not exist on older DB snapshots
        last_llm = None
        recent_errors = 0
        events_today = 0
        llm_calls_today = 0
        try:
            last_llm = conn.execute(
                "SELECT latency_ms, model, created_at FROM llm_call_log ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            one_hour_ago = ts_cutoff(hours_back=1)
            recent_errors = conn.execute(
                "SELECT COUNT(*) FROM game_events WHERE severity IN ('warning','error') AND created_at >= ?",
                [one_hour_ago],
            ).fetchone()[0]
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            events_today = conn.execute(
                "SELECT COUNT(*) FROM game_events WHERE created_at >= ?", [today]
            ).fetchone()[0]
            llm_calls_today = conn.execute(
                "SELECT COUNT(*) FROM llm_call_log WHERE created_at >= ?", [today]
            ).fetchone()[0]
        except Exception:
            pass

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
    active_combat = data.get("active_combat")

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
        ut = (t.get("user_text") or "")[:800]
        at = (t.get("assistant_text") or "")[:1200]
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

    # --- Active combat section ---
    if active_combat:
        enemies_str = ", ".join(
            f"{en.get('name', '?')}({en.get('hp', '?')}HP)"
            for en in active_combat.get("alive_enemies", [])
        )
        active_combat_str = (
            f"WALKA AKTYWNA — Runda {active_combat.get('round', '?')}, "
            f"tura: {active_combat.get('current_turn', '?')}\n"
            f"Zywi wrogowie: {enemies_str}"
        )
    else:
        active_combat_str = "(brak walki)"

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

## Aktywna walka
{active_combat_str}

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
# Tool 10: initialize_player_session
# ---------------------------------------------------------------------------


@mcp.tool()
def initialize_player_session() -> str:
    """
    Log in as the configured test player and auto-select an active campaign + character.
    MUST be called before submit_player_turn, change_player_zone, or flee_from_combat.
    Returns a summary of the current game state and the campaign_id to use with read tools.
    """
    global _session_token, _session_user_id, _session_campaign_id, _session_character_id

    if not _TEST_USERNAME or not _TEST_PASSWORD:
        return "ERROR: TEST_USERNAME or TEST_PASSWORD env vars not set on the MCP server."

    try:
        with httpx.Client(timeout=15) as c:
            r = c.post(
                f"{_GAME_API_URL}/auth/login",
                json={"username": _TEST_USERNAME, "password": _TEST_PASSWORD},
            )
            r.raise_for_status()
            auth = r.json()
    except Exception as e:
        return f"ERROR: Login failed — {e}"

    _session_token = auth["access_token"]
    _session_user_id = auth["user_id"]

    # ── Check for pinned MCP config in game_config_meta ──────────────────────
    _pinned_campaign_id: Optional[int] = None
    _pinned_hero_id: Optional[int] = None
    _config_mode = "auto-selected"
    try:
        with sqlite3.connect(DB_PATH) as _db:
            _db.row_factory = sqlite3.Row
            _meta_rows = _db.execute(
                "SELECT key, value FROM game_config_meta WHERE key IN (?, ?)",
                ("mcp_default_campaign_id", "mcp_default_hero_id"),
            ).fetchall()
            _meta = {r["key"]: r["value"] for r in _meta_rows}
            if _meta.get("mcp_default_campaign_id"):
                _pinned_campaign_id = int(_meta["mcp_default_campaign_id"])
            if _meta.get("mcp_default_hero_id"):
                _pinned_hero_id = int(_meta["mcp_default_hero_id"])
    except Exception:
        pass  # DB read failure — fall back to auto-select

    try:
        campaigns = _api_get("/campaigns").get("campaigns", [])
    except Exception as e:
        return f"ERROR: Could not list campaigns — {e}"

    if not campaigns:
        return "ERROR: No campaigns found. Create one in the admin panel and assign a character."

    # Use pinned campaign if configured and still exists/active, else auto-select
    campaign = None
    if _pinned_campaign_id is not None:
        campaign = next(
            (c for c in campaigns if c["id"] == _pinned_campaign_id and c.get("status") == "active"),
            None,
        )
        if campaign:
            _config_mode = f"pinned to campaign {_pinned_campaign_id}"
    if campaign is None:
        active = [c for c in campaigns if c.get("status") == "active"]
        campaign = active[0] if active else campaigns[0]
        _config_mode = "auto-selected"

    _session_campaign_id = campaign["id"]

    try:
        heroes = _api_get("/heroes", params={"user_id": _session_user_id}).get("heroes", [])
    except Exception as e:
        return f"ERROR: Could not list heroes — {e}"

    if not heroes:
        return "ERROR: No characters found. Create one in the admin panel."

    # Use pinned hero if configured and belongs to this campaign, else auto-select
    hero = None
    if _pinned_hero_id is not None:
        hero = next(
            (h for h in heroes if h["id"] == _pinned_hero_id and h.get("campaign_id") == _session_campaign_id),
            None,
        )
        if hero:
            _config_mode += f" / pinned hero {_pinned_hero_id}"
    if hero is None:
        assigned = [h for h in heroes if h.get("campaign_id") == _session_campaign_id]
        hero = assigned[0] if assigned else heroes[0]

    _session_character_id = hero["id"]

    # Clear any stale pending_skill_test that might bleed from a prior session
    try:
        with sqlite3.connect(DB_PATH) as _db:
            _db.row_factory = sqlite3.Row
            _gs_row = _db.execute(
                "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                (_session_campaign_id,),
            ).fetchone()
            if _gs_row:
                _sf = json.loads(_gs_row["session_flags"] or "{}")
                if _sf.get("pending_skill_test") or _sf.get("state") == "SKILL_TEST_PENDING":
                    _sf.pop("pending_skill_test", None)
                    _sf["state"] = "NARRATIVE"
                    _db.execute(
                        "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
                        (json.dumps(_sf, ensure_ascii=False), _gs_row["id"]),
                    )
                    _db.commit()
    except Exception:
        pass

    try:
        char = _api_get(f"/characters/{_session_character_id}")
    except Exception as e:
        return f"Partial init — character load failed: {e}"

    sheet = char.get("sheet_json", {})
    hp = sheet.get("current_hp", "?")
    max_hp = sheet.get("max_hp", "?")
    level = hero_level(sheet) if isinstance(sheet, dict) else 1
    archetype = sheet.get("archetype", "?")
    location = char.get("current_location_label", "nieznana lokacja")
    name = char.get("name", "?")
    gold = sheet.get("gold", 0)

    return (
        f"=== SESSION READY ===\n"
        f"User: {_TEST_USERNAME} (id={_session_user_id})\n"
        f"Campaign: \"{campaign['title']}\" (id={_session_campaign_id}, status={campaign['status']})\n"
        f"Character: {name} | Level {level} {archetype} | HP {hp}/{max_hp} | Gold: {gold}\n"
        f"Location: {location}\n"
        f"Config: {_config_mode}\n\n"
        f"Tip: call get_full_campaign_context({_session_campaign_id}) to read full game state,\n"
        f"then submit_player_turn(action) to take an action."
    )


# ---------------------------------------------------------------------------
# Tool 11: submit_player_turn
# ---------------------------------------------------------------------------


@mcp.tool()
def submit_player_turn(action: str) -> str:
    """
    Submit a player action to the game master. Describe what your character does in Polish.
    Examples: 'Atakuję goblina mieczem', 'Szukam ukrytych drzwi', 'Rozmawiam z karczmarką'.
    Call get_full_campaign_context(campaign_id) afterwards to see the updated state.

    Args:
        action: What your character does (Polish preferred, natural language)
    """
    if not _session_campaign_id or not _session_character_id:
        return "ERROR: Session not initialized. Call initialize_player_session() first."

    try:
        result = _api_post(
            f"/campaigns/{_session_campaign_id}/turns",
            {"character_id": _session_character_id, "text": action, "input_type": "player"},
            timeout=120,
        )
    except Exception as e:
        return f"ERROR submitting turn: {e}"

    route = result.get("route", "")

    # Auto-resolve skill tests — backend already committed a d20, just need to confirm
    if route in ("skill_test_keyword", "skill_test"):
        pending = result.get("skill_test_pending", {})
        skill_label = pending.get("skill_label") or pending.get("skill_key", "?")
        committed_d20 = pending.get("committed_d20", "?")
        mods = pending.get("modifier_breakdown", {})
        # Backend's calc_skill_modifier_info returns "total" (not "total_modifier"). Fall back
        # to the legacy key for old pending payloads.
        total_mod = (mods.get("total") if isinstance(mods, dict) else None)
        if total_mod is None and isinstance(mods, dict):
            total_mod = mods.get("total_modifier", 0)
        if total_mod is None:
            total_mod = 0
        total = (committed_d20 + total_mod) if isinstance(committed_d20, int) else "?"
        skill_test_id = pending.get("skill_test_id", "")

        if skill_test_id and isinstance(committed_d20, int):
            try:
                resolve_result = _api_post(
                    f"/campaigns/{_session_campaign_id}/skill-test/resolve",
                    {
                        "character_id": _session_character_id,
                        "skill_test_id": skill_test_id,
                        "d20_roll": committed_d20,
                    },
                    timeout=60,
                )
                prose = resolve_result.get("prose") or resolve_result.get("narrative") or ""
                # Backend nests roll outcome under skill_test_result — see api/turns.py.
                st_res = resolve_result.get("skill_test_result") or {}
                success = st_res.get("success")
                nat20 = st_res.get("nat20")
                nat1 = st_res.get("nat1")
                # For DC counter, opponent_total IS the DC threshold; for opposed it's the rolled total.
                _opp_total = st_res.get("opponent_total")
                dc = _opp_total if _opp_total is not None else (mods.get("dc", "?") if isinstance(mods, dict) else "?")
                result_label = "SUKCES" if success else "PORAŻKA"
                if nat20: result_label = "NAT 20 — KRYTYCZNY SUKCES!"
                if nat1: result_label = "NAT 1 — KRYTYCZNA PORAŻKA!"
                lines = [
                    f"🎲 Test umiejętności: {skill_label} | d20={committed_d20} + {total_mod} = {total} vs DC {dc} → {result_label}",
                ]
                if prose:
                    lines.append(f"MG:\n{prose[:2000]}")
                return "\n".join(lines)
            except Exception as resolve_err:
                return (
                    f"🎲 Test umiejętności wymagany: {skill_label}\n"
                    f"d20 (committed)={committed_d20}, modyfikator={total_mod}, suma={total}\n"
                    f"BŁĄD auto-rozwiązania: {resolve_err}\n"
                    f"Wywołaj submit_player_turn z dowolną akcją aby kontynuować."
                )
        return (
            f"🎲 Test umiejętności wymagany: {skill_label}\n"
            f"d20 (committed)={committed_d20}, modyfikator={total_mod}, suma={total}\n"
            f"Wywołaj submit_player_turn z dowolną akcją aby kontynuować."
        )

    parts = []

    res = result.get("result", {})
    if isinstance(res, str):
        # res might itself be a JSON string
        try:
            res = json.loads(res)
        except Exception:
            parts.append(f"GM:\n{res[:2000]}")
            res = {}
    if isinstance(res, dict):
        # Check for nested message field (streaming non-JSON turn response)
        msg = res.get("message", "")
        if isinstance(msg, str) and msg.strip():
            try:
                msg_parsed = json.loads(msg)
                narration = msg_parsed.get("narrative") or msg_parsed.get("narration") or msg_parsed.get("text", "")
            except Exception:
                narration = msg
        else:
            narration = res.get("narrative") or res.get("narration") or res.get("text") or res.get("assistant_text", "")
        if narration:
            parts.append(f"GM:\n{narration[:2000]}")
        roll_info = res.get("roll")
        if roll_info:
            parts.append(f"Roll: {roll_info}")
        verdict = res.get("outcome") or res.get("verdict")
        if verdict:
            parts.append(f"Outcome: {verdict}")

    cs = result.get("combat_state") or {}
    if cs:
        status = cs.get("status")
        if status == "ended":
            parts.append("\n[Walka zakończona]")
        elif status == "active":
            combatants = cs.get("combatants", [])
            player_cb = next((cb for cb in combatants if cb.get("type") == "player"), None)
            alive_enemies = [
                cb for cb in combatants
                if cb.get("type") != "player" and (cb.get("hp_current") or cb.get("current_hp") or 0) > 0
            ]
            combat_banner = ["", "⚔️ WALKA AKTYWNA"]
            if player_cb:
                php = player_cb.get("hp_current") or player_cb.get("current_hp", "?")
                mhp = player_cb.get("hp_max") or player_cb.get("max_hp", "?")
                pzone = player_cb.get("zone", "engaged")
                combat_banner.append(f"Twoje HP: {php}/{mhp} | Strefa: {pzone}")
            if alive_enemies:
                enemy_lines = [
                    f"  - {e.get('name','?')}: {e.get('hp_current') or e.get('current_hp','?')}HP [{e.get('zone','?')}]"
                    for e in alive_enemies
                ]
                combat_banner.append("Żywi wrogowie:")
                combat_banner.extend(enemy_lines)
            combat_banner.append(f"Runda: {cs.get('round_number','?')} | Tura: {cs.get('current_turn','?')}")
            parts.append("\n".join(combat_banner))

    if route and route not in ("narrative", "combat"):
        parts.append(f"[Route: {route}]")

    if not parts:
        return f"Turn submitted. Raw: {json.dumps(result, ensure_ascii=False)[:800]}"

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Tool 12: change_player_zone
# ---------------------------------------------------------------------------


@mcp.tool()
def change_player_zone() -> str:
    """
    Toggle combat zone between 'engaged' (melee / zwarcie) and 'ranged' (dystans).
    Use to close into melee range or retreat to distance. Costs your action for the turn.
    Only valid during active combat.
    """
    if not _session_campaign_id:
        return "ERROR: Session not initialized. Call initialize_player_session() first."

    try:
        result = _api_post(f"/campaigns/{_session_campaign_id}/combat/zone-change")
        if not result.get("ok", True):
            reason = result.get("reason", "unknown")
            return f"Zmiana strefy nie powiodła się: {reason}. Użyj tej akcji tylko w swojej turze."
        from_zone = result.get("from", "?")
        to_zone = result.get("to", "?")
        zone_name = {"engaged": "zwarcie", "ranged": "dystans"}.get(to_zone, to_zone)
        return f"Strefa zmieniona: {from_zone} → {to_zone} ({zone_name}). Tura zużyta."
    except Exception as e:
        return f"ERROR changing zone: {e}"


# ---------------------------------------------------------------------------
# Tool 13: flee_from_combat
# ---------------------------------------------------------------------------


@mcp.tool()
def flee_from_combat() -> str:
    """
    Attempt to flee from the current combat. You escape but forfeit XP and loot.
    Only valid during active combat.
    """
    if not _session_campaign_id:
        return "ERROR: Session not initialized. Call initialize_player_session() first."

    try:
        result = _api_post(f"/campaigns/{_session_campaign_id}/combat/flee")
        if result.get("already_ended"):
            return "Walka już się skończyła (brak aktywnej walki)."
        if result.get("fled"):
            return "Uciekłeś z walki pomyślnie."
        return f"Flee result: {json.dumps(result, ensure_ascii=False)}"
    except Exception as e:
        return f"ERROR: {e}"


# ---------------------------------------------------------------------------
# Tool 14: roll_dice
# ---------------------------------------------------------------------------


@mcp.tool()
def roll_dice(dice: str = "d20") -> str:
    """
    Roll dice for skill tests, combat, or anything else.
    Format: 'd20', '2d6', 'd8+3', 'd20-1'.
    Returns roll result with nat20/nat1 flags for d20.
    """
    m = _re.match(r'^(\d*)d(\d+)([+-]\d+)?$', dice.strip().lower())
    if not m:
        return f"Nieprawidłowy format '{dice}'. Użyj: 'd20', '2d6', 'd8+3'"
    count = int(m.group(1) or 1)
    sides = int(m.group(2))
    mod = int(m.group(3) or 0)
    if count < 1 or count > 20 or sides < 2 or sides > 100:
        return f"Nieprawidłowe parametry: liczba kości 1-20, ściany kości 2-100"
    rolls = [_random.randint(1, sides) for _ in range(count)]
    total = sum(rolls) + mod
    rolls_str = "+".join(str(r) for r in rolls)
    mod_str = f"{mod:+d}" if mod != 0 else ""
    result_line = f"🎲 {dice}: [{rolls_str}]{mod_str} = **{total}**"
    if count == 1 and sides == 20:
        if rolls[0] == 20:
            result_line += " — NAT 20: KRYTYCZNY SUKCES!"
        elif rolls[0] == 1:
            result_line += " — NAT 1: KRYTYCZNA PORAŻKA!"
    return result_line


# ---------------------------------------------------------------------------
# Tool 15: take_short_rest
# ---------------------------------------------------------------------------


@mcp.tool()
def take_short_rest() -> str:
    """
    Take a short rest to recover HP. Uses one short rest charge (max 2 per session).
    Only valid outside of active combat, in a safe location or after clearing an area.
    """
    if not _session_campaign_id or not _session_character_id:
        return "ERROR: Session not initialized. Call initialize_player_session() first."

    try:
        result = _api_post(
            f"/characters/{_session_character_id}/rest?type=short",
            {},
            timeout=30,
        )
    except Exception as e:
        return f"ERROR: {e}"

    if result.get("error"):
        return f"Odpoczynek niemożliwy: {result['error']}"

    hp_gained = result.get("hp_gained", 0)
    hp_now = result.get("current_hp", "?")
    max_hp = result.get("max_hp", "?")
    rests_left = result.get("short_rests_remaining", "?")

    if hp_gained == 0:
        return f"Odpocząłeś, ale nie odzyskałeś HP (może już jesteś na maksimum). HP: {hp_now}/{max_hp}. Odpoczynki: {rests_left} pozostało."
    return f"Krótki odpoczynek: +{hp_gained} HP. HP: {hp_now}/{max_hp}. Odpoczynki: {rests_left} pozostało."


# ---------------------------------------------------------------------------
# Forge / Campaign-creation tools (admin API)
# ---------------------------------------------------------------------------
# Requires ADMIN_TOKEN env var — same token used by the admin panel.
# Flow: forge_create_idea → forge_create_template → forge_generate_plan
#       → forge_publish_template → forge_launch_campaign
# Content: forge_create_game_entry for weapons / armor / items / enemies.

_ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
_FORGE_API = os.environ.get("GAME_API_URL", "http://backend:8000/api")


def _admin_headers() -> dict:
    return {"Content-Type": "application/json", "Authorization": f"Bearer {_ADMIN_TOKEN}"}


def _admin_get(path: str, params: dict | None = None) -> dict:
    with httpx.Client(timeout=30) as c:
        r = c.get(f"{_FORGE_API}{path}", headers=_admin_headers(), params=params)
        r.raise_for_status()
        return r.json()


def _admin_post(path: str, body: dict | None = None, timeout: float = 180) -> dict:
    with httpx.Client(timeout=timeout) as c:
        r = c.post(f"{_FORGE_API}{path}", json=body or {}, headers=_admin_headers())
        r.raise_for_status()
        return r.json()


def _admin_patch(path: str, body: dict | None = None) -> dict:
    with httpx.Client(timeout=30) as c:
        r = c.patch(f"{_FORGE_API}{path}", json=body or {}, headers=_admin_headers())
        r.raise_for_status()
        return r.json()


@mcp.tool()
def forge_workflow_guide() -> str:
    """
    Returns step-by-step instructions for creating a campaign or game content via forge tools.
    Call this first if unsure what to do next.
    """
    return """
=== FORGE WORKFLOW GUIDE ===

## CREATE CAMPAIGN (full flow)
1. forge_create_idea(title, premise, tone, themes, difficulty)
   → returns idea_id
2. forge_create_template(idea_id, title, description, atmosphere, difficulty_rating)
   → returns template_id
3. forge_generate_plan(template_id, act_count=5)
   → LLM generates acts, key_npcs, key_locations, endings (~30-60s)
   → returns full gm_plan_json
4. forge_list_templates()
   → verify template looks good
5. forge_publish_template(template_id)
   → status: draft → published
   → DONE. All players see it immediately in "Gotowe Kampanie" and start it themselves.
   → Do NOT call forge_launch_campaign for normal player access.

6. forge_launch_campaign(template_id, user_id, campaign_title)   [ADMIN ONLY]
   → Force-creates a campaign for a specific user_id (e.g. gifting a campaign).
   → Only use when explicitly asked to assign to a specific player.

## CREATE GAME CONTENT
forge_create_game_entry(entry_type, data)

entry_type="weapon": {key, label, damage_die, linked_stat, weapon_type, weapon_slot, rarity, description, allowed_classes, effect_json (optional)}
  weapon_type: melee|ranged|spell   ← EXACT VALUES ONLY (not one_handed/two_handed/thrown)
  weapon_slot: main_hand|two_handed|off_hand_only|either   ← default: main_hand
  linked_stat: STR|DEX|INT|WIS|CHA|LCK
  rarity: 1=common|2=uncommon|3=rare|4=legendary   ← INTEGER, NOT string
  damage_die: d4|d6|d8|d10|d12|2d6
  allowed_classes: ["warrior"] or ["warrior","scholar"] or ["scholar"]

entry_type="armor": {key, label, ac_bonus, item_type, rarity, description, allowed_classes, effect_json (optional)}
  item_type: light|medium|heavy|shield
  allowed_classes: ["warrior"] or ["warrior","scholar"]   ← NOTE: field is "allowed_classes" NOT "allowed_archetypes"
  ac_bonus: integer (e.g. 2 for +2 AC)
  rarity: 1=common|2=uncommon|3=rare|4=legendary   ← INTEGER, NOT string

entry_type="enemy": {key, label, hp_base, ac_base, attack_bonus, damage_die, tier, description, loot_table_key}
  tier: minion|standard|elite|boss

entry_type="item": {key, label, item_type, value_gp, rarity, description, effect_json (optional)}
  item_type: tool|quest|key|misc
  rarity: 1=common|2=uncommon|3=rare|4=legendary   ← INTEGER, NOT string

entry_type="consumable": {key, label, effect_type, base_price, rarity, description, effect_json (optional)}
  effect_type: heal|buff|antidote|utility
  rarity: 1=common|2=uncommon|3=rare|4=legendary   ← INTEGER, NOT string
  NOTE: consumables have NO allowed_classes/allowed_archetypes field — omit it

## EFFECT_JSON SCHEMA (EXACT — do NOT deviate or hallucinate)
effect_json is OPTIONAL on weapons/armor/items/consumables. If provided MUST match this exact schema:

{
  "schema_version": 1,                    ← always exactly 1
  "effect_category": "<category>",        ← one of 4 values below
  "effects": [ <one or more effect objects> ]
}

ALLOWED effect_category values:
  "gear_bonus"           → for weapons and armor (passive stat bonus)
  "consumable_immediate" → for consumables and items (one-time use)
  "character_condition"  → for conditions (poison, bleed, stun)
  "aura"                 → persistent aura effects

Each effect object in "effects" array:
  { "type": "<type>", ...extra fields based on type }

ALLOWED type values per category:
  gear_bonus:           static_stat_modifier, narrative_only
  consumable_immediate: heal_hp, restore_mana, apply_condition, remove_condition, narrative_only
  character_condition:  periodic_save, static_stat_modifier, block_action, narrative_only
  aura:                 periodic_save, static_stat_modifier, apply_condition, remove_condition, block_action, narrative_only

EXTRA FIELDS per type (only include what the type needs):
  static_stat_modifier → "stat": one of STR|DEX|CON|INT|WIS|CHA   "value": integer (e.g. 2 or -1)
  heal_hp              → "value": integer OR dice string like "1d8" or "2d6+2"
  restore_mana         → "value": integer OR dice string
  apply_condition      → "condition_key": snake_case string (e.g. "poisoned", "stunned")
  remove_condition     → "condition_key": snake_case string
  periodic_save        → "dc_key": snake_case (refs DC table) OR "value": integer
                         "tick": start_turn|each_round|on_use
                         "expires": save_success|manual|duration_rounds:N  (e.g. duration_rounds:3)
  block_action         → no extra fields
  narrative_only       → no extra fields

VALID EXAMPLES:
  Healing potion:
    {"schema_version":1,"effect_category":"consumable_immediate","effects":[{"type":"heal_hp","value":"1d8+2"}]}
  Ring of Agility (+2 DEX):
    {"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"static_stat_modifier","stat":"DEX","value":2}]}
  Poison condition (save each round):
    {"schema_version":1,"effect_category":"character_condition","effects":[{"type":"periodic_save","dc_key":"poison_resist","tick":"each_round","expires":"save_success"}]}
  Mana restore scroll:
    {"schema_version":1,"effect_category":"consumable_immediate","effects":[{"type":"restore_mana","value":"1d6"}]}

DO NOT invent fields. DO NOT use effect_json for simple flavor — omit it entirely for plain items.

## TIPS
- All keys must be snake_case, unique, lowercase
- To create campaign-scoped items (visible in template editor): pass template_id=<id> in forge_create_game_entry. Admin promotes to global from the Szablon → Przedmioty tab.
- After forge_generate_plan, plan is NOT auto-saved until tool returns success
- forge_launch_campaign requires user_id (player's numeric ID from DB)
- Campaign starts immediately after launch — player sees opening scene on first turn
"""


@mcp.tool()
def forge_create_idea(
    title: str,
    premise: str,
    tone: list[str],
    themes: list[str],
    difficulty: str = "medium",
) -> str:
    """
    Save a new campaign idea to the forge.
    tone: e.g. ["dark", "mysterious"] — adjectives describing atmosphere
    themes: e.g. ["betrayal", "ancient curse", "political intrigue"]
    difficulty: easy | medium | hard | epic
    Returns idea_id to use in forge_create_template.
    """
    if not _ADMIN_TOKEN:
        return "ERROR: ADMIN_TOKEN env var not set."
    idea_data = {
        "title": title,
        "premise": premise,
        "tone": tone,
        "themes": themes,
        "difficulty": difficulty,
        "arcs": [],
        "hooks": [],
    }
    try:
        result = _admin_post("/admin/forge/chat/save", {"idea_data": idea_data})
        idea = result.get("idea", {})
        return f"OK idea_id={idea.get('id')} title={idea.get('title')!r}"
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
def forge_create_template(
    idea_id: int,
    title: str,
    description: str = "",
    atmosphere: str = "",
    difficulty_rating: int = 3,
) -> str:
    """
    Create a campaign template linked to an idea.
    difficulty_rating: 1-5
    Returns template_id to use in forge_generate_plan.
    """
    if not _ADMIN_TOKEN:
        return "ERROR: ADMIN_TOKEN env var not set."
    try:
        result = _admin_post("/admin/forge/templates", {
            "title": title,
            "description": description,
            "atmosphere": atmosphere,
            "difficulty_rating": difficulty_rating,
            "adventure_idea_id": idea_id,
            "gm_plan_json": {},
            "hook_ids": [],
        })
        return f"OK template_id={result.get('id')} status={result.get('status')!r}"
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
def forge_generate_plan(
    template_id: int,
    act_count: int = 5,
    difficulty: str = "medium",
) -> str:
    """
    Generate full CampaignPlan V2 (acts, key_npcs, key_locations, endings) via LLM.
    Stores result in template.gm_plan_json. Takes 30-120s depending on LLM speed.
    If this call times out, the plan may still have been saved — call forge_list_templates
    to check status before retrying. Returns summary of generated plan on success.
    """
    if not _ADMIN_TOKEN:
        return "ERROR: ADMIN_TOKEN env var not set."
    try:
        result = _admin_post(
            f"/admin/forge/templates/{template_id}/generate-plan",
            {"suggested_act_count": act_count, "difficulty": difficulty},
            timeout=180,
        )
        plan = result.get("gm_plan_json") or {}
        if isinstance(plan, str):
            import json as _j
            plan = _j.loads(plan)
        acts = plan.get("acts", [])
        locs = plan.get("key_locations", [])
        npcs = plan.get("key_npcs", [])
        return (
            f"OK template_id={template_id}\n"
            f"Acts({len(acts)}): {', '.join(a.get('title','?') for a in acts)}\n"
            f"Locations({len(locs)}): {', '.join(l.get('name','?') for l in locs)}\n"
            f"NPCs({len(npcs)}): {', '.join(n.get('name','?') for n in npcs)}"
        )
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
def forge_publish_template(template_id: int) -> str:
    """
    Mark template as published so players can use it.
    Must call after forge_generate_plan succeeds.
    """
    if not _ADMIN_TOKEN:
        return "ERROR: ADMIN_TOKEN env var not set."
    try:
        result = _admin_patch(f"/admin/forge/templates/{template_id}", {"status": "published"})
        return f"OK template_id={template_id} status={result.get('status')!r}"
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
def forge_launch_campaign(
    template_id: int,
    user_id: int,
    campaign_title: str,
) -> str:
    """
    Create a campaign from a published template for a specific player.
    user_id: numeric player ID (use get_player_stats or get_world_analytics to find).
    Returns campaign_id — player can enter immediately.
    """
    if not _ADMIN_TOKEN:
        return "ERROR: ADMIN_TOKEN env var not set."
    try:
        result = _admin_post("/campaigns", {
            "title": campaign_title,
            "system_id": "fantasy",
            "model_id": "default",
            "owner_user_id": user_id,
            "language": "pl",
            "mode": "pre_built",
            "status": "active",
            "template_id": template_id,
            "selected_hook_ids": [],
        })
        return f"OK campaign_id={result.get('id')} title={result.get('title')!r}"
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
def forge_list_templates(status: str = "published") -> str:
    """
    List campaign templates.
    status: draft | published | all
    """
    if not _ADMIN_TOKEN:
        return "ERROR: ADMIN_TOKEN env var not set."
    try:
        params = {} if status == "all" else {"status": status}
        result = _admin_get("/admin/forge/templates", params)
        templates = result if isinstance(result, list) else result.get("items", result.get("templates", []))
        if not templates:
            return f"No templates with status={status!r}"
        lines = [
            f"id={t['id']} status={t.get('status')!r} title={t.get('title')!r} "
            f"plan={'YES' if t.get('gm_plan_json') and len(str(t.get('gm_plan_json',{})))>100 else 'NO'}"
            for t in templates
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
def forge_create_game_entry(entry_type: str, data: dict, template_id: int | None = None) -> str:
    """
    Create a weapon / armor / item / consumable / enemy directly in the game DB.
    entry_type: weapon | armor | item | consumable | enemy
    data: dict matching the type's required fields (call forge_workflow_guide for field reference).
    template_id: optional — link this entry to a campaign template (int ID). Admin can then promote to global from template editor.
    Returns the saved record key.
    """
    if not _ADMIN_TOKEN:
        return "ERROR: ADMIN_TOKEN env var not set."

    table_map = {
        "weapon": "game_config_weapons",
        "armor": "game_config_armor",
        "item": "game_config_items",
        "consumable": "game_config_consumables",
        "enemy": "game_config_enemies",
    }
    table = table_map.get(entry_type)
    if not table:
        return f"ERROR: unknown entry_type {entry_type!r}. Use: {list(table_map)}"

    if template_id is not None:
        data = dict(data)
        data["template_id"] = template_id

    key = data.get("key", "")
    try:
        result = _admin_post("/admin/smart-entry/save", {
            "table": table,
            "draft": data,
            "session_id": "forge-mcp",
            "target_key": None,
        })
        saved = result.get("record", {})
        return f"OK key={result.get('key') or (saved.get('key') if saved else key)!r} table={table} mode=create"
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 409 and key:
            # Key exists — update instead of insert
            try:
                result = _admin_post("/admin/smart-entry/save", {
                    "table": table,
                    "draft": data,
                    "session_id": "forge-mcp",
                    "target_key": key,
                })
                return f"OK key={key!r} table={table} mode=update (key already existed)"
            except Exception as e2:
                return f"ERROR on update after 409: {e2}"
        return f"ERROR {e.response.status_code}: {e.response.text[:200]}"
    except Exception as e:
        return f"ERROR: {e}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # "streamable-http" = MCP spec 2025-03-26 (supported by Perplexity, Claude Desktop)
    # "sse"             = legacy SSE transport (Claude Code < 1.3, older clients)
    transport = os.environ.get("MCP_TRANSPORT", "streamable-http")
    mcp.run(transport=transport)
