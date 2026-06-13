"""TDD: Issue #546 — U31 Scene load from DB on location entry."""
import json
import random
import sqlite3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

DB_PATH = "/data/ai_gm.db"


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _fresh_campaign(conn: sqlite3.Connection) -> int:
    """Insert a minimal campaign + session row; return campaign_id."""
    cur = conn.execute(
        """INSERT INTO campaigns (title, system_id, model_id, owner_user_id, mode, status)
           VALUES ('[U31-TEST]', 'dnd5e', 'test', 1, 'solo', 'active')""",
    )
    campaign_id = cur.lastrowid
    conn.execute(
        """INSERT INTO game_sessions (campaign_id, scene_enemies, scene_npcs, scene_cleared, active_quests, player_conditions)
           VALUES (?, '[]', '[]', 0, '[]', '[]')""",
        (campaign_id,),
    )
    conn.commit()
    return campaign_id


def _insert_location(conn, key="test_inn_u31", label="Test Inn"):
    conn.execute(
        "INSERT OR IGNORE INTO game_locations (key, label, location_type) VALUES (?, ?, 'macro')",
        (key, label),
    )
    conn.commit()


def _insert_sublocation(conn, key="test_inn_cellar_u31", label="Inn Cellar", parent_key="test_inn_u31"):
    parent_id = conn.execute(
        "SELECT id FROM game_locations WHERE key = ?", (parent_key,)
    ).fetchone()
    parent_id = parent_id[0] if parent_id else None
    conn.execute(
        """INSERT OR IGNORE INTO game_locations (key, label, location_type, parent_key, parent_id)
           VALUES (?, ?, 'sub', ?, ?)""",
        (key, label, parent_key, parent_id),
    )
    conn.commit()


def _insert_npc(conn, key="marta_u31", label="Marta Karczmarka"):
    conn.execute(
        "INSERT OR IGNORE INTO npcs (key, label, npc_type) VALUES (?, ?, 'neutral')",
        (key, label),
    )
    conn.commit()


def _insert_npc_assignment(conn, location_key, npc_key, is_active=1):
    conn.execute(
        "INSERT OR IGNORE INTO location_npc_assignments (location_key, npc_key, is_active) VALUES (?, ?, ?)",
        (location_key, npc_key, is_active),
    )
    conn.commit()


def _insert_enemy(conn, key="goblin_u31", label="Goblin"):
    conn.execute(
        """INSERT OR IGNORE INTO game_config_enemies
           (key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die)
           VALUES (?, ?, 10, 10, 2, 0, '1d4')""",
        (key, label),
    )
    conn.commit()


def _insert_enemy_assignment(conn, location_key, enemy_key, spawn_chance=1.0, max_count=2):
    conn.execute(
        """INSERT OR IGNORE INTO location_enemy_assignments
           (location_key, enemy_key, spawn_chance, max_count) VALUES (?, ?, ?, ?)""",
        (location_key, enemy_key, spawn_chance, max_count),
    )
    conn.commit()


def _get_scene(conn, campaign_id):
    row = conn.execute(
        "SELECT scene_npcs, scene_enemies FROM game_sessions WHERE campaign_id = ?",
        (campaign_id,),
    ).fetchone()
    if not row:
        return [], []
    npcs = json.loads(row[0] or "[]")
    enemies = json.loads(row[1] or "[]")
    return npcs, enemies


# ─── Test 1: enter_location_scene loads NPCs ─────────────────────────────────

def test_enter_location_loads_npcs():
    """After enter_location_scene, scene_npcs populated from location_npc_assignments."""
    from app.services.world_state_service import enter_location_scene

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        campaign_id = _fresh_campaign(conn)
        _insert_location(conn)
        _insert_npc(conn)
        _insert_npc_assignment(conn, "test_inn_u31", "marta_u31")

        result = enter_location_scene(campaign_id, "test_inn_u31")

        npcs, enemies = _get_scene(conn, campaign_id)
        assert result["npcs_loaded"] == 1
        assert len(npcs) == 1
        assert npcs[0]["key"] == "marta_u31"
        assert "marta" in npcs[0]["name"].lower()
    finally:
        conn.close()


# ─── Test 2: enter_location_scene spawns enemies via spawn_chance ─────────────

def test_enter_location_spawns_enemies_always():
    """spawn_chance=1.0 → enemies always in scene_enemies."""
    from app.services.world_state_service import enter_location_scene

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        campaign_id = _fresh_campaign(conn)
        _insert_location(conn, key="goblin_camp_u31", label="Goblin Camp")
        _insert_enemy(conn)
        _insert_enemy_assignment(conn, "goblin_camp_u31", "goblin_u31", spawn_chance=1.0, max_count=2)

        enter_location_scene(campaign_id, "goblin_camp_u31")

        _, enemies = _get_scene(conn, campaign_id)
        assert len(enemies) >= 1
        assert enemies[0]["key"] == "goblin_u31"
    finally:
        conn.close()


# ─── Test 3: spawn_chance=0.0 → no enemies ────────────────────────────────────

def test_enter_location_zero_spawn_chance_no_enemies():
    """spawn_chance=0.0 → never spawns enemies."""
    from app.services.world_state_service import enter_location_scene

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        campaign_id = _fresh_campaign(conn)
        _insert_location(conn, key="empty_inn_u31", label="Empty Inn")
        _insert_enemy(conn)
        _insert_enemy_assignment(conn, "empty_inn_u31", "goblin_u31", spawn_chance=0.0, max_count=3)

        enter_location_scene(campaign_id, "empty_inn_u31")

        _, enemies = _get_scene(conn, campaign_id)
        assert len(enemies) == 0
    finally:
        conn.close()


