"""Admin endpoints for the LOCATION duplicate detector (#1409).

Twin of admin_duplicates.py but for game_locations. Merge never touches
world_hexes (PIOTR-OWNED map) — see location_duplicate_service.

GET  /api/admin/location-duplicates        — scan (dup groups + garbage buckets)
GET  /api/admin/location-duplicates/count  — badge counter (excess exact dups)
POST /api/admin/location-duplicates/merge  — re-home children, delete losers
POST /api/admin/location-duplicates/ignore — «to nie duplikat»
GET  /api/admin/location-duplicates/ignores
DELETE /api/admin/location-duplicates/ignore/{ignore_id}
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.services.admin_auth import verify_admin_token
from app.services.duplicate_service import list_ignores, unignore
from app.services.location_duplicate_service import (
    count_location_duplicates,
    ignore_location_duplicates,
    merge_location_duplicates,
    scan_location_duplicates,
)
from app.core.db_runtime import resolve_db_path

DB_PATH = resolve_db_path()

router = APIRouter(prefix="/api/admin/location-duplicates", tags=["admin-location-duplicates"])


def _require_admin(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Invalid admin token")


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@router.get("")
def location_duplicates_scan(_: None = Depends(_require_admin)):
    conn = _get_db()
    try:
        return scan_location_duplicates(conn)
    finally:
        conn.close()


@router.get("/count")
def location_duplicates_count(_: None = Depends(_require_admin)):
    conn = _get_db()
    try:
        return {"count": count_location_duplicates(conn)}
    finally:
        conn.close()


class MergeReq(BaseModel):
    keep_key: str
    remove_keys: list[str]


@router.post("/merge")
def location_duplicates_merge(req: MergeReq, _: None = Depends(_require_admin)):
    conn = _get_db()
    try:
        return merge_location_duplicates(conn, req.keep_key, req.remove_keys)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        conn.close()


class IgnoreReq(BaseModel):
    keys: list[str]


@router.post("/ignore")
def location_duplicates_ignore(req: IgnoreReq, _: None = Depends(_require_admin)):
    conn = _get_db()
    try:
        return {"stored_pairs": ignore_location_duplicates(conn, req.keys)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        conn.close()


@router.get("/ignores")
def location_duplicates_ignores(_: None = Depends(_require_admin)):
    conn = _get_db()
    try:
        return {"ignores": [i for i in list_ignores(conn) if i["table_name"] == "locations"]}
    finally:
        conn.close()


@router.delete("/ignore/{ignore_id}")
def location_duplicates_unignore(ignore_id: int, _: None = Depends(_require_admin)):
    conn = _get_db()
    try:
        unignore(conn, ignore_id)
        return {"ok": True}
    finally:
        conn.close()
