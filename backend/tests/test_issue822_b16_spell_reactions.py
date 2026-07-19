"""TDD: Issue #822 (B16) — system reakcji czarów (mirror_image / blink / globe_invulnerability).

MVP = STAN PREWENCYJNY (decyzja akceptacji #1): czar `spell_type='reaction'` rzucony na siebie
zapisuje stan na combatancie gracza; stan auto-odpala się przy NASTĘPNYM trafieniu wroga,
w punkcie PRZED obrażeniami — wcześniej niż okno reakcji dodge/block (iluzja „zjada" cios).
Bez prawdziwego interrupt-window między turami (poza zakresem MVP).

Modele (Numbers Policy — wartości startowe, strojone w Sandboxie):
  • mirror_image  (T2, 3 mana) → pula N ŁADUNKÓW anulowania; każdy cios zużywa 1 ładunek → 0 dmg;
                                  pula 0 → stan znika.
  • blink         (T3, 4 mana) → % szansy pudła przez N rund; każdy cios losuje d100 ≤ miss_chance → 0 dmg;
                                  po wygaśnięciu rund stan znika.
  • globe_invulnerability (T5, 6 mana) → N rund nietykalności; każdy cios → 0 dmg, bez zużycia ładunku;
                                  po wygaśnięciu rund stan znika.

Priorytet rozstrzygania: globe > mirror_image > blink. Reakcja czaru poprzedza dodge/shield_block
(jedna reakcja/rundę — czar negujący cios pomija okno dodge/block). Brak regresji S15/S16/B10.
"""
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _fixtures_schema import table_sql

from app.services import combat_service, spell_service


# ─── Pure helper: _try_spell_reaction (auto-wyzwalany stan PRZED obrażeniami) ──

def test_globe_negates_for_active_rounds_then_expires():
    """globe_invulnerability aktywne w zadeklarowanych rundach → cios znegowany; po wygaśnięciu None."""
    p = {"globe_invulnerability": {"until_round": 3}}
    out = {}
    res = combat_service._try_spell_reaction(p, 2, out)        # runda 2 ≤ 3
    assert res is not None and res.get("negated") is True
    assert res.get("type") == "globe_invulnerability"
    assert p.get("globe_invulnerability") is not None          # globe nie zużywa ładunku
    # runda 4 > 3 → wygasa, brak negacji, klucz usunięty
    out2 = {}
    res2 = combat_service._try_spell_reaction(p, 4, out2)
    assert res2 is None
    assert "globe_invulnerability" not in p


def test_mirror_image_consumes_one_charge_per_hit():
    """mirror_image: każdy cios zużywa 1 ładunek i neguje; pula 0 → stan znika."""
    p = {"mirror_image": {"charges": 2}}
    res1 = combat_service._try_spell_reaction(p, 1, {})
    assert res1.get("negated") is True and res1.get("type") == "mirror_image"
    assert p["mirror_image"]["charges"] == 1
    res2 = combat_service._try_spell_reaction(p, 1, {})
    assert res2.get("negated") is True
    assert "mirror_image" not in p                              # ostatni ładunek → stan znika
    res3 = combat_service._try_spell_reaction(p, 1, {})
    assert res3 is None                                         # brak ładunków → normalna ścieżka


def test_blink_negates_when_roll_within_chance():
    """blink: d100 ≤ miss_chance → cios znegowany (migocze przez pustkę)."""
    p = {"blink": {"miss_chance": 50, "until_round": 3}}
    with patch.object(combat_service, "_roll_d100", lambda: 30):  # 30 ≤ 50 → pudło
        res = combat_service._try_spell_reaction(p, 2, {})
    assert res is not None and res.get("negated") is True
    assert res.get("type") == "blink"
    assert p.get("blink") is not None                            # blink trwa do końca rund


