"""TDD: Issue #739 — min_level gating dla lochów.

Weryfikuje:
- _get_hero_level() wyprowadza poziom z lifetime XP (kanonicznie, jak frontend)
- enter_dungeon() zwraca 403 (level_too_low) gdy hero_level < dungeon.min_level
- enter_dungeon() przepuszcza bohatera na/powyżej min_level (gate nie odpala)
"""
from __future__ import annotations
from _fixtures_schema import table_sql

import json
import sqlite3
from unittest.mock import patch

import pytest
from fastapi import HTTPException


SCHEMA = """
CREATE TABLE characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    sheet_json TEXT DEFAULT '{}'
);

CREATE TABLE game_dungeons (
    key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    tile_category_key TEXT,
    tile_count INTEGER,
    min_level INTEGER DEFAULT 1,
    cooldown_hours INTEGER DEFAULT 72,
    is_active INTEGER DEFAULT 1
);

""" + table_sql("game_config_meta") + """
"""


@pytest.fixture
def db(tmp_path):
    db_file = tmp_path / "test_739.db"
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)

    # Deep dungeon: requires level 3
    conn.execute(
        "INSERT INTO game_dungeons (key, label, tile_category_key, tile_count, min_level) "
        "VALUES ('katakumby_mroku', 'Katakumby Mroku', 'cat', 7, 3)"
    )
    # Onboarding dungeon: level 1
    conn.execute(
        "INSERT INTO game_dungeons (key, label, tile_category_key, tile_count, min_level) "
        "VALUES ('krypta_probna', 'Krypta Próbna', 'cat', 4, 1)"
    )
    # dungeon_enabled flag (default True)
    conn.execute(
        "INSERT INTO game_config_meta (key, value) VALUES ('game_mode_flags', ?)",
        (json.dumps({"dungeon_enabled": True}),),
    )
    # Hero lvl 1 (0 lifetime XP) and hero lvl 3 (250 XP → flat 100/lvl = lvl 3)
    conn.execute(
        "INSERT INTO characters (id, user_id, sheet_json) VALUES (1, 1, ?)",
        (json.dumps({"xp_lifetime_earned": 0, "level": 1}),),
    )
    conn.execute(
        "INSERT INTO characters (id, user_id, sheet_json) VALUES (2, 1, ?)",
        (json.dumps({"xp_lifetime_earned": 250, "level": 1}),),  # stale level=1, XP→lvl3
    )
    conn.commit()
    yield conn, str(db_file)
    conn.close()


def _patch_db(db_path: str):
    from app.api import dungeons
    from app.services import dungeon_service as ds
    dungeons.DB_PATH = db_path
    ds.DB_PATH = db_path
    return dungeons


# ─── Test 1: _get_hero_level wyprowadza poziom z lifetime XP ──────────────────

def test_hero_level_derived_from_xp(db):
    """_get_hero_level() używa xp_lifetime_earned, nie przestarzałego sheet.level."""
    conn, db_path = db
    dungeons = _patch_db(db_path)

    # Hero 2 ma sheet.level=1, ale 250 XP → kanonicznie poziom 3
    with patch("app.services.xp_service.get_xp_level_thresholds", return_value=None):
        assert dungeons._get_hero_level(2) == 3, \
            "Poziom powinien być wyprowadzony z XP (250 → lvl3), nie ze stale level=1"
        assert dungeons._get_hero_level(1) == 1


# ─── Test 2: lvl1 → 403 przy wejściu do lochu min_level=3 ────────────────────

def test_enter_403_when_below_min_level(db):
    """Bohater Poz.1 wchodzący do Katakumby Mroku (min_level=3) → 403 level_too_low."""
    conn, db_path = db
    dungeons = _patch_db(db_path)

    req = dungeons.DungeonEnterReq(character_id=1, campaign_id=99)
    with patch("app.services.xp_service.get_xp_level_thresholds", return_value=None):
        with pytest.raises(HTTPException) as exc_info:
            dungeons.enter_dungeon("katakumby_mroku", req)

    assert exc_info.value.status_code == 403, \
        f"Oczekiwano 403, got: {exc_info.value.status_code}"
    detail = exc_info.value.detail
    assert isinstance(detail, dict) and detail.get("error") == "level_too_low", \
        f"detail.error powinno być 'level_too_low', got: {detail!r}"
    assert detail.get("min_level") == 3
    assert detail.get("hero_level") == 1


# ─── Test 3: lvl3+ przechodzi przez gate (nie podnosi 403) ───────────────────

def test_enter_passes_gate_when_at_min_level(db):
    """Bohater Poz.3 NIE dostaje 403 — gate przepuszcza, wejście leci dalej."""
    conn, db_path = db
    dungeons = _patch_db(db_path)

    req = dungeons.DungeonEnterReq(character_id=2, campaign_id=99)

    fake_instance = {
        "dungeon_label": "Katakumby Mroku",
        "graph": {"entry_node": "main_0", "nodes": {"main_0": {"content": {}}}},
    }
    with patch("app.services.xp_service.get_xp_level_thresholds", return_value=None), \
         patch("app.services.dungeon_tile_service.enter_dungeon_tiles", return_value=fake_instance), \
         patch.object(dungeons, "_save_dungeon_entry_snapshot", return_value=None):
        resp = dungeons.enter_dungeon("katakumby_mroku", req)

    assert resp["ok"] is True, "Wejście powinno się powieść dla bohatera Poz.3"
    assert resp["dungeon_run"] is fake_instance


# ─── Test 4: lvl1 wchodzi do lochu onboardingowego (min_level=1) ─────────────

def test_enter_onboarding_dungeon_ok_for_lvl1(db):
    """Bohater Poz.1 może wejść do krypta_probna (min_level=1) — gate nie blokuje."""
    conn, db_path = db
    dungeons = _patch_db(db_path)

    req = dungeons.DungeonEnterReq(character_id=1, campaign_id=99)

    fake_instance = {
        "dungeon_label": "Krypta Próbna",
        "graph": {"entry_node": "main_0", "nodes": {"main_0": {"content": {}}}},
    }
    with patch("app.services.xp_service.get_xp_level_thresholds", return_value=None), \
         patch("app.services.dungeon_tile_service.enter_dungeon_tiles", return_value=fake_instance), \
         patch.object(dungeons, "_save_dungeon_entry_snapshot", return_value=None):
        resp = dungeons.enter_dungeon("krypta_probna", req)

    assert resp["ok"] is True
