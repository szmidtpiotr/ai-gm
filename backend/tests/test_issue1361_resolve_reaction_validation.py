"""TDD: Issue #1361 (WALKA-T2-FIX-b) — `resolve_reaction` waliduje wybór vs `pending['options']`.

Weryfikacja #1359: `resolve_reaction` sprawdzał tylko czy wybór jest ZNANYM typem reakcji —
nie sprawdzał go względem `pending_reaction.options` (available-only, zapisane przy otwarciu
okna). Resolvery `_try_*` gate'ują skill/locked/no_shield/no_mana, ale ŻADEN nie re-sprawdza
capu 1/rundę (#1322). Skutek: opcja wyszarzona `cap_reached` wysłana ręcznie (devtools) była
w pełni stosowana → obejście capu SF10.

Fix: wybór != 'take' MUSI być w `pending['options']`; inaczej degradacja do 'take' + flaga
`reaction_rejected`. Jedno miejsce pokrywa wszystkie powody (cap/mana/shield/lockout).
"""
from _fixtures_schema import table_sql
import json
import sqlite3
from unittest.mock import patch

import pytest

from app.services import combat_service


# ─── DB fixture (wzorzec z #633) ──────────────────────────────────────────────

def _combat_db(tmp_path, *, dodge_rank=0, shield_block_rank=0, shield=False,
               attack_bonus=0, round_n=1, reaction_used_round=0, second_enemy=False):
    db = tmp_path / "i1361.db"
    player = {
        "id": "player", "type": "player", "name": "Aldric",
        "hp_current": 20, "hp_max": 20, "defense": 10, "zone": "engaged",
        "stats": {"STR": 14, "DEX": 14, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
        "conditions": [],
    }
    if reaction_used_round:
        player["reaction_used_round"] = reaction_used_round
    enemy = {
        "id": "bandit", "type": "enemy", "enemy_key": "bandit", "name": "Bandit",
        "hp_current": 40, "hp_max": 40, "attack_bonus": attack_bonus,
        "damage_dice": "1d8", "zone": "engaged",
    }
    sheet = {"stats": player["stats"], "current_hp": 20, "max_hp": 20,
             "defense": {"base": 10}, "conditions": [],
             "skills": {"dodge": dodge_rank, "shield_block": shield_block_rank}}
    combatant_list = [player, enemy]
    order = ["bandit", "player"]
    if second_enemy:
        combatant_list.append({
            "id": "bandit2", "type": "enemy", "enemy_key": "bandit", "name": "Bandit II",
            "hp_current": 40, "hp_max": 40, "attack_bonus": attack_bonus,
            "damage_dice": "1d8", "zone": "engaged",
        })
        order = ["bandit", "bandit2", "player"]
    combatants = json.dumps(combatant_list, ensure_ascii=False).replace("'", "''")
    turn_order_json = json.dumps(order).replace("'", "''")
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(f"""
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, status TEXT DEFAULT 'active', mode TEXT);
        INSERT INTO campaigns (id,title) VALUES (1,'I1361');
        CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
          name TEXT, system_id TEXT, sheet_json TEXT);
        INSERT INTO characters (id,campaign_id,user_id,name,system_id,sheet_json)
          VALUES (1,1,1,'Aldric','fantasy','{sj}');
        """ + table_sql("game_config_weapons") + """
        INSERT INTO game_config_weapons (key,label) VALUES ('wooden_shield','Drewniana Tarcza');
        CREATE TABLE character_inventory (id INTEGER PRIMARY KEY AUTOINCREMENT,
          character_id INTEGER, weapon_key TEXT, item_key TEXT, equipped INTEGER DEFAULT 0,
          durability_current INTEGER, durability_max INTEGER, affixes_json TEXT);
        CREATE TABLE active_combat (id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER UNIQUE,
          character_id INTEGER, round INTEGER DEFAULT 1, turn_order TEXT, current_turn TEXT,
          combatants TEXT, status TEXT DEFAULT 'active', ended_reason TEXT, location_tag TEXT,
          loot_pool TEXT, created_at TEXT, updated_at TEXT);
        INSERT INTO active_combat (campaign_id,character_id,round,turn_order,current_turn,combatants,status)
          VALUES (1,1,{round_n},'{turn_order_json}','bandit','{combatants}','active');
        CREATE TABLE combat_turns (id INTEGER PRIMARY KEY AUTOINCREMENT, combat_id INTEGER, campaign_id INTEGER,
          turn_number REAL, actor TEXT, event_type TEXT, roll_value INTEGER, damage INTEGER, hp_after INTEGER,
          target_id TEXT, target_name TEXT, hit INTEGER, narrative TEXT,
          created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
        """)
        if shield:
            conn.execute(
                "INSERT INTO character_inventory (character_id,weapon_key,equipped,durability_current,durability_max) "
                "VALUES (1,'wooden_shield',1,60,60)")
        conn.commit()
    finally:
        conn.close()
    return db


def _combatant_hp(db, cid="player"):
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
        for c in json.loads(row[0]):
            if c.get("id") == cid:
                return int(c.get("hp_current", -1))
    finally:
        conn.close()
    return -1


def _dice(monkeypatch, d20_seq):
    it = iter(d20_seq)
    monkeypatch.setattr(combat_service, "roll_d20", lambda: next(it))
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 7)
    monkeypatch.setattr(combat_service, "roll_dice_detailed",
                        lambda *a, **k: {"die": "1d6", "rolls": [7], "sides": 6, "n": 1})


