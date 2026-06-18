"""
Rest Service — Stage 2B / 2C

- hex_is_safe_for_rest: resolves safe status for a hex (admin diagnostic).
- perform_long_rest / perform_short_rest: Stage 2C X3/X4 endpoints.
"""

from __future__ import annotations

import json
import random
import sqlite3
from typing import Any

import structlog

logger = structlog.get_logger()

DB_PATH = "/data/ai_gm.db"


def _open_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hex_is_safe_for_rest(
    q: int,
    r: int,
    *,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Resolve safe-for-rest for a hex.

    Returns a dict shaped:
        {
            "safe": bool,
            "reason": str,            # one of: safe_via_location |
                                      #   unsafe_location_flag_off |
                                      #   wilderness_no_location |
                                      #   unknown_location_key |
                                      #   no_hex_record
            "location_key": str|None,
            "location_label": str|None,
            "hex_type": str|None,
            "q": int,
            "r": int,
        }
    """
    own_conn = False
    if conn is None:
        conn = _open_conn()
        own_conn = True

    try:
        hex_row = conn.execute(
            """SELECT q, r, hex_type, label, location_key
               FROM world_hexes
               WHERE q = ? AND r = ? AND is_active = 1
               LIMIT 1""",
            (q, r),
        ).fetchone()

        result: dict[str, Any] = {
            "safe": False,
            "reason": "no_hex_record",
            "location_key": None,
            "location_label": None,
            "hex_type": None,
            "q": q,
            "r": r,
        }

        if not hex_row:
            return result

        result["hex_type"] = hex_row["hex_type"]
        location_key = hex_row["location_key"]
        result["location_key"] = location_key

        if not location_key:
            result["reason"] = "wilderness_no_location"
            return result

        loc_row = conn.execute(
            """SELECT key, label, safe_for_rest
               FROM game_locations
               WHERE key = ? AND is_active = 1
               LIMIT 1""",
            (location_key,),
        ).fetchone()

        if not loc_row:
            result["reason"] = "unknown_location_key"
            return result

        result["location_label"] = loc_row["label"]
        is_safe = bool(loc_row["safe_for_rest"])
        result["safe"] = is_safe
        result["reason"] = "safe_via_location" if is_safe else "unsafe_location_flag_off"
        return result
    finally:
        if own_conn:
            conn.close()


# ── Stage 2C: X3 / X4 rest logic ─────────────────────────────────────────────

MAX_SHORT_RESTS = 2  # T23 spec: max 2 short rests between long rests


def _is_safe_for_character(character_id: int, campaign_id: int, conn: sqlite3.Connection) -> bool:
    """Check safe_for_rest via current_location_id, then hex fallback."""
    sess = conn.execute(
        "SELECT current_location_id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    if not sess:
        return False

    # Primary: current_location_id → game_locations.safe_for_rest
    loc_id = sess["current_location_id"]
    if loc_id:
        loc = conn.execute(
            "SELECT safe_for_rest FROM game_locations WHERE id = ? AND is_active = 1",
            (loc_id,),
        ).fetchone()
        if loc:
            return bool(loc["safe_for_rest"])

    # Fallback: current hex from session_flags
    try:
        flags = json.loads(sess["session_flags"] or "{}")
        hex_pos = flags.get("current_hex") or {}
        q, r = int(hex_pos.get("q", 0)), int(hex_pos.get("r", 0))
    except (TypeError, ValueError, KeyError):
        return False
    return hex_is_safe_for_rest(q, r, conn=conn)["safe"]


def perform_long_rest(
    conn: sqlite3.Connection,
    character_id: int,
    campaign_id: int,
) -> dict[str, Any]:
    """Stage 2C X3 — long rest.

    - Validates safe_for_rest
    - +8 ingame hours
    - Full HP + mana restore
    - Flush pending_xp → xp_available
    - Reset short_rests_used = 0, death_saves_failed = 0
    """
    from app.services.clock_service import advance_clock
    from app.services.dice import parse_character_sheet

    if not _is_safe_for_character(character_id, campaign_id, conn):
        return {"ok": False, "error": "not_safe_for_rest"}

    row = conn.execute(
        "SELECT sheet_json FROM characters WHERE id = ?", (character_id,)
    ).fetchone()
    if not row:
        return {"ok": False, "error": "character_not_found"}

    sheet = parse_character_sheet(row["sheet_json"])

    hp_before = int(sheet.get("current_hp") or 0)
    max_hp = int(sheet.get("max_hp") or 0)
    mana_before = int(sheet.get("current_mana") or 0)
    max_mana = int(sheet.get("max_mana") or 0)
    pending_xp = int(sheet.get("pending_xp") or 0)
    xp_available = int(sheet.get("xp_available") or 0)
    xp_lifetime = int(sheet.get("xp_lifetime_earned") or 0)

    sheet["current_hp"] = max_hp
    sheet["current_mana"] = max_mana
    sheet["pending_xp"] = 0
    sheet["xp_available"] = xp_available + pending_xp
    if pending_xp:
        sheet["xp_lifetime_earned"] = xp_lifetime + pending_xp
    sheet["short_rests_used"] = 0
    sheet["death_saves_failed"] = 0

    # S9 (#604): pełny sen zdejmuje WSZYSTKIE poziomy kondycji stackowalnych (exhausted).
    conds = sheet.get("conditions")
    if isinstance(conds, list) and conds:
        from app.services.combat_service import reduce_stacking_conditions
        new_conds, _ = reduce_stacking_conditions(conds, remove_all=True)
        sheet["conditions"] = new_conds

    conn.execute(
        "UPDATE characters SET sheet_json = ? WHERE id = ?",
        (json.dumps(sheet, ensure_ascii=False), character_id),
    )

    advance_clock(campaign_id, 8, "long_rest", conn=conn)

    if pending_xp:
        conn.execute(
            """INSERT INTO character_xp_grants
               (character_id, campaign_id, amount, reason, source, granted_by_user_id)
               VALUES (?, ?, ?, 'Długi odpoczynek — odblokowanie PD', 'long_rest', 0)""",
            (character_id, campaign_id, pending_xp),
        )

    conn.commit()

    logger.info(
        "long_rest_performed",
        character_id=character_id,
        campaign_id=campaign_id,
        hp_restored=max_hp - hp_before,
        mana_restored=max_mana - mana_before,
        xp_unlocked=pending_xp,
    )

    return {
        "ok": True,
        "type": "long",
        "hp_before": hp_before,
        "hp_after": max_hp,
        "mana_before": mana_before,
        "mana_after": max_mana,
        "xp_unlocked": pending_xp,
        "xp_available": sheet["xp_available"],
        "hours_advanced": 8,
    }


def perform_short_rest(
    conn: sqlite3.Connection,
    character_id: int,
    campaign_id: int,
) -> dict[str, Any]:
    """Stage 2C X4 — short rest.

    - Validates safe_for_rest
    - Max 2 short rests between long rests (T23)
    - +1 ingame hour
    - Regen 1d6 + CON_mod HP (capped at max_hp)
    """
    from app.services.clock_service import advance_clock
    from app.services.dice import parse_character_sheet

    if not _is_safe_for_character(character_id, campaign_id, conn):
        return {"ok": False, "error": "not_safe_for_rest"}

    row = conn.execute(
        "SELECT sheet_json FROM characters WHERE id = ?", (character_id,)
    ).fetchone()
    if not row:
        return {"ok": False, "error": "character_not_found"}

    sheet = parse_character_sheet(row["sheet_json"])
    used = int(sheet.get("short_rests_used") or 0)
    if used >= MAX_SHORT_RESTS:
        return {"ok": False, "error": "short_rest_exhausted"}

    hp = int(sheet.get("current_hp") or 0)
    max_hp = int(sheet.get("max_hp") or 0)
    con_mod = int((sheet.get("stat_modifiers") or {}).get("CON", 0) or 0)
    roll = random.randint(1, 6)
    healed = max(0, roll + con_mod)
    new_hp = min(max_hp, hp + healed)

    sheet["current_hp"] = new_hp
    sheet["short_rests_used"] = used + 1
    # #761: rejestr leczenia z krótkiego odpoczynku
    if new_hp != hp:
        try:
            from app.services.state_log_service import record_state_change
            record_state_change(
                campaign_id=campaign_id, resource="hp", character_id=character_id,
                before_val=hp, after_val=new_hp, cause="rest",
                meta={"rest_type": "short", "roll": roll, "con_mod": con_mod},
            )
        except Exception:
            pass

    # S9 (#604): krótki odpoczynek (1h) zdejmuje 1 poziom kondycji stackowalnych (exhausted).
    conds = sheet.get("conditions")
    if isinstance(conds, list) and conds:
        from app.services.combat_service import reduce_stacking_conditions
        new_conds, _ = reduce_stacking_conditions(conds, remove_all=False)
        sheet["conditions"] = new_conds

    conn.execute(
        "UPDATE characters SET sheet_json = ? WHERE id = ?",
        (json.dumps(sheet, ensure_ascii=False), character_id),
    )
    advance_clock(campaign_id, 1, "short_rest", conn=conn)
    conn.commit()

    logger.info(
        "short_rest_performed",
        character_id=character_id,
        campaign_id=campaign_id,
        roll=roll,
        con_mod=con_mod,
        hp_before=hp,
        hp_after=new_hp,
        short_rests_used=used + 1,
    )

    return {
        "ok": True,
        "type": "short",
        "roll": roll,
        "con_mod": con_mod,
        "hp_before": hp,
        "hp_after": new_hp,
        "hours_advanced": 1,
        "short_rests_used": used + 1,
        "short_rests_remaining": MAX_SHORT_RESTS - (used + 1),
    }
