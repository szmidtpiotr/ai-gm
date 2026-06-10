"""TDD: Issue #465 — F5 Wskrzeszenie jako gold sink.

Acceptance criteria:
- Config: resurrection_enabled (bool) + resurrection_gold_percent (int percent)
- cost_preview() shows gold cost when enabled with gold_percent mode
- apply_resurrection() deducts correct gold amount
- Disabled by default — no cost when disabled
"""
import sys
sys.path.insert(0, "/app")

import json
import sqlite3
import pytest
from app.services.resurrection_service import (
    get_global_resurrection_config,
    set_global_resurrection_config,
    cost_preview,
    apply_resurrection,
)


# ─── Fixture ─────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE game_config_meta (
            key TEXT PRIMARY KEY, value TEXT, updated_at TEXT
        );
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            resurrection_uses_remaining INTEGER
        );
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER,
            user_id INTEGER,
            sheet_json TEXT DEFAULT '{}',
            status TEXT DEFAULT 'dead',
            gold_gp INTEGER DEFAULT 0
        );
        CREATE TABLE character_gold_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER,
            delta INTEGER,
            source TEXT,
            meta_json TEXT,
            game_clock_day INTEGER,
            reverted_at TEXT
        );
        CREATE TABLE character_dungeon_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER
        );
        CREATE TABLE character_spells (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER,
            spell_key TEXT,
            rank INTEGER,
            learned_at_level INTEGER
        );
        INSERT INTO users VALUES (1, NULL);
        INSERT INTO characters (id, user_id, campaign_id, status, gold_gp, sheet_json)
            VALUES (1, 1, 99, 'dead', 200,
                '{"max_hp":20,"current_hp":0,"archetype":"warrior","level":3,"xp":200,
                  "stats":{"CON":12,"INT":10}}');
    """)
    conn.commit()

    import app.services.clock_service as _clock
    _orig = _clock.get_clock_state
    _clock.get_clock_state = lambda cid, conn=None: {"day": 5, "hour": 12, "ingame_hours": 120, "hour_str": "12:00", "period": "Południe", "display": "Dzień 5"}
    yield conn
    _clock.get_clock_state = _orig
    conn.close()


# ─── F5 AC1 — Config: resurrection_enabled (bool) ────────────────────────────

def test_resurrection_disabled_by_default(db):
    """Feature must be OFF by default — no surprise gold loss for new installs."""
    cfg = get_global_resurrection_config(db)
    assert cfg["enabled"] is False


def test_resurrection_can_be_enabled(db):
    """Admin can enable resurrection globally."""
    set_global_resurrection_config(db, enabled=True)
    cfg = get_global_resurrection_config(db)
    assert cfg["enabled"] is True


def test_resurrection_can_be_disabled_again(db):
    """Admin can turn off resurrection after enabling it."""
    set_global_resurrection_config(db, enabled=True)
    set_global_resurrection_config(db, enabled=False)
    cfg = get_global_resurrection_config(db)
    assert cfg["enabled"] is False


# ─── F5 AC1 — Config: resurrection_gold_percent ──────────────────────────────

def test_set_gold_percent_mode(db):
    """Admin sets mode=gold_percent with a percent value."""
    set_global_resurrection_config(db, enabled=True, mode="gold_percent", value=25)
    cfg = get_global_resurrection_config(db)
    assert cfg["mode"] == "gold_percent"
    assert cfg["value"] == 25


def test_gold_percent_value_persists(db):
    """Configured percent survives a read-back cycle."""
    set_global_resurrection_config(db, enabled=True, mode="gold_percent", value=33)
    cfg = get_global_resurrection_config(db)
    assert cfg["value"] == 33


# ─── F5 AC2 — Death screen: cost_preview shows cost when enabled ──────────────

def test_preview_shows_gold_cost_when_enabled(db):
    """When enabled with gold_percent, preview returns cost with gold_lost amount."""
    set_global_resurrection_config(db, enabled=True, mode="gold_percent", value=25)
    p = cost_preview(1, 1, db)
    assert p["enabled"] is True
    assert "cost" in p
    assert p["cost"]["mode"] == "gold_percent"
    assert p["cost"]["gold_lost"] == 50   # 25% of 200 gp


def test_preview_shows_current_gold_amount(db):
    """Preview cost dict exposes current_gold so frontend can show '25% of 200 GP'."""
    set_global_resurrection_config(db, enabled=True, mode="gold_percent", value=25)
    p = cost_preview(1, 1, db)
    assert p["cost"]["current_gold"] == 200


def test_preview_disabled_returns_no_cost(db):
    """When disabled, preview returns enabled=False — no cost shown on death screen."""
    p = cost_preview(1, 1, db)
    assert p["enabled"] is False
    assert "cost" not in p or p.get("reason") == "resurrection_disabled"


# ─── F5 AC3 — apply_resurrection deducts correct gold ────────────────────────

def test_apply_gold_percent_deducts_correct_amount(db):
    """25% of 200 GP = 50 GP deducted on resurrection."""
    set_global_resurrection_config(db, enabled=True, mode="gold_percent", value=25)
    result = apply_resurrection(1, 1, db, force=False)
    assert result["cost_applied"]["gold_lost"] == 50
    row = db.execute("SELECT gold_gp FROM characters WHERE id = 1").fetchone()
    assert row["gold_gp"] == 150  # 200 - 50


def test_apply_gold_percent_journals_the_loss(db):
    """Gold deduction must appear in character_gold_log with resurrection source."""
    set_global_resurrection_config(db, enabled=True, mode="gold_percent", value=10)
    apply_resurrection(1, 1, db, force=False)
    log = db.execute(
        "SELECT delta, source FROM character_gold_log WHERE character_id = 1 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert log["delta"] == -20   # 10% of 200
    assert "resurrection" in log["source"]


def test_apply_revives_hero_to_half_max_hp(db):
    """After gold deduction, hero status='active' with HP = max_hp // 2 = 10."""
    set_global_resurrection_config(db, enabled=True, mode="gold_percent", value=10)
    result = apply_resurrection(1, 1, db, force=False)
    assert result["revived_hp"] == 10   # max_hp 20 // 2
    row = db.execute("SELECT status FROM characters WHERE id = 1").fetchone()
    assert row["status"] == "active"


def test_apply_no_gold_deduction_when_broke(db):
    """Hero with 0 GP loses 0 GP — resurrection still works, no negative gold."""
    db.execute("UPDATE characters SET gold_gp = 0 WHERE id = 1")
    db.commit()
    set_global_resurrection_config(db, enabled=True, mode="gold_percent", value=25)
    result = apply_resurrection(1, 1, db, force=False)
    assert result["cost_applied"]["gold_lost"] == 0
    row = db.execute("SELECT gold_gp FROM characters WHERE id = 1").fetchone()
    assert row["gold_gp"] == 0


# ─── Backward compat ──────────────────────────────────────────────────────────

def test_force_resurrect_always_free(db):
    """Admin force-resurrect ignores gold_percent config — admin bypass stays free."""
    set_global_resurrection_config(db, enabled=True, mode="gold_percent", value=100)
    result = apply_resurrection(1, 1, db, force=True)
    assert result["cost_applied"].get("free") is True
    row = db.execute("SELECT gold_gp FROM characters WHERE id = 1").fetchone()
    assert row["gold_gp"] == 200  # gold untouched
