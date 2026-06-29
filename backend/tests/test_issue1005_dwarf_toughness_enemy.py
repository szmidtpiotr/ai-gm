"""TDD: Issue #1005 — przynajmniej 1 wróg w DB ma damage_type w DWARF_TOUGHNESS_TYPES.

Mechanic Krasnoludowej Toughness ('Twardy jak kamień') istnieje w combat_service.py,
ale bez wroga z kwalifikującym damage_type nigdy się nie aktywuje w rozgrywce.
"""
import sqlite3
import sys

sys.path.insert(0, "/app")

DB_PATH = "/data/ai_gm.db"
DWARF_TOUGHNESS_TYPES = ("poison", "dark", "rdzen")


def test_at_least_one_enemy_with_qualifying_damage_type():
    """Co najmniej 1 wróg w DB musi mieć damage_type w {poison, dark, rdzen}."""
    conn = sqlite3.connect(DB_PATH)
    try:
        placeholders = ",".join(f"'{t}'" for t in DWARF_TOUGHNESS_TYPES)
        row = conn.execute(
            f"SELECT COUNT(*) FROM game_config_enemies WHERE damage_type IN ({placeholders}) AND is_active = 1"
        ).fetchone()
        count = row[0]
    finally:
        conn.close()

    assert count >= 1, (
        f"Brak aktywnego wroga z damage_type IN {DWARF_TOUGHNESS_TYPES}. "
        f"Mechanic 'Twardy jak kamień' jest nieosiągalny w normalnej rozgrywce. "
        f"Dodaj np. giant_spider z damage_type='poison'."
    )


def test_giant_spider_has_poison_damage_type():
    """giant_spider powinien mieć damage_type='poison' (tematycznie pająk = trucizna)."""
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT damage_type FROM game_config_enemies WHERE key = 'giant_spider'"
        ).fetchone()
    finally:
        conn.close()

    assert row is not None, "Wróg 'giant_spider' nie istnieje w DB"
    assert row[0] == "poison", (
        f"giant_spider.damage_type = '{row[0]}', oczekiwano 'poison'. "
        f"Aktualizacja wymagana przez #1005."
    )


def test_dwarf_toughness_types_constant_intact():
    """Backward compat: stałe DWARF_TOUGHNESS_TYPES i DWARF_TOUGHNESS_REDUCTION niezmienione."""
    from app.services.combat_service import DWARF_TOUGHNESS_REDUCTION, DWARF_TOUGHNESS_TYPES

    assert "poison" in DWARF_TOUGHNESS_TYPES
    assert "dark" in DWARF_TOUGHNESS_TYPES
    assert "rdzen" in DWARF_TOUGHNESS_TYPES
    assert DWARF_TOUGHNESS_REDUCTION == 2
