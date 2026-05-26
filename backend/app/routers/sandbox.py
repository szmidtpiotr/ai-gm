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
from app.services.xp_service import get_hero_level as _get_hero_level

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
    """All active heroes the admin can sandbox-test against.
    Excludes the sandbox clones themselves (name prefixed '[SBX] ')."""
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
              AND (name NOT LIKE '[SBX] %' OR name IS NULL)
              AND COALESCE(json_extract(sheet_json,'$.__sandbox_clone__'), 0) = 0
            ORDER BY id DESC
            LIMIT 50
            """,
        ).fetchall()
    return {"heroes": [dict(r) for r in rows]}


def _purge_prior_sandbox_clones(c: sqlite3.Connection, user_id: int) -> int:
    """Hard-delete any sandbox clones owned by this user. FK CASCADE drops
    their inventory + spells. Returns count of clones removed."""
    priors = c.execute(
        "SELECT id FROM characters WHERE user_id = ? AND name LIKE '[SBX] %'",
        (user_id,),
    ).fetchall()
    for p in priors:
        c.execute("DELETE FROM characters WHERE id = ?", (int(p["id"]),))
    return len(priors)


def _clone_hero_for_sandbox(
    c: sqlite3.Connection, source_hero_id: int, campaign_id: int
) -> int:
    """Create a disposable copy of `source_hero_id` for sandbox combat.

    Copies the `characters` row, `character_inventory` rows, and
    `character_spells` rows. Tags the clone with name prefix '[SBX] ' and
    `sheet_json.__sandbox_clone__ = true` so it can be detected and
    filtered out elsewhere. Returns the new clone's character id.
    """
    orig = c.execute(
        "SELECT * FROM characters WHERE id = ? AND is_active = 1",
        (source_hero_id,),
    ).fetchone()
    if not orig:
        raise HTTPException(status_code=404, detail="hero not found")

    sheet = json.loads(orig["sheet_json"] or "{}")
    sheet["__sandbox_clone__"] = True
    sheet["__sandbox_source_id__"] = int(source_hero_id)
    sheet_json = json.dumps(sheet, ensure_ascii=False)
    clone_name = f"[SBX] {orig['name']}"

    cur = c.execute(
        """
        INSERT INTO characters
            (campaign_id, user_id, name, system_id, sheet_json, location, is_active,
             created_at, backstory, appearance, personality, motivation, note,
             gold, gold_gp, hero_status, visited_location_keys, status)
        SELECT ?, user_id, ?, system_id, ?, location, 1,
               datetime('now'), backstory, appearance, personality, motivation, note,
               gold, gold_gp, hero_status, visited_location_keys, 'in_campaign'
        FROM characters WHERE id = ?
        """,
        (campaign_id, clone_name, sheet_json, source_hero_id),
    )
    clone_id = int(cur.lastrowid)

    c.execute(
        """
        INSERT INTO character_inventory
            (character_id, item_key, weapon_key, consumable_key, quantity, equipped,
             slot, acquired_at, source, meta_json, label)
        SELECT ?, item_key, weapon_key, consumable_key, quantity, equipped,
               slot, acquired_at, source, meta_json, label
        FROM character_inventory WHERE character_id = ?
        """,
        (clone_id, source_hero_id),
    )

    c.execute(
        """
        INSERT INTO character_spells (character_id, spell_key, rank, use_count)
        SELECT ?, spell_key, rank, use_count
        FROM character_spells WHERE character_id = ?
        """,
        (clone_id, source_hero_id),
    )

    return clone_id


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
    """Prepare an isolated sandbox session against a copy of the chosen hero.

    Critical isolation guarantee: the sandbox NEVER modifies the original
    hero. On setup we (1) end any lingering sandbox combat, (2) hard-delete
    any prior sandbox clones for this owner (cascade drops their inventory
    and spells), (3) clone the chosen hero into a new disposable character
    row (`name = "[SBX] <orig>"`, `sheet_json.__sandbox_clone__ = true`),
    and (4) bind the clone to the sandbox campaign. All subsequent attacks,
    HP/mana decrements, death-saves, equipment changes etc. happen on the
    clone — the original hero stays untouched even if the sandbox combat
    ends in player_dead.

    Body: `{hero_id: int}` — id of the **original** hero to copy from.
    Returns: `{campaign_id, character_id, source_hero_id, hero summary}`.
    """
    source_hero_id = int(payload.get("hero_id") or 0)
    if not source_hero_id:
        raise HTTPException(status_code=400, detail="hero_id required")

    with _conn() as c:
        # Foreign-key cascade for the clone deletion needs to be enabled
        c.execute("PRAGMA foreign_keys = ON")

        orig = c.execute(
            "SELECT id, user_id, name FROM characters WHERE id = ? AND is_active = 1",
            (source_hero_id,),
        ).fetchone()
        if not orig:
            raise HTTPException(status_code=404, detail="hero not found")

        user_id = int(orig["user_id"])
        campaign_id = _ensure_sandbox_campaign(c, user_id)

        # Drop any active_combat row for this sandbox campaign — the existing
        # row references the prior clone via FK (character_id) and would block
        # the upcoming clone purge. Also wipe combat_turns history so the
        # events feed starts clean. Both are sandbox-only data, safe to discard.
        c.execute("DELETE FROM combat_turns WHERE campaign_id = ?", (campaign_id,))
        c.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))

        # Wipe prior sandbox clones for this owner — FK cascade clears their
        # inventory + spells too.
        purged = _purge_prior_sandbox_clones(c, user_id)

        # Fresh clone of the chosen hero (original row untouched).
        clone_id = _clone_hero_for_sandbox(c, source_hero_id, campaign_id)

        # game_sessions row so combat_service helpers don't trip.
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

        clone_row = c.execute(
            "SELECT id, name, sheet_json FROM characters WHERE id = ?",
            (clone_id,),
        ).fetchone()
        sheet = json.loads(clone_row["sheet_json"] or "{}")

    return {
        "campaign_id": campaign_id,
        "character_id": clone_id,
        "source_hero_id": source_hero_id,
        "prior_clones_purged": purged,
        "hero": {
            "id": clone_row["id"],
            "name": clone_row["name"],
            "archetype": sheet.get("archetype"),
            "level": _get_hero_level(sheet),
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


@router.get("/character/{character_id}")
def get_character_full(character_id: int) -> dict[str, Any]:
    """Aggregated character snapshot for the sandbox sheet card:
    parsed sheet (stats, hp/mana, conditions) + inventory + spells.
    Single call to keep the UI render path cheap."""
    with _conn() as c:
        row = c.execute(
            "SELECT id, name, sheet_json, gold_gp FROM characters WHERE id = ? AND is_active = 1",
            (character_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="character not found")
        sheet = json.loads(row["sheet_json"] or "{}")

    # Inventory + spells: call services directly to avoid HTTP hop
    from app.services import loot_service
    from app.services.spell_service import get_character_spells

    try:
        inventory = loot_service.get_character_inventory(character_id)
    except Exception:
        inventory = {}
    try:
        spells = get_character_spells(character_id)
    except Exception:
        spells = []

    return {
        "id": row["id"],
        "name": row["name"],
        "gold_gp": row["gold_gp"] or 0,
        "archetype": sheet.get("archetype"),
        "level": int(sheet.get("level") or 1),
        "stats": sheet.get("stats") or {},
        "skills": sheet.get("skills") or {},
        "hp": int(sheet.get("current_hp") or 0),
        "max_hp": int(sheet.get("max_hp") or 0),
        "mana": int(sheet.get("current_mana") or 0),
        "max_mana": int(sheet.get("max_mana") or 0),
        "conditions": sheet.get("conditions") or [],
        "inventory": inventory,
        "spells": spells,
    }


@router.post("/advance-turn")
def advance_turn_endpoint(payload: dict = Body(...)) -> dict[str, Any]:
    """Advance the turn pointer to the next combatant. In real gameplay this
    happens inside the narration pipeline; the sandbox skips narration so it
    needs an explicit way to end the player's turn after an attack."""
    cid = int(payload.get("campaign_id") or 0)
    if not cid:
        raise HTTPException(status_code=400, detail="campaign_id required")
    try:
        new_turn = combat.advance_turn(cid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "current_turn": new_turn, "combat_state": combat.load_combat_snapshot(cid)}


@router.post("/end-combat")
def end_combat(payload: dict = Body(...)) -> dict[str, Any]:
    """Force-end the active combat for this sandbox campaign. Body: `{campaign_id, reason?}`."""
    cid = int(payload.get("campaign_id") or 0)
    reason = str(payload.get("reason") or "sandbox_end")
    if not cid:
        raise HTTPException(status_code=400, detail="campaign_id required")
    combat.end_combat(cid, reason)
    return {"ok": True}
