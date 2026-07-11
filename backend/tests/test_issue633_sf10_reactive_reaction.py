"""TDD: Issue #633 — SF10: reaktywny modal uniku/bloku (zastępuje pre-deklarację).

Model REAKTYWNY (decyzja Piotra 2026-06-15): gdy wróg TRAFIA i gracz ma DOSTĘPNĄ reakcję
(skill dodge ≥ 1 LUB shield_block ≥ 1 + tarcza), niezużytą w tej rundzie — silnik NIE
nalicza obrażeń od razu. Zamiast tego ustawia `pending_reaction` w stanie walki i zwraca
`reaction_window=True` z listą dostępnych opcji. Pętla tury wroga PAUZUJE.

Gracz wybiera przez `resolve_reaction(campaign_id, choice)`:
  • take  → pełne obrażenia (bez rzutu)
  • dodge → test DEX vs trafienie (reuse _try_dodge_reaction); sukces = 0 dmg
  • block → test STR (reuse _try_shield_block_reaction); redukcja/odparcie

Zasady: 1 reakcja/rundę (drugi cios tej rundy = auto, bez okna). Brak skilla i tarczy =
brak okna (auto-naliczanie, jak dawniej). RZUT ATAKU WROGA (nat 20/nat 1) NIETKNIĘTY.
"""
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import combat_service


# ─── DB fixture (wzorzec z #611) ──────────────────────────────────────────────

