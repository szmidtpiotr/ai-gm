"""TDD: Issue #612 — S17: Wrestling (gracz nakłada kondycje wrogom testem przeciwnym).

Zapasy = akcja bojowa. Pierwszy skill, którego SUKCES MECHANICZNIE nakłada kondycję na
wroga (dotąd kondycje nakładały tylko bronie/czary). Gate: tura gracza + ZWARCIE
(gracz i cel w strefie engaged). Silnik rzuca obie strony testu przeciwnego STR vs STR
(d20 + STR_mod [+ rank + proficiency gracza]); stopień liczy S1 (_derive_outcome):
  • sukces (margines 0…+4)            → CEL: slowed (schwytany/przewrócony)
  • sukces krytyczny (margines ≥ +5)  → CEL: stunned 1 rundę (unieruchomiony)
  • porażka (margines −1…−4)          → brak efektu
  • krytyczna porażka (margines ≤ −5) → GRACZ: slowed (sam przewrócony)

Mapowanie wynik→kondycja jest DANYMI (skill_counters: on_success_condition /
on_crit_condition / on_critfail_self_condition) — Zasada 1 FAZY S: ZERO
``if skill_key == "wrestling"`` w silniku. Reużywa apply_condition_to_combatant (cel)
i apply_condition_to_player (samo-przewrócenie). Konsumuje turę.

RZUTY ATAKU W WALCE (nat 20 / nat 1, podwójne obrażenia) NIETKNIĘTE — wrestling to test
umiejętności; margines dotyczy wyłącznie jego.
"""
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import combat_service


# ─── Generyczny prymityw: wynik → kondycja (Zasada 1, data-driven) ────────────

def test_apply_outcome_success_to_target(monkeypatch):
    """SUKCES → on_success_condition nakładana na CEL (apply_condition_to_combatant)."""
    calls = []
    monkeypatch.setattr(combat_service, "apply_condition_to_combatant",
                        lambda cid, ref, key: calls.append(("target", ref, key)) or {"ok": True})
    monkeypatch.setattr(combat_service, "apply_condition_to_player",
                        lambda cid, key: calls.append(("self", key)) or {"ok": True})
    mapping = {"on_success_condition": "slowed", "on_crit_condition": "stunned",
               "on_critfail_self_condition": "slowed"}
    out = combat_service._apply_skill_outcome_conditions(1, mapping, "SUCCESS", "bandit")
    assert calls == [("target", "bandit", "slowed")]
    assert out and out[0]["condition"] == "slowed" and out[0]["who"] == "target"


def test_apply_outcome_crit_uses_stronger_condition(monkeypatch):
    """SUKCES KRYTYCZNY → on_crit_condition (mocniejsza, np. stunned) na CEL."""
    calls = []
    monkeypatch.setattr(combat_service, "apply_condition_to_combatant",
                        lambda cid, ref, key: calls.append((ref, key)) or {"ok": True})
    mapping = {"on_success_condition": "slowed", "on_crit_condition": "stunned",
               "on_critfail_self_condition": "slowed"}
    combat_service._apply_skill_outcome_conditions(1, mapping, "CRITICAL_SUCCESS", "bandit")
    assert calls == [("bandit", "stunned")]


def test_apply_outcome_critfail_to_self(monkeypatch):
    """KRYTYCZNA PORAŻKA → on_critfail_self_condition na GRACZU (apply_condition_to_player)."""
    calls = []
    monkeypatch.setattr(combat_service, "apply_condition_to_player",
                        lambda cid, key: calls.append(("self", key)) or {"ok": True})
    monkeypatch.setattr(combat_service, "apply_condition_to_combatant",
                        lambda *a, **k: pytest.fail("nie wolno nakładać na cel przy crit-fail"))
    mapping = {"on_success_condition": "slowed", "on_crit_condition": "stunned",
               "on_critfail_self_condition": "slowed"}
    out = combat_service._apply_skill_outcome_conditions(1, mapping, "CRITICAL_FAILURE", "bandit")
    assert calls == [("self", "slowed")]
    assert out[0]["who"] == "self"


def test_apply_outcome_failure_noop(monkeypatch):
    """PORAŻKA → nic się nie nakłada."""
    monkeypatch.setattr(combat_service, "apply_condition_to_combatant",
                        lambda *a, **k: pytest.fail("brak kondycji przy zwykłej porażce"))
    monkeypatch.setattr(combat_service, "apply_condition_to_player",
                        lambda *a, **k: pytest.fail("brak kondycji przy zwykłej porażce"))
    mapping = {"on_success_condition": "slowed", "on_crit_condition": "stunned",
               "on_critfail_self_condition": "slowed"}
    assert combat_service._apply_skill_outcome_conditions(1, mapping, "FAILURE", "bandit") == []


# ─── Integracja z prawdziwym silnikiem walki (resolve_wrestling) ──────────────

