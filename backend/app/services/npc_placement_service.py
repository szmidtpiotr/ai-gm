"""Obsada lokacji — JEDNO źródło prawdy o tym, który NPC gdzie stoi (#1524).

Fala 1 „Sprzątania lokacji". Przed tym modułem wiązanie NPC↔lokacja żyło w trzech
miejscach naraz (`location_npc_assignments`, inline `game_locations.npc_keys`,
legacy `npc_locations` po `npc_id`), a każdy czytelnik wybierał inny zestaw —
stąd gospodarze widmo, podwójne liczenie i NPC w lokacjach, których nie ma.

Model docelowy (decyzje Piotra z 2026-07-21, #1524):

* **`location_npc_assignments` = kanon.** Wszystkie odczyty i zapisy idą tędy.
* **`game_locations.npc_keys` = kopia pochodna** (lustro dla mapy admina i
  eksportu treści). Odświeżane po każdym zapisie; nigdy nie czytane jako prawda.
* **`npc_locations` = legacy.** Nie czytany i nie zapisywany; migracja backfilluje
  go do przypisań i czyści (DROP po weryfikacji na DEV).
* **Gospodarz siedzi w sub-lokacji.** Makro mające sub-lokacje jest hubem i musi
  zostać puste (spójność z modelem osady #1212).
"""
from __future__ import annotations

import json
import sqlite3

__all__ = [
    "npc_keys_for_location",
    "locations_for_npc_key",
    "locations_for_npc_id",
    "npc_key_for_id",
    "assign_npc",
    "unassign_npc",
    "set_locations_for_npc_key",
    "set_locations_for_npc_id",
    "resync_npc_keys_mirror",
    "max_tier_for_npc_key",
    "npc_is_at_location",
    "location_is_hub",
]


def _clean(value: object) -> str:
    return str(value or "").strip()


# ─── Odczyt ──────────────────────────────────────────────────────────────────

def npc_keys_for_location(conn: sqlite3.Connection, location_key: str, *, active_only: bool = True) -> list[str]:
    """Klucze NPC obsadzonych w tej lokacji (kanon: tabela przypisań)."""
    key = _clean(location_key)
    if not key:
        return []
    sql = "SELECT npc_key FROM location_npc_assignments WHERE location_key = ?"
    if active_only:
        sql += " AND COALESCE(is_active, 1) = 1"
    sql += " ORDER BY npc_key"
    try:
        rows = conn.execute(sql, (key,)).fetchall()
    except sqlite3.OperationalError:
        return []
    return [_clean(r[0]) for r in rows if _clean(r[0])]


def locations_for_npc_key(conn: sqlite3.Connection, npc_key: str, *, active_only: bool = True) -> list[str]:
    key = _clean(npc_key)
    if not key:
        return []
    sql = "SELECT location_key FROM location_npc_assignments WHERE npc_key = ?"
    if active_only:
        sql += " AND COALESCE(is_active, 1) = 1"
    sql += " ORDER BY location_key"
    try:
        rows = conn.execute(sql, (key,)).fetchall()
    except sqlite3.OperationalError:
        return []
    return [_clean(r[0]) for r in rows if _clean(r[0])]


def npc_key_for_id(conn: sqlite3.Connection, npc_id: int) -> str | None:
    row = conn.execute("SELECT key FROM npcs WHERE id = ?", (int(npc_id),)).fetchone()
    return _clean(row[0]) if row else None


def locations_for_npc_id(conn: sqlite3.Connection, npc_id: int, *, active_only: bool = True) -> list[str]:
    key = npc_key_for_id(conn, npc_id)
    return locations_for_npc_key(conn, key, active_only=active_only) if key else []


def npc_is_at_location(conn: sqlite3.Connection, npc_key: str, location_key: str) -> bool:
    """NPC bez ANI JEDNEGO przypisania jest globalny (dostępny wszędzie).

    Zachowanie sprzed #1524: seedowy/testowy handlarz bez obsady nie może być
    odrzucony przez bramkę „nie ma go tutaj". Gdy NPC ma jakąkolwiek obsadę,
    liczy się tylko ona.
    """
    loc = _clean(location_key).lower()
    if not loc:
        return True
    assigned = [k.lower() for k in locations_for_npc_key(conn, npc_key)]
    if not assigned:
        return True
    return loc in assigned


def max_tier_for_npc_key(conn: sqlite3.Connection, npc_key: str, *, default: int = 1) -> int:
    """Najwyższy tier spośród lokacji, w których NPC stoi (cennik sklepu)."""
    try:
        rows = conn.execute(
            "SELECT COALESCE(gl.tier, 1) FROM location_npc_assignments a "
            "JOIN game_locations gl ON gl.key = a.location_key "
            "WHERE a.npc_key = ? AND COALESCE(a.is_active, 1) = 1",
            (_clean(npc_key),),
        ).fetchall()
    except sqlite3.OperationalError:
        return default
    tiers = [int(r[0]) for r in rows if r[0] is not None]
    return max(tiers) if tiers else default


def location_is_hub(conn: sqlite3.Connection, location_key: str) -> bool:
    """Makro mające sub-lokacje = hub osady. Gospodarze siedzą w subach, nie tutaj."""
    key = _clean(location_key)
    if not key:
        return False
    row = conn.execute(
        "SELECT location_type FROM game_locations WHERE key = ?", (key,)
    ).fetchone()
    if not row or _clean(row[0]) != "macro":
        return False
    sub = conn.execute(
        "SELECT 1 FROM game_locations WHERE parent_key = ? LIMIT 1", (key,)
    ).fetchone()
    return sub is not None


