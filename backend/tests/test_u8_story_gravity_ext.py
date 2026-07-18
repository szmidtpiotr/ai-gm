"""TDD: #532 U8 — Story Gravity extensions: dungeon pause, l3_enabled_gotowa per campaign type."""
import json
import sqlite3
import sys

sys.path.insert(0, "/app")
from _fixtures_schema import table_sql


def _make_db(plan_turns=0, template_key=None, dungeon_run=None, turns_since=20):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY,
            gm_plan_json TEXT,
            source_template_id INTEGER DEFAULT NULL
        );
        CREATE TABLE campaign_turns (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER,
            turn_number INTEGER
        );
        """ + table_sql("game_config_meta") + """
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER,
            session_flags TEXT DEFAULT '{}'
        );
    """)
    # Plan with no beat visited → stagnation = all turns
    plan = {"acts": [{"key_beats": [{"beat_key": "b1", "visited": False}]}]}
    # template_key maps to source_template_id (use 1 if set, NULL if not)
    src_tmpl_id = 1 if template_key else None
    conn.execute(
        "INSERT INTO campaigns VALUES (1, ?, ?)",
        (json.dumps(plan), src_tmpl_id),
    )
    # Insert turns so MAX(turn_number) = turns_since
    for i in range(1, turns_since + 1):
        conn.execute("INSERT INTO campaign_turns VALUES (?, 1, ?)", (i, i))

    session_flags = {}
    if dungeon_run:
        session_flags["dungeon_run"] = {"dungeon_key": "test_dungeon"}
    conn.execute(
        "INSERT INTO game_sessions VALUES (1, 1, ?)",
        (json.dumps(session_flags),),
    )
    conn.commit()
    return conn


# ─── Dungeon pause ────────────────────────────────────────────────────────────

def test_dungeon_pause_returns_level_zero():
    """Story Gravity returns level=0 when player is in dungeon."""
    from app.services.story_gravity_service import compute_story_gravity

    # 20 turns without beat → normally would be L3, but dungeon_run is set
    conn = _make_db(turns_since=20, dungeon_run=True)
    result = compute_story_gravity(1, conn)
    assert result["level"] == 0, "Dungeon run should pause Story Gravity"


def test_no_dungeon_gives_normal_gravity():
    """Without dungeon_run, Story Gravity escalates normally."""
    from app.services.story_gravity_service import compute_story_gravity

    conn = _make_db(turns_since=20, dungeon_run=False)
    result = compute_story_gravity(1, conn)
    assert result["level"] >= 1, "20 turns without beat should give L1 or higher"


# ─── L3 per campaign type ─────────────────────────────────────────────────────

def test_l3_enabled_gotowa_in_defaults():
    """l3_enabled_gotowa=True is in default Story Gravity config."""
    # Import the module to get _DEFAULTS
    import importlib
    import app.services.story_gravity_service as sg
    importlib.reload(sg)
    assert "l3_enabled_gotowa" in sg._DEFAULTS
    assert sg._DEFAULTS["l3_enabled_gotowa"] is True


def test_gotowa_kampania_l3_active_with_l3_enabled_gotowa():
    """Gotowa Kampania (template_key set) uses l3_enabled_gotowa for L3 check."""
    from app.services.story_gravity_service import compute_story_gravity, set_story_gravity_config

    # Use in-memory conn with game_config_meta
    conn = _make_db(turns_since=20, template_key="some_template")

    # Configure: l3_enabled=False (global OFF), l3_enabled_gotowa=True
    conn.execute(
        "INSERT OR REPLACE INTO game_config_meta VALUES ('story_gravity_config', ?)",
        (json.dumps({
            "enabled": True,
            "turns_l1": 5,
            "turns_l2": 10,
            "turns_l3": 15,
            "l3_enabled": False,
            "l3_enabled_gotowa": True,
        }),)
    )
    conn.commit()

    result = compute_story_gravity(1, conn)
    # 20 turns, template_key set, l3_enabled_gotowa=True → should be L3
    assert result["level"] == 3, f"Gotowa Kampania should reach L3 but got {result['level']}"


def test_nowa_kampania_l3_off_with_l3_enabled_false():
    """Nowa Kampania (no template_key) uses l3_enabled for L3 — stays at L2 when l3_enabled=False."""
    from app.services.story_gravity_service import compute_story_gravity

    conn = _make_db(turns_since=20, template_key=None)

    # Configure: l3_enabled=False, l3_enabled_gotowa=True
    conn.execute(
        "INSERT OR REPLACE INTO game_config_meta VALUES ('story_gravity_config', ?)",
        (json.dumps({
            "enabled": True,
            "turns_l1": 5,
            "turns_l2": 10,
            "turns_l3": 15,
            "l3_enabled": False,
            "l3_enabled_gotowa": True,
        }),)
    )
    conn.commit()

    result = compute_story_gravity(1, conn)
    # 20 turns, no template_key, l3_enabled=False → should be L2 max
    assert result["level"] == 2, f"Nowa Kampania should stop at L2 but got {result['level']}"


def test_turns_since_beat_in_response():
    """compute_story_gravity returns turns_since_beat correctly."""
    from app.services.story_gravity_service import compute_story_gravity

    conn = _make_db(turns_since=7)
    result = compute_story_gravity(1, conn)
    assert result["turns_since_beat"] == 7
