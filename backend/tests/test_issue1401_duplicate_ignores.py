"""TDD: Issue #1401 — ignorowanie fałszywych duplikatów (follow-up #1399).

Acceptance:
- ignore_duplicates(conn, table, keys) — zapisuje wszystkie pary z grupy (posortowane, idempotentnie)
- scan_duplicates/count_duplicates pomijają grupę, której WSZYSTKIE pary są zignorowane
- nowy rekord dołączający do zignorowanej grupy → grupa wraca (nie wszystkie pary zignorowane)
- cross-table (items↔consumables) też ignorowalny (table='cross')
- list_ignores / unignore(id) — podgląd i cofnięcie
"""
import sys
sys.path.insert(0, "/app")
from _fixtures_schema import table_sql

import sqlite3
import pytest

from app.services.duplicate_service import (
    scan_duplicates,
    count_duplicates,
    ignore_duplicates,
    list_ignores,
    unignore,
)


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        table_sql("game_config_items")
        + table_sql("game_config_consumables")
        + table_sql("game_config_weapons")
    )
    yield conn
    conn.close()


def _add_item(conn, key, label):
    conn.execute("INSERT INTO game_config_items (key, label) VALUES (?, ?)", (key, label))


def _add_consumable(conn, key, label):
    conn.execute("INSERT INTO game_config_consumables (key, label) VALUES (?, ?)", (key, label))


# ─── ignore: zapis par ───────────────────────────────────────────────────────

def test_ignore_stores_sorted_pairs_idempotently(db):
    """Grupa 3 rekordów → 3 pary; ponowne wywołanie nie duplikuje wpisów."""
    ignore_duplicates(db, "items", ["b", "a", "c"])
    ignore_duplicates(db, "items", ["a", "b", "c"])
    rows = list_ignores(db)
    pairs = {(r["key_a"], r["key_b"]) for r in rows}
    assert pairs == {("a", "b"), ("a", "c"), ("b", "c")}
    assert all(r["table_name"] == "items" for r in rows)


def test_ignore_rejects_bad_input(db):
    with pytest.raises(ValueError):
        ignore_duplicates(db, "enemies", ["a", "b"])
    with pytest.raises(ValueError):
        ignore_duplicates(db, "items", ["only-one"])


# ─── scan/count respektują ignorowanie ───────────────────────────────────────

def test_ignored_exact_group_hidden_and_count_drops(db):
    _add_item(db, "luneta_1", "Luneta")
    _add_item(db, "luneta_2", "luneta")
    assert count_duplicates(db) == 1

    ignore_duplicates(db, "items", ["luneta_1", "luneta_2"])

    result = scan_duplicates(db)
    assert result["tables"]["items"] == []
    assert count_duplicates(db) == 0
    assert result["excess"] == 0


def test_new_record_reopens_ignored_group(db):
    """Ignorujemy PARY, nie nazwę — trzeci rekord o tej nazwie przywraca grupę."""
    _add_item(db, "luneta_1", "Luneta")
    _add_item(db, "luneta_2", "luneta")
    ignore_duplicates(db, "items", ["luneta_1", "luneta_2"])
    _add_item(db, "luneta_3", "LUNETA")

    result = scan_duplicates(db)
    groups = [g for g in result["tables"]["items"] if g["match"] == "exact"]
    assert len(groups) == 1
    assert {r["key"] for r in groups[0]["records"]} == {"luneta_1", "luneta_2", "luneta_3"}
    assert count_duplicates(db) == 2  # grupa ×3 widoczna w całości


def test_ignored_fuzzy_group_hidden(db):
    _add_item(db, "mik_1", "Mikstura leczenia")
    _add_item(db, "mik_2", "Mikstura leczenia II")
    ignore_duplicates(db, "items", ["mik_1", "mik_2"])
    result = scan_duplicates(db)
    assert result["tables"]["items"] == []


def test_ignored_cross_entry_hidden(db):
    _add_item(db, "mikstura_i", "Mikstura leczenia")
    _add_consumable(db, "mikstura_c", "mikstura leczenia")
    assert len(scan_duplicates(db)["cross"]) == 1

    ignore_duplicates(db, "cross", ["mikstura_i", "mikstura_c"])
    assert scan_duplicates(db)["cross"] == []


# ─── unignore ────────────────────────────────────────────────────────────────

def test_unignore_restores_group(db):
    _add_item(db, "luneta_1", "Luneta")
    _add_item(db, "luneta_2", "luneta")
    ignore_duplicates(db, "items", ["luneta_1", "luneta_2"])
    assert scan_duplicates(db)["tables"]["items"] == []

    for row in list_ignores(db):
        unignore(db, row["id"])

    assert len(scan_duplicates(db)["tables"]["items"]) == 1
    assert count_duplicates(db) == 1
