"""TDD: Issue #1359 [WALKA-T2-FIX] — niedostępne obrony wyszarzone z powodem, nie ukryte.

Weryfikacja #1350 (BUG-2): backend zwracał TYLKO dostępne reakcje, więc niedostępne (np.
Tarcza Many bez many) znikały całkowicie — gracz nie wiedział, że ma wykupioną zdolność.

Fix:
1. `_reaction_options_detailed()` zwraca WSZYSTKIE opcje wg POSIADANYCH skilli, każdą z flagą
   `available` + `reason` (no_mana / no_shield / cap_reached / locked / None).
2. `_reaction_options()` (list[str] dostępnych) pozostaje = [o['key'] for o in detailed if available]
   — backward compat dla bramek okna reakcji.
3. snapshot niesie `defense_options_detailed`; okno reakcji niesie `reaction_options_detailed`.
"""
import importlib
import json
import sqlite3
from unittest.mock import patch

import pytest

combat_service = importlib.import_module("app.services.combat_service")


# ─── DB fixture (parytet z test_issue1350) ───────────────────────────────────

def _combat_db(tmp_path, *, skills: dict, current_mana: int = 10,
               current_turn: str = "player", attack_bonus: int = 10):
    db = tmp_path / "combat1359.db"
    player = {"id": "player", "type": "player", "name": "Aldric",
              "hp_current": 20, "hp_max": 20, "stats": {"INT": 14, "DEX": 12, "STR": 12},
              "defense": 10, "zone": "engaged"}
    enemy = {"id": "bandit", "type": "enemy", "enemy_key": "bandit", "name": "Bandit",
             "hp_current": 40, "hp_max": 40, "attack_bonus": attack_bonus,
             "damage_dice": "1d8", "zone": "engaged"}
    sheet = {"stats": player["stats"], "current_hp": 20, "max_hp": 20,
             "defense": {"base": 10}, "conditions": [], "skills": dict(skills),
             "current_mana": current_mana, "max_mana": 20}
    combatants = json.dumps([player, enemy], ensure_ascii=False).replace("'", "''")
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(f"""
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, status TEXT DEFAULT 'active', mode TEXT);
        INSERT INTO campaigns (id,title) VALUES (1,'T2FIX');
        CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
          name TEXT, system_id TEXT, sheet_json TEXT);
        INSERT INTO characters (id,campaign_id,user_id,name,system_id,sheet_json)
          VALUES (1,1,1,'Aldric','fantasy','{sj}');
        CREATE TABLE active_combat (id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER UNIQUE,
          character_id INTEGER, round INTEGER DEFAULT 1, turn_order TEXT, current_turn TEXT,
          combatants TEXT, status TEXT DEFAULT 'active', ended_reason TEXT, location_tag TEXT,
          loot_pool TEXT, created_at TEXT, updated_at TEXT);
        INSERT INTO active_combat (campaign_id,character_id,round,turn_order,current_turn,combatants,status)
          VALUES (1,1,1,'["bandit","player"]','{current_turn}','{combatants}','active');
        CREATE TABLE combat_turns (id INTEGER PRIMARY KEY AUTOINCREMENT, combat_id INTEGER, campaign_id INTEGER,
          turn_number REAL, actor TEXT, event_type TEXT, roll_value INTEGER, damage INTEGER, hp_after INTEGER,
          target_id TEXT, target_name TEXT, hit INTEGER, narrative TEXT,
          created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
        """)
        conn.commit()
    finally:
        conn.close()
    return db


def _by_key(detailed):
    return {o["key"]: o for o in detailed}


# ─── Test główny: niedostępna Tarcza Many wyszarzona z powodem, nie ukryta ────

def test_detailed_mana_shield_no_mana_is_greyed_not_hidden(tmp_path):
    """Mag ze skillem mana_shield bez many → wpis mana_shield ISTNIEJE, available=False, reason='no_mana'."""
    db = _combat_db(tmp_path, skills={"mana_shield": 1}, current_mana=0)
    conn = sqlite3.connect(str(db))
    try:
        p = {}
        sheet = {"skills": {"mana_shield": 1}, "current_mana": 0}
        detailed = combat_service._reaction_options_detailed(conn, 1, p, sheet, 1, enemy_count=1)
    finally:
        conn.close()
    by = _by_key(detailed)
    assert "mana_shield" in by, "Tarcza Many musi być OBECNA (wyszarzona), nie ukryta"
    assert by["mana_shield"]["available"] is False
    assert by["mana_shield"]["reason"] == "no_mana"


def test_detailed_arcane_ward_no_mana_greyed(tmp_path):
    """Mag ze skillem arcane_ward bez many → wpis obecny, available=False, reason='no_mana'."""
    db = _combat_db(tmp_path, skills={"arcane_ward": 1}, current_mana=0)
    conn = sqlite3.connect(str(db))
    try:
        detailed = combat_service._reaction_options_detailed(
            conn, 1, {}, {"skills": {"arcane_ward": 1}, "current_mana": 0}, 1, enemy_count=1)
    finally:
        conn.close()
    by = _by_key(detailed)
    assert "arcane_ward" in by
    assert by["arcane_ward"]["available"] is False
    assert by["arcane_ward"]["reason"] == "no_mana"


