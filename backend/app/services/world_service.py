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
_SET_SAFE_FOR_REST_RE = re.compile(
    r"\[SET_SAFE_FOR_REST:\s*([^\]\s:,]+)\s*:\s*(on|off|true|false|1|0)\s*\]",
    re.IGNORECASE,
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

    # [SET_SAFE_FOR_REST:location_key:on|off]
    for m in _SET_SAFE_FOR_REST_RE.finditer(narrative):
        location_key = m.group(1).strip()
        raw_val = m.group(2).strip().lower()
        new_value = 1 if raw_val in ("on", "true", "1") else 0
        change = set_location_safe_for_rest(conn, location_key, new_value, source="llm_tag")
        if change:
            created.append({"type": "safe_for_rest_change", **change})
        cleaned = cleaned.replace(m.group(0), "")

    return cleaned.strip(), created


def set_location_safe_for_rest(
    conn: sqlite3.Connection,
    location_key: str,
    value: int,
    source: str = "admin",
) -> dict | None:
    """Toggle safe_for_rest on an existing location. Returns change dict or None
    if the location was not found. No-op (still returns dict) if value already matches."""
    row = conn.execute(
        "SELECT id, key, label, safe_for_rest FROM game_locations WHERE key = ? AND is_active = 1",
        (location_key,),
    ).fetchone()
    if not row:
        logger.warning("set_safe_for_rest_unknown_location", key=location_key, source=source)
        return None
    prev = int(row["safe_for_rest"] or 0)
    new_value = 1 if value else 0
    if prev != new_value:
        conn.execute(
            "UPDATE game_locations SET safe_for_rest = ?, updated_at = datetime('now') WHERE id = ?",
            (new_value, row["id"]),
        )
        conn.commit()
    logger.info(
        "safe_for_rest_set",
        key=location_key,
        previous=prev,
        new=new_value,
        source=source,
    )
    return {
        "location_key": location_key,
        "label": row["label"],
        "previous": prev,
        "new": new_value,
        "source": source,
    }


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
                rules, review_status, ai_generated, is_active,
                created_by, canonical, source_campaign_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending_review', 1, 1,
                       'gm_runtime', 0, ?)""",
            (key, label, loc_type, description, parent_id, parent_key or None, rules_json, campaign_id)
        )
        conn.commit()
        logger.info("create_location_tag_processed", key=key, campaign_id=campaign_id, created_by="gm_runtime")
        return {"key": key, "label": label, "review_status": "pending_review", "created_by": "gm_runtime"}
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
    conn: sqlite3.Connection,
    location_key: str | None,
    character_id: int | None = None,
) -> str:
    """
    Build the [AVAILABLE CONTENT] block injected into LLM context.
    Lists NPCs and enemies for the current location, plus
    (Stage 2B-Schema S14) nearby known places of the same biome/subtype
    that the GM should reuse before inventing new ones.
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

    # Stage 2B-Schema S14: nearby known places of the same biome/subtype the GM
    # should reuse before inventing new ones. Tier-capped by hero level so we
    # don't dangle T5 dungeons in front of a freshly-rolled hero.
    nearby = _nearby_known_places(conn, location_key, character_id)
    if nearby:
        lines.append("\nNearby known places of this type (prefer these over [CREATE_LOCATION]):")
        for r in nearby:
            tags = []
            if r["canonical"]:
                tags.append("canonical")
            if r["usage_count"]:
                tags.append(f"visits={r['usage_count']}")
            tag_str = f" [{', '.join(tags)}]" if tags else ""
            tier_str = f"T{r['tier']}" if r["tier"] is not None else "T?"
            lines.append(f"  - {r['key']}: {r['label']} ({tier_str}){tag_str}")

    if len(lines) <= 2:
        return ""  # Nothing useful to inject

    return "\n".join(lines)


