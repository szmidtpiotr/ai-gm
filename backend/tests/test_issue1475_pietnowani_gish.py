"""Issue #1475 PN-2 — Wojownik-Mag (gish): nowy archetyp Piętnowanych.

Zakres:
  * HP baza 8 (między Wojownikiem 10 a Uczonym 6),
  * mana połowiczna: 4 + (INT_mod × level) // 2,
  * gish liczy się jako CASTER (rzuca czary, ma manę),
  * gish jest EKSKLUZYWNY dla Piętnowanych — inne rasy mają go zamkniętego,
  * odwrócenie bonusu gisha (STR+1/INT+1/CON+1) przy odzysku baz (#1520),
  * bramka czarów: tier ≤ 2 (learn), rank ≤ 2 (upgrade).

Bramka broni jednoręcznej (equip_item) i pełny przebieg walki = smoke/PN-4.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.characters import _core_bases_from_stored_stats
from app.services import race_start_service as rss
from app.services import spell_service
from app.services.vitality_service import (
    calculate_hp,
    calculate_mana,
    is_caster,
)


# ─── Wital: HP i mana gisha ──────────────────────────────────────────────────

def test_gish_hp_base_between_warrior_and_scholar():
    # CON 12 (mod +1), L1 → 8 + 1 = 9. Wojownik 11, Uczony 7.
    assert calculate_hp("wojownik_mag", 12, 1) == 9
    assert calculate_hp("warrior", 12, 1) == 11
    assert calculate_hp("scholar", 12, 1) == 7


def test_gish_mana_is_half_scholar_formula():
    # INT 14 (mod +2), L1 → 4 + (2×1)//2 = 5. Uczony 8 + 2 = 10.
    assert calculate_mana("wojownik_mag", 14, 1) == 5
    assert calculate_mana("scholar", 14, 1) == 10
    # L4: gish 4 + (2×4)//2 = 8; Uczony 8 + 8 = 16.
    assert calculate_mana("wojownik_mag", 14, 4) == 8
    assert calculate_mana("scholar", 14, 4) == 16


def test_gish_mana_never_below_one():
    assert calculate_mana("wojownik_mag", 6, 1) >= 1  # INT 6 → ujemny mod, floor 1


def test_gish_is_caster_warrior_is_not():
    assert is_caster("wojownik_mag") is True
    assert is_caster("scholar") is True
    assert is_caster("warrior") is False
    assert is_caster("rogue") is False


# ─── Bramka archetypu: gish tylko dla Piętnowanych ───────────────────────────

def test_gish_locked_for_all_but_pietnowani():
    for race in ("human", "dwarf", "elf"):
        assert rss.archetype_allowed(race, "wojownik_mag") is False
        assert "Piętnowanych" in (rss.archetype_block_reason(race, "wojownik_mag") or "")
    assert rss.archetype_allowed("pietnowani", "wojownik_mag") is True


def test_pietnowani_allowed_paths_are_scholar_and_gish():
    blocked = rss.blocked_archetypes_for_race("pietnowani")
    assert set(blocked) == {"warrior", "rogue"}
    assert rss.archetype_allowed("pietnowani", "scholar") is True
    assert rss.archetype_allowed("pietnowani", "wojownik_mag") is True


# ─── Odwrócenie bonusu gisha (#1520 path-independent bazy) ────────────────────

def test_gish_bonus_is_reversed_on_base_recovery():
    # Stored = rzut + gish (+1 STR/+1 INT/+1 CON) + rasa Piętnowani (INT+2/WIS+1/CON−1).
    stored = {"STR": 13, "DEX": 10, "CON": 12, "INT": 15, "WIS": 11, "CHA": 10, "LCK": 10}
    bases = _core_bases_from_stored_stats(stored, "wojownik_mag", "pietnowani")
    # STR: 13 − 1(gish) − 0(rasa) = 12
    assert bases["STR"] == 12
    # INT: 15 − 1(gish) − 2(rasa) = 12
    assert bases["INT"] == 12
    # CON: 12 − 1(gish) − (−1)(rasa) = 12
    assert bases["CON"] == 12
    # WIS: 11 − 0(gish) − 1(rasa) = 10
    assert bases["WIS"] == 10


# ─── Bramka czarów gisha: tier ≤ 2, rank ≤ 2 ─────────────────────────────────

def test_gish_spell_caps_constants():
    assert spell_service.GISH_MAX_SPELL_TIER == 2
    assert spell_service.GISH_MAX_SPELL_RANK == 2


def _spell_db(archetype: str) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE characters (id INTEGER PRIMARY KEY, race TEXT, sheet_json TEXT)")
    conn.execute("CREATE TABLE character_spells (character_id INTEGER, spell_key TEXT, rank INTEGER, learned_at_level INTEGER)")
    conn.execute("CREATE TABLE game_config_spells (key TEXT PRIMARY KEY, label TEXT, tier INTEGER, race_lock TEXT)")
    import json
    # Poziom 9, żeby bramka poziomu (max_tier=ceil(9/2)=5) NIE była ograniczeniem —
    # ograniczać ma wyłącznie cap gisha.
    sheet = json.dumps({"level": 9, "archetype": archetype})
    conn.execute("INSERT INTO characters (id, race, sheet_json) VALUES (1, 'pietnowani', ?)", (sheet,))
    conn.execute("INSERT INTO game_config_spells (key, label, tier, race_lock) VALUES ('t1_bolt','Iskra T1',1,'pietnowani')")
    conn.execute("INSERT INTO game_config_spells (key, label, tier, race_lock) VALUES ('t2_ward','Tarcza T2',2,'pietnowani')")
    conn.execute("INSERT INTO game_config_spells (key, label, tier, race_lock) VALUES ('t3_storm','Burza T3',3,'pietnowani')")
    conn.commit()
    return conn


def test_gish_can_learn_tier_1_and_2():
    conn = _spell_db("wojownik_mag")
    try:
        assert spell_service.learn_spell(1, "t1_bolt", conn=conn)["rank"] == 1
        assert spell_service.learn_spell(1, "t2_ward", conn=conn)["rank"] == 1
    finally:
        conn.close()


def test_gish_cannot_learn_tier_3():
    conn = _spell_db("wojownik_mag")
    try:
        with pytest.raises(ValueError, match="tier 1–2"):
            spell_service.learn_spell(1, "t3_storm", conn=conn)
    finally:
        conn.close()


def test_scholar_can_learn_tier_3():
    """Kontrola: Uczony (pełny mag) nie ma capa gisha."""
    conn = _spell_db("scholar")
    try:
        assert spell_service.learn_spell(1, "t3_storm", conn=conn)["rank"] == 1
    finally:
        conn.close()


def test_gish_cannot_upgrade_past_rank_2():
    conn = _spell_db("wojownik_mag")
    try:
        spell_service.learn_spell(1, "t1_bolt", conn=conn)          # R1
        assert spell_service.upgrade_spell(1, "t1_bolt", conn=conn)["rank"] == 2  # R2 OK
        with pytest.raises(ValueError, match="R2"):
            spell_service.upgrade_spell(1, "t1_bolt", conn=conn)     # R3 zablokowane
    finally:
        conn.close()
