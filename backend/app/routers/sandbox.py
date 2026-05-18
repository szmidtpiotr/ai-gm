"""Combat Sandbox — dev/test harness for combat mechanics.

Lets an admin spawn arbitrary combats against a chosen hero without going
through the narrative pipeline. Reuses the production combat engine
(`combat_service.initiate_combat`, `resolve_attack`, `change_player_zone`,
`end_combat`) so anything verified here matches real gameplay behavior.

The sandbox lives on a dedicated campaign per (user, hero) pair, created
on first use. The campaign stays around so repeated runs don't pollute
the DB; combat is started/ended on demand.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from app.services import combat_service as combat

DB_PATH = Path("/data/ai_gm.db")
SANDBOX_TITLE_PREFIX = "[SANDBOX]"

router = APIRouter(prefix="/admin/sandbox", tags=["sandbox"])


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


# ── Lookups ─────────────────────────────────────────────────────────────────


@router.get("/heroes")
def list_heroes() -> dict[str, Any]:
    """All active heroes the admin can sandbox-test against."""
    with _conn() as c:
        rows = c.execute(
            """
            SELECT id, name, user_id, campaign_id, status,
                   json_extract(sheet_json,'$.archetype') AS archetype,
                   json_extract(sheet_json,'$.level')     AS level,
                   json_extract(sheet_json,'$.current_hp') AS hp,
                   json_extract(sheet_json,'$.max_hp')     AS max_hp
            FROM characters
            WHERE is_active = 1
            ORDER BY id DESC
            LIMIT 50
            """,
        ).fetchall()
    return {"heroes": [dict(r) for r in rows]}


@router.get("/enemies")
def list_enemies() -> dict[str, Any]:
    """Enemy templates the admin can spawn."""
    with _conn() as c:
        rows = c.execute(
            """
            SELECT key, label, tier, hp_base, ac_base, attack_bonus,
                   damage_die, dex_modifier, xp_award
            FROM game_config_enemies
            WHERE is_active = 1
            ORDER BY
              CASE tier WHEN 'minion' THEN 0 WHEN 'standard' THEN 1
                        WHEN 'elite' THEN 2 WHEN 'boss' THEN 3 ELSE 4 END,
              hp_base, label
            """,
        ).fetchall()
    return {"enemies": [dict(r) for r in rows]}


# ── Sandbox campaign lifecycle ─────────────────────────────────────────────


def _ensure_sandbox_campaign(conn: sqlite3.Connection, user_id: int) -> int:
    """Return campaign_id of the user's sandbox campaign, creating it if absent."""
    row = conn.execute(
        "SELECT id FROM campaigns WHERE owner_user_id = ? AND title LIKE ? LIMIT 1",
        (user_id, f"{SANDBOX_TITLE_PREFIX}%"),
    ).fetchone()
    if row:
        return int(row["id"])
    cur = conn.execute(
        """
        INSERT INTO campaigns (title, system_id, model_id, owner_user_id, language, mode, status, gm_plan_json)
        VALUES (?, 'fantasy', 'sandbox', ?, 'pl', 'sandbox', 'active', '{}')
        """,
        (f"{SANDBOX_TITLE_PREFIX} u{user_id}", user_id),
    )
    conn.commit()
    return int(cur.lastrowid)


