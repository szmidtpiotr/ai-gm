"""
World Service — V2 Phase 03 Tasks 08/09/10

Handles:
- [CREATE_LOCATION], [CREATE_NPC], [CREATE_ENEMY] tag parsing and DB creation
- [NPC_KILLED] tag processing
- Available content index builder (locations, NPCs, enemies per location)
- Review queue helpers for admin
- Current location lookup with safe_for_rest
"""

from __future__ import annotations

import json
import re
import sqlite3
import structlog
from typing import Any

logger = structlog.get_logger()

DB_PATH = "/data/ai_gm.db"

# ── CREATE tag patterns ────────────────────────────────────────────────────

_CREATE_LOC_RE = re.compile(
    r"\[CREATE_LOCATION:\s*(.*?)\]", re.IGNORECASE | re.DOTALL
)
_CREATE_NPC_RE = re.compile(
    r"\[CREATE_NPC:\s*(.*?)\]", re.IGNORECASE | re.DOTALL
)
_CREATE_ENEMY_RE = re.compile(
    r"\[CREATE_ENEMY:\s*(.*?)\]", re.IGNORECASE | re.DOTALL
)
_NPC_KILLED_RE = re.compile(
    r"\[NPC_KILLED:\s*key\s*=\s*([^\]\s,]+)\]", re.IGNORECASE
)


def _parse_kv(raw: str) -> dict[str, str]:
    """Parse 'key=value, key2=value2' into a dict."""
    params: dict[str, str] = {}
    for part in raw.split(","):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            params[k.strip().lower()] = v.strip()
    return params


# ── Tag processing ─────────────────────────────────────────────────────────

def process_create_tags(
    narrative: str,
    conn: sqlite3.Connection,
    campaign_id: int,
) -> tuple[str, list[dict]]:
    """
    Scan narrative for [CREATE_*] and [NPC_KILLED] tags.
    Create/update DB records. Strip tags from narrative.
    Returns (cleaned_narrative, list_of_created_entities).
    """
    created: list[dict] = []
    cleaned = narrative

    # [CREATE_LOCATION]
    for m in _CREATE_LOC_RE.finditer(narrative):
        params = _parse_kv(m.group(1))
        key = params.get("key", "").strip()
        if not key:
            cleaned = cleaned.replace(m.group(0), "")
            continue
        entity = _get_or_create_location(conn, key, params, campaign_id)
        if entity:
            created.append({"type": "location", **entity})
        cleaned = cleaned.replace(m.group(0), "")

    # [CREATE_NPC]
    for m in _CREATE_NPC_RE.finditer(narrative):
        params = _parse_kv(m.group(1))
        key = params.get("key", "").strip()
        if not key:
            cleaned = cleaned.replace(m.group(0), "")
            continue
        entity = _get_or_create_npc(conn, key, params, campaign_id)
        if entity:
            created.append({"type": "npc", **entity})
        cleaned = cleaned.replace(m.group(0), "")

    # [CREATE_ENEMY]
    for m in _CREATE_ENEMY_RE.finditer(narrative):
        params = _parse_kv(m.group(1))
        key = params.get("key", "").strip()
        if not key:
            cleaned = cleaned.replace(m.group(0), "")
            continue
        entity = _get_or_create_enemy(conn, key, params, campaign_id)
        if entity:
            created.append({"type": "enemy", **entity})
        cleaned = cleaned.replace(m.group(0), "")

    # [NPC_KILLED]
    for m in _NPC_KILLED_RE.finditer(narrative):
        npc_key = m.group(1).strip()
        _process_npc_killed(conn, npc_key, campaign_id)
        cleaned = cleaned.replace(m.group(0), "")
        logger.info("npc_killed_processed", npc_key=npc_key, campaign_id=campaign_id)

    return cleaned.strip(), created


# ── Entity create helpers ──────────────────────────────────────────────────

