"""L7 — Checkpointy + śmierć kończy run + porzucenie 50% cooldown.

Tests: checkpoint save/restore matrix, death semantics, abandon 50% cooldown,
win keeps state, resume graph preserved without re-roll.

Issue: #676
"""
from __future__ import annotations

import json
import math
import sqlite3
import pytest
from datetime import datetime, timezone

DB_PATH = "/data/ai_gm.db"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now_utc():
    return datetime.now(timezone.utc)


def _make_dungeon(conn, key="test_l7_dungeon", cooldown_hours=72):
    """Insert a minimal tile-capable dungeon."""
    conn.execute("""
        INSERT OR REPLACE INTO game_dungeons
            (key, label, location_key, dungeon_difficulty, tile_category_key, cooldown_hours,
             boss_tile_id, endless_growth_n, is_active)
        VALUES (?, ?, ?, 1, 'crypt', ?, NULL, 2, 1)
    """, (key, f"Test Dungeon {key}", key, cooldown_hours))
    conn.commit()


def _make_character(conn, char_id=99700, hp=20, gold=100, xp=50, mana=8, level=2):
    """Insert/replace a minimal character with given stats."""
    sheet = {
        "level": level,
        "current_hp": hp,
        "max_hp": hp,
        "current_mana": mana,
        "xp_lifetime_earned": xp,
        "xp_available": 10,
    }
    conn.execute("""
        INSERT OR REPLACE INTO characters
            (id, user_id, name, system_id, sheet_json, gold, gold_gp, status, campaign_id)
        VALUES (?, 1, 'TestHero', 'fantasy', ?, ?, 0, 'idle', NULL)
    """, (char_id, json.dumps(sheet), gold))
    conn.commit()
    return char_id


def _make_campaign_with_session(conn, campaign_id=99700, char_id=99700):
    """Insert minimal campaign + game_session for dungeon flags."""
    conn.execute("""
        INSERT OR REPLACE INTO campaigns (id, owner_user_id, title, system_id, model_id, status)
        VALUES (?, 1, 'L7 Test Campaign', 'fantasy', 'default', 'active')
    """, (campaign_id,))
    conn.execute("""
        INSERT OR REPLACE INTO game_sessions (campaign_id, session_flags)
        VALUES (?, '{}')
    """, (campaign_id,))
    conn.commit()


def _set_dungeon_run(conn, campaign_id, run_dict):
    flags = json.loads(conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1", (campaign_id,)
    ).fetchone()["session_flags"] or "{}")
    flags["dungeon_run"] = run_dict
    conn.execute("UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                 (json.dumps(flags), campaign_id))
    conn.commit()


def _get_dungeon_run(conn, campaign_id):
    row = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1", (campaign_id,)
    ).fetchone()
    return json.loads(row["session_flags"] or "{}").get("dungeon_run")


def _save_entry_snapshot(conn, campaign_id, turn_number, state_dict):
    conn.execute("""
        INSERT INTO world_state_snapshots (campaign_id, turn_number, snapshot_json, snapshot_source)
        VALUES (?, ?, ?, 'dungeon_enter')
    """, (campaign_id, turn_number, json.dumps(state_dict)))
    conn.commit()


def _save_boss_snapshot(conn, campaign_id, turn_number, state_dict):
    cur = conn.execute("""
        INSERT INTO world_state_snapshots (campaign_id, turn_number, snapshot_json, snapshot_source)
        VALUES (?, ?, ?, 'dungeon_boss_checkpoint')
    """, (campaign_id, turn_number, json.dumps(state_dict)))
    conn.commit()
    return cur.lastrowid


def _get_sheet(conn, char_id):
    row = conn.execute("SELECT sheet_json, gold, gold_gp FROM characters WHERE id = ?", (char_id,)).fetchone()
    sheet = json.loads(row["sheet_json"])
    sheet["_gold"] = row["gold"]
    return sheet


