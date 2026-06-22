"""TDD: Issue #598 — mechanika walki dwoma broniami (dual-wield).

Matchup-based (decyzja Piotra):
  • dwie LEKKIE bronie (sztylet+sztylet) + skill `dual_wield` rank≥1 → 'dual_attack' (2 ataki/turę)
  • dowolna broń + druga broń (nie-2-lekkie)                        → 'parry' (+2 do obrony, 1 atak)
  • pusta off-hand / tarcza (nie-broń w off)                        → 'none' (1 atak jak dziś)
  • broń dwuręczna w main                                           → 'none' (zajmuje obie ręce)

'Lekkość' broni (#598 MVP): pochodna `finesse` (override jawną kolumną `light` gdy kiedyś dodamy).
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _fixtures_schema import table_sql

from app.services.weapon_rules import (
    PARRY_DEFENSE_BONUS,
    classify_dual_combo,
    dual_wield_skill_rank,
    is_light_weapon,
    offhand_weapon_key_from_inventory,
    parry_defense_bonus,
    weapon_key_from_inventory,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

DAGGER = {"key": "dagger", "label": "Sztylet", "damage_die": "1d4",
          "linked_stat": "DEX", "weapon_type": "melee", "two_handed": 0, "finesse": 1}
SHORTSWORD = {"key": "shortsword", "label": "Short Sword", "damage_die": "1d6",
              "linked_stat": "STR", "weapon_type": "melee", "two_handed": 0, "finesse": 0}
LONGSWORD = {"key": "longsword", "label": "Długi Miecz", "damage_die": "1d8",
             "linked_stat": "STR", "weapon_type": "melee", "two_handed": 0, "finesse": 0}
GREATSWORD = {"key": "greatsword", "label": "Wielki Miecz", "damage_die": "2d6",
              "linked_stat": "STR", "weapon_type": "melee", "two_handed": 1, "finesse": 0}


def _inv_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            weapon_key TEXT,
            equipped INTEGER DEFAULT 0,
            slot TEXT
        );
        """ + table_sql("game_config_weapons") + """
        INSERT INTO game_config_weapons (key,label,damage_die,linked_stat,weapon_type,two_handed,finesse)
        VALUES ('dagger','Sztylet','1d4','DEX','melee',0,1),
               ('shortsword','Short Sword','1d6','STR','melee',0,0),
               ('longsword','Długi Miecz','1d8','STR','melee',0,0);
        """
    )
    return conn


# ─── is_light_weapon ─────────────────────────────────────────────────────────

def test_light_weapon_derived_from_finesse():
    assert is_light_weapon(DAGGER) is True          # finesse → lekka
    assert is_light_weapon(SHORTSWORD) is False      # brak finesse → ciężka
    assert is_light_weapon(LONGSWORD) is False


def test_two_handed_is_never_light():
    assert is_light_weapon(GREATSWORD) is False      # 2H wyklucza lekkość mimo czegokolwiek


def test_explicit_light_column_overrides_finesse():
    # przyszły override: kolumna `light` wygrywa z heurystyką finesse
    assert is_light_weapon({**SHORTSWORD, "light": 1}) is True
    assert is_light_weapon({**DAGGER, "light": 0}) is False


def test_light_weapon_none_is_false():
    assert is_light_weapon(None) is False


# ─── classify_dual_combo ─────────────────────────────────────────────────────

def test_two_light_with_skill_gives_dual_attack():
    assert classify_dual_combo(DAGGER, DAGGER, dual_wield_rank=1) == "dual_attack"
    assert classify_dual_combo(DAGGER, DAGGER, dual_wield_rank=3) == "dual_attack"


def test_two_light_without_skill_is_none():
    # dwa sztylety ale brak umiejętności → 1 atak (off-hand kosmetyczny)
    assert classify_dual_combo(DAGGER, DAGGER, dual_wield_rank=0) == "none"


def test_heavy_main_plus_offhand_weapon_is_parry():
    # short sword (główna) + sztylet (pomocnicza) → parowanie, NIE drugi atak
    assert classify_dual_combo(SHORTSWORD, DAGGER, dual_wield_rank=3) == "parry"
    assert classify_dual_combo(LONGSWORD, LONGSWORD, dual_wield_rank=1) == "parry"