def _get_or_create_location(
    conn: sqlite3.Connection, key: str, params: dict, campaign_id: int
) -> dict | None:
    # Check if exists
    row = conn.execute(
        "SELECT key, label, location_type, safe_for_rest, review_status FROM game_locations WHERE key = ?",
        (key,)
    ).fetchone()
    if row:
        return dict(row)

    label = params.get("label", key.replace("_", " ").title())
    loc_type = params.get("type", "sub").lower()
    if loc_type not in ("macro", "sub"):
        loc_type = "sub"
    parent_key = params.get("parent_key", "")
    atmosphere = params.get("atmosphere", "")
    description = params.get("description", "")

    # Resolve parent_id
    parent_id = None
    if parent_key:
        p_row = conn.execute("SELECT id FROM game_locations WHERE key = ?", (parent_key,)).fetchone()
        if p_row:
            parent_id = p_row[0]

    # Build rules JSON with atmosphere if provided
    rules_json = json.dumps({"atmosphere": atmosphere}) if atmosphere else None

    try:
        conn.execute(
            """INSERT OR IGNORE INTO game_locations
               (key, label, location_type, description, parent_id, parent_key,
                rules, review_status, ai_generated, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending_review', 1, 1)""",
            (key, label, loc_type, description, parent_id, parent_key or None, rules_json)
        )
        conn.commit()
        logger.info("create_location_tag_processed", key=key, campaign_id=campaign_id)
        return {"key": key, "label": label, "review_status": "pending_review"}
    except Exception as e:
        logger.warning("create_location_failed", key=key, error=str(e))
        return None


def _get_or_create_npc(
    conn: sqlite3.Connection, key: str, params: dict, campaign_id: int
) -> dict | None:
    row = conn.execute(
        "SELECT key, label FROM npcs WHERE key = ?", (key,)
    ).fetchone()
    if row:
        return dict(row)

    name = params.get("name", key.replace("_", " ").title())
    role = params.get("role", "neutral").lower()
    personality_raw = params.get("personality", "")
    location_key = params.get("location_key", "")

    # Map role to npc_type
    npc_type_map = {
        "innkeeper": "neutral", "merchant": "merchant", "shopkeeper": "merchant",
        "quest_giver": "quest_giver", "informant": "neutral", "ally": "ally",
        "antagonist": "antagonist", "thug": "antagonist", "guard": "neutral",
    }
    npc_type = npc_type_map.get(role, "neutral")

    # Generate personality_prompt from raw description (truncate to 300)
    personality_prompt = personality_raw[:300] if personality_raw else f"{name} — {role}."

    try:
        conn.execute(
            """INSERT OR IGNORE INTO npcs
               (key, label, npc_type, personality_prompt, keyword_triggers,
                personality_json, review_status, is_active, is_shop)
               VALUES (?, ?, ?, ?, '[]', '{}', 'pending_review', 1, 0)""",
            (key, name, npc_type, personality_prompt)
        )
        conn.commit()

        # Assign to location if provided
        if location_key:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO location_npc_assignments (location_key, npc_key) VALUES (?, ?)",
                    (location_key, key)
                )
                conn.commit()
            except Exception:
                pass

        logger.info("create_npc_tag_processed", key=key, campaign_id=campaign_id)
        return {"key": key, "label": name, "review_status": "pending_review"}
    except Exception as e:
        logger.warning("create_npc_failed", key=key, error=str(e))
        return None


