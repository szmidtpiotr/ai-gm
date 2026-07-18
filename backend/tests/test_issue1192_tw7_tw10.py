"""#1192 FAZA TW — TW7 ucieczka konno z encountera + TW10 admin CRUD katalogu.

TW7: resolve_travel_escape czyta pending encounter z session_flags.travel_plan,
mapuje tier wroga, rozlicza test Jeździectwa; sukces → combat_seen=True (walki nie
ma). TW10: admin_create/update/delete + campaign_companions.
"""
import json
import sqlite3

import pytest

from app.migrations_admin import _ensure_companions_schema
from app.services import companion_service as cs


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER, name TEXT,
            system_id TEXT, sheet_json TEXT DEFAULT '{}', gold_gp INTEGER DEFAULT 0
        );
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, session_flags TEXT
        );
        CREATE TABLE game_config_enemies (key TEXT PRIMARY KEY, tier TEXT);
        """
    )
    _ensure_companions_schema(c)
    sheet = {"stats": {"DEX": 14}, "skills": {"riding": 3}}
    c.execute("INSERT INTO characters (id, campaign_id, name, system_id, sheet_json, gold_gp) "
              "VALUES (1, 50, 'Hero', 'fantasy', ?, 100)", (json.dumps(sheet),))
    c.execute("INSERT INTO game_config_enemies (key, tier) VALUES ('goblin','weak'),('ogre','elite')")
    c.commit()
    return c


def _seed_encounter(conn, enemy_key="goblin"):
    tp = {"interrupt_reason": "encounter", "enemy_key": enemy_key, "combat_seen": False}
    conn.execute("INSERT INTO game_sessions (campaign_id, session_flags) VALUES (50, ?)",
                 (json.dumps({"travel_plan": tp}),))
    conn.commit()


# ── TW7 ─────────────────────────────────────────────────────────────────────

def test_tw7_escape_requires_encounter(conn):
    cs.buy(conn, 1, "horse")
    with pytest.raises(ValueError, match="no_encounter"):
        cs.resolve_travel_escape(conn, 50, 1)


def test_tw7_escape_requires_mount(conn):
    _seed_encounter(conn)
    with pytest.raises(ValueError, match="no_mount"):
        cs.resolve_travel_escape(conn, 50, 1)


def test_tw7_tier_maps_to_dc(conn):
    cs.buy(conn, 1, "horse")
    _seed_encounter(conn, "ogre")  # elite → tier 3 → DC 16
    r = cs.resolve_travel_escape(conn, 50, 1)
    assert r["dc"] == 16 and r["enemy_tier"] == 3 and r["enemy_key"] == "ogre"


def test_tw7_success_sets_combat_seen(conn):
    cs.buy(conn, 1, "horse")  # riding R3 + DEX14 vs weak DC12 → very likely escape
    _seed_encounter(conn, "goblin")
    r = cs.resolve_travel_escape(conn, 50, 1)
    sf = json.loads(conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=50").fetchone()[0])
    if r["escaped"]:
        assert sf["travel_plan"]["combat_seen"] is True
    else:
        assert sf["travel_plan"]["combat_seen"] is False  # walka ruszy


def test_tw7_underfed_mount_cannot_escape(conn):
    cs.buy(conn, 1, "horse")
    conn.execute("UPDATE character_companions SET underfed = 1")
    _seed_encounter(conn)
    with pytest.raises(ValueError, match="no_mount"):
        cs.resolve_travel_escape(conn, 50, 1)


# ── TW10 admin CRUD ─────────────────────────────────────────────────────────

def test_tw10_admin_create(conn):
    item = cs.admin_create(conn, {
        "key": "war_horse", "label": "Koń bojowy", "type": "mount", "hp_base": 25,
        "buy_cost": 120, "passive_json": '{"travel_speed_mult":0.7}',
    })
    assert item["key"] == "war_horse" and item["created_by"] == "admin"


def test_tw10_admin_create_rejects_bad_key(conn):
    with pytest.raises(ValueError, match="invalid_key"):
        cs.admin_create(conn, {"key": "Bad Key!", "label": "x", "type": "mount"})


def test_tw10_admin_create_rejects_bad_json(conn):
    with pytest.raises(ValueError, match="invalid_passive_json"):
        cs.admin_create(conn, {"key": "k1", "label": "x", "type": "mount",
                               "passive_json": "{not json"})


def test_tw10_admin_duplicate(conn):
    with pytest.raises(ValueError, match="companion_exists"):
        cs.admin_create(conn, {"key": "horse", "label": "dup", "type": "mount"})


def test_tw10_admin_update(conn):
    cs.admin_update(conn, "horse", {"buy_cost": 99})
    row = conn.execute("SELECT buy_cost FROM game_config_companions WHERE key='horse'").fetchone()
    assert row["buy_cost"] == 99


def test_tw10_admin_delete(conn):
    cs.admin_delete(conn, "mule")
    assert conn.execute("SELECT 1 FROM game_config_companions WHERE key='mule'").fetchone() is None


def test_tw10_campaign_monitor(conn):
    cs.buy(conn, 1, "horse")
    cs.hire(conn, 1, "mercenary")
    out = cs.campaign_companions(conn, 50)
    assert len(out) == 2
    assert all(c["character_id"] == 1 for c in out)