def _nearby_known_places(
    conn: sqlite3.Connection,
    current_key: str,
    character_id: int | None,
    limit: int = 5,
) -> list:
    """
    Return up to `limit` locations matching the current biome and subtype.
    Ordered canonical → popular. Excludes the current location itself.

    Note: no tier cap. The list is only a hint to the narrator (for reuse
    during action: create), not a movement target. Tier is rendered next
    to each entry so the GM can self-select. Hero level is not yet
    reliably tracked in sheet_json across all characters.
    """
    try:
        cur_row = conn.execute(
            "SELECT biome, location_subtype FROM game_locations WHERE key = ? AND is_active=1 LIMIT 1",
            (current_key,),
        ).fetchone()
        if not cur_row:
            return []
        biome = cur_row["biome"] if "biome" in cur_row.keys() else None
        subtype = cur_row["location_subtype"] if "location_subtype" in cur_row.keys() else None
        if not biome and not subtype:
            return []

        def _query(use_subtype: bool):
            clauses = ["is_active=1", "key != ?"]
            p: list = [current_key]
            if biome:
                clauses.append("biome = ?")
                p.append(biome)
            if subtype and use_subtype:
                clauses.append("location_subtype = ?")
                p.append(subtype)
            sql = (
                "SELECT key, label, tier, canonical, COALESCE(usage_count, 0) AS usage_count "
                f"FROM game_locations WHERE {' AND '.join(clauses)} "
                "ORDER BY canonical DESC, usage_count DESC, label ASC LIMIT ?"
            )
            p.append(limit)
            return conn.execute(sql, p).fetchall()

        # Try strict biome+subtype first; fall back to biome-only if empty so
        # unique subtypes (e.g. the only city in the world) still surface
        # sibling places worth reusing (taverns, temples, shops in the same biome).
        rows = _query(use_subtype=True)
        if not rows and subtype:
            rows = _query(use_subtype=False)
        return rows
    except Exception as exc:
        logger.warning("nearby_known_places_error", error=str(exc), current_key=current_key)
        return []


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

def build_camp(
    conn: sqlite3.Connection,
    campaign_id: int,
    q: int,
    r: int,
) -> dict:
    """Stage 2B R4 — create a temporary `temp_camp_*` sub-location on hex (q, r).

    - Refuses if the hex already has an `is_active=1` location with `safe_for_rest=1`.
    - Resolves parent macro via the existing hex.location_key (if any) — falls back to NULL.
    - Inserts location with `safe_for_rest=1`, `temporary=1`, `created_by='gm_runtime'`,
      `canonical=0`, `source_campaign_id=campaign_id`, `location_subtype='camp'`,
      `biome` copied from world_hexes.hex_type.
    - Points `world_hexes.location_key` at the new key.

    Returns the new location dict. Raises ValueError on gate violations so the
    router can translate into the right HTTP status.
    """
    import time
    hex_row = conn.execute(
        "SELECT hex_type, label, location_key FROM world_hexes WHERE q = ? AND r = ? AND is_active = 1",
        (q, r),
    ).fetchone()
    if not hex_row:
        raise ValueError("no_hex_record")

    hex_type = hex_row["hex_type"]
    existing_location_key = hex_row["location_key"]

    if existing_location_key:
        existing = conn.execute(
            "SELECT id, key, label, safe_for_rest, location_type, parent_key FROM game_locations WHERE key = ? AND is_active = 1",
            (existing_location_key,),
        ).fetchone()
        if existing and int(existing["safe_for_rest"] or 0) == 1:
            raise ValueError("hex_already_safe")

        # Check entire settlement tree for safe_for_rest=1 (#994):
        # If the current location is a sub, its siblings or parent may have a rest spot.
        if existing:
            root_key = None
            if existing["location_type"] == "macro":
                root_key = existing["key"]
            elif existing["parent_key"]:
                root_key = existing["parent_key"]

            if root_key:
                # Check root macro itself
                root = conn.execute(
                    "SELECT key, label, safe_for_rest FROM game_locations WHERE key = ? AND is_active = 1",
                    (root_key,),
                ).fetchone()
                if root and int(root["safe_for_rest"] or 0) == 1:
                    raise ValueError(f"settlement_has_rest|{root['key']}|{root['label']}")
                # Check sibling sub-locations
                safe_sub = conn.execute(
                    "SELECT key, label FROM game_locations WHERE parent_key = ? AND is_active = 1 AND safe_for_rest = 1 LIMIT 1",
                    (root_key,),
                ).fetchone()
                if safe_sub:
                    raise ValueError(f"settlement_has_rest|{safe_sub['key']}|{safe_sub['label']}")

    # Resolve parent macro: prefer the macro hosting the current hex's location,
    # else nearest macro by parent_id chain — but for simplicity, just inherit
    # whatever sits on the hex right now (likely a wilderness sub or NULL).
    parent_id = None
    parent_key = None
    if existing_location_key:
        parent_row = conn.execute(
            "SELECT id, key, location_type, parent_id, parent_key FROM game_locations WHERE key = ? AND is_active = 1",
            (existing_location_key,),
        ).fetchone()
        if parent_row:
            if parent_row["location_type"] == "macro":
                parent_id = parent_row["id"]
                parent_key = parent_row["key"]
            else:
                parent_id = parent_row["parent_id"]
                parent_key = parent_row["parent_key"]

    # Map hex_type → biome (camp inherits surroundings)
    BIOME_FROM_HEX = {
        "forest": "forest", "mountain": "mountain", "swamp": "swamp",
        "plains": "plains", "coast": "coast", "desert": "desert",
        "tundra": "tundra", "underground": "underground", "city": "urban",
        "road": "plains",
    }
    biome = BIOME_FROM_HEX.get((hex_type or "").lower(), None)

    key = f"temp_camp_{campaign_id}_{int(time.time())}"
    label = "Obozowisko"
    description = "Twój obóz polowy. Niewielkie ognisko, koce i broń pod ręką. Nasłuchujesz odgłosów w ciemności."

    conn.execute(
        """INSERT INTO game_locations
           (key, label, location_type, description, parent_id, parent_key,
            is_active, safe_for_rest, temporary, review_status,
            created_by, canonical, source_campaign_id,
            location_subtype, biome, tier)
           VALUES (?, ?, 'sub', ?, ?, ?,
                   1, 1, 1, 'permanent',
                   'gm_runtime', 0, ?,
                   'camp', ?, 1)""",
        (key, label, description, parent_id, parent_key, campaign_id, biome),
    )
    conn.execute(
        "UPDATE world_hexes SET location_key = ? WHERE q = ? AND r = ? AND is_active = 1",
        (key, q, r),
    )
    conn.commit()

    logger.info(
        "build_camp",
        campaign_id=campaign_id,
        q=q, r=r, key=key,
        parent_key=parent_key, biome=biome,
    )
    return {
        "key": key,
        "label": label,
        "location_type": "sub",
        "safe_for_rest": 1,
        "temporary": 1,
        "parent_key": parent_key,
        "biome": biome,
        "q": q,
        "r": r,
    }


