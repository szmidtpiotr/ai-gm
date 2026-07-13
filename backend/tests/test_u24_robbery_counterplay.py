"""TDD: Issue #574 — U24 Napad: counterplay (ostrzeżenie + rzut obronny + próg biedy + limit 24h).

Bazuje na F8/#468 (robbery_service). U24 dokłada warstwę "kara z możliwością reakcji":
- DC obrony wg poziomu z zamka {8,12,16,20,24}
- rzut obronny d20 + stat_mod (stat wg wariantu napadu)
- próg biedy: napad nie odpala się gdy złoto < 50 gp
- limit: max 1 napad / 24h realne / kampania (znacznik w session_flags)

Mechanika decyduje, LLM narruje (game_mechanics.md CZĘŚĆ 10).
"""
import sys
sys.path.insert(0, "/app")
from _fixtures_schema import table_sql

import json
import sqlite3
import pytest

from app.services.robbery_service import (
    robbery_defense_dc,
    roll_robbery_defense,
    can_trigger_robbery,
    record_robbery_trigger,
    apply_robbery,
    is_robbery_encounter,
)


# ─── Fixture ─────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER,
            is_active INTEGER DEFAULT 1,
            gold_gp INTEGER NOT NULL DEFAULT 0,
            sheet_json TEXT
        );
        CREATE TABLE character_gold_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER,
            delta INTEGER,
            source TEXT,
            meta_json TEXT,
            game_clock_day INTEGER DEFAULT 1,
            wall_clock_at TEXT NOT NULL DEFAULT (datetime('now')),
            reverted_at TEXT
        );
        """ + table_sql("game_config_meta") + """
        """
    )
    # Hero: campaign 100, 200 gold, DEX 16 (+3), WIS 8 (-1), level 1
    sheet = json.dumps({"level": 1, "stats": {"DEX": 16, "WIS": 8}})
    conn.execute(
        "INSERT INTO characters (id, campaign_id, is_active, gold_gp, sheet_json) VALUES (1, 100, 1, 200, ?)",
        (sheet,),
    )
    # Poor hero: campaign 200, 30 gold
    sheet_poor = json.dumps({"level": 1, "stats": {"DEX": 10, "WIS": 10}})
    conn.execute(
        "INSERT INTO characters (id, campaign_id, is_active, gold_gp, sheet_json) VALUES (2, 200, 1, 30, ?)",
        (sheet_poor,),
    )
    conn.commit()
    yield conn
    conn.close()


def _gold(db, cid=1):
    return db.execute("SELECT gold_gp FROM characters WHERE id=?", (cid,)).fetchone()["gold_gp"]


# ─── DC wg poziomu (zamek {8,12,16,20,24}) ───────────────────────────────────

def test_defense_dc_in_lock():
    """Każde DC obrony należy do zamka {8,12,16,20,24}."""
    lock = {8, 12, 16, 20, 24}
    for lvl in range(1, 16):
        assert robbery_defense_dc(lvl) in lock


def test_defense_dc_scales_with_level():
    """DC rośnie (nie maleje) z poziomem bohatera."""
    assert robbery_defense_dc(1) <= robbery_defense_dc(5) <= robbery_defense_dc(10)


# ─── Rzut obronny ─────────────────────────────────────────────────────────────

def test_defense_roll_uses_stat_modifier(db):
    """Rzut obronny dolicza modyfikator wskazanej statystyki (DEX +3)."""
    res = roll_robbery_defense(db, 1, "DEX", dc=12)
    assert res["stat"] == "DEX"
    # total = d20 (1..20) + 3
    assert res["total"] == res["roll"] + 3
    assert res["dc"] == 12
    assert isinstance(res["success"], bool)
    assert res["success"] == (res["total"] >= 12)


def test_defense_roll_success_against_low_dc(db):
    """Przy DC=1 i dodatnim modyfikatorze rzut zawsze się udaje."""
    res = roll_robbery_defense(db, 1, "DEX", dc=1)
    assert res["success"] is True


def test_defense_roll_failure_against_impossible_dc(db):
    """Przy DC=99 rzut zawsze przegrywa."""
    res = roll_robbery_defense(db, 1, "DEX", dc=99)
    assert res["success"] is False


# ─── Próg biedy + limit częstości ─────────────────────────────────────────────

def test_robbery_blocked_below_poverty_threshold(db):
    """Napad nie odpala się gdy złoto < 50 gp."""
    res = can_trigger_robbery(db, campaign_id=200, char_id=2, session_flags={})
    assert res["allowed"] is False
    assert res["reason"] == "below_poverty_threshold"


def test_robbery_allowed_above_threshold(db):
    """Napad dozwolony gdy złoto >= 50 gp i brak ostatniego napadu."""
    res = can_trigger_robbery(db, campaign_id=100, char_id=1, session_flags={})
    assert res["allowed"] is True


def test_robbery_blocked_within_24h(db):
    """Drugi napad w ciągu 24h realnych jest zablokowany."""
    sf = {}
    record_robbery_trigger(sf)  # ustawia last_robbery_at = teraz
    res = can_trigger_robbery(db, campaign_id=100, char_id=1, session_flags=sf)
    assert res["allowed"] is False
    assert res["reason"] == "rate_limited_24h"


def test_robbery_allowed_after_24h(db):
    """Po >24h realnych od ostatniego napadu znów dozwolony."""
    sf = {"last_robbery_at": "2000-01-01T00:00:00"}  # dawno temu
    res = can_trigger_robbery(db, campaign_id=100, char_id=1, session_flags=sf)
    assert res["allowed"] is True


def test_record_robbery_sets_timestamp():
    """record_robbery_trigger zapisuje znacznik czasu do session_flags."""
    sf = {}
    record_robbery_trigger(sf)
    assert "last_robbery_at" in sf
    assert isinstance(sf["last_robbery_at"], str) and len(sf["last_robbery_at"]) >= 10


# ─── Integracja: sukces obrony = brak straty; porażka = strata 20% ─────────────

def test_successful_defense_keeps_gold(db):
    """Gdy obrona się uda, złoto pozostaje nietknięte (resolve nie woła apply_robbery)."""
    res = roll_robbery_defense(db, 1, "DEX", dc=1)  # gwarantowany sukces
    assert res["success"] is True
    # apply_robbery NIE jest wołane przy sukcesie — symulujemy decyzję wywołującego
    if not res["success"]:
        apply_robbery(db, 1)
    assert _gold(db, 1) == 200


def test_failed_defense_applies_robbery(db):
    """Gdy obrona przegra, apply_robbery zabiera 20%."""
    res = roll_robbery_defense(db, 1, "DEX", dc=99)  # gwarantowana porażka
    assert res["success"] is False
    if not res["success"]:
        apply_robbery(db, 1)
    assert _gold(db, 1) == 160  # 200 - 20%


# ─── Backward compatibility (F8/#468 niezmienione) ────────────────────────────

def test_apply_robbery_still_works(db):
    """Stary apply_robbery działa bez zmian (kompatybilność wsteczna)."""
    res = apply_robbery(db, 1)
    assert res["ok"] is True
    assert res["gold_stolen"] == 40
    assert _gold(db, 1) == 160


def test_is_robbery_encounter_still_works():
    """is_robbery_encounter rozpoznaje typ napadu (bez zmian)."""
    assert is_robbery_encounter({"encounter_type": "robbery"}) is True
    assert is_robbery_encounter({"enemies": [{"enemy_key": "wolf"}]}) is False