# ─── Test główny: opcja spoza pending['options'] (cap_reached) odrzucona ───────

def test_capped_dodge_via_devtools_degraded_to_take(tmp_path, monkeypatch):
    """Swarm + reakcja już zużyta w rundzie → dodge WYSZARZONE (cap_reached, puste options).
    Ręczne wysłanie 'dodge' (devtools) NIE może zanegować obrażeń — degradacja do 'take'.

    Bez fixa: `_try_dodge_reaction` nie re-sprawdza capu → wysoki rzut uniku (20) neguje
    cios mimo wyczerpanego capu (obejście #1322). Z fixem: dodge spoza options → take."""
    db = _combat_db(tmp_path, dodge_rank=2, attack_bonus=0,
                    reaction_used_round=1, second_enemy=True)
    _dice(monkeypatch, [10, 20])   # atak raw10 → trafia AC10; dodge 20 gdyby zastosowany → negacja
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out_atk = combat_service.resolve_attack(1, 0, attacker="enemy")
        assert out_atk.get("reaction_options") == []          # cap → brak dostępnych opcji
        out = combat_service.resolve_reaction(1, "dodge")      # obejście przez devtools
    assert out.get("reaction_rejected") is not None            # fix: odrzucony/zdegradowany
    assert out.get("reaction_rejected", {}).get("choice") == "dodge"
    assert (out.get("reaction") or {}).get("dodged") is not True
    assert out["damage"] > 0                                   # obrażenia naliczone jak 'take'
    assert _combatant_hp(db) < 20                              # cap NIE obejdziony


# ─── Backward compatibility: normalny wybór z okna działa bez zmian ───────────

def test_valid_dodge_from_options_unaffected(tmp_path, monkeypatch):
    """Single enemy, brak capu → dodge JEST w options i normalnie neguje cios (bez flagi)."""
    db = _combat_db(tmp_path, dodge_rank=2, attack_bonus=0)
    _dice(monkeypatch, [10, 20])   # atak trafia; dodge 20+DEX2+rank2=24 vs 10 → sukces
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out_atk = combat_service.resolve_attack(1, 0, attacker="enemy")
        assert "dodge" in (out_atk.get("reaction_options") or [])
        out = combat_service.resolve_reaction(1, "dodge")
    assert out.get("reaction_rejected") is None
    assert out["reaction"]["dodged"] is True
    assert out["damage"] == 0
    assert _combatant_hp(db) == 20


def test_take_always_allowed(tmp_path, monkeypatch):
    """'take' NIGDY nie jest odrzucane, nawet przy pustych options (cap/lockout)."""
    db = _combat_db(tmp_path, dodge_rank=2, attack_bonus=0,
                    reaction_used_round=1, second_enemy=True)
    _dice(monkeypatch, [10])
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        combat_service.resolve_attack(1, 0, attacker="enemy")
        out = combat_service.resolve_reaction(1, "take")
    assert out.get("reaction_rejected") is None
    assert out["damage"] > 0