def test_blink_does_not_negate_when_roll_above_chance():
    """blink: d100 > miss_chance → cios przechodzi (None → normalna ścieżka obrażeń)."""
    p = {"blink": {"miss_chance": 50, "until_round": 3}}
    with patch.object(combat_service, "_roll_d100", lambda: 80):  # 80 > 50 → trafia
        res = combat_service._try_spell_reaction(p, 2, {})
    assert res is None
    assert p.get("blink") is not None                            # stan nadal aktywny (kolejne ciosy)


def test_blink_expires_after_rounds():
    """blink poza zadeklarowanymi rundami → wygasa, klucz usunięty, brak negacji."""
    p = {"blink": {"miss_chance": 50, "until_round": 2}}
    res = combat_service._try_spell_reaction(p, 5, {})           # runda 5 > 2
    assert res is None
    assert "blink" not in p


def test_no_reaction_state_returns_none():
    """Brak stanu reakcji → None (silnik idzie normalną ścieżką dodge/block/dmg)."""
    p = {"hp_current": 10}
    assert combat_service._try_spell_reaction(p, 1, {}) is None


def test_priority_globe_over_mirror_image():
    """globe + mirror_image aktywne → globe rozstrzyga PIERWSZY (ładunek lustra NIE zużyty)."""
    p = {"globe_invulnerability": {"until_round": 5}, "mirror_image": {"charges": 2}}
    res = combat_service._try_spell_reaction(p, 1, {})
    assert res.get("type") == "globe_invulnerability"
    assert p["mirror_image"]["charges"] == 2                     # lustro nietknięte


# ─── Integracja z silnikiem walki (resolve_attack, spell_type=reaction) ───────

def _combat_db(tmp_path, *, mana=10, max_mana=10, round_n=1,
               player_state=None, current_turn="player"):
    db = tmp_path / "b16.db"
    player = {
        "id": "player", "type": "player", "name": "Mag",
        "hp_current": 12, "hp_max": 12, "defense": 10, "zone": "ranged",
        "stats": {"STR": 8, "DEX": 10, "CON": 8, "INT": 16, "WIS": 12, "CHA": 10},
        "conditions": [],
    }
    if player_state:
        player.update(player_state)
    enemy = {
        "id": "goblin", "type": "enemy", "enemy_key": "goblin", "name": "Goblin",
        "hp_current": 20, "hp_max": 20, "defense": 10, "attack_bonus": 5,
        "damage_dice": "1d6", "zone": "ranged", "conditions": [],
        "stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 7, "WIS": 8, "CHA": 8},
    }
    sheet = {
        "archetype": "scholar", "level": 5,
        "stats": player["stats"], "current_hp": 12, "max_hp": 12,
        "current_mana": mana, "max_mana": max_mana, "conditions": [], "skills": {},
    }
    combatants = json.dumps([player, enemy], ensure_ascii=False).replace("'", "''")
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(f"""
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, status TEXT DEFAULT 'active', mode TEXT);
        INSERT INTO campaigns (id,title,mode) VALUES (1,'B16','single');
        CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
          name TEXT, system_id TEXT, sheet_json TEXT);
        INSERT INTO characters (id,campaign_id,user_id,name,system_id,sheet_json)
          VALUES (1,1,1,'Mag','fantasy','{sj}');
        CREATE TABLE active_combat (id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER UNIQUE,
          character_id INTEGER, round INTEGER DEFAULT 1, turn_order TEXT, current_turn TEXT,
          combatants TEXT, status TEXT DEFAULT 'active', ended_reason TEXT, location_tag TEXT,
          loot_pool TEXT, boss_defeated INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT);
        INSERT INTO active_combat (campaign_id,character_id,round,turn_order,current_turn,combatants,status)
          VALUES (1,1,{round_n},'["player","goblin"]','{current_turn}','{combatants}','active');
        CREATE TABLE combat_turns (id INTEGER PRIMARY KEY AUTOINCREMENT, combat_id INTEGER, campaign_id INTEGER,
          turn_number REAL, actor TEXT, event_type TEXT, roll_value INTEGER, damage INTEGER, hp_after INTEGER,
          target_id TEXT, target_name TEXT, hit INTEGER, narrative TEXT,
          created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
        """ + table_sql("game_config_conditions") + """
        """ + table_sql("game_config_spells") + """
        INSERT INTO game_config_spells (key,label,spell_type,mana_cost,tier,target_zone,effect_json) VALUES
          ('mirror_image','Lustrzane Odbicie','reaction',3,2,'self','{"reaction":"mirror_image","charges":3}'),
          ('blink','Migotanie','reaction',4,3,'self','{"reaction":"blink","miss_chance":50,"rounds":3}'),
          ('globe_invulnerability','Kula Niewrażliwości','reaction',6,5,'self','{"reaction":"globe_invulnerability","rounds":2}');
        INSERT INTO game_config_spells (key,label,spell_type,mana_cost,tier,damage_die) VALUES
          ('fire_bolt','Ognisty Pocisk','attack',2,1,'1d8');
        CREATE TABLE character_spells (character_id INTEGER, spell_key TEXT, rank INTEGER DEFAULT 1,
          learned_at_level INTEGER DEFAULT 1);
        """ + table_sql("game_config_enemies") + """
        INSERT INTO game_config_enemies (key,label,hp_base,ac_base,attack_bonus,damage_die,dex_modifier,skills_json,stats_json,tier,loot_table_key,drop_chance,xp_award)
          VALUES ('goblin','Goblin',20,10,0,'1d6',0,NULL,NULL,'minion',NULL,0,10);
        """)
        conn.execute(
            "INSERT INTO character_spells (character_id, spell_key, rank) "
            "SELECT c.id, s.key, 1 FROM characters c, game_config_spells s"
        )  # #1431: bramka wymaga znanego czaru — seeduj czary jako znane
        conn.commit()
    finally:
        conn.close()
    return db


