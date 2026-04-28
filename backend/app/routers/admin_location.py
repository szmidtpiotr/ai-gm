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

@router.get("/api/admin/locations/pending")
async def get_pending_locations(
    _admin: None = Depends(require_admin_token),
):
    """Zwraca lokalizacje AI oczekujące na zatwierdzenie admina."""
    conn = _get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT child.*, parent.label AS parent_label, parent.key AS parent_key
            FROM game_locations child
            LEFT JOIN game_locations parent ON parent.id = child.parent_id
            WHERE COALESCE(child.ai_generated, 0) = 1
              AND COALESCE(child.approved, 1) = 0
              AND child.is_active = 1
            ORDER BY child.created_at DESC
            """
        ).fetchall()
        locations = [dict(row) for row in rows]
        return {"locations": locations, "count": len(locations)}
    except sqlite3.Error as e:
        logger.error("get_pending_locations_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Błąd bazy danych: {str(e)}")
    finally:
        conn.close()


@router.post("/api/admin/locations/{location_id}/approve")
async def approve_location(
    location_id: int,
    _admin: None = Depends(require_admin_token),
):
    """Zatwierdza lokalizację utworzoną automatycznie przez AI."""
    conn = _get_db_connection()
    try:
        cursor = conn.execute(
            """
            UPDATE game_locations
            SET approved = 1, updated_at = datetime('now')
            WHERE id = ? AND is_active = 1
            """,
            (location_id,),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Lokalizacja {location_id} nie istnieje")
        return {"status": "approved", "id": location_id}
    except sqlite3.Error as e:
        logger.error("approve_location_error", error=str(e), location_id=location_id)
        raise HTTPException(status_code=500, detail=f"Błąd bazy danych: {str(e)}")
    finally:
        conn.close()


@router.post("/api/admin/locations/{location_id}/reject")
async def reject_location(
    location_id: int,
    _admin: None = Depends(require_admin_token),
):
    """Odrzuca lokalizację AI przez soft delete."""
    conn = _get_db_connection()
    try:
        cursor = conn.execute(
            """
            UPDATE game_locations
            SET is_active = 0, updated_at = datetime('now')
            WHERE id = ?
            """,
            (location_id,),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Lokalizacja {location_id} nie istnieje")
        return {"status": "rejected", "id": location_id}
    except sqlite3.Error as e:
        logger.error("reject_location_error", error=str(e), location_id=location_id)
        raise HTTPException(status_code=500, detail=f"Błąd bazy danych: {str(e)}")
    finally:
        conn.close()


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
            "filters_applied": {
                "since": since,
                "session_id": session_id
            },
            "entries": log_entries
        }
        
    except sqlite3.Error as e:
        logger.error("get_all_location_logs_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Błąd bazy danych: {str(e)}")
    finally:
        conn.close()
