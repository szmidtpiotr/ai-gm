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


def _has_active_combat(campaign_id: int, conn: sqlite3.Connection) -> bool:
    """#860: True if combat is in progress for the campaign (status='active').

    Rest must be blocked mid-fight regardless of how 'safe' the location is —
    otherwise a fight in a `safe_for_rest=true` location is healable mid-combat.
    """
    row = conn.execute(
        "SELECT 1 FROM active_combat WHERE campaign_id = ? AND status = 'active' LIMIT 1",
        (campaign_id,),
    ).fetchone()
    return row is not None


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
            "SELECT key, safe_for_rest FROM game_locations WHERE id = ? AND is_active = 1",
            (loc_id,),
        ).fetchone()
        if loc:
            if bool(loc["safe_for_rest"]):
                return True
            # #1063 Opcja B: osada bez własnej flagi, ale z sub-lokacją inn/tavern.
            from app.services.world_service import settlement_lodging
            return settlement_lodging(conn, loc["key"]) is not None

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
    - Level-up if XP threshold crossed (#1024)
    - Reset short_rests_used = 0, death_saves_failed = 0
    """
    from app.services.clock_service import advance_clock
    from app.services.dice import parse_character_sheet

    if _has_active_combat(campaign_id, conn):
        return {"ok": False, "error": "in_combat"}

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

    # #1024: level-up check. grant_pending_xp already updated xp_lifetime_earned
    # to include pending XP — compute the correct level from it now.
    new_max_hp = max_hp
    new_max_mana = max_mana
    leveled_up = False
    new_level = int(sheet.get("level") or 1)

    if pending_xp > 0:
        from app.services.xp_service import level_from_xp, get_xp_level_thresholds
        from app.services.vitality_service import apply_level_up
        old_level = new_level
        thresholds = get_xp_level_thresholds(conn)
        new_level = level_from_xp(xp_lifetime, thresholds)
        level_ups = max(0, new_level - old_level)
        if level_ups > 0:
            archetype = str(sheet.get("archetype") or "warrior").lower()
            stats = sheet.get("stats") or {}
            con = int(stats.get("CON", 10) or 10)
            int_stat = int(stats.get("INT", 10) or 10)
            for _ in range(level_ups):
                new_max_hp, new_max_mana = apply_level_up(
                    archetype, new_max_hp, new_max_mana, con, int_stat
                )
            sheet["level"] = new_level
            sheet["max_hp"] = new_max_hp
            sheet["max_mana"] = new_max_mana
            leveled_up = True

    # PT-D1 (#1124): przy 3 stackach zmęczenia odpoczynek regeneruje o połowę mniej HP/many.
    # Mnożnik liczony PRZED wyczyszczeniem zmęczenia (odpoczynek najpierw leczy, potem budzi wypoczętego).
    from app.services.fatigue_service import compute_regen_multiplier, clear_all_fatigue
    regen_mult = compute_regen_multiplier(sheet.get("conditions") or [], race=sheet.get("race"))
    hp_healed = int(round((new_max_hp - hp_before) * regen_mult))
    mana_healed = int(round((new_max_mana - mana_before) * regen_mult))
    sheet["current_hp"] = min(new_max_hp, hp_before + max(0, hp_healed))
    sheet["current_mana"] = min(new_max_mana, mana_before + max(0, mana_healed))
    sheet["pending_xp"] = 0
    sheet["xp_available"] = xp_available + pending_xp
    if pending_xp:
        sheet["xp_lifetime_earned"] = xp_lifetime + pending_xp
    sheet["short_rests_used"] = 0
    sheet["death_saves_failed"] = 0

    # PT-D1 (#1124): pełny nocleg czyści WSZYSTKIE stacki zmęczenia (exhausted).
    sheet["conditions"] = clear_all_fatigue(sheet.get("conditions") or [])

    conn.execute(
        "UPDATE characters SET sheet_json = ? WHERE id = ?",
        (json.dumps(sheet, ensure_ascii=False), character_id),
    )

    advance_clock(campaign_id, 8, "long_rest", conn=conn)

    # PT7 #1117: Reset daily march budget after long rest
    # PT9 #1119: Roll camp encounter before clearing flags, then clear boost
    camp_encounter: dict[str, Any] = {}
    try:
        _gs_rest = conn.execute(
            "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if _gs_rest:
            _sf_rest = json.loads(_gs_rest["session_flags"] or "{}")
            _boost = float(_sf_rest.get("camp_encounter_boost") or 0.0)
            _night_march = bool(_sf_rest.get("night_march", False))
            if _boost > 0:
                _night_bonus = 0.10 if _night_march else 0.0
                _effective = min(1.0, _boost + _night_bonus)
                _roll = random.random()
                _triggered = _roll < _effective
                _enemy_key = None
                if _triggered:
                    _hex = _sf_rest.get("current_hex") or {}
                    _q, _r = _hex.get("q"), _hex.get("r")
                    if _q is not None and _r is not None:
                        _hex_row = conn.execute(
                            "SELECT encounter_pool FROM world_hexes WHERE q = ? AND r = ? AND is_active = 1 LIMIT 1",
                            (_q, _r),
                        ).fetchone()
                        if _hex_row:
                            _pool = json.loads(_hex_row["encounter_pool"] or "[]")
                            _enemy_key = random.choice(_pool) if _pool else None
                camp_encounter = {
                    "triggered": _triggered,
                    "roll": round(_roll, 3),
                    "effective_boost": round(_effective, 3),
                    "night_march_bonus": _night_march,
                    "enemy_key": _enemy_key,
                }
                logger.info(
                    "camp_encounter_rolled",
                    campaign_id=campaign_id,
                    triggered=_triggered,
                    boost=_boost,
                    night_march=_night_march,
                    enemy_key=_enemy_key,
                )
            _sf_rest["hours_marched_today"] = 0.0
            _sf_rest["night_march"] = False
            _sf_rest.pop("camp_encounter_boost", None)
            # PT-D1 (#1124): pełny nocleg = reset dziennych liczników zmęczenia.
            _sf_rest["fatigue_march_charged"] = False
            try:
                from app.services.clock_service import get_clock_state
                _sf_rest["fatigue_last_rest_day"] = int(get_clock_state(campaign_id, conn=conn).get("day_number", 1))
            except Exception:
                pass
            conn.execute(
                "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
                (json.dumps(_sf_rest, ensure_ascii=False), _gs_rest["id"]),
            )
    except Exception as _re:
        logger.warning("march_budget_reset_failed", error=str(_re))

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
        hp_restored=sheet["current_hp"] - hp_before,
        mana_restored=sheet["current_mana"] - mana_before,
        regen_mult=regen_mult,
        xp_unlocked=pending_xp,
        leveled_up=leveled_up,
        new_level=new_level if leveled_up else None,
    )

    result: dict[str, Any] = {
        "ok": True,
        "type": "long",
        "hp_before": hp_before,
        "hp_after": sheet["current_hp"],
        "mana_before": mana_before,
        "mana_after": sheet["current_mana"],
        "regen_mult": regen_mult,
        "xp_unlocked": pending_xp,
        "xp_available": sheet["xp_available"],
        "hours_advanced": 8,
    }
    if leveled_up:
        result["leveled_up"] = True
        result["new_level"] = new_level
    if camp_encounter:
        result["camp_encounter"] = camp_encounter
    return result


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

    if _has_active_combat(campaign_id, conn):
        return {"ok": False, "error": "in_combat"}

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
    # PT-D1 (#1124): przy 3 stackach zmęczenia regeneracja o połowę mniejsza.
    from app.services.fatigue_service import compute_regen_multiplier
    regen_mult = compute_regen_multiplier(sheet.get("conditions") or [], race=sheet.get("race"))
    healed = max(0, int(round((roll + con_mod) * regen_mult)))
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

    # PT-D1 (#1124): krótki odpoczynek NIE czyści zmęczenia (tylko pełny nocleg).
    # (Zmiana wobec S9 — zmęczenie podróżne wymaga pełnego snu, patrz issue #1124.)

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
