"""L8 — Boss, loot i tryb nieskończony.

Tests:
- get_boss_loot_rarity_for_cycle: cycles 1-2 base, 3-4 +1, 5-6 +2, cap legendary
- roll_boss_loot_for_endless: empty when no boss_loot_table_key
- on_boss_tile_cleared: non-boss tile, boss tile, idempotent, checkpoint saved
- extend_dungeon_for_endless: n=0 same length, n=2 grows, cycle increments, graph merged
- 3-cycle loop segment lengths with n=0 and n=2
- Enemy scaling in cycle 2 (+1 level vs cycle 1)

Issue: #677
"""
from __future__ import annotations

import json
import sqlite3
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, "/app")

import app.services.dungeon_service as ds
import app.services.dungeon_tile_service as dts

DB_PATH = "/data/ai_gm.db"

# ── In-memory schema ──────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE dungeon_tile_categories (
    key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    style_modifier TEXT DEFAULT '',
    system_prompt TEXT,
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE dungeon_tiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_key TEXT NOT NULL,
    label TEXT NOT NULL,
    image_url TEXT,
    doors_json TEXT DEFAULT '[]',
    room_description TEXT DEFAULT '',
    enemies_json TEXT DEFAULT '[]',
    items_json TEXT DEFAULT '[]',
    active_states_json TEXT DEFAULT '[]',
    riddle_key TEXT,
    exit_conditions_json TEXT DEFAULT '[]',
    is_boss_tile INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE game_config_enemies (
    key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    hp_base INTEGER DEFAULT 5,
    ac_base INTEGER DEFAULT 8,
    attack_bonus INTEGER DEFAULT 0,
    damage_die TEXT DEFAULT '1d6',
    damage_bonus INTEGER DEFAULT 0,
    dex_modifier INTEGER DEFAULT 0,
    tier TEXT DEFAULT 'standard',
    stats_json TEXT DEFAULT NULL
);

CREATE TABLE game_config_items (key TEXT PRIMARY KEY, label TEXT NOT NULL);
CREATE TABLE game_config_weapons (key TEXT PRIMARY KEY, label TEXT NOT NULL);
CREATE TABLE game_config_consumables (key TEXT PRIMARY KEY, label TEXT NOT NULL);
CREATE TABLE game_config_riddles (
    key TEXT PRIMARY KEY, text TEXT NOT NULL, answer TEXT NOT NULL,
    answer_alts TEXT DEFAULT '[]', hints TEXT DEFAULT '[]', is_active INTEGER DEFAULT 1
);

CREATE TABLE game_dungeons (
    key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    location_key TEXT,
    rooms INTEGER DEFAULT 4,
    enemy_pool TEXT DEFAULT '[]',
    boss_enemy TEXT,
    loot_tier TEXT DEFAULT 'standard',
    atmosphere TEXT,
    cooldown_hours INTEGER DEFAULT 72,
    min_level INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1,
    chest_loot_table_key TEXT,
    boss_loot_table_key TEXT,
    room_loot_chance REAL DEFAULT 0.15,
    room_types_json TEXT DEFAULT '{}',
    riddle_source TEXT,
    riddle_max_hints INTEGER DEFAULT 2,
    dungeon_difficulty INTEGER DEFAULT 1,
    tile_category_key TEXT,
    tile_count INTEGER DEFAULT 4,
    boss_tile_id INTEGER,
    endless_growth_n INTEGER DEFAULT 0
);

CREATE TABLE game_config_loot_tables (
    key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE game_config_loot_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    loot_table_key TEXT NOT NULL,
    item_key TEXT,
    weapon_key TEXT,
    consumable_key TEXT,
    weight INTEGER DEFAULT 50,
    qty_min INTEGER DEFAULT 1,
    qty_max INTEGER DEFAULT 1
);

CREATE TABLE game_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    session_flags TEXT DEFAULT '{}'
);

