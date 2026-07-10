"""#1302 — passive relic effects: stats/AC/skills from equipped relics, in AND out
of combat, plus the character card. Unit-level coverage of the single chokepoint
(equipment_effects_service), the skill-test modifier fold-in, and the Forge
item-signature effect_json generation."""
import json
import sqlite3

import pytest

from app.services import equipment_effects_service as eq
from app.services.skill_service import calc_skill_modifier_info, _skill_stat
from app.routers.adventure_forge import _build_signature_effect_json


def _mk_conn(effects_by_slot: dict[str, list], weapons_by_slot: dict[str, list] | None = None) -> sqlite3.Connection:
    """In-memory DB with character 1 wearing the given items/weapons.

    effects_by_slot:  {slot: [effect dicts]} → one game_config_items row per slot.
    weapons_by_slot:  {slot: [effect dicts]} → one game_config_weapons row per slot.
    Only the config tables exist (no game_items), so the service's rich query hits
    OperationalError and falls back to the config-only path.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE game_config_items (key TEXT PRIMARY KEY, effect_json TEXT)")
    conn.execute("CREATE TABLE game_config_weapons (key TEXT PRIMARY KEY, effect_json TEXT)")
    conn.execute(
        "CREATE TABLE character_inventory (id INTEGER PRIMARY KEY, character_id INTEGER, "
        "item_key TEXT, weapon_key TEXT, game_item_key TEXT, equipped INTEGER, slot TEXT)"
    )
    i = 0
    for slot, effects in effects_by_slot.items():
        i += 1
        key = f"relic_{i}"
        conn.execute("INSERT INTO game_config_items (key, effect_json) VALUES (?, ?)",
                     (key, json.dumps({"schema_version": 1, "effects": effects})))
        conn.execute(
            "INSERT INTO character_inventory (character_id, item_key, weapon_key, game_item_key, equipped, slot) "
            "VALUES (1, ?, NULL, NULL, 1, ?)", (key, slot))
    for slot, effects in (weapons_by_slot or {}).items():
        i += 1
        key = f"weap_{i}"
        conn.execute("INSERT INTO game_config_weapons (key, effect_json) VALUES (?, ?)",
                     (key, json.dumps({"schema_version": 1, "effects": effects})))
        conn.execute(
            "INSERT INTO character_inventory (character_id, item_key, weapon_key, game_item_key, equipped, slot) "
            "VALUES (1, NULL, ?, NULL, 1, ?)", (key, slot))
    conn.commit()
    return conn


def test_no_relic_returns_empty():
    conn = _mk_conn({})
    b = eq.get_equipment_bonuses(1, conn)
    assert b == {"stats": {}, "skills": {}, "ac": 0}


def test_single_relic_stat_and_ac():
    conn = _mk_conn({"relic1": [
        {"type": "static_stat_modifier", "stat": "CHA", "value": 2},
        {"type": "ac_bonus", "value": 1},
    ]})
    b = eq.get_equipment_bonuses(1, conn)
    assert b["stats"] == {"CHA": 2}
    assert b["ac"] == 1


def test_two_relics_stack_sum():
    # Decision (Piotr): two +CHA relics SUM.
    conn = _mk_conn({
        "relic1": [{"type": "static_stat_modifier", "stat": "CHA", "value": 1}],
        "relic2": [{"type": "static_stat_modifier", "stat": "CHA", "value": 1}],
    })
    assert eq.get_equipment_bonuses(1, conn)["stats"] == {"CHA": 2}


def test_unequipped_relic_ignored():
    conn = _mk_conn({"relic1": [{"type": "static_stat_modifier", "stat": "STR", "value": 3}]})
    # Unequip it → bonus disappears everywhere.
    conn.execute("UPDATE character_inventory SET equipped = 0")
    conn.commit()
    assert eq.get_equipment_bonuses(1, conn)["stats"] == {}


def test_skill_modifier_folds_relic_stat():
    sheet = {"stats": {k: 12 for k in ("STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK")}, "skills": {}}
    skill = "persuasion"
    gov = _skill_stat(skill)  # governing stat for this skill
    base = calc_skill_modifier_info(sheet, skill)
    conn = _mk_conn({"relic1": [{"type": "static_stat_modifier", "stat": gov, "value": 2}]})
    info = calc_skill_modifier_info(sheet, skill, conn=conn, character_id=1)
    # 12 → 14 raises the modifier by exactly 1.
    assert info["stat_mod"] == base["stat_mod"] + 1
    assert info["equipment_bonus"] == 1
    assert info["total"] == base["total"] + 1


def test_skill_modifier_folds_relic_skill_rank():
    sheet = {"stats": {k: 10 for k in ("STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK")},
             "skills": {"persuasion": 0}}
    conn = _mk_conn({"relic1": [{"type": "static_skill_modifier", "skill": "persuasion", "value": 2}]})
    base = calc_skill_modifier_info(sheet, "persuasion")
    info = calc_skill_modifier_info(sheet, "persuasion", conn=conn, character_id=1)
    assert info["skill_rank"] == base["skill_rank"] + 2
    assert info["total"] == base["total"] + 2


def test_pure_when_no_conn():
    sheet = {"stats": {"CHA": 12}, "skills": {}}
    a = calc_skill_modifier_info(sheet, "persuasion")
    assert a.get("equipment_bonus", 0) == 0


def test_signature_item_effect_json_non_empty():
    # #1301 acceptance: item signature gets a non-empty passive effect_json.
    efx = _build_signature_effect_json("Relikt dodaje charyzmy w rozmowach", 4, "item")
    assert efx is not None
    parsed = json.loads(efx)
    types = {e["type"] for e in parsed["effects"]}
    assert "static_stat_modifier" in types
    assert any(e.get("stat") == "CHA" for e in parsed["effects"])


def test_signature_item_effect_json_defaults_ac():
    # Vague prose still yields a mechanical hook (ac_bonus fallback), never empty.
    efx = _build_signature_effect_json("tajemniczy artefakt", 5, "item")
    parsed = json.loads(efx)
    assert parsed["effects"]
    assert parsed["effects"][0]["value"] >= 1


def test_signature_consumable_still_none():
    assert _build_signature_effect_json("leczy", 4, "consumable") is None


# ── #1302 rozszerzenie (Piotr): każdy założony przedmiot, nie tylko relik ─────

def test_armor_slot_grants_stat_out_of_combat():
    # Piękna zbroja (slot torso) daje +CHA — poza walką też.
    conn = _mk_conn({"torso": [{"type": "static_stat_modifier", "stat": "CHA", "value": 2}]})
    assert eq.get_equipment_bonuses(1, conn)["stats"] == {"CHA": 2}


def test_weapon_slot_stat_read_and_excluded_in_combat():
    # Miecz +CHA (main_hand). Poza walką liczy się; w walce EXCLUDE main_hand (broń osobno).
    conn = _mk_conn({}, weapons_by_slot={"main_hand": [{"type": "static_stat_modifier", "stat": "CHA", "value": 2}]})
    assert eq.get_equipment_bonuses(1, conn)["stats"] == {"CHA": 2}
    assert eq.get_equipment_bonuses(1, conn, exclude_slots=("main_hand",))["stats"] == {}


def test_mixed_slots_sum_across_gear():
    conn = _mk_conn({
        "torso": [{"type": "static_stat_modifier", "stat": "CHA", "value": 1}],
        "relic1": [{"type": "static_stat_modifier", "stat": "CHA", "value": 1}, {"type": "ac_bonus", "value": 2}],
    })
    b = eq.get_equipment_bonuses(1, conn)
    assert b["stats"] == {"CHA": 2}
    assert b["ac"] == 2


def test_item_grants_skill_from_zero():
    # Magiczny wytrych nadaje lockpick nawet gdy postać nie ma tej umiejętności.
    conn = _mk_conn({"relic1": [{"type": "static_skill_modifier", "skill": "lockpick", "value": 2}]})
    sheet = {"stats": {k: 10 for k in ("STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK")}, "skills": {}}
    info = calc_skill_modifier_info(sheet, "lockpick", conn=conn, character_id=1)
    assert info["skill_rank"] == 2  # od zera
    assert info["total"] >= 2


def test_forge_item_maps_skill_from_prose():
    # Kuźnia: opis z wytrychem → static_skill_modifier lockpick.
    efx = _build_signature_effect_json("Magiczny wytrych otwierający każdy zamek", 4, "item")
    parsed = json.loads(efx)
    skills = [e for e in parsed["effects"] if e["type"] == "static_skill_modifier"]
    assert skills and skills[0]["skill"] == "lockpick"
