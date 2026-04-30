"""Phase 8D — Endpointy do zarządzania lokalizacją sesji."""

import sqlite3

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.core.logging import get_logger
from app.migrations_admin import DB_PATH
from app.services.admin_auth import verify_admin_token
from app.services.location_config_service import get_bool_flag
from app.services.location_intent_parser import LocationIntent, parse
from app.services.location_validator import ValidationResult, log_integrity_violation, validate_move
from app.services.location_context_injector import build_location_context

logger = get_logger(__name__)
router = APIRouter(tags=["Session Location"])


class LocationUpdateRequest(BaseModel):
    """Request body dla aktualizacji lokalizacji sesji."""
    location_key: str


class LocationUpdateResponse(BaseModel):
    """Response po aktualizacji lokalizacji."""
    success: bool
    location_id: int
    location_label: str
    previous_location_id: int | None
    is_new_location: bool = False


def _get_db_connection() -> sqlite3.Connection:
    """Zwraca połączenie do bazy danych."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def require_admin_token(authorization: str | None = Header(default=None)) -> None:
    """Dependency weryfikująca admin token z header Authorization."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    token = authorization.removeprefix("Bearer ").strip()
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Invalid admin token")


@router.patch("/api/session/{session_id}/location", response_model=LocationUpdateResponse)
async def update_session_location(
    session_id: int,
    req: LocationUpdateRequest,
    _admin: None = Depends(require_admin_token),
):
    """
    Aktualizuje lokalizację sesji (wewnętrzny endpoint po walidacji).
    
    Args:
        session_id: ID sesji
        location_key: klucz lokalizacji docelowej
    
    Returns:
        Szczegóły aktualizacji
    
    Raises:
        404: Lokalizacja nie istnieje lub sesja nie istnieje
        401: Brak autoryzacji
    """
    conn = _get_db_connection()
    try:
        # Sprawdź czy sesja istnieje
        session_row = conn.execute(
            "SELECT id, current_location_id FROM game_sessions WHERE id = ?",
            (session_id,)
        ).fetchone()
        
        if not session_row:
            raise HTTPException(status_code=404, detail=f"Sesja {session_id} nie istnieje")
        
        previous_location_id = session_row["current_location_id"]
        
        # Pobierz lokalizację docelową
        loc_row = conn.execute(
            "SELECT id, label FROM game_locations WHERE key = ? AND is_active = 1",
            (req.location_key,)
        ).fetchone()
        
        if not loc_row:
            raise HTTPException(
                status_code=404, 
                detail=f"Lokalizacja '{req.location_key}' nie istnieje lub jest nieaktywna"
            )
        
        # Aktualizuj sesję
        conn.execute(
            """
            UPDATE game_sessions 
            SET current_location_id = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (loc_row["id"], session_id)
        )
        conn.commit()
        
        logger.info("session_location_updated",
                   session_id=session_id,
                   previous_location_id=previous_location_id,
                   new_location_id=loc_row["id"],
                   location_key=req.location_key)
        
        return LocationUpdateResponse(
            success=True,
            location_id=loc_row["id"],
            location_label=loc_row["label"],
            previous_location_id=previous_location_id,
            is_new_location=False
        )
        
    except sqlite3.Error as e:
        logger.error("update_session_location_db_error", error=str(e), session_id=session_id)
        raise HTTPException(status_code=500, detail=f"Błąd bazy danych: {str(e)}")
    finally:
        conn.close()


@router.get("/api/session/{session_id}/location")
async def get_session_location(
    session_id: int,
    _admin: None = Depends(require_admin_token),
):
    """
    Zwraca aktualną lokalizację sesji z kontekstem.
    
    Args:
        session_id: ID sesji
    
    Returns:
        Szczegóły lokalizacji lub 404 jeśli brak
    """
    conn = _get_db_connection()
    try:
        row = conn.execute(
            """
            SELECT gl.*, gs.session_flags 
            FROM game_sessions gs
            LEFT JOIN game_locations gl ON gs.current_location_id = gl.id
            WHERE gs.id = ?
            """,
            (session_id,)
        ).fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Sesja {session_id} nie istnieje")
        
        if not row["current_location_id"]:
            raise HTTPException(status_code=404, detail="Sesja nie ma przypisanej lokalizacji")
        
        location = dict(row)
        location["context_text"] = build_location_context(session_id)
        
        return location
        
    finally:
        conn.close()


@router.post("/api/session/{session_id}/validate-move")
async def validate_session_move(
    session_id: int,
    intent: LocationIntent,
    _admin: None = Depends(require_admin_token),
):
    """
    Waliduje ruch do nowej lokalizacji bez wykonywania (dry-run).
    
    Używany przez handler /move do sprawdzenia przed wykonaniem.
    
    Args:
        session_id: ID sesji
        intent: intencja ruchu
    
    Returns:
        Wynik walidacji (allowed, reason, suggested_location_id)
    """
    result = validate_move(session_id, intent)
    
    return {
        "allowed": result.allowed,
        "resolved_location_id": result.resolved_location_id,
        "is_new_location": result.is_new_location,
        "block_reason": result.block_reason
    }


