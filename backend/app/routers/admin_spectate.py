"""Admin spectator + resume router — Issue #400.

Player-frontend-callable endpoints (an admin browses/resumes any campaign from
the normal game UI). Gating is by the caller's own user id + is_admin flag,
matching the low-auth player API surface. Every endpoint requires a valid
admin_user_id.
"""
import sqlite3

from fastapi import APIRouter, HTTPException, Query

from app.services.admin_spectate_service import (
    is_admin_user,
    list_users,
    list_all_campaigns,
    resume_campaign,
)

DB_PATH = "/data/ai_gm.db"

router = APIRouter(prefix="/api/admin-spectate", tags=["admin-spectate"])


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _require_admin(conn: sqlite3.Connection, admin_user_id: int) -> None:
    if not is_admin_user(conn, admin_user_id):
        raise HTTPException(status_code=403, detail="admin only")


@router.get("/users")
def get_users(admin_user_id: int = Query(...)):
    """Users for the admin dropdown."""
    conn = _get_db()
    try:
        _require_admin(conn, admin_user_id)
        return {"users": list_users(conn)}
    finally:
        conn.close()


@router.get("/campaigns")
def get_campaigns(admin_user_id: int = Query(...), user_id: int | None = Query(None)):
    """All campaigns (optionally filtered by owner via the dropdown)."""
    conn = _get_db()
    try:
        _require_admin(conn, admin_user_id)
        return {"campaigns": list_all_campaigns(conn, user_id=user_id)}
    finally:
        conn.close()


@router.get("/campaigns/{campaign_id}/view")
def get_campaign_view(campaign_id: int, admin_user_id: int = Query(...), limit: int = Query(30, ge=1, le=100)):
    """Read-only spectator bundle: campaign meta + last turns + character."""
    conn = _get_db()
    try:
        _require_admin(conn, admin_user_id)
        camp = conn.execute(
            "SELECT id, title, status, owner_user_id FROM campaigns WHERE id = ?",
            (campaign_id,),
        ).fetchone()
        if not camp:
            raise HTTPException(status_code=404, detail="campaign not found")
        turns = conn.execute(
            """SELECT id, turn_number, character_id, user_text, assistant_text, route, created_at
               FROM campaign_turns WHERE campaign_id = ?
               ORDER BY id DESC LIMIT ?""",
            (campaign_id, limit),
        ).fetchall()
        char_id = None
        for t in turns:
            if t["character_id"] is not None:
                char_id = t["character_id"]
                break
        character = None
        if char_id is not None:
            cr = conn.execute(
                "SELECT id, name, sheet_json, status, campaign_id FROM characters WHERE id = ?",
                (char_id,),
            ).fetchone()
            character = dict(cr) if cr else None
        return {
            "campaign": dict(camp),
            "turns": [dict(t) for t in reversed(turns)],
            "character": character,
        }
    finally:
        conn.close()


@router.post("/campaigns/{campaign_id}/resume")
def post_resume(campaign_id: int, admin_user_id: int = Query(...)):
    """Re-attach the campaign's hero + reactivate so it's playable again."""
    conn = _get_db()
    try:
        _require_admin(conn, admin_user_id)
        out = resume_campaign(conn, campaign_id)
        if not out.get("ok"):
            raise HTTPException(status_code=400, detail=out.get("reason") or "resume failed")
        return out
    finally:
        conn.close()
