"""TDD: Issue #562 (U14) — pełny reset bohatera przy nowej kampanii.

C19 resetował tylko HP (mana dorzucona później). U14 rozszerza reset na:
- conditions w sheet_json → []
- wiersze w tabeli character_conditions → usunięte
- aktywne character_rentals → status='expired'
- flaga sandbox __sandbox_clone__ w sheet → usunięta
NIE rusza XP / złota / ekwipunku / zaklęć.
Reset tylko na świeżej kampanii (0 tur); wznowienie istniejącej kampanii nie rusza stanu.
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
    status TEXT NOT NULL DEFAULT 'idle',
    gold_gp INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL DEFAULT 'Test',
    status TEXT NOT NULL DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS campaign_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    character_id INTEGER NOT NULL,
    turn_number INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS character_conditions (
    id INTEGER PRIMARY KEY,
    character_id INTEGER NOT NULL,
    condition_type TEXT NOT NULL,
    severity INTEGER DEFAULT 1,
    rounds_remaining INTEGER,
    expires_at TEXT,
    source TEXT,
    effect_json TEXT
);
CREATE TABLE IF NOT EXISTS character_rentals (
    id INTEGER PRIMARY KEY,
    character_id INTEGER NOT NULL,
    campaign_id INTEGER,
    expires_at_turn INTEGER NOT NULL DEFAULT 5,
    status TEXT NOT NULL DEFAULT 'active'
);
"""


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _add_character(conn, char_id=1, sheet=None, campaign_id=None, gold=100):
    if sheet is None:
        sheet = {"current_hp": 3, "max_hp": 45, "level": 1, "archetype": "warrior"}
    conn.execute(
        "INSERT INTO characters(id, name, user_id, campaign_id, sheet_json, status, gold_gp) "
        "VALUES(?,?,1,?,?,?,?)",
        (char_id, "Hero", campaign_id, json.dumps(sheet),
         "idle" if campaign_id is None else "in_campaign", gold),
    )
    conn.commit()


def _add_campaign(conn, camp_id=1):
    conn.execute("INSERT INTO campaigns(id, title) VALUES(?,?)", (camp_id, "Test"))
    conn.commit()


def _add_turn(conn, campaign_id, character_id):
    conn.execute(
        "INSERT INTO campaign_turns(campaign_id, character_id) VALUES(?,?)",
        (campaign_id, character_id),
    )
    conn.commit()


def _sheet(conn, char_id=1):
    row = conn.execute("SELECT sheet_json FROM characters WHERE id=?", (char_id,)).fetchone()
    return json.loads(row["sheet_json"])


# ─── Test główny: conditions czyszczone w sheet ──────────────────────────────

def test_conditions_cleared_in_sheet_on_fresh_campaign():
    from app.services.character_campaign_service import maybe_reset_hp_for_new_campaign
    conn = _make_db()
    _add_character(conn, sheet={
        "current_hp": 3, "max_hp": 45, "level": 1, "archetype": "scholar",
        "current_mana": 0, "max_mana": 20, "conditions": ["poisoned", "frightened"],
    })
    _add_campaign(conn)
    maybe_reset_hp_for_new_campaign(conn, character_id=1, campaign_id=1)
    sheet = _sheet(conn)
    assert sheet["conditions"] == [], "conditions w sheet muszą być puste po resecie"
    assert sheet["current_mana"] == 20, "mana pełna po resecie"
    assert sheet["current_hp"] == 45, "HP pełne po resecie"


def test_character_conditions_table_cleared_on_fresh_campaign():
    from app.services.character_campaign_service import maybe_reset_hp_for_new_campaign
    conn = _make_db()
    _add_character(conn)
    _add_campaign(conn)
    conn.execute("INSERT INTO character_conditions(character_id, condition_type) VALUES(1,'poisoned')")
    conn.execute("INSERT INTO character_conditions(character_id, condition_type) VALUES(1,'bleeding')")
    conn.commit()
    maybe_reset_hp_for_new_campaign(conn, character_id=1, campaign_id=1)
    cnt = conn.execute("SELECT COUNT(*) FROM character_conditions WHERE character_id=1").fetchone()[0]
    assert cnt == 0, "wiersze character_conditions muszą zniknąć po resecie"


def test_active_rentals_expired_on_fresh_campaign():
    from app.services.character_campaign_service import maybe_reset_hp_for_new_campaign
    conn = _make_db()
    _add_character(conn)
    _add_campaign(conn)
    conn.execute("INSERT INTO character_rentals(character_id, status) VALUES(1,'active')")
    conn.commit()
    maybe_reset_hp_for_new_campaign(conn, character_id=1, campaign_id=1)
    status = conn.execute("SELECT status FROM character_rentals WHERE character_id=1").fetchone()[0]
    assert status == "expired", "aktywny rental musi być wygaszony po resecie"


def test_sandbox_flag_popped_on_fresh_campaign():
    from app.services.character_campaign_service import maybe_reset_hp_for_new_campaign
    conn = _make_db()
    _add_character(conn, sheet={
        "current_hp": 3, "max_hp": 45, "__sandbox_clone__": True,
    })
    _add_campaign(conn)
    maybe_reset_hp_for_new_campaign(conn, character_id=1, campaign_id=1)
    sheet = _sheet(conn)
    assert "__sandbox_clone__" not in sheet, "wisząca flaga sandbox musi być usunięta"


# ─── Niezmienność: XP / złoto / ekwipunek / zaklęcia ─────────────────────────

def test_gold_xp_untouched_on_reset():
    from app.services.character_campaign_service import maybe_reset_hp_for_new_campaign
    conn = _make_db()
    _add_character(conn, sheet={
        "current_hp": 3, "max_hp": 45, "xp": 1234, "gold": 999, "conditions": ["poisoned"],
    }, gold=777)
    _add_campaign(conn)
    maybe_reset_hp_for_new_campaign(conn, character_id=1, campaign_id=1)
    sheet = _sheet(conn)
    assert sheet["xp"] == 1234, "XP nietknięte"
    assert sheet["gold"] == 999, "złoto w sheet nietknięte"
    gold_col = conn.execute("SELECT gold_gp FROM characters WHERE id=1").fetchone()[0]
    assert gold_col == 777, "kolumna gold_gp nietknięta"


# ─── Backward compat / guard: wznowienie istniejącej kampanii ────────────────

def test_conditions_not_reset_on_existing_campaign():
    from app.services.character_campaign_service import maybe_reset_hp_for_new_campaign
    conn = _make_db()
    _add_character(conn, sheet={
        "current_hp": 3, "max_hp": 45, "conditions": ["poisoned"],
    }, campaign_id=1)
    _add_campaign(conn)
    _add_turn(conn, 1, 1)  # kampania ma już tury → wznowienie
    result = maybe_reset_hp_for_new_campaign(conn, character_id=1, campaign_id=1)
    assert result is False, "wznowienie nie resetuje"
    sheet = _sheet(conn)
    assert sheet["conditions"] == ["poisoned"], "conditions zachowane przy wznowieniu"
    assert sheet["current_hp"] == 3, "HP zachowane przy wznowieniu"


def test_hp_reset_still_works():
    """C19 regression — podstawowy reset HP nadal działa."""
    from app.services.character_campaign_service import maybe_reset_hp_for_new_campaign
    conn = _make_db()
    _add_character(conn, sheet={"current_hp": 3, "max_hp": 45})
    _add_campaign(conn)
    result = maybe_reset_hp_for_new_campaign(conn, character_id=1, campaign_id=1)
    assert result is True
    assert _sheet(conn)["current_hp"] == 45