# ─── Zapis (zawsze przez przypisania + odświeżenie lustra) ───────────────────

def assign_npc(
    conn: sqlite3.Connection,
    location_key: str,
    npc_key: str,
    *,
    assignment_type: str = "resident",
    notes: str | None = None,
) -> None:
    loc, npc = _clean(location_key), _clean(npc_key)
    if not loc or not npc:
        raise ValueError("location_key i npc_key są wymagane")
    if location_is_hub(conn, loc):
        raise ValueError(
            f"'{loc}' to makro-hub z sub-lokacjami — gospodarz musi trafić do sub-lokacji (#1524)"
        )
    conn.execute(
        "INSERT INTO location_npc_assignments (location_key, npc_key, assignment_type, notes, is_active) "
        "VALUES (?, ?, ?, ?, 1) "
        "ON CONFLICT(location_key, npc_key) DO UPDATE SET is_active = 1, "
        "assignment_type = excluded.assignment_type",
        (loc, npc, assignment_type, notes),
    )
    resync_npc_keys_mirror(conn, [loc])


def unassign_npc(conn: sqlite3.Connection, location_key: str, npc_key: str) -> None:
    loc, npc = _clean(location_key), _clean(npc_key)
    conn.execute(
        "DELETE FROM location_npc_assignments WHERE location_key = ? AND npc_key = ?",
        (loc, npc),
    )
    resync_npc_keys_mirror(conn, [loc])


def set_locations_for_npc_key(conn: sqlite3.Connection, npc_key: str, location_keys: list[str]) -> None:
    """Zastępuje całą obsadę tego NPC (odpowiednik dawnego `_set_npc_locations`)."""
    npc = _clean(npc_key)
    if not npc:
        return
    wanted = [_clean(k) for k in (location_keys or []) if _clean(k)]
    for loc in wanted:
        if location_is_hub(conn, loc):
            raise ValueError(
                f"'{loc}' to makro-hub z sub-lokacjami — wybierz sub-lokację (#1524)"
            )
    touched = set(locations_for_npc_key(conn, npc, active_only=False)) | set(wanted)
    conn.execute("DELETE FROM location_npc_assignments WHERE npc_key = ?", (npc,))
    for loc in wanted:
        conn.execute(
            "INSERT OR REPLACE INTO location_npc_assignments "
            "(location_key, npc_key, assignment_type, is_active) VALUES (?, ?, 'resident', 1)",
            (loc, npc),
        )
    resync_npc_keys_mirror(conn, sorted(touched))


def set_npcs_for_location(conn: sqlite3.Connection, location_key: str, npc_keys: list[str]) -> None:
    """Zastępuje całą obsadę lokacji (panel admina / generator lokacji)."""
    loc = _clean(location_key)
    if not loc:
        return
    wanted = [_clean(k) for k in (npc_keys or []) if _clean(k)]
    if wanted and location_is_hub(conn, loc):
        raise ValueError(
            f"'{loc}' to makro-hub z sub-lokacjami — gospodarz musi trafić do sub-lokacji (#1524)"
        )
    conn.execute("DELETE FROM location_npc_assignments WHERE location_key = ?", (loc,))
    for npc in wanted:
        conn.execute(
            "INSERT OR REPLACE INTO location_npc_assignments "
            "(location_key, npc_key, assignment_type, is_active) VALUES (?, ?, 'resident', 1)",
            (loc, npc),
        )
    resync_npc_keys_mirror(conn, [loc])


def set_locations_for_npc_id(conn: sqlite3.Connection, npc_id: int, location_keys: list[str]) -> None:
    key = npc_key_for_id(conn, npc_id)
    if key:
        set_locations_for_npc_key(conn, key, location_keys)


def forget_npc(conn: sqlite3.Connection, npc_key: str) -> None:
    """Kasacja NPC — obsada znika razem z nim."""
    set_locations_for_npc_key(conn, npc_key, [])


# ─── Lustro `npc_keys` ───────────────────────────────────────────────────────

def resync_npc_keys_mirror(conn: sqlite3.Connection, location_keys: list[str] | None = None) -> int:
    """Przepisuje `game_locations.npc_keys` z przypisań. Zwraca liczbę zmienionych wierszy.

    Bez argumentu odświeża CAŁY katalog — używane przez migrację i skrypty seedujące.
    """
    try:
        if location_keys is None:
            rows = conn.execute("SELECT key, npc_keys FROM game_locations").fetchall()
        else:
            keys = [_clean(k) for k in location_keys if _clean(k)]
            if not keys:
                return 0
            ph = ",".join("?" for _ in keys)
            rows = conn.execute(
                f"SELECT key, npc_keys FROM game_locations WHERE key IN ({ph})", tuple(keys)
            ).fetchall()
    except sqlite3.OperationalError:
        return 0

    changed = 0
    for row in rows:
        key = _clean(row[0])
        current = row[1]
        want = json.dumps(npc_keys_for_location(conn, key), ensure_ascii=False)
        if _clean(current) == want:
            continue
        conn.execute("UPDATE game_locations SET npc_keys = ? WHERE key = ?", (want, key))
        changed += 1
    return changed
