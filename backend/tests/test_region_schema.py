"""TDD: RM1 (#1028) — kolumna region + tabela world_regions.

Weryfikuje że migracja RM1 (_ensure_region_schema) poprawnie dodała:
- world_hexes.region (NOT NULL, DEFAULT 'kresy')
- game_locations.region (nullable)
- tabela world_regions z 6 wierszami (Kresy=live, reszta coming)
- indeksy idx_world_hexes_region_scope + idx_world_hexes_region_level
"""
import os
import sqlite3

import pytest

REAL_DB = "/data/ai_gm.db"


@pytest.fixture(scope="module")
def db():
    if not os.path.exists(REAL_DB):
        pytest.skip("brak realnej DB (/data/ai_gm.db) — test tylko w kontenerze")
    conn = sqlite3.connect(REAL_DB)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def _columns(conn, table: str) -> set[str]:
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def _indexes(conn, table: str) -> set[str]:
    return {r["name"] for r in conn.execute(f"PRAGMA index_list({table})")}


# ─── world_hexes ─────────────────────────────────────────────────────────────

def test_world_hexes_has_region_column(db):
    assert "region" in _columns(db, "world_hexes"), \
        "world_hexes nie ma kolumny region — migracja RM1 nie zadziałała"


def test_world_hexes_region_default_kresy(db):
    """Wszystkie istniejące heksy mają region='kresy' (DEFAULT stosuje się do ADD COLUMN)."""
    row = db.execute(
        "SELECT count(*) AS cnt FROM world_hexes WHERE map_level=0 AND region != 'kresy'"
    ).fetchone()
    assert row["cnt"] == 0, f"{row['cnt']} heksów map_level=0 ma region != 'kresy'"


def test_world_hexes_count_unchanged(db):
    """Migracja nie usunęła żadnych heksów (oczekiwane ~2498-2500)."""
    row = db.execute("SELECT count(*) AS cnt FROM world_hexes WHERE map_level=0").fetchone()
    assert row["cnt"] >= 2490, f"Za mało heksów map_level=0: {row['cnt']}"


def test_world_hexes_region_scope_index(db):
    assert "idx_world_hexes_region_scope" in _indexes(db, "world_hexes"), \
        "brak indeksu idx_world_hexes_region_scope na world_hexes"


def test_world_hexes_region_level_index(db):
    assert "idx_world_hexes_region_level" in _indexes(db, "world_hexes"), \
        "brak indeksu idx_world_hexes_region_level na world_hexes"


# ─── game_locations ──────────────────────────────────────────────────────────

def test_game_locations_has_region_column(db):
    assert "region" in _columns(db, "game_locations"), \
        "game_locations nie ma kolumny region — migracja RM1 nie zadziałała"


# ─── world_regions ───────────────────────────────────────────────────────────

def test_world_regions_table_exists(db):
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='world_regions'"
    ).fetchone()
    assert row is not None, "tabela world_regions nie istnieje"


def test_world_regions_has_6_rows(db):
    row = db.execute("SELECT count(*) AS cnt FROM world_regions").fetchone()
    assert row["cnt"] == 6, f"world_regions powinna mieć 6 wierszy, ma {row['cnt']}"


def test_world_regions_kresy_is_live(db):
    row = db.execute("SELECT status FROM world_regions WHERE key='kresy'").fetchone()
    assert row is not None, "brak wpisu kresy w world_regions"
    assert row["status"] == "live", f"Kresy.status={row['status']!r}, oczekiwano 'live'"


def test_world_regions_others_are_coming(db):
    rows = db.execute(
        "SELECT key, status FROM world_regions WHERE key != 'kresy'"
    ).fetchall()
    assert len(rows) == 5, f"Oczekiwano 5 krain poza Kresami, jest {len(rows)}"
    bad = [r["key"] for r in rows if r["status"] != "coming"]
    assert not bad, f"Te krainy mają status != 'coming': {bad}"


def test_world_regions_all_keys_present(db):
    expected = {"kresy", "koronne_niziny", "czarnobor", "siwe_granie", "wybrzeze_lez", "martwe_pustkowia"}
    rows = db.execute("SELECT key FROM world_regions").fetchall()
    actual = {r["key"] for r in rows}
    assert actual == expected, f"Brakujące/nadmiarowe klucze krain: diff={actual ^ expected}"
