"""U25 (#575) — Pity timer afiksów (drop boss-kill + reroll u craftera).

Czysty RNG przy niskiej przepustowości dropów (narracyjne RPG ≠ Diablo) może dać
długie serie bez nagrody. Gwarancja dolna chroni motywację grindu:

- DROP: licznik boss-killów bez afiksowanej broni per postać. Po `BOSS_DROP_PITY_THRESHOLD`
  killach bez afiksu następny drop broni dostaje gwarantowany afiks T1+ (licznik reset).
- REROLL: licznik rerollów tego samego przedmiotu bez zmiany afiksu. Po
  `REROLL_PITY_THRESHOLD` rerollach bez zmiany kolejny reroll wymusza INNY klucz (reset).

Liczniki żyją w tabeli `affix_pity (character_id, scope, counter)` — przeżywają restart.
`scope`:  'boss_drop' (per postać)  |  'reroll:<inventory_id>' (per przedmiot).

Wartości progów są STARTOWE (Numbers Policy) — tuning po playteście ekonomii.
"""
import sqlite3

# Numbers Policy — wartości startowe, do tuningu po playteście:
BOSS_DROP_PITY_THRESHOLD = 3   # boss-kille bez afiksu przed gwarancją
REROLL_PITY_THRESHOLD = 3      # rerolle bez zmiany przed gwarancją innego afiksu
GUARANTEED_AFFIX_TIER = 1      # gwarantowany afiks = tier 1 (T1+)


def _ensure_table(conn: sqlite3.Connection) -> None:
    """Defensywne CREATE TABLE — żywa baza dostaje tabelę z migracji (main.py),
    a testy in-memory tworzą ją tutaj. Idempotentne."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS affix_pity (
            character_id INTEGER NOT NULL,
            scope TEXT NOT NULL,
            counter INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (character_id, scope)
        )
        """
    )


def get_counter(conn: sqlite3.Connection, character_id: int, scope: str) -> int:
    _ensure_table(conn)
    row = conn.execute(
        "SELECT counter FROM affix_pity WHERE character_id = ? AND scope = ?",
        (int(character_id), scope),
    ).fetchone()
    if not row:
        return 0
    return int(row[0])


def _set_counter(conn: sqlite3.Connection, character_id: int, scope: str, value: int) -> int:
    _ensure_table(conn)
    conn.execute(
        """
        INSERT INTO affix_pity (character_id, scope, counter, updated_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(character_id, scope)
        DO UPDATE SET counter = excluded.counter, updated_at = datetime('now')
        """,
        (int(character_id), scope, int(value)),
    )
    conn.commit()
    return int(value)


# ─── DROP pity (boss-kille) ─────────────────────────────────────────────────────

def boss_drop_guaranteed(
    conn: sqlite3.Connection, character_id: int, threshold: int = BOSS_DROP_PITY_THRESHOLD
) -> bool:
    """True gdy następny drop broni z bossa MUSI dostać afiks (próg osiągnięty)."""
    return get_counter(conn, character_id, "boss_drop") >= threshold


def record_boss_drop(conn: sqlite3.Connection, character_id: int, got_affix: bool) -> int:
    """Zapisuje wynik boss-killa. got_affix=True → reset; False → +1. Zwraca nowy licznik."""
    if got_affix:
        return _set_counter(conn, character_id, "boss_drop", 0)
    new_val = get_counter(conn, character_id, "boss_drop") + 1
    return _set_counter(conn, character_id, "boss_drop", new_val)


# ─── REROLL pity (per przedmiot) ────────────────────────────────────────────────

def _reroll_scope(inv_id: int) -> str:
    return f"reroll:{int(inv_id)}"


def reroll_guaranteed_different(
    conn: sqlite3.Connection, character_id: int, inv_id: int, threshold: int = REROLL_PITY_THRESHOLD
) -> bool:
    """True gdy kolejny reroll tego przedmiotu MUSI dać inny klucz niż obecny."""
    return get_counter(conn, character_id, _reroll_scope(inv_id)) >= threshold


def record_reroll(conn: sqlite3.Connection, character_id: int, inv_id: int, changed: bool) -> int:
    """Zapisuje wynik rerolla. changed=True (klucz się zmienił) → reset; False → +1."""
    scope = _reroll_scope(inv_id)
    if changed:
        return _set_counter(conn, character_id, scope, 0)
    new_val = get_counter(conn, character_id, scope) + 1
    return _set_counter(conn, character_id, scope, new_val)
