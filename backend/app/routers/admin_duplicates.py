"""Admin endpoints for the content duplicate detector (#1399).

GET  /api/admin/duplicates        — full scan (exact/fuzzy groups + cross-table)
GET  /api/admin/duplicates/count  — cheap badge counter (excess exact dups)
POST /api/admin/duplicates/merge  — merge a group: re-point refs, delete losers
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.services.admin_auth import verify_admin_token
from app.services.duplicate_service import (
    count_duplicates,
    ignore_duplicates,
    list_ignores,
    merge_duplicates,
    scan_duplicates,
    unignore,
)
from app.core.db_runtime import resolve_db_path

DB_PATH = resolve_db_path()

router = APIRouter(prefix="/api/admin/duplicates", tags=["admin-duplicates"])


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


class MergeReq(BaseModel):
    table: str
    keep_key: str
    remove_keys: list[str]


@router.get("")
def duplicates_scan(_: None = Depends(_require_admin)):
    conn = _get_db()
    try:
        return scan_duplicates(conn)
    finally:
        conn.close()


@router.get("/count")
def duplicates_count(_: None = Depends(_require_admin)):
    conn = _get_db()
    try:
        return {"count": count_duplicates(conn)}
    finally:
        conn.close()


@router.post("/merge")
def duplicates_merge(req: MergeReq, _: None = Depends(_require_admin)):
    conn = _get_db()
    try:
        return merge_duplicates(conn, req.table, req.keep_key, req.remove_keys)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        conn.close()


class IgnoreReq(BaseModel):
    table: str
    keys: list[str]


@router.post("/ignore")
def duplicates_ignore(req: IgnoreReq, _: None = Depends(_require_admin)):
    """#1401 — «to nie duplikat»: schowaj grupę/parę przy kolejnych skanach."""
    conn = _get_db()
    try:
        stored = ignore_duplicates(conn, req.table, req.keys)
        return {"stored_pairs": stored}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        conn.close()


@router.get("/ignores")
def duplicates_ignores(_: None = Depends(_require_admin)):
    conn = _get_db()
    try:
        return {"ignores": list_ignores(conn)}
    finally:
        conn.close()


@router.delete("/ignore/{ignore_id}")
def duplicates_unignore(ignore_id: int, _: None = Depends(_require_admin)):
    conn = _get_db()
    try:
        unignore(conn, ignore_id)
        return {"ok": True}
    finally:
        conn.close()
