"""F17 (#477) — Hidden Trait admin endpoints."""
import sqlite3

from fastapi import APIRouter, Depends, Header, HTTPException

from app.services.hidden_trait_service import get_trait_pool

ADMIN_SQLITE_PATH = "/data/ai_gm.db"

router = APIRouter(prefix="/admin/hidden-traits", tags=["admin-hidden-traits"])


def _require_admin(authorization: str | None = Header(default=None)) -> None:
    """Simple admin token check (mirrors pattern in admin.py)."""
    from app.services.admin_auth import verify_admin_token
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing auth token")
    token = authorization.removeprefix("Bearer ").strip()
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Invalid admin token")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(ADMIN_SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@router.get("")
def list_hidden_traits(_: None = Depends(_require_admin)):
    """Return all active hidden traits."""
    conn = _conn()
    try:
        return get_trait_pool(conn)
    finally:
        conn.close()