def _get_or_create_enemy(
    conn: sqlite3.Connection, key: str, params: dict, campaign_id: int
) -> dict | None:
    row = conn.execute(
        "SELECT key, label FROM game_config_enemies WHERE key = ?", (key,)
    ).fetchone()
    if row:
        return dict(row)

    name = params.get("name", key.replace("_", " ").title())
    tier = params.get("tier", "standard").lower()
    if tier not in ("weak", "standard", "elite", "boss"):
        tier = "standard"
    based_on = params.get("based_on", "")

    # Tier defaults
    tier_stats = {
        "weak":     {"hp_base": 6,  "ac_base": 9,  "attack_bonus": 1, "damage_die": "d4", "xp_award": 10},
        "standard": {"hp_base": 12, "ac_base": 11, "attack_bonus": 2, "damage_die": "d6", "xp_award": 25},
        "elite":    {"hp_base": 25, "ac_base": 14, "attack_bonus": 4, "damage_die": "d8", "xp_award": 50},
        "boss":     {"hp_base": 50, "ac_base": 16, "attack_bonus": 6, "damage_die": "d10", "xp_award": 150},
    }
    stats = dict(tier_stats[tier])

    # Inherit from based_on if provided
    if based_on:
        base = conn.execute(
            "SELECT hp_base, ac_base, attack_bonus, damage_die FROM game_config_enemies WHERE key = ?",
            (based_on,)
        ).fetchone()
        if base:
            stats["hp_base"] = base["hp_base"]
            stats["ac_base"] = base["ac_base"]
            stats["attack_bonus"] = base["attack_bonus"]
            stats["damage_die"] = base["damage_die"]

    try:
        conn.execute(
            """INSERT OR IGNORE INTO game_config_enemies
               (key, label, tier, hp_base, ac_base, attack_bonus, damage_die,
                damage_bonus, attacks_per_turn, xp_award, is_active, review_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0, 1, ?, 1, 'pending_review')""",
            (key, name, tier, stats["hp_base"], stats["ac_base"],
             stats["attack_bonus"], stats["damage_die"], stats["xp_award"])
        )
        conn.commit()
        logger.info("create_enemy_tag_processed", key=key, campaign_id=campaign_id)
        return {"key": key, "label": name, "tier": tier, "review_status": "pending_review"}
    except Exception as e:
        logger.warning("create_enemy_failed", key=key, error=str(e))
        return None


def _process_npc_killed(
    conn: sqlite3.Connection, npc_key: str, campaign_id: int
) -> None:
    """Mark NPC as dead (is_active=0) and update campaign plan."""
    try:
        conn.execute("UPDATE npcs SET is_active = 0 WHERE key = ?", (npc_key,))
        conn.commit()
    except Exception as e:
        logger.warning("npc_killed_update_failed", npc_key=npc_key, error=str(e))
        return

    # Update campaign plan key_npcs alive flag
    try:
        row = conn.execute(
            "SELECT plan_json FROM campaigns WHERE id = ?", (campaign_id,)
        ).fetchone()
        if not row or not row[0]:
            return
        plan = json.loads(row[0])
        changed = False
        for npc in plan.get("key_npcs", []):
            if npc.get("key") == npc_key and npc.get("alive", True):
                npc["alive"] = False
                changed = True
        if changed:
            conn.execute(
                "UPDATE campaigns SET plan_json = ? WHERE id = ?",
                (json.dumps(plan, ensure_ascii=False), campaign_id)
            )
            conn.commit()
            logger.info("campaign_plan_npc_marked_dead", npc_key=npc_key, campaign_id=campaign_id)
    except Exception as e:
        logger.warning("npc_killed_plan_update_failed", npc_key=npc_key, error=str(e))


# ── Available content index ────────────────────────────────────────────────