def test_empty_offhand_is_none():
    # nic / tarcza (nie-broń) w pomocniczej → brak mechaniki dual
    assert classify_dual_combo(DAGGER, None, dual_wield_rank=3) == "none"
    assert classify_dual_combo(SHORTSWORD, None, dual_wield_rank=3) == "none"


def test_two_handed_main_blocks_dual():
    # broń dwuręczna zajmuje obie ręce — żaden off-hand nie liczy się
    assert classify_dual_combo(GREATSWORD, DAGGER, dual_wield_rank=3) == "none"


# ─── dual_wield_skill_rank ───────────────────────────────────────────────────

def test_dual_wield_skill_rank_reads_sheet():
    assert dual_wield_skill_rank({"skills": {"dual_wield": 2}}) == 2
    assert dual_wield_skill_rank({"skills": {}}) == 0
    assert dual_wield_skill_rank({}) == 0


# ─── off-hand inventory reader ───────────────────────────────────────────────

def test_offhand_reader_reads_off_hand_slot():
    conn = _inv_db()
    conn.execute("INSERT INTO character_inventory (character_id,weapon_key,equipped,slot) VALUES (?,?,?,?)",
                 (7, "shortsword", 1, "main_hand"))
    conn.execute("INSERT INTO character_inventory (character_id,weapon_key,equipped,slot) VALUES (?,?,?,?)",
                 (7, "dagger", 1, "off_hand"))
    conn.commit()
    assert offhand_weapon_key_from_inventory(conn, 7) == "dagger"
    # backward-compat: main-hand reader nietknięty, dalej zwraca main_hand
    assert weapon_key_from_inventory(conn, 7) == "shortsword"
    conn.close()


def test_offhand_reader_none_when_empty():
    conn = _inv_db()
    conn.execute("INSERT INTO character_inventory (character_id,weapon_key,equipped,slot) VALUES (?,?,?,?)",
                 (8, "shortsword", 1, "main_hand"))
    conn.commit()
    assert offhand_weapon_key_from_inventory(conn, 8) is None
    conn.close()


# ─── parry_defense_bonus (integracja DB) ─────────────────────────────────────

def test_parry_bonus_for_sword_plus_dagger():
    conn = _inv_db()
    conn.execute("INSERT INTO character_inventory (character_id,weapon_key,equipped,slot) VALUES (?,?,?,?)",
                 (9, "shortsword", 1, "main_hand"))
    conn.execute("INSERT INTO character_inventory (character_id,weapon_key,equipped,slot) VALUES (?,?,?,?)",
                 (9, "dagger", 1, "off_hand"))
    conn.commit()
    sheet = {"skills": {"dual_wield": 3}, "stats": {"STR": 14, "DEX": 14}}
    assert parry_defense_bonus(conn, 9, sheet) == PARRY_DEFENSE_BONUS
    conn.close()


def test_no_parry_bonus_for_dual_attack_combo():
    conn = _inv_db()
    conn.execute("INSERT INTO character_inventory (character_id,weapon_key,equipped,slot) VALUES (?,?,?,?)",
                 (10, "dagger", 1, "main_hand"))
    conn.execute("INSERT INTO character_inventory (character_id,weapon_key,equipped,slot) VALUES (?,?,?,?)",
                 (10, "dagger", 1, "off_hand"))
    conn.commit()
    sheet = {"skills": {"dual_wield": 1}, "stats": {"STR": 14, "DEX": 16}}
    # dwa sztylety + skill = dual_attack, NIE parry
    assert parry_defense_bonus(conn, 10, sheet) == 0
    conn.close()


def test_no_parry_bonus_when_offhand_empty():
    conn = _inv_db()
    conn.execute("INSERT INTO character_inventory (character_id,weapon_key,equipped,slot) VALUES (?,?,?,?)",
                 (11, "shortsword", 1, "main_hand"))
    conn.commit()
    assert parry_defense_bonus(conn, 11, {"skills": {}, "stats": {}}) == 0
    conn.close()


# ─── Integracja: resolve_offhand_followup (drugi atak off-hand) ───────────────

