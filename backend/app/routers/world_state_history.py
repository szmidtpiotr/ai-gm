"""B6 (#352) — Admin endpoints: World State history viewer.

GET /api/admin/campaigns/{campaign_id}/world-state
    → last 20 snapshots for campaign (newest first)

GET /api/admin/campaigns/{campaign_id}/world-state/latest
    → single latest snapshot or null
"""
from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, Header, HTTPException

DB_PATH = "/data/ai_gm.db"

from app.services.admin_auth import verify_admin_token

router = APIRouter()


# ── Auth dependency ────────────────────────────────────────────────────────────

def _require_admin(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing admin token")
    token = authorization.removeprefix("Bearer ").strip()
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Invalid admin token")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_snapshot_row(row: sqlite3.Row) -> dict:
    d = dict(row)
    raw = d.get("snapshot_json") or "{}"
    try:
        d["snapshot_json"] = json.loads(raw)
    except (ValueError, TypeError):
        d["snapshot_json"] = {}
    return d


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/admin/campaigns/{campaign_id}/world-state")
def get_world_state_history(
    campaign_id: int,
    _: None = Depends(_require_admin),
):
    """Return last 20 World State snapshots for a campaign (newest first)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, campaign_id, turn_number, snapshot_source, created_at, snapshot_json
            FROM world_state_snapshots
            WHERE campaign_id = ?
            ORDER BY id DESC
            LIMIT 20
            """,
            (campaign_id,),
        ).fetchall()
    finally:
        conn.close()

    snapshots = [_parse_snapshot_row(r) for r in rows]
    latest = snapshots[0] if snapshots else None
    return {"snapshots": snapshots, "latest": latest}


@router.get("/admin/campaigns/{campaign_id}/world-state/latest")
def get_world_state_latest(
    campaign_id: int,
    _: None = Depends(_require_admin),
):
    """Return the single most recent World State snapshot, or null."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT id, campaign_id, turn_number, snapshot_source, created_at, snapshot_json
            FROM world_state_snapshots
            WHERE campaign_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (campaign_id,),
        ).fetchone()
    finally:
        conn.close()

    snapshot = _parse_snapshot_row(row) if row else None
    return {"snapshot": snapshot}