def build_available_content_index(
    conn: sqlite3.Connection, location_key: str | None
) -> str:
    """
    Build the [AVAILABLE CONTENT] block injected into LLM context.
    Lists NPCs and enemies for the current location.
    """
    if not location_key:
        return ""

    lines = [
        "[AVAILABLE CONTENT — use these keys, do not invent new ones unless unavoidable]",
        f"Location: {location_key}",
    ]

    # NPCs in location — check location_npc_assignments first, then npc_keys JSON
    npc_rows = conn.execute(
        """SELECT n.key, n.label, n.npc_type
           FROM location_npc_assignments lna
           JOIN npcs n ON n.key = lna.npc_key
           WHERE lna.location_key = ? AND lna.is_active = 1 AND n.is_active = 1""",
        (location_key,)
    ).fetchall()

    if not npc_rows:
        # Fallback to npc_keys JSON on game_locations
        loc_row = conn.execute(
            "SELECT npc_keys FROM game_locations WHERE key = ?", (location_key,)
        ).fetchone()
        if loc_row and loc_row[0]:
            try:
                keys = json.loads(loc_row[0])
                if keys:
                    npc_rows = conn.execute(
                        f"SELECT key, label, npc_type FROM npcs WHERE key IN ({','.join('?'*len(keys))}) AND is_active=1",
                        keys
                    ).fetchall()
            except Exception:
                pass

    if npc_rows:
        lines.append("\nNearby NPCs:")
        for r in npc_rows:
            lines.append(f"  - {r['key']}: {r['label']} ({r['npc_type']})")

    # Enemies in location — check location_enemy_assignments first, then enemy_keys JSON
    enemy_rows = conn.execute(
        """SELECT e.key, e.label, e.tier
           FROM location_enemy_assignments lea
           JOIN game_config_enemies e ON e.key = lea.enemy_key
           WHERE lea.location_key = ? AND lea.is_active = 1 AND e.is_active = 1""",
        (location_key,)
    ).fetchall()

    if not enemy_rows:
        loc_row = conn.execute(
            "SELECT enemy_keys FROM game_locations WHERE key = ?", (location_key,)
        ).fetchone()
        if loc_row and loc_row[0]:
            try:
                keys = json.loads(loc_row[0])
                if keys:
                    enemy_rows = conn.execute(
                        f"SELECT key, label, tier FROM game_config_enemies WHERE key IN ({','.join('?'*len(keys))}) AND is_active=1",
                        keys
                    ).fetchall()
            except Exception:
                pass

    if enemy_rows:
        lines.append("\nPossible threats:")
        for r in enemy_rows:
            lines.append(f"  - {r['key']}: {r['label']} (tier: {r['tier']})")

    if len(lines) <= 2:
        return ""  # Nothing useful to inject

    return "\n".join(lines)


# ── V2 NPC context block ───────────────────────────────────────────────────

def build_v2_npc_context_block(
    conn: sqlite3.Connection,
    location_key: str | None,
    player_text: str = "",
    topic: str = "",
) -> str | None:
    """
    Build the V2 [NPC CONTEXT] block using personality_prompt + keyword_triggers.
    Also injects must_reveal_info constraints when keywords match.
    """
    if not location_key:
        return None

    # Get NPCs in this location
    npc_rows = conn.execute(
        """SELECT n.key, n.label, n.npc_type, n.personality_prompt, n.keyword_triggers
           FROM location_npc_assignments lna
           JOIN npcs n ON n.key = lna.npc_key
           WHERE lna.location_key = ? AND lna.is_active = 1 AND n.is_active = 1""",
        (location_key,)
    ).fetchall()

    if not npc_rows:
        # Fallback to npc_keys JSON
        loc_row = conn.execute(
            "SELECT npc_keys FROM game_locations WHERE key = ?", (location_key,)
        ).fetchone()
        if loc_row and loc_row[0]:
            try:
                keys = json.loads(loc_row[0])
                if keys:
                    npc_rows = conn.execute(
                        f"""SELECT key, label, npc_type, personality_prompt, keyword_triggers
                            FROM npcs WHERE key IN ({','.join('?'*len(keys))}) AND is_active=1""",
                        keys
                    ).fetchall()
            except Exception:
                pass

    if not npc_rows:
        return None

    combined_text = f"{player_text} {topic}".lower()
    lines = ["[NPC CONTEXT]", f"location: {location_key}"]

    for row in npc_rows:
        npc_key = row["key"]
        name = row["label"]
        npc_type = row["npc_type"] or "neutral"
        personality = (row["personality_prompt"] or "")[:300].strip()

        lines.append(f"\n[NPC: {name}]")
        lines.append(f"type: {npc_type}")
        if personality:
            lines.append(f"personality: {personality}")

        # Check keyword triggers
        try:
            triggers = json.loads(row["keyword_triggers"] or "[]")
        except (json.JSONDecodeError, TypeError):
            triggers = []

        for trigger in triggers:
            keyword = str(trigger.get("keyword", "")).lower().strip()
            if not keyword:
                continue
            if keyword in combined_text:
                must_reveal = str(trigger.get("must_reveal_info", "")).strip()
                is_secret = bool(trigger.get("is_secret", False))
                if must_reveal:
                    if is_secret:
                        lines.append(
                            f"[MUST INCLUDE — {name} reveals reluctantly, hints then confirms if pressed]: {must_reveal}"
                        )
                    else:
                        lines.append(f"[MUST INCLUDE — {name} reveals]: {must_reveal}")

    return "\n".join(lines)


