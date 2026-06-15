"""TDD: Issue #648 (B6) — Seed czarów maga Faza 1 do game_config_spells.

Kontrakt seeda: 16 czarów adoptowalnych dziś (atak single-target / heal-self /
self-buff obronny / kondycje mapowane na ISTNIEJĄCE stany FAZY S). Bez zmian
schematu. Brak aoe/summon/ally w zaseedowanym zbiorze. effect_type każdego
czaru-kondycji = klucz istniejący w game_config_conditions (reużycie, zero duplikatu).
"""
import sqlite3
import pytest

import app.services.spell_service as spell_service

DB_PATH = "/data/ai_gm.db"

# ── Kanoniczny zbiór B6 (źródło: rpg_spells_design_doc.md, CZĘŚĆ AK.4) ──────────
# (key, tier, mana_cost, spell_type, damage_die, heal_die, effect_type)
B6_SPELLS = [
    # atak single-target
    ("fire_bolt",       1, 2, "attack",    "1d8", None, None),
    ("frost_bolt",      1, 2, "attack",    "1d8", None, None),
    ("acid_splash",     1, 1, "attack",    "1d6", None, None),
    ("lightning_arrow", 2, 3, "attack",    "2d6", None, None),
    ("ice_lance",       2, 3, "attack",    "2d8", None, None),
    ("inferno_strike",  3, 4, "attack",    "3d6", None, None),
    # heal self
    ("minor_heal",      1, 1, "heal",      None, "1d6", None),
    # self-buff obronny
    ("ward_of_iron",    1, 2, "defense",   None, None, None),
    ("mage_armor",      2, 3, "defense",   None, None, None),
    # kondycje (mapowane na FAZA S)
    ("frost_grip",      1, 2, "effect",    None, None, "slowed"),
    ("hex",             2, 2, "effect",    None, None, "cursed"),
    ("poison_touch",    2, 2, "effect",    "1d4", None, "poisoned"),
    ("blind",           2, 3, "effect",    None, None, "blinded"),
    ("confusion",       3, 3, "effect",    None, None, "confused"),
    ("stun_bolt",       4, 4, "effect",    "1d6", None, "stunned"),
    # narrative self (potrzebny startowemu zestawowi B8)
    ("detect_magic",    1, 1, "narrative", None, None, None),
]

B6_KEYS = [s[0] for s in B6_SPELLS]


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


# ─── Test główny: wszystkie 16 czarów B6 zaseedowane z poprawnymi wartościami ──

@pytest.mark.parametrize("key,tier,mana,stype,dmg,heal,effect", B6_SPELLS)
def test_b6_spell_seeded(key, tier, mana, stype, dmg, heal, effect):
    """Każdy czar B6 istnieje w game_config_spells z wartościami z docu."""
    spell = spell_service.get_spell(key)
    assert spell is not None, f"Czar '{key}' nie zaseedowany"
    assert int(spell["tier"]) == tier, f"{key}: tier {spell['tier']} != {tier}"
    assert int(spell["mana_cost"]) == mana, f"{key}: mana {spell['mana_cost']} != {mana}"
    assert spell["spell_type"] == stype, f"{key}: type {spell['spell_type']} != {stype}"
    assert (spell["damage_die"] or None) == dmg, f"{key}: dmg {spell['damage_die']} != {dmg}"
    assert (spell["heal_die"] or None) == heal, f"{key}: heal {spell['heal_die']} != {heal}"
    assert (spell["effect_type"] or None) == effect, f"{key}: effect {spell['effect_type']} != {effect}"


# ─── Kondycje reużywają FAZY S (zero duplikatu stanu) ─────────────────────────

def test_b6_effect_types_are_existing_conditions():
    """effect_type każdego czaru-kondycji = klucz w game_config_conditions."""
    conn = _conn()
    try:
        valid = {r["key"] for r in conn.execute("SELECT key FROM game_config_conditions").fetchall()}
    finally:
        conn.close()
    for key, *_rest, effect in B6_SPELLS:
        if effect is not None:
            assert effect in valid, f"{key}: kondycja '{effect}' nie istnieje w FAZA S"


# ─── Zakres B6: brak aoe / summon / ally w zaseedowanym zbiorze ────────────────

def test_b6_no_aoe_or_summon_in_set():
    """Żaden czar B6 nie jest attack_aoe ani summon (te → B11 / Blok 3)."""
    for key in B6_KEYS:
        spell = spell_service.get_spell(key)
        assert spell is not None, f"Czar '{key}' nie zaseedowany"
        assert int(spell.get("aoe") or 0) == 0, f"{key}: aoe=1 poza zakresem B6"
        assert spell["spell_type"] not in ("attack_aoe", "summon"), \
            f"{key}: type {spell['spell_type']} poza zakresem B6"


# ─── Backward compat: oryginalne 10 czarów (Task 26) nietknięte ───────────────

def test_legacy_spells_still_present():
    """Czary z Task 26 nadal istnieją bez zmian (zero regresji)."""
    for key in ("magic_bolt", "mend_wounds", "arcane_shield", "sleep",
                "burning_arc", "drain_life", "chain_lightning", "stone_skin",
                "fireball", "magic_light"):
        assert spell_service.get_spell(key) is not None, f"Legacy czar '{key}' zniknął"
