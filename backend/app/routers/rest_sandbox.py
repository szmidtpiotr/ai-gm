"""Rest Sandbox — Stage 2C+ admin harness for testing the full rest loop.

Mirrors Combat Sandbox (sandbox.py / issue #21). Lets an admin exercise the
complete rest cycle: build_camp → short rest → long rest → HP/mana regen →
encounter roll — on a disposable clone of any hero, without touching the
original character or playing through a campaign.

Clone tag: name prefix '[RSB] ', sheet.__rest_sandbox_clone__ = true.
"""
from __future__ import annotations

import json
import random
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from app.routers.admin import require_admin_token
from app.core.db_runtime import resolve_db_path

DB_PATH = Path(resolve_db_path())
RSB_TITLE_PREFIX = "[REST-SANDBOX]"
CLONE_PREFIX = "[RSB] "

router = APIRouter(prefix="/admin/rest-sandbox", tags=["rest-sandbox"])  # auth: warstwa /api/admin (#1187)


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


# ── Hero list ────────────────────────────────────────────────────────────────

@router.get("/heroes")
def list_heroes() -> dict[str, Any]:
    """All active heroes excluding rest-sandbox clones."""
    with _conn() as c:
        rows = c.execute(
            """
            SELECT id, name, user_id,
                   json_extract(sheet_json,'$.archetype') AS archetype,
                   json_extract(sheet_json,'$.current_hp') AS hp,
                   json_extract(sheet_json,'$.max_hp') AS max_hp,
                   json_extract(sheet_json,'$.current_mana') AS mana,
                   json_extract(sheet_json,'$.max_mana') AS max_mana
            FROM characters
            WHERE is_active = 1
              AND name NOT LIKE ?
              AND COALESCE(json_extract(sheet_json,'$.__rest_sandbox_clone__'), 0) = 0
              AND COALESCE(json_extract(sheet_json,'$.__sandbox_clone__'), 0) = 0
            ORDER BY id DESC LIMIT 50
            """,
            (f"{CLONE_PREFIX}%",),
        ).fetchall()
    return {"heroes": [dict(r) for r in rows]}


# ── Sandbox campaign + clone lifecycle ────────────────────────────────────────

def _ensure_rsb_campaign(conn: sqlite3.Connection, user_id: int) -> int:
    row = conn.execute(
        "SELECT id FROM campaigns WHERE owner_user_id = ? AND title LIKE ? LIMIT 1",
        (user_id, f"{RSB_TITLE_PREFIX}%"),
    ).fetchone()
    if row:
        return int(row["id"])
    cur = conn.execute(
        "INSERT INTO campaigns (title, system_id, model_id, owner_user_id, language, mode, status, gm_plan_json) "
        "VALUES (?, 'fantasy', 'sandbox', ?, 'pl', 'sandbox', 'active', '{}')",
        (f"{RSB_TITLE_PREFIX} u{user_id}", user_id),
    )
    conn.commit()
    return int(cur.lastrowid)


def _purge_rsb_clones(conn: sqlite3.Connection, user_id: int) -> int:
    conn.execute("PRAGMA foreign_keys = ON")
    rows = conn.execute(
        "SELECT id FROM characters WHERE user_id = ? AND name LIKE ?",
        (user_id, f"{CLONE_PREFIX}%"),
    ).fetchall()
    for r in rows:
        conn.execute("DELETE FROM characters WHERE id = ?", (int(r["id"]),))
    return len(rows)


def _clone_hero(conn: sqlite3.Connection, source_id: int, campaign_id: int) -> int:
    orig = conn.execute(
        "SELECT * FROM characters WHERE id = ? AND is_active = 1", (source_id,)
    ).fetchone()
    if not orig:
        raise HTTPException(status_code=404, detail="hero not found")

    sheet = json.loads(orig["sheet_json"] or "{}")
    sheet["__rest_sandbox_clone__"] = True
    sheet["__sandbox_source_id__"] = int(source_id)
    # Start at full HP/mana so tests begin from a clean state
    sheet["current_hp"] = int(sheet.get("max_hp") or 10)
    sheet["current_mana"] = int(sheet.get("max_mana") or 0)
    sheet["short_rests_used"] = 0
    sheet["pending_xp"] = 0

    cur = conn.execute(
        """INSERT INTO characters
               (campaign_id, user_id, name, system_id, sheet_json, location, is_active,
                created_at, backstory, appearance, personality, motivation, note,
                gold, gold_gp, hero_status, visited_location_keys, status)
           SELECT ?, user_id, ?, system_id, ?, location, 1,
                  datetime('now'), backstory, appearance, personality, motivation, note,
                  gold, gold_gp, hero_status, visited_location_keys, 'in_campaign'
           FROM characters WHERE id = ?""",
        (campaign_id, f"{CLONE_PREFIX}{orig['name']}", json.dumps(sheet, ensure_ascii=False), source_id),
    )
    clone_id = int(cur.lastrowid)

    conn.execute(
        "INSERT INTO character_inventory "
        "(character_id,item_key,weapon_key,consumable_key,quantity,equipped,slot,acquired_at,source,meta_json,label) "
        "SELECT ?,item_key,weapon_key,consumable_key,quantity,equipped,slot,acquired_at,source,meta_json,label "
        "FROM character_inventory WHERE character_id = ?",
        (clone_id, source_id),
    )
    conn.execute(
        "INSERT INTO character_spells (character_id,spell_key,rank,use_count) "
        "SELECT ?,spell_key,rank,use_count FROM character_spells WHERE character_id = ?",
        (clone_id, source_id),
    )
    return clone_id