def _combat_db(tmp_path, *, player_str=14, enemy_str=10, wrestling_rank=1,
               player_zone="engaged", enemy_zone="engaged", enemy_hp=40):
    db = tmp_path / "wrestle.db"
    player = {
        "id": "player", "type": "player", "name": "Aldric",
        "hp_current": 20, "hp_max": 20, "defense": 10, "zone": player_zone,
        "stats": {"STR": player_str, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
        "conditions": [],
    }
    enemy = {
        "id": "bandit", "type": "enemy", "enemy_key": "bandit", "name": "Bandyta",
        "hp_current": enemy_hp, "hp_max": 40, "defense": 10, "attack_bonus": 0,
        "damage_dice": "1d6", "zone": enemy_zone, "conditions": [],
        "stats": {"STR": enemy_str, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
    }
    sheet = {"stats": player["stats"], "current_hp": 20, "max_hp": 20,
             "conditions": [], "skills": {"wrestling": wrestling_rank}}
    combatants = json.dumps([player, enemy], ensure_ascii=False).replace("'", "''")
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(f"""
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, status TEXT DEFAULT 'active');
        INSERT INTO campaigns (id,title) VALUES (1,'S17');
        CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
          name TEXT, system_id TEXT, sheet_json TEXT);
        INSERT INTO characters (id,campaign_id,user_id,name,system_id,sheet_json)
          VALUES (1,1,1,'Aldric','fantasy','{sj}');
        CREATE TABLE active_combat (id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER UNIQUE,
          character_id INTEGER, round INTEGER DEFAULT 1, turn_order TEXT, current_turn TEXT,
          combatants TEXT, status TEXT DEFAULT 'active', ended_reason TEXT, location_tag TEXT,
          loot_pool TEXT, created_at TEXT, updated_at TEXT);
        INSERT INTO active_combat (campaign_id,character_id,round,turn_order,current_turn,combatants,status)
          VALUES (1,1,1,'["player","bandit"]','player','{combatants}','active');
        CREATE TABLE combat_turns (id INTEGER PRIMARY KEY AUTOINCREMENT, combat_id INTEGER, campaign_id INTEGER,
          turn_number REAL, actor TEXT, event_type TEXT, roll_value INTEGER, damage INTEGER, hp_after INTEGER,
          target_id TEXT, target_name TEXT, hit INTEGER, narrative TEXT,
          created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
        CREATE TABLE game_config_conditions (key TEXT PRIMARY KEY, label TEXT, effect_json TEXT,
          is_active INTEGER DEFAULT 1, stackable INTEGER DEFAULT 0);
        INSERT INTO game_config_conditions (key,label,effect_json,is_active,stackable) VALUES
          ('slowed','Spowolniony','{{"effects":[{{"type":"static_stat_modifier","stat":"DEX","value":-2}}]}}',1,0),
          ('stunned','Ogłuszony','{{"effects":[{{"type":"skip_turn"}}]}}',1,0);
        CREATE TABLE skill_counters (player_skill_key TEXT PRIMARY KEY, counter_type TEXT DEFAULT 'dc',
          counter_key TEXT, default_dc INTEGER DEFAULT 12,
          on_success_condition TEXT, on_crit_condition TEXT, on_critfail_self_condition TEXT);
        INSERT INTO skill_counters
          (player_skill_key,counter_type,counter_key,default_dc,on_success_condition,on_crit_condition,on_critfail_self_condition)
          VALUES ('wrestling','opposed','STR',12,'slowed','stunned','slowed');
        """)
        conn.commit()
    finally:
        conn.close()
    return db


def _seq_d20(values):
    """Zwraca funkcję roll_d20 zwracającą kolejne wartości z listy (player, enemy, ...)."""
    it = iter(values)
    return lambda *a, **k: next(it)


def _enemy_conditions(db):
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
        combatants = json.loads(row[0])
    finally:
        conn.close()
    enemy = next(c for c in combatants if c.get("type") == "enemy")
    player = next(c for c in combatants if c.get("type") == "player")
    return ([str(x.get("key")) for x in (enemy.get("conditions") or [])],
            [str(x.get("key")) for x in (player.get("conditions") or [])])


def test_wrestling_success_slows_enemy(tmp_path, monkeypatch):
    """Realny silnik: sukces (margines 0…+4) → CEL dostaje slowed."""
    db = _combat_db(tmp_path, player_str=14, enemy_str=10)  # player +2, enemy +0
    # player d20=12 → 14 ; enemy d20=12 → 12 ; margines +2 → SUCCESS (nie crit)
    monkeypatch.setattr(combat_service, "roll_d20", _seq_d20([12, 12]))
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_wrestling(1)
    assert out["ok"] is True
    assert out["outcome"] == "SUCCESS"
    enemy_conds, player_conds = _enemy_conditions(db)
    assert "slowed" in enemy_conds
    assert "stunned" not in enemy_conds
    assert player_conds == []


def test_wrestling_crit_stuns_enemy(tmp_path, monkeypatch):
    """Margines ≥ +5 → CEL dostaje stunned (mocniejsza kondycja)."""
    db = _combat_db(tmp_path, player_str=18, enemy_str=8)  # player +4, enemy -1
    # player d20=15 → 19+rank1=20 ; enemy d20=8 → 7 ; margines ≥ +5 → CRITICAL_SUCCESS
    monkeypatch.setattr(combat_service, "roll_d20", _seq_d20([15, 8]))
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_wrestling(1)
    assert out["outcome"] == "CRITICAL_SUCCESS"
    enemy_conds, _ = _enemy_conditions(db)
    assert "stunned" in enemy_conds


def test_wrestling_critfail_slows_self(tmp_path, monkeypatch):
    """Margines ≤ −5 → GRACZ sam dostaje slowed (przewrócony)."""
    db = _combat_db(tmp_path, player_str=8, enemy_str=18)  # player -1, enemy +4
    # player d20=3 → 2+rank1=3 ; enemy d20=15 → 19 ; margines ≤ −5 → CRITICAL_FAILURE
    monkeypatch.setattr(combat_service, "roll_d20", _seq_d20([3, 15]))
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_wrestling(1)
    assert out["outcome"] == "CRITICAL_FAILURE"
    enemy_conds, player_conds = _enemy_conditions(db)
    assert "slowed" in player_conds
    assert "slowed" not in enemy_conds


def test_wrestling_zone_gate_blocks_ranged(tmp_path, monkeypatch):
    """Cel poza zwarciem (ranged) → blokada bez konsumpcji tury (jak melee out_of_range)."""
    db = _combat_db(tmp_path, enemy_zone="ranged")
    monkeypatch.setattr(combat_service, "roll_d20", _seq_d20([12, 12]))
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_wrestling(1)
    assert out["ok"] is False
    assert out["block_reason"] == "out_of_range"
    # tura NIE skonsumowana — nadal gracza
    conn = sqlite3.connect(str(db))
    try:
        cur = conn.execute("SELECT current_turn FROM active_combat WHERE campaign_id=1").fetchone()[0]
    finally:
        conn.close()
    assert cur == "player"
    enemy_conds, _ = _enemy_conditions(db)
    assert enemy_conds == []


def test_wrestling_consumes_turn(tmp_path, monkeypatch):
    """Udane zapasy konsumują turę gracza (advance_turn → kolej wroga)."""
    db = _combat_db(tmp_path)
    monkeypatch.setattr(combat_service, "roll_d20", _seq_d20([12, 12]))
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        combat_service.resolve_wrestling(1)
    conn = sqlite3.connect(str(db))
    try:
        cur = conn.execute("SELECT current_turn FROM active_combat WHERE campaign_id=1").fetchone()[0]
    finally:
        conn.close()
    assert cur == "bandit"


def test_wrestling_requires_player_turn(tmp_path, monkeypatch):
    """Poza turą gracza wrestling jest odrzucany (ValueError)."""
    db = _combat_db(tmp_path)
    conn = sqlite3.connect(str(db))
    try:
        conn.execute("UPDATE active_combat SET current_turn='bandit' WHERE campaign_id=1")
        conn.commit()
    finally:
        conn.close()
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        with pytest.raises(ValueError):
            combat_service.resolve_wrestling(1)


def test_wrestling_logs_both_rolls(tmp_path, monkeypatch):
    """Log walki ma event_type='wrestling' z obiema stronami rzutu (jawne dla narratora/UI)."""
    db = _combat_db(tmp_path)
    monkeypatch.setattr(combat_service, "roll_d20", _seq_d20([12, 10]))
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        combat_service.resolve_wrestling(1)
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute(
            "SELECT event_type, narrative FROM combat_turns WHERE event_type='wrestling'").fetchone()
    finally:
        conn.close()
    assert row is not None
    nar = json.loads(row[1])
    assert nar["player_roll"] == 12 and nar["enemy_roll"] == 10
    assert "outcome" in nar and "margin" in nar


# ─── Backward compat — zwykła zmiana strefy nadal działa (silnik nietknięty) ──

def test_zone_change_still_works(tmp_path, monkeypatch):
    """change_player_zone (T34) działa bez zmian po dodaniu wrestling."""
    db = _combat_db(tmp_path)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.change_player_zone(1)
    assert out["ok"] is True
    assert out["to"] == "ranged"  # engaged → ranged


# ─── Seed (po rebuildzie /data — RED zanim migracja wejdzie) ──────────────────

def test_wrestling_skill_and_counter_seeded():
    """Skill wrestling (STR) + skill_counters opposed STR vs STR z mapowaniem kondycji."""
    conn = sqlite3.connect("/data/ai_gm.db")
    try:
        skill = conn.execute(
            "SELECT linked_stat FROM game_config_skills WHERE key='wrestling'").fetchone()
        assert skill is not None, "skill 'wrestling' nie zaseedowany"
        assert str(skill[0]).upper() == "STR"
        ctr = conn.execute(
            "SELECT counter_type, counter_key, on_success_condition, on_crit_condition, "
            "on_critfail_self_condition FROM skill_counters WHERE player_skill_key='wrestling'"
        ).fetchone()
        assert ctr is not None, "skill_counters dla 'wrestling' nie zaseedowany"
        assert ctr[0] == "opposed" and str(ctr[1]).upper() == "STR"
        assert ctr[2] == "slowed" and ctr[3] == "stunned" and ctr[4] == "slowed"
    finally:
        conn.close()
