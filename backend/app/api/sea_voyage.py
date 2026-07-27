"""WL-4 (#1504) — Endpointy rejsów port↔port (Wybrzeże Łez).

  GET  /api/campaigns/{id}/sea-routes?character_id=  → trasy z bieżącego portu
  POST /api/campaigns/{id}/sail                       → wykonaj rejs {character_id, route_key}

Cienka warstwa nad sea_voyage_service. POST serializowany turn-lockiem (jak /travel),
żeby rejs racujący z /turns nie mutował pozycji/zegara/złota równolegle (#1443).
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from app.core.jwt_auth import assert_campaign_owner
from app.core.db_runtime import resolve_db_path
from app.services import turn_lock
from app.services import sea_voyage_service as svc

router = APIRouter(tags=["sea_voyage"])

DB_PATH = resolve_db_path()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class SailPayload(BaseModel):
    character_id: int
    route_key: str


@router.get("/campaigns/{campaign_id}/sea-routes")
def get_sea_routes(
    campaign_id: int,
    character_id: int = Query(...),
    authorization: str | None = Header(default=None),
):
    """Trasy rejsu dostępne z bieżącego portu (dla panelu „Wypłyń")."""
    assert_campaign_owner(campaign_id, authorization)
    conn = _get_conn()
    try:
        return svc.list_sea_routes(conn, campaign_id, int(character_id))
    finally:
        conn.close()


@router.post("/campaigns/{campaign_id}/sail")
def player_sail(
    campaign_id: int,
    payload: SailPayload,
    authorization: str | None = Header(default=None),
):
    """Wykonaj rejs po wybranej trasie — pobiera złoto, przesuwa zegar, losuje zdarzenie."""
    assert_campaign_owner(campaign_id, authorization)
    _lock_key = turn_lock.acquire_or_409(campaign_id)
    conn = _get_conn()
    try:
        return svc.execute_sea_voyage(
            conn, campaign_id, int(payload.character_id), payload.route_key,
        )
    except svc.VoyageError as e:
        status = svc.VOYAGE_ERROR_STATUS.get(e.code, 400)
        raise HTTPException(status_code=status, detail=e.message)
    finally:
        conn.close()
        turn_lock.release(_lock_key)
