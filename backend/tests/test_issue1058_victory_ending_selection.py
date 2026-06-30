"""TDD: Issue #1058 — victory ending selection matches player choices, not always endings[0]."""
import json
import sqlite3
import sys
import pytest

sys.path.insert(0, "/app")


# ─── helpers we are about to add ─────────────────────────────────────────────

def _make_plan(endings):
    return {"endings": endings}

ENDINGS_LIST = [
    {
        "id": "ending_primary",
        "title": "Milczący porządek",
        "type": "primary",
        "description": "Gorzki łald",
        "requirements": ["ksiega_znakow nie zostaje ujawniona"],
    },
    {
        "id": "ending_alternate",
        "title": "Pęknięty łańcuch",
        "type": "alternate",
        "description": "Częściowe wyzwolenie",
        "requirements": ["Mizel ujawnia ksiega_znakow"],
    },
]

ENDINGS_DICT = {
    "ending_primary": ENDINGS_LIST[0],
    "ending_alternate": ENDINGS_LIST[1],
}


# ─── Test 1: _find_ending_by_id — list form ──────────────────────────────────

def test_find_ending_by_id_list():
    """_find_ending_by_id must locate ending by id in list form."""
    from app.services.solo_death_service import _find_ending_by_id

    result = _find_ending_by_id(ENDINGS_LIST, "ending_alternate")
    assert result is not None, "_find_ending_by_id returned None for valid id in list"
    assert result["id"] == "ending_alternate"
    assert result["title"] == "Pęknięty łańcuch"


# ─── Test 2: _find_ending_by_id — dict form ──────────────────────────────────

def test_find_ending_by_id_dict():
    """_find_ending_by_id must locate ending by id in dict form."""
    from app.services.solo_death_service import _find_ending_by_id

    result = _find_ending_by_id(ENDINGS_DICT, "ending_primary")
    assert result is not None
    assert result["id"] == "ending_primary"


# ─── Test 3: _find_primary_type_ending ignores position, picks by type ───────

def test_find_primary_type_ending_not_index_zero():
    """_find_primary_type_ending picks type='primary' even if not at index 0."""
    from app.services.solo_death_service import _find_primary_type_ending

    # Reverse order: alternate first, primary second
    reversed_endings = [
        {"id": "ending_alternate", "type": "alternate", "title": "Alt"},
        {"id": "ending_primary", "type": "primary", "title": "Primary"},
    ]
    result = _find_primary_type_ending(reversed_endings)
    assert result is not None
    assert result["type"] == "primary"
    assert result["id"] == "ending_primary"


# ─── Test 4: end_summary_payload returns ending_type field ───────────────────

