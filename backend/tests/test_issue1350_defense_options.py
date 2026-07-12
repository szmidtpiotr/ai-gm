"""TDD: Issue #1350 [WALKA-T2] — piguła Obrona wg skilli postaci.

Composer maga (pre-deklaracja „Obrona") ma widzieć swoje obrony zamiast hardcoded unik/blok:
1. snapshot walki niesie `defense_options` (wynik `_reaction_options()` dla aktualnego stanu
   gracza) — frontend nie zgaduje skilli,
2. `declare_player_reaction` akceptuje `arcane_ward` (#1324) i `mana_shield` (#1325) obok
   `dodge`/`shield_block`; walidacja many liczona w momencie WYZWOLENIA (resolver), nie deklaracji.
"""
import importlib
import json
import sqlite3
from unittest.mock import patch

import pytest

combat_service = importlib.import_module("app.services.combat_service")


# ─── DB fixture: walka z bohaterem o zadanych skillach ───────────────────────

def _combat_db(tmp_path, *, skills: dict, current_mana: int = 10,
               current_turn: str = "player", declared: str | None = None,
               attack_bonus: int = 10):
    db = tmp_path / "combat1350.db"
    player = {"id": "player", "type": "player", "name": "Aldric",
              "hp_current": 20, "hp_max": 20, "stats": {"INT": 14, "DEX": 12, "STR": 12},
              "defense": 10, "zone": "engaged"}
    if declared:
        player["reaction_declared"] = declared
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
        INSERT INTO campaigns (id,title) VALUES (1,'T2');
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


# ─── Test główny: defense_options w snapshotcie ──────────────────────────────

def test_snapshot_defense_options_mage_sees_arcane_and_mana(tmp_path):
    """Mag ze skillami arcane_ward + mana_shield i maną → oba w defense_options."""
    db = _combat_db(tmp_path, skills={"arcane_ward": 1, "mana_shield": 1}, current_mana=10)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        snap = combat_service.load_combat_snapshot(1)
    assert snap is not None
    opts = snap.get("defense_options")
    assert isinstance(opts, list)
    assert "arcane_ward" in opts
    assert "mana_shield" in opts


def test_snapshot_defense_options_warrior_dodge_only(tmp_path):
    """Wojownik ze skillem dodge → 'dodge' w defense_options, bez opcji magicznych."""
    db = _combat_db(tmp_path, skills={"dodge": 1}, current_mana=0)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        snap = combat_service.load_combat_snapshot(1)
    opts = snap.get("defense_options")
    assert "dodge" in opts
    assert "arcane_ward" not in opts
    assert "mana_shield" not in opts


def test_snapshot_defense_options_no_mana_excludes_arcane(tmp_path):
    """Mag bez many → arcane_ward NIE w opcjach (gate mana ≥ koszt)."""
    db = _combat_db(tmp_path, skills={"arcane_ward": 1, "mana_shield": 1}, current_mana=0)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        snap = combat_service.load_combat_snapshot(1)
    opts = snap.get("defense_options")
    assert "arcane_ward" not in opts
    assert "mana_shield" not in opts


# ─── declare_player_reaction: nowe typy magiczne ─────────────────────────────

def test_declare_arcane_ward_accepted(tmp_path):
    """Mag ze skillem arcane_ward może zadeklarować barierę (nie ValueError)."""
    db = _combat_db(tmp_path, skills={"arcane_ward": 1}, current_mana=10, current_turn="player")
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        r = combat_service.declare_player_reaction(1, "arcane_ward")
    assert r["reaction_declared"] == "arcane_ward"


def test_declare_mana_shield_accepted(tmp_path):
    """Mag ze skillem mana_shield może zadeklarować Tarczę Many."""
    db = _combat_db(tmp_path, skills={"mana_shield": 1}, current_mana=10, current_turn="player")
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        r = combat_service.declare_player_reaction(1, "mana_shield")
    assert r["reaction_declared"] == "mana_shield"


def test_declare_arcane_ward_requires_skill(tmp_path):
    """Bez skilla arcane_ward deklaracja odrzucona (ValueError → 400)."""
    db = _combat_db(tmp_path, skills={"dodge": 1}, current_mana=10, current_turn="player")
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        with pytest.raises(ValueError):
            combat_service.declare_player_reaction(1, "arcane_ward")


def test_declare_arcane_ward_no_mana_still_accepted(tmp_path):
    """Walidacja many liczona przy WYZWOLENIU, nie deklaracji — 0 many nie blokuje deklaracji."""
    db = _combat_db(tmp_path, skills={"arcane_ward": 1}, current_mana=0, current_turn="player")
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        r = combat_service.declare_player_reaction(1, "arcane_ward")
    assert r["reaction_declared"] == "arcane_ward"


# ─── Acceptance: declare arcane_ward → następne trafienie rozwiązane barierą ──

def test_declared_arcane_ward_resolves_next_hit_as_ward(tmp_path, monkeypatch):
    """Po deklaracji Bariery kolejne trafienie wroga rozliczone testem INT (mana −1)."""
    db = _combat_db(tmp_path, skills={"arcane_ward": 1}, current_mana=10,
                    current_turn="player", attack_bonus=0)  # atak 18 ≤ bariera 21 → warded
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 18)  # trafienie + zdany test INT
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 7)
    monkeypatch.setattr(combat_service, "roll_dice_detailed",
                        lambda *a, **k: {"die": "1d8", "rolls": [7], "sides": 8, "n": 1})
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        combat_service.declare_player_reaction(1, "arcane_ward")
        # przełącz na turę wroga i odpal atak → okno reakcji z opcją arcane_ward
        conn = sqlite3.connect(str(db))
        conn.execute("UPDATE active_combat SET current_turn='bandit' WHERE campaign_id=1")
        conn.commit(); conn.close()
        win = combat_service.resolve_attack(1, 0, attacker="enemy")
        assert win.get("reaction_window") is True
        assert "arcane_ward" in (win.get("reaction_options") or [])
        out = combat_service.resolve_reaction(1, "arcane_ward")
    assert out.get("reaction", {}).get("warded") is True
    assert out["damage"] == 0


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_declare_dodge_still_works(tmp_path):
    """Stary typ dodge nadal działa bez zmian (toggle on)."""
    db = _combat_db(tmp_path, skills={"dodge": 1}, current_turn="player")
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        r = combat_service.declare_player_reaction(1, "dodge")
    assert r["reaction_declared"] == "dodge"


def test_declare_unknown_type_rejected(tmp_path):
    """Nieznany typ reakcji nadal odrzucony (ValueError)."""
    db = _combat_db(tmp_path, skills={"dodge": 1}, current_turn="player")
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        with pytest.raises(ValueError):
            combat_service.declare_player_reaction(1, "teleport")