def _get_inventory(conn, char_id):
    rows = conn.execute(
        "SELECT item_key, weapon_key, consumable_key, quantity, equipped FROM character_inventory WHERE character_id = ?",
        (char_id,)
    ).fetchall()
    return [dict(r) for r in rows]


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def cleanup():
    """Clean test data before/after each test. Resets DB_PATH in case prior tests patched it."""
    import app.services.dungeon_service as _ds
    import app.services.dungeon_tile_service as _dts
    _ds.DB_PATH = DB_PATH
    _dts.DB_PATH = DB_PATH
    conn = _get_db()
    try:
        for cid in [99700, 99701, 99702, 99703, 99704]:
            conn.execute("DELETE FROM world_state_snapshots WHERE campaign_id = ?", (cid,))
            conn.execute("DELETE FROM game_sessions WHERE campaign_id = ?", (cid,))
            conn.execute("DELETE FROM campaigns WHERE id = ?", (cid,))
        for char_id in [99700, 99701, 99702, 99703, 99704]:
            conn.execute("DELETE FROM character_inventory WHERE character_id = ?", (char_id,))
            conn.execute("DELETE FROM characters WHERE id = ?", (char_id,))
            conn.execute("DELETE FROM character_dungeon_runs WHERE character_id = ?", (char_id,))
        conn.execute("DELETE FROM game_dungeons WHERE key LIKE 'test_l7%'")
        conn.commit()
    finally:
        conn.close()
    yield
    conn = _get_db()
    try:
        for cid in [99700, 99701, 99702, 99703, 99704]:
            conn.execute("DELETE FROM world_state_snapshots WHERE campaign_id = ?", (cid,))
            conn.execute("DELETE FROM game_sessions WHERE campaign_id = ?", (cid,))
            conn.execute("DELETE FROM campaigns WHERE id = ?", (cid,))
        for char_id in [99700, 99701, 99702, 99703, 99704]:
            conn.execute("DELETE FROM character_inventory WHERE character_id = ?", (char_id,))
            conn.execute("DELETE FROM characters WHERE id = ?", (char_id,))
            conn.execute("DELETE FROM character_dungeon_runs WHERE character_id = ?", (char_id,))
        conn.execute("DELETE FROM game_dungeons WHERE key LIKE 'test_l7%'")
        conn.commit()
    finally:
        conn.close()


# ── T1: restore_dungeon_checkpoint — restores from entry snapshot ─────────────

def test_l7_t1_restore_from_entry_snapshot():
    """restore_dungeon_checkpoint restores HP/gold/XP/mana from dungeon_enter snapshot."""
    from app.services.dungeon_service import restore_dungeon_checkpoint

    conn = _get_db()
    try:
        _make_character(conn, char_id=99700, hp=20, gold=100, xp=50, mana=8, level=2)
        _make_campaign_with_session(conn, campaign_id=99700, char_id=99700)

        entry_state = {
            "current_hp": 20,
            "max_hp": 20,
            "current_mana": 8,
            "gold": 100,
            "gold_gp": 0,
            "inventory": [],
            "xp_lifetime_earned": 50,
            "xp_available": 10,
        }
        _save_entry_snapshot(conn, 99700, 0, entry_state)

        # Simulate taking damage + earning XP mid-dungeon
        sheet_after = {"level": 2, "current_hp": 5, "max_hp": 20, "current_mana": 2,
                       "xp_lifetime_earned": 80, "xp_available": 30}
        conn.execute("UPDATE characters SET sheet_json = ?, gold = ? WHERE id = ?",
                     (json.dumps(sheet_after), 60, 99700))
        conn.commit()
    finally:
        conn.close()

    result = restore_dungeon_checkpoint(99700, 99700)
    assert result is True

    conn = _get_db()
    try:
        sheet = _get_sheet(conn, 99700)
    finally:
        conn.close()

    assert sheet["current_hp"] == 20, "HP should be restored to entry value"
    assert sheet["current_mana"] == 8, "Mana should be restored to entry value"
    assert sheet["_gold"] == 100, "Gold should be restored to entry value"
    assert sheet["xp_lifetime_earned"] == 50, "XP should be rolled back to entry value"


# ── T2: restore_dungeon_checkpoint — boss checkpoint takes priority ────────────

