"""Phase 8D — Injector kontekstu lokalizacji do system promptu GM.

U29 — build_swiat_block(): blok === ŚWIAT === z danymi hex + lokacje z bazy + kandydaci.
"""

import json
import re
import sqlite3
from typing import Optional

from app.core.logging import get_logger
from app.migrations_admin import DB_PATH

logger = get_logger(__name__)

# Maks. lokacji w known_locations (bez kolumny campaign_id — graf od bieżącej pozycji)
_KNOWN_LOCATION_CAP = 120

# ── U29: Flat-top hex directions (q_delta, r_delta, direction_name) ──────────

_HEX_DIRECTIONS = [
    (1,  0,  "wschód"),
    (-1, 0,  "zachód"),
    (0,  1,  "południe"),
    (0,  -1, "północ"),
    (1,  -1, "północny-wschód"),
    (-1, 1,  "południowy-zachód"),
]

# ── U29: Keyword → location_subtype mapping for candidate search ──────────────

_INTENT_KEYWORDS: dict[str, list[str]] = {
    "karczma":      ["tavern", "inn"],
    "gospoda":      ["tavern", "inn"],
    "tawerna":      ["tavern", "inn"],
    "kowal":        ["smithy", "forge"],
    "kuźnia":       ["smithy", "forge"],
    "świątynia":    ["temple", "church"],
    "kościół":      ["temple", "church"],
    "kaplica":      ["temple", "church"],
    "sklep":        ["shop", "market"],
    "rynek":        ["market", "shop"],
    "targowisko":   ["market", "shop"],
    "strażnica":    ["watchtower", "guard_post"],
    "wieża":        ["watchtower", "tower"],
    "port":         ["harbor", "port"],
    "stajnia":      ["stable"],
    "gildia":       ["guild"],
}

# Cap bloku ~400 tokenów ≈ 1600 znaków
_SWIAT_BLOCK_MAX_CHARS = 1600

# Fallback atmosphere per terrain type — used when world_hexes.atmosphere IS NULL.
# Gives LLM concrete sensory cues so narration matches terrain.
_TERRAIN_ATMOSPHERE: dict[str, str] = {
    "forest":    "Gęsty las. Skrzypią drzewa, śpiewają ptaki, mech wygłusza kroki.",
    "plains":    "Otwarta równina. Wiatr gnie trawy, horyzont daleki, niebo szerokie.",
    "hills":     "Pagórkowaty teren. Ostre trawy, wiatr na wzniesieniach, daleki widok.",
    "mountains": "Skaliste zbocze. Cienkie powietrze, ostre głazy, zimny wiatr z przełęczy.",
    "river":     "Kręty brzeg rzeki. Szum nurtu, mokre kamienie, mgła nad wodą, zapach mułu i trzcin.",
    "water":     "Brzeg wielkiej wody. Spokojna tafla, szum fal, zapach ryb i wilgoci.",
    "swamp":     "Bagniste trzęsawisko. Chlupot pod butami, mgła, smród gnijącej roślinności.",
    "desert":    "Pustynia lub pustać. Żar, pył, brak cienia, wiatr niosący piasek.",
    "ruins":     "Rozsypane ruiny. Pył, powykrzywiane kamienie, cisza przerywana szelestem gruzu.",
    "dungeon":   "Mroczne podziemia. Wilgoć, kapanie wody, odgłosy z głębin.",
    "road":      "Ubita droga. Koleje wozów, kamienne znaki milowe, kurz pod butami.",
    "town":      "Osada. Dym z kominów, szczek psów w oddali, głosy i zapach gotowanego jedzenia.",
    "castle":    "Kamienny zamek lub forteca. Chłód murów, echo kroków, straże na blanach.",
    "cave":      "Jaskinia. Kompletna ciemność bez pochodni, kapanie wody, zaciszna cisza.",
    "tundra":    "Mroźna tundra. Wiatr tnie po twarzy, niska roślinność, śnieg w zagłębieniach.",
    "coast":     "Wybrzeże. Krzyk mew, fale rozbijające się o brzeg, słony wiatr.",
    "volcanic":  "Teren wulkaniczny. Czarna skała, zapach siarki, gorące powietrze drży nad ziemią.",
}


