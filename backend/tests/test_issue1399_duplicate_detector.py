"""TDD: Issue #1399 — detektor duplikatów treści (skan + licznik + merge z przepinaniem referencji).

Acceptance:
- normalize_label() — lower/trim/zbite spacje
- scan_duplicates(conn) — grupy exact (pewniaki) i fuzzy (podobne nazwy) per tabela
  (items/consumables/weapons) + pary cross-table items↔consumables (informacyjnie)
- count_duplicates(conn) — liczba nadmiarowych rekordów exact (do badge)
- merge_duplicates(conn, table, keep_key, remove_keys) — przepina referencje
  (character_inventory, game_config_loot_entries, character_rentals,
  game_config_weapons.ammo_key, game_config_recipes.output_key + inputs_json)
  i usuwa duplikaty w jednej transakcji
"""
import sys
sys.path.insert(0, "/app")
from _fixtures_schema import table_sql

import json
import sqlite3
import pytest

from app.services.duplicate_service import (
    normalize_label,
    scan_duplicates,
    count_duplicates,
    merge_duplicates,
)


# ─── Fixture ─────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        table_sql("game_config_items")
        + table_sql("game_config_consumables")
        + table_sql("game_config_weapons")
        + table_sql("game_config_loot_entries")
        + """
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            item_key TEXT,
            weapon_key TEXT,
            consumable_key TEXT,
            quantity INTEGER DEFAULT 1,
            equipped INTEGER DEFAULT 0
        );
        CREATE TABLE character_rentals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            item_key TEXT
        );
        CREATE TABLE game_config_recipes (
            key TEXT PRIMARY KEY,
            label TEXT,
            inputs_json TEXT,
            output_type TEXT,
            output_key TEXT
        );
        """
    )
    yield conn
    conn.close()


def _add_item(conn, key, label, **extra):
    cols = {"key": key, "label": label}
    cols.update(extra)
    names = ", ".join(cols)
    ph = ", ".join("?" for _ in cols)
    conn.execute(f"INSERT INTO game_config_items ({names}) VALUES ({ph})", list(cols.values()))


def _add_consumable(conn, key, label):
    conn.execute("INSERT INTO game_config_consumables (key, label) VALUES (?, ?)", (key, label))


def _add_weapon(conn, key, label, **extra):
    cols = {"key": key, "label": label}
    cols.update(extra)
    names = ", ".join(cols)
    ph = ", ".join("?" for _ in cols)
    conn.execute(f"INSERT INTO game_config_weapons ({names}) VALUES ({ph})", list(cols.values()))


# ─── normalize_label ─────────────────────────────────────────────────────────

def test_normalize_label_lower_trim_collapse():
    assert normalize_label("  Miecz   Stalowy ") == "miecz stalowy"
    assert normalize_label("LUNETA") == "luneta"
    assert normalize_label(None) == ""


# ─── scan: exact groups ──────────────────────────────────────────────────────

def test_scan_exact_group_same_label(db):
    """Dwa itemy o tej samej nazwie (różna wielkość liter) → jedna grupa exact."""
    _add_item(db, "luneta_1", "Luneta")
    _add_item(db, "luneta_2", "luneta")
    _add_item(db, "unikat", "Złoty bożek")

    result = scan_duplicates(db)
    groups = result["tables"]["items"]
    exact = [g for g in groups if g["match"] == "exact"]
    assert len(exact) == 1
    keys = {r["key"] for r in exact[0]["records"]}
    assert keys == {"luneta_1", "luneta_2"}


def test_scan_clean_db_no_groups(db):
    """Backward compat: baza bez duplikatów → zero grup, licznik 0."""
    _add_item(db, "a", "Alfa")
    _add_item(db, "b", "Beta")
    result = scan_duplicates(db)
    assert result["tables"]["items"] == []
    assert result["tables"]["consumables"] == []
    assert result["tables"]["weapons"] == []
    assert result["cross"] == []
    assert count_duplicates(db) == 0


def test_count_duplicates_excess_only(db):
    """Licznik = nadmiarowe rekordy exact (grupa ×3 = 2 nadmiarowe)."""
    _add_item(db, "k1", "Czaszka demona")
    _add_item(db, "k2", "czaszka demona")
    _add_item(db, "k3", "Czaszka Demona")
    _add_consumable(db, "c1", "Mikstura leczenia")
    _add_consumable(db, "c2", "mikstura leczenia")
    assert count_duplicates(db) == 3  # 2 (items) + 1 (consumables)


# ─── scan: fuzzy groups ──────────────────────────────────────────────────────

def test_scan_fuzzy_group_similar_label(db):
    """Podobne (nie identyczne) nazwy → grupa fuzzy do ręcznej oceny."""
    _add_item(db, "mik_1", "Mikstura leczenia")
    _add_item(db, "mik_2", "Mikstura leczenia II")

    result = scan_duplicates(db)
    fuzzy = [g for g in result["tables"]["items"] if g["match"] == "fuzzy"]
    assert len(fuzzy) == 1
    keys = {r["key"] for r in fuzzy[0]["records"]}
    assert keys == {"mik_1", "mik_2"}
    # fuzzy NIE wlicza się do badge (tylko pewniaki)
    assert count_duplicates(db) == 0