def test_l7_t2_restore_from_boss_checkpoint():
    """restore_dungeon_checkpoint prefers latest boss checkpoint over entry."""
    from app.services.dungeon_service import restore_dungeon_checkpoint

    conn = _get_db()
    try:
        _make_character(conn, char_id=99701, hp=20, gold=100, xp=50, mana=8, level=2)
        _make_campaign_with_session(conn, campaign_id=99701, char_id=99701)

        entry_state = {
            "current_hp": 20, "max_hp": 20, "current_mana": 8,
            "gold": 100, "gold_gp": 0, "inventory": [],
            "xp_lifetime_earned": 50, "xp_available": 10,
        }
        _save_entry_snapshot(conn, 99701, 0, entry_state)

        # Boss checkpoint: higher HP, XP and gold
        boss_state = {
            "current_hp": 15, "max_hp": 20, "current_mana": 6,
            "gold": 150, "gold_gp": 0, "inventory": [],
            "xp_lifetime_earned": 75, "xp_available": 20,
        }
        _save_boss_snapshot(conn, 99701, 5, boss_state)

        # Simulate further damage after boss
        sheet_after = {"level": 2, "current_hp": 1, "max_hp": 20, "current_mana": 0,
                       "xp_lifetime_earned": 100, "xp_available": 40}
        conn.execute("UPDATE characters SET sheet_json = ?, gold = ? WHERE id = ?",
                     (json.dumps(sheet_after), 200, 99701))
        conn.commit()
    finally:
        conn.close()

    result = restore_dungeon_checkpoint(99701, 99701)
    assert result is True

    conn = _get_db()
    try:
        sheet = _get_sheet(conn, 99701)
    finally:
        conn.close()

    assert sheet["current_hp"] == 15, "HP should be from boss checkpoint, not entry"
    assert sheet["current_mana"] == 6, "Mana from boss checkpoint"
    assert sheet["_gold"] == 150, "Gold from boss checkpoint"
    assert sheet["xp_lifetime_earned"] == 75, "XP from boss checkpoint"


# ── T3: handle_dungeon_death — marks failed, restores state, starts cooldown ──

def test_l7_t3_death_marks_failed_restores_and_sets_cooldown():
    """Death marks run failed, restores from last checkpoint, starts cooldown."""
    from app.services.dungeon_service import handle_dungeon_death

    conn = _get_db()
    try:
        _make_dungeon(conn, key="test_l7_dungeon", cooldown_hours=72)
        _make_character(conn, char_id=99700, hp=20, gold=100, xp=50, mana=8, level=2)
        _make_campaign_with_session(conn, campaign_id=99700, char_id=99700)

        # Entry snapshot
        entry_state = {
            "current_hp": 20, "max_hp": 20, "current_mana": 8,
            "gold": 100, "gold_gp": 0, "inventory": [],
            "xp_lifetime_earned": 50, "xp_available": 10,
        }
        _save_entry_snapshot(conn, 99700, 0, entry_state)

        run = {
            "system": "tiles_v2",
            "dungeon_key": "test_l7_dungeon",
            "dungeon_label": "Test Dungeon",
            "completed": False,
            "failed": False,
            "checkpoints": [{"cycle": 1, "source": "dungeon_enter"}],
            "at_checkpoint": False,
            "cooldown_hours": 72,
        }
        _set_dungeon_run(conn, 99700, run)

        # Simulate damage in dungeon
        sheet_after = {"level": 2, "current_hp": 0, "max_hp": 20, "current_mana": 0,
                       "xp_lifetime_earned": 70, "xp_available": 25}
        conn.execute("UPDATE characters SET sheet_json = ?, gold = ? WHERE id = ?",
                     (json.dumps(sheet_after), 80, 99700))
        conn.commit()
    finally:
        conn.close()

    result = handle_dungeon_death(99700, 99700)
    assert result["ok"] is True
    assert result.get("restored") is True, "State should be restored"
    assert result.get("failed") is True, "Should report failed=True"

    conn = _get_db()
    try:
        # State restored
        sheet = _get_sheet(conn, 99700)
        assert sheet["current_hp"] == 20, "HP restored to entry"
        assert sheet["xp_lifetime_earned"] == 50, "XP rolled back to entry"
        assert sheet["_gold"] == 100, "Gold restored to entry"

        # Run marked failed (not restarted)
        run = _get_dungeon_run(conn, 99700)
        assert run is not None
        assert run.get("failed") is True, "Run should be marked failed"
        assert run.get("completed") is False, "Run not completed"

        # Cooldown set
        cooldown_row = conn.execute(
            "SELECT cooldown_until FROM character_dungeon_runs WHERE character_id = ? AND location_key = ?",
            (99700, "test_l7_dungeon")
        ).fetchone()
        assert cooldown_row is not None, "Cooldown should be set"
    finally:
        conn.close()