def _player_combatant(db):
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
        combatants = json.loads(row[0])
    finally:
        conn.close()
    return next(c for c in combatants if c.get("type") == "player")


def _mana(db):
    conn = sqlite3.connect(str(db))
    try:
        sj = conn.execute("SELECT sheet_json FROM characters WHERE id=1").fetchone()[0]
    finally:
        conn.close()
    return int(json.loads(sj).get("current_mana"))


def test_cast_mirror_image_sets_charges_state(tmp_path):
    """mirror_image w walce → stan mirror_image.charges=3, mana 10→7, ZERO obrażeń wrogowi."""
    db = _combat_db(tmp_path, mana=10)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, None, attacker="player", raw_d20=12,
                                            spell_key="mirror_image")
    assert out.get("spell_type") == "reaction"
    assert int(out.get("damage") or 0) == 0
    p = _player_combatant(db)
    assert p.get("mirror_image", {}).get("charges") == 3
    assert _mana(db) == 7


def test_cast_blink_sets_blink_state(tmp_path):
    """blink w walce (runda 1, rounds=3) → stan blink aktywny do rundy 3, mana 10→6."""
    db = _combat_db(tmp_path, mana=10, round_n=1)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, None, attacker="player", raw_d20=12,
                                            spell_key="blink")
    assert out.get("spell_type") == "reaction"
    p = _player_combatant(db)
    assert p.get("blink", {}).get("miss_chance") == 50
    assert p.get("blink", {}).get("until_round") == 3            # runda 1 + 3 rundy - 1
    assert _mana(db) == 6


def test_cast_globe_sets_invulnerability_window(tmp_path):
    """globe_invulnerability (runda 2, rounds=2) → stan aktywny do rundy 3, mana 10→4."""
    db = _combat_db(tmp_path, mana=10, round_n=2)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, None, attacker="player", raw_d20=12,
                                            spell_key="globe_invulnerability")
    assert out.get("spell_type") == "reaction"
    p = _player_combatant(db)
    assert p.get("globe_invulnerability", {}).get("until_round") == 3   # runda 2 + 2 rundy - 1
    assert _mana(db) == 4