@router.post("/setup")
def setup_sandbox(payload: dict = Body(...)) -> dict[str, Any]:
    """Prepare the sandbox: ensure a sandbox campaign exists for this hero's
    owner and assign the hero to it (campaign_id update on the hero row).
    Body: `{hero_id: int}`. Returns `{campaign_id, character_id, hero}`."""
    hero_id = int(payload.get("hero_id") or 0)
    if not hero_id:
        raise HTTPException(status_code=400, detail="hero_id required")

    with _conn() as c:
        hero = c.execute(
            "SELECT id, user_id, name, campaign_id, sheet_json FROM characters WHERE id = ? AND is_active = 1",
            (hero_id,),
        ).fetchone()
        if not hero:
            raise HTTPException(status_code=404, detail="hero not found")

        campaign_id = _ensure_sandbox_campaign(c, int(hero["user_id"]))

        # Force-end any active combat lingering on this campaign
        ac = c.execute(
            "SELECT id FROM active_combat WHERE campaign_id = ? AND status = 'active'",
            (campaign_id,),
        ).fetchone()
        if ac:
            c.execute(
                "UPDATE active_combat SET status='ended', ended_reason='sandbox_reset', updated_at=datetime('now') WHERE id = ?",
                (int(ac["id"]),),
            )

        # Bind hero to the sandbox campaign for the duration
        c.execute(
            "UPDATE characters SET campaign_id = ?, status = 'in_campaign' WHERE id = ?",
            (campaign_id, hero_id),
        )

        # Ensure a game_sessions row exists so combat_service helpers don't trip
        gs = c.execute(
            "SELECT id FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not gs:
            c.execute(
                """INSERT INTO game_sessions (id, campaign_id, session_flags, created_at)
                   VALUES (?, ?, '{"state":"NARRATIVE"}', datetime('now'))""",
                (uuid.uuid4().hex, campaign_id),
            )

        c.commit()

        hero_row = c.execute(
            "SELECT id, name, json_extract(sheet_json,'$.archetype') AS archetype, sheet_json FROM characters WHERE id = ?",
            (hero_id,),
        ).fetchone()
        sheet = json.loads(hero_row["sheet_json"] or "{}")

    return {
        "campaign_id": campaign_id,
        "character_id": hero_id,
        "hero": {
            "id": hero_row["id"],
            "name": hero_row["name"],
            "archetype": hero_row["archetype"],
            "level": int(sheet.get("level") or 1),
            "hp": int(sheet.get("current_hp") or sheet.get("max_hp") or 0),
            "max_hp": int(sheet.get("max_hp") or 0),
            "mana": int(sheet.get("current_mana") or 0),
            "max_mana": int(sheet.get("max_mana") or 0),
        },
    }


@router.post("/reset-hero")
def reset_hero(payload: dict = Body(...)) -> dict[str, Any]:
    """Restore the hero's HP, mana, and clear conditions. Body: `{character_id: int}`."""
    char_id = int(payload.get("character_id") or 0)
    if not char_id:
        raise HTTPException(status_code=400, detail="character_id required")
    with _conn() as c:
        row = c.execute(
            "SELECT sheet_json FROM characters WHERE id = ?",
            (char_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="hero not found")
        sheet = json.loads(row["sheet_json"] or "{}")
        sheet["current_hp"] = int(sheet.get("max_hp") or 1)
        if "max_mana" in sheet:
            sheet["current_mana"] = int(sheet.get("max_mana") or 0)
        sheet["conditions"] = []
        c.execute(
            "UPDATE characters SET sheet_json = ? WHERE id = ?",
            (json.dumps(sheet, ensure_ascii=False), char_id),
        )
        c.commit()
    return {
        "ok": True,
        "hp": sheet.get("current_hp"),
        "max_hp": sheet.get("max_hp"),
        "mana": sheet.get("current_mana"),
        "max_mana": sheet.get("max_mana"),
    }


@router.post("/start-combat")
def start_combat(payload: dict = Body(...)) -> dict[str, Any]:
    """Wrap `combat_service.initiate_combat` with no narrative dressing.
    Body: `{campaign_id, character_id, enemy_keys: [str]}`."""
    cid = int(payload.get("campaign_id") or 0)
    char_id = int(payload.get("character_id") or 0)
    enemies = list(payload.get("enemy_keys") or [])
    if not cid or not char_id or not enemies:
        raise HTTPException(status_code=400, detail="campaign_id, character_id, enemy_keys required")
    try:
        res = combat.initiate_combat(cid, char_id, enemies)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "combat_state": combat.load_combat_snapshot(cid), "initiate": res}


@router.post("/end-combat")
def end_combat(payload: dict = Body(...)) -> dict[str, Any]:
    """Force-end the active combat for this sandbox campaign. Body: `{campaign_id, reason?}`."""
    cid = int(payload.get("campaign_id") or 0)
    reason = str(payload.get("reason") or "sandbox_end")
    if not cid:
        raise HTTPException(status_code=400, detail="campaign_id required")
    combat.end_combat(cid, reason)
    return {"ok": True}