def deactivate_temporary_location_on_hex(
    conn: sqlite3.Connection, q: int, r: int
) -> dict | None:
    """Soft-delete any `temporary=1` location attached to a hex.

    Called when MOVEMENT validates a move away from this hex. Restores
    world_hexes.location_key to the canonical parent location (fixes #992 anchor
    desync — previously set to NULL, orphaning sessions that were still anchored
    to the temp location).
    Returns the deactivated row info, or None if no temp was present.
    """
    hex_row = conn.execute(
        "SELECT location_key FROM world_hexes WHERE q = ? AND r = ? AND is_active = 1",
        (q, r),
    ).fetchone()
    if not hex_row or not hex_row["location_key"]:
        return None
    loc_key = hex_row["location_key"]
    loc_row = conn.execute(
        "SELECT id, key, label, temporary, parent_key FROM game_locations WHERE key = ? AND is_active = 1",
        (loc_key,),
    ).fetchone()
    if not loc_row or int(loc_row["temporary"] or 0) != 1:
        return None
    conn.execute(
        "UPDATE game_locations SET is_active = 0, safe_for_rest = 0, updated_at = datetime('now') WHERE id = ?",
        (loc_row["id"],),
    )
    # #992: restore canonical location_key instead of setting NULL
    parent_key = loc_row["parent_key"] or None
    if parent_key:
        canonical_exists = conn.execute(
            "SELECT 1 FROM game_locations WHERE key = ? AND is_active = 1 LIMIT 1",
            (parent_key,),
        ).fetchone()
        restore_key = parent_key if canonical_exists else None
    else:
        restore_key = None
    conn.execute(
        "UPDATE world_hexes SET location_key = ? WHERE q = ? AND r = ? AND is_active = 1",
        (restore_key, q, r),
    )
    # #992: fix stale anchor in sessions still pointing at the deactivated temp_camp
    if parent_key:
        conn.execute(
            """UPDATE game_sessions
               SET session_flags = json_set(session_flags, '$.current_location_key', ?)
               WHERE json_extract(session_flags, '$.current_location_key') = ?""",
            (parent_key, loc_key),
        )
    conn.commit()
    logger.info("temp_location_deactivated", key=loc_key, q=q, r=r,
                restored_key=restore_key)
    return {"key": loc_key, "label": loc_row["label"]}


