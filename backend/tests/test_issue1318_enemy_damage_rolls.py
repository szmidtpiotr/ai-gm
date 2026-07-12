"""#1318: enemy attack response must carry damage_die + damage_rolls so the
frontend can play the second-stage NdX damage dice animation (parity with the
player attack path, #661). Fixture mirrors test_issue610 (no dodge skill, no
shield → no reaction window, damage applied immediately)."""
import json
import sqlite3
from unittest.mock import patch

from app.services import combat_service


def _combat_db(tmp_path):
    db = tmp_path / "enemy_dmg.db"
    player = {
        "id": "player", "type": "player", "name": "Aldric",
        "hp_current": 20, "hp_max": 20, "defense": 10, "zone": "engaged",
        "stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
        "conditions": [],
    }
    enemy = {
        "id": "bandit", "type": "enemy", "enemy_key": "bandit", "name": "Bandit",
        "hp_current": 40, "hp_max": 40, "attack_bonus": 10, "damage_dice": "2d6",
        "zone": "engaged",
    }
    sheet = {"stats": player["stats"], "current_hp": 20, "max_hp": 20,
             "defense": {"base": 10}, "conditions": [], "skills": {}}
    combatants = json.dumps([player, enemy], ensure_ascii=False).replace("'", "''")
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(f"""
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, status TEXT DEFAULT 'active', mode TEXT);
        INSERT INTO campaigns (id,title) VALUES (1,'#1318');
        CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
          name TEXT, system_id TEXT, sheet_json TEXT);
        INSERT INTO characters (id,campaign_id,user_id,name,system_id,sheet_json)
          VALUES (1,1,1,'Aldric','fantasy','{sj}');
        CREATE TABLE active_combat (id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER UNIQUE,
          character_id INTEGER, round INTEGER DEFAULT 1, turn_order TEXT, current_turn TEXT,
          combatants TEXT, status TEXT DEFAULT 'active', ended_reason TEXT, location_tag TEXT,
          loot_pool TEXT, created_at TEXT, updated_at TEXT);
        INSERT INTO active_combat (campaign_id,character_id,round,turn_order,current_turn,combatants,status)
          VALUES (1,1,1,'["bandit","player"]','bandit','{combatants}','active');
        CREATE TABLE combat_turns (id INTEGER PRIMARY KEY AUTOINCREMENT, combat_id INTEGER, campaign_id INTEGER,
          turn_number REAL, actor TEXT, event_type TEXT, roll_value INTEGER, damage INTEGER, hp_after INTEGER,
          target_id TEXT, target_name TEXT, hit INTEGER, narrative TEXT,
          created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
        """)
        conn.commit()
    finally:
        conn.close()
    return db


def test_enemy_hit_exposes_damage_rolls(tmp_path, monkeypatch):
    """Trafienie wroga niesie damage_die i damage_rolls zgodne z obrażeniami bazowymi.
    T5-5e (#1351): single-player bez skilla/tarczy otwiera okno take-only — damage_die/
    damage_rolls są już w odpowiedzi resolve_attack (liczone przed oknem), a wynikowe
    obrażenia po resolve_reaction("take")."""
    db = _combat_db(tmp_path)
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 18)  # atak 28, hit (raw != 1)
    monkeypatch.setattr(combat_service, "roll_dice_detailed",
                        lambda *a, **k: {"die": "2d6", "rolls": [4, 3], "sides": 6, "n": 2})
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, 0, attacker="enemy")
        assert out["hit"] is True
        assert out.get("reaction_window") is True
        assert out["damage_die"] == "2d6"
        assert out["damage_rolls"] == [4, 3]
        res = combat_service.resolve_reaction(1, "take")
    # baza 7 (4+3) + margines #826 (atak 28 − obrona 10 → +3), pancerz 0 → 10
    assert res["damage"] == 10


def test_enemy_miss_has_no_damage_rolls(tmp_path, monkeypatch):
    """Pudło wroga: brak damage_rolls → frontend nie odpala drugiego etapu animacji.
    T5-5e (#1351): w single-player wróg pudłuje WYŁĄCZNIE przy Nat 1 (raw=1) — pasywny
    unik zniknął, silnik nie rozstrzyga uniku za gracza."""
    db = _combat_db(tmp_path)
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 1)   # Nat 1 wroga = auto-pudło
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, 0, attacker="enemy")
    assert out["hit"] is False
    assert out.get("reaction_window") is not True
    assert "damage_rolls" not in out