def test_end_summary_payload_returns_ending_type():
    """Victory payload must include 'ending_type' field."""
    from app.services.solo_death_service import end_summary_payload

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY, status TEXT, death_reason TEXT,
            ended_at TEXT, epitaph TEXT, gm_plan_json TEXT,
            model_id TEXT DEFAULT 'test', owner_user_id INTEGER DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY, name TEXT, sheet_json TEXT,
            campaign_id INTEGER, user_id INTEGER DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE campaign_turns (
            id INTEGER PRIMARY KEY, campaign_id INTEGER,
            turn_number INTEGER, user_text TEXT, assistant_text TEXT
        )
    """)
    plan = {
        "selected_ending_id": "ending_alternate",
        "endings": ENDINGS_LIST,
    }
    conn.execute(
        "INSERT INTO campaigns VALUES (1,'completed',NULL,NULL,NULL,?,?,1)",
        (json.dumps(plan), "test_model"),
    )
    conn.execute(
        "INSERT INTO characters VALUES (1,'Mizel','{}',1,1)"
    )
    conn.commit()

    result = end_summary_payload(conn, campaign_id=1)
    assert result is not None, "end_summary_payload returned None for completed campaign"
    assert "ending_type" in result, f"'ending_type' missing from result keys: {list(result.keys())}"
    assert result["ending_type"] == "alternate", f"Expected 'alternate', got: {result['ending_type']}"
    assert result["ending_title"] == "Pęknięty łańcuch"


# ─── Test 5: maybe_complete_campaign sets ended_at ───────────────────────────

def test_maybe_complete_campaign_sets_ended_at():
    """maybe_complete_campaign must write ended_at when campaign completes."""
    from app.services.campaign_plan_runtime import maybe_complete_campaign

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY, status TEXT, ended_at TEXT,
            gm_plan_json TEXT, model_id TEXT DEFAULT 'test',
            owner_user_id INTEGER DEFAULT 1, epitaph TEXT, death_reason TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE character_quests (
            id INTEGER PRIMARY KEY, character_id INTEGER,
            campaign_id INTEGER, status TEXT, quest_type TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, session_flags TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE game_events (
            id INTEGER PRIMARY KEY, event_type TEXT, campaign_id INTEGER,
            character_id INTEGER, user_id INTEGER, data_json TEXT,
            severity TEXT DEFAULT 'info', created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # All acts completed
    plan = {
        "active_act": 1,
        "acts": [
            {"title": "Act 1", "completed": True, "key_beats": []},
        ],
        "endings": ENDINGS_LIST,
    }
    conn.execute(
        "INSERT INTO campaigns VALUES (1,'active',NULL,?,?,1,NULL,NULL)",
        (json.dumps(plan), "test_model"),
    )
    conn.commit()

    result = maybe_complete_campaign(1, 1, 5, conn)
    assert result is True, "maybe_complete_campaign should return True on first completion"

    row = conn.execute("SELECT status, ended_at FROM campaigns WHERE id = 1").fetchone()
    assert row["status"] == "completed"
    assert row["ended_at"] is not None, "ended_at must be set after victory"
    assert len(row["ended_at"]) > 0, "ended_at must not be empty string"


# ─── Test 6: _store_selected_ending writes ending_id to gm_plan_json ─────────

def test_store_selected_ending_writes_to_gm_plan():
    """_store_selected_ending must update gm_plan_json.selected_ending_id in DB."""
    from app.services.solo_death_service import _store_selected_ending

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    plan = {"selected_ending_id": None, "endings": ENDINGS_LIST}
    conn.execute("""
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY, status TEXT, gm_plan_json TEXT,
            ended_at TEXT
        )
    """)
    conn.execute(
        "INSERT INTO campaigns VALUES (1,'completed',?,NULL)",
        (json.dumps(plan),),
    )
    conn.commit()

    _store_selected_ending(conn, campaign_id=1, ending_id="ending_alternate")

    row = conn.execute("SELECT gm_plan_json FROM campaigns WHERE id = 1").fetchone()
    updated_plan = json.loads(row["gm_plan_json"])
    assert updated_plan.get("selected_ending_id") == "ending_alternate", (
        f"expected 'ending_alternate' in selected_ending_id, got: {updated_plan.get('selected_ending_id')}"
    )


# ─── Test 7: backward compat — death path returns same fields ─────────────────

def test_death_payload_still_works():
    """Death campaign payload must still return outcome='death' with expected fields."""
    from app.services.solo_death_service import end_summary_payload

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY, status TEXT, death_reason TEXT,
            ended_at TEXT, epitaph TEXT, gm_plan_json TEXT,
            model_id TEXT DEFAULT 'test', owner_user_id INTEGER DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY, name TEXT, sheet_json TEXT,
            campaign_id INTEGER, user_id INTEGER DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE campaign_turns (
            id INTEGER PRIMARY KEY, campaign_id INTEGER,
            turn_number INTEGER, user_text TEXT, assistant_text TEXT
        )
    """)
    conn.execute(
        "INSERT INTO campaigns VALUES (2,'ended','Killed by a dragon','2025-01-01','Here lies a hero','{}','test_model',1)"
    )
    conn.execute(
        "INSERT INTO characters VALUES (1,'Warrior','{}',2,1)"
    )
    conn.commit()

    result = end_summary_payload(conn, campaign_id=2)
    assert result is not None
    assert result["outcome"] == "death"
    assert result["death_reason"] == "Killed by a dragon"
    assert result["epitaph"] == "Here lies a hero"
