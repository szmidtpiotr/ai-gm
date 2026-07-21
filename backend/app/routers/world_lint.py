"""#1527 (fala 4) — Kontrola świata: lint zamiast cichej samonaprawy.

Endpointy pod `/api/admin/world/lint` (auth: warstwa `/api/admin`, #1187):

* `GET  /api/admin/world/lint`          — lista wykrytych rozjazdów
* `GET  /api/admin/world/lint/count`    — sama liczba (badge w nawigacji)
* `POST /api/admin/world/lint/fix`      — napraw JEDEN rozjazd (`issue_id`)
* `GET  /api/admin/world/lint/history`  — kronika napraw (start + panel)
"""
import sqlite3

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.db_runtime import resolve_db_path
from app.services.world_lint_service import (
    LINT_LIST_LIMIT,
    fix_world_lint_issue,
    lint_history,
    lint_issue_count,
    run_world_lint,
)

router = APIRouter(prefix="/api/admin/world", tags=["admin-world-lint"])


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(resolve_db_path())
    conn.row_factory = sqlite3.Row
    return conn


class LintFixRequest(BaseModel):
    issue_id: str


@router.get("/lint")
def get_world_lint(limit: int = LINT_LIST_LIMIT):
    """Raport lintu świata dla zakładki 🩺 Kontrola świata."""
    conn = _get_db()
    try:
        return run_world_lint(conn, limit=max(1, min(int(limit), 1000)))
    finally:
        conn.close()


@router.get("/lint/count")
def get_world_lint_count():
    """Sama liczba rozjazdów — badge przy pozycji „Świat" w nawigacji."""
    conn = _get_db()
    try:
        return {"count": lint_issue_count(conn)}
    finally:
        conn.close()


@router.post("/lint/fix")
def post_world_lint_fix(payload: LintFixRequest):
    """Napraw jeden rozjazd. Reguły treściowe odmawiają (400) — nie zgadujemy."""
    conn = _get_db()
    try:
        result = fix_world_lint_issue(conn, payload.issue_id)
    finally:
        conn.close()
    if not result["fixed"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.get("/lint/history")
def get_world_lint_history(limit: int = 50):
    """Kronika napraw — co naprawił start backendu, co naprawił człowiek."""
    conn = _get_db()
    try:
        return {"entries": lint_history(conn, limit=max(1, min(int(limit), 500)))}
    finally:
        conn.close()