# ── T4: death does NOT restart from tile 1 (overrides E16) ───────────────────

def test_l7_t4_death_does_not_restart_to_tile_1():
    """Death marks failed but does NOT reset positions to start tile."""
    from app.services.dungeon_service import handle_dungeon_death

    conn = _get_db()
    try:
        _make_dungeon(conn, key="test_l7_dungeon")
        _make_character(conn, char_id=99700)
        _make_campaign_with_session(conn, campaign_id=99700)

        _save_entry_snapshot(conn, 99700, 0, {
            "current_hp": 20, "max_hp": 20, "current_mana": 8,
            "gold": 100, "gold_gp": 0, "inventory": [],
            "xp_lifetime_earned": 50, "xp_available": 10,
        })

        run = {
            "system": "tiles_v2",
            "dungeon_key": "test_l7_dungeon",
            "graph": {"entry_node": "n1", "nodes": {"n1": {}, "n2": {}, "n3": {}}},
            "positions": {"99700": "n3"},  # player at tile 3
            "completed": False,
            "failed": False,
            "checkpoints": [{"cycle": 1, "source": "dungeon_enter"}],
            "at_checkpoint": False,
            "cooldown_hours": 72,
        }
        _set_dungeon_run(conn, 99700, run)
    finally:
        conn.close()

    handle_dungeon_death(99700, 99700)

    conn = _get_db()
    try:
        run = _get_dungeon_run(conn, 99700)
        # Positions NOT reset to entry node
        assert run["positions"].get("99700") == "n3", "Position must NOT be reset on death"
    finally:
        conn.close()


# ── T5: handle_dungeon_abandon mid-segment — 50% cooldown, restore ────────────

def test_l7_t5_abandon_mid_segment_50pct_cooldown():
    """Mid-segment abandon: restore from checkpoint + 50% cooldown (ceiling)."""
    from app.services.dungeon_service import handle_dungeon_abandon

    conn = _get_db()
    try:
        _make_dungeon(conn, key="test_l7_dungeon", cooldown_hours=72)
        _make_character(conn, char_id=99702, hp=20, gold=100, xp=50, mana=8, level=2)
        _make_campaign_with_session(conn, campaign_id=99702, char_id=99702)

        _save_entry_snapshot(conn, 99702, 0, {
            "current_hp": 20, "max_hp": 20, "current_mana": 8,
            "gold": 100, "gold_gp": 0, "inventory": [],
            "xp_lifetime_earned": 50, "xp_available": 10,
        })

        run = {
            "system": "tiles_v2",
            "dungeon_key": "test_l7_dungeon",
            "completed": False,
            "failed": False,
            "checkpoints": [{"cycle": 1, "source": "dungeon_enter"}],
            "at_checkpoint": False,  # mid-segment
            "cooldown_hours": 72,
        }
        _set_dungeon_run(conn, 99702, run)

        # Take some damage / earn XP
        sheet_after = {"level": 2, "current_hp": 10, "max_hp": 20, "current_mana": 3,
                       "xp_lifetime_earned": 65, "xp_available": 18}
        conn.execute("UPDATE characters SET sheet_json = ?, gold = ? WHERE id = ?",
                     (json.dumps(sheet_after), 75, 99702))
        conn.commit()
    finally:
        conn.close()

    result = handle_dungeon_abandon(99702, 99702)
    assert result["ok"] is True
    assert result["at_checkpoint"] is False
    assert result["restored"] is True, "State should be restored mid-segment"

    conn = _get_db()
    try:
        sheet = _get_sheet(conn, 99702)
        assert sheet["current_hp"] == 20, "HP restored to checkpoint"
        assert sheet["xp_lifetime_earned"] == 50, "XP rolled back"

        cooldown_row = conn.execute(
            "SELECT cooldown_until FROM character_dungeon_runs WHERE character_id = ? AND location_key = ?",
            (99702, "test_l7_dungeon")
        ).fetchone()
        assert cooldown_row is not None

        # Verify it's approximately 50% of 72h = 36h from now
        cooldown_str = cooldown_row["cooldown_until"]
        cooldown_dt = datetime.fromisoformat(cooldown_str.replace("Z", "+00:00"))
        if cooldown_dt.tzinfo is None:
            cooldown_dt = cooldown_dt.replace(tzinfo=timezone.utc)
        diff_hours = (cooldown_dt - _now_utc()).total_seconds() / 3600
        expected_hours = math.ceil(72 * 0.5)  # = 36
        assert abs(diff_hours - expected_hours) < 0.1, f"Cooldown should be {expected_hours}h, got {diff_hours:.1f}h"
    finally:
        conn.close()


