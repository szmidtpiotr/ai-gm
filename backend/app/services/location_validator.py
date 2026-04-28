"""Phase 8D — Walidator spójności ruchu (fuzzy match + reguły przechodzenia)."""

import json
import sqlite3
from dataclasses import dataclass
from typing import Optional

from rapidfuzz import fuzz

from app.core.logging import get_logger
from app.migrations_admin import DB_PATH
from app.services.llm_service import generate_chat
from app.services.location_intent_parser import LocationIntent

logger = get_logger(__name__)

FUZZY_MATCH_THRESHOLD = 80  # Score >= 80% uznajemy za match


@dataclass
class ValidationResult:
    """Wynik walidacji ruchu."""
    allowed: bool
    resolved_location_id: Optional[int]
    is_new_location: bool
    block_reason: Optional[str]


def _get_db_connection() -> sqlite3.Connection:
    """Zwraca połączenie do bazy danych."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _get_location_by_id(location_id: int) -> Optional[dict]:
    """Pobiera lokalizację po ID."""
    conn = _get_db_connection()
    try:
        row = conn.execute(
            "SELECT * FROM game_locations WHERE id = ? AND is_active = 1",
            (location_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _get_location_by_key(key: str) -> Optional[dict]:
    """Pobiera lokalizację po kluczu."""
    conn = _get_db_connection()
    try:
        row = conn.execute(
            "SELECT * FROM game_locations WHERE key = ? AND is_active = 1",
            (key,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _find_all_locations() -> list[dict]:
    """Pobiera wszystkie aktywne lokalizacje."""
    conn = _get_db_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM game_locations WHERE is_active = 1 ORDER BY label"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _fuzzy_match_location(target_label: str, locations: list[dict]) -> Optional[dict]:
    """
    Fuzzy match po label — zwraca najlepszy match jeśli score >= threshold.
    
    Returns:
        Najlepsza pasująca lokalizacja lub None
    """
    best_match = None
    best_score = 0
    
    for loc in locations:
        score = fuzz.ratio(target_label.lower(), loc["label"].lower())
        if score > best_score and score >= FUZZY_MATCH_THRESHOLD:
            best_score = score
            best_match = loc
    
    return best_match


def _ask_llm_if_same_location(target_label: str, existing_label: str) -> bool:
    """
    Zapytaj LLM czy dwie nazwy to ta sama lokalizacja (fallback dla fuzzy match).
    
    Returns:
        True jeśli LLM potwierdzi że to ta sama lokalizacja
    """
    prompt = f"""Czy "{target_label}" i "{existing_label}" opisują tę samą lokalizację w świecie gry?

