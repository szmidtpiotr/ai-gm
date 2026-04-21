"""Phase 8A — combat state API (solo campaigns)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import combat_service as combat

router = APIRouter(tags=["combat"])


class CombatStartRequest(BaseModel):
    enemy_keys: list[str] = Field(..., min_length=1)
    character_id: int | None = None


class ResolveAttackRequest(BaseModel):
    roll_result: int
    attacker: str = "player"


def _first_character_id(campaign_id: int) -> int:
    conn = sqlite3.connect(combat.COMBAT_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id FROM characters WHERE campaign_id = ? ORDER BY id ASC LIMIT 1",
            (campaign_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=400, detail="Campaign has no character")
    return int(row["id"])


@router.post("/campaigns/{campaign_id}/combat/start")
def post_start_combat(campaign_id: int, body: CombatStartRequest):
    if combat.get_active_combat(campaign_id):
        raise HTTPException(
            status_code=409,
            detail=(
                "W tej kampanii jest już aktywna walka. Zakończ ją (np. narracja po zwycięstwie, "
                "przycisk ucieczki) zanim rozpoczniesz nową sesję w silniku."
            ),
        )
    ch_id = body.character_id if body.character_id is not None else _first_character_id(campaign_id)
    try:
        state = combat.initiate_combat(campaign_id, ch_id, body.enemy_keys)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return state


@router.get("/campaigns/{campaign_id}/combat")
def get_combat(campaign_id: int):
    """Active combat only. When none, 200 + active:false (avoid 404 spam from UI polling)."""
    st = combat.get_active_combat(campaign_id)
    if not st:
        return {"active": False, "combat": None}
    return {"active": True, "combat": st}


@router.get("/campaigns/{campaign_id}/combat/turns")
def get_combat_turns(campaign_id: int, limit: int = Query(50, ge=1, le=200)):
    """Chronological combat engine log for the campaign's current combat row (active or ended)."""
    rows = combat.list_combat_turns_for_campaign(campaign_id, limit=limit)
    return {"turns": rows, "count": len(rows)}


@router.post("/campaigns/{campaign_id}/combat/resolve-attack")
def post_resolve_attack(campaign_id: int, body: ResolveAttackRequest):
    try:
        return combat.resolve_attack(campaign_id, body.roll_result, attacker=body.attacker)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/campaigns/{campaign_id}/combat/enemy-turn")
def post_enemy_turn(campaign_id: int):
    try:
        res = combat.resolve_attack(campaign_id, 0, attacker="enemy")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    snap = combat.load_combat_snapshot(campaign_id)
    if snap and snap.get("status") == "active":
        try:
            new_turn = combat.advance_turn(campaign_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        res["advance_turn"] = new_turn
    else:
        res["advance_turn"] = "ended"
    res["combat_state"] = combat.load_combat_snapshot(campaign_id)
    return res


@router.post("/campaigns/{campaign_id}/combat/flee")
def post_flee(campaign_id: int):
    """
    End active combat as fled. Returns 409 if there is no active combat row
    (distinct from a missing HTTP route — avoids confusion with literal 404).
    Idempotent: if combat already ended with reason fled, returns 200 with already_ended.
    """
    if combat.get_active_combat(campaign_id):
        combat.end_combat(campaign_id, "fled")
        return {
            "fled": True,
            "already_ended": False,
            "combat_state": combat.load_combat_snapshot(campaign_id),
        }
    snap = combat.load_combat_snapshot(campaign_id)
    if (
        snap
        and str(snap.get("status") or "") == "ended"
        and str(snap.get("ended_reason") or "") == "fled"
    ):
        return {"fled": True, "already_ended": True, "combat_state": snap}
    raise HTTPException(
        status_code=409,
        detail=(
            "Brak aktywnej walki — ucieczka z silnika jest możliwa tylko gdy trwa walka "
            "(status active). Jeśli panel jest nieaktualny, odśwież stronę."
        ),
    )