def test_detailed_shield_block_without_shield_greyed(tmp_path):
    """Skill shield_block ale bez założonej tarczy → wpis obecny, available=False, reason='no_shield'."""
    db = _combat_db(tmp_path, skills={"shield_block": 1})
    conn = sqlite3.connect(str(db))
    try:
        with patch.object(combat_service, "_player_has_shield_equipped", return_value=(False, None)):
            detailed = combat_service._reaction_options_detailed(
                conn, 1, {}, {"skills": {"shield_block": 1}, "current_mana": 0}, 1, enemy_count=1)
    finally:
        conn.close()
    by = _by_key(detailed)
    assert "shield_block" in by
    assert by["shield_block"]["available"] is False
    assert by["shield_block"]["reason"] == "no_shield"


def test_detailed_available_when_mana_present(tmp_path):
    """Mag z maną → mana_shield available=True, reason None."""
    db = _combat_db(tmp_path, skills={"mana_shield": 1}, current_mana=10)
    conn = sqlite3.connect(str(db))
    try:
        detailed = combat_service._reaction_options_detailed(
            conn, 1, {}, {"skills": {"mana_shield": 1}, "current_mana": 10}, 1, enemy_count=1)
    finally:
        conn.close()
    by = _by_key(detailed)
    assert by["mana_shield"]["available"] is True
    assert by["mana_shield"]["reason"] is None


def test_detailed_omits_unowned_skills(tmp_path):
    """Opcja bez posiadanego skilla NIE pojawia się (WSZYSTKIE = wg POSIADANYCH skilli)."""
    db = _combat_db(tmp_path, skills={"dodge": 1})
    conn = sqlite3.connect(str(db))
    try:
        detailed = combat_service._reaction_options_detailed(
            conn, 1, {}, {"skills": {"dodge": 1}, "current_mana": 0}, 1, enemy_count=1)
    finally:
        conn.close()
    by = _by_key(detailed)
    assert "dodge" in by
    assert "mana_shield" not in by
    assert "arcane_ward" not in by
    assert "shield_block" not in by


# ─── Backward compat: _reaction_options = dostępne z detailed ─────────────────

def test_reaction_options_equals_available_subset(tmp_path):
    """`_reaction_options` (list[str]) = klucze available z detailed (bez zmiany zachowania)."""
    db = _combat_db(tmp_path, skills={"mana_shield": 1, "arcane_ward": 1}, current_mana=0)
    conn = sqlite3.connect(str(db))
    try:
        p, sheet = {}, {"skills": {"mana_shield": 1, "arcane_ward": 1}, "current_mana": 0}
        flat = combat_service._reaction_options(conn, 1, p, sheet, 1, enemy_count=1)
        detailed = combat_service._reaction_options_detailed(conn, 1, p, sheet, 1, enemy_count=1)
    finally:
        conn.close()
    assert flat == [o["key"] for o in detailed if o["available"]]
    # bez many oba magiczne niedostępne → flat pusta, ale detailed je NIESIE
    assert flat == []
    assert {o["key"] for o in detailed} == {"mana_shield", "arcane_ward"}


# ─── snapshot niesie defense_options_detailed ────────────────────────────────

def test_snapshot_carries_defense_options_detailed(tmp_path):
    """snapshot walki niesie `defense_options_detailed` (lista dictów key/available/reason)."""
    db = _combat_db(tmp_path, skills={"mana_shield": 1}, current_mana=0)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        snap = combat_service.load_combat_snapshot(1)
    detailed = snap.get("defense_options_detailed")
    assert isinstance(detailed, list)
    by = _by_key(detailed)
    assert "mana_shield" in by and by["mana_shield"]["available"] is False
    # stary klucz nadal obecny (available-only)
    assert isinstance(snap.get("defense_options"), list)
    assert "mana_shield" not in snap["defense_options"]


# ─── okno reakcji niesie reaction_options_detailed ───────────────────────────

def test_reaction_window_carries_detailed(tmp_path, monkeypatch):
    """resolve_attack (wróg) otwiera okno → niesie `reaction_options_detailed` z wyszarzonymi."""
    db = _combat_db(tmp_path, skills={"dodge": 1, "mana_shield": 1}, current_mana=0,
                    current_turn="bandit", attack_bonus=5)
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 12)
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 5)
    monkeypatch.setattr(combat_service, "roll_dice_detailed",
                        lambda *a, **k: {"die": "1d8", "rolls": [5], "sides": 8, "n": 1})
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        win = combat_service.resolve_attack(1, 0, attacker="enemy")
    assert win.get("reaction_window") is True
    detailed = win.get("reaction_options_detailed")
    assert isinstance(detailed, list)
    by = _by_key(detailed)
    assert by["dodge"]["available"] is True          # skill dodge, brak capu
    assert "mana_shield" in by                        # obecna mimo braku many
    assert by["mana_shield"]["available"] is False
    assert by["mana_shield"]["reason"] == "no_mana"
