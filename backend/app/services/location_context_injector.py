"""Phase 8D — Injector kontekstu lokalizacji do system promptu GM."""

import sqlite3
from typing import Optional

from app.core.logging import get_logger
from app.migrations_admin import DB_PATH

logger = get_logger(__name__)


def _get_db_connection() -> sqlite3.Connection:
    """Zwraca połączenie do bazy danych."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _get_location_with_parent(location_id: int) -> Optional[dict]:
    """Pobiera lokalizację wraz z parentem."""
    conn = _get_db_connection()
    try:
        # Pobierz lokalizację
        loc_row = conn.execute(
            "SELECT * FROM game_locations WHERE id = ? AND is_active = 1",
            (location_id,)
        ).fetchone()
        
        if not loc_row:
            return None
        
        loc = dict(loc_row)
        
        # Pobierz parenta jeśli istnieje
        if loc.get("parent_id"):
            parent_row = conn.execute(
                "SELECT key, label FROM game_locations WHERE id = ? AND is_active = 1",
                (loc["parent_id"],)
            ).fetchone()
            if parent_row:
                loc["parent"] = dict(parent_row)
        
        # Pobierz sąsiednie lokalizacje (dzieci tego samego parenta lub dzieci tej lokalizacji)
        neighbors = []
        
        if loc.get("parent_id"):
            # Siblings (inne sub-lokalizacje tego samego makro)
            siblings = conn.execute(
                """
                SELECT key, label FROM game_locations 
                WHERE parent_id = ? AND id != ? AND is_active = 1
                ORDER BY label
                """,
                (loc["parent_id"], location_id)
            ).fetchall()
            neighbors.extend([dict(s) for s in siblings])
        
        # Dzieci tej lokalizacji (jeśli makro)
        children = conn.execute(
            """
            SELECT key, label FROM game_locations 
            WHERE parent_id = ? AND is_active = 1
            ORDER BY label
            """,
            (location_id,)
        ).fetchall()
        neighbors.extend([dict(c) for c in children])
        
        loc["neighbors"] = neighbors[:5]  # Max 5 sąsiadów
        
        return loc
        
    finally:
        conn.close()


def build_location_context(session_id: int) -> str:
    """
    Buduje blok kontekstu lokalizacji do wstrzyknięcia w system prompt.
    
    Format:
    [KONTEKST LOKALIZACJI — nie zmieniaj bez uzasadnienia]
    Aktualna lokalizacja: Karczma Pod Wisielcem (sub, rodzic: Miasto Varen)
    Opis: Stara karczma przy bramie wschodniej. Głośna, zadymiona.
    Zasady specjalne: brak walki na terenie lokalu.
    Możliwe sąsiednie lokalizacje: Rynek Główny, Stajnia, Brama Południowa
    
    Args:
        session_id: ID sesji gracza
    
    Returns:
        Blok tekstowy kontekstu lub pusty string jeśli brak lokalizacji
    """
    try:
        conn = _get_db_connection()
        try:
            # Pobierz current_location_id z sesji
            row = conn.execute(
                "SELECT current_location_id FROM game_sessions WHERE id = ?",
                (session_id,)
            ).fetchone()
            
            if not row or not row["current_location_id"]:
                return ""  # Brak lokalizacji — brak wstrzyknięcia
            
            location_id = row["current_location_id"]
            
        finally:
            conn.close()
        
        # Pobierz szczegóły lokalizacji
        loc = _get_location_with_parent(location_id)
        if not loc:
            return ""
        
        # Zbuduj kontekst
        lines = ["[KONTEKST LOKALIZACJI — nie zmieniaj bez uzasadnienia]"]
        
        # Aktualna lokalizacja
        loc_type = loc.get("location_type", "unknown")
        parent_info = ""
        if loc.get("parent"):
            parent_info = f", rodzic: {loc['parent']['label']}"
        
        lines.append(f"Aktualna lokalizacja: {loc['label']} ({loc_type}{parent_info})")
        
        # Opis
        if loc.get("description"):
            lines.append(f"Opis: {loc['description']}")
        
        # Zasady specjalne
        if loc.get("rules"):
            try:
                import json
                rules = json.loads(loc["rules"])
                if isinstance(rules, dict):
                    rules_text = ", ".join([f"{k}: {v}" for k, v in rules.items()])
                    lines.append(f"Zasady specjalne: {rules_text}")
                else:
                    lines.append(f"Zasady specjalne: {loc['rules']}")
            except json.JSONDecodeError:
                lines.append(f"Zasady specjalne: {loc['rules']}")
        
        # Sąsiednie lokalizacje
        if loc.get("neighbors"):
            neighbor_names = [n["label"] for n in loc["neighbors"]]
            lines.append(f"Możliwe sąsiednie lokalizacje: {', '.join(neighbor_names)}")
        
        # NPC i wrogowie (opcjonalnie)
        if loc.get("npc_keys"):
            try:
                import json
                npcs = json.loads(loc["npc_keys"]) if loc["npc_keys"].startswith("[") else []
                if npcs:
                    lines.append(f"Obecni NPC: {', '.join(npcs)}")
            except json.JSONDecodeError:
                pass
        
        lines.append("")  # Pusta linia na końcu
        
        return "\n".join(lines)
        
    except Exception as e:
        logger.error("build_location_context_error", error=str(e), session_id=session_id)
        return ""  # Błąd — brak wstrzyknięcia, gra kontynuuje


def inject_into_system_prompt(base_prompt: str, session_id: int) -> str:
    """
    Wstrzykuje kontekst lokalizacji na początek system promptu.
    
    Args:
        base_prompt: oryginalny system prompt
        session_id: ID sesji
    
    Returns:
        System prompt z wstrzykniętym kontekstem
    """
    location_context = build_location_context(session_id)
    
    if not location_context:
        return base_prompt
    
    # Wstrzyknięcie na początek (przed główną treścią)
    return location_context + "\n\n" + base_prompt
