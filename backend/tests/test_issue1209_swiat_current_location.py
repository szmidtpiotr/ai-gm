"""TDD: Issue #1209 — blok ŚWIAT musi wiedzieć, że gracz jest WEWNĄTRZ lokacji.

Kampania 1000021 tury 12-14: sesja zakotwiczona w karczmie (macro), a narracja
malowała las i wypuściła graczowi słowo "hex". Dwa źródła:
- build_swiat_block nie czytał current_location — tylko teren hexa + lista POI,
- build_swiat_imperative chronił wnętrza tylko dla location_type='sub';
  macro dostawało imperatyw OUTDOOR ("opisuj OBECNY teren").
"""
import json
import sys
import sqlite3

sys.path.insert(0, "/app")


def _make_db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE world_hexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            q INTEGER, r INTEGER, hex_type TEXT DEFAULT 'forest', label TEXT,
            atmosphere TEXT, map_level INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1,
            location_key TEXT
        );
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT, label TEXT, description TEXT, location_type TEXT,
            location_subtype TEXT, biome TEXT, parent_id INTEGER, parent_key TEXT,
            world_hex_q INTEGER, world_hex_r INTEGER,
            approved INTEGER DEFAULT 1, is_active INTEGER DEFAULT 1
        );
        CREATE TABLE location_npc_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_key TEXT, npc_key TEXT, assignment_type TEXT DEFAULT 'resident',
            is_active INTEGER DEFAULT 1
        );
    """)
    db.execute("INSERT INTO world_hexes (q,r,hex_type) VALUES (38,6,'forest')")
    db.execute(
        "INSERT INTO game_locations (key,label,description,location_type,location_subtype,world_hex_q,world_hex_r) "
        "VALUES ('karczma_x','Karczma Pod Kołem','Zadymiona izba przy trakcie.','macro','tavern',38,6)"
    )
    db.commit()
    return db


_FLAGS = {"current_hex": {"q": 38, "r": 6}}


# ─── build_swiat_block ────────────────────────────────────────────────────────

def test_block_leads_with_current_location():
    from app.services.location_context_injector import build_swiat_block
    db = _make_db()
    block = build_swiat_block(db, _FLAGS, "", current_location_key="karczma_x")
    assert "GRAcz JEST W".lower() in block.lower()
    assert "Karczma Pod Kołem" in block
    assert "WEWNĄTRZ tej lokacji" in block
    # atmosfera terenu zdegradowana do otoczenia
    assert "Atmosfera terenu:" not in block
    assert "po wyjściu z lokacji" in block


def test_block_no_self_duplicate_in_poi_list():
    from app.services.location_context_injector import build_swiat_block
    db = _make_db()
    block = build_swiat_block(db, _FLAGS, "", current_location_key="karczma_x")
    assert block.count("[karczma_x]") == 1, "lokacja bieżąca nie dubluje się na liście POI"


def test_block_without_location_keeps_terrain_atmosphere():
    from app.services.location_context_injector import build_swiat_block
    db = _make_db()
    block = build_swiat_block(db, _FLAGS, "")
    assert "Atmosfera terenu:" in block
    assert "GRACZ JEST W" not in block


def test_block_always_bans_technical_words():
    from app.services.location_context_injector import build_swiat_block
    db = _make_db()
    for kwargs in ({}, {"current_location_key": "karczma_x"}):
        block = build_swiat_block(db, _FLAGS, "", **kwargs)
        assert "NIE używaj słów technicznych" in block


# ─── build_swiat_imperative ───────────────────────────────────────────────────

def test_imperative_protects_macro_location():
    from app.services.game_engine import build_swiat_imperative
    db = _make_db()
    loc_id = db.execute("SELECT id FROM game_locations WHERE key='karczma_x'").fetchone()["id"]
    imp = build_swiat_imperative(db, loc_id)
    assert "BOHATER JEST W LOKACJI" in imp
    assert "Karczma Pod Kołem" in imp
    assert "PRZEMIEŚCIŁ SIĘ" not in imp, "macro-lokacja nie może dostawać imperatywu OUTDOOR"


def test_imperative_outdoor_without_location():
    from app.services.game_engine import build_swiat_imperative
    db = _make_db()
    imp = build_swiat_imperative(db, None)
    assert "PRZEMIEŚCIŁ SIĘ" in imp


def test_imperative_protects_sub_location_still():
    from app.services.game_engine import build_swiat_imperative
    db = _make_db()
    db.execute(
        "INSERT INTO game_locations (key,label,location_type) VALUES ('izba','Izba na piętrze','sub')"
    )
    db.commit()
    loc_id = db.execute("SELECT id FROM game_locations WHERE key='izba'").fetchone()["id"]
    imp = build_swiat_imperative(db, loc_id)
    assert "BOHATER JEST W LOKACJI" in imp
