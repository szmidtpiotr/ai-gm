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


def _mk_conn(effects_by_slot: dict[str, list]) -> sqlite3.Connection:
    """In-memory DB with character 1 wearing the given relics.

    effects_by_slot: {slot: [effect dicts]} → one game_config_items relic per slot,
    equipped in that slot. Only game_config_items exists (no game_items table), so the
    service's rich query hits OperationalError and falls back to the gci-only path.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE game_config_items (key TEXT PRIMARY KEY, effect_json TEXT)"
    )
    conn.execute(
        "CREATE TABLE character_inventory (id INTEGER PRIMARY KEY, character_id INTEGER, "
        "item_key TEXT, game_item_key TEXT, equipped INTEGER, slot TEXT)"
    )
    i = 0
    for slot, effects in effects_by_slot.items():
        i += 1
        key = f"relic_{i}"
        conn.execute(
            "INSERT INTO game_config_items (key, effect_json) VALUES (?, ?)",
            (key, json.dumps({"schema_version": 1, "effects": effects})),
        )
        conn.execute(
            "INSERT INTO character_inventory (character_id, item_key, game_item_key, equipped, slot) "
            "VALUES (1, ?, NULL, 1, ?)",
            (key, slot),
        )
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