CREATE TABLE campaigns (
    id INTEGER PRIMARY KEY,
    owner_user_id INTEGER NOT NULL DEFAULT 1,
    title TEXT NOT NULL,
    system_id TEXT NOT NULL DEFAULT 'fantasy',
    model_id TEXT NOT NULL DEFAULT 'default',
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE characters (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL DEFAULT 1,
    name TEXT NOT NULL,
    system_id TEXT NOT NULL DEFAULT 'fantasy',
    sheet_json TEXT DEFAULT '{}',
    gold INTEGER DEFAULT 0,
    gold_gp INTEGER DEFAULT 0,
    status TEXT DEFAULT 'idle',
    campaign_id INTEGER
);

CREATE TABLE character_inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL,
    item_key TEXT,
    weapon_key TEXT,
    consumable_key TEXT,
    quantity INTEGER DEFAULT 1,
    equipped INTEGER DEFAULT 0
);

CREATE TABLE world_state_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    turn_number INTEGER DEFAULT 0,
    snapshot_json TEXT NOT NULL DEFAULT '{}',
    snapshot_source TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE character_dungeon_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL,
    location_key TEXT NOT NULL,
    cooldown_until TEXT,
    completed_at TEXT,
    UNIQUE(character_id, location_key)
);
"""


@pytest.fixture
def db(tmp_path):
    """Temp SQLite with full tile+dungeon+character schema."""
    db_file = str(tmp_path / "test_l8.db")
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)

    # Category + tiles (4 regular, 2 boss) — enough for draw_tile_graph
    conn.execute("INSERT INTO dungeon_tile_categories VALUES ('test_cat','Test Cat',1,'','',0)")
    for i in range(4):
        doors = json.dumps(["N", "S", "E", "W"][:3])  # 3-door regular tile
        conn.execute(
            "INSERT INTO dungeon_tiles (category_key,label,doors_json,room_description,is_boss_tile,is_active)"
            " VALUES (?,?,?,?,0,1)",
            ("test_cat", f"Room {i}", doors, f"Desc {i}"),
        )
    # Boss tiles with 1 door (entry only possible variant)
    for i in range(2):
        conn.execute(
            "INSERT INTO dungeon_tiles (category_key,label,doors_json,room_description,is_boss_tile,is_active)"
            " VALUES (?,?,?,?,1,1)",
            ("test_cat", f"Boss {i}", json.dumps(["N", "S"]), f"Boss Desc {i}"),
        )

    # Dungeon
    conn.execute("""
        INSERT INTO game_dungeons
            (key,label,location_key,dungeon_difficulty,tile_category_key,tile_count,
             endless_growth_n,boss_loot_table_key,cooldown_hours,is_active)
        VALUES ('test_l8','Test L8 Dungeon','l8_loc',1,'test_cat',4,0,NULL,72,1)
    """)

    # Campaign + session + character
    conn.execute("INSERT INTO campaigns(id,owner_user_id,title,system_id,model_id,status) VALUES(9800,1,'L8','fantasy','default','active')")
    conn.execute("INSERT INTO game_sessions(campaign_id,session_flags) VALUES(9800,'{}')")
    conn.execute("""
        INSERT INTO characters(id,user_id,name,sheet_json,gold,gold_gp,status)
        VALUES(9800,1,'Hero','{}',100,0,'active')
    """)
    conn.commit()
    return db_file


def _set_run(conn, campaign_id, run):
    flags = json.loads(conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id=? LIMIT 1", (campaign_id,)
    ).fetchone()["session_flags"] or "{}")
    flags["dungeon_run"] = run
    conn.execute("UPDATE game_sessions SET session_flags=? WHERE campaign_id=?",
                 (json.dumps(flags), campaign_id))
    conn.commit()


def _get_run(conn, campaign_id):
    row = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id=? LIMIT 1", (campaign_id,)
    ).fetchone()
    return json.loads(row["session_flags"] or "{}").get("dungeon_run")


def _make_run(cycle=1, boss_choice_pending=False, boss_node="node_boss"):
    """Minimal v2 dungeon run with a boss node at current position."""
    return {
        "system": "tiles_v2",
        "dungeon_key": "test_l8",
        "dungeon_label": "Test L8",
        "dungeon_difficulty": 1,
        "cycle": cycle,
        "completed": False,
        "failed": False,
        "at_checkpoint": False,
        "boss_choice_pending": boss_choice_pending,
        "cooldown_hours": 72,
        "checkpoints": [{"cycle": 1, "source": "dungeon_enter", "xp_lifetime_earned": 0}],
        "positions": {"9800": boss_node},
        "graph": {
            "entry_node": "node_0",
            "boss_node": boss_node,
            "nodes": {
                "node_0": {
                    "tile_id": 1,
                    "position": [0, 0],
                    "doors_open": {"N": None, "S": boss_node, "E": None},
                    "door_hints": {},
                    "content": {"is_boss_tile": False, "enemies": [], "room_description": "Start"},
                    "visited": True,
                    "cleared": True,
                    "is_boss": False,
                },
                boss_node: {
                    "tile_id": 5,
                    "position": [0, 1],
                    "doors_open": {"N": "node_0", "S": None},
                    "door_hints": {},
                    "content": {"is_boss_tile": True, "enemies": [], "room_description": "Boss room"},
                    "visited": True,
                    "cleared": False,
                    "is_boss": True,
                },
            },
        },
    }


# ── T1: Boss rarity cycle progression ────────────────────────────────────────

def test_l8_t1_boss_rarity_cycle_progression(db):
    """get_boss_loot_rarity_for_cycle: +1 tier per 2 cycles, cap legendary."""
    with patch.object(ds, "DB_PATH", db):
        # Tier D1: base is epic or legendary (random); pin via mock
        with patch.object(ds, "get_loot_rarity_for_difficulty", return_value="epic"):
            assert ds.get_boss_loot_rarity_for_cycle(1, 1) == "epic",  "Cycle 1: base"
            assert ds.get_boss_loot_rarity_for_cycle(1, 2) == "epic",  "Cycle 2: still base"
            assert ds.get_boss_loot_rarity_for_cycle(1, 3) == "legendary", "Cycle 3: +1 → legendary"
            assert ds.get_boss_loot_rarity_for_cycle(1, 4) == "legendary", "Cycle 4: +1 → legendary"
            assert ds.get_boss_loot_rarity_for_cycle(1, 5) == "legendary", "Cycle 5: cap legendary"
            assert ds.get_boss_loot_rarity_for_cycle(1, 10) == "legendary","Cycle 10: cap legendary"


def test_l8_t1b_rarity_bump_from_rare(db):
    """If base is rare: cycle 3→epic, cycle 5→legendary (cap)."""
    with patch.object(ds, "DB_PATH", db):
        with patch.object(ds, "get_loot_rarity_for_difficulty", return_value="rare"):
            assert ds.get_boss_loot_rarity_for_cycle(1, 1) == "rare"
            assert ds.get_boss_loot_rarity_for_cycle(1, 3) == "epic"
            assert ds.get_boss_loot_rarity_for_cycle(1, 5) == "legendary"


# ── T2: roll_boss_loot_for_endless — no table ────────────────────────────────

def test_l8_t2_roll_boss_loot_no_table(db):
    """roll_boss_loot_for_endless returns empty list when boss_loot_table_key is NULL."""
    with patch.object(ds, "DB_PATH", db):
        loot, rarity = ds.roll_boss_loot_for_endless("test_l8", cycle=1)
        assert loot == [], "No loot table → empty list"
        assert rarity in ("epic", "legendary"), f"Rarity should be boss tier, got {rarity!r}"


# ── T3: on_boss_tile_cleared — non-boss node returns False ───────────────────

def test_l8_t3_on_boss_tile_cleared_non_boss(db):
    """on_boss_tile_cleared returns is_boss_tile=False for non-boss tile node."""
    run = _make_run()
    # Position player at a non-boss node
    run["positions"] = {"9800": "node_0"}

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        _set_run(conn, 9800, run)
    finally:
        conn.close()

    with patch.object(dts, "DB_PATH", db), patch.object(ds, "DB_PATH", db):
        result = dts.on_boss_tile_cleared(9800, 9800)

    assert result["is_boss_tile"] is False
    assert result["loot"] == []


# ── T4: on_boss_tile_cleared — boss tile sets flag + returns True ─────────────

def test_l8_t4_on_boss_tile_cleared_boss_node(db):
    """on_boss_tile_cleared on boss tile: boss_choice_pending=True, is_boss_tile=True."""
    run = _make_run()  # player already at boss node

    # Insert XP thresholds + character sheet
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        _set_run(conn, 9800, run)
        conn.execute("UPDATE characters SET sheet_json=? WHERE id=9800",
                     (json.dumps({"level": 1, "current_hp": 10, "max_hp": 10,
                                  "current_mana": 4, "xp_lifetime_earned": 0, "xp_available": 0}),))
        conn.commit()
    finally:
        conn.close()

    with patch.object(dts, "DB_PATH", db), patch.object(ds, "DB_PATH", db):
        # Patch save_dungeon_checkpoint to avoid world_state_service import chain
        with patch.object(dts, "save_dungeon_checkpoint", return_value={"cycle": 1}) as mock_cp:
            result = dts.on_boss_tile_cleared(9800, 9800)

    assert result["is_boss_tile"] is True
    mock_cp.assert_called_once_with(9800, 9800)

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        updated_run = _get_run(conn, 9800)
    finally:
        conn.close()

    assert updated_run["boss_choice_pending"] is True


# ── T4b: on_boss_tile_cleared returns GRANTED loot (with labels) ──────────────

def test_l8_t4b_boss_loot_returns_granted_with_labels(db):
    """#719: returned loot must be the GRANTED rows (carry human `label`), not the
    raw roll (only *_key columns). The player-facing 'co wypadło' reveal needs labels."""
    run = _make_run()

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        _set_run(conn, 9800, run)
        conn.execute("UPDATE characters SET sheet_json=? WHERE id=9800",
                     (json.dumps({"level": 1, "current_hp": 10, "max_hp": 10,
                                  "current_mana": 4, "xp_lifetime_earned": 0, "xp_available": 0}),))
        conn.commit()
    finally:
        conn.close()

    rolled = [{"item_key": "x", "consumable_key": None, "weapon_key": None, "quantity": 1}]
    granted = [{"label": "Korona Lisza", "item_type": "weapon", "quantity": 1,
                "source": "dungeon", "key": "x", "inventory_id": 5}]

    with patch.object(dts, "DB_PATH", db), patch.object(ds, "DB_PATH", db):
        with patch.object(dts, "save_dungeon_checkpoint", return_value={"cycle": 1}), \
             patch.object(ds, "roll_boss_loot_for_endless", return_value=(rolled, "epic")), \
             patch.object(ds, "grant_dungeon_loot", return_value=granted) as mock_grant:
            result = dts.on_boss_tile_cleared(9800, 9800)

    assert result["is_boss_tile"] is True
    assert result["loot"] == granted, "must return granted rows, not raw *_key roll"
    assert all("label" in it for it in result["loot"]), "every reveal item needs a label"
    mock_grant.assert_called_once()


# ── T5: on_boss_tile_cleared — idempotent ────────────────────────────────────

def test_l8_t5_on_boss_tile_cleared_idempotent(db):
    """Second call when boss_choice_pending=True returns early without double-grant."""
    run = _make_run(boss_choice_pending=True)

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        _set_run(conn, 9800, run)
    finally:
        conn.close()

    with patch.object(dts, "DB_PATH", db), patch.object(ds, "DB_PATH", db):
        with patch.object(dts, "save_dungeon_checkpoint") as mock_cp:
            result = dts.on_boss_tile_cleared(9800, 9800)

    assert result["is_boss_tile"] is True
    mock_cp.assert_not_called()  # no double-checkpoint


# ── T6: extend_dungeon_for_endless n=0 — tile_count unchanged ─────────────────

def test_l8_t6_extend_endless_n0_same_length(db):
    """extend_dungeon_for_endless with n=0: new segment has same tile_count as base."""
    run = _make_run(cycle=1)

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        _set_run(conn, 9800, run)
        # Set endless_growth_n=0 (default) and tile_count=4
        conn.execute("UPDATE game_dungeons SET tile_count=4, endless_growth_n=0 WHERE key='test_l8'")
        conn.commit()
    finally:
        conn.close()

    with patch.object(dts, "DB_PATH", db), patch.object(ds, "DB_PATH", db):
        result = dts.extend_dungeon_for_endless(9800, 9800)

    # n=0: length = 4 + 0*(2-1) = 4
    assert result["ok"] is True
    assert result["new_cycle"] == 2
    assert result["new_segment_tile_count"] == 4, (
        f"n=0: segment must stay at base tile_count=4, got {result['new_segment_tile_count']}"
    )


# ── T7: extend_dungeon_for_endless n=2 — length grows ────────────────────────

def _minimal_graph(entry="node_0", boss="node_1"):
    """Return a minimal 2-node graph for mocking draw_tile_graph."""
    return {
        "entry_node": entry,
        "boss_node": boss,
        "nodes": {
            entry: {
                "tile_id": 1, "position": [0, 0],
                "doors_open": {"S": boss, "N": None},
                "door_hints": {}, "content": {"is_boss_tile": False, "enemies": []},
                "visited": False, "cleared": False, "is_boss": False,
            },
            boss: {
                "tile_id": 5, "position": [0, 1],
                "doors_open": {"N": entry, "S": None},
                "door_hints": {}, "content": {"is_boss_tile": True, "enemies": []},
                "visited": False, "cleared": False, "is_boss": True,
            },
        },
    }


def test_l8_t7_extend_endless_n2_grows(db):
    """extend_dungeon_for_endless with n=2: new_segment_tile_count = base + n*(cycle-1)."""
    run = _make_run(cycle=1)

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        _set_run(conn, 9800, run)
        conn.execute("UPDATE game_dungeons SET tile_count=4, endless_growth_n=2 WHERE key='test_l8'")
        conn.commit()
    finally:
        conn.close()

    # Mock draw_tile_graph to return a minimal valid graph (avoids tile pool constraints)
    with patch.object(dts, "DB_PATH", db), patch.object(ds, "DB_PATH", db):
        with patch.object(dts, "draw_tile_graph", return_value=_minimal_graph()) as mock_dtg:
            result = dts.extend_dungeon_for_endless(9800, 9800)

    # n=2: cycle 1→2: length = 4 + 2*(2-1) = 6
    assert result["new_segment_tile_count"] == 6, (
        f"n=2 cycle 2: expected 6, got {result['new_segment_tile_count']}"
    )
    # Verify draw_tile_graph was called with the computed tile_count
    mock_dtg.assert_called_once()
    _, call_tile_count = mock_dtg.call_args[0][0], mock_dtg.call_args[0][1]
    assert call_tile_count == 6, f"draw_tile_graph must receive tile_count=6, got {call_tile_count}"


# ── T8: extend_dungeon_for_endless 3-cycle loop lengths ──────────────────────

def test_l8_t8_three_cycle_segment_lengths_n2(db):
    """3-cycle endless loop: verify lengths 4, 6, 8 for n=2 (mocked draw_tile_graph)."""
    # Cycle 1→2: length=4+2*1=6; cycle 2→3: length=4+2*2=8
    base = 4
    n = 2
    with patch.object(dts, "DB_PATH", db), patch.object(ds, "DB_PATH", db):
        with patch.object(dts, "draw_tile_graph", return_value=_minimal_graph()):
            for target_cycle in [2, 3]:
                expected = base + n * (target_cycle - 1)
                run = _make_run(cycle=target_cycle - 1)
                conn = sqlite3.connect(db)
                conn.row_factory = sqlite3.Row
                try:
                    _set_run(conn, 9800, run)
                    conn.execute("UPDATE game_dungeons SET tile_count=?,endless_growth_n=? WHERE key='test_l8'",
                                 (base, n))
                    conn.commit()
                finally:
                    conn.close()

                result = dts.extend_dungeon_for_endless(9800, 9800)
                assert result["new_segment_tile_count"] == expected, (
                    f"Cycle {target_cycle}: expected tile_count={expected}, got {result['new_segment_tile_count']}"
                )


# ── T9: extend_dungeon_for_endless — cycle+1, flags reset ────────────────────

def test_l8_t9_extend_cycle_increments_and_flags_reset(db):
    """After go_deeper: cycle=2, at_checkpoint=False, boss_choice_pending=False."""
    run = _make_run(cycle=1, boss_choice_pending=True)
    run["at_checkpoint"] = True  # boss was defeated

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        _set_run(conn, 9800, run)
    finally:
        conn.close()

    with patch.object(dts, "DB_PATH", db), patch.object(ds, "DB_PATH", db):
        result = dts.extend_dungeon_for_endless(9800, 9800)

    assert result["new_cycle"] == 2

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        updated_run = _get_run(conn, 9800)
    finally:
        conn.close()

    assert updated_run["cycle"] == 2, "cycle must be incremented to 2"
    assert updated_run["at_checkpoint"] is False, "at_checkpoint reset to False"
    assert updated_run["boss_choice_pending"] is False, "boss_choice_pending reset to False"


# ── T10: extend_dungeon_for_endless — new nodes in graph ─────────────────────

def test_l8_t10_extend_new_nodes_added_to_graph(db):
    """After go_deeper, graph contains new cycle-prefixed nodes."""
    run = _make_run(cycle=1)

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        _set_run(conn, 9800, run)
    finally:
        conn.close()

    with patch.object(dts, "DB_PATH", db), patch.object(ds, "DB_PATH", db):
        result = dts.extend_dungeon_for_endless(9800, 9800)

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        updated_run = _get_run(conn, 9800)
    finally:
        conn.close()

    nodes = updated_run["graph"]["nodes"]
    cycle_prefix = "c2_"
    new_nodes = [k for k in nodes if k.startswith(cycle_prefix)]
    assert len(new_nodes) > 0, "No new cycle-prefixed nodes found after go_deeper"

    # Boss node connects to new entry
    old_boss_nid = "node_boss"
    boss_node = nodes.get(old_boss_nid) or {}
    boss_doors = boss_node.get("doors_open") or {}
    assert result["new_entry_node"] in boss_doors.values(), (
        f"Boss node must have door pointing to new entry {result['new_entry_node']}"
    )


# ── T11: 3-cycle loop checkpoint after each boss ─────────────────────────────

def test_l8_t11_checkpoint_saved_per_boss_cycle(db):
    """Checkpoint saved after each boss defeat (via on_boss_tile_cleared)."""
    checkpoints_saved = []

    def mock_checkpoint(campaign_id, character_id):
        checkpoints_saved.append({"campaign": campaign_id, "char": character_id})
        return {"cycle": len(checkpoints_saved), "source": "dungeon_boss_checkpoint"}

    for cycle_num in [1, 2, 3]:
        run = _make_run(cycle=cycle_num)

        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        try:
            _set_run(conn, 9800, run)
        finally:
            conn.close()

        with patch.object(dts, "DB_PATH", db), patch.object(ds, "DB_PATH", db):
            with patch.object(dts, "save_dungeon_checkpoint", side_effect=mock_checkpoint):
                result = dts.on_boss_tile_cleared(9800, 9800)

        assert result["is_boss_tile"] is True, f"Cycle {cycle_num}: expected boss tile"

    assert len(checkpoints_saved) == 3, f"Expected 3 checkpoints, got {len(checkpoints_saved)}"


# ── T12: enemy scaling cycle 2 vs cycle 1 ────────────────────────────────────

def test_l8_t12_enemy_scaling_cycle2_vs_cycle1():
    """scale_enemy_for_dungeon_tier cycle 2 → +1 effective level → higher HP than cycle 1."""
    base = {
        "hp_base": 5, "ac_base": 8, "attack_bonus": 0, "damage_bonus": 0,
        "stats_json": '{"CON": 14}',  # CON_mod=2, scaling visible
    }
    with patch("app.services.dungeon_tile_service.random") as mock_rnd:
        # Tier 1: lvl range 1–2; fix to lvl 1 for both calls
        mock_rnd.randint.return_value = 1
        mock_rnd.choice = __import__("random").choice
        mock_rnd.sample = __import__("random").sample
        scaled_c1 = dts.scale_enemy_for_dungeon_tier(dict(base), 1, is_boss=False, cycle=1)
        scaled_c2 = dts.scale_enemy_for_dungeon_tier(dict(base), 1, is_boss=False, cycle=2)

    assert scaled_c2["hp_base"] > scaled_c1["hp_base"], (
        f"Cycle 2 enemy must have more HP than cycle 1: {scaled_c1['hp_base']} vs {scaled_c2['hp_base']}"
    )