# ── T6: handle_dungeon_abandon at checkpoint — full reward, no restore ─────────

def test_l7_t6_abandon_at_checkpoint_full_cooldown_no_restore():
    """Abandon at checkpoint (boss beaten, segment not started): full reward, 100% cooldown."""
    from app.services.dungeon_service import handle_dungeon_abandon

    conn = _get_db()
    try:
        _make_dungeon(conn, key="test_l7_dungeon", cooldown_hours=24)
        _make_character(conn, char_id=99703, hp=10, gold=200, xp=80, mana=5, level=2)
        _make_campaign_with_session(conn, campaign_id=99703, char_id=99703)

        _save_entry_snapshot(conn, 99703, 0, {
            "current_hp": 20, "max_hp": 20, "current_mana": 8,
            "gold": 100, "gold_gp": 0, "inventory": [],
            "xp_lifetime_earned": 50, "xp_available": 10,
        })

        run = {
            "system": "tiles_v2",
            "dungeon_key": "test_l7_dungeon",
            "completed": False,
            "failed": False,
            "checkpoints": [
                {"cycle": 1, "source": "dungeon_enter"},
                {"cycle": 1, "source": "dungeon_boss_checkpoint", "snapshot_id": 1}
            ],
            "at_checkpoint": True,  # boss defeated, segment not started
            "cooldown_hours": 24,
        }
        _set_dungeon_run(conn, 99703, run)
    finally:
        conn.close()

    result = handle_dungeon_abandon(99703, 99703)
    assert result["ok"] is True
    assert result["at_checkpoint"] is True
    assert result.get("restored") is False, "At checkpoint: no restore"

    conn = _get_db()
    try:
        # State NOT restored (player keeps progress)
        sheet = _get_sheet(conn, 99703)
        assert sheet["current_hp"] == 10, "HP NOT restored at checkpoint exit"
        assert sheet["_gold"] == 200, "Gold NOT restored at checkpoint exit"
        assert sheet["xp_lifetime_earned"] == 80, "XP NOT rolled back at checkpoint exit"

        # Cooldown: 100% of 24h
        cooldown_row = conn.execute(
            "SELECT cooldown_until FROM character_dungeon_runs WHERE character_id = ? AND location_key = ?",
            (99703, "test_l7_dungeon")
        ).fetchone()
        assert cooldown_row is not None
        cooldown_str = cooldown_row["cooldown_until"]
        cooldown_dt = datetime.fromisoformat(cooldown_str.replace("Z", "+00:00"))
        if cooldown_dt.tzinfo is None:
            cooldown_dt = cooldown_dt.replace(tzinfo=timezone.utc)
        diff_hours = (cooldown_dt - _now_utc()).total_seconds() / 3600
        assert abs(diff_hours - 24) < 0.1, f"Cooldown should be 24h, got {diff_hours:.1f}h"
    finally:
        conn.close()


# ── T7: save_dungeon_checkpoint — saves snapshot + appends to run ─────────────

