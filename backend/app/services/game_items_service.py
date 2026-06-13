"""U11b (#557) — helper dla game_items: jednolite źródło odczytu przedmiotów.

Zastępuje czytanie z game_config_weapons / game_config_items / game_config_consumables
we wszystkich serwisach. Stare tabele pozostają (zapisy w U11c).
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any


def flatten_game_item(row: sqlite3.Row | dict) -> dict[str, Any]:
    """Spłaszcz wiersz game_items: rozwiń weapon_data/item_data do płaskich pól."""
    d = dict(row)
    weapon_data: dict = {}
    item_data: dict = {}
    try:
        if d.get("weapon_data"):
            weapon_data = (
                json.loads(d["weapon_data"])
                if isinstance(d["weapon_data"], str)
                else d["weapon_data"]
            )
    except Exception:
        pass
    try:
        if d.get("item_data"):
            item_data = (
                json.loads(d["item_data"])
                if isinstance(d["item_data"], str)
                else d["item_data"]
            )
    except Exception:
        pass
    merged = {**d, **weapon_data, **item_data}
    merged.pop("weapon_data", None)
    merged.pop("item_data", None)
    return merged


def get_item(
    conn: sqlite3.Connection,
    key: str,
    *,
    kind: str | None = None,
) -> dict[str, Any] | None:
    """Pobierz item z game_items po kluczu. Opcjonalnie ogranicz do kind."""
    k = str(key or "").strip()
    if not k:
        return None
    try:
        if kind:
            row = conn.execute(
                "SELECT * FROM game_items WHERE key = ? AND kind = ? AND is_active = 1",
                (k, kind),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM game_items WHERE key = ? AND is_active = 1",
                (k,),
            ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    return flatten_game_item(row)


def get_weapon_row(conn: sqlite3.Connection, key: str) -> dict[str, Any] | None:
    """Pobierz broń z game_items w formacie zgodnym z weapon_rules._normalize_weapon_row."""
    k = str(key or "").strip()
    if not k:
        return None
    try:
        row = conn.execute(
            """
            SELECT key, label,
                   json_extract(weapon_data, '$.damage_die')   AS damage_die,
                   json_extract(weapon_data, '$.linked_stat')  AS linked_stat,
                   json_extract(weapon_data, '$.weapon_type')  AS weapon_type,
                   json_extract(weapon_data, '$.two_handed')   AS two_handed,
                   json_extract(weapon_data, '$.finesse')      AS finesse,
                   json_extract(weapon_data, '$.range_m')      AS range_m,
                   json_extract(weapon_data, '$.weapon_slot')  AS weapon_slot,
                   effect_json
            FROM game_items
            WHERE key = ? AND kind = 'weapon' AND is_active = 1
            """,
            (k,),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    return dict(row) if row else None


def query_items(
    conn: sqlite3.Connection,
    *,
    kind: str | None = None,
    approved_only: bool = True,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Zwróć listę itemów z game_items, opcjonalnie filtrowaną po kind."""
    conds = ["is_active = 1"]
    params: list = []
    if approved_only:
        conds.append("COALESCE(approved, 1) = 1")
    if kind:
        conds.append("kind = ?")
        params.append(kind)
    sql = f"SELECT * FROM game_items WHERE {' AND '.join(conds)} ORDER BY key ASC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        return []
    return [flatten_game_item(r) for r in rows]
