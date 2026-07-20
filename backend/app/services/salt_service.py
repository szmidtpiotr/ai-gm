"""SG-7 (#1481) — sól jako materiał przeciw-Rdzeniowy.

Fikcja (docs/world/regions/siwe_granie.md §6): sól nie jest magiczna — jest
*obojętna na Rdzeń* (izolator). Trzy przedmioty krainy Siwych Grań:

* **Krąg soli** (``salt_circle``)  — istoty Rdzenia nie wchodzą do ZWARCIA przez 3 rundy.
* **Solona klinga** (``salted_blade``) — +1k4 obrażeń vs istoty Rdzenia, na jedną walkę.
* **Szczypta soli** (``salt_pinch``) — następny miscast złagodzony o 1 stopień,
  ale sól tłumi też własny kanał: −1 do obrażeń czarów do końca walki.

Silnik: kondycje (G3 #1465) + consumables z ``effect_json.apply_condition``.
Ten moduł to CZYTNIK tych kondycji — sam nie nakłada niczego; nakładanie idzie
zwykłą ścieżką użycia przedmiotu (``loot_service.use_inventory_item``).

„Istota Rdzenia" = wróg z ``game_config_enemies.creature_type`` w
:data:`CORE_BEING_TYPES` (nieumarli, demony, twory Rdzenia).
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

SALT_CIRCLE_KEY = "salt_circle"
SALT_BLADE_KEY = "salted_blade"
SALT_PINCH_KEY = "salt_pinch"

#: Typy istot, na które sól działa. Wartości startowe — do strojenia w Sandboksie.
CORE_BEING_TYPES = {"undead", "demon", "rdzen"}

#: Kość bonusu Solonej klingi (wartość startowa, lore §6).
SALT_BLADE_DIE = "1d4"

#: Kara do obrażeń czarów po Szczypcie soli (wartość startowa, lore §6).
SALT_PINCH_SPELL_PENALTY = 1

_CREATURE_TYPE_CACHE: dict[str, str] = {}


# ── klasyfikacja wroga ───────────────────────────────────────────────────────

def enemy_creature_type(conn: sqlite3.Connection | None, enemy: dict[str, Any] | None) -> str:
    """Typ istoty dla combatanta wroga: z pola combatanta, inaczej z katalogu.

    Puste = nieznany (żaden efekt solny nie zadziała). Stare walki zapisane przed
    tą falą nie mają pola w JSON-ie — dlatego fallback po ``enemy_key``.
    """
    if not isinstance(enemy, dict):
        return ""
    direct = str(enemy.get("creature_type") or "").strip().lower()
    if direct:
        return direct
    key = str(enemy.get("enemy_key") or "").strip().lower()
    if not key or conn is None:
        return ""
    if key in _CREATURE_TYPE_CACHE:
        return _CREATURE_TYPE_CACHE[key]
    try:
        row = conn.execute(
            "SELECT creature_type FROM game_config_enemies WHERE key = ?", (key,)
        ).fetchone()
    except sqlite3.OperationalError:  # stara baza bez kolumny
        return ""
    value = ""
    if row is not None:
        try:
            value = str(row["creature_type"] or "").strip().lower()
        except (IndexError, KeyError, TypeError):
            value = ""
    _CREATURE_TYPE_CACHE[key] = value
    return value


def is_core_being(conn: sqlite3.Connection | None, enemy: dict[str, Any] | None) -> bool:
    """Czy wróg jest istotą Rdzenia (nieumarły / demon / twór Rdzenia)."""
    return enemy_creature_type(conn, enemy) in CORE_BEING_TYPES


# ── odczyt kondycji solnych ──────────────────────────────────────────────────

def _condition_entries(source: Any) -> list[dict[str, Any]]:
    if isinstance(source, dict):
        raw = source.get("conditions")
    elif isinstance(source, list):
        raw = source
    else:
        raw = None
    if not isinstance(raw, list):
        return []
    return [c for c in raw if isinstance(c, dict)]


def find_conditions(key: str, *sources: Any) -> list[dict[str, Any]]:
    """Wszystkie wpisy kondycji ``key`` we wskazanych źródłach (combatant i/lub sheet).

    Zwraca REFERENCJE — wołający może mutować runtime (np. zużycie łagodzenia)
    i zapis pójdzie razem ze zwykłym zapisem sheetu/combatantów.
    """
    key_lo = str(key or "").strip().lower()
    found: list[dict[str, Any]] = []
    for src in sources:
        for cond in _condition_entries(src):
            if str(cond.get("key") or "").strip().lower() == key_lo:
                found.append(cond)
    return found


def has_condition(key: str, *sources: Any) -> bool:
    return bool(find_conditions(key, *sources))


# ── efekty ───────────────────────────────────────────────────────────────────

def salt_circle_blocks_charge(
    conn: sqlite3.Connection | None,
    player_combatant: dict[str, Any] | None,
    enemy: dict[str, Any] | None,
    *,
    sheet: dict[str, Any] | None = None,
) -> bool:
    """Czy krąg soli zatrzymuje doskok tego wroga do zwarcia.

    Blokuje wyłącznie WEJŚCIE do zwarcia i wyłącznie istotom Rdzenia — żywy troll
    przejdzie przez sól bez wrażenia.
    """
    if not has_condition(SALT_CIRCLE_KEY, player_combatant, sheet):
        return False
    return is_core_being(conn, enemy)


def salted_blade_bonus(
    conn: sqlite3.Connection | None,
    player_combatant: dict[str, Any] | None,
    enemy: dict[str, Any] | None,
    *,
    sheet: dict[str, Any] | None = None,
    roller=None,
) -> int:
    """+1k4 obrażeń, gdy solona klinga tnie istotę Rdzenia (inaczej 0)."""
    if not has_condition(SALT_BLADE_KEY, player_combatant, sheet):
        return 0
    if not is_core_being(conn, enemy):
        return 0
    if roller is None:
        from app.services.combat_service import roll_damage_dice as _roll

        def roller(expr: str) -> int:
            return int(_roll(expr))
    try:
        return max(0, int(roller(SALT_BLADE_DIE)))
    except Exception:
        return 0


def spell_damage_penalty(
    player_combatant: dict[str, Any] | None,
    *,
    sheet: dict[str, Any] | None = None,
) -> int:
    """−1 do obrażeń czarów po szczypcie soli (sól tłumi też własny kanał)."""
    if not has_condition(SALT_PINCH_KEY, player_combatant, sheet):
        return 0
    return SALT_PINCH_SPELL_PENALTY


def consume_miscast_softening(*sources: Any) -> bool:
    """Czy ten miscast jest łagodzony o 1 stopień — i zużyj łagodzenie.

    Szczypta soli daje JEDNO złagodzenie na walkę; kara do obrażeń czarów zostaje
    do końca walki, więc kondycji nie zdejmujemy — znaczymy runtime.
    """
    entries = find_conditions(SALT_PINCH_KEY, *sources)
    if not entries:
        return False
    fresh = [
        c for c in entries
        if not bool((c.get("runtime") or {}).get("miscast_softened"))
    ]
    if not fresh:
        return False
    for cond in entries:
        runtime = cond.get("runtime")
        if not isinstance(runtime, dict):
            runtime = {}
            cond["runtime"] = runtime
        runtime["miscast_softened"] = True
    return True


# ── sprzątanie po walce ──────────────────────────────────────────────────────

def clears_on_combat_end(condition: dict[str, Any]) -> bool:
    """Czy kondycja ma w effect_json ``clear_on: "combat_end"`` (dane, nie ``if key ==``)."""
    raw = condition.get("effect_json")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or "{}")
        except (ValueError, TypeError):
            return False
    if not isinstance(raw, dict):
        return False
    return str(raw.get("clear_on") or "").strip().lower() == "combat_end"


def strip_combat_end_conditions(conditions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    """Zdejmij kondycje ważne „na jedną walkę". Zwraca (nowa lista, czy zmieniono)."""
    if not isinstance(conditions, list):
        return [], False
    kept = [c for c in conditions if not (isinstance(c, dict) and clears_on_combat_end(c))]
    return kept, len(kept) != len(conditions)
