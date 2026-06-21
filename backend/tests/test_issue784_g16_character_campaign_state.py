"""TDD #784 G16 — character_campaign_state: per-campaign HP/mana/conditions isolation."""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ─── minimal schema ──────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL DEFAULT 'x',
    display_name TEXT NOT NULL DEFAULT ''
);
INSERT INTO users (id, username) VALUES (1, 'alice'), (2, 'bob');

CREATE TABLE campaigns (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL DEFAULT 'T',
    system_id TEXT NOT NULL DEFAULT 'fantasy',
    model_id TEXT NOT NULL DEFAULT 'm',
    owner_user_id INTEGER NOT NULL DEFAULT 1,
    mode TEXT NOT NULL DEFAULT 'solo',
    status TEXT NOT NULL DEFAULT 'active',
    lobby_status TEXT NOT NULL DEFAULT 'open',
    max_players INTEGER NOT NULL DEFAULT 4,
    round_timer_hours INTEGER NOT NULL DEFAULT 24,
    round_timer_minutes INTEGER NOT NULL DEFAULT 1440,
    host_user_id INTEGER
);

CREATE TABLE characters (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER,
    user_id INTEGER NOT NULL DEFAULT 1,
    name TEXT NOT NULL DEFAULT 'Hero',
    system_id TEXT NOT NULL DEFAULT 'fantasy',
    sheet_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'idle',
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE campaign_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'player',
    status TEXT NOT NULL DEFAULT 'invited',
    character_id INTEGER,
    UNIQUE(campaign_id, user_id)
);

