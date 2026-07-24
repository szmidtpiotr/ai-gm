"""CB-7 (#1490) — smaczki Czarnoboru: światło w borze + dziegieć czarnodrzewny.

Fikcja (docs/world/regions/czarnobor.md §6): niemagiczne mechaniki na istniejących
silnikach — lustro soli i srebra Siwych Grań ([[salt_service]]).

* **Próchno świetlne** (``prochno_swietlne``) — zimne światło z próchna czarnodrzewu.
  Pochodnia (otwarty ogień) NOCĄ w borze PODBIJA szansę spotkań (płomień wabi) —
  próchno nie. Wybór gracza: „widzę lepiej vs jestem widoczny". Mechanicznie:
  mnożnik szansy spotkania w nocnym marszu (:func:`light_encounter_mult`).
* **Dziegieć czarnodrzewny** (``dziegiec_czarnodrzewny``) — cuchnące smarowidło
  maskujące zapach: bonus do skradania + niższa szansa spotkań z bestiami na
  hexach LEŚNYCH przez 1 dzień gry.

Silnik dziegciu: kondycje są rundowe (walka), a ten buff jest DZIENNY (podróż +
skradanie), więc trzymamy go w ``session_flags`` kampanii — wzorzec cooldownów
zielarstwa ([[herb_gathering_service]]) — a nie jako kondycję sheetu. Nakładanie
idzie zwykłą ścieżką użycia przedmiotu (``loot_service.use_inventory_item``).

Wszystkie liczby to WARTOŚCI STARTOWE (Numbers Policy) — strojone w Sandboksie.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

# ── Numbers Policy (Sandbox-tunable STARTING values) ──────────────────────────

#: Otwarty ogień (pochodnia) NOCĄ wabi to, co czai się w borze: mnożnik >1 do
#: szansy spotkania podczas nocnego marszu. Zimne światło (próchno) = 1.0.
TORCH_NIGHT_ENCOUNTER_MULT = 1.5

#: Dziegieć na hexie LEŚNYM: mnożnik szansy spotkania (poza lasem = 1.0, bez efektu).
DZIEGIEC_FOREST_ENCOUNTER_MULT = 0.5

#: Dziegieć: bonus do rzutu na skradanie (skill ``stealth``) póki buff aktywny.
DZIEGIEC_STEALTH_BONUS = 2

#: Dziegieć: jak długo trzyma smarowidło — 1 dzień gry = 24 godziny w grze.
DZIEGIEC_DURATION_HOURS = 24

#: Klucz buffa w ``session_flags`` — próg godzin gry, do którego dziegieć działa.
SCENT_MASK_FLAG = "scent_mask_until_hours"

#: hex_type traktowane jako „las" dla dziegciu (Czarnobór + Grań + rdzeń świata).
_FOREST_HEX_TYPES = frozenset({"forest", "las_iglasty", "czarny_las"})

#: Twardy fallback — klucze przedmiotów z otwartym ogniem (wabią nocą), gdy
#: przedmiot nie ma jawnego ``effect_json.light_kind``.
_OPEN_FLAME_ITEM_KEYS = frozenset({"torch"})


# ── światło: pochodnia vs próchno ─────────────────────────────────────────────

def _light_kind(effect_json: Any) -> str:
    """``effect_json.light_kind`` (``open_flame`` / ``cold``) lub '' gdy brak."""
    raw = effect_json
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or "{}")
        except (ValueError, TypeError):
            return ""
    if not isinstance(raw, dict):
        return ""
    return str(raw.get("light_kind") or "").strip().lower()


def item_is_open_flame(item_key: str | None, effect_json: Any) -> bool:
    """Czy dane źródło światła to otwarty ogień (wabi nocą).

    Prawda z ``effect_json.light_kind == 'open_flame'``; jawny ``cold`` (próchno)
    zawsze fałsz; brak flagi → fallback po znanym kluczu pochodni.
    """
    kind = _light_kind(effect_json)
    if kind == "open_flame":
        return True
    if kind == "cold":
        return False
    return str(item_key or "").strip().lower() in _OPEN_FLAME_ITEM_KEYS


def carries_open_flame_light(conn: sqlite3.Connection | None, character_id: int) -> bool:
    """Czy bohater niesie w plecaku źródło światła z otwartym ogniem (pochodnia).

    Próchno świetlne (zimne) nie liczy się — o to cały wybór krainy. Defensywne:
    brak połączenia / stara baza → False (żadnej kary).
    """
    if conn is None:
        return False
    try:
        rows = conn.execute(
            """
            SELECT gi.key AS key, gi.effect_json AS effect_json
            FROM character_inventory ci
            JOIN game_config_items gi ON gi.key = ci.item_key
            WHERE ci.character_id = ? AND ci.item_key IS NOT NULL
            """,
            (int(character_id),),
        ).fetchall()
    except sqlite3.OperationalError:
        return False
    for r in rows:
        try:
            if item_is_open_flame(r["key"], r["effect_json"]):
                return True
        except (IndexError, KeyError, TypeError):
            continue
    return False


def light_encounter_mult(*, has_open_flame: bool, night_march: bool) -> float:
    """Mnożnik szansy spotkania od źródła światła.

    Tylko podczas NOCNEGO marszu i tylko dla otwartego ognia (pochodni). Próchno
    (zimne światło) oraz dzień = 1.0 (brak zmiany).
    """
    if night_march and has_open_flame:
        return TORCH_NIGHT_ENCOUNTER_MULT
    return 1.0


# ── dziegieć: buff dzienny w session_flags ────────────────────────────────────

def salve_payload_from_item(effect_json: Any) -> dict[str, Any] | None:
    """Zwróć payload gdy przedmiot to smarowidło maskujące zapach, inaczej None.

    Konwencja: ``effect_json.effect_category == 'scent_mask'``.
    """
    raw = effect_json
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or "{}")
        except (ValueError, TypeError):
            return None
    if not isinstance(raw, dict):
        return None
    if str(raw.get("effect_category") or "").strip().lower() == "scent_mask":
        return raw
    return None


def _ingame_hours(conn: sqlite3.Connection | None, campaign_id: int) -> int:
    try:
        from app.services.clock_service import get_clock_state
        return int(get_clock_state(int(campaign_id), conn=conn).get("ingame_hours", 0) or 0)
    except Exception:
        return 0


def apply_scent_mask_buff(conn: sqlite3.Connection, campaign_id: int) -> dict[str, Any]:
    """Nałóż buff dziegciu na kampanię (zapis do ``session_flags``). Zwróć podsumowanie.

    Buff wygasa po :data:`DZIEGIEC_DURATION_HOURS` godzinach gry (compare-on-read).
    """
    now_h = _ingame_hours(conn, campaign_id)
    until_h = now_h + DZIEGIEC_DURATION_HOURS
    gs = conn.execute(
        "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (int(campaign_id),),
    ).fetchone()
    if not gs:
        raise ValueError("no game session for campaign")
    sf = json.loads((gs["session_flags"] if gs["session_flags"] else None) or "{}")
    sf[SCENT_MASK_FLAG] = until_h
    conn.execute(
        "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
        (json.dumps(sf, ensure_ascii=False), gs["id"]),
    )
    return {
        "expires_ingame_hours": until_h,
        "duration_hours": DZIEGIEC_DURATION_HOURS,
        "stealth_bonus": DZIEGIEC_STEALTH_BONUS,
    }


def scent_mask_active(session_flags: Any, ingame_hours: int) -> bool:
    """Czy dziegieć wciąż działa o danej godzinie gry (compare-on-read)."""
    if not isinstance(session_flags, dict):
        return False
    until = session_flags.get(SCENT_MASK_FLAG)
    if until is None:
        return False
    try:
        return int(ingame_hours) < int(until)
    except (TypeError, ValueError):
        return False


def dziegiec_stealth_bonus(session_flags: Any, ingame_hours: int) -> int:
    """Bonus do skradania od dziegciu (0 gdy nieaktywny)."""
    return DZIEGIEC_STEALTH_BONUS if scent_mask_active(session_flags, ingame_hours) else 0


def forest_encounter_mult(session_flags: Any, ingame_hours: int, hex_type: Any) -> float:
    """Mnożnik szansy spotkania od dziegciu na danym hexie.

    Działa tylko na hexach LEŚNYCH i tylko póki buff aktywny; inaczej 1.0.
    """
    if not scent_mask_active(session_flags, ingame_hours):
        return 1.0
    if str(hex_type or "").strip().lower() in _FOREST_HEX_TYPES:
        return DZIEGIEC_FOREST_ENCOUNTER_MULT
    return 1.0
