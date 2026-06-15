"""TDD: Issue #652 (B7) — tier-gating nauki czarów + model trafienia (pojedynek na stat obrony).

Decyzja D-spell (game_mechanics.md CZĘŚĆ AK.6): atak czaru bez zmian; czary nie-atakujące =
pojedynek INT_mag vs stat obrony celu (WIS umysł / CON ciało); zwrot ½ many przy oporze.
Tier → bramka nauki max_tier=ceil(level/2). Waluta = XP (arcane_points martwe).
"""
import json
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import spell_service


# ─── max_spell_tier_for_level: bramka tieru wg poziomu ───────────────────────

@pytest.mark.parametrize("level,expected_max_tier", [
    (1, 1), (2, 1), (3, 2), (4, 2), (5, 3), (6, 3), (7, 4), (10, 5),
])
def test_max_spell_tier_for_level(level, expected_max_tier):
    assert spell_service.max_spell_tier_for_level(level) == expected_max_tier


# ─── spell_save_stat: kondycja → stat obrony ─────────────────────────────────

@pytest.mark.parametrize("cond,stat", [
    ("confused", "WIS"), ("cursed", "WIS"), ("blinded", "WIS"), ("charmed", "WIS"),
    ("slowed", "CON"), ("frozen", "CON"), ("stunned", "CON"), ("poisoned", "CON"),
    ("nieznana_kondycja", "CON"),  # fallback ciało
])
def test_spell_save_stat(cond, stat):
    assert spell_service.spell_save_stat(cond) == stat


# ─── resolve_spell_opposed_save: pojedynek na właściwy stat ──────────────────

class _FakeRng:
    """Zwraca kolejne wartości z listy dla randint — deterministyczne testy."""
    def __init__(self, values):
        self._values = list(values)
    def randint(self, a, b):
        return self._values.pop(0)


def test_opposed_save_lands_on_dumb_target():
    """Mag INT 16 (+3) vs goblin-brute WIS 8 (-1): równe kości → mag wygrywa (landed)."""
    caster = {"stats": {"INT": 16}}
    target_stats = {"WIS": 8}
    rng = _FakeRng([10, 10])  # caster d20=10, target d20=10
    res = spell_service.resolve_spell_opposed_save(caster, target_stats, "confused", rng=rng)
    assert res["save_stat"] == "WIS"
    assert res["caster_total"] == 13  # 10 + 3
    assert res["target_total"] == 9   # 10 - 1
    assert res["landed"] is True


def test_opposed_save_resisted_by_strong_mind():
    """Mag INT 12 (+1) vs caster WIS 16 (+3): równe kości → cel się opiera."""
    caster = {"stats": {"INT": 12}}
    target_stats = {"WIS": 16}
    rng = _FakeRng([10, 10])
    res = spell_service.resolve_spell_opposed_save(caster, target_stats, "cursed", rng=rng)
    assert res["landed"] is False


def test_opposed_save_tie_goes_to_caster():
    """Remis totali → mag wygrywa (D-spell: remis dla rzucającego)."""
    caster = {"stats": {"INT": 10}}   # +0
    target_stats = {"CON": 10}        # +0
    rng = _FakeRng([12, 12])          # oba totale = 12
    res = spell_service.resolve_spell_opposed_save(caster, target_stats, "slowed", rng=rng)
    assert res["caster_total"] == res["target_total"] == 12
    assert res["landed"] is True


# ─── mana_refund_on_resist: zwrot połowy (floor) ─────────────────────────────

@pytest.mark.parametrize("cost,refund", [(4, 2), (3, 1), (2, 1), (1, 0), (0, 0)])
def test_mana_refund_on_resist(cost, refund):
    assert spell_service.mana_refund_on_resist(cost) == refund


# ─── learn_spell: bramka tieru wg poziomu (integracja na tymczasowej DB) ─────

@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "b7.db")
    conn = sqlite3.connect(db_file)
    conn.executescript(
        """
        CREATE TABLE game_config_spells (key TEXT PRIMARY KEY, label TEXT, tier INTEGER);
        CREATE TABLE character_spells (character_id INTEGER, spell_key TEXT, rank INTEGER,
            use_count INTEGER DEFAULT 0, learned_at_level INTEGER DEFAULT 1);
        CREATE TABLE characters (id INTEGER PRIMARY KEY, sheet_json TEXT);
        INSERT INTO game_config_spells (key, label, tier) VALUES
            ('fire_bolt', 'Ognista Strzała', 1),
            ('chain_lightning', 'Łańcuch Błyskawic', 4);
        INSERT INTO characters (id, sheet_json) VALUES
            (1, '{"level": 1, "archetype": "scholar"}'),
            (2, '{"level": 7, "archetype": "scholar"}');
        """
    )
    conn.commit()
    conn.close()

    def _fake_get_db():
        c = sqlite3.connect(db_file)
        c.row_factory = sqlite3.Row
        return c

    monkeypatch.setattr(spell_service, "_get_db", _fake_get_db)
    return db_file


def test_learn_spell_blocks_tier_above_level(temp_db):
    """L1 mag NIE może nauczyć się tier 4 (max_tier=1)."""
    with pytest.raises(ValueError):
        spell_service.learn_spell(1, "chain_lightning")


def test_learn_spell_allows_tier_within_level(temp_db):
    """L1 mag MOŻE nauczyć się tier 1."""
    res = spell_service.learn_spell(1, "fire_bolt")
    assert res["spell_key"] == "fire_bolt"
    assert res["rank"] == 1


def test_learn_spell_high_level_allows_high_tier(temp_db):
    """L7 mag (max_tier=4) MOŻE nauczyć się tier 4."""
    res = spell_service.learn_spell(2, "chain_lightning")
    assert res["spell_key"] == "chain_lightning"