def _ensure_rsb_session_and_hex(conn: sqlite3.Connection, campaign_id: int) -> tuple[str, int, int]:
    """Ensure a game_session + a plains hex exist for this RSB campaign.
    Returns (session_id, hex_q, hex_r)."""
    # Session
    gs = conn.execute(
        "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    if not gs:
        sess_id = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO game_sessions (id, campaign_id, session_flags) VALUES (?,?,?)",
            (sess_id, campaign_id, json.dumps({"state": "NARRATIVE", "current_hex": {"q": 99, "r": 99}})),
        )
        conn.commit()
        sess_id_val = sess_id
    else:
        sess_id_val = gs["id"]
        flags = json.loads(gs["session_flags"] or "{}")
        if "current_hex" not in flags:
            flags["current_hex"] = {"q": 99, "r": 99}
            conn.execute(
                "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
                (json.dumps(flags), sess_id_val),
            )
            conn.commit()

    # Dedicated sandbox hex at (99, 99)
    q, r = 99, 99
    conn.execute(
        "INSERT OR IGNORE INTO world_hexes "
        "(q,r,hex_type,label,encounter_chance,encounter_pool,created_by_gm,created_by_campaign_id,is_active) "
        "VALUES (?,?,'plains','[RSB] Poligon',0.3,'[]',1,?,1)",
        (q, r, campaign_id),
    )
    conn.commit()
    return sess_id_val, q, r


# ── Setup ────────────────────────────────────────────────────────────────────

@router.post("/setup")
def setup(payload: dict = Body(...)) -> dict[str, Any]:
    """Clone hero into RSB campaign, create test hex, anchor session."""
    source_id = int(payload.get("hero_id") or 0)
    if not source_id:
        raise HTTPException(status_code=400, detail="hero_id required")

    with _conn() as c:
        c.execute("PRAGMA foreign_keys = ON")
        orig = c.execute(
            "SELECT user_id, name FROM characters WHERE id = ? AND is_active = 1",
            (source_id,),
        ).fetchone()
        if not orig:
            raise HTTPException(status_code=404, detail="hero not found")

        user_id = int(orig["user_id"])
        campaign_id = _ensure_rsb_campaign(c, user_id)
        purged = _purge_rsb_clones(c, user_id)

        # Also reset the test hex to unsafe so each session starts clean
        c.execute(
            "UPDATE game_locations SET safe_for_rest = 0, is_active = 0 "
            "WHERE source_campaign_id = ? AND location_subtype = 'camp'",
            (campaign_id,),
        )
        c.execute(
            "UPDATE world_hexes SET location_key = NULL WHERE q = 99 AND r = 99",
        )

        clone_id = _clone_hero(c, source_id, campaign_id)
        sess_id, q, r = _ensure_rsb_session_and_hex(c, campaign_id)

        # Anchor session to clone
        c.execute(
            "UPDATE game_sessions SET current_location_id = NULL WHERE id = ?",
            (sess_id,),
        )
        flags = json.loads(
            c.execute("SELECT session_flags FROM game_sessions WHERE id=?", (sess_id,)).fetchone()["session_flags"] or "{}"
        )
        flags["current_hex"] = {"q": q, "r": r}
        c.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
            (json.dumps(flags), sess_id),
        )
        c.commit()

        sheet = json.loads(c.execute(
            "SELECT sheet_json FROM characters WHERE id = ?", (clone_id,)
        ).fetchone()["sheet_json"] or "{}")

    return {
        "ok": True,
        "campaign_id": campaign_id,
        "character_id": clone_id,
        "source_hero_id": source_id,
        "test_hex": {"q": q, "r": r},
        "prior_clones_purged": purged,
        "hero": {
            "id": clone_id,
            "name": f"{CLONE_PREFIX}{orig['name']}",
            "archetype": sheet.get("archetype"),
            "hp": int(sheet.get("current_hp") or 0),
            "max_hp": int(sheet.get("max_hp") or 0),
            "mana": int(sheet.get("current_mana") or 0),
            "max_mana": int(sheet.get("max_mana") or 0),
            "xp_available": int(sheet.get("xp_available") or 0),
            "pending_xp": int(sheet.get("pending_xp") or 0),
            "short_rests_used": int(sheet.get("short_rests_used") or 0),
        },
    }


