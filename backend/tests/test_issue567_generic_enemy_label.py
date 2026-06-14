"""TDD: Issue #567 — generic placeholder enemy never surfaces the literal "Wróg".

When combat resolves with the seed fallback enemy (`key='enemy'`, legacy `label='Wróg'`),
the roll-card identity must show a neutral Polish name ("Napastnik"), not "Wróg".
Real enemies keep their catalog label.
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import combat_service


def _conn_with_enemy(label: str, key: str) -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute(
        """CREATE TABLE game_config_enemies (
            key TEXT PRIMARY KEY, label TEXT, hp_base INT, ac_base INT,
            attack_bonus INT, damage_die TEXT, dex_modifier INT, skills_json TEXT,
            tier TEXT, loot_table_key TEXT, drop_chance REAL, xp_award INT
        )"""
    )
    c.execute(
        "INSERT INTO game_config_enemies (key, label, tier, xp_award) VALUES (?, ?, 'standard', 25)",
        (key, label),
    )
    c.commit()
    return c


def test_generic_enemy_never_shows_wrog():
    """Seed fallback (key='enemy', label='Wróg') → neutral name, not 'Wróg'."""
    c = _conn_with_enemy("Wróg", "enemy")
    _key, name = combat_service._roll_card_enemy_identity(
        c, {"enemy_key": "enemy", "name": "Wróg"}, "enemy_01"
    )
    assert name != "Wróg"
    assert name == "Napastnik"


def test_generic_label_variants_normalized():
    """Other generic placeholder labels also normalize away."""
    for lab in ("Wrog", "Enemy", "Przeciwnik"):
        c = _conn_with_enemy(lab, "enemy")
        _k, name = combat_service._roll_card_enemy_identity(
            c, {"enemy_key": "enemy", "name": lab}, "enemy_01"
        )
        assert name == "Napastnik", f"label {lab!r} not normalized"


def test_real_enemy_keeps_label():
    """A real catalog enemy keeps its proper label (backward compat)."""
    c = _conn_with_enemy("Goblin Szaman", "goblin_szaman")
    _key, name = combat_service._roll_card_enemy_identity(
        c, {"enemy_key": "goblin_szaman", "name": "Goblin Szaman"}, "goblin_szaman_01"
    )
    assert name == "Goblin Szaman"
