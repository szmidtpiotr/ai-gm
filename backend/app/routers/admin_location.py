"""Phase 8D — Admin endpointy dla Location Integrity (flagi i logi)."""

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from app.core.logging import get_logger
from app.migrations_admin import DB_PATH
from app.services.admin_auth import verify_admin_token
from app.services.location_config_service import (
    get_all_flags,
    get_bool_flag,
    set_session_flag,
    delete_session_flag,
)

logger = get_logger(__name__)
router = APIRouter(tags=["Admin Location Integrity"])


# ============================================================================
# Pydantic Models
# ============================================================================

class FlagsPatchRequest(BaseModel):
    """Request body dla aktualizacji flag sesji."""
    location_integrity_enabled: Optional[int] = None
    location_auto_create_enabled: Optional[int] = None
    location_parser_json_enabled: Optional[int] = None
    location_parser_fallback_enabled: Optional[int] = None


class FlagsResponse(BaseModel):
    """Response z flagami."""
    session_id: int
    effective_flags: dict
    session_overrides: Optional[dict]
    global_defaults: dict


class LocationLogEntry(BaseModel):
    """Pojedynczy wpis logu."""
    id: int
    session_id: int
    character_id: Optional[int]
    attempted_move: str
    current_location_key: Optional[str]
    reason_blocked: str
    created_at: str


class CampaignSessionLocationPatch(BaseModel):
    """PATCH body dla LOC-4 — ustawienie current_location_id sesji kampanii."""
    location_id: Optional[int] = None


# ============================================================================
# Dependencies
# ============================================================================

def require_admin_token(authorization: str | None = Header(default=None)) -> None:
    """Dependency weryfikująca admin token z header Authorization."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    token = authorization.removeprefix("Bearer ").strip()
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Invalid admin token")


def _get_db_connection() -> sqlite3.Connection:
    """Zwraca połączenie do bazy danych."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================================
# Endpointy flag globalnych (game_config_meta)
# ============================================================================

@router.get("/api/admin/config/location-flags")
async def get_global_location_flags(
    _admin: None = Depends(require_admin_token),
):
    """
    Zwraca globalne wartości domyślne flag Location Integrity z game_config_meta.
    """
    conn = _get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT key, value FROM game_config_meta
            WHERE key IN (
                'location_integrity_enabled',
                'location_auto_create_enabled',
                'location_parser_json_enabled',
                'location_parser_fallback_enabled'
            )
            """
        ).fetchall()
        
        flags = {
            "location_integrity_enabled": True,
            "location_auto_create_enabled": True,
            "location_parser_json_enabled": True,
            "location_parser_fallback_enabled": True,
        }
        
        for row in rows:
            key = row["key"]
            value = row["value"]
            # Parse as boolean (1/0/true/false)
            flags[key] = value in ("1", "true", "True", "TRUE", True, 1)
        
        return flags
        
    except sqlite3.Error as e:
        logger.error("get_global_flags_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Błąd bazy danych: {str(e)}")
    finally:
        conn.close()


@router.put("/api/admin/config/location-flags")
async def update_global_location_flags(
    req: FlagsPatchRequest,
    _admin: None = Depends(require_admin_token),
):
    """
    Aktualizuje globalne wartości domyślne flag w game_config_meta.
    
    Tylko flagi przekazane w body są modyfikowane.
    """
    conn = _get_db_connection()
    try:
        updated = []
        for flag_name in [
            "location_integrity_enabled",
            "location_auto_create_enabled",
            "location_parser_json_enabled",
            "location_parser_fallback_enabled",
        ]:
            value = getattr(req, flag_name)
            if value is not None:
                str_value = "1" if value else "0"
                conn.execute(
                    """
                    INSERT INTO game_config_meta (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (flag_name, str_value)
                )
                updated.append(flag_name)
        
        conn.commit()
        logger.info("global_location_flags_updated", flags=updated)
        
        # Return current state
        return await get_global_location_flags(_admin)
        
    except sqlite3.Error as e:
        logger.error("update_global_flags_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Błąd bazy danych: {str(e)}")
    finally:
        conn.close()