def test_scan_fuzzy_not_for_distinct_labels(db):
    """Wyraźnie różne nazwy nie sklejają się w grupę."""
    _add_item(db, "a", "Luneta")
    _add_item(db, "b", "Czaszka demona")
    result = scan_duplicates(db)
    assert result["tables"]["items"] == []


# ─── scan: cross-table ───────────────────────────────────────────────────────

def test_scan_cross_table_items_consumables(db):
    """Ta sama nazwa w items i consumables → wpis w cross (informacyjny)."""
    _add_item(db, "mikstura_i", "Mikstura leczenia")
    _add_consumable(db, "mikstura_c", "mikstura leczenia")

    result = scan_duplicates(db)
    assert len(result["cross"]) == 1
    entry = result["cross"][0]
    assert "mikstura_i" in entry["item_keys"]
    assert "mikstura_c" in entry["consumable_keys"]


# ─── scan: ref counts ────────────────────────────────────────────────────────

def test_scan_records_have_ref_counts(db):
    """Każdy rekord grupy ma licznik użyć (ekwipunek + loot)."""
    _add_item(db, "luneta_1", "Luneta")
    _add_item(db, "luneta_2", "luneta")
    db.execute("INSERT INTO character_inventory (character_id, item_key) VALUES (1, 'luneta_1')")
    db.execute("INSERT INTO character_inventory (character_id, item_key) VALUES (2, 'luneta_1')")
    db.execute(
        "INSERT INTO game_config_loot_entries (loot_table_key, item_key, weight) VALUES ('lt', 'luneta_2', 50)"
    )

    result = scan_duplicates(db)
    group = result["tables"]["items"][0]
    by_key = {r["key"]: r for r in group["records"]}
    assert by_key["luneta_1"]["refs"] == 2
    assert by_key["luneta_2"]["refs"] == 1


# ─── merge ───────────────────────────────────────────────────────────────────

def test_merge_repoints_all_references_and_deletes(db):
    """Merge przepina ekwipunek, loot, wypożyczenia i przepisy, po czym usuwa duplikaty."""
    _add_item(db, "keep", "Luneta")
    _add_item(db, "dup_a", "luneta")
    _add_item(db, "dup_b", "LUNETA")
    db.execute("INSERT INTO character_inventory (character_id, item_key) VALUES (1, 'dup_a')")
    db.execute("INSERT INTO character_rentals (character_id, item_key) VALUES (1, 'dup_b')")
    db.execute(
        "INSERT INTO game_config_loot_entries (loot_table_key, item_key, weight) VALUES ('lt', 'dup_a', 50)"
    )
    db.execute(
        "INSERT INTO game_config_recipes (key, label, inputs_json, output_type, output_key) "
        "VALUES ('rec', 'Przepis', ?, 'item', 'dup_b')",
        (json.dumps([{"item_key": "dup_a", "qty": 2}]),),
    )

    summary = merge_duplicates(db, "items", "keep", ["dup_a", "dup_b"])

    assert db.execute("SELECT item_key FROM character_inventory").fetchone()[0] == "keep"
    assert db.execute("SELECT item_key FROM character_rentals").fetchone()[0] == "keep"
    assert db.execute("SELECT item_key FROM game_config_loot_entries").fetchone()[0] == "keep"
    rec = db.execute("SELECT inputs_json, output_key FROM game_config_recipes").fetchone()
    assert rec["output_key"] == "keep"
    assert json.loads(rec["inputs_json"])[0]["item_key"] == "keep"
    remaining = {r[0] for r in db.execute("SELECT key FROM game_config_items")}
    assert remaining == {"keep"}
    assert summary["deleted"] == ["dup_a", "dup_b"]


def test_merge_weapons_repoints_ammo_key(db):
    """Merge broni przepina też ammo_key innych broni."""
    _add_weapon(db, "strzaly_keep", "Strzały")
    _add_weapon(db, "strzaly_dup", "strzały")
    _add_weapon(db, "luk", "Łuk", ammo_key="strzaly_dup")
    db.execute("INSERT INTO character_inventory (character_id, weapon_key) VALUES (1, 'strzaly_dup')")

    merge_duplicates(db, "weapons", "strzaly_keep", ["strzaly_dup"])

    assert db.execute("SELECT ammo_key FROM game_config_weapons WHERE key='luk'").fetchone()[0] == "strzaly_keep"
    assert db.execute("SELECT weapon_key FROM character_inventory").fetchone()[0] == "strzaly_keep"
    remaining = {r[0] for r in db.execute("SELECT key FROM game_config_weapons")}
    assert remaining == {"strzaly_keep", "luk"}


def test_merge_rejects_bad_input(db):
    """Nieznana tabela / keep w remove_keys / nieistniejący keep → ValueError."""
    _add_item(db, "a", "Alfa")
    _add_item(db, "b", "alfa")
    with pytest.raises(ValueError):
        merge_duplicates(db, "enemies", "a", ["b"])
    with pytest.raises(ValueError):
        merge_duplicates(db, "items", "a", ["a", "b"])
    with pytest.raises(ValueError):
        merge_duplicates(db, "items", "ghost", ["b"])