CREATE TABLE character_campaign_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL,
    campaign_id INTEGER NOT NULL,
    current_hp INTEGER NOT NULL DEFAULT 0,
    max_hp INTEGER NOT NULL DEFAULT 0,
    current_mana INTEGER NOT NULL DEFAULT 0,
    max_mana INTEGER NOT NULL DEFAULT 0,
    conditions_json TEXT NOT NULL DEFAULT '[]',
    position_json TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(character_id, campaign_id)
);
"""


def _mk_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


# ─── imports under test ──────────────────────────────────────────────────────

from app.services.campaign_state_service import (  # noqa: E402
    is_mp_campaign,
    get_battle_state,
    save_battle_state,
    create_initial_state,
    overlay_sheet_from_campaign_state,
)


# ─── helpers ─────────────────────────────────────────────────────────────────

def _seed(conn, *, solo_id=1, mp_id=2, char_id=1, hp=20, mana=8):
    conn.execute("INSERT INTO campaigns (id, mode) VALUES (?, 'solo')", (solo_id,))
    conn.execute("INSERT INTO campaigns (id, mode, lobby_status) VALUES (?, 'multiplayer', 'open')", (mp_id,))
    sheet = json.dumps({"current_hp": hp, "max_hp": hp, "current_mana": mana, "max_mana": mana, "conditions": []})
    conn.execute("INSERT INTO characters (id, campaign_id, sheet_json) VALUES (?, ?, ?)", (char_id, solo_id, sheet))
    conn.commit()
    return sheet


# ─── Tests: is_mp_campaign ───────────────────────────────────────────────────

def test_g16_is_mp_campaign_returns_true_for_multiplayer():
    conn = _mk_db()
    conn.execute("INSERT INTO campaigns (id, mode) VALUES (1, 'multiplayer')")
    conn.commit()
    assert is_mp_campaign(conn, 1) is True


def test_g16_is_mp_campaign_returns_false_for_solo():
    conn = _mk_db()
    conn.execute("INSERT INTO campaigns (id, mode) VALUES (1, 'solo')")
    conn.commit()
    assert is_mp_campaign(conn, 1) is False


# ─── Tests: create_initial_state ────────────────────────────────────────────

def test_g16_create_initial_state_inserts_row():
    conn = _mk_db()
    _seed(conn)
    sheet = {"current_hp": 18, "max_hp": 20, "current_mana": 5, "max_mana": 8}
    create_initial_state(conn, campaign_id=2, character_id=1, sheet=sheet)
    conn.commit()
    row = conn.execute(
        "SELECT * FROM character_campaign_state WHERE character_id=1 AND campaign_id=2"
    ).fetchone()
    assert row is not None
    assert row["current_hp"] == 18
    assert row["max_hp"] == 20
    assert row["current_mana"] == 5
    assert row["max_mana"] == 8
    assert json.loads(row["conditions_json"]) == []


def test_g16_create_initial_state_is_idempotent():
    conn = _mk_db()
    _seed(conn)
    sheet = {"current_hp": 18, "max_hp": 20}
    create_initial_state(conn, campaign_id=2, character_id=1, sheet=sheet)
    create_initial_state(conn, campaign_id=2, character_id=1, sheet=sheet)
    conn.commit()
    count = conn.execute(
        "SELECT COUNT(*) FROM character_campaign_state WHERE character_id=1 AND campaign_id=2"
    ).fetchone()[0]
    assert count == 1


# ─── Tests: save_battle_state ────────────────────────────────────────────────

def test_g16_save_battle_state_writes_hp_mana_conditions():
    conn = _mk_db()
    _seed(conn)
    create_initial_state(conn, campaign_id=2, character_id=1, sheet={"current_hp": 20, "max_hp": 20})
    conditions = [{"key": "burned", "label": "Płonący"}]
    save_battle_state(conn, campaign_id=2, character_id=1, sheet={
        "current_hp": 12, "max_hp": 20, "current_mana": 3, "max_mana": 8, "conditions": conditions
    })
    conn.commit()
    row = conn.execute(
        "SELECT * FROM character_campaign_state WHERE character_id=1 AND campaign_id=2"
    ).fetchone()
    assert row["current_hp"] == 12
    assert row["current_mana"] == 3
    assert json.loads(row["conditions_json"]) == conditions


# ─── Tests: get_battle_state ─────────────────────────────────────────────────

def test_g16_get_battle_state_returns_none_when_no_row():
    conn = _mk_db()
    _seed(conn)
    assert get_battle_state(conn, campaign_id=2, character_id=1) is None


def test_g16_get_battle_state_returns_dict_with_values():
    conn = _mk_db()
    _seed(conn)
    create_initial_state(conn, campaign_id=2, character_id=1, sheet={"current_hp": 15, "max_hp": 20})
    conn.commit()
    state = get_battle_state(conn, campaign_id=2, character_id=1)
    assert state is not None
    assert state["current_hp"] == 15
    assert state["max_hp"] == 20


# ─── Tests: overlay_sheet_from_campaign_state ────────────────────────────────

def test_g16_overlay_applies_ccs_hp_to_sheet():
    conn = _mk_db()
    _seed(conn)
    create_initial_state(conn, campaign_id=2, character_id=1, sheet={"current_hp": 12, "max_hp": 20, "current_mana": 3, "max_mana": 8})
    conn.commit()
    sheet = {"current_hp": 20, "max_hp": 20, "current_mana": 8, "max_mana": 8}
    overlay_sheet_from_campaign_state(conn, campaign_id=2, character_id=1, sheet=sheet)
    assert sheet["current_hp"] == 12
    assert sheet["current_mana"] == 3


def test_g16_overlay_noop_for_solo_campaign():
    conn = _mk_db()
    _seed(conn)
    sheet = {"current_hp": 20, "max_hp": 20}
    overlay_sheet_from_campaign_state(conn, campaign_id=1, character_id=1, sheet=sheet)
    assert sheet["current_hp"] == 20  # unchanged


def test_g16_overlay_noop_when_no_ccs_row():
    conn = _mk_db()
    _seed(conn)
    sheet = {"current_hp": 20, "max_hp": 20}
    overlay_sheet_from_campaign_state(conn, campaign_id=2, character_id=1, sheet=sheet)
    assert sheet["current_hp"] == 20  # no CCS row → unchanged


# ─── Tests: isolation — MP damage doesn't touch sheet_json ───────────────────

def test_g16_save_char_sheet_mp_does_not_write_hp_to_sheet_json():
    """_save_char_sheet for MP campaign routes HP/mana to CCS, not sheet_json."""
    from app.services.combat_service import _save_char_sheet  # noqa: PLC0415

    conn = _mk_db()
    _seed(conn, hp=20, mana=8)
    create_initial_state(conn, campaign_id=2, character_id=1, sheet={"current_hp": 20, "max_hp": 20, "current_mana": 8, "max_mana": 8})
    conn.commit()

    # Simulate MP damage: HP drops to 12
    modified_sheet = {"current_hp": 12, "max_hp": 20, "current_mana": 5, "max_mana": 8, "conditions": [], "archetype": "warrior"}
    _save_char_sheet(conn, campaign_id=2, character_id=1, sheet=modified_sheet)
    conn.commit()

    # sheet_json must NOT have current_hp=12 (solo HP untouched)
    raw = conn.execute("SELECT sheet_json FROM characters WHERE id=1").fetchone()["sheet_json"]
    saved = json.loads(raw)
    assert saved.get("current_hp") != 12, "MP damage must NOT update sheet_json current_hp"

    # CCS must have current_hp=12
    state = get_battle_state(conn, campaign_id=2, character_id=1)
    assert state is not None
    assert state["current_hp"] == 12, "MP damage must update character_campaign_state current_hp"


def test_g16_save_char_sheet_solo_writes_full_sheet_json():
    """_save_char_sheet for solo campaign writes full sheet_json (backward compat)."""
    from app.services.combat_service import _save_char_sheet  # noqa: PLC0415

    conn = _mk_db()
    _seed(conn, hp=20)
    modified_sheet = {"current_hp": 15, "max_hp": 20, "archetype": "warrior"}
    _save_char_sheet(conn, campaign_id=1, character_id=1, sheet=modified_sheet)
    conn.commit()

    raw = conn.execute("SELECT sheet_json FROM characters WHERE id=1").fetchone()["sheet_json"]
    saved = json.loads(raw)
    assert saved["current_hp"] == 15, "Solo mode must write current_hp to sheet_json"


# ─── Tests: migration backfill ───────────────────────────────────────────────

def test_g16_backfill_copies_hp_from_sheet_json_to_ccs():
    """Backfill migration creates CCS row from existing character's sheet_json."""
    from app.migrations_admin import _backfill_character_campaign_state  # noqa: PLC0415

    conn = _mk_db()
    sheet = json.dumps({"current_hp": 14, "max_hp": 20, "current_mana": 4, "max_mana": 8})
    conn.execute("INSERT INTO campaigns (id, mode) VALUES (1, 'multiplayer')")
    conn.execute("INSERT INTO characters (id, campaign_id, sheet_json) VALUES (1, 1, ?)", (sheet,))
    conn.execute("INSERT INTO campaign_members (campaign_id, user_id, character_id, status) VALUES (1, 1, 1, 'accepted')")
    conn.commit()

    _backfill_character_campaign_state(conn)
    conn.commit()

    row = conn.execute(
        "SELECT * FROM character_campaign_state WHERE character_id=1 AND campaign_id=1"
    ).fetchone()
    assert row is not None
    assert row["current_hp"] == 14
    assert row["max_hp"] == 20
    assert row["current_mana"] == 4


def test_g16_backfill_skips_solo_campaigns():
    """Backfill must not create CCS rows for solo campaigns."""
    from app.migrations_admin import _backfill_character_campaign_state  # noqa: PLC0415

    conn = _mk_db()
    sheet = json.dumps({"current_hp": 20, "max_hp": 20})
    conn.execute("INSERT INTO campaigns (id, mode) VALUES (1, 'solo')")
    conn.execute("INSERT INTO characters (id, campaign_id, sheet_json) VALUES (1, 1, ?)", (sheet,))
    conn.commit()

    _backfill_character_campaign_state(conn)
    conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM character_campaign_state").fetchone()[0]
    assert count == 0, "Solo campaigns must not get CCS rows"