# ============================================================================
# Endpointy flag sesyjnych
# ============================================================================

@router.get("/api/admin/session/{session_id}/flags", response_model=FlagsResponse)
async def get_session_flags(
    session_id: int,
    _admin: None = Depends(require_admin_token),
):
    """
    Zwraca effective flags dla sesji z podziałem na źródła.
    
    - effective_flags: wartości po merge (session ?? global ?? default)
    - session_overrides: tylko flagi nadpisane dla tej sesji (lub null)
    - global_defaults: wartości globalne z game_config_meta
    """
    # Sprawdź czy sesja istnieje
    conn = _get_db_connection()
    try:
        row = conn.execute(
            "SELECT id FROM game_sessions WHERE id = ? LIMIT 1",
            (session_id,)
        ).fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Sesja {session_id} nie istnieje")
    finally:
        conn.close()
    
    flags_data = get_all_flags(session_id)
    
    return FlagsResponse(
        session_id=session_id,
        **flags_data
    )


@router.patch("/api/admin/session/{session_id}/flags")
async def patch_session_flags(
    session_id: int,
    req: FlagsPatchRequest,
    _admin: None = Depends(require_admin_token),
):
    """
    Nadpisuje wybrane flagi dla sesji.
    
    Tylko flagi przekazane w body są modyfikowane (merge, nie full replace).
    Aby usunąć nadpisanie i wrócić do globala — użyj DELETE.
    """
    # Sprawdź czy sesja istnieje
    conn = _get_db_connection()
    try:
        row = conn.execute(
            "SELECT id FROM game_sessions WHERE id = ? LIMIT 1",
            (session_id,)
        ).fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Sesja {session_id} nie istnieje")
    finally:
        conn.close()
    
    updated_flags = []
    
    # Aktualizuj tylko przekazane flagi
    for flag_name in ["location_integrity_enabled", "location_parser_json_enabled", "location_parser_fallback_enabled"]:
        value = getattr(req, flag_name)
        if value is not None:
            success = set_session_flag(session_id, flag_name, str(value))
            if not success:
                raise HTTPException(status_code=500, detail=f"Błąd zapisu flagi {flag_name}")
            updated_flags.append(flag_name)
    
    logger.info("session_flags_updated", session_id=session_id, flags=updated_flags)
    
    # Zwróć aktualny stan
    flags_data = get_all_flags(session_id)
    return {
        "success": True,
        "updated_flags": updated_flags,
        "current_state": flags_data
    }


@router.delete("/api/admin/session/{session_id}/flags/{flag_key}")
async def delete_session_flag_endpoint(
    session_id: int,
    flag_key: str,
    _admin: None = Depends(require_admin_token),
):
    """
    Usuwa nadpisanie flagi dla sesji (przywraca wartość globalną).
    
    Args:
        flag_key: nazwa flagi do usunięcia (np. 'location_integrity_enabled')
    """
    # Sprawdź czy sesja istnieje
    conn = _get_db_connection()
    try:
        row = conn.execute(
            "SELECT id FROM game_sessions WHERE id = ? LIMIT 1",
            (session_id,)
        ).fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Sesja {session_id} nie istnieje")
    finally:
        conn.close()
    
    # Sprawdź czy flaga jest prawidłowa
    valid_flags = ["location_integrity_enabled", "location_parser_json_enabled", "location_parser_fallback_enabled"]
    if flag_key not in valid_flags:
        raise HTTPException(status_code=400, detail=f"Nieprawidłowa nazwa flagi. Dozwolone: {valid_flags}")
    
    success = delete_session_flag(session_id, flag_key)
    
    if not success:
        raise HTTPException(status_code=500, detail=f"Błąd usuwania flagi {flag_key}")
    
    logger.info("session_flag_deleted", session_id=session_id, flag=flag_key)
    
    # Zwróć aktualny stan
    flags_data = get_all_flags(session_id)
    return {
        "success": True,
        "deleted_flag": flag_key,
        "current_state": flags_data
    }


