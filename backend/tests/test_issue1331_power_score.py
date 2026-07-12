"""BL-A5 (#1331) — Power Score + budżet spotkań f(power).

Rytuał końca sesji: goły bohater lvl 1 vs wyekwipowany lvl 5 — power WYRAŹNIE różny
przy tym samym systemie liczenia; budżet spotkania rośnie z power; wagi z meta stroją
wynik bez zmiany kodu.
"""
import json
import sqlite3

import pytest

from app.services.power_service import compute_power_score, get_power_weights
from app.services import encounter_service as enc


def _db() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE characters (id INTEGER PRIMARY KEY, sheet_json TEXT,
            campaign_id INTEGER, is_active INTEGER DEFAULT 1);
        CREATE TABLE character_inventory (id INTEGER PRIMARY KEY, character_id INTEGER,
            item_key TEXT, weapon_key TEXT, consumable_key TEXT, game_item_key TEXT,
            quantity INTEGER DEFAULT 1, equipped INTEGER DEFAULT 0, slot TEXT);
        CREATE TABLE game_config_weapons (key TEXT PRIMARY KEY, damage_die TEXT, effect_json TEXT);
        CREATE TABLE game_config_items (key TEXT PRIMARY KEY, ac_bonus INTEGER DEFAULT 0, effect_json TEXT);
        CREATE TABLE game_config_spells (key TEXT PRIMARY KEY, tier INTEGER);
        CREATE TABLE character_spells (character_id INTEGER, spell_key TEXT, rank INTEGER DEFAULT 1);
        CREATE TABLE game_config_meta (key TEXT PRIMARY KEY, value TEXT);
        """
    )
    return c


def _add_char(c, cid, level, skills=None):
    sheet = {"level": level, "skills": skills or {}, "archetype": "warrior"}
    c.execute("INSERT INTO characters (id, sheet_json) VALUES (?, ?)",
              (cid, json.dumps(sheet)))
    return sheet


# ── Acceptance: goły lvl1 vs wyekwipowany lvl5 ────────────────────────────────

def test_naked_lvl1_low_power():
    c = _db()
    sheet = _add_char(c, 1, 1)
    res = compute_power_score(c, 1, sheet)
    # Goły bohater: tylko poziom liczy się → power ≈ 1.
    assert res["score"] == pytest.approx(1.0, abs=0.01)
    assert res["breakdown"]["avg_weapon_damage"] == 0
    assert res["breakdown"]["armor_reduction"] == 0
    assert res["breakdown"]["max_spell_tier"] == 0


def test_equipped_lvl5_high_power():
    c = _db()
    sheet = _add_char(c, 1, 5, skills={"attack": 3, "dodge": 2, "two_handed": 1, "initiative": 2})
    c.execute("INSERT INTO game_config_weapons (key, damage_die) VALUES ('greatsword','2d6')")
    c.execute("INSERT INTO game_config_items (key, ac_bonus) VALUES ('plate', 4)")
    c.execute("INSERT INTO game_config_spells (key, tier) VALUES ('fireball', 3)")
    c.execute("INSERT INTO character_inventory (character_id, weapon_key, equipped, slot) "
              "VALUES (1,'greatsword',1,'main_hand')")
    c.execute("INSERT INTO character_inventory (character_id, item_key, equipped, slot) "
              "VALUES (1,'plate',1,'armor')")
    c.execute("INSERT INTO character_spells (character_id, spell_key, rank) VALUES (1,'fireball',1)")
    res = compute_power_score(c, 1, sheet)
    # 5 + 7/2 + 4 + 8/3 + 3 + 0 = 18.17
    assert res["score"] == pytest.approx(18.2, abs=0.1)
    bd = res["breakdown"]
    assert bd["avg_weapon_damage"] == pytest.approx(7.0)
    assert bd["armor_reduction"] == 4
    assert bd["combat_skill_ranks"] == 8
    assert bd["max_spell_tier"] == 3


def test_ritual_naked_vs_equipped_clearly_different():
    """Ten sam silnik — goły lvl1 ≪ wyekwipowany lvl5 (S4)."""
    c = _db()
    naked = compute_power_score(c, 1, _add_char(c, 1, 1))["score"]
    _add_char(c, 2, 5, skills={"attack": 3, "dodge": 2, "two_handed": 1, "initiative": 2})
    c.execute("INSERT INTO game_config_weapons (key, damage_die) VALUES ('gs','2d6')")
    c.execute("INSERT INTO game_config_items (key, ac_bonus) VALUES ('plate', 4)")
    c.execute("INSERT INTO game_config_spells (key, tier) VALUES ('fb', 3)")
    c.execute("INSERT INTO character_inventory (character_id, weapon_key, equipped, slot) "
              "VALUES (2,'gs',1,'main_hand')")
    c.execute("INSERT INTO character_inventory (character_id, item_key, equipped, slot) "
              "VALUES (2,'plate',1,'armor')")
    c.execute("INSERT INTO character_spells (character_id, spell_key) VALUES (2,'fb')")
    equipped = compute_power_score(c, 2, None)["score"]
    assert equipped > naked + 10        # różnica wyraźna, nie kosmetyczna
    assert equipped > naked * 3


# ── Wagi z meta stroją wynik bez zmiany kodu ─────────────────────────────────

def test_weights_from_meta_override():
    c = _db()
    sheet = _add_char(c, 1, 5)
    c.execute("INSERT INTO game_config_weapons (key, damage_die) VALUES ('gs','2d6')")
    c.execute("INSERT INTO character_inventory (character_id, weapon_key, equipped, slot) "
              "VALUES (1,'gs',1,'main_hand')")
    base = compute_power_score(c, 1, sheet)["score"]     # 5 + 3.5 = 8.5
    c.execute("INSERT INTO game_config_meta (key, value) VALUES "
              "('power_score_weights', ?)", (json.dumps({"weapon": 0}),))
    tuned = compute_power_score(c, 1, sheet)["score"]     # broń wyzerowana → 5.0
    assert base == pytest.approx(8.5, abs=0.1)
    assert tuned == pytest.approx(5.0, abs=0.1)
    assert get_power_weights(c)["weapon"] == 0.0


# ── Budżet spotkania rośnie z power ───────────────────────────────────────────

def test_threat_budget_scales_with_power():
    c = _db()
    b_low = enc.threat_budget_for_power(c, 1.0)
    b_high = enc.threat_budget_for_power(c, 18.0)
    assert b_high > b_low
    # power 1 daje ten sam budżet co poziom 1 (parytet ze starym f(level))
    assert b_low == pytest.approx(enc.threat_budget_for_level(c, 1), abs=0.01)


def test_composer_budget_uses_power_when_given():
    """encounter_composer z power → budżet f(power); większe power = grubszy budżet."""
    import random
    c = _db()
    c.executescript(
        """
        CREATE TABLE game_config_enemies (key TEXT PRIMARY KEY, label TEXT, hp_base INTEGER,
            ac_base INTEGER, attack_bonus INTEGER, damage_die TEXT, damage_bonus INTEGER,
            attacks_per_turn INTEGER, tier TEXT, min_level INTEGER, max_level INTEGER,
            terrain_tags TEXT, world_scope TEXT, review_status TEXT, is_active INTEGER);
        """
    )
    c.execute("INSERT INTO game_config_enemies VALUES "
              "('goblin','Goblin',8,12,1,'1d6',0,1,'weak',NULL,NULL,NULL,'global','permanent',1)")
    lo = enc.encounter_composer(c, level=5, hex_type=None, rng=random.Random(1), power=1.0)
    hi = enc.encounter_composer(c, level=5, hex_type=None, rng=random.Random(1), power=20.0)
    assert lo and hi
    assert hi["threat_budget"] > lo["threat_budget"]
    assert hi["power_score"] == 20.0
