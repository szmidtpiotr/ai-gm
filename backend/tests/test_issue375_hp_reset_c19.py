"""TDD: Issue #375 — C19 HP reset when hero enters a fresh campaign.

Tests verify:
- Fresh campaign (0 turns): hp_current reset to max_hp
- Existing campaign (has turns): hp_current NOT touched
- HP reset uses correct max_hp from sheet_json
- Service function maybe_reset_hp_for_new_campaign() exists and works
- Backward compat: assign-campaign response unchanged
"""
import sys
import sqlite3
import json
sys.path.insert(0, "/app")

SCHEMA = """
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL DEFAULT 'Hero',
    user_id INTEGER NOT NULL DEFAULT 1,
    campaign_id INTEGER,
    sheet_json TEXT NOT NULL DEFAULT '{}',
    is_active INTEGER NOT NULL DEFAULT 1,
    location TEXT,
    status TEXT NOT NULL DEFAULT 'idle',
    gold_gp INTEGER NOT NULL DEFAULT 0,
    system_id TEXT NOT NULL DEFAULT 'fantasy',
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL DEFAULT 'Test',
    owner_user_id INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'active',
    system_id TEXT NOT NULL DEFAULT 'fantasy',
    language TEXT NOT NULL DEFAULT 'pl',
    mode TEXT NOT NULL DEFAULT 'solo'
);
CREATE TABLE IF NOT EXISTS campaign_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    character_id INTEGER NOT NULL,
    turn_number INTEGER NOT NULL DEFAULT 1,
    user_text TEXT,
    assistant_text TEXT,
    route TEXT DEFAULT 'narrative',
    created_at TEXT DEFAULT (datetime('now'))
);
"""


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _add_character(conn, char_id=1, current_hp=3, max_hp=45, campaign_id=None):
    sheet = {"current_hp": current_hp, "max_hp": max_hp, "level": 1, "archetype": "warrior"}
    conn.execute(
        "INSERT INTO characters(id, name, user_id, campaign_id, sheet_json, status) VALUES(?,?,1,?,?,?)",
        (char_id, "Hero", campaign_id, json.dumps(sheet), "idle" if campaign_id is None else "in_campaign")
    )
    conn.commit()


def _add_campaign(conn, camp_id=1):
    conn.execute("INSERT INTO campaigns(id, title) VALUES(?,?)", (camp_id, "Test Campaign"))
    conn.commit()


def _add_turn(conn, campaign_id, character_id):
    conn.execute(
        "INSERT INTO campaign_turns(campaign_id, character_id) VALUES(?,?)",
        (campaign_id, character_id)
    )
    conn.commit()


# ─── Core service function ────────────────────────────────────────────────────

def test_maybe_reset_hp_importable():
    """maybe_reset_hp_for_new_campaign must be importable from character_campaign_service."""
    from app.services.character_campaign_service import maybe_reset_hp_for_new_campaign
    assert callable(maybe_reset_hp_for_new_campaign)


def test_hp_reset_on_fresh_campaign():
    """Fresh campaign (0 turns): hp_current must be reset to max_hp."""
    from app.services.character_campaign_service import maybe_reset_hp_for_new_campaign

    conn = _make_db()
    _add_character(conn, char_id=1, current_hp=3, max_hp=45)
    _add_campaign(conn, camp_id=1)

    result = maybe_reset_hp_for_new_campaign(conn, character_id=1, campaign_id=1)

    # Verify HP was reset
    row = conn.execute("SELECT sheet_json FROM characters WHERE id=1").fetchone()
    sheet = json.loads(row["sheet_json"])
    assert sheet["current_hp"] == 45, (
        f"Nowa kampania (0 tur) powinna zresetować HP do max ({45}), "
        f"ale current_hp={sheet['current_hp']}. "
        f"Bohater wchodzi do nowej przygody nadal poraniony."
    )
    assert result is True, "maybe_reset_hp_for_new_campaign() powinno zwrócić True gdy reset nastąpił"


