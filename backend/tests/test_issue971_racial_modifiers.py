"""TDD: Issue #971 — warstwa modyfikatorów rasowych (staty + HP)."""
import sys
sys.path.insert(0, "/app")

from app.services.actor_stats import apply_racial_modifiers


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_dwarf_gets_racial_stat_bonuses():
    """Krasnolud: CON+2, STR+1, CHA−1, DEX−1."""
    sheet = {"stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10, "LCK": 10}}
    result = apply_racial_modifiers(sheet, "dwarf")
    s = result["stats"]
    assert s["CON"] == 12, f"CON powinno być 12, jest {s['CON']}"
    assert s["STR"] == 11, f"STR powinno być 11, jest {s['STR']}"
    assert s["CHA"] == 9,  f"CHA powinno być 9, jest {s['CHA']}"
    assert s["DEX"] == 9,  f"DEX powinno być 9, jest {s['DEX']}"
    assert s["INT"] == 10  # bez zmiany
    assert s["WIS"] == 10  # bez zmiany


def test_dwarf_hp_recalculated_after_racial_mods():
    """Krasnolud-Wojownik lvl1: HP wyższe niż Człowiek-Wojownik dzięki CON+2."""
    from app.services.vitality_service import calculate_hp
    # Człowiek wojownik CON=11 (10+1 archetype) → mod=0
    human_sheet = {"stats": {"CON": 11}, "archetype": "warrior"}
    human_mods = apply_racial_modifiers(human_sheet, "human")
    human_hp = calculate_hp("warrior", human_mods["stats"]["CON"], 1)

    # Krasnolud wojownik CON=11+2=13 → mod=+1
    dwarf_sheet = {"stats": {"CON": 11}, "archetype": "warrior"}
    dwarf_mods = apply_racial_modifiers(dwarf_sheet, "dwarf")
    dwarf_hp = calculate_hp("warrior", dwarf_mods["stats"]["CON"], 1)

    assert dwarf_hp > human_hp, (
        f"Krasnolud powinien mieć więcej HP niż człowiek: {dwarf_hp} <= {human_hp}"
    )


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_human_race_no_modifiers():
    """Człowiek: żadne staty się nie zmieniają."""
    sheet = {"stats": {"STR": 12, "DEX": 14, "CON": 10, "INT": 13, "WIS": 11, "CHA": 15, "LCK": 10}}
    original = dict(sheet["stats"])
    result = apply_racial_modifiers(sheet, "human")
    assert result["stats"] == original, "Człowiek nie powinien mieć modyfikatorów rasowych"


def test_unknown_race_defaults_to_human():
    """Nieznana rasa traktowana jak człowiek (brak modów)."""
    sheet = {"stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10, "LCK": 10}}
    result = apply_racial_modifiers(sheet, "elf")
    assert result["stats"]["CON"] == 10, "Nieznana rasa nie powinna zmieniać statów"
