"""WL-5 (#1504/#1505) — Pływy na Wybrzeżu Łez.

Źródło prawdy: docs/world/regions/wybrzeze_lez.md §6 (ZATWIERDZONE):
  „Pływy — `plycizna` przejezdna przy odpływie, zabójcza przy przypływie
   (kto zostanie — traci HP / musi uciekać). Działa na istniejącym zegarze gry."
  „Tabliczka pływów — przedmiot z portu: pokazuje, ile godzin do zmiany."

Ten moduł to CZYTNIK stanu zegara (jak ``wasteland_service`` / ``salt_service``) —
NIE buduje nowego zegara. Fazę pływu liczy z ``clock_service.get_clock_state``
(``ingame_hours``), a wpięcie w ruch/odpoczynek zamyka się w dwóch hookach:

  1. BLOKADA WEJŚCIA — przy PRZYPŁYWIE ``execute_travel`` odrzuca podróż, której
     CELEM jest hex ``plycizna`` (TravelError „tide_high"). Przy odpływie — wolna droga.
  2. ZASTANY PRZYPŁYWEM — ``maybe_tide_strand`` po podróży / długim odpoczynku:
     jeśli bohater STOI na ``plycizna`` a woda właśnie wróciła, wybieramy ŁAGODNIEJSZY
     wariant z §6 — WYMUSZONE PRZENIESIENIE na najbliższy suchy hex + drobne HP
     (nie zabija). Wariant „utrata HP na miejscu" odrzucony jako zbyt karzący.

Tabliczka pływów (``tabliczka_plywow``) niczego nie zmienia w mechanice — odsłania
tylko LICZNIK godzin do zmiany. Bez niej ``get_tide_state`` zwraca ``hours_to_change=None``
i gracz zgaduje (kanon §6).

WARTOŚCI STARTOWE (Numbers Policy) — wszystko do strojenia w Sandboksie:
  * TIDE_PHASE_HOURS = 6  → faza trwa 6 h, więc 2 PEŁNE CYKLE pływów na dobę
    (odpływ→przypływ→odpływ→przypływ). ODNOTOWANE: 2 cykle/dobę.
  * TIDE_STRAND_HP_DIE = "1d4" — otarcia/wychłodzenie przy ucieczce przed wodą.
"""

from __future__ import annotations

import json
import random
import sqlite3

import structlog

logger = structlog.get_logger()

# ── Numbers Policy (wartości startowe, Sandbox-tunable) ──────────────────────
#: Długość jednej fazy pływu w godzinach gry. 6 h → 2 pełne cykle na dobę.
TIDE_PHASE_HOURS = 6
#: Teren objęty pływami — jedyny „mokro-suchy" typ.
TIDE_HEX_TYPE = "plycizna"
#: Kość obrażeń przy zastaniu przez przypływ (łagodny wariant: przeniesienie + drobne HP).
TIDE_STRAND_HP_DIE = "1d4"
#: Kondycja nakładana zastanemu przez wodę (istniejąca — nie tworzymy nowej).
TIDE_STRAND_CONDITION = "przemoczony"
#: Przedmiot-tabliczka: odsłania licznik godzin do zmiany pływu.
TABLICZKA_KEY = "tabliczka_plywow"
#: Typy terenu liczone jako „wybrzeże" — na nich ŻAR pokazuje wskaźnik pływu.
COAST_HEX_TYPES = {"plycizna", "rafy", "morze", "wydmy", "coast"}
#: Ile hexów wszerz szukać suchego lądu przy wymuszonym przeniesieniu.
STRAND_SEARCH_RADIUS = 4

_PHASE_LOW = "odplyw"     # ODPŁYW — plycizna przejezdna
_PHASE_HIGH = "przyplyw"  # PRZYPŁYW — plycizna nieprzejezdna, zabójcza
_PHASE_LABELS = {_PHASE_LOW: "Odpływ", _PHASE_HIGH: "Przypływ"}


# ── Faza pływu (czysta arytmetyka na zegarze — testowalna bez DB) ────────────

