"""Ammunition system (#764) + recovery (#765).

Broń dystansowa (łuk/kusza) zużywa amunicję (strzały/bełty) przy ataku. Amunicja
żyje w `character_inventory` jako stack — historycznie consumable lądują pod
kolumną `item_key` (patrz `grant_loot_to_character`), więc liczymy/odejmujemy po
OBU kolumnach (`item_key` ORAZ `consumable_key`) dla pełnej robustności.

Numbers Policy:
- DEFAULT_RECOVER_CHANCE = 0.40 — szansa odzysku 1 sztuki po walce (#765),
  wartość STARTOWA do strojenia w Sandboxie.
"""
from __future__ import annotations

import random
import sqlite3
from typing import Any, Callable

DEFAULT_RECOVER_CHANCE = 0.40  # #765 — starting value, Sandbox-tunable


def ammo_key_for_weapon(weapon_row: dict[str, Any] | None) -> str | None:
    """Klucz wymaganej amunicji dla broni (łuk→'arrows', kusza→'bolts'); None gdy brak."""
    if not weapon_row:
        return None
    raw = weapon_row.get("ammo_key")
    if raw is None:
        return None
    key = str(raw).strip()
    return key or None


def _ammo_match_sql() -> str:
    return "character_id = ? AND (consumable_key = ? OR item_key = ?)"


def get_ammo_quantity(conn: sqlite3.Connection, character_id: int, ammo_key: str) -> int:
    """Suma sztuk danej amunicji w plecaku bohatera."""
    if not ammo_key:
        return 0
    row = conn.execute(
        f"SELECT COALESCE(SUM(quantity), 0) AS q FROM character_inventory WHERE {_ammo_match_sql()}",
        (int(character_id), ammo_key, ammo_key),
    ).fetchone()
    return int((row["q"] if row else 0) or 0)


def consume_ammo(conn: sqlite3.Connection, character_id: int, ammo_key: str, n: int = 1) -> bool:
    """Odejmij n sztuk. True gdy starczyło (i odjęto), False gdy za mało (bez zmian)."""
    if not ammo_key or n <= 0:
        return False
    cid = int(character_id)
    if get_ammo_quantity(conn, cid, ammo_key) < n:
        return False
    remaining = n
    rows = conn.execute(
        f"SELECT id, quantity FROM character_inventory WHERE {_ammo_match_sql()} AND quantity > 0 "
        "ORDER BY quantity ASC, id ASC",
        (cid, ammo_key, ammo_key),
    ).fetchall()
    for r in rows:
        if remaining <= 0:
            break
        take = min(remaining, int(r["quantity"]))
        conn.execute("UPDATE character_inventory SET quantity = quantity - ? WHERE id = ?", (take, r["id"]))
        remaining -= take
    conn.execute(
        f"DELETE FROM character_inventory WHERE {_ammo_match_sql()} AND quantity <= 0",
        (cid, ammo_key, ammo_key),
    )
    conn.commit()
    return True


def add_ammo(conn: sqlite3.Connection, character_id: int, ammo_key: str, n: int) -> None:
    """Dołóż n sztuk amunicji — stackuj na istniejący wiersz lub utwórz nowy."""
    if not ammo_key or n <= 0:
        return
    cid = int(character_id)
    existing = conn.execute(
        f"SELECT id FROM character_inventory WHERE {_ammo_match_sql()} ORDER BY id ASC LIMIT 1",
        (cid, ammo_key, ammo_key),
    ).fetchone()
    if existing:
        conn.execute("UPDATE character_inventory SET quantity = quantity + ? WHERE id = ?", (n, existing["id"]))
    else:
        conn.execute(
            "INSERT INTO character_inventory (character_id, item_key, quantity, source) VALUES (?, ?, ?, 'ammo_recover')",
            (cid, ammo_key, n),
        )
    conn.commit()


def recover_ammo(
    conn: sqlite3.Connection,
    character_id: int,
    ammo_key: str,
    shots_fired: int,
    chance: float = DEFAULT_RECOVER_CHANCE,
    rng: Callable[[], float] | None = None,
) -> int:
    """Rzut per wystrzelona sztuka (odzysk gdy rng() < chance); odzyskane wracają do plecaka.

    Zwraca liczbę odzyskanych sztuk.
    """
    roll = rng or random.random
    shots = max(0, int(shots_fired or 0))
    recovered = sum(1 for _ in range(shots) if roll() < chance)
    if recovered:
        add_ammo(conn, character_id, ammo_key, recovered)
    return recovered