# ============================================================================
# Endpointy zatwierdzania lokalizacji AI
# ============================================================================

@router.get("/api/admin/locations/stats")
async def location_stats(
    _admin: None = Depends(require_admin_token),
):
    """Stage 2B-Schema S19 — telemetry: counts by created_by + canonical share."""
    conn = _get_db_connection()
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM game_locations WHERE is_active = 1"
        ).fetchone()[0]
        seed = conn.execute(
            "SELECT COUNT(*) FROM game_locations WHERE is_active = 1 AND created_by = 'seed'"
        ).fetchone()[0]
        admin_count = conn.execute(
            "SELECT COUNT(*) FROM game_locations WHERE is_active = 1 AND created_by = 'admin'"
        ).fetchone()[0]
        gm_runtime = conn.execute(
            "SELECT COUNT(*) FROM game_locations WHERE is_active = 1 AND created_by = 'gm_runtime'"
        ).fetchone()[0]
        canonical = conn.execute(
            "SELECT COUNT(*) FROM game_locations WHERE is_active = 1 AND canonical = 1"
        ).fetchone()[0]
        return {
            "total": total,
            "seed_count": seed,
            "admin_count": admin_count,
            "gm_runtime_count": gm_runtime,
            "canonical_count": canonical,
            "gm_runtime_share": round(gm_runtime / total, 3) if total else 0.0,
        }
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# R9 (#1249): pending-locations approve/reject flow removed — superseded by the
# world_review.py implementation (POST /api/admin/world/review/{type}/{key}) which
# the active admin UI (world.js / map.js) actually calls. No frontend consumer.


class SafeForRestPatch(BaseModel):
    """PATCH body — value=true → marks location safe_for_rest; false → unsets."""
    value: bool


@router.get("/api/admin/hex-safe/{q}/{r}")
async def get_hex_safe_for_rest(
    q: int,
    r: int,
    _admin: None = Depends(require_admin_token),
):
    """Stage 2B R2 — admin diagnostic: resolve safe-for-rest for hex (q, r).
    Returns the inheritance chain + reasoning so admins can debug without SQL."""
    from app.services.rest_service import hex_is_safe_for_rest

    conn = _get_db_connection()
    try:
        return hex_is_safe_for_rest(q, r, conn=conn)
    finally:
        conn.close()


@router.patch("/api/admin/locations/{location_key}/safe-for-rest")
async def set_location_safe_for_rest_endpoint(
    location_key: str,
    body: SafeForRestPatch,
    _admin: None = Depends(require_admin_token),
):
    """Stage 2B R1 — admin/dev toggle for safe_for_rest on a location.
    Mirrors the [SET_SAFE_FOR_REST:key:on|off] LLM tag path."""
    from app.services.world_service import set_location_safe_for_rest

    conn = _get_db_connection()
    try:
        change = set_location_safe_for_rest(conn, location_key, 1 if body.value else 0, source="admin")
        if not change:
            raise HTTPException(status_code=404, detail=f"Lokalizacja '{location_key}' nie istnieje")
        return {"status": "ok", **change}
    finally:
        conn.close()


# R9 (#1249): reject_location removed alongside the pending flow above.


# ============================================================================
# Endpointy logów
# ============================================================================

