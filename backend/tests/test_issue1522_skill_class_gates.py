"""Issue #1522 — bramka umiejętności: archetyp + rasa.

Przed: jedna pula dla wszystkich. Rzut startowy losował z 18 kluczy (archetyp
wpływał tylko na wagę), a zamiana w kreatorze dopuszczała CAŁY katalog 43 skilli
— Zwiadowca bez many mógł wziąć Tarczę Many, Wojownik Arkanową Barierę.
"""

from __future__ import annotations

import random
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.character_creation_config import CREATION_SKILL_POOL, roll_creation_skills
from app.services.skill_access_service import (
    RACE_SKILL_UNLOCK,
    SKILL_ARCHETYPE_LOCK,
    blocked_skills_for,
    filter_allowed_skills,
    skill_allowed,
    skill_block_reason,
)

MAGIC = ("arcana", "arcane_ward", "mana_shield", "magic_sense")
HEAVY = ("shield_block", "two_handed", "wrestling")
THIEF = ("lockpick", "pickpocket", "disguise")


# ─── Reguła dostępu ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("key", MAGIC)
def test_magic_skills_are_scholar_only(key):
    assert skill_allowed(key, "scholar", "human")
    assert not skill_allowed(key, "rogue", "human")
    assert not skill_allowed(key, "warrior", "human")


@pytest.mark.parametrize("key", HEAVY)
def test_heavy_combat_is_warrior_only(key):
    assert skill_allowed(key, "warrior", "human")
    assert not skill_allowed(key, "scholar", "human")


@pytest.mark.parametrize("key", THIEF)
def test_thief_skills_are_rogue_only(key):
    assert skill_allowed(key, "rogue", "human")
    assert not skill_allowed(key, "warrior", "human")


def test_common_skills_open_to_everyone():
    for key in ("athletics", "dodge", "survival", "persuasion", "medicine", "alchemy"):
        for arch in ("warrior", "scholar", "rogue"):
            assert skill_allowed(key, arch, "human"), (key, arch)


# ─── Odblokowania rasowe ─────────────────────────────────────────────────────

def test_elf_reads_the_cracks_regardless_of_class():
    """Elf zna mapę pęknięć Rdzenia — Wyczucie Magii mimo braku many."""
    assert skill_allowed("magic_sense", "rogue", "elf")
    assert not skill_allowed("magic_sense", "rogue", "human")
    # ale reszta magii pozostaje zamknięta — elf-Zwiadowca nie rzuca zaklęć
    assert not skill_allowed("mana_shield", "rogue", "elf")
    assert not skill_allowed("arcana", "rogue", "elf")


def test_dwarf_grew_up_by_shield_and_anvil():
    assert skill_allowed("shield_block", "scholar", "dwarf")
    assert skill_allowed("two_handed", "scholar", "dwarf")
    assert not skill_allowed("shield_block", "scholar", "human")


def test_unlocks_reference_real_locks():
    """Odblokowanie skilla, którego nikt nie blokuje, byłoby martwym wpisem."""
    for race, keys in RACE_SKILL_UNLOCK.items():
        for k in keys:
            assert k in SKILL_ARCHETYPE_LOCK, (race, k)


def test_blocked_set_shrinks_with_race():
    assert "magic_sense" in blocked_skills_for("rogue", "human")
    assert "magic_sense" not in blocked_skills_for("rogue", "elf")


def test_block_reason_is_polish_and_names_the_class():
    reason = skill_block_reason("mana_shield", "rogue", "human")
    assert reason and "Uczony" in reason
    assert skill_block_reason("athletics", "rogue", "human") is None


# ─── Rzut startowy ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("archetype,race", [
    ("rogue", "human"), ("rogue", "elf"), ("warrior", "human"),
    ("warrior", "dwarf"), ("scholar", "human"), ("scholar", "dwarf"),
])
def test_rolled_skills_never_break_the_gate(archetype, race):
    """100 rzutów — żaden nie może przyznać zakazanego skilla."""
    for seed in range(100):
        ranks = roll_creation_skills(archetype, random.Random(seed), race=race)
        for key, rank in ranks.items():
            if rank > 0:
                assert skill_allowed(key, archetype, race), (seed, archetype, race, key)


def test_rogue_never_rolls_arcana():
    for seed in range(200):
        ranks = roll_creation_skills("rogue", random.Random(seed))
        assert int(ranks.get("arcana", 0)) == 0, seed


def test_scholar_can_still_roll_arcana():
    assert any(
        int(roll_creation_skills("scholar", random.Random(s)).get("arcana", 0)) > 0
        for s in range(50)
    )


def test_all_pool_keys_still_present_with_rank_zero():
    """Klucze spoza puli danej klasy zostają w arkuszu z rangą 0 (kompatybilność)."""
    ranks = roll_creation_skills("rogue", random.Random(1))
    assert set(ranks) == set(CREATION_SKILL_POOL)


def test_race_bias_does_not_unlock_anything():
    """Bias rasowy tylko podbija szansę — nie omija bramki."""
    for seed in range(50):
        ranks = roll_creation_skills("scholar", random.Random(seed), race="dwarf")
        for key, rank in ranks.items():
            if rank > 0:
                assert skill_allowed(key, "scholar", "dwarf"), (seed, key)


# ─── Filtr listy ─────────────────────────────────────────────────────────────

def test_filter_keeps_order_and_drops_blocked():
    keys = ["athletics", "mana_shield", "dodge", "lockpick", "survival"]
    assert filter_allowed_skills(keys, "warrior", "human") == [
        "athletics", "dodge", "survival",
    ]


# ─── Awans za XP ─────────────────────────────────────────────────────────────

def _xp_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE characters (id INTEGER PRIMARY KEY, race TEXT, sheet_json TEXT)"
    )
    conn.commit()
    return conn


def test_xp_gate_blocks_learning_but_not_ranking_up():
    """Postać sprzed bramki ma skill z rangą 1 — wolno rozwijać, nie wolno nauczyć nowego."""
    from app.services import xp_service

    import json
    conn = _xp_conn()
    try:
        sheet = {"archetype": "rogue", "skills": {"arcana": 1}, "xp_available": 999}
        conn.execute(
            "INSERT INTO characters (id, race, sheet_json) VALUES (1, 'human', ?)",
            (json.dumps(sheet),),
        )
        conn.commit()
        # nauka NOWEGO zakazanego skilla → blokada
        with pytest.raises(ValueError) as e:
            xp_service.spend_skill_rank_up(conn, 1, "mana_shield")
        assert "skill_locked_for_class" in str(e.value)
    finally:
        conn.close()
