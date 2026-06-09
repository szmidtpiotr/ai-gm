"""E23 — Seen mechanics per-user tracking.

GET  /api/users/{user_id}/seen-mechanics       → list seen mechanic keys
POST /api/users/{user_id}/seen-mechanics        → mark mechanic as seen (idempotent)
"""
from __future__ import annotations
import json
import sqlite3
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()
DB_PATH = "/data/ai_gm.db"

VALID_MECHANIC_KEYS = {
    "dice_roll", "combat_start", "damage_taken",
    "xp_gained", "gold_gained", "death_save",
    # future keys from E27
    "affixes", "crafting", "multiplayer",
}


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class MarkSeenRequest(BaseModel):
    mechanic_key: str


@router.get("/users/{user_id}/seen-mechanics")
def get_seen_mechanics(user_id: int):
    """Return list of mechanic_key strings the user has already seen."""
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT mechanic_key, seen_at FROM seen_mechanics WHERE user_id = ? ORDER BY seen_at",
            (user_id,),
        ).fetchall()
        return {"seen": [{"mechanic_key": r["mechanic_key"], "seen_at": r["seen_at"]} for r in rows]}
    finally:
        conn.close()


@router.post("/users/{user_id}/seen-mechanics")
def mark_mechanic_seen(user_id: int, req: MarkSeenRequest):
    """Mark a mechanic as seen for the user (idempotent — UPSERT)."""
    conn = _get_db()
    try:
        conn.execute(
            """INSERT INTO seen_mechanics (user_id, mechanic_key)
               VALUES (?, ?)
               ON CONFLICT(user_id, mechanic_key) DO NOTHING""",
            (user_id, req.mechanic_key),
        )
        conn.commit()
        return {"ok": True, "mechanic_key": req.mechanic_key}
    finally:
        conn.close()