Odpowiedz TYLKO "TAK" lub "NIE"."""
    
    try:
        response = generate_chat(
            messages=[
                {"role": "system", "content": "Jesteż asystentem RPG. Odpowiadaj krótko TAK lub NIE."},
                {"role": "user", "content": prompt}
            ],
            model=None,
            llm_config=None
        )
        
        answer = (response or "").strip().upper()
        return answer.startswith("TAK")
        
    except Exception as e:
        logger.error("llm_same_location_check_error", error=str(e))
        return False


def _get_session_current_location(session_id: int) -> Optional[dict]:
    """Pobiera aktualną lokalizację sesji."""
    conn = _get_db_connection()
    try:
        row = conn.execute(
            """
            SELECT gl.* FROM game_locations gl
            JOIN game_sessions gs ON gs.current_location_id = gl.id
            WHERE gs.id = ? AND gl.is_active = 1
            """,
            (session_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _is_same_parent_sub_move(current_loc: dict, target_parent_id: Optional[int]) -> bool:
    """
    Sprawdza czy ruch Sub → Sub w obrębie tego samego parenta.
    
    Returns:
        True jeśli obie są 'sub' i mają tego samego parenta
    """
    if current_loc.get("location_type") != "sub":
        return False
    
    # Jeśli target to sub, sprawdź czy ten sam parent
    if target_parent_id is not None and current_loc.get("parent_id") == target_parent_id:
        return True
    
    return False


def _create_new_location(intent: LocationIntent) -> Optional[dict]:
    """
    Tworzy nową lokalizację (tylko gdy action='create').
    
    Returns:
        Utworzona lokalizacja lub None
    """
    if intent.action != "create":
        return None
    
    conn = _get_db_connection()
    try:
        # Sprawdź czy parent istnieje (jeśli podany)
        parent_id = None
        if intent.parent_key:
            parent = _get_location_by_key(intent.parent_key)
            if parent:
                parent_id = parent["id"]
        
        # Generuj klucz z label (slugify)
        import re
        key = re.sub(r'[^\w\s-]', '', intent.target_label.lower())
        key = re.sub(r'[-\s]+', '_', key)
        
        # Sprawdź czy klucz już istnieje
        existing = _get_location_by_key(key)
        if existing:
            # Dodaj timestamp do klucza
            key = f"{key}_{__import__('time').time()}"
        
        cursor = conn.execute(
            """
            INSERT INTO game_locations (key, label, description, parent_id, location_type)
            VALUES (?, ?, ?, ?, ?)
            """,
            (key, intent.target_label, intent.description, parent_id, "sub")
        )
        conn.commit()
        
        new_id = cursor.lastrowid
        return _get_location_by_id(new_id)
        
    except sqlite3.Error as e:
        logger.error("create_location_error", error=str(e))
        return None
    finally:
        conn.close()


def validate_move(session_id: int, intent: LocationIntent) -> ValidationResult:
    """
    Waliduje ruch zgodnie z regułami przechodzenia (D-LOC-04).
    
    Flow:
    1. Pobierz current_location_id sesji
    2. Fuzzy match po label (score >= 80)
    3. Jeśli score < 80 → zapytaj LLM
    4. Jeśli LLM mówi NIE → nowa lokalizacja (tylko jeśli action='create')
    5. Sprawdź reguły przechodzenia (Sub→Sub swobodne, Makro→Makro soft block)
    
    Args:
        session_id: ID sesji gracza
        intent: wykryta intencja ruchu
    
    Returns:
        ValidationResult z decyzją o ruchu
    """
    try:
        # Pobierz aktualną lokalizację
        current_loc = _get_session_current_location(session_id)
        
        if not current_loc:
            # Brak aktualnej lokalizacji — dowolny ruch dozwolony (inicjalizacja)
            # Spróbuj znaleźć lub utworzyć lokalizację docelową
            all_locs = _find_all_locations()
            matched = _fuzzy_match_location(intent.target_label, all_locs)
            
            if matched:
                return ValidationResult(
                    allowed=True,
                    resolved_location_id=matched["id"],
                    is_new_location=False,
                    block_reason=None
                )
            
            # Utwórz nową jeśli action='create'
            if intent.action == "create":
                new_loc = _create_new_location(intent)
                if new_loc:
                    return ValidationResult(
                        allowed=True,
                        resolved_location_id=new_loc["id"],
                        is_new_location=True,
                        block_reason=None
                    )
            
            return ValidationResult(
                allowed=False,
                resolved_location_id=None,
                is_new_location=False,
                block_reason="Brak aktualnej lokalizacji i nie można utworzyć nowej"
            )
        
        # Fuzzy match po wszystkich lokalizacjach
        all_locs = _find_all_locations()
        matched = _fuzzy_match_location(intent.target_label, all_locs)
        
        if matched:
            # Sprawdź czy to ta sama (LLM potwierdzenie dla edge cases)
            if fuzz.ratio(intent.target_label.lower(), matched["label"].lower()) < 95:
                # Niedokładny match — zapytaj LLM
                if not _ask_llm_if_same_location(intent.target_label, matched["label"]):
                    # LLM mówi że to inne miejsce
                    matched = None
        
        if not matched:
            # Nie znaleziono — próba utworzenia nowej (tylko z action='create')
            if intent.action == "create":
                new_loc = _create_new_location(intent)
                if new_loc:
                    return ValidationResult(
                        allowed=True,
                        resolved_location_id=new_loc["id"],
                        is_new_location=True,
                        block_reason=None
                    )
            
            return ValidationResult(
                allowed=False,
                resolved_location_id=None,
                is_new_location=False,
                block_reason=f"Nieznana lokalizacja: {intent.target_label}. Użyj action='create' lub wybierz istniejącą."
            )
        
        # Mamy match — sprawdź reguły przechodzenia
        target_loc = matched
        
        # Sub → Sub (ten sam parent): swobodne
        if _is_same_parent_sub_move(current_loc, target_loc.get("parent_id")):
            return ValidationResult(
                allowed=True,
                resolved_location_id=target_loc["id"],
                is_new_location=False,
                block_reason=None
            )
        
        # Makro → Makro (lub Sub → Sub różny parent): soft block
        # GM powinien wygenerować narrację podróży
        if current_loc.get("location_type") == "macro" or target_loc.get("location_type") == "macro":
            # Dozwolone, ale z zaleceniem narracji podróży
            logger.info("macro_move_soft_block", 
                       from_loc=current_loc["label"],
                       to_loc=target_loc["label"])
            # Still allowed — backend nie blokuje, liczy na GM narration
            return ValidationResult(
                allowed=True,
                resolved_location_id=target_loc["id"],
                is_new_location=False,
                block_reason=None  # Soft block — nie twarda blokada
            )
        
        # Sub → Sub (różni parent): traktowane jak Makro → Makro
        return ValidationResult(
            allowed=True,
            resolved_location_id=target_loc["id"],
            is_new_location=False,
            block_reason=None
        )
        
    except Exception as e:
        logger.error("location_validation_error", error=str(e), session_id=session_id)
        return ValidationResult(
            allowed=False,
            resolved_location_id=None,
            is_new_location=False,
            block_reason=f"Błąd walidacji: {str(e)}"
        )


def log_integrity_violation(session_id: int, intent: LocationIntent, reason: str) -> None:
    """Loguje próbę niespójnej zmiany lokalizacji."""
    conn = _get_db_connection()
    try:
        # Pobierz character_id z sesji (jeśli istnieje)
        row = conn.execute(
            "SELECT campaign_id FROM game_sessions WHERE id = ?",
            (session_id,)
        ).fetchone()
        
        character_id = None  # TODO: rozwiązanie pobierania character_id z sesji
        
        conn.execute(
            """
            INSERT INTO location_integrity_log 
                (session_id, character_id, attempted_move, reason_blocked)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, character_id, intent.target_label, reason)
        )
        conn.commit()
        
        logger.warning("location_integrity_violation_logged",
                      session_id=session_id,
                      attempted_move=intent.target_label,
                      reason=reason)
    except sqlite3.Error as e:
        logger.error("log_integrity_violation_error", error=str(e))
    finally:
        conn.close()