def tide_phase(ingame_hours: int) -> str:
    """Faza pływu dla danej liczby godzin gry.

    Blok godzin ``[0,6) → odpływ``, ``[6,12) → przypływ``, ``[12,18) → odpływ`` …
    Naprzemiennie co TIDE_PHASE_HOURS. Zakotwiczone w absolutnym ``ingame_hours``
    (monotoniczny, nigdy się nie resetuje) → pływ jest spójny między dobami.
    """
    block = int(ingame_hours) // TIDE_PHASE_HOURS
    return _PHASE_HIGH if (block % 2 == 1) else _PHASE_LOW


def is_flood(ingame_hours: int) -> bool:
    """True przy PRZYPŁYWIE (woda wysoka — plycizna nieprzejezdna)."""
    return tide_phase(ingame_hours) == _PHASE_HIGH


def is_plycizna_passable(ingame_hours: int) -> bool:
    """Czy płyciznę da się przejść teraz (tylko przy odpływie)."""
    return not is_flood(ingame_hours)


def hours_to_next_change(ingame_hours: int) -> int:
    """Ile PEŁNYCH godzin gry do najbliższej zmiany pływu (1..TIDE_PHASE_HOURS)."""
    rem = TIDE_PHASE_HOURS - (int(ingame_hours) % TIDE_PHASE_HOURS)
    return rem if rem > 0 else TIDE_PHASE_HOURS