@router.get("/api/admin/session/{session_id}/location-log")
async def get_session_location_log(
    session_id: int,
    limit: int = Query(default=50, ge=1, le=500),
    since: Optional[str] = Query(default=None, description="Filtr daty ISO format (2026-04-25T00:00:00)"),
    _admin: None = Depends(require_admin_token),
):
    """
    Zwraca logi blokad lokalizacji dla konkretnej sesji.
    
    Query params:
    - limit: max liczba wpisów (1-500, default: 50)
    - since: opcjonalny filtr daty (ISO format)
    """
    conn = _get_db_connection()
    try:
        # Sprawdź czy sesja istnieje (opcjonalnie)
        session_row = conn.execute(
            "SELECT id FROM game_sessions WHERE id = ? LIMIT 1",
            (session_id,)
        ).fetchone()
        
        # Buduj query
        where_clauses = ["session_id = ?"]
        params = [session_id]
        
        if since:
            where_clauses.append("created_at >= ?")
            params.append(since)
        
        where_sql = " AND ".join(where_clauses)
        
        # Pobierz logi
        rows = conn.execute(
            f"""
            SELECT * FROM location_integrity_log
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params + [limit]
        ).fetchall()
        
        log_entries = []
        for row in rows:
            log_entries.append({
                "id": row["id"],
                "session_id": row["session_id"],
                "character_id": row["character_id"],
                "attempted_move": row["attempted_move"],
                "current_location_key": row["current_location_key"],
                "reason_blocked": row["reason_blocked"],
                "created_at": row["created_at"]
            })
        
        return {
            "session_id": session_id,
            "count": len(log_entries),
            "entries": log_entries
        }
        
    except sqlite3.Error as e:
        logger.error("get_location_log_error", error=str(e), session_id=session_id)
        raise HTTPException(status_code=500, detail=f"Błąd bazy danych: {str(e)}")
    finally:
        conn.close()


@router.get("/api/admin/location-log")
async def get_all_location_logs(
    limit: int = Query(default=50, ge=1, le=500),
    since: Optional[str] = Query(default=None, description="Filtr daty ISO format"),
    session_id: Optional[int] = Query(default=None, description="Opcjonalny filtr po session_id"),
    _admin: None = Depends(require_admin_token),
):
    """
    Zwraca logi blokad lokalizacji ze wszystkich sesji.
    
    Query params:
    - limit: max liczba wpisów (1-500, default: 50)
    - since: opcjonalny filtr daty (ISO format)
    - session_id: opcjonalny filtr po konkretnej sesji
    """
    conn = _get_db_connection()
    try:
        # Buduj query
        where_clauses = []
        params = []
        
        if session_id:
            where_clauses.append("session_id = ?")
            params.append(session_id)
        
        if since:
            where_clauses.append("created_at >= ?")
            params.append(since)
        
        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)
        
        # Pobierz logi
        query = f"""
            SELECT * FROM location_integrity_log
            {where_sql}
            ORDER BY created_at DESC
            LIMIT ?
        """
        
        rows = conn.execute(query, params + [limit]).fetchall()
        
        log_entries = []
        for row in rows:
            log_entries.append({
                "id": row["id"],
                "session_id": row["session_id"],
                "character_id": row["character_id"],
                "attempted_move": row["attempted_move"],
                "current_location_key": row["current_location_key"],
                "reason_blocked": row["reason_blocked"],
                "created_at": row["created_at"]
            })

        return {
            "count": len(log_entries),
            "entries": log_entries,
            "filters_applied": {
                "session_id": session_id,
                "since": since,
                "limit": limit,
            },
        }
        
    except sqlite3.Error as e:
        logger.error("get_all_location_logs_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Błąd bazy danych: {str(e)}")
    finally:
        conn.close()


# ----------------------------------------------------------------------------
# LOC-4 — kampania ↔ session current_location_id (panel admin)
# ----------------------------------------------------------------------------


def _campaign_session_location_payload(conn: sqlite3.Connection, campaign_id: int) -> dict:
    rows = conn.execute(
        """
        SELECT id, key, label, location_type,
               COALESCE(approved, 1) AS approved,
               COALESCE(is_active, 1) AS is_active
        FROM game_locations
        WHERE COALESCE(is_active, 1) = 1
        ORDER BY COALESCE(approved, 1) DESC, label COLLATE NOCASE
        """
    ).fetchall()
    locations = [
        {
            "id": int(r["id"]),
            "key": r["key"],
            "label": r["label"],
            "location_type": r["location_type"] or "macro",
            "approved": int(r["approved"] or 0),
        }
        for r in rows
    ]
    sess = conn.execute(
        """
        SELECT id, campaign_id, current_location_id FROM game_sessions
        WHERE campaign_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (campaign_id,),
    ).fetchone()

    current: dict | None = None
    current_location_id: int | None = None
    session_id_val: str | int | None = None
    if sess:
        session_id_val = sess["id"]
        current_location_id = (
            int(sess["current_location_id"]) if sess["current_location_id"] is not None else None
        )
        if current_location_id is not None:
            lr = conn.execute(
                """
                SELECT id, key, label, location_type,
                       COALESCE(approved, 1) AS approved
                FROM game_locations
                WHERE id = ? AND COALESCE(is_active, 1) = 1
                """,
                (current_location_id,),
            ).fetchone()
            if lr:
                current = {
                    "id": int(lr["id"]),
                    "key": lr["key"],
                    "label": lr["label"],
                    "location_type": lr["location_type"] or "macro",
                    "approved": int(lr["approved"] or 0),
                }
    return {
        "campaign_id": campaign_id,
        "session_id": session_id_val,
        "current_location_id": current_location_id,
        "current": current,
        "locations": locations,
    }


