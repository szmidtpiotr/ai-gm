"""F17 (#477) — Hidden Trait admin endpoints."""
import sqlite3

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.services.hidden_trait_service import (
    assign_trait,
    get_character_trait,
    get_trait_pool,
    is_trait_revealed,
    reveal_trait,
)

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


class AssignTraitRequest(BaseModel):
    character_id: int
    trait_key: str


@router.get("")
def list_hidden_traits(_: None = Depends(_require_admin)):
    """Return all active hidden traits."""
    conn = _conn()
    try:
        return get_trait_pool(conn)
    finally:
        conn.close()


@router.post("/assign")
def assign_hidden_trait(
    body: AssignTraitRequest,
    _: None = Depends(_require_admin),
):
    """Assign a hidden trait to a character."""
    conn = _conn()
    try:
        assign_trait(conn, body.character_id, body.trait_key)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()
    return {"ok": True, "trait_key": body.trait_key}


@router.get("/character/{character_id}")
def get_trait_for_character(
    character_id: int,
    _: None = Depends(_require_admin),
):
    """Return the hidden trait assigned to a character."""
    conn = _conn()
    try:
        key = get_character_trait(conn, character_id)
        revealed = is_trait_revealed(conn, character_id)
    finally:
        conn.close()
    return {"character_id": character_id, "trait_key": key, "revealed": revealed}


@router.post("/character/{character_id}/reveal")
def reveal_character_trait(
    character_id: int,
    _: None = Depends(_require_admin),
):
    """Mark a character's hidden trait as revealed."""
    conn = _conn()
    try:
        reveal_trait(conn, character_id)
    finally:
        conn.close()
    return {"ok": True, "revealed": True}