def test_l7_t7_save_boss_checkpoint():
    """save_dungeon_checkpoint saves world_state_snapshots row + appends to run.checkpoints."""
    from app.services.dungeon_tile_service import save_dungeon_checkpoint

    conn = _get_db()
    try:
        _make_character(conn, char_id=99704, hp=15, gold=150, xp=75, mana=6, level=2)
        _make_campaign_with_session(conn, campaign_id=99704, char_id=99704)

        run = {
            "system": "tiles_v2",
            "dungeon_key": "test_l7_dungeon",
            "cycle": 1,
            "checkpoints": [{"cycle": 1, "source": "dungeon_enter"}],
            "at_checkpoint": False,
            "completed": False,
            "failed": False,
        }
        _set_dungeon_run(conn, 99704, run)
    finally:
        conn.close()

    checkpoint = save_dungeon_checkpoint(99704, 99704)

    assert checkpoint.get("source") == "dungeon_boss_checkpoint"
    assert checkpoint.get("cycle") == 1
    assert checkpoint.get("xp_lifetime_earned") == 75
    assert "snapshot_id" in checkpoint

    conn = _get_db()
    try:
        # Snapshot saved in world_state_snapshots
        snap_row = conn.execute(
            "SELECT snapshot_json, snapshot_source FROM world_state_snapshots WHERE id = ?",
            (checkpoint["snapshot_id"],)
        ).fetchone()
        assert snap_row is not None
        assert snap_row["snapshot_source"] == "dungeon_boss_checkpoint"
        snap = json.loads(snap_row["snapshot_json"])
        assert snap["current_hp"] == 15
        assert snap["xp_lifetime_earned"] == 75

        # Run updated
        run = _get_dungeon_run(conn, 99704)
        assert len(run["checkpoints"]) == 2
        assert run["checkpoints"][-1]["source"] == "dungeon_boss_checkpoint"
        assert run.get("at_checkpoint") is True, "at_checkpoint flag set after boss"
    finally:
        conn.close()


# ── T8: enter_dungeon_tiles records entry checkpoint in run.checkpoints ────────

def test_l7_t8_enter_dungeon_tiles_entry_checkpoint():
    """enter_dungeon_tiles initializes run.checkpoints with entry checkpoint."""
    from app.services.dungeon_tile_service import enter_dungeon_tiles

    conn = _get_db()
    try:
        _make_dungeon(conn, key="test_l7_dungeon2")
        _make_character(conn, char_id=99700, hp=20, gold=100, xp=50, mana=8, level=2)
        _make_campaign_with_session(conn, campaign_id=99700, char_id=99700)

        # Need at least some tiles in the category — skip if no 'crypt' tiles
        tile_count = conn.execute(
            "SELECT COUNT(*) as c FROM dungeon_tiles WHERE category_key = 'crypt' AND is_boss_tile = 0"
        ).fetchone()["c"]
        boss_count = conn.execute(
            "SELECT COUNT(*) as c FROM dungeon_tiles WHERE category_key = 'crypt' AND is_boss_tile = 1"
        ).fetchone()["c"]
        if tile_count < 2 or boss_count < 1:
            pytest.skip("No 'crypt' tiles in DB — skipping enter test")
    finally:
        conn.close()

    run = enter_dungeon_tiles(99700, 99700, "test_l7_dungeon2", hero_level=2)

    assert "checkpoints" in run, "run must have checkpoints key"
    assert len(run["checkpoints"]) >= 1, "Entry checkpoint must be present"
    entry_cp = run["checkpoints"][0]
    assert entry_cp["source"] == "dungeon_enter"
    assert "xp_lifetime_earned" in entry_cp
    assert entry_cp["xp_lifetime_earned"] == 50


# ── T9: XP rollback recalculates level ────────────────────────────────────────