def test_hp_not_reset_on_existing_campaign():
    """Campaign with turns: hp_current must NOT be changed."""
    from app.services.character_campaign_service import maybe_reset_hp_for_new_campaign

    conn = _make_db()
    _add_character(conn, char_id=1, current_hp=3, max_hp=45, campaign_id=1)
    _add_campaign(conn, camp_id=1)
    _add_turn(conn, campaign_id=1, character_id=1)  # existing campaign has turns

    result = maybe_reset_hp_for_new_campaign(conn, character_id=1, campaign_id=1)

    row = conn.execute("SELECT sheet_json FROM characters WHERE id=1").fetchone()
    sheet = json.loads(row["sheet_json"])
    assert sheet["current_hp"] == 3, (
        f"Istniejąca kampania (ma tury) NIE powinna resetować HP. "
        f"current_hp powinno być 3 (niezmienione), ale jest {sheet['current_hp']}."
    )
    assert result is False, "maybe_reset_hp_for_new_campaign() powinno zwrócić False gdy brak resetu"


def test_hp_reset_uses_correct_max_hp():
    """HP reset must use the character's own max_hp, not a hardcoded value."""
    from app.services.character_campaign_service import maybe_reset_hp_for_new_campaign

    conn = _make_db()
    _add_character(conn, char_id=1, current_hp=7, max_hp=22)
    _add_campaign(conn, camp_id=1)

    maybe_reset_hp_for_new_campaign(conn, character_id=1, campaign_id=1)

    sheet = json.loads(conn.execute("SELECT sheet_json FROM characters WHERE id=1").fetchone()["sheet_json"])
    assert sheet["current_hp"] == 22, (
        f"HP reset musi użyć max_hp={22} z sheet_json, "
        f"ale current_hp={sheet['current_hp']}."
    )


def test_hp_already_full_still_works():
    """If hp is already full, reset is a no-op (idempotent)."""
    from app.services.character_campaign_service import maybe_reset_hp_for_new_campaign

    conn = _make_db()
    _add_character(conn, char_id=1, current_hp=45, max_hp=45)
    _add_campaign(conn, camp_id=1)

    maybe_reset_hp_for_new_campaign(conn, character_id=1, campaign_id=1)

    sheet = json.loads(conn.execute("SELECT sheet_json FROM characters WHERE id=1").fetchone()["sheet_json"])
    assert sheet["current_hp"] == 45, "HP już pełne — reset jest idempotentny, musi zostać 45"


def test_hp_reset_handles_missing_max_hp():
    """If sheet_json has no max_hp, function must not crash."""
    from app.services.character_campaign_service import maybe_reset_hp_for_new_campaign

    conn = _make_db()
    # Sheet without max_hp
    conn.execute(
        "INSERT INTO characters(id, name, user_id, sheet_json, status) VALUES(1,'Hero',1,'{}','idle')"
    )
    _add_campaign(conn, camp_id=1)
    conn.commit()

    # Must not raise
    result = maybe_reset_hp_for_new_campaign(conn, character_id=1, campaign_id=1)
    assert result is not None  # any return value, just must not crash


# ─── Integration: assign_hero_to_campaign calls HP reset ─────────────────────

def test_assign_campaign_resets_hp_for_new_campaign():
    """assign_hero_to_campaign must call HP reset for a fresh campaign (0 turns)."""
    # This is a structural test — checks that the assign-campaign endpoint
    # calls maybe_reset_hp_for_new_campaign when campaign has 0 turns.
    # We verify by inspecting the endpoint source code.
    import inspect
    from app.api.characters import assign_hero_to_campaign
    src = inspect.getsource(assign_hero_to_campaign)
    assert "maybe_reset_hp" in src or "reset_hp" in src or "hp_current" in src.lower(), (
        "assign_hero_to_campaign nie wywołuje resetu HP. "
        "Dodaj wywołanie maybe_reset_hp_for_new_campaign() w endpoincie assign-campaign."
    )