# ─── Test 4: inactive assignments not loaded ──────────────────────────────────

def test_inactive_assignments_skipped():
    """is_active=0 NPCs not loaded."""
    from app.services.world_state_service import enter_location_scene

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        campaign_id = _fresh_campaign(conn)
        _insert_location(conn, key="locked_inn_u31", label="Locked Inn")
        _insert_npc(conn, key="ghost_npc_u31", label="Duch")
        _insert_npc_assignment(conn, "locked_inn_u31", "ghost_npc_u31", is_active=0)

        enter_location_scene(campaign_id, "locked_inn_u31")

        npcs, _ = _get_scene(conn, campaign_id)
        assert len(npcs) == 0
    finally:
        conn.close()


# ─── Test 5: exit_location_scene clears both ─────────────────────────────────

def test_exit_location_clears_scene():
    """exit_location_scene sets scene_npcs=[] and scene_enemies=[]."""
    from app.services.world_state_service import enter_location_scene, exit_location_scene

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        campaign_id = _fresh_campaign(conn)
        _insert_location(conn)
        _insert_npc(conn)
        _insert_npc_assignment(conn, "test_inn_u31", "marta_u31")

        enter_location_scene(campaign_id, "test_inn_u31")
        npcs_before, _ = _get_scene(conn, campaign_id)
        assert len(npcs_before) == 1  # populated

        exit_location_scene(campaign_id)

        npcs, enemies = _get_scene(conn, campaign_id)
        assert npcs == []
        assert enemies == []
    finally:
        conn.close()


# ─── Test 6: enter returns correct counts ─────────────────────────────────────

def test_enter_location_returns_correct_counts():
    """Return dict has npcs_loaded, enemies_spawned, location_key."""
    from app.services.world_state_service import enter_location_scene

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        campaign_id = _fresh_campaign(conn)
        _insert_location(conn, key="tavern_u31", label="Tavern")
        _insert_npc(conn, key="barkeep_u31", label="Karczmarz")
        _insert_npc_assignment(conn, "tavern_u31", "barkeep_u31")
        _insert_enemy(conn)
        _insert_enemy_assignment(conn, "tavern_u31", "goblin_u31", spawn_chance=1.0, max_count=1)

        result = enter_location_scene(campaign_id, "tavern_u31")

        assert result["location_key"] == "tavern_u31"
        assert result["npcs_loaded"] == 1
        assert "enemies_spawned" in result
    finally:
        conn.close()


# ─── Test 7: unknown location_key → empty scene, no crash ─────────────────────

def test_enter_unknown_location_no_crash():
    """Unknown location → empty scene (0 NPCs, 0 enemies), no exception."""
    from app.services.world_state_service import enter_location_scene

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        campaign_id = _fresh_campaign(conn)

        result = enter_location_scene(campaign_id, "NONEXISTENT_LOCATION_U31")

        npcs, enemies = _get_scene(conn, campaign_id)
        assert npcs == []
        assert enemies == []
        assert result["npcs_loaded"] == 0
        assert result["enemies_spawned"] == 0
    finally:
        conn.close()


# ─── Test 8: enter_sublocation_scene swaps scene, saves parent key ────────────

def test_enter_sublocation_swaps_scene():
    """Entering sub-location replaces scene; parent state preserved in flags."""
    from app.services.world_state_service import enter_location_scene, enter_sublocation_scene

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        campaign_id = _fresh_campaign(conn)
        # Parent location with an NPC
        _insert_location(conn, key="parent_inn_u31", label="Parent Inn")
        _insert_npc(conn, key="parent_npc_u31", label="Rodzic NPC")
        _insert_npc_assignment(conn, "parent_inn_u31", "parent_npc_u31")
        # Sub-location with different NPC
        _insert_sublocation(conn, key="sub_cellar_u31", label="Piwnica", parent_key="parent_inn_u31")
        _insert_npc(conn, key="sub_npc_u31", label="Podziemny NPC")
        _insert_npc_assignment(conn, "sub_cellar_u31", "sub_npc_u31")

        # Enter parent first
        enter_location_scene(campaign_id, "parent_inn_u31")
        npcs_parent, _ = _get_scene(conn, campaign_id)
        assert len(npcs_parent) == 1
        assert npcs_parent[0]["key"] == "parent_npc_u31"

        # Enter sub-location — scene swaps
        enter_sublocation_scene(campaign_id, "sub_cellar_u31")

        npcs_sub, _ = _get_scene(conn, campaign_id)
        assert len(npcs_sub) == 1
        assert npcs_sub[0]["key"] == "sub_npc_u31"

        # Parent key saved in session_flags
        gs = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()
        flags = json.loads(gs["session_flags"] or "{}")
        assert flags.get("parent_location_key") == "parent_inn_u31"
    finally:
        conn.close()


# ─── Backward compat: set_world_state_flags still works unchanged ─────────────

def test_set_world_state_flags_backward_compat():
    """set_world_state_flags still accepts arbitrary list values without regression."""
    from app.services.world_state_service import set_world_state_flags, get_world_state_flags

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        campaign_id = _fresh_campaign(conn)

        set_world_state_flags(
            campaign_id,
            scene_enemies=[{"key": "rat", "name": "Rat", "hp": 5}],
            scene_npcs=[{"key": "merchant", "name": "Kupiec"}],
        )

        result = get_world_state_flags(campaign_id)
        assert result["scene_enemies"][0]["key"] == "rat"
        assert result["scene_npcs"][0]["key"] == "merchant"
    finally:
        conn.close()