def cycles_per_day() -> int:
    """Ile pełnych cykli pływów na dobę (odnotowana wartość startowa)."""
    return max(1, 24 // (TIDE_PHASE_HOURS * 2))


def phase_label(phase: str) -> str:
    return _PHASE_LABELS.get(phase, phase)


# ── Ekwipunek ────────────────────────────────────────────────────────────────

def has_tide_board(conn: sqlite3.Connection, character_id: int) -> bool:
    """Czy bohater niesie Tabliczkę pływów (odsłania licznik godzin do zmiany)."""
    try:
        row = conn.execute(
            """SELECT 1 FROM character_inventory
               WHERE character_id = ?
                 AND (item_key = ? OR consumable_key = ?)
                 AND COALESCE(quantity, 1) > 0
               LIMIT 1""",
            (int(character_id), TABLICZKA_KEY, TABLICZKA_KEY),
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    return row is not None


# ── Odczyt położenia / terenu ────────────────────────────────────────────────

def _current_hex(conn: sqlite3.Connection, campaign_id: int) -> tuple[int, int] | None:
    try:
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (int(campaign_id),),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    flags = json.loads((row["session_flags"] if row else None) or "{}")
    ch = flags.get("current_hex")
    if not ch:
        return None
    try:
        return (int(ch["q"]), int(ch["r"]))
    except (KeyError, TypeError, ValueError):
        return None


def _hex_type_at(conn: sqlite3.Connection, q: int, r: int) -> str:
    try:
        row = conn.execute(
            "SELECT hex_type FROM world_hexes WHERE q=? AND r=? AND map_level=0 AND is_active=1 LIMIT 1",
            (int(q), int(r)),
        ).fetchone()
    except sqlite3.OperationalError:
        return ""
    return str((row["hex_type"] if row else "") or "")


def _passable_dry_types(conn: sqlite3.Connection) -> set[str]:
    """Typy terenu przejezdne i SUCHE (bez płycizny/morza/raf) — cel ucieczki."""
    try:
        rows = conn.execute(
            "SELECT hex_type FROM hex_type_config WHERE is_passable = 1 AND is_active = 1"
        ).fetchall()
    except sqlite3.OperationalError:
        return set()
    dry = {str(r["hex_type"]) for r in rows}
    dry.discard(TIDE_HEX_TYPE)
    return dry


def nearest_dry_hex(conn: sqlite3.Connection, q: int, r: int) -> tuple[int, int] | None:
    """BFS od (q,r) po sąsiadach do najbliższego suchego, przejezdnego hexa.

    Używane przy wymuszonym przeniesieniu — bohater ucieka z zalewanej mielizny
    na najbliższy stały ląd.
    """
    from app.services.hex_travel_service import hex_neighbors

    dry_types = _passable_dry_types(conn)
    if not dry_types:
        return None
    seen: set[tuple[int, int]] = {(int(q), int(r))}
    frontier = [(int(q), int(r))]
    for _ in range(STRAND_SEARCH_RADIUS):
        nxt: list[tuple[int, int]] = []
        for (cq, cr) in frontier:
            for (nq, nr) in hex_neighbors(cq, cr):
                if (nq, nr) in seen:
                    continue
                seen.add((nq, nr))
                if _hex_type_at(conn, nq, nr) in dry_types:
                    return (nq, nr)
                nxt.append((nq, nr))
        frontier = nxt
        if not frontier:
            break
    return None


# ── Stan pływu dla API / UI ──────────────────────────────────────────────────

def get_tide_state(
    conn: sqlite3.Connection, campaign_id: int, character_id: int
) -> dict:
    """Pełny stan pływu dla panelu ŻAR i logiki bramek.

    ``hours_to_change`` odsłonięte TYLKO gdy bohater niesie Tabliczkę pływów —
    bez niej gracz zgaduje (kanon §6).
    """
    from app.services.clock_service import get_clock_state

    clock = get_clock_state(campaign_id, conn=conn)
    ingame_hours = int(clock.get("ingame_hours", 0))
    phase = tide_phase(ingame_hours)
    nxt = _PHASE_HIGH if phase == _PHASE_LOW else _PHASE_LOW

    hex_xy = _current_hex(conn, campaign_id)
    cur_type = _hex_type_at(conn, *hex_xy) if hex_xy else ""
    on_coast = cur_type in COAST_HEX_TYPES

    board = has_tide_board(conn, character_id)
    return {
        "phase": phase,                                   # "odplyw" | "przyplyw"
        "phase_label": phase_label(phase),                # "Odpływ" | "Przypływ"
        "is_flood": phase == _PHASE_HIGH,
        "passable": phase == _PHASE_LOW,                  # czy plycizna przejezdna
        "on_coast": on_coast,                             # pokazać wskaźnik?
        "on_shallows": cur_type == TIDE_HEX_TYPE,         # stoję na plycizna?
        "current_hex_type": cur_type,
        "next_phase": nxt,
        "next_phase_label": phase_label(nxt),
        "has_board": board,
        # licznik tylko z tabliczką:
        "hours_to_change": hours_to_next_change(ingame_hours) if board else None,
        "cycles_per_day": cycles_per_day(),
        "ingame_hours": ingame_hours,
    }


# ── Hook 1: blokada wejścia (wołany z execute_travel) ────────────────────────

def tide_blocks_entry(
    conn: sqlite3.Connection, campaign_id: int, dest_q: int, dest_r: int
) -> bool:
    """True gdy CEL to plycizna, a trwa przypływ → podróży nie wolno rozpocząć."""
    if _hex_type_at(conn, dest_q, dest_r) != TIDE_HEX_TYPE:
        return False
    from app.services.clock_service import get_clock_state

    ingame_hours = int(get_clock_state(campaign_id, conn=conn).get("ingame_hours", 0))
    return is_flood(ingame_hours)


# ── Hook 2: zastany przypływem (wołany po podróży / długim odpoczynku) ────────

def maybe_tide_strand(
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int,
    result: dict | None = None,
    *,
    rng: random.Random | None = None,
) -> dict | None:
    """Jeśli bohater STOI na plycizna a trwa PRZYPŁYW — łagodny wariant §6:
    ostrzeżenie + WYMUSZONE PRZENIESIENIE na najbliższy suchy hex + drobne HP.

    Zwraca opis zdarzenia (dla ``result['tide_strand']`` i narracji) albo None,
    gdy nic się nie dzieje (nie na płyciźnie / odpływ / brak suchego lądu).
    Commit robi ta funkcja (utrwala HP + pozycję przed add_condition).
    """
    rng = rng or random
    hex_xy = _current_hex(conn, campaign_id)
    if hex_xy is None:
        return None
    cq, cr = hex_xy
    if _hex_type_at(conn, cq, cr) != TIDE_HEX_TYPE:
        return None

    from app.services.clock_service import get_clock_state

    ingame_hours = int(get_clock_state(campaign_id, conn=conn).get("ingame_hours", 0))
    if not is_flood(ingame_hours):
        return None  # odpływ — mielizna sucha, nic nie grozi

    dry = nearest_dry_hex(conn, cq, cr)
    if dry is None:
        logger.warning("tide_strand_no_dry_hex", campaign_id=campaign_id, q=cq, r=cr)
        # Fallback: nie ma dokąd uciec — samo drobne HP (nadal nie zabija).
        dry = (cq, cr)

    # obrażenia (min 1 HP — pływ nie zabija, tylko goni)
    dmg = rng.randint(1, int(TIDE_STRAND_HP_DIE.split("d")[1]))
    _row = conn.execute(
        "SELECT sheet_json FROM characters WHERE id=?", (character_id,)
    ).fetchone()
    sheet = json.loads(_row["sheet_json"] or "{}") if _row else {}
    cur_hp = int(sheet.get("current_hp", sheet.get("max_hp", 0)) or 0)
    sheet["current_hp"] = max(1, cur_hp - dmg)
    conn.execute(
        "UPDATE characters SET sheet_json=? WHERE id=?",
        (json.dumps(sheet, ensure_ascii=False), character_id),
    )

    # wymuszone przeniesienie na suchy hex
    moved = dry != (cq, cr)
    if moved:
        from app.services.location_state_service import set_position

        set_position(
            conn, campaign_id, current_hex={"q": dry[0], "r": dry[1]},
            clear_location_id=True, clear_local_hex=True, character_id=character_id,
        )
        conn.execute(
            "INSERT INTO campaign_hex_data (campaign_id, hex_q, hex_r, discovered) VALUES (?,?,?,1) "
            "ON CONFLICT(campaign_id, hex_q, hex_r) DO UPDATE SET discovered = 1",
            (campaign_id, dry[0], dry[1]),
        )
        if isinstance(result, dict):
            result["arrived_hex"] = {"q": dry[0], "r": dry[1]}
            _dt = _hex_type_at(conn, dry[0], dry[1])
            result["hex_data"] = {"q": dry[0], "r": dry[1], "hex_type": _dt or "plains"}
    conn.commit()

    try:
        from app.services.combat_service import add_condition_to_character
        add_condition_to_character(conn, character_id, campaign_id, TIDE_STRAND_CONDITION)
        conn.commit()
    except Exception as _cond_err:  # noqa: BLE001
        logger.warning("tide_strand_condition_failed", error=str(_cond_err))

    strand = {
        "damage": dmg, "moved": moved,
        "from": {"q": cq, "r": cr},
        "to": {"q": dry[0], "r": dry[1]},
    }
    if isinstance(result, dict):
        result["tide_strand"] = strand

    # narracja mechaniczna (bez LLM)
    if moved:
        msg = (
            f"Woda wraca szybciej, niż zdążysz się obejrzeć — przypływ zalewa mieliznę. "
            f"Brniesz przez rosnący nurt i ledwie wygrzebujesz się na suchy brzeg "
            f"(−{dmg} HP), przemoczony do suchej nitki."
        )
    else:
        msg = (
            f"Przypływ dopada cię na mieliźnie — nie ma dokąd uciec. Trzymasz się, "
            f"jak możesz, aż woda opadnie (−{dmg} HP), przemoczony i wyczerpany."
        )
    try:
        tn = conn.execute(
            "SELECT COALESCE(MAX(turn_number),0)+1 FROM campaign_turns WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO campaign_turns (campaign_id, character_id, turn_number, user_text, assistant_text, route, created_at) "
            "VALUES (?,?,?,?,?,?,datetime('now'))",
            (campaign_id, character_id, int(tn),
             "[Przypływ]", json.dumps({"narrative": msg}, ensure_ascii=False), "narrative"),
        )
        conn.commit()
    except Exception as _turn_err:  # noqa: BLE001
        logger.warning("tide_strand_turn_failed", error=str(_turn_err))

    return strand