# ── Character snapshot ────────────────────────────────────────────────────────

@router.get("/character/{character_id}")
def get_character(character_id: int) -> dict[str, Any]:
    with _conn() as c:
        row = c.execute(
            "SELECT id, name, sheet_json FROM characters WHERE id = ? AND is_active = 1",
            (character_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="character not found")
        sheet = json.loads(row["sheet_json"] or "{}")
    return {
        "id": row["id"],
        "name": row["name"],
        "archetype": sheet.get("archetype"),
        "hp": int(sheet.get("current_hp") or 0),
        "max_hp": int(sheet.get("max_hp") or 0),
        "mana": int(sheet.get("current_mana") or 0),
        "max_mana": int(sheet.get("max_mana") or 0),
        "xp_available": int(sheet.get("xp_available") or 0),
        "xp_lifetime_earned": int(sheet.get("xp_lifetime_earned") or 0),
        "pending_xp": int(sheet.get("pending_xp") or 0),
        "short_rests_used": int(sheet.get("short_rests_used") or 0),
        "conditions": sheet.get("conditions") or [],
        "stats": sheet.get("stats") or {},
    }


# ── Rest controls ─────────────────────────────────────────────────────────────

@router.post("/set-hex-safe")
def set_hex_safe(payload: dict = Body(...)) -> dict[str, Any]:
    """Toggle safe_for_rest on the RSB test hex's current location."""
    campaign_id = int(payload.get("campaign_id") or 0)
    safe = bool(payload.get("safe", True))
    if not campaign_id:
        raise HTTPException(status_code=400, detail="campaign_id required")

    with _conn() as c:
        # Get the current location from the session
        sess = c.execute(
            "SELECT current_location_id FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        loc_id = sess["current_location_id"] if sess else None

        if loc_id:
            c.execute(
                "UPDATE game_locations SET safe_for_rest = ? WHERE id = ?",
                (1 if safe else 0, loc_id),
            )
            c.commit()
            loc = c.execute("SELECT key, label, safe_for_rest FROM game_locations WHERE id = ?", (loc_id,)).fetchone()
            return {"ok": True, "safe_for_rest": safe, "location_key": loc["key"], "location_label": loc["label"]}

        # No location yet — note that build-camp is needed first
        return {"ok": False, "detail": "no_location_set — use build-camp first"}


@router.post("/build-camp")
def build_camp_endpoint(payload: dict = Body(...)) -> dict[str, Any]:
    """Create a temporary camp on the RSB test hex."""
    campaign_id = int(payload.get("campaign_id") or 0)
    character_id = int(payload.get("character_id") or 0)
    if not campaign_id or not character_id:
        raise HTTPException(status_code=400, detail="campaign_id and character_id required")

    from app.services.world_service import build_camp

    with _conn() as c:
        try:
            location = build_camp(c, campaign_id, 99, 99)
        except ValueError as e:
            err = str(e)
            if err == "hex_already_safe":
                # Already camped — just return current state
                loc = c.execute(
                    "SELECT id, key, label, safe_for_rest FROM game_locations "
                    "WHERE source_campaign_id = ? AND location_subtype = 'camp' AND is_active = 1 LIMIT 1",
                    (campaign_id,),
                ).fetchone()
                if loc:
                    c.execute(
                        "UPDATE game_sessions SET current_location_id = ? WHERE campaign_id = ?",
                        (loc["id"], campaign_id),
                    )
                    c.commit()
                    return {"ok": True, "already_camped": True, "location": dict(loc)}
            raise HTTPException(status_code=409, detail=err) from e

        # Anchor session to the new camp location
        loc_row = c.execute(
            "SELECT id, key, label FROM game_locations WHERE key = ? AND is_active = 1",
            (location["key"],),
        ).fetchone()
        if loc_row:
            c.execute(
                "UPDATE game_sessions SET current_location_id = ? WHERE campaign_id = ?",
                (loc_row["id"], campaign_id),
            )
            c.commit()

    return {"ok": True, "location": location}


@router.post("/short-rest")
def short_rest(payload: dict = Body(...)) -> dict[str, Any]:
    """Proxy to perform_short_rest."""
    campaign_id = int(payload.get("campaign_id") or 0)
    character_id = int(payload.get("character_id") or 0)
    if not campaign_id or not character_id:
        raise HTTPException(status_code=400, detail="campaign_id and character_id required")

    from app.services.rest_service import perform_short_rest

    with _conn() as c:
        result = perform_short_rest(c, character_id, campaign_id)

    if not result.get("ok"):
        err = result.get("error", "unknown")
        raise HTTPException(status_code=409, detail=err)
    return result


@router.post("/long-rest")
def long_rest(payload: dict = Body(...)) -> dict[str, Any]:
    """Proxy to perform_long_rest."""
    campaign_id = int(payload.get("campaign_id") or 0)
    character_id = int(payload.get("character_id") or 0)
    if not campaign_id or not character_id:
        raise HTTPException(status_code=400, detail="campaign_id and character_id required")

    from app.services.rest_service import perform_long_rest

    with _conn() as c:
        result = perform_long_rest(c, character_id, campaign_id)

    if not result.get("ok"):
        err = result.get("error", "unknown")
        raise HTTPException(status_code=409, detail=err)
    return result


@router.post("/roll-encounter")
def roll_encounter(payload: dict = Body(...)) -> dict[str, Any]:
    """Force an encounter check on the RSB test hex (q=99, r=99)."""
    with _conn() as c:
        hex_row = c.execute(
            "SELECT encounter_chance, encounter_pool FROM world_hexes WHERE q = 99 AND r = 99 AND is_active = 1",
        ).fetchone()
        if not hex_row:
            return {"ok": False, "detail": "test hex not found"}

        chance = float(hex_row["encounter_chance"] or 0.3)
        pool = json.loads(hex_row["encounter_pool"] or "[]")

        roll = random.random()
        triggered = roll < chance
        enemy = random.choice(pool) if triggered and pool else None

    return {
        "ok": True,
        "roll": round(roll, 3),
        "chance": chance,
        "triggered": triggered,
        "enemy_key": enemy,
        "detail": f"Napotkano {enemy}!" if triggered and enemy
                  else ("Spotkanie! (brak wrogów w puli)" if triggered else "Czysto — bez spotkania."),
    }


@router.post("/reset-hero")
def reset_hero(payload: dict = Body(...)) -> dict[str, Any]:
    """Restore HP/mana, clear conditions, reset rest charges and pending XP."""
    character_id = int(payload.get("character_id") or 0)
    if not character_id:
        raise HTTPException(status_code=400, detail="character_id required")

    with _conn() as c:
        row = c.execute(
            "SELECT sheet_json FROM characters WHERE id = ?", (character_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="character not found")
        sheet = json.loads(row["sheet_json"] or "{}")
        sheet["current_hp"] = int(sheet.get("max_hp") or 1)
        sheet["current_mana"] = int(sheet.get("max_mana") or 0)
        sheet["conditions"] = []
        sheet["short_rests_used"] = 0
        sheet["pending_xp"] = 0
        c.execute(
            "UPDATE characters SET sheet_json = ? WHERE id = ?",
            (json.dumps(sheet, ensure_ascii=False), character_id),
        )
        c.commit()

    return {
        "ok": True,
        "hp": sheet["current_hp"],
        "max_hp": sheet.get("max_hp"),
        "mana": sheet["current_mana"],
        "short_rests_used": 0,
        "pending_xp": 0,
    }


@router.post("/end")
def end_session(payload: dict = Body(...)) -> dict[str, Any]:
    """Tear down RSB session: deactivate clones + reset test hex."""
    campaign_id = int(payload.get("campaign_id") or 0)
    if not campaign_id:
        raise HTTPException(status_code=400, detail="campaign_id required")

    with _conn() as c:
        c.execute("PRAGMA foreign_keys = ON")
        c.execute(
            "UPDATE characters SET is_active = 0 WHERE campaign_id = ? AND name LIKE ?",
            (campaign_id, f"{CLONE_PREFIX}%"),
        )
        c.execute(
            "UPDATE game_locations SET is_active = 0 "
            "WHERE source_campaign_id = ? AND location_subtype = 'camp'",
            (campaign_id,),
        )
        c.execute(
            "UPDATE world_hexes SET location_key = NULL WHERE q = 99 AND r = 99",
        )
        c.commit()

    return {"ok": True}
