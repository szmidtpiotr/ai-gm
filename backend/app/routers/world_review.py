"""
World Review Queue Router — V2 Phase 03 Task 10

Admin endpoints for reviewing and approving/discarding pending_review
world entities created by the GM during sessions.
"""

import sqlite3
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.world_service import (
    get_pending_review_counts,
    get_pending_locations,
    get_pending_npcs,
    get_pending_enemies,
    approve_entity,
    discard_entity,
)

DB_PATH = "/data/ai_gm.db"

router = APIRouter(prefix="/api/admin/world", tags=["admin-world-review"])


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/pending/counts")
def pending_counts():
    """Total count of pending_review entities per type. Used for admin badge."""
    conn = _get_db()
    try:
        counts = get_pending_review_counts(conn)
        counts["total"] = sum(counts.values())
        return counts
    finally:
        conn.close()


@router.get("/pending/locations")
def pending_locations():
    conn = _get_db()
    try:
        return {"items": get_pending_locations(conn)}
    finally:
        conn.close()


@router.get("/pending/npcs")
def pending_npcs():
    conn = _get_db()
    try:
        return {"items": get_pending_npcs(conn)}
    finally:
        conn.close()


@router.get("/pending/enemies")
def pending_enemies():
    conn = _get_db()
    try:
        return {"items": get_pending_enemies(conn)}
    finally:
        conn.close()


class ReviewAction(BaseModel):
    action: str  # "approve" or "discard"


@router.post("/review/{entity_type}/{key}")
def review_entity(entity_type: str, key: str, req: ReviewAction):
    """
    Approve or discard a pending_review entity.
    entity_type: location | npc | enemy
    action: approve | discard
    """
    if entity_type not in ("location", "npc", "enemy"):
        raise HTTPException(status_code=400, detail=f"Unknown entity type: {entity_type}")
    if req.action not in ("approve", "discard"):
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'discard'")

    conn = _get_db()
    try:
        if req.action == "approve":
            ok = approve_entity(conn, entity_type, key)
        else:
            ok = discard_entity(conn, entity_type, key)

        if not ok:
            raise HTTPException(status_code=404, detail=f"{entity_type} '{key}' not found")
        return {"ok": True, "entity_type": entity_type, "key": key, "action": req.action}
    finally:
        conn.close()
