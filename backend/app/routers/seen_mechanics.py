"""E23 — Seen mechanics per-user tracking.

GET  /api/users/{user_id}/seen-mechanics       → list seen mechanic keys
POST /api/users/{user_id}/seen-mechanics        → mark mechanic as seen (idempotent)
"""
from __future__ import annotations
import json
import sqlite3
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.db_runtime import resolve_db_path

router = APIRouter()
DB_PATH = resolve_db_path()

VALID_MECHANIC_KEYS = {
    "dice_roll", "combat_start", "damage_taken",
    "xp_gained", "gold_gained", "death_save",
    # future keys from E27
    "affixes", "crafting", "multiplayer",
    # U20 (#572)
    "durability", "raids", "crafter",
    # L16/L12b — dungeon tile mode
    "dungeon_tiles",
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


@router.get("/users/{user_id}/has-campaigns")
def user_has_campaigns(user_id: int):
    """Return whether the user has any campaigns (used to decide tutorial offer)."""
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM campaigns WHERE owner_user_id = ?",
            (user_id,),
        ).fetchone()
        return {"has_campaigns": bool(row and int(row["c"] or 0) > 0)}
    finally:
        conn.close()


@router.get("/users/{user_id}/mechanic-cards")
def get_mechanic_cards_library(user_id: int):
    """Return full onboarding cards for all mechanics the user has already seen (the library)."""
    from app.services.onboarding_service import MECHANIC_CARDS
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT mechanic_key, seen_at FROM seen_mechanics WHERE user_id = ? ORDER BY seen_at",
            (user_id,),
        ).fetchall()
        cards = []
        for r in rows:
            key = r["mechanic_key"]
            card_def = MECHANIC_CARDS.get(key)
            if card_def:
                cards.append({
                    "mechanic_key": key,
                    "title": card_def["title"],
                    "content": card_def["content"],
                    "seen_at": r["seen_at"],
                })
        return {"cards": cards}
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
