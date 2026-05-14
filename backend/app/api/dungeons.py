"""Player-facing dungeon run API — Task 41."""
from __future__ import annotations

import sqlite3
from fastapi import APIRouter, Body, HTTPException

router = APIRouter()
DB_PATH = "/data/ai_gm.db"


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/dungeons")
def list_dungeons_for_character(character_id: int):
    from app.services.dungeon_service import list_dungeons
    return {"dungeons": list_dungeons(character_id)}


@router.get("/dungeons/{dungeon_key}")
def get_dungeon_detail(dungeon_key: str, character_id: int | None = None):
    from app.services.dungeon_service import check_cooldown, get_dungeon
    d = get_dungeon(dungeon_key)
    if not d:
        raise HTTPException(status_code=404, detail="Dungeon not found")
    if character_id:
        d["cooldown"] = check_cooldown(character_id, dungeon_key)
    return d


@router.post("/dungeons/{dungeon_key}/complete")
def complete_dungeon_run(dungeon_key: str, req: dict = Body(...)):
    character_id = req.get("character_id")
    if not character_id:
        raise HTTPException(status_code=400, detail="character_id required")
    from app.services.dungeon_service import (
        check_cooldown,
        complete_dungeon,
        get_dungeon,
    )
    d = get_dungeon(dungeon_key)
    if not d:
        raise HTTPException(status_code=404, detail="Dungeon not found")
    cd = check_cooldown(int(character_id), dungeon_key)
    if cd.get("on_cooldown"):
        raise HTTPException(
            status_code=409,
            detail=f"Dungeon on cooldown for {cd.get('hours_remaining')}h",
        )
    result = complete_dungeon(int(character_id), dungeon_key)
    return {"ok": True, **result, "xp_granted": 75}


@router.get("/characters/{character_id}/dungeon-history")
def character_dungeon_history(character_id: int):
    from app.services.dungeon_service import get_run_history
    history = get_run_history(character_id)
    return {"history": history}

# ── New endpoints ─────────────────────────────────────────────────────────────

from pydantic import BaseModel


class DungeonEnterReq(BaseModel):
    character_id: int
    campaign_id: int


@router.post("/dungeons/{dungeon_key}/enter")
def enter_dungeon(dungeon_key: str, req: DungeonEnterReq):
    """Enter a dungeon — checks cooldown, generates instance, stores in session."""
    from app.services.dungeon_service import enter_dungeon as _enter, get_dungeon
    import sqlite3 as _sl

    dungeon = get_dungeon(dungeon_key)
    if not dungeon:
        raise HTTPException(status_code=404, detail="Dungeon not found")

    # Get hero level from character sheet
    conn = _sl.connect(DB_PATH)
    conn.row_factory = _sl.Row
    try:
        char = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ? AND campaign_id = ?",
            (req.character_id, req.campaign_id),
        ).fetchone()
        if not char:
            raise HTTPException(status_code=404, detail="Character not found")
        import json
        sheet = json.loads(char["sheet_json"] or "{}")
        hero_level = int(sheet.get("level", 1) or 1)
    finally:
        conn.close()

    try:
        instance = _enter(req.campaign_id, req.character_id, dungeon_key, hero_level)
    except PermissionError as e:
        parts = str(e).split(":")
        detail = {"error": "dungeon_on_cooldown"}
        if len(parts) >= 3:
            detail["cooldown_until"] = parts[1]
            detail["hours_remaining"] = float(parts[2])
        raise HTTPException(status_code=423, detail=detail)

    # First room narration
    first_room = instance["rooms"][0] if instance["rooms"] else {}
    enemy_key = first_room.get("enemy_key", "")
    atm = instance.get("atmosphere", "")
    return {
        "ok": True,
        "dungeon_run": instance,
        "room_narrative": f"Wkraczasz do {instance['dungeon_label']}. {atm} "
                          f"W pierwszej komnacie czai się {'boss' if first_room.get('is_boss') else enemy_key}.",
    }


@router.post("/dungeons/advance-room")
def advance_dungeon_room(req: DungeonEnterReq):
    """Mark current room cleared and advance to next room."""
    from app.services.dungeon_service import advance_room, get_active_dungeon_run, complete_dungeon, get_current_room

    run = get_active_dungeon_run(req.campaign_id)
    if not run:
        raise HTTPException(status_code=409, detail="No active dungeon run")

    updated_run = advance_room(req.campaign_id)

    # If dungeon completed, record the clear
    if updated_run.get("completed"):
        try:
            complete_dungeon(req.character_id, updated_run["dungeon_key"])
        except Exception:
            pass
        return {
            "ok": True,
            "dungeon_run": updated_run,
            "completed": True,
            "narrative": f"Pokonałeś {updated_run['dungeon_label']}! Możesz teraz zebrać łupy i wyjść.",
        }

    next_room = get_current_room(updated_run)
    enemy_key = (next_room or {}).get("enemy_key", "")
    is_boss = (next_room or {}).get("is_boss", False)
    return {
        "ok": True,
        "dungeon_run": updated_run,
        "completed": False,
        "narrative": f"Komnat {updated_run['current_room']}/{updated_run['total_rooms']}. "
                     + (f"BOSS: {enemy_key}!" if is_boss else f"Wróg: {enemy_key}."),
    }


@router.get("/campaigns/{campaign_id}/dungeon-run")
def get_current_dungeon_run(campaign_id: int):
    """Return active dungeon run from session, if any."""
    from app.services.dungeon_service import get_active_dungeon_run
    run = get_active_dungeon_run(campaign_id)
    if not run:
        return {"dungeon_run": None}
    return {"dungeon_run": run}