def _combat_db(tmp_path, *, dodge_rank=0, shield_block_rank=0, shield=False,
               attack_bonus=10, round_n=1, reaction_used_round=0):
    db = tmp_path / "sf10.db"
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
    combatants = json.dumps([player, enemy], ensure_ascii=False).replace("'", "''")
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(f"""
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, status TEXT DEFAULT 'active', mode TEXT);
        INSERT INTO campaigns (id,title) VALUES (1,'SF10');
        CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
          name TEXT, system_id TEXT, sheet_json TEXT);
        INSERT INTO characters (id,campaign_id,user_id,name,system_id,sheet_json)
          VALUES (1,1,1,'Aldric','fantasy','{sj}');
        CREATE TABLE game_config_weapons (key TEXT PRIMARY KEY, label TEXT);
        INSERT INTO game_config_weapons (key,label) VALUES ('wooden_shield','Drewniana Tarcza');
        CREATE TABLE character_inventory (id INTEGER PRIMARY KEY AUTOINCREMENT,
          character_id INTEGER, weapon_key TEXT, item_key TEXT, equipped INTEGER DEFAULT 0,
          durability_current INTEGER, durability_max INTEGER, affixes_json TEXT);
        CREATE TABLE active_combat (id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER UNIQUE,
          character_id INTEGER, round INTEGER DEFAULT 1, turn_order TEXT, current_turn TEXT,
          combatants TEXT, status TEXT DEFAULT 'active', ended_reason TEXT, location_tag TEXT,
          loot_pool TEXT, created_at TEXT, updated_at TEXT);
        INSERT INTO active_combat (campaign_id,character_id,round,turn_order,current_turn,combatants,status)
          VALUES (1,1,{round_n},'["bandit","player"]','bandit','{combatants}','active');
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


def _pending(db):
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
        for c in json.loads(row[0]):
            if c.get("id") == "player":
                return c.get("pending_reaction")
    finally:
        conn.close()
    return None


# ─── Test główny: okno reakcji zamiast natychmiastowych obrażeń ───────────────

def test_hit_opens_reaction_window_not_damage(tmp_path, monkeypatch):
    """Trafienie + dostępny unik → reaction_window, obrażenia NIE naliczone, pending zapisane."""
    db = _combat_db(tmp_path, dodge_rank=2, attack_bonus=10)
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 10)        # attack_roll 20 trafia
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 7)
    monkeypatch.setattr(combat_service, "roll_dice_detailed",
                        lambda *a, **k: {"die": "1d6", "rolls": [7], "sides": 6, "n": 1})
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, 0, attacker="enemy")
    assert out["hit"] is True
    assert out.get("reaction_window") is True
    assert "dodge" in (out.get("reaction_options") or [])
    assert out.get("reaction_resolved") is not True
    # obrażenia NIE naliczone — HP gracza nietknięte, pending zapisane w stanie walki
    assert _combatant_hp(db) == 20
    pend = _pending(db)
    assert pend is not None
    assert int(pend.get("attack_roll", 0)) > 0


def test_resolve_reaction_take_applies_full_damage(tmp_path, monkeypatch):
    """Po oknie: choice=take → pełne obrażenia, pending wyczyszczone.

    #826: 'take' przepuszcza obrażenia przez nowy model: 7 baza + margines (atak 20 −
    obrona pac 10 = 10 → 2 progi → +2), pancerz 0 (ac_base 10). Razem 9."""
    db = _combat_db(tmp_path, dodge_rank=2, attack_bonus=10)
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 10)
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 7)
    monkeypatch.setattr(combat_service, "roll_dice_detailed",
                        lambda *a, **k: {"die": "1d6", "rolls": [7], "sides": 6, "n": 1})
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        combat_service.resolve_attack(1, 0, attacker="enemy")
        out = combat_service.resolve_reaction(1, "take")
    assert out["damage"] == 9                   # 7 baza + 2 margines (#826)
    assert out.get("margin_damage_bonus") == 2
    assert out["player_hp_remaining"] == 11
    assert _combatant_hp(db) == 11
    assert _pending(db) is None


def test_resolve_reaction_dodge_success_negates(tmp_path, monkeypatch):
    """choice=dodge z wysokim rzutem → 0 obrażeń."""
    db = _combat_db(tmp_path, dodge_rank=2, attack_bonus=0)
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 7)
    monkeypatch.setattr(combat_service, "roll_dice_detailed",
                        lambda *a, **k: {"die": "1d6", "rolls": [7], "sides": 6, "n": 1})
    # atak: raw 10 → attack_roll 10 (trafia AC 10); unik: 18 + DEX2 + rank2 = 22 vs 10 → sukces
    rolls = iter([10, 18])
    monkeypatch.setattr(combat_service, "roll_d20", lambda: next(rolls))
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        combat_service.resolve_attack(1, 0, attacker="enemy")
        out = combat_service.resolve_reaction(1, "dodge")
    assert out["reaction"]["reaction"] == "dodge"
    assert out["reaction"]["dodged"] is True
    assert out["damage"] == 0
    assert _combatant_hp(db) == 20


# ─── Brak dostępnej reakcji → natychmiastowe obrażenia (backward-compat) ───────

def test_no_skill_no_shield_applies_damage_immediately(tmp_path, monkeypatch):
    """Brak dodge i tarczy → brak okna reakcji, obrażenia naliczone od razu.

    #826: AC nie jest już progiem trafienia — bez reakcji rozstrzyga pojedynczy pasywny
    unik d20+DEX (tu d20=10 + DEX_mod 2 = 12 < atak 20 → trafienie). Obrażenia bazowe 5
    + margines (atak 20 − obrona pac 10 = 10 → 2 progi po 5 → +2), pancerz 0 (ac_base 10
    → armor max(0,10−10)=0). Razem 7."""
    db = _combat_db(tmp_path, dodge_rank=0, shield_block_rank=0, shield=False, attack_bonus=10)
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 10)
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 5)
    monkeypatch.setattr(combat_service, "roll_dice_detailed",
                        lambda *a, **k: {"die": "1d6", "rolls": [5], "sides": 6, "n": 1})
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, 0, attacker="enemy")
    assert out["hit"] is True
    assert out.get("reaction_window") is not True
    assert out["damage"] == 7          # 5 baza + 2 margines (#826), pancerz 0
    assert out.get("margin_damage_bonus") == 2
    assert _combatant_hp(db) == 13


# ─── 1 reakcja/rundę ──────────────────────────────────────────────────────────

def test_one_reaction_per_round(tmp_path, monkeypatch):
    """Reakcja już zużyta w tej rundzie → drugi cios bez okna, obrażenia od razu.

    #826: reakcja zużyta → ścieżka bez reakcji (pasywny unik d20+DEX 12 < atak 20 → trafia).
    6 baza + 2 margines (atak 20 − pac 10), pancerz 0 → 8."""
    db = _combat_db(tmp_path, dodge_rank=2, attack_bonus=10, round_n=1, reaction_used_round=1)
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 10)
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 6)
    monkeypatch.setattr(combat_service, "roll_dice_detailed",
                        lambda *a, **k: {"die": "1d6", "rolls": [6], "sides": 6, "n": 1})
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, 0, attacker="enemy")
    assert out.get("reaction_window") is not True
    assert out["damage"] == 8          # 6 baza + 2 margines (#826)
    assert _combatant_hp(db) == 12


# ─── #826: gracz z reakcją dostaje OKNO uniku nawet na słaby cios ──────────────

def test_enemy_low_roll_opens_window_for_reaction_player(tmp_path, monkeypatch):
    """#826 (zastępuje pudło-AC): AC nie jest progiem trafienia. Gracz z dostępnym
    unikiem dostaje okno reakcji na KAŻDY cios (poza Nat 1 wroga) — słaby rzut wroga
    zostanie łatwo uniknięty w oknie, zamiast być z góry odfiltrowanym progiem AC.
    To naprawia 'wcisnąłem unik a oberwałem': unik mierzy się z faktycznym rzutem ataku."""
    db = _combat_db(tmp_path, dodge_rank=2, attack_bonus=0)
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 3)   # słaby cios wroga (atak 3)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, 0, attacker="enemy")
    assert out["hit"] is True                 # cios dosięga; jedyny test = okno uniku
    assert out.get("reaction_window") is True
    assert "dodge" in (out.get("reaction_options") or [])
    assert _combatant_hp(db) == 20            # obrażenia wstrzymane do resolve_reaction


def test_enemy_nat1_auto_miss_no_window(tmp_path, monkeypatch):
    """#826: Nat 1 wroga = auto-pudło nawet gdy gracz ma unik — żadnego okna, HP nietknięte."""
    db = _combat_db(tmp_path, dodge_rank=2, attack_bonus=0)
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 1)   # Nat 1 wroga
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, 0, attacker="enemy")
    assert out["hit"] is False
    assert out.get("reaction_window") is not True
    assert _combatant_hp(db) == 20
