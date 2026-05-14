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
