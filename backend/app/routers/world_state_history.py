"""B6 (#352) + F21 (#481) — Admin endpoints: World State history viewer.

GET /api/admin/campaigns/{campaign_id}/world-state
    → last 20 snapshots for campaign (newest first)

GET /api/admin/campaigns/{campaign_id}/world-state/latest
    → single latest snapshot or null

GET /api/admin/campaigns/{campaign_id}/world-state/diff?a=<snap_id>&b=<snap_id>
    → JSON diff between two snapshots: {added, removed, changed}
"""
from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.services.world_state_diff_service import compute_snapshot_diff
from app.core.db_runtime import resolve_db_path

DB_PATH = resolve_db_path()

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


@router.get("/admin/campaigns/{campaign_id}/world-state/diff")
def get_world_state_diff(
    campaign_id: int,
    a: int = Query(..., description="Older snapshot ID"),
    b: int = Query(..., description="Newer snapshot ID"),
    _: None = Depends(_require_admin),
):
    """Return diff between two snapshots. a=older, b=newer."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row_a = conn.execute(
            "SELECT id, turn_number, snapshot_source, created_at, snapshot_json FROM world_state_snapshots WHERE id = ? AND campaign_id = ?",
            (a, campaign_id),
        ).fetchone()
        row_b = conn.execute(
            "SELECT id, turn_number, snapshot_source, created_at, snapshot_json FROM world_state_snapshots WHERE id = ? AND campaign_id = ?",
            (b, campaign_id),
        ).fetchone()
    finally:
        conn.close()

    if not row_a:
        raise HTTPException(status_code=404, detail=f"Snapshot {a} not found for campaign {campaign_id}")
    if not row_b:
        raise HTTPException(status_code=404, detail=f"Snapshot {b} not found for campaign {campaign_id}")

    snap_a = json.loads(row_a["snapshot_json"] or "{}")
    snap_b = json.loads(row_b["snapshot_json"] or "{}")

    diff = compute_snapshot_diff(snap_a, snap_b)

    return {
        "campaign_id": campaign_id,
        "snap_a": {"id": row_a["id"], "turn_number": row_a["turn_number"], "created_at": row_a["created_at"]},
        "snap_b": {"id": row_b["id"], "turn_number": row_b["turn_number"], "created_at": row_b["created_at"]},
        "diff": diff,
    }
