"""#1292 — mechanical tavern/inn/smith/healer services (bypass the LLM entirely).

Sibling to shop.py (merchant items) but for game_config_services (lodging, food,
repairs, healing, travel). Player-facing modal opens via a suggested_actions chip
or a deterministic pre-LLM text intercept — never via a narrator [SPEND_GOLD] tag.
"""
import sqlite3

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services import location_services

router = APIRouter(tags=["services"])

DB_PATH = "/data/ai_gm.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class ServiceBuyRequest(BaseModel):
    character_id: int


class ServiceBuyBatchRequest(BaseModel):
    character_id: int
    service_keys: list[str]


def _map_error(e: ValueError) -> HTTPException:
    msg = str(e)
    if msg == "service_not_found":
        return HTTPException(status_code=404, detail="Service not available here")
    if msg == "character_not_found":
        return HTTPException(status_code=404, detail="Character not found")
    if msg == "insufficient_gold":
        return HTTPException(status_code=402, detail="Not enough gold")
    if msg == "empty_cart":
        return HTTPException(status_code=400, detail="No services selected")
    return HTTPException(status_code=400, detail=msg)


@router.get("/services/at-location/{location_key}")
def get_services_at_location(location_key: str, character_id: int = Query(...)):
    conn = _get_conn()
    try:
        data = location_services.get_services_catalog(conn, location_key, character_id)
        return {"ok": True, "data": data}
    finally:
        conn.close()


@router.post("/services/{service_key}/buy")
def post_service_buy(service_key: str, body: ServiceBuyRequest):
    conn = _get_conn()
    try:
        data = location_services.buy_service(conn, body.character_id, service_key)
        return {"ok": True, "data": data}
    except ValueError as e:
        raise _map_error(e) from e
    finally:
        conn.close()


@router.post("/services/buy-batch")
def post_services_buy_batch(body: ServiceBuyBatchRequest):
    """Multi-select checkout: buy several services at once. Atomic — verifies the
    full cart is affordable before deducting anything."""
    conn = _get_conn()
    try:
        data = location_services.buy_services_batch(conn, body.character_id, body.service_keys)
        return {"ok": True, "data": data}
    except ValueError as e:
        raise _map_error(e) from e
    finally:
        conn.close()
