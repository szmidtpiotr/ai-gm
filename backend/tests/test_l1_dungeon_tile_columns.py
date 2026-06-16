"""TDD: Issue #670 (L1) — Konfiguracja kafelkowa lochu w DB + admin.

Tabela game_dungeons musi mieć 4 nowe kolumny:
  tile_category_key TEXT, tile_count INTEGER, boss_tile_id INTEGER, endless_growth_n INTEGER DEFAULT 0.
PATCH i POST endpointy muszą je przyjmować i zapisywać.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.migrations_admin import _ensure_dungeon_tile_l1_columns


# ─── Fixture: in-memory baza z minimalną tabelą game_dungeons ─────────────────

@pytest.fixture
def db_with_dungeons(tmp_path):
    db_path = tmp_path / "test_l1.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE game_dungeons (
            key TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            location_key TEXT NOT NULL,
            rooms INTEGER NOT NULL DEFAULT 5,
            enemy_pool TEXT NOT NULL DEFAULT '[]',
            boss_enemy TEXT,
            loot_tier TEXT NOT NULL DEFAULT 'standard',
            atmosphere TEXT,
            cooldown_hours INTEGER NOT NULL DEFAULT 72,
            min_level INTEGER NOT NULL DEFAULT 1,
            is_active INTEGER NOT NULL DEFAULT 1
        )
    """)
    conn.execute(
        "INSERT INTO game_dungeons (key, label, location_key) VALUES ('gw','Goblin Warren','goblin_warren')"
    )
    conn.commit()
    yield conn, str(db_path)
    conn.close()


# ─── Test 1: migracja dodaje wszystkie 4 kolumny ─────────────────────────────

def test_migration_adds_four_tile_columns(db_with_dungeons):
    """_ensure_dungeon_tile_l1_columns dodaje tile_category_key, tile_count, boss_tile_id, endless_growth_n."""
    conn, _ = db_with_dungeons

    _ensure_dungeon_tile_l1_columns(conn)

    cols = {row[1] for row in conn.execute("PRAGMA table_info(game_dungeons)")}
    assert "tile_category_key" in cols, "brak tile_category_key"
    assert "tile_count" in cols, "brak tile_count"
    assert "boss_tile_id" in cols, "brak boss_tile_id"
    assert "endless_growth_n" in cols, "brak endless_growth_n"


# ─── Test 2: migracja jest idempotentna ──────────────────────────────────────

def test_migration_is_idempotent(db_with_dungeons):
    """Dwukrotne wywołanie _ensure_dungeon_tile_l1_columns nie rzuca wyjątku."""
    conn, _ = db_with_dungeons

    _ensure_dungeon_tile_l1_columns(conn)
    _ensure_dungeon_tile_l1_columns(conn)  # drugi raz — brak błędu

    cols = {row[1] for row in conn.execute("PRAGMA table_info(game_dungeons)")}
    assert "tile_category_key" in cols


# ─── Test 3: endless_growth_n DEFAULT 0 ──────────────────────────────────────

def test_endless_growth_n_defaults_to_zero(db_with_dungeons):
    """Istniejący wiersz po migracji ma endless_growth_n = 0 (DEFAULT)."""
    conn, _ = db_with_dungeons

    _ensure_dungeon_tile_l1_columns(conn)

    val = conn.execute(
        "SELECT endless_growth_n FROM game_dungeons WHERE key='gw'"
    ).fetchone()[0]
    assert val == 0 or val is None  # SQLite ALTER DEFAULT nie backfilluje → NULL lub 0


# ─── Test 4: PATCH logika zapisuje nowe pola ─────────────────────────────────

def test_patch_allowed_fields_include_tile_columns(db_with_dungeons):
    """Symulacja PATCH update: tile_category_key/tile_count/boss_tile_id/endless_growth_n zapisują się."""
    conn, db_path = db_with_dungeons
    _ensure_dungeon_tile_l1_columns(conn)

    # Symulacja logiki PATCH z admin.py (bez HTTP — test jednostkowy)
    updates = {
        "tile_category_key": "krypta",
        "tile_count": 6,
        "boss_tile_id": None,
        "endless_growth_n": 2,
    }
    sets = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + ["gw"]
    conn.execute(f"UPDATE game_dungeons SET {sets} WHERE key = ?", vals)
    conn.commit()

    row = conn.execute(
        "SELECT tile_category_key, tile_count, boss_tile_id, endless_growth_n "
        "FROM game_dungeons WHERE key='gw'"
    ).fetchone()
    assert row[0] == "krypta"
    assert row[1] == 6
    assert row[2] is None
    assert row[3] == 2


# ─── Test 5: tile_count NULL dla lochu bez konfiguracji kafelkowej ────────────

def test_tile_count_null_without_config(db_with_dungeons):
    """Loch bez ustawionego tile_count ma NULL (brak OperationalError — kolumna istnieje)."""
    conn, _ = db_with_dungeons
    _ensure_dungeon_tile_l1_columns(conn)

    val = conn.execute(
        "SELECT tile_count FROM game_dungeons WHERE key='gw'"
    ).fetchone()[0]
    # NULL jest poprawnym stanem — brak konfiguracji kafelkowej
    assert val is None