def sync_location_hex_coordinates(conn: sqlite3.Connection) -> int:
    """#992: Stamp game_locations.world_hex_q/r for canonical locations that
    have a world_hexes entry (via world_hexes.location_key) but lack coordinates.

    This is idempotent — only rows with world_hex_q IS NULL are updated.
    Returns the count of updated rows.
    """
    rows = conn.execute(
        """SELECT wh.q, wh.r, wh.location_key
           FROM world_hexes wh
           JOIN game_locations gl ON gl.key = wh.location_key
           WHERE wh.is_active = 1
             AND wh.map_level = 0
             AND gl.is_active = 1
             AND gl.world_hex_q IS NULL"""
    ).fetchall()
    count = 0
    for row in rows:
        conn.execute(
            "UPDATE game_locations SET world_hex_q = ?, world_hex_r = ? WHERE key = ? AND world_hex_q IS NULL",
            (int(row["q"]), int(row["r"]), row["location_key"]),
        )
        count += 1
    if count:
        conn.commit()
        logger.info("sync_location_hex_coordinates", updated=count)
    return count


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
        ("game_config_weapons", "weapons"),
        ("game_config_items", "items"),
    ]:
        try:
            row = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE review_status = 'pending_review'"
            ).fetchone()
            counts[label] = int(row[0]) if row else 0
        except Exception:
            counts[label] = 0
    return counts