def test_cast_reaction_insufficient_mana_blocked(tmp_path):
    """Za mało many → blocked, stan NIE nałożony."""
    db = _combat_db(tmp_path, mana=1)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, None, attacker="player", raw_d20=12,
                                            spell_key="globe_invulnerability")
    assert out.get("blocked") is True
    assert out.get("mana_insufficient") is True
    assert "globe_invulnerability" not in _player_combatant(db)


def test_enemy_attack_mirror_image_eats_blow(tmp_path):
    """Wróg trafia: mirror_image (3) zjada cios → 0 dmg w bohatera, ładunek 3→2, HP=12."""
    db = _combat_db(tmp_path, mana=10, current_turn="goblin",
                    player_state={"mirror_image": {"charges": 3}})
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)), \
         patch.object(combat_service, "roll_d20", lambda *a, **k: 18), \
         patch.object(combat_service, "roll_damage_dice", lambda *a, **k: 5):
        out = combat_service.resolve_attack(1, None, attacker="enemy", raw_d20=None)
    assert out.get("hit") is True
    assert int(out.get("damage") or 0) == 0
    assert int(out.get("player_hp_remaining") or 0) == 12
    p = _player_combatant(db)
    assert p.get("mirror_image", {}).get("charges") == 2
    sr = out.get("spell_reaction") or {}
    assert sr.get("type") == "mirror_image" and sr.get("negated") is True


def test_enemy_attack_globe_zeroes_damage(tmp_path):
    """Wróg trafia: globe aktywne (do rundy 3, walka w rundzie 1) → 0 dmg, HP=12, ładunek nie potrzebny."""
    db = _combat_db(tmp_path, mana=10, round_n=1, current_turn="goblin",
                    player_state={"globe_invulnerability": {"until_round": 3}})
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)), \
         patch.object(combat_service, "roll_d20", lambda *a, **k: 18), \
         patch.object(combat_service, "roll_damage_dice", lambda *a, **k: 6):
        out = combat_service.resolve_attack(1, None, attacker="enemy", raw_d20=None)
    assert int(out.get("damage") or 0) == 0
    assert int(out.get("player_hp_remaining") or 0) == 12
    assert _player_combatant(db).get("globe_invulnerability") is not None


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_enemy_attack_without_reaction_state_still_damages(tmp_path):
    """Brak stanu reakcji → cios wroga zadaje obrażenia normalnie (S15/B10 nietknięte).
    T5-5e (#1351): single-player bez wyszkolonej reakcji otwiera okno take-only; obrażenia
    naliczane po resolve_reaction("take")."""
    db = _combat_db(tmp_path, mana=10, current_turn="goblin")
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)), \
         patch.object(combat_service, "roll_d20", lambda *a, **k: 18), \
         patch.object(combat_service, "roll_damage_dice", lambda *a, **k: 5):
        out = combat_service.resolve_attack(1, None, attacker="enemy", raw_d20=None)
        assert out.get("hit") is True
        if out.get("reaction_window"):
            out = combat_service.resolve_reaction(1, "take")
    assert int(out.get("damage") or 0) > 0
    assert int(out.get("player_hp_remaining") or 0) < 12


def test_attack_spell_unchanged_not_reaction(tmp_path):
    """fire_bolt (attack) NIE wchodzi w gałąź reaction — nadal atak (#475 nietknięte)."""
    db = _combat_db(tmp_path, mana=10)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)), \
         patch.object(combat_service, "roll_d20", lambda *a, **k: 5):
        out = combat_service.resolve_attack(1, None, attacker="player", raw_d20=18,
                                            spell_key="fire_bolt")
    assert out.get("spell_type") != "reaction"
    assert "reaction" not in str(out.get("attack_test") or "")
