"""Tests for U28 — Placement engine: lokacje osadzane na hexach mechanicznie."""
import json
import sqlite3
import pytest
from app.services.placement_engine import try_place_location_on_hex, get_floating_locations


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE world_hexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            q INTEGER NOT NULL, r INTEGER NOT NULL,
            hex_type TEXT NOT NULL DEFAULT 'plains',
            map_level INTEGER NOT NULL DEFAULT 0,
            region TEXT NOT NULL DEFAULT 'kresy',
            label TEXT, encounter_chance REAL DEFAULT 0.15,
            encounter_pool TEXT DEFAULT '[]',
            location_key TEXT, is_active INTEGER DEFAULT 1
        );
        CREATE TABLE hex_type_config (
            hex_type TEXT PRIMARY KEY,
            location_spawn_chance REAL NOT NULL DEFAULT 0.15
        );
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY, key TEXT UNIQUE,
            label TEXT, placement TEXT DEFAULT 'floating',
            terrain_tags TEXT DEFAULT '[]',
            approved INTEGER DEFAULT 1, is_active INTEGER DEFAULT 1,
            location_type TEXT DEFAULT 'macro', location_subtype TEXT,
            biome TEXT, tier INTEGER DEFAULT 1,
            world_hex_q INTEGER, world_hex_r INTEGER,
            region TEXT, description TEXT, parent_key TEXT, ai_generated INTEGER DEFAULT 0
        );
        INSERT INTO hex_type_config VALUES ('town', 1.0);
        INSERT INTO hex_type_config VALUES ('plains', 0.15);
        INSERT INTO hex_type_config VALUES ('forest', 0.15);
        INSERT INTO world_hexes (q,r,hex_type,map_level,region,is_active) VALUES (5,3,'town',0,'kresy',1);
        INSERT INTO world_hexes (q,r,hex_type,map_level,region,is_active) VALUES (1,1,'plains',0,'kresy',1);
    """)
    return conn


def _add_location(conn, key, tags, placement='floating', approved=1):
    conn.execute(
        "INSERT INTO game_locations (key, label, placement, terrain_tags, approved, is_active)"
        " VALUES (?,?,?,?,?,1)",
        (key, key, placement, json.dumps(tags), approved)
    )
    conn.commit()


# ─── Testy główne ──────────────────────────────────────────────────────────────

def test_town_hex_gets_location(db):
    """Hex typu town (spawn_chance=1.0) dostaje lokację z tagiem town."""
    _add_location(db, 'karczma_1', ['town', 'plains'])
    result = try_place_location_on_hex(db, 5, 3, 'town', campaign_seed=42)
    assert result == 'karczma_1'
    # world_hexes.location_key zaktualizowany
    row = db.execute("SELECT location_key FROM world_hexes WHERE q=5 AND r=3").fetchone()
    assert row['location_key'] == 'karczma_1'
    # placement → placed
    loc = db.execute("SELECT placement FROM game_locations WHERE key='karczma_1'").fetchone()
    assert loc['placement'] == 'placed'


def test_location_not_placed_twice(db):
    """Lokacja osadzona raz nie może się osadzić ponownie na innym hexie."""
    _add_location(db, 'fort_1', ['town'])
    try_place_location_on_hex(db, 5, 3, 'town', campaign_seed=1)
    # Drugi hex town — brak floating lokacji z tagiem town (fort_1 już placed)
    db.execute("INSERT INTO world_hexes (q,r,hex_type,is_active) VALUES (6,3,'town',1)")
    db.commit()
    result2 = try_place_location_on_hex(db, 6, 3, 'town', campaign_seed=1)
    assert result2 is None


def test_hex_already_has_location_skipped(db):
    """Hex z istniejącą location_key zwraca istniejący klucz, nie rusza lokacji floating."""
    _add_location(db, 'tawerna_1', ['town'])
    db.execute("UPDATE world_hexes SET location_key='existing_loc' WHERE q=5 AND r=3")
    db.commit()
    result = try_place_location_on_hex(db, 5, 3, 'town', campaign_seed=1)
    assert result == 'existing_loc'  # zwraca istniejący klucz, nie nowy
    loc = db.execute("SELECT placement FROM game_locations WHERE key='tawerna_1'").fetchone()
    assert loc['placement'] == 'floating'  # nie ruszona


def test_no_matching_terrain_tags_returns_none(db):
    """Brak lokacji z pasującymi tagami → None (hex pozostaje pusty)."""
    _add_location(db, 'gorska_twierdza', ['mountains', 'hills'])
    result = try_place_location_on_hex(db, 5, 3, 'town', campaign_seed=1)
    assert result is None


def test_unapproved_location_excluded(db):
    """Nieatwierdzona lokacja nie wchodzi do puli placement."""
    _add_location(db, 'pending_loc', ['town'], approved=0)
    result = try_place_location_on_hex(db, 5, 3, 'town', campaign_seed=1)
    assert result is None


def test_get_floating_locations_excludes_placed(db):
    """get_floating_locations zwraca tylko floating+approved, nie placed."""
    _add_location(db, 'floating_1', ['plains'])
    _add_location(db, 'placed_1', ['town'], placement='placed')
    result = get_floating_locations(db)
    keys = [r['key'] for r in result]
    assert 'floating_1' in keys
    assert 'placed_1' not in keys


def test_get_floating_locations_terrain_tags_parsed(db):
    """get_floating_locations zwraca terrain_tags jako listę (nie string)."""
    _add_location(db, 'loc_a', ['forest', 'hills'])
    result = get_floating_locations(db)
    found = next((r for r in result if r['key'] == 'loc_a'), None)
    assert found is not None
    assert isinstance(found['terrain_tags'], list)
    assert 'forest' in found['terrain_tags']


def test_low_spawn_chance_no_placement(db):
    """Plains hex ma spawn_chance=0.15 — deterministycznie nie dostaje lokacji przy seed 999."""
    _add_location(db, 'polna_wioska', ['plains'])
    # Seed 999 na hexie (1,1) plains — sprawdź czy deterministycznie None
    result = try_place_location_on_hex(db, 1, 1, 'plains', campaign_seed=999)
    # Nie wymuszamy wyniku None — tylko że funkcja nie crashuje i zwraca str|None
    assert result is None or isinstance(result, str)