# ── Current location lookup ────────────────────────────────────────────────

def get_current_location_info(
    conn: sqlite3.Connection, campaign_id: int
) -> dict | None:
    """
    Returns {key, label, safe_for_rest} for the current location of a campaign session.
    Returns None if no location set.
    """
    row = conn.execute(
        """SELECT gl.key, gl.label, COALESCE(gl.safe_for_rest, 0) as safe_for_rest
           FROM game_sessions gs
           JOIN game_locations gl ON gl.id = gs.current_location_id
           WHERE gs.campaign_id = ?
           LIMIT 1""",
        (campaign_id,)
    ).fetchone()
    if row and row["key"]:
        return {
            "key": row["key"],
            "label": row["label"],
            "safe_for_rest": int(row["safe_for_rest"] or 0),
        }
    return None


# ── Review queue helpers ───────────────────────────────────────────────────

def get_pending_review_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Return count of pending_review records per entity type."""
    counts = {}
    for table, label in [
        ("game_locations", "locations"),
        ("npcs", "npcs"),
        ("game_config_enemies", "enemies"),
    ]:
        try:
            row = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE review_status = 'pending_review'"
            ).fetchone()
            counts[label] = int(row[0]) if row else 0
        except Exception:
            counts[label] = 0
    return counts


def get_pending_locations(conn: sqlite3.Connection) -> list[dict]:
    try:
        rows = conn.execute(
            """SELECT key, label, location_type, description, review_status
               FROM game_locations WHERE review_status = 'pending_review'
               ORDER BY rowid DESC LIMIT 100"""
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_pending_npcs(conn: sqlite3.Connection) -> list[dict]:
    try:
        rows = conn.execute(
            """SELECT key, label, npc_type, personality_prompt, review_status
               FROM npcs WHERE review_status = 'pending_review'
               ORDER BY rowid DESC LIMIT 100"""
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_pending_enemies(conn: sqlite3.Connection) -> list[dict]:
    try:
        rows = conn.execute(
            """SELECT key, label, tier, hp_base, review_status
               FROM game_config_enemies WHERE review_status = 'pending_review'
               ORDER BY rowid DESC LIMIT 100"""
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def approve_entity(conn: sqlite3.Connection, entity_type: str, key: str) -> bool:
    table = {"location": "game_locations", "npc": "npcs", "enemy": "game_config_enemies"}.get(entity_type)
    if not table:
        return False
    try:
        conn.execute(f"UPDATE {table} SET review_status = 'permanent' WHERE key = ?", (key,))
        conn.commit()
        return True
    except Exception:
        return False


def discard_entity(conn: sqlite3.Connection, entity_type: str, key: str) -> bool:
    table = {"location": "game_locations", "npc": "npcs", "enemy": "game_config_enemies"}.get(entity_type)
    if not table:
        return False
    try:
        conn.execute(f"UPDATE {table} SET review_status = 'discarded' WHERE key = ?", (key,))
        conn.commit()
        return True
    except Exception:
        return False
