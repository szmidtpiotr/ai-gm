"""Encounter Forge Router — autoring AI encounterów w Kuźni (PT-D4b #1131).

Trzy endpointy nad kanonicznym katalogiem `game_config_encounters` (pod-task A #1130):
- GET  /api/admin/forge/encounters/schema?kind=combat|social — pola formularza + dozwolone enumy FK
- POST /api/admin/forge/encounters/generate — LLM wypełnia JSON wg schematu (FK-enum, batch)
- POST /api/admin/forge/encounters/save — walidacja FK + DC/gold → INSERT do katalogu

Anty-halucynacja: AI dostaje dozwolone klucze jako enum i tylko wybiera; zapis z
wymyślonym kluczem → 400. Reużywa auth + DB helper z adventure_forge.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.routers.adventure_forge import _get_db, _require_admin
from app.services import encounter_catalog_service as cat

router = APIRouter(prefix="/api/admin/forge/encounters", tags=["admin-encounter-forge"])


def _check_kind(kind: str) -> None:
    if kind not in ("combat", "social"):
        raise HTTPException(status_code=400, detail="kind musi być 'combat' lub 'social'")


@router.get("/schema")
def encounter_schema(kind: str = Query(...), _: None = Depends(_require_admin)):
    """Pola formularza + dozwolone enumy (enemy_key / skill / npc_key) dla danego kind."""
    _check_kind(kind)
    conn = _get_db()
    try:
        cat.ensure_catalog_schema(conn)
        return cat.build_schema(conn, kind)
    finally:
        conn.close()


@router.get("/catalog")
def encounter_catalog_list(
    kind: Optional[str] = Query(None),
    biome: Optional[str] = Query(None),
    subtype: Optional[str] = Query(None),
    _: None = Depends(_require_admin),
):
    """Lista rekordów katalogu dla panelu (filtr kind/biome/subtype)."""
    if kind:  # pusty string / None = bez filtra kind
        _check_kind(kind)
    conn = _get_db()
    try:
        cat.ensure_catalog_schema(conn)
        rows = cat.list_catalog(conn, kind=kind, biome=biome, subtype=subtype)
        return {"ok": True, "count": len(rows), "encounters": rows}
    finally:
        conn.close()


@router.delete("/catalog/{key}")
def encounter_catalog_delete(key: str, _: None = Depends(_require_admin)):
    """Usuń rekord katalogu po kluczu. Nieistniejący → 404."""
    conn = _get_db()
    try:
        cat.ensure_catalog_schema(conn)
        if not cat.delete_encounter(conn, key):
            raise HTTPException(status_code=404, detail=f"encounter '{key}' nie istnieje")
        return {"ok": True, "key": key}
    finally:
        conn.close()


class GenerateReq(BaseModel):
    kind: str
    count: int = 1
    biome: Optional[str] = None
    subtype: Optional[str] = None
    level: Optional[int] = None


@router.post("/generate")
def encounter_generate(req: GenerateReq, _: None = Depends(_require_admin)):
    """LLM generuje N draftów (FK-enum). Zwraca listę draftów status='pending' do akceptacji."""
    _check_kind(req.kind)
    conn = _get_db()
    try:
        cat.ensure_catalog_schema(conn)
        drafts = cat.generate_encounter_drafts(
            conn, req.kind, req.count,
            biome=req.biome, subtype=req.subtype, level=req.level,
        )
        return {"ok": True, "count": len(drafts), "drafts": drafts}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


class SaveReq(BaseModel):
    draft: dict


@router.post("/save")
def encounter_save(req: SaveReq, _: None = Depends(_require_admin)):
    """Waliduj FK + DC/gold i zapisz draft do katalogu. Wymyślony klucz FK → 400."""
    conn = _get_db()
    try:
        cat.ensure_catalog_schema(conn)
        key = cat.save_encounter_from_draft(conn, req.draft)
        return {"ok": True, "key": key}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()
