"""Phase 8D — Injector kontekstu lokalizacji do system promptu GM."""

import json
import sqlite3
from typing import Optional

from app.core.logging import get_logger
from app.migrations_admin import DB_PATH

logger = get_logger(__name__)

# Maks. lokacji w known_locations (bez kolumny campaign_id — graf od bieżącej pozycji)
_KNOWN_LOCATION_CAP = 120


def get_session_id_for_campaign(conn: sqlite3.Connection, campaign_id: int) -> int | str | None:
    """Ostatnia sesja kampanii — spójnie z turns._get_session_id_for_campaign."""
    row = conn.execute(
        """
        SELECT id FROM game_sessions
        WHERE campaign_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (campaign_id,),
    ).fetchone()
    if row:
        return row["id"]
    return None


def _collect_related_location_ids(
    conn: sqlite3.Connection, current_id: int, max_n: int = _KNOWN_LOCATION_CAP
) -> set[int]:
    """
    Opcja A (bez campaign_id): przodkowie bieżącej lokacji, rodzeństwo, dzieci
    wzdłuż łańcucha rodziców (szerokość 1 — bez pełnego DFS całego świata).
    """
    ids: set[int] = set()
    if not current_id or max_n <= 0:
        return ids

    lid: int | None = current_id
    while lid is not None and len(ids) < max_n:
        ids.add(lid)
        row = conn.execute(
            "SELECT parent_id FROM game_locations WHERE id = ? AND COALESCE(is_active, 1) = 1",
            (lid,),
        ).fetchone()
        lid = int(row["parent_id"]) if row and row["parent_id"] is not None else None

    snapshot = list(ids)
    for pid in snapshot:
        if len(ids) >= max_n:
            break
        for ch in conn.execute(
            "SELECT id FROM game_locations WHERE parent_id = ? AND COALESCE(is_active, 1) = 1",
            (pid,),
        ):
            cid = int(ch["id"])
            if cid not in ids:
                ids.add(cid)
                if len(ids) >= max_n:
                    break

    prow = conn.execute(
        "SELECT parent_id FROM game_locations WHERE id = ?",
        (current_id,),
    ).fetchone()
    if prow and prow["parent_id"] is not None:
        for s in conn.execute(
            "SELECT id FROM game_locations WHERE parent_id = ? AND COALESCE(is_active, 1) = 1",
            (int(prow["parent_id"]),),
        ):
            sid = int(s["id"])
            if sid not in ids:
                ids.add(sid)
                if len(ids) >= max_n:
                    break

    return ids


def build_location_context_block(session_id: int | str, conn: sqlite3.Connection) -> str | None:
    """
    Blok [LOCATION CONTEXT] jako osobna wiadomość systemowa dla LLM (8D-LOC-1 REV2).
    Opcja A: known_locations = lokacje na grafie od current_location_id (cap).
    Zwraca None przy braku sesji / braku current_location / braku wiersza lokacji.
    """
    row = conn.execute(
        "SELECT current_location_id FROM game_sessions WHERE id = ?",
        (str(session_id),),
    ).fetchone()
    if not row or not row["current_location_id"]:
        return None

    cur_id = int(row["current_location_id"])
    cur = conn.execute(
        "SELECT key, label, location_type FROM game_locations WHERE id = ? AND COALESCE(is_active, 1) = 1",
        (cur_id,),
    ).fetchone()
    if not cur:
        return None

    rel_ids = _collect_related_location_ids(conn, cur_id, _KNOWN_LOCATION_CAP)
    if cur_id not in rel_ids:
        rel_ids.add(cur_id)

    placeholders = ",".join("?" * len(rel_ids))
    params: list = list(rel_ids)
    params.append(cur_id)

    known = conn.execute(
        f"""
        SELECT gl.id, gl.key, gl.label, p.key AS parent_key
        FROM game_locations gl
        LEFT JOIN game_locations p ON p.id = gl.parent_id AND COALESCE(p.is_active, 1) = 1
        WHERE gl.id IN ({placeholders})
          AND COALESCE(gl.is_active, 1) = 1
          AND (COALESCE(gl.approved, 1) = 1 OR gl.id = ?)
        ORDER BY gl.label COLLATE NOCASE
        """,
        params,
    ).fetchall()

    lines = [
        "[LOCATION CONTEXT]",
        "current_location: { "
        + f'"key": {json.dumps(cur["key"])}, "label": {json.dumps(cur["label"])}, '
        + f'"type": {json.dumps(cur["location_type"] or "macro")}'
        + " }",
        "known_locations:",
    ]
    for loc in known:
        pk = loc["parent_key"]
        if pk is None or pk == "":
            parent_lit = "null"
        else:
            parent_lit = json.dumps(str(pk))
        lines.append(
            "  - { "
            + f'"key": {json.dumps(loc["key"])}, "label": {json.dumps(loc["label"])}, '
            + f'"parent_key": {parent_lit}'
            + " }"
        )
    return "\n".join(lines)


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
