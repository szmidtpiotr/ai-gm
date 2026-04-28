"""Phase 8D — Serwis konfiguracji flag lokalizacji z merge logiką session/global."""

import json
import sqlite3
from typing import Optional

from app.migrations_admin import DB_PATH


def _get_db_connection() -> sqlite3.Connection:
    """Zwraca połączenie do bazy danych."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_global_flag(key: str, default: str = "0") -> str:
    """Pobiera flagę globalną z game_config_meta."""
    conn = _get_db_connection()
    try:
        row = conn.execute(
            "SELECT value FROM game_config_meta WHERE key = ? LIMIT 1",
            (key,)
        ).fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def get_session_flag(session_id: int, key: str) -> Optional[str]:
    """Pobiera flagę per sesja z session_flags (JSON)."""
    conn = _get_db_connection()
    try:
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE id = ? LIMIT 1",
            (session_id,)
        ).fetchone()
        
        if not row or not row["session_flags"]:
            return None
        
        flags = json.loads(row["session_flags"])
        return flags.get(key)
    except (json.JSONDecodeError, sqlite3.Error):
        return None
    finally:
        conn.close()


def get_flag(key: str, session_id: Optional[int] = None, default: str = "0") -> str:
    """
    Pobiera flagę z merge logiką: session_flag ?? global_flag ?? default.
    
    Args:
        key: nazwa flagi (np. 'location_integrity_enabled')
        session_id: ID sesji (opcjonalnie)
        default: wartość domyślna jeśli flaga nie istnieje
    
    Returns:
        Wartość flagi jako string
    """
    # Najpierw spróbuj session_flag (jeśli podano session_id)
    if session_id is not None:
        session_value = get_session_flag(session_id, key)
        if session_value is not None:
            return session_value
    
    # Fallback na global_flag
    return get_global_flag(key, default)


def get_bool_flag(key: str, session_id: Optional[int] = None, default: bool = False) -> bool:
    """Pobiera flagę jako boolean."""
    value = get_flag(key, session_id, "1" if default else "0")
    return value.lower() in ("1", "true", "yes", "on")


def set_session_flag(session_id: int, key: str, value: str) -> bool:
    """
    Ustawia flagę per sesja w session_flags (JSON merge).
    
    Args:
        session_id: ID sesji
        key: nazwa flagi
        value: wartość flagi (string)
    
    Returns:
        True jeśli sukces, False jeśli błąd
    """
    conn = _get_db_connection()
    try:
        # Pobierz istniejące flagi
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE id = ? LIMIT 1",
            (session_id,)
        ).fetchone()
        
        if not row:
            return False  # Sesja nie istnieje
        
        # Parsuj istniejące flagi lub utwórz nowe
        flags = {}
        if row["session_flags"]:
            try:
                flags = json.loads(row["session_flags"])
            except json.JSONDecodeError:
                flags = {}
        
        # Ustaw nową flagę
        flags[key] = value
        
        # Zapisz z powrotem
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
            (json.dumps(flags, ensure_ascii=False), session_id)
        )
        conn.commit()
        return True
        
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def delete_session_flag(session_id: int, key: str) -> bool:
    """
    Usuwa flagę per sesja (przywraca wartość globalną).
    
    Args:
        session_id: ID sesji
        key: nazwa flagi do usunięcia
    
    Returns:
        True jeśli sukces, False jeśli błąd
    """
    conn = _get_db_connection()
    try:
        # Pobierz istniejące flagi
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE id = ? LIMIT 1",
            (session_id,)
        ).fetchone()
        
        if not row or not row["session_flags"]:
            return True  # Brak flag = sukces
        
        # Parsuj istniejące flagi
        try:
            flags = json.loads(row["session_flags"])
        except json.JSONDecodeError:
            return True  # Nieprawidłowy JSON = traktuj jako pusty
        
        # Usuń flagę jeśli istnieje
        if key in flags:
            del flags[key]
            
            # Zapisz z powrotem
            conn.execute(
                "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
                (json.dumps(flags, ensure_ascii=False) if flags else "{}", session_id)
            )
            conn.commit()
        
        return True
        
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def get_all_flags(session_id: Optional[int] = None) -> dict:
    """
    Pobiera wszystkie flagi lokalizacji z pełnym podziałem.
    
    Returns:
        {
            "effective_flags": {...},
            "session_overrides": {...} lub null,
            "global_defaults": {...}
        }
    """
    location_flags = [
        "location_integrity_enabled",
        "location_parser_json_enabled", 
        "location_parser_fallback_enabled"
    ]
    
    result = {
        "effective_flags": {},
        "session_overrides": None,
        "global_defaults": {}
    }
    
    # Pobierz globalne wartości
    for flag in location_flags:
        result["global_defaults"][flag] = get_global_flag(flag, "1")
        result["effective_flags"][flag] = get_flag(flag, session_id, "1")
    
    # Pobierz session overrides (jeśli podano session_id)
    if session_id is not None:
        overrides = {}
        for flag in location_flags:
            session_val = get_session_flag(session_id, flag)
            if session_val is not None:
                overrides[flag] = session_val
        
        if overrides:
            result["session_overrides"] = overrides
    
    return result
