"""TDD: Issue #653 — heal spell out of combat must return dice roll data for frontend viz."""
import sys, os, json, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ─── helpers ─────────────────────────────────────────────────────────────────

def _make_scholar_sheet(hp=30, max_hp=30, mana=10, int_stat=14):
    return {
        "archetype": "scholar",
        "current_hp": hp,
        "max_hp": max_hp,
        "current_mana": mana,
        "stats": {"STR": 8, "DEX": 10, "CON": 12, "INT": int_stat, "WIS": 12, "CHA": 10, "LCK": 10},
        "conditions": [],
    }


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_mend_wounds_response_contains_heal_dice():
    """#653: heal spell response must include heal_die, heal_rolls, heal_modifier for frontend dice animation."""
    from app.services.spell_service import resolve_mend_wounds
    spell_stats = {"heal_die": "2d6", "mana_cost": 2}
    sheet = _make_scholar_sheet(hp=10, mana=10, int_stat=14)  # INT 14 → mod +2

    result = resolve_mend_wounds(sheet, spell_stats)

    # Must have die notation
    assert "heal_die" in result, "heal_die missing from response (#653)"
    assert result["heal_die"] == "2d6", f"Expected heal_die='2d6', got {result['heal_die']!r}"

    # Must have per-die rolls list (for 3D dice to land on)
    assert "heal_rolls" in result, "heal_rolls missing from response (#653)"
    assert isinstance(result["heal_rolls"], list), "heal_rolls must be a list"
    assert len(result["heal_rolls"]) == 2, f"2d6 → expect 2 rolls, got {result['heal_rolls']}"
    for r in result["heal_rolls"]:
        assert 1 <= r <= 6, f"Each d6 roll must be 1-6, got {r}"

    # Must have modifier
    assert "heal_modifier" in result, "heal_modifier missing from response (#653)"
    assert result["heal_modifier"] == 2, f"INT 14 → mod +2, got {result['heal_modifier']}"

    # Must have correct total (sum of rolls + modifier)
    expected_total = sum(result["heal_rolls"]) + result["heal_modifier"]
    assert result["healed"] == expected_total, f"healed mismatch: {result['healed']} != {expected_total}"


def test_mend_wounds_response_has_outcome_heal():
    """#653: spell_type heal response must have outcome='heal' for frontend branch logic."""
    from app.services.spell_service import resolve_mend_wounds
    sheet = _make_scholar_sheet(hp=5, mana=10, int_stat=10)  # INT 10 → mod 0
    result = resolve_mend_wounds(sheet, {"heal_die": "1d6"})

    assert result.get("outcome") == "heal", f"Expected outcome='heal', got {result.get('outcome')!r}"


def test_heal_capped_at_max_hp():
    """#653: hp_after capped at max_hp; heal_rolls still present for dice animation."""
    from app.services.spell_service import resolve_mend_wounds
    sheet = _make_scholar_sheet(hp=29, max_hp=30, mana=10, int_stat=10)  # 1 below max
    result = resolve_mend_wounds(sheet, {"heal_die": "2d6"})

    assert result["hp_after"] <= 30, "hp_after must not exceed max_hp"
    # healed = raw roll (not capped); animation always shows what was rolled
    assert result["healed"] >= 0
    # dice rolls still present even when overheal happens
    assert "heal_rolls" in result and len(result["heal_rolls"]) == 2


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_defense_spell_has_no_heal_dice():
    """#653: defense spell cast OOC must NOT include heal_rolls/heal_die/heal_modifier."""
    from unittest.mock import patch, MagicMock

    sheet = _make_scholar_sheet()
    defense_spell = {
        "key": "ward_of_iron", "label": "Tarcza Żelazna",
        "spell_type": "defense", "tier": 2,
        "base_mana_cost": 0, "base_damage_die": None, "base_heal_die": None,
        "r1_mana_cost": 0, "r2_mana_cost": 0, "r3_mana_cost": 0,
        "r1_damage_die": None, "r2_damage_die": None, "r3_damage_die": None,
        "r1_heal_die": None, "r2_heal_die": None, "r3_heal_die": None,
        "description": "Tarcza ochronna",
    }

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = {
        "sheet_json": json.dumps(sheet)
    }

    with patch("app.services.spell_service._get_db", return_value=mock_conn), \
         patch("app.services.spell_service.get_character_spell",
               return_value={"spell_key": "ward_of_iron", "rank": 1}), \
         patch("app.services.spell_service.get_spell", return_value=defense_spell), \
         patch("app.services.spell_service.get_spell_stats_at_rank",
               return_value={"mana_cost": 0}), \
         patch("app.services.spell_service.record_spell_use"):

        from app.services.spell_service import cast_spell_out_of_combat
        result = cast_spell_out_of_combat(1, "ward_of_iron")

    assert "heal_rolls" not in result, f"defense response must not have heal_rolls, got: {result}"
    assert "heal_die" not in result, f"defense response must not have heal_die, got: {result}"
    assert "heal_modifier" not in result, f"defense response must not have heal_modifier, got: {result}"
    assert result.get("outcome") == "defense"
