"""#1193 — Admin API dla wydarzeń regionalnych ("żywy świat").

Świat → Wydarzenia: lista aktywnych eventów per region, ręczne wylosuj /
zakończ / dodaj, przełącznik auto-losowania przy day-ticku (domyślnie OFF).
Auth: własna warstwa Bearer (spójna z pozostałymi routerami /api/admin).
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Body, Depends, Header, HTTPException

from app.migrations_admin import DB_PATH
from app.services import world_event_service as wes
from app.services.admin_auth import verify_admin_token

router = APIRouter(prefix="/api/admin/world-events", tags=["admin-world-events"])


def _require_admin(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    if not verify_admin_token(authorization.removeprefix("Bearer ").strip()):
        raise HTTPException(status_code=403, detail="Invalid admin token")


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _known_regions(conn: sqlite3.Connection) -> list[str]:
    """Regiony z world_regions (jeśli tabela istnieje), inaczej domyślny."""
    try:
        rows = conn.execute(
            "SELECT key FROM world_regions WHERE COALESCE(is_active, 1) = 1 ORDER BY key"
        ).fetchall()
        keys = [r["key"] for r in rows if r["key"]]
        if keys:
            return keys
    except sqlite3.OperationalError:
        pass
    from app.services.reputation_service import REGION_DEFAULT
    return [REGION_DEFAULT]


@router.get("", dependencies=[Depends(_require_admin)])
def list_world_events(include_ended: bool = False):
    """Aktywne eventy (opcjonalnie z zakończonymi) + szablony + config + regiony."""
    conn = _conn()
    try:
        return {
            "events": wes.list_events(conn, include_ended=include_ended),
            "templates": wes.list_templates(conn, active_only=True),
            "regions": _known_regions(conn),
            "auto_roll": wes.is_auto_roll_enabled(),
            "daily_chance": wes._daily_chance(),
        }
    finally:
        conn.close()


@router.get("/templates", dependencies=[Depends(_require_admin)])
def list_event_templates():
    conn = _conn()
    try:
        return {"templates": wes.list_templates(conn, active_only=False)}
    finally:
        conn.close()


@router.post("", dependencies=[Depends(_require_admin)])
def add_world_event(payload: dict = Body(...)):
    """Ręczne uruchomienie eventu. Body: {region, template_key, duration_days?}."""
    region = (payload.get("region") or "").strip() or None
    template_key = (payload.get("template_key") or "").strip()
    duration_days = payload.get("duration_days")
    if not template_key:
        raise HTTPException(status_code=422, detail="template_key required")
    conn = _conn()
    try:
        try:
            ev = wes.start_event(conn, region, template_key, source="manual",
                                 duration_days=int(duration_days) if duration_days else None)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        conn.commit()
        return {"ok": True, "event": ev}
    finally:
        conn.close()


@router.post("/roll", dependencies=[Depends(_require_admin)])
def roll_world_event(payload: dict = Body(default={})):
    """Ręczne losowanie eventu dla regionu (ważone `weight`). Body: {region?}."""
    region = (payload.get("region") or "").strip() or None
    conn = _conn()
    try:
        ev = wes.roll_event(conn, region, source="random")
        conn.commit()
        if ev is None:
            return {"ok": False, "reason": "region_busy_or_no_templates"}
        return {"ok": True, "event": ev}
    finally:
        conn.close()


@router.patch("/{event_id}/end", dependencies=[Depends(_require_admin)])
def end_world_event(event_id: int):
    conn = _conn()
    try:
        changed = wes.end_event(conn, int(event_id))
        conn.commit()
        return {"ok": changed}
    finally:
        conn.close()


@router.post("/auto-roll", dependencies=[Depends(_require_admin)])
def set_auto_roll(payload: dict = Body(...)):
    """Przełącznik auto-losowania przy day-ticku. Body: {enabled: bool}."""
    enabled = bool(payload.get("enabled"))
    wes.set_auto_roll(enabled)
    return {"ok": True, "auto_roll": enabled}