def _hex_distance(q1: int, r1: int, q2: int, r2: int) -> int:
    return max(abs(q1 - q2), abs(r1 - r2), abs((q1 + r1) - (q2 + r2)))


def _detect_location_intent(player_message: str) -> list[str]:
    """Returns list of location_subtype strings matching keywords in player_message.

    Uses stem matching (first N-1 chars of keyword) to handle Polish declension:
    'karczma' stem 'karczm' matches 'karczmy', 'karczmie', etc.
    """
    if not player_message:
        return []
    msg_lower = player_message.lower()
    subtypes: list[str] = []
    for keyword, subs in _INTENT_KEYWORDS.items():
        # Use stem = keyword minus last char for declension tolerance
        stem = keyword[:-1] if len(keyword) > 3 else keyword
        if stem in msg_lower:
            subtypes.extend(subs)
    return list(dict.fromkeys(subtypes))  # deduplicate, preserve order


def _get_hex_row(conn: sqlite3.Connection, q: int, r: int) -> dict | None:
    row = conn.execute(
        "SELECT q, r, hex_type, label, atmosphere FROM world_hexes WHERE q=? AND r=? AND is_active=1",
        (q, r),
    ).fetchone()
    return dict(row) if row else None


def _get_locations_on_hex(conn: sqlite3.Connection, q: int, r: int) -> list[dict]:
    rows = conn.execute(
        """SELECT key, label, description, location_subtype, biome
           FROM game_locations
           WHERE world_hex_q=? AND world_hex_r=? AND approved=1 AND is_active=1""",
        (q, r),
    ).fetchall()
    return [dict(r) for r in rows]


def _get_location_npcs(conn: sqlite3.Connection, location_key: str) -> list[dict]:
    rows = conn.execute(
        """SELECT npc_key, assignment_type
           FROM location_npc_assignments
           WHERE location_key=? AND is_active=1""",
        (location_key,),
    ).fetchall()
    return [dict(r) for r in rows]


def _get_hex_neighbors(conn: sqlite3.Connection, q: int, r: int) -> list[dict]:
    neighbors = []
    for dq, dr, direction in _HEX_DIRECTIONS:
        nq, nr = q + dq, r + dr
        row = conn.execute(
            "SELECT q, r, hex_type, label, location_key FROM world_hexes WHERE q=? AND r=? AND is_active=1",
            (nq, nr),
        ).fetchone()
        if row:
            n = dict(row)
            n["direction"] = direction
            neighbors.append(n)
    return neighbors


def _find_location_candidates(
    conn: sqlite3.Connection,
    q: int,
    r: int,
    subtypes: list[str],
    limit: int = 3,
) -> list[dict]:
    """Find top locations from DB matching subtypes, sorted by distance from (q,r).

    Wariant 2 (decyzja 2026-06-12): floating (niezakotwiczone) lokacje liczą się
    jako kandydaci — zostaną osadzone przy odkryciu pasującego hexa (U28).
    Placed lokacje sortowane wg dystansu; floating lądują na końcu listy.
    """
    if not subtypes:
        return []
    placeholders = ",".join("?" * len(subtypes))
    rows = conn.execute(
        f"""SELECT key, label, location_subtype, biome, placement, world_hex_q, world_hex_r
            FROM game_locations
            WHERE location_subtype IN ({placeholders})
              AND approved=1 AND is_active=1
            LIMIT 30""",
        subtypes,
    ).fetchall()
    candidates = []
    for row in rows:
        c = dict(row)
        if c.get("world_hex_q") is not None and c.get("world_hex_r") is not None:
            c["distance"] = _hex_distance(q, r, int(c["world_hex_q"]), int(c["world_hex_r"]))
            c["floating"] = False
        else:
            c["distance"] = 999
            c["floating"] = True
        candidates.append(c)
    candidates.sort(key=lambda x: x["distance"])
    return candidates[:limit]


