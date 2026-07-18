"""Companion & mount player API — #1192 FAZA TW.

Deterministic (no LLM): recruit/buy/dismiss towarzysze & wierzchowce, list what
a location offers, list a character's active companions. Mirrors services_shop.py.
"""
import sqlite3

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services import companion_service

router = APIRouter(tags=["companions"])

DB_PATH = "/data/ai_gm.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class HireRequest(BaseModel):
    companion_key: str
    campaign_id: int | None = None


class BuyRequest(BaseModel):
    companion_key: str
    custom_name: str | None = None
    campaign_id: int | None = None


class DismissRequest(BaseModel):
    companion_id: int


_ERR = {
    "companion_not_found": (404, "Companion not found"),
    "not_hireable": (400, "Companion cannot be hired"),
    "not_buyable": (400, "Companion cannot be bought"),
    "slot_occupied": (409, "That companion slot is already taken"),
    "insufficient_gold": (402, "Not enough gold"),
}


def _map_error(e: ValueError) -> HTTPException:
    code, msg = _ERR.get(str(e), (400, str(e)))
    return HTTPException(status_code=code, detail=msg)


@router.get("/characters/{character_id}/companions")
def list_companions(character_id: int):
    conn = _get_conn()
    try:
        return {"ok": True, "data": companion_service.get_active_companions(conn, character_id)}
    finally:
        conn.close()


@router.get("/locations/{location_key}/companions")
def companions_at_location(location_key: str, character_id: int = Query(...)):
    conn = _get_conn()
    try:
        data = companion_service.companions_at_location(
            conn, location_key, character_id=character_id
        )
        return {"ok": True, "data": data}
    finally:
        conn.close()


@router.post("/characters/{character_id}/companions/hire")
def hire_companion(character_id: int, body: HireRequest):
    conn = _get_conn()
    try:
        data = companion_service.hire(
            conn, character_id, body.companion_key, campaign_id=body.campaign_id
        )
        return {"ok": True, "data": data}
    except ValueError as e:
        raise _map_error(e) from e
    finally:
        conn.close()


@router.post("/characters/{character_id}/companions/buy")
def buy_companion(character_id: int, body: BuyRequest):
    conn = _get_conn()
    try:
        data = companion_service.buy(
            conn, character_id, body.companion_key,
            custom_name=body.custom_name, campaign_id=body.campaign_id,
        )
        return {"ok": True, "data": data}
    except ValueError as e:
        raise _map_error(e) from e
    finally:
        conn.close()


@router.post("/characters/{character_id}/companions/dismiss")
def dismiss_companion(character_id: int, body: DismissRequest):
    conn = _get_conn()
    try:
        data = companion_service.dismiss(conn, character_id, body.companion_id)
        return {"ok": True, "data": data}
    except ValueError as e:
        raise _map_error(e) from e
    finally:
        conn.close()


class MountEscapeRequest(BaseModel):
    character_id: int


@router.post("/campaigns/{campaign_id}/travel/escape-mounted")
def escape_mounted(campaign_id: int, body: MountEscapeRequest):
    """TW7: próba ucieczki konno z aktywnego spotkania w podróży (test Jeździectwa).
    Sukces = walki nie ma; porażka = walka ruszy przy TRAVEL_RESUME."""
    conn = _get_conn()
    try:
        data = companion_service.resolve_travel_escape(conn, campaign_id, body.character_id)
        return {"ok": True, "data": data}
    except ValueError as e:
        code = {"no_encounter": 409, "no_mount": 400}.get(str(e), 400)
        raise HTTPException(status_code=code, detail=str(e)) from e
    finally:
        conn.close()
