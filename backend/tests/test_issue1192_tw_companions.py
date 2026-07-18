"""#1192 FAZA TW — towarzysze podróży + wierzchowce.

Covers TW1 (schema+seeds), TW2 (hire/buy/dismiss/grant/slots), TW3 (upkeep),
TW5 (travel multiplier gated by riding), TW6 (encounter chance), TW7 (escape),
TW8 (combat companion builder + death).
"""
import json
import sqlite3

import pytest

from app.migrations_admin import _ensure_companions_schema
from app.services import companion_service as cs


def _mk_char(conn, cid=1, gold=100, dex=14, riding=0):
    sheet = {"stats": {"STR": 12, "DEX": dex, "CON": 12, "INT": 10, "WIS": 10, "CHA": 10},
             "skills": {"riding": riding}}
    conn.execute(
        "INSERT INTO characters (id, campaign_id, user_id, name, system_id, sheet_json, gold_gp) "
        "VALUES (?,?,?,?,?,?,?)",
        (cid, None, 1, "Test", "fantasy", json.dumps(sheet), gold),
    )
    conn.commit()


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    # minimal characters table (subset of prod schema)
    c.execute(
        """CREATE TABLE characters (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
            name TEXT, system_id TEXT, sheet_json TEXT NOT NULL DEFAULT '{}',
            gold_gp INTEGER NOT NULL DEFAULT 0
        )"""
    )
    c.execute(
        """CREATE TABLE game_locations (
            key TEXT PRIMARY KEY, label TEXT, location_subtype TEXT,
            safe_for_rest INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1, region TEXT
        )"""
    )
    _ensure_companions_schema(c)
    _mk_char(c)
    return c


# ── TW1 schema + seeds ──────────────────────────────────────────────────────

def test_tw1_seeds_present(conn):
    rows = {r["key"]: r for r in conn.execute("SELECT * FROM game_config_companions")}
    assert {"horse", "mule", "dog_tracker", "mercenary", "tracker"} <= set(rows)
    # Mounts never carry an attack profile.
    assert rows["horse"]["attack_json"] is None
    assert rows["mule"]["attack_json"] is None
    # Combat types do.
    assert rows["mercenary"]["attack_json"] is not None
    # created_by seed for content-as-code.
    assert all(r["created_by"] == "seed" for r in rows.values())


# ── TW2 hire / buy / slots / dismiss / grant ────────────────────────────────

def test_tw2_hire_deducts_gold(conn):
    res = cs.hire(conn, 1, "mercenary")
    assert res["paid_gp"] == 5
    assert conn.execute("SELECT gold_gp FROM characters WHERE id=1").fetchone()[0] == 95
    active = cs.get_active_companions(conn, 1)
    assert len(active) == 1 and active[0]["ownership"] == "hired"


def test_tw2_buy_owned(conn):
    res = cs.buy(conn, 1, "horse", custom_name="Cień")
    assert res["paid_gp"] == 60
    m = cs.get_active_mount(conn, 1)
    assert m and m["name"] == "Cień" and m["ownership"] == "owned"


def test_tw2_mount_not_hireable_but_buyable(conn):
    # horse has daily_cost>0 so hireable too; mercenary has buy_cost NULL → not buyable
    with pytest.raises(ValueError, match="not_buyable"):
        cs.buy(conn, 1, "mercenary")


def test_tw2_slot_occupied_same_kind(conn):
    cs.hire(conn, 1, "mercenary")
    with pytest.raises(ValueError, match="slot_occupied"):
        cs.hire(conn, 1, "tracker")  # both combat slot


def test_tw2_mount_and_combat_are_separate_slots(conn):
    cs.buy(conn, 1, "horse")
    cs.hire(conn, 1, "mercenary")  # different slot → allowed
    assert len(cs.get_active_companions(conn, 1)) == 2


def test_tw2_insufficient_gold(conn):
    conn.execute("UPDATE characters SET gold_gp = 2 WHERE id=1")
    with pytest.raises(ValueError, match="insufficient_gold"):
        cs.buy(conn, 1, "horse")


def test_tw2_grant_no_charge(conn):
    cs.grant_companion(conn, 1, "horse", source="quest")
    assert conn.execute("SELECT gold_gp FROM characters WHERE id=1").fetchone()[0] == 100
    assert cs.get_active_mount(conn, 1) is not None


def test_tw2_dismiss(conn):
    r = cs.hire(conn, 1, "mercenary")
    cs.dismiss(conn, 1, r["id"])
    assert cs.get_active_companions(conn, 1) == []


# ── TW3 upkeep ──────────────────────────────────────────────────────────────

def test_tw3_hired_daily_deduction(conn):
    cs.hire(conn, 1, "mercenary", day=1)
    cs.run_daily_upkeep(conn, 1, day=2)
    # hire paid 5 up front on day1, upkeep 5 on day2 → 90
    assert conn.execute("SELECT gold_gp FROM characters WHERE id=1").fetchone()[0] == 90


def test_tw3_hired_walks_after_unpaid(conn):
    cs.hire(conn, 1, "mercenary", day=1)  # -5 → 95
    conn.execute("UPDATE characters SET gold_gp = 0 WHERE id=1")
    cs.run_daily_upkeep(conn, 1, day=2)   # unpaid 1
    assert cs.get_active_combat_companion(conn, 1) is not None
    cs.run_daily_upkeep(conn, 1, day=3)   # unpaid 2 → dismissed
    assert cs.get_active_combat_companion(conn, 1) is None


