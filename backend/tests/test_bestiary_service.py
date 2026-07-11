"""TDD: #1191 E1 — Bestiariusz: per-character kill counters per enemy type.

Kills aggregate per (character_id, enemy_key). Tier derived from kills:
1 kill → tier 1, 5 → tier 2 (HP preview), 15 → tier 3 (+1 to-hit).
Recording a kill must never raise (combat-safe). MP credits only the killer.
"""
import sqlite3
import pytest

from app.services import bestiary_service as bs


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute(
        """
        CREATE TABLE character_bestiary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            enemy_key TEXT NOT NULL,
            kills INTEGER NOT NULL DEFAULT 0,
            first_kill_at TEXT,
            last_kill_at TEXT,
            unlocked_tier INTEGER NOT NULL DEFAULT 0,
            UNIQUE(character_id, enemy_key)
        )
        """
    )
    c.execute(
        """
        CREATE TABLE game_config_enemies (
            key TEXT PRIMARY KEY, label TEXT, description TEXT,
            lore_text TEXT, image_url TEXT, hp_base INTEGER, tier TEXT
        )
        """
    )
    c.executemany(
        "INSERT INTO game_config_enemies (key,label,description,hp_base,tier) VALUES (?,?,?,?,?)",
        [("goblin", "Goblin", "Mały drań", 12, "1"),
         ("orc", "Ork", "Duży drań", 30, "2")],
    )
    c.commit()
    yield c
    c.close()


# ─── tier derivation ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("kills,tier", [(0, 0), (1, 1), (4, 1), (5, 2), (14, 2), (15, 3), (99, 3)])
def test_tier_for_kills(kills, tier):
    assert bs.tier_for_kills(kills) == tier


# ─── record_kill ─────────────────────────────────────────────────────────────

def test_first_kill_creates_tier1(conn):
    r = bs.record_kill(7, "goblin", conn=conn)
    assert r == {"kills": 1, "unlocked_tier": 1, "tier_up": True}
    assert bs.get_entry_tier(7, "goblin", conn=conn) == 1


def test_kills_accumulate_upsert(conn):
    for _ in range(5):
        bs.record_kill(7, "goblin", conn=conn)
    row = conn.execute(
        "SELECT kills, unlocked_tier FROM character_bestiary "
        "WHERE character_id=7 AND enemy_key='goblin'").fetchone()
    assert row["kills"] == 5
    assert row["unlocked_tier"] == 2


def test_tier_up_flag_only_on_threshold(conn):
    ups = [bs.record_kill(7, "goblin", conn=conn)["tier_up"] for _ in range(6)]
    # tier_up at kill #1 (t1) and #5 (t2), not #2,3,4,6
    assert ups == [True, False, False, False, True, False]


def test_tier3_at_15_kills(conn):
    for _ in range(15):
        bs.record_kill(7, "orc", conn=conn)
    assert bs.get_entry_tier(7, "orc", conn=conn) == 3
    assert bs.hunter_hit_bonus(7, "orc", conn=conn) == 1


def test_hunter_bonus_zero_below_tier3(conn):
    for _ in range(14):
        bs.record_kill(7, "orc", conn=conn)
    assert bs.hunter_hit_bonus(7, "orc", conn=conn) == 0


def test_kills_isolated_per_character_and_enemy(conn):
    bs.record_kill(7, "goblin", conn=conn)
    bs.record_kill(7, "goblin", conn=conn)
    bs.record_kill(8, "goblin", conn=conn)
    bs.record_kill(7, "orc", conn=conn)
    assert conn.execute("SELECT kills FROM character_bestiary WHERE character_id=7 AND enemy_key='goblin'").fetchone()["kills"] == 2
    assert conn.execute("SELECT kills FROM character_bestiary WHERE character_id=8 AND enemy_key='goblin'").fetchone()["kills"] == 1
    assert conn.execute("SELECT kills FROM character_bestiary WHERE character_id=7 AND enemy_key='orc'").fetchone()["kills"] == 1


# ─── combat-safe no-ops (must never raise) ───────────────────────────────────

@pytest.mark.parametrize("cid,ek", [(None, "goblin"), ("", "goblin"), (7, ""), (7, None), (7, 123)])
def test_record_kill_noop_on_bad_input(conn, cid, ek):
    assert bs.record_kill(cid, ek, conn=conn) == {}
    # nothing written
    assert conn.execute("SELECT COUNT(*) FROM character_bestiary").fetchone()[0] == 0


def test_record_kill_swallows_db_error():
    # bad connection object → must return {} not raise
    class Boom:
        def execute(self, *a, **k):
            raise sqlite3.OperationalError("boom")
    assert bs.record_kill(7, "goblin", conn=Boom()) == {}


# ─── batch tiers ─────────────────────────────────────────────────────────────

def test_get_entry_tiers_batch(conn):
    for _ in range(5):
        bs.record_kill(7, "goblin", conn=conn)
    bs.record_kill(7, "orc", conn=conn)
    tiers = bs.get_entry_tiers(7, ["goblin", "orc", "unknown"], conn=conn)
    assert tiers == {"goblin": 2, "orc": 1, "unknown": 0}


# ─── get_bestiary catalogue (locked entries never leak) ──────────────────────

def test_get_bestiary_locked_and_unlocked(conn, monkeypatch):
    monkeypatch.setattr(bs, "_conn", lambda: conn)
    for _ in range(5):
        bs.record_kill(7, "goblin", conn=conn)  # tier 2 → hp visible
    result = bs.get_bestiary(7)
    assert result["summary"] == {"unlocked": 1, "total": 2, "pct": 50}
    by_lock = {e.get("locked") for e in result["entries"]}
    assert by_lock == {True, False}
    unlocked = next(e for e in result["entries"] if not e["locked"])
    assert unlocked["name"] == "Goblin"
    assert unlocked["hp_max"] == 12  # tier >=2 exposes hp
    locked = next(e for e in result["entries"] if e["locked"])
    assert locked == {"locked": True}  # NO name/key leak


def test_get_bestiary_hides_hp_below_tier2(conn, monkeypatch):
    monkeypatch.setattr(bs, "_conn", lambda: conn)
    bs.record_kill(7, "goblin", conn=conn)  # tier 1 only
    unlocked = next(e for e in bs.get_bestiary(7)["entries"] if not e["locked"])
    assert "hp_max" not in unlocked


def test_get_bestiary_empty_for_unknown_hero(conn, monkeypatch):
    monkeypatch.setattr(bs, "_conn", lambda: conn)
    result = bs.get_bestiary(999)
    assert result["summary"]["unlocked"] == 0
    assert all(e["locked"] for e in result["entries"])
