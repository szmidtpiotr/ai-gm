"""WL-8b (#1504) — Endpointy kantoru (weksle) enklawy krasnoludzkiej.

  GET  /api/campaigns/{id}/kantor?character_id=      → stan: dostępność + weksle + złoto
  POST /api/campaigns/{id}/kantor/buy    {character_id, amount}     → wystaw weksel
  POST /api/campaigns/{id}/kantor/redeem {character_id, weksel_id}  → wymień na złoto

Cienka warstwa nad kantor_service. Buy/redeem wymagają, by bohater stał w miejscu
z kantorem (enklawa krasnoludzka) — inaczej 409. Auth: właściciel postaci.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from app.core.db_runtime import resolve_db_path
from app.core.jwt_auth import assert_character_owner
from app.services import kantor_service as svc

router = APIRouter(tags=["kantor"])

DB_PATH = resolve_db_path()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class WekselBuyRequest(BaseModel):
    character_id: int
    amount: int


class WekselRedeemRequest(BaseModel):
    character_id: int
    weksel_id: int


_ERR_STATUS = {
    "character_not_found": 404,
    "weksel_not_found": 404,
    "amount_too_small": 400,
    "insufficient_gold": 400,
    "no_kantor_here": 409,
}


def _raise(e: ValueError):
    code = str(e)
    raise HTTPException(status_code=_ERR_STATUS.get(code, 400), detail=code)


@router.get("/campaigns/{campaign_id}/kantor")
def get_kantor(
    campaign_id: int,
    character_id: int = Query(...),
    authorization: str | None = Header(default=None),
):
    """Stan kantoru: czy tu dostępny, lista weksli, aktualne złoto i suma w papierze."""
    assert_character_owner(int(character_id), authorization)
    conn = _get_conn()
    try:
        from app.services.economy_service import get_character_gold
        return {
            "ok": True,
            "available": svc.kantor_available(conn, campaign_id),
            "weksle": svc.list_weksle(conn, int(character_id)),
            "weksle_total": svc.total_weksle_value(conn, int(character_id)),
            "gold": int(get_character_gold(conn, int(character_id))),
            "fee_pct": svc.KANTOR_FEE_PCT,
            "min_amount": svc.MIN_WEKSEL_AMOUNT,
        }
    finally:
        conn.close()


@router.post("/campaigns/{campaign_id}/kantor/buy")
def buy_weksel(
    campaign_id: int,
    body: WekselBuyRequest,
    authorization: str | None = Header(default=None),
):
    """Zamień złoto na weksel (nominał + prowizja). Wymaga kantoru w lokacji."""
    assert_character_owner(body.character_id, authorization)
    conn = _get_conn()
    try:
        if not svc.kantor_available(conn, campaign_id):
            _raise(ValueError("no_kantor_here"))
        result = svc.buy_weksel(conn, body.character_id, body.amount)
        conn.commit()
        return {"ok": True, "data": result}
    except ValueError as e:
        conn.rollback()
        _raise(e)
    finally:
        conn.close()


@router.post("/campaigns/{campaign_id}/kantor/redeem")
def redeem_weksel(
    campaign_id: int,
    body: WekselRedeemRequest,
    authorization: str | None = Header(default=None),
):
    """Wymień weksel na złoto (pełny nominał). Wymaga kantoru w lokacji."""
    assert_character_owner(body.character_id, authorization)
    conn = _get_conn()
    try:
        if not svc.kantor_available(conn, campaign_id):
            _raise(ValueError("no_kantor_here"))
        result = svc.redeem_weksel(conn, body.character_id, body.weksel_id)
        conn.commit()
        return {"ok": True, "data": result}
    except ValueError as e:
        conn.rollback()
        _raise(e)
    finally:
        conn.close()