def get_pending_items(conn: sqlite3.Connection) -> list[dict]:
    """D1 (#376) — Return narrative items awaiting admin review.

    Includes `note` and `weight_kg` so the admin "Edytuj i Zatwierdź" modal can
    pre-fill all editable fields before approval.
    """
    try:
        rows = conn.execute(
            """SELECT key, label, item_type, description, value_gp, weight_kg, note,
                      campaign_id, review_status, ai_generated, created_at,
                      pending_category
               FROM game_config_items
               WHERE review_status = 'pending_review'
               ORDER BY rowid DESC LIMIT 100"""
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        # pending_category column may not exist yet (pre-migration) — retry without it
        try:
            rows = conn.execute(
                """SELECT key, label, item_type, description, value_gp, weight_kg, note,
                          campaign_id, review_status, ai_generated, created_at
                   FROM game_config_items
                   WHERE review_status = 'pending_review'
                   ORDER BY rowid DESC LIMIT 100"""
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []


def get_pending_weapons(conn: sqlite3.Connection) -> list[dict]:
    """Return narrative weapons awaiting admin review."""
    try:
        rows = conn.execute(
            """SELECT key, label, weapon_type, damage_die, linked_stat, description,
                      campaign_id, review_status, ai_generated, created_at
               FROM game_config_weapons
               WHERE review_status = 'pending_review'
               ORDER BY rowid DESC LIMIT 100"""
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_pending_locations(conn: sqlite3.Connection) -> list[dict]:
    try:
        rows = conn.execute(
            """SELECT key, label, location_type, description, review_status,
                      created_by, location_subtype, biome, tier, canonical,
                      safe_for_rest, parent_key, source_campaign_id,
                      ai_generated, is_active, temporary
               FROM game_locations
               WHERE review_status = 'pending_review' AND is_active = 1
               ORDER BY rowid DESC LIMIT 100"""
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def update_location_fields(conn: sqlite3.Connection, key: str, fields: dict) -> bool:
    """#590: edit a location's descriptive fields before approving/placing.

    Only whitelisted columns are writable — `key`, `approved`, `review_status`,
    `placement` and any unknown keys are ignored (prevents accidental state changes
    and SQL injection via column names).
    """
    editable = {
        "label", "description", "location_type", "location_subtype",
        "biome", "tier", "parent_key", "terrain_tags", "safe_for_rest",
    }
    sets = {k: v for k, v in (fields or {}).items() if k in editable}
    if not sets:
        return False
    assigns = ", ".join(f"{col} = ?" for col in sets)
    params = list(sets.values()) + [key]
    conn.execute(f"UPDATE game_locations SET {assigns} WHERE key = ?", params)
    conn.commit()
    return True


def get_pending_npcs(conn: sqlite3.Connection) -> list[dict]:
    try:
        rows = conn.execute(
            """SELECT key, label, npc_type, personality_prompt, review_status, created_at
               FROM npcs WHERE review_status = 'pending_review'
               ORDER BY rowid DESC LIMIT 100"""
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_pending_enemies(conn: sqlite3.Connection) -> list[dict]:
    try:
        rows = conn.execute(
            """SELECT key, label, tier, hp_base, review_status, created_at
               FROM game_config_enemies WHERE review_status = 'pending_review'
               ORDER BY rowid DESC LIMIT 100"""
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def approve_entity(conn: sqlite3.Connection, entity_type: str, key: str) -> bool:
    table = {
        "location": "game_locations", "npc": "npcs",
        "enemy": "game_config_enemies", "weapon": "game_config_weapons",
        "item": "game_config_items",
    }.get(entity_type)
    if not table:
        return False
    try:
        conn.execute(f"UPDATE {table} SET review_status = 'permanent' WHERE key = ?", (key,))
        if entity_type == "enemy":
            _ensure_enemy_loot_table(conn, key)
        if entity_type == "weapon":
            # Approve globally: clear campaign_id so weapon is available everywhere
            conn.execute(
                "UPDATE game_config_weapons SET approved = 1, campaign_id = NULL WHERE key = ?", (key,)
            )
            # U11c dual-write: re-read legacy row → upsert game_items (creates row if AI-generated
            # weapon was never backfilled; carries approved=1 just set above).
            try:
                from app.services.game_items_service import sync_from_legacy
                sync_from_legacy(conn, "game_config_weapons", key)
            except Exception:
                pass
        if entity_type == "item":
            # D1 (#376) — approve globally: catalog filters by COALESCE(approved, 1) = 1
            conn.execute(
                "UPDATE game_config_items SET approved = 1, campaign_id = NULL WHERE key = ?", (key,)
            )
            # U11c dual-write: re-read legacy row → upsert game_items
            try:
                from app.services.game_items_service import sync_from_legacy
                sync_from_legacy(conn, "game_config_items", key)
            except Exception:
                pass
        if entity_type == "location":
            # Location validator + injectors filter by COALESCE(approved, 1) = 1, so flipping
            # review_status alone leaves the row invisible. Promote to globally visible.
            conn.execute(
                "UPDATE game_locations SET approved = 1 WHERE key = ?", (key,)
            )
        conn.commit()
        return True
    except Exception:
        return False


def _ensure_enemy_loot_table(conn: sqlite3.Connection, enemy_key: str) -> None:
    """Create and assign a loot table for an enemy if it doesn't already have one."""
    try:
        row = conn.execute(
            "SELECT label, loot_table_key FROM game_config_enemies WHERE key = ?", (enemy_key,)
        ).fetchone()
        if not row:
            return
        if row["loot_table_key"]:
            return
        lt_key = f"loot_{enemy_key}"
        label = row["label"] or enemy_key
        exists = conn.execute(
            "SELECT key FROM game_config_loot_tables WHERE key = ?", (lt_key,)
        ).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO game_config_loot_tables (key, label, description, is_active) VALUES (?, ?, '', 1)",
                (lt_key, f"Łupy: {label}"),
            )
        conn.execute(
            "UPDATE game_config_enemies SET loot_table_key = ? WHERE key = ?",
            (lt_key, enemy_key),
        )
    except Exception:
        pass


def discard_entity(conn: sqlite3.Connection, entity_type: str, key: str) -> bool:
    table = {
        "location": "game_locations", "npc": "npcs",
        "enemy": "game_config_enemies", "weapon": "game_config_weapons",
        "item": "game_config_items",
    }.get(entity_type)
    if not table:
        return False
    try:
        conn.execute(f"UPDATE {table} SET review_status = 'discarded' WHERE key = ?", (key,))
        conn.commit()
        return True
    except Exception:
        return False