def test_l7_t9_xp_rollback_recalculates_level():
    """After death, level recalculated from rolled-back XP."""
    from app.services.dungeon_service import restore_dungeon_checkpoint

    conn = _get_db()
    try:
        # Start at level 1 (XP=0), earned enough to hit level 2 (XP=100) inside dungeon
        _make_character(conn, char_id=99700, hp=10, gold=50, xp=0, mana=4, level=1)
        _make_campaign_with_session(conn, campaign_id=99700, char_id=99700)

        _save_entry_snapshot(conn, 99700, 0, {
            "current_hp": 10, "max_hp": 10, "current_mana": 4,
            "gold": 50, "gold_gp": 0, "inventory": [],
            "xp_lifetime_earned": 0, "xp_available": 0,
        })

        # Mid-dungeon: level-up happened
        sheet_after = {"level": 2, "current_hp": 5, "max_hp": 12, "current_mana": 2,
                       "xp_lifetime_earned": 100, "xp_available": 0}
        conn.execute("UPDATE characters SET sheet_json = ? WHERE id = ?",
                     (json.dumps(sheet_after), 99700))
        conn.commit()
    finally:
        conn.close()

    restore_dungeon_checkpoint(99700, 99700)

    conn = _get_db()
    try:
        sheet = _get_sheet(conn, 99700)
        assert sheet["xp_lifetime_earned"] == 0, "XP rolled back to 0"
        assert sheet["level"] == 1, "Level recalculated to 1 after XP rollback"
    finally:
        conn.close()


# ── T10: resume — run preserved in session_flags with graph ──────────────────

def test_l7_t10_resume_active_run_has_graph():
    """Active uncompleted run preserved in session_flags; graph not re-rolled."""
    from app.services.dungeon_service import get_active_dungeon_run

    conn = _get_db()
    try:
        _make_character(conn, char_id=99700)
        _make_campaign_with_session(conn, campaign_id=99700, char_id=99700)

        graph = {
            "entry_node": "n1",
            "nodes": {
                "n1": {"tile_id": 10, "content": {"room_description": "Test"}},
                "n2": {"tile_id": 11, "content": {}},
            }
        }
        run = {
            "system": "tiles_v2",
            "dungeon_key": "test_l7_dungeon",
            "graph": graph,
            "positions": {"99700": "n2"},
            "completed": False,
            "failed": False,
            "checkpoints": [{"cycle": 1, "source": "dungeon_enter"}],
        }
        _set_dungeon_run(conn, 99700, run)
        conn.execute(
            "UPDATE characters SET campaign_id = ? WHERE id = ?", (99700, 99700)
        )
        conn.commit()
    finally:
        conn.close()

    retrieved = get_active_dungeon_run(99700)
    assert retrieved is not None, "Active run should be retrievable"
    assert retrieved["graph"]["entry_node"] == "n1"
    assert retrieved["positions"]["99700"] == "n2", "Position preserved from mid-dungeon"
    assert not retrieved.get("completed")


# ── T11: start_dungeon_cooldown fraction=0.5 ceiling ─────────────────────────

def test_l7_t11_cooldown_fraction_ceiling():
    """start_dungeon_cooldown with fraction=0.5 and odd hours uses ceiling."""
    from app.services.dungeon_service import start_dungeon_cooldown

    conn = _get_db()
    try:
        # 3-hour cooldown → 50% = 1.5 → ceil = 2h
        _make_dungeon(conn, key="test_l7_odd", cooldown_hours=3)
        _make_character(conn, char_id=99700)
    finally:
        conn.close()

    result = start_dungeon_cooldown(99700, "test_l7_odd", fraction=0.5)
    assert "cooldown_until" in result

    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT cooldown_until FROM character_dungeon_runs WHERE character_id = ? AND location_key = ?",
            (99700, "test_l7_odd")
        ).fetchone()
        assert row is not None
        cooldown_dt = datetime.fromisoformat(row["cooldown_until"].replace("Z", "+00:00"))
        if cooldown_dt.tzinfo is None:
            cooldown_dt = cooldown_dt.replace(tzinfo=timezone.utc)
        diff_hours = (cooldown_dt - _now_utc()).total_seconds() / 3600
        expected = math.ceil(3 * 0.5)  # = 2
        assert abs(diff_hours - expected) < 0.1, f"Expected {expected}h ceil, got {diff_hours:.1f}h"
    finally:
        conn.close()
