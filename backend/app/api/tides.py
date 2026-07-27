"""WL-5 (#1504/#1505) — Endpoint stanu pływów (Wybrzeże Łez).

  GET /api/campaigns/{id}/tide?character_id=  → stan pływu dla panelu ŻAR

Cienka warstwa nad tide_service.get_tide_state. Read-only (nie mutuje stanu),
więc bez turn-locka. Licznik godzin do zmiany widoczny tylko z Tabliczką pływów.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Header, Query

from app.core.jwt_auth import assert_campaign_owner
from app.core.db_runtime import resolve_db_path
from app.services import tide_service as svc

router = APIRouter(tags=["tides"])

DB_PATH = resolve_db_path()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/campaigns/{campaign_id}/tide")
def get_tide(
    campaign_id: int,
    character_id: int = Query(...),
    authorization: str | None = Header(default=None),
):
    """Stan pływu: faza, przejezdność płycizny, wskaźnik wybrzeża, licznik (z tabliczką)."""
    assert_campaign_owner(campaign_id, authorization)
    conn = _get_conn()
    try:
        return svc.get_tide_state(conn, campaign_id, int(character_id))
    finally:
        conn.close()