def test_tw3_owned_mount_underfed_not_dismissed(conn):
    cs.buy(conn, 1, "horse", day=1)  # -60
    conn.execute("UPDATE characters SET gold_gp = 0 WHERE id=1")
    cs.run_daily_upkeep(conn, 1, day=2)
    cs.run_daily_upkeep(conn, 1, day=3)
    m = cs.get_active_mount(conn, 1)
    assert m is not None and m["underfed"] is True


def test_tw3_idempotent_same_day(conn):
    cs.hire(conn, 1, "mercenary", day=1)
    cs.run_daily_upkeep(conn, 1, day=2)
    g = conn.execute("SELECT gold_gp FROM characters WHERE id=1").fetchone()[0]
    cs.run_daily_upkeep(conn, 1, day=2)  # no double charge
    assert conn.execute("SELECT gold_gp FROM characters WHERE id=1").fetchone()[0] == g


def test_tw3_stabled_covers_feed(conn):
    cs.buy(conn, 1, "horse", day=1)
    g = conn.execute("SELECT gold_gp FROM characters WHERE id=1").fetchone()[0]
    cs.run_daily_upkeep(conn, 1, day=2, stabled=True)
    assert conn.execute("SELECT gold_gp FROM characters WHERE id=1").fetchone()[0] == g


# ── TW5 travel multiplier gated by riding ───────────────────────────────────

def test_tw5_horse_speed_by_rank(conn):
    cs.buy(conn, 1, "horse")
    assert cs.get_travel_multiplier(conn, 1) == pytest.approx(0.85)  # R0
    conn.execute("UPDATE characters SET sheet_json = ? WHERE id=1",
                 (json.dumps({"stats": {"DEX": 14}, "skills": {"riding": 3}}),))
    assert cs.get_travel_multiplier(conn, 1) == pytest.approx(0.65)  # R3


def test_tw5_underfed_no_bonus(conn):
    cs.buy(conn, 1, "horse")
    conn.execute("UPDATE character_companions SET underfed = 1")
    assert cs.get_travel_multiplier(conn, 1) == pytest.approx(1.0)


def test_tw5_cap_bonus(conn):
    assert cs.get_daily_cap_bonus(conn, 1) == 0.0
    cs.buy(conn, 1, "horse")
    assert cs.get_daily_cap_bonus(conn, 1) == pytest.approx(2.0)


def test_tw5_tracker_forest(conn):
    cs.hire(conn, 1, "tracker")
    assert cs.get_travel_multiplier(conn, 1, hex_type="las") == pytest.approx(0.8)
    assert cs.get_travel_multiplier(conn, 1, hex_type="gory") == pytest.approx(1.0)


# ── TW6 encounter chance ────────────────────────────────────────────────────

def test_tw6_dog_lowers_encounter(conn):
    assert cs.get_encounter_chance_mult(conn, 1) == pytest.approx(1.0)
    cs.hire(conn, 1, "dog_tracker")
    assert cs.get_encounter_chance_mult(conn, 1) == pytest.approx(0.8)


# ── TW7 mounted escape ──────────────────────────────────────────────────────

def test_tw7_escape_dc_scales_with_tier(conn):
    cs.buy(conn, 1, "horse")
    r = cs.resolve_mount_escape(conn, 1, enemy_tier=3)
    assert r["dc"] == 16  # 10 + 2*3
    assert "escaped" in r


def test_tw7_escape_requires_mount(conn):
    assert cs.can_escape_mounted(conn, 1) is False
    cs.buy(conn, 1, "horse")
    assert cs.can_escape_mounted(conn, 1) is True


def test_tw7_underfed_cannot_escape(conn):
    cs.buy(conn, 1, "horse")
    conn.execute("UPDATE character_companions SET underfed = 1")
    assert cs.can_escape_mounted(conn, 1) is False


# ── TW8 combat companion ────────────────────────────────────────────────────

def test_tw8_build_combatant(conn):
    cs.hire(conn, 1, "mercenary")
    comb = cs.build_companion_combatant(conn, 1)
    assert comb["type"] == "companion"
    assert comb["owner_id"] == "player"
    assert comb["damage_dice"] == "1d6"
    assert comb["zone"] == "engaged"


def test_tw8_mount_never_combatant(conn):
    cs.buy(conn, 1, "horse")
    assert cs.build_companion_combatant(conn, 1) is None


def test_tw8_death_is_permanent(conn):
    r = cs.hire(conn, 1, "mercenary")
    comb = cs.build_companion_combatant(conn, 1)
    cs.sync_companion_hp(conn, 1, comb["companion_row_id"], 0)
    assert cs.get_active_combat_companion(conn, 1) is None
    row = conn.execute("SELECT state FROM character_companions WHERE id=?", (r["id"],)).fetchone()
    assert row["state"] == "dead"


def test_tw8_hp_sync_survive(conn):
    cs.hire(conn, 1, "mercenary")
    comb = cs.build_companion_combatant(conn, 1)
    cs.sync_companion_hp(conn, 1, comb["companion_row_id"], 7)
    assert cs.get_active_combat_companion(conn, 1)["current_hp"] == 7