def build_swiat_block(
    conn: sqlite3.Connection,
    session_flags: dict,
    player_message: str = "",
) -> str | None:
    """U29 — Builds the === ŚWIAT === block for the LLM narrator.

    Returns None when there's no current_hex in session_flags (no hex context).
    Returns the block string otherwise (always contains at minimum hex coordinates).

    Token cap: ~400 tokens (~1600 chars). Priority: hex locations > candidates > neighbors.
    """
    current_hex = session_flags.get("current_hex") or {}
    q = current_hex.get("q")
    r = current_hex.get("r")
    if q is None or r is None:
        return None

    q, r = int(q), int(r)

    hex_row = _get_hex_row(conn, q, r)
    hex_type = (hex_row or {}).get("hex_type", "nieznany")
    hex_label = (hex_row or {}).get("label") or f"({q},{r})"
    # Use DB atmosphere if set, fall back to built-in terrain description
    hex_atmosphere = (
        ((hex_row or {}).get("atmosphere") or "").strip()
        or _TERRAIN_ATMOSPHERE.get(hex_type, "")
    )

    lines = ["=== ŚWIAT ===", f"Hex: q={q} r={r} | teren: {hex_type} | {hex_label}"]
    if hex_atmosphere:
        lines.append(f"Atmosfera terenu: {hex_atmosphere}")

    # ── Lokacje na hexie (priorytet 1) ────────────────────────────────────────
    locations = _get_locations_on_hex(conn, q, r)
    if locations:
        lines.append("Lokacje na tym hexie:")
        for loc in locations:
            loc_line = f"  [{loc['key']}] {loc['label']}"
            subtype = loc.get("location_subtype") or ""
            if subtype:
                loc_line += f" ({subtype})"
            lines.append(loc_line)
            desc = (loc.get("description") or "").strip()
            if desc:
                lines.append(f"    Opis: {desc[:120]}")
            # NPCs
            npcs = _get_location_npcs(conn, loc["key"])
            if npcs:
                npc_parts = [f"{n['npc_key']} [{n['assignment_type']}]" for n in npcs]
                lines.append(f"    NPC: {', '.join(npc_parts)}")

    # ── Kandydaci z bazy (priorytet 2 — gdy intencja gracza) ─────────────────
    intent_subtypes = _detect_location_intent(player_message)
    if intent_subtypes:
        candidates = _find_location_candidates(conn, q, r, intent_subtypes)
        if candidates:
            lines.append("Kandydaci z bazy (pasują do intencji gracza):")
            for cand in candidates:
                dist = cand.get("distance", "?")
                if cand.get("floating"):
                    dist_txt = "pula nieosadzona — zostanie przypisana przy odkryciu hexa"
                else:
                    dist_txt = f"{dist} hex" if isinstance(dist, int) and dist < 999 else "nieznana odległość"
                lines.append(f"  [{cand['key']}] {cand['label']} — {dist_txt}")
        else:
            lines.append("brak_dopasowania: true")

    # ── Sąsiednie hexy (priorytet 3) ─────────────────────────────────────────
    block_so_far = "\n".join(lines)
    if len(block_so_far) < _SWIAT_BLOCK_MAX_CHARS - 200:
        neighbors = _get_hex_neighbors(conn, q, r)
        if neighbors:
            neighbor_parts = []
            for nb in neighbors:
                nb_txt = f"{nb['direction']}: {nb.get('label') or '?'} [{nb.get('hex_type','?')}]"
                if nb.get("location_key"):
                    nb_txt += f" → {nb['location_key']}"
                neighbor_parts.append(nb_txt)
            lines.append("Sąsiedzi: " + " | ".join(neighbor_parts))

    result = "\n".join(lines)

    # Hard cap
    if len(result) > _SWIAT_BLOCK_MAX_CHARS:
        result = result[:_SWIAT_BLOCK_MAX_CHARS] + "\n[...blok ucięty — token cap]"

    return result


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