@router.get("/api/admin/campaigns/{campaign_id}/session-location")
async def get_campaign_session_location(
    campaign_id: int,
    _admin: None = Depends(require_admin_token),
):
    """
    LOC-4: stan sesji kampanii (current_location_id) + lista lokacji z katalogu (sort: approved).
    """
    conn = _get_db_connection()
    try:
        ok = conn.execute("SELECT id FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        if not ok:
            raise HTTPException(status_code=404, detail="Kampania nie istnieje")
        return _campaign_session_location_payload(conn, campaign_id)
    except HTTPException:
        raise
    except sqlite3.Error as e:
        logger.error("get_campaign_session_location_db_error", error=str(e), campaign_id=campaign_id)
        raise HTTPException(status_code=500, detail=f"Błąd bazy danych: {str(e)}")
    finally:
        conn.close()


@router.patch("/api/admin/campaigns/{campaign_id}/session-location")
async def patch_campaign_session_location(
    campaign_id: int,
    body: CampaignSessionLocationPatch,
    _admin: None = Depends(require_admin_token),
):
    """
    LOC-4: ustawia `game_sessions.current_location_id` dla ostatniej sesji kampanii;
    przy braku wiersza — INSERT z `id = str(campaign_id)`.
    `location_id: null` — reset (NULL).
    """
    conn = _get_db_connection()
    try:
        ok = conn.execute("SELECT id FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        if not ok:
            raise HTTPException(status_code=404, detail="Kampania nie istnieje")

        old_session = conn.execute(
            """
            SELECT id, current_location_id FROM game_sessions
            WHERE campaign_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (campaign_id,),
        ).fetchone()

        old_key: str | None = None
        if old_session and old_session["current_location_id"]:
            rk = conn.execute(
                "SELECT key FROM game_locations WHERE id = ?",
                (int(old_session["current_location_id"]),),
            ).fetchone()
            old_key = str(rk["key"]) if rk and rk["key"] else None

        new_loc_id: int | None = None
        new_key: str | None = None

        if body.location_id is not None:
            loc_row = conn.execute(
                """
                SELECT id, key FROM game_locations
                WHERE id = ? AND COALESCE(is_active, 1) = 1
                """,
                (int(body.location_id),),
            ).fetchone()
            if not loc_row:
                raise HTTPException(status_code=404, detail="Lokalizacja nie istnieje lub nieaktywna")
            new_loc_id = int(loc_row["id"])
            new_key = str(loc_row["key"]) if loc_row["key"] else None

        effective_session_for_log = str(old_session["id"]) if old_session else str(campaign_id)

        if old_session:
            conn.execute(
                """
                UPDATE game_sessions
                SET current_location_id = ?
                WHERE id = ?
                """,
                (new_loc_id, old_session["id"]),
            )
        else:
            conn.execute(
                """
                INSERT INTO game_sessions (id, campaign_id, current_location_id, session_flags)
                VALUES (?, ?, ?, '{}')
                """,
                (str(campaign_id), campaign_id, new_loc_id),
            )
            effective_session_for_log = str(campaign_id)
        conn.commit()

        logger.info(
            "admin_location_override",
            campaign_id=campaign_id,
            session_id=effective_session_for_log,
            old_location_key=old_key,
            new_location_key=new_key,
            new_location_id=new_loc_id,
        )

        return _campaign_session_location_payload(conn, campaign_id)
    except HTTPException:
        raise
    except sqlite3.Error as e:
        logger.error(
            "patch_campaign_session_location_db_error", error=str(e), campaign_id=campaign_id
        )
        raise HTTPException(status_code=500, detail=f"Błąd bazy danych: {str(e)}")
    finally:
        conn.close()


# ── World Builder endpoints (Phase 08 Task 40) ────────────────────────────

# R9 (#1249): world-builder graph endpoints removed — location position (Cytoscape)
# + location_connections CRUD had zero consumers (no frontend/admin/test caller).
# The active world map is hex-based (admin.py hex-map + hex_world.py); the legacy
# node-graph "World Builder" (Task 40) is not wired into the modular admin.


# ── U28 — Placement engine endpoints ─────────────────────────────────────────

@router.get("/api/admin/locations/floating")
async def get_floating_locations(_: None = Depends(require_admin_token)):
    """U28: Lista approved lokacji w stanie floating (niezakotwiczonych na hexach)."""
    from app.services.placement_engine import get_floating_locations as _get_floating
    conn = _get_db_connection()
    try:
        return _get_floating(conn)
    finally:
        conn.close()


class EditLocationBody(BaseModel):
    fields: dict


@router.patch("/api/admin/locations/{location_key}/edit")
async def edit_location_fields(
    location_key: str,
    body: EditLocationBody,
    _: None = Depends(require_admin_token),
):
    """#590: edit a pending/floating location's descriptive fields before approve/place."""
    from app.services.world_service import update_location_fields
    conn = _get_db_connection()
    try:
        exists = conn.execute(
            "SELECT key FROM game_locations WHERE key=? AND is_active=1", (location_key,)
        ).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Location not found")
        ok = update_location_fields(conn, location_key, body.fields or {})
        if not ok:
            raise HTTPException(status_code=400, detail="No editable fields provided")
        return {"ok": True, "key": location_key}
    finally:
        conn.close()


class PlaceLocationBody(BaseModel):
    q: int
    r: int


@router.post("/api/admin/locations/{location_key}/place")
async def place_location_on_hex(
    location_key: str,
    body: PlaceLocationBody,
    _: None = Depends(require_admin_token),
):
    """U28: Ręczne osadzenie floating lokacji na wskazanym hexie."""
    conn = _get_db_connection()
    try:
        loc = conn.execute(
            "SELECT key, placement FROM game_locations WHERE key=? AND is_active=1",
            (location_key,),
        ).fetchone()
        if not loc:
            raise HTTPException(status_code=404, detail="Location not found")
        if loc["placement"] == "placed":
            raise HTTPException(status_code=409, detail="Location already placed on a hex")
        hex_row = conn.execute(
            "SELECT q, r, location_key FROM world_hexes WHERE q=? AND r=? AND is_active=1",
            (body.q, body.r),
        ).fetchone()
        if not hex_row:
            raise HTTPException(status_code=404, detail="Hex not found")
        if hex_row["location_key"]:
            raise HTTPException(status_code=409, detail="Hex already has a location assigned")
        # #1243: single writer — hex canon + derived cache in one call.
        from app.services.hex_location_link import link_location_to_hex
        link_location_to_hex(conn, location_key, body.q, body.r)
        conn.commit()
        return {"ok": True, "key": location_key, "q": body.q, "r": body.r}
    finally:
        conn.close()
