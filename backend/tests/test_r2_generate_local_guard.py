"""TDD: Issue #1242 (R2) — Admin "Generuj mapę lokalną" nie może niszczyć osady.

POST /api/admin/world/generate-local kasował wszystkie map_level=1 sub-hexy
rodzica bez sprawdzenia location_key — wymazując wygenerowaną mapę osady
(FAZA ML). Po naprawie:
  - sub-hexy z location_key + brak force → 409,
  - force=true → wyczyszczenie session_flags.local_hex sesji wskazujących
    kasowane wiersze,
  - nowe sub-hexy dziedziczą region rodzica.
"""
import sys
import json
import sqlite3

import pytest
from fastapi import HTTPException

sys.path.insert(0, "/app")

SCHEMA = """
CREATE TABLE IF NOT EXISTS world_hexes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    q INTEGER NOT NULL,
    r INTEGER NOT NULL,
    hex_type TEXT NOT NULL DEFAULT 'plains',
    label TEXT,
    atmosphere TEXT,
    encounter_chance REAL NOT NULL DEFAULT 0.0,
    encounter_pool TEXT NOT NULL DEFAULT '[]',
    location_key TEXT,
    region TEXT,
    discovered_in_campaign_id INTEGER,
    created_by_gm INTEGER NOT NULL DEFAULT 0,
    created_by_campaign_id INTEGER,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    parent_hex_id INTEGER,
    map_level INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS hex_type_config (
    hex_type TEXT PRIMARY KEY,
    label TEXT,
    map_icon TEXT,
    map_color TEXT,
    spawn_weight REAL NOT NULL DEFAULT 1.0,
    encounter_base_chance REAL NOT NULL DEFAULT 0.0,
    has_submap INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS game_sessions (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER,
    current_location_id INTEGER,
    session_flags TEXT NOT NULL DEFAULT '{}'
);
"""

PARENT_REGION = "wachtenberg"


@pytest.fixture
def dbfile(tmp_path):
    """Temp file DB: a parent hub hex with a 3-hex settlement local map."""
    path = str(tmp_path / "r2.db")
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    c.execute(
        "INSERT INTO hex_type_config (hex_type, spawn_weight, encounter_base_chance, is_active)"
        " VALUES ('plains', 1.0, 0.1, 1)"
    )
    # Parent hub hex (map_level=0) in region 'wachtenberg'
    c.execute(
        "INSERT INTO world_hexes (id, q, r, hex_type, region, parent_hex_id, map_level, is_active)"
        " VALUES (100, 10, 10, 'plains', ?, NULL, 0, 1)",
        (PARENT_REGION,),
    )
    # Settlement local map: 3 sub-hexes WITH location_key
    for i, lk in enumerate(["rynek", "karczma", "kuznia"], start=1):
        c.execute(
            "INSERT INTO world_hexes (id, q, r, hex_type, location_key, parent_hex_id, map_level, is_active)"
            " VALUES (?, ?, 0, 'plains', ?, 100, 1, 1)",
            (200 + i, i, lk),
        )
    # A player session standing on sub-hex 201
    c.execute(
        "INSERT INTO game_sessions (id, campaign_id, session_flags) VALUES (1, 1, ?)",
        (json.dumps({"local_hex": {"hex_id": 201, "q": 1, "r": 0, "location_key": "rynek"}}),),
    )
    c.commit()
    c.close()
    return path


def _call_generate_local(dbfile, monkeypatch, force=False):
    from app.routers import hex_world

    def _fake_db():
        cc = sqlite3.connect(dbfile)
        cc.row_factory = sqlite3.Row
        return cc

    monkeypatch.setattr(hex_world, "_get_db", _fake_db)
    monkeypatch.setattr(hex_world, "_require_admin", lambda *a, **k: None)

    body = hex_world.LocalGenRequest(parent_q=10, parent_r=10, seed=1, radius=2, force=force)
    return hex_world.generate_local(body, authorization="Bearer test")


def test_generate_local_refuses_settlement_without_force(dbfile, monkeypatch):
    """Sub-hexy z location_key + brak force → 409."""
    with pytest.raises(HTTPException) as ei:
        _call_generate_local(dbfile, monkeypatch, force=False)
    assert ei.value.status_code == 409
    assert "sublokacji" in ei.value.detail

    # Settlement untouched
    c = sqlite3.connect(dbfile)
    n = c.execute(
        "SELECT COUNT(*) FROM world_hexes WHERE parent_hex_id=100 AND location_key IS NOT NULL"
    ).fetchone()[0]
    c.close()
    assert n == 3, "osada nie może być tknięta przy odmowie"


def test_generate_local_force_clears_local_hex_and_inherits_region(dbfile, monkeypatch):
    """force=true → osada nadpisana, sesja bez martwego local_hex, region dziedziczony."""
    res = _call_generate_local(dbfile, monkeypatch, force=True)
    assert res["hexes_created"] > 0

    c = sqlite3.connect(dbfile)
    c.row_factory = sqlite3.Row

    # Session no longer points at a deleted hex
    flags = json.loads(
        c.execute("SELECT session_flags FROM game_sessions WHERE id=1").fetchone()["session_flags"]
    )
    assert "local_hex" not in flags, f"local_hex wskazujący kasowany wiersz musi być wyczyszczony, mam: {flags}"

    # Old settlement sub-hexes gone
    old = c.execute("SELECT COUNT(*) FROM world_hexes WHERE id IN (201,202,203)").fetchone()[0]
    assert old == 0, "stare sub-hexy osady powinny zniknąć"

    # New sub-hexes inherit parent region
    regions = {
        r["region"]
        for r in c.execute(
            "SELECT DISTINCT region FROM world_hexes WHERE parent_hex_id=100 AND map_level=1"
        ).fetchall()
    }
    c.close()
    assert regions == {PARENT_REGION}, f"nowe sub-hexy muszą dziedziczyć region rodzica, mam: {regions}"
