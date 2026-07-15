"""U11b/c (#557/#558) — helper dla game_items: jednolite źródło odczytu i zapisu przedmiotów.

U11b: zastępuje czytanie z game_config_weapons / game_config_items / game_config_consumables.
U11c: dual-write — create_weapon/create_item/smart_entry/approve_entity piszą tu też.
Stare tabele pozostają do momentu drop (decyzja Piotra po 2 tygodniach stabilności).
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
                   json_extract(weapon_data, '$.light')        AS light,
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


_ITEM_TYPE_TO_KIND: dict[str, str] = {
    "armor": "armor",
    "shield": "armor",
    "consumable": "consumable",
}


def _item_type_to_kind(item_type: str) -> str:
    return _ITEM_TYPE_TO_KIND.get((item_type or "").lower(), "item")


# ──────────────────────────────────────────────────────────────────────────────
# U11c (#558) — WRITE/SYNC: dual-write z legacy tabel do game_items.
#
# Po U11b odczyt idzie wyłącznie z game_items, więc każdy zapis do starej tabeli
# (game_config_weapons / game_config_items / game_config_consumables) musi być
# zsynchronizowany do game_items, inaczej nowy/edytowany przedmiot nie pojawi się
# w grze. Stare tabele pozostają zapisywane (DEPRECATED — drop po 2 tyg.).
#
# Strategia: po zapisie legacy RE-READ wiersza i UPSERT do game_items — mapowanie
# kolumn identyczne jak backfill U11a (jedno źródło prawdy). Funkcje przyjmują
# OTWARTE połączenie i NIE commitują — robi to wywołujący (legacy + sync = 1 txn).
# ──────────────────────────────────────────────────────────────────────────────

LEGACY_ITEM_TABLES = (
    "game_config_weapons",
    "game_config_items",
    "game_config_consumables",
)


def _upsert(conn: sqlite3.Connection, cols: dict[str, Any]) -> None:
    """INSERT ... ON CONFLICT(key) DO UPDATE — prawdziwy upsert pojedynczego rekordu.

    created_by/created_at NIE są nadpisywane przy update (zachowanie proweniencji).
    """
    keys = list(cols.keys())
    placeholders = ", ".join("?" for _ in keys)
    col_list = ", ".join(keys)
    update_cols = [k for k in keys if k not in ("key", "created_at", "created_by")]
    set_clause = ", ".join(f"{k}=excluded.{k}" for k in update_cols)
    set_clause = (set_clause + ", " if set_clause else "") + "updated_at=datetime('now')"
    sql = (
        f"INSERT INTO game_items ({col_list}) VALUES ({placeholders}) "
        f"ON CONFLICT(key) DO UPDATE SET {set_clause}"
    )
    conn.execute(sql, [cols[k] for k in keys])


def upsert_from_weapon(conn: sqlite3.Connection, key: str) -> bool:
    """Zsynchronizuj wiersz game_config_weapons → game_items (kind='weapon')."""
    k = str(key or "").strip()
    if not k:
        return False
    try:
        row = conn.execute(
            """SELECT key, label, description, value_gp, effect_json, rarity, min_level,
                      location_tags, approved, is_active, weight_kg, note, locked_at,
                      damage_die, weapon_type, linked_stat, allowed_classes, two_handed,
                      finesse, light, range_m, targeting, aoe_radius_m, magic_school, weapon_slot
               FROM game_config_weapons WHERE key = ?""",
            (k,),
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    if not row:
        return False
    weapon_slot = row["weapon_slot"] or "main_hand"
    weapon_data = json.dumps({
        "damage_die": row["damage_die"],
        "weapon_type": row["weapon_type"],
        "linked_stat": row["linked_stat"],
        "allowed_classes": row["allowed_classes"],
        "two_handed": row["two_handed"],
        "finesse": row["finesse"],
        "light": row["light"],
        "range_m": row["range_m"],
        "targeting": row["targeting"],
        "aoe_radius_m": row["aoe_radius_m"],
        "magic_school": row["magic_school"],
        "weapon_slot": weapon_slot,
    })
    _upsert(conn, {
        "key": k, "kind": "weapon",
        "label": row["label"] or "", "description": row["description"] or "",
        "price_gp": float(row["value_gp"] or 0), "effect_json": row["effect_json"],
        "equip_slot": weapon_slot,
        "rarity": int(row["rarity"] or 1), "min_level": int(row["min_level"] or 1),
        "location_tags": row["location_tags"] or "[]",
        "approved": int(row["approved"] if row["approved"] is not None else 1),
        "is_active": int(row["is_active"] if row["is_active"] is not None else 1),
        "weapon_data": weapon_data, "item_data": "{}",
        "weight_kg": float(row["weight_kg"] or 0), "note": row["note"],
        "locked_at": row["locked_at"],
    })
    return True


def upsert_from_item(conn: sqlite3.Connection, key: str) -> bool:
    """Zsynchronizuj wiersz game_config_items → game_items (kind z item_type)."""
    k = str(key or "").strip()
    if not k:
        return False
    try:
        row = conn.execute(
            """SELECT key, label, description, value_gp, effect_json, rarity, min_level,
                      location_tags, approved, is_active, weight_kg, note, locked_at,
                      item_type, ac_bonus, armor_coverage, allowed_classes,
                      charges, effect_type, effect_dice, effect_bonus, effect_target
               FROM game_config_items WHERE key = ?""",
            (k,),
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    if not row:
        return False
    kind = _item_type_to_kind(row["item_type"])
    equip_slot = "armor" if kind == "armor" else None
    item_data = json.dumps({
        "item_type": row["item_type"],
        "ac_bonus": row["ac_bonus"],
        "armor_coverage": row["armor_coverage"],
        "allowed_classes": row["allowed_classes"],
        "charges": row["charges"],
        "effect_type": row["effect_type"],
        "effect_dice": row["effect_dice"],
        "effect_bonus": row["effect_bonus"],
        "effect_target": row["effect_target"],
    })
    _upsert(conn, {
        "key": k, "kind": kind,
        "label": row["label"] or "", "description": row["description"] or "",
        "price_gp": float(row["value_gp"] or 0), "effect_json": row["effect_json"],
        "equip_slot": equip_slot,
        "rarity": int(row["rarity"] or 1), "min_level": int(row["min_level"] or 1),
        "location_tags": row["location_tags"] or "[]",
        "approved": int(row["approved"] if row["approved"] is not None else 1),
        "is_active": int(row["is_active"] if row["is_active"] is not None else 1),
        "weapon_data": "{}", "item_data": item_data,
        "weight_kg": float(row["weight_kg"] or 0), "note": row["note"],
        "locked_at": row["locked_at"],
    })
    return True


def upsert_from_consumable(conn: sqlite3.Connection, key: str) -> bool:
    """Zsynchronizuj wiersz game_config_consumables → game_items (kind='consumable')."""
    k = str(key or "").strip()
    if not k:
        return False
    try:
        row = conn.execute(
            """SELECT key, label, description, base_price, rarity, min_level,
                      location_tags, approved, is_active, weight_kg, note, locked_at,
                      effect_type, effect_dice, effect_bonus, effect_target, charges
               FROM game_config_consumables WHERE key = ?""",
            (k,),
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    if not row:
        return False
    item_data = json.dumps({
        "effect_type": row["effect_type"],
        "effect_dice": row["effect_dice"],
        "effect_bonus": row["effect_bonus"],
        "effect_target": row["effect_target"],
        "charges": row["charges"],
    })
    _upsert(conn, {
        "key": k, "kind": "consumable",
        "label": row["label"] or "", "description": row["description"] or "",
        "price_gp": float(row["base_price"] or 0), "effect_json": None,
        "equip_slot": None,
        "rarity": int(row["rarity"] or 1), "min_level": int(row["min_level"] or 1),
        "location_tags": row["location_tags"] or "[]",
        "approved": int(row["approved"] if row["approved"] is not None else 1),
        "is_active": int(row["is_active"] if row["is_active"] is not None else 1),
        "weapon_data": "{}", "item_data": item_data,
        "weight_kg": float(row["weight_kg"] or 0), "note": row["note"],
        "locked_at": row["locked_at"],
    })
    return True


def sync_from_legacy(conn: sqlite3.Connection, table: str, key: str) -> bool:
    """Dispatcher: sync rekordu z dowolnej legacy tabeli item-kind do game_items.

    Non-fatal — łapie wyjątki, by nie wywrócić zapisu legacy. Dla tabel spoza
    LEGACY_ITEM_TABLES (spells/locations/enemies) zwraca False.
    """
    try:
        if table == "game_config_weapons":
            return upsert_from_weapon(conn, key)
        if table == "game_config_items":
            return upsert_from_item(conn, key)
        if table == "game_config_consumables":
            return upsert_from_consumable(conn, key)
    except Exception:
        return False
    return False


def delete_from_game_items(conn: sqlite3.Connection, key: str) -> None:
    """Usuń rekord z game_items (po usunięciu z legacy tabeli). Non-fatal."""
    k = str(key or "").strip()
    if not k:
        return
    try:
        conn.execute("DELETE FROM game_items WHERE key = ?", (k,))
    except sqlite3.OperationalError:
        pass


def reconcile_all(conn: sqlite3.Connection) -> int:
    """Przebuduj game_items ze wszystkich legacy tabel (idempotentny upsert).

    Wołane po imporcie katalogu (bulk DELETE+INSERT w legacy). Zwraca liczbę
    zsynchronizowanych rekordów.
    """
    n = 0
    for table, fn in (
        ("game_config_weapons", upsert_from_weapon),
        ("game_config_items", upsert_from_item),
        ("game_config_consumables", upsert_from_consumable),
    ):
        try:
            keys = [r[0] for r in conn.execute(f"SELECT key FROM {table}").fetchall()]
        except sqlite3.OperationalError:
            continue
        for k in keys:
            if fn(conn, k):
                n += 1
    return n


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