def _combat_db(tmp_path) -> str:
    """Minimalna baza walki: 1 aktywna walka (tura gracza) + bohater."""
    import json as _json
    db = str(tmp_path / "ds598_combat.db")
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE active_combat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            character_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            current_turn TEXT,
            combatants TEXT NOT NULL,
            round INTEGER DEFAULT 1
        );
        CREATE TABLE characters (id INTEGER PRIMARY KEY, sheet_json TEXT);
        """
    )
    combatants = _json.dumps([
        {"id": "player", "type": "player", "hp_current": 20, "hp_max": 20},
        {"id": "bandit_01", "type": "enemy", "hp_current": 12, "hp_max": 12},
    ])
    conn.execute(
        "INSERT INTO active_combat (campaign_id,character_id,status,current_turn,combatants) VALUES (?,?,?,?,?)",
        (1, 1, "active", "player", combatants),
    )
    conn.execute("INSERT INTO characters (id,sheet_json) VALUES (1,?)",
                 (_json.dumps({"skills": {"dual_wield": 2}, "stats": {"STR": 14, "DEX": 16}}),))
    conn.commit()
    conn.close()
    return db


_DAGGER_ROW = {"key": "dagger", "label": "Sztylet", "damage_die": "1d4",
               "linked_stat": "DEX", "weapon_type": "melee", "two_handed": 0, "finesse": 1}


def test_offhand_followup_fires_for_dual_attack(tmp_path, monkeypatch):
    from app.services import combat_service as cs
    monkeypatch.setattr(cs, "COMBAT_DB_PATH", _combat_db(tmp_path))
    monkeypatch.setattr(cs, "player_dual_combo_for_character",
                        lambda conn, ch_id, sheet: ("dual_attack", _DAGGER_ROW, _DAGGER_ROW))
    monkeypatch.setattr(cs, "roll_d20", lambda: 13)
    spy = {}
    def _fake_resolve(campaign_id, roll_result, **kw):
        spy["campaign_id"] = campaign_id
        spy["kw"] = kw
        return {"hit": True, "combat_state": {"status": "active"}}
    monkeypatch.setattr(cs, "resolve_attack", _fake_resolve)

    out = cs.resolve_offhand_followup(1)
    assert out is not None
    assert spy["kw"]["attacker"] == "player"
    assert spy["kw"]["weapon_override"] == _DAGGER_ROW   # off-hand wymuszony
    assert spy["kw"]["raw_d20"] == 13


def test_offhand_followup_skipped_when_not_dual(tmp_path, monkeypatch):
    from app.services import combat_service as cs
    monkeypatch.setattr(cs, "COMBAT_DB_PATH", _combat_db(tmp_path))
    monkeypatch.setattr(cs, "player_dual_combo_for_character",
                        lambda conn, ch_id, sheet: ("parry", _DAGGER_ROW, _DAGGER_ROW))
    called = {"n": 0}
    monkeypatch.setattr(cs, "resolve_attack", lambda *a, **k: called.__setitem__("n", called["n"] + 1))

    assert cs.resolve_offhand_followup(1) is None
    assert called["n"] == 0   # parry → BRAK drugiego ataku


def test_offhand_followup_skipped_when_no_living_enemy(tmp_path, monkeypatch):
    import json as _json
    from app.services import combat_service as cs
    db = _combat_db(tmp_path)
    # zabij jedynego wroga
    conn = sqlite3.connect(db)
    dead = _json.dumps([
        {"id": "player", "type": "player", "hp_current": 20, "hp_max": 20},
        {"id": "bandit_01", "type": "enemy", "hp_current": 0, "hp_max": 12, "dead": True},
    ])
    conn.execute("UPDATE active_combat SET combatants = ? WHERE campaign_id = 1", (dead,))
    conn.commit(); conn.close()
    monkeypatch.setattr(cs, "COMBAT_DB_PATH", db)
    monkeypatch.setattr(cs, "player_dual_combo_for_character",
                        lambda conn, ch_id, sheet: ("dual_attack", _DAGGER_ROW, _DAGGER_ROW))
    called = {"n": 0}
    monkeypatch.setattr(cs, "resolve_attack", lambda *a, **k: called.__setitem__("n", called["n"] + 1))

    assert cs.resolve_offhand_followup(1) is None
    assert called["n"] == 0   # walka rozstrzygnięta → brak off-hand
