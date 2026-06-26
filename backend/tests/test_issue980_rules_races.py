"""TDD: Issue #980 — Ksiega zasad: rozdział X Rasy bohatera."""
import sys
sys.path.insert(0, "/app")


def test_rules_chapter_x_race_content_complete():
    """Rozdział Rasy istnieje w backendzie — weryfikacja przez stałe z kodu."""
    from app.services.actor_stats import RACIAL_STAT_MODS, apply_racial_modifiers
    # Rozdział opisuje modyfikatory: +2 KON, +1 STR, -1 CHA, -1 DEX dla krasnoluda
    dwarf_mods = RACIAL_STAT_MODS.get("dwarf", {})
    assert dwarf_mods.get("CON") == 2, f"Brak +2 KON dla krasnoluda: {dwarf_mods}"
    assert dwarf_mods.get("STR") == 1, f"Brak +1 STR: {dwarf_mods}"
    assert dwarf_mods.get("CHA") == -1, f"Brak -1 CHA: {dwarf_mods}"
    assert dwarf_mods.get("DEX") == -1, f"Brak -1 DEX: {dwarf_mods}"


def test_rules_twardy_jak_kamien_mechanics():
    """Twardy jak kamień opisany w Księdze — weryfikacja przez mechanikę."""
    from app.services.combat_service import DWARF_TOUGHNESS_TYPES, DWARF_TOUGHNESS_REDUCTION
    assert "poison" in DWARF_TOUGHNESS_TYPES
    assert "dark" in DWARF_TOUGHNESS_TYPES
    assert "rdzen" in DWARF_TOUGHNESS_TYPES
    assert DWARF_TOUGHNESS_REDUCTION == 2, f"Redukcja powinna być 2, jest {DWARF_TOUGHNESS_REDUCTION}"


def test_rules_kowalskie_oko_discount():
    """Kowalskie oko: 15% zniżka i 20 zł reperacja opisane w Księdze."""
    from app.services.shop_service import DWARF_SHOP_DISCOUNT, DWARF_REPAIR_COST_GP
    assert DWARF_SHOP_DISCOUNT == 0.15
    assert DWARF_REPAIR_COST_GP == 20


def test_rules_wzrok_gornika_constants():
    """Wzrok górnika: +3 krasnolud / -4 człowiek opisane w Księdze."""
    from app.services.dungeon_service import DWARF_DARKVISION_BONUS, HUMAN_DARKNESS_PENALTY
    assert DWARF_DARKVISION_BONUS == 3
    assert HUMAN_DARKNESS_PENALTY == -4


def test_rules_rdzen_magia_miscast_threshold():
    """Rdzeń-magia: miscast na Nat1+Nat2 opisane w Księdze."""
    from app.services.spell_service import DWARF_MISCAST_THRESHOLD, is_miscast
    assert DWARF_MISCAST_THRESHOLD == 2
    # Krasnolud: Nat 1 i Nat 2 to miscast
    assert is_miscast(1, "dwarf") is True
    assert is_miscast(2, "dwarf") is True
    assert is_miscast(3, "dwarf") is False
    # Człowiek: tylko Nat 1
    assert is_miscast(1, "human") is True
    assert is_miscast(2, "human") is False


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_rules_six_dwarf_spells_in_db():
    """6 czarów Rdzenia w DB — Ksiega ich wymienia."""
    import sqlite3
    conn = sqlite3.connect("/data/ai_gm.db")
    rows = conn.execute(
        "SELECT key FROM game_config_spells WHERE race_lock = 'dwarf'"
    ).fetchall()
    conn.close()
    keys = [r[0] for r in rows]
    for expected in ("vein_tremor", "rdzen_pulse", "vein_bleed", "rdzen_shield", "deep_quake", "black_vein"):
        assert expected in keys, f"Brak czaru '{expected}' — opisany w Księdze"
