"""TDD: Issue #582 (S2) — Staty wrogów: stats_json + archetypy + seed heurystyką.

RED→GREEN: wróg dostaje 7 statów (STR..LCK) generowanych z archetypu po keywordach
klucza/etykiety (wzorzec jak `_default_zone_for_enemy`). Admin nadal tworzy wroga
4 liczbami; staty powstają same i można je nadpisać. Brak statów / NULL = default 10
(zero regresji combat).
"""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.services.actor_stats import (
    STAT_KEYS,
    archetype_for_actor,
    stats_for_actor,
    parse_stats_json,
    validate_stats_json,
)


# ─── Heurystyka archetypów (czysta, bez DB) ─────────────────────────────────

def test_seven_stat_keys():
    """7 statów dokładnie: STR, DEX, CON, INT, WIS, CHA, LCK."""
    assert STAT_KEYS == ["STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK"]


def test_archetype_brute():
    """Osiłek/bandyta → brute: STR wysokie, INT niskie."""
    assert archetype_for_actor("bandyta", "Bandyta") == "brute"
    s = stats_for_actor("bandyta", "Bandyta")
    assert s["STR"] == 16
    assert s["INT"] <= 8


def test_archetype_skirmisher():
    """Łucznik/archer → strzelec: DEX wysokie."""
    assert archetype_for_actor("goblin_lucznik", "Goblin Łucznik") == "skirmisher"
    assert stats_for_actor("goblin_lucznik", "Goblin Łucznik")["DEX"] == 15


def test_archetype_caster():
    """Mag/szaman → caster: INT+WIS wysokie, STR niskie."""
    assert archetype_for_actor("szaman_orkow", "Szaman Orków") == "caster"
    s = stats_for_actor("szaman_orkow", "Szaman Orków")
    assert s["INT"] == 14
    assert s["WIS"] == 14
    assert s["STR"] <= 8


def test_archetype_beast():
    """Wilk/bestia → beast: INT bardzo niskie."""
    assert archetype_for_actor("wilk_lesny", "Wilk Leśny") == "beast"
    assert stats_for_actor("wilk_lesny", "Wilk Leśny")["INT"] <= 3


def test_archetype_default_humanoid():
    """Brak rozpoznanego keywordu → humanoid-default: wszystko 10."""
    assert archetype_for_actor("zagadkowy_byt", "Zagadkowy Byt") == "humanoid"
    s = stats_for_actor("zagadkowy_byt", "Zagadkowy Byt")
    assert all(s[k] == 10 for k in STAT_KEYS)


def test_bandyta_lucznik_skirmisher_wins():
    """Acceptance: `bandyta_lucznik` ma DEX 15 — rola bojowa (strzelec) bije generyczne brute."""
    assert stats_for_actor("bandyta_lucznik", "Bandyta Łucznik")["DEX"] == 15


# ─── Parse / validate (NULL-fallback = default 10) ──────────────────────────

def test_parse_stats_null_fallback_all_10():
    """NULL / pusty stats_json → wszystkie staty 10 (zero regresji combat)."""
    for raw in (None, "", "null", "{}"):
        s = parse_stats_json(raw)
        assert all(s[k] == 10 for k in STAT_KEYS), raw


def test_parse_stats_fills_missing_keys_with_10():
    """Częściowy stats_json → brakujące staty uzupełnione 10."""
    s = parse_stats_json(json.dumps({"STR": 16}))
    assert s["STR"] == 16
    assert s["DEX"] == 10
    assert all(s[k] == 10 for k in STAT_KEYS if k != "STR")


def test_validate_stats_json_roundtrip():
    """validate zwraca JSON-string z 7 statami (int)."""
    out = validate_stats_json({"STR": 16, "dex": 12})
    parsed = json.loads(out)
    assert parsed["STR"] == 16
    assert parsed["DEX"] == 12


def test_validate_stats_json_none_returns_empty():
    """None → '{}' (oznacza: użyj archetypu / defaultu przy odczycie)."""
    assert validate_stats_json(None) == "{}"


# ─── DB: create_enemy auto-archetyp + override ──────────────────────────────

def test_create_enemy_auto_archetype_stats():
    """Tworząc wroga BEZ statów, dostaje staty z archetypu (caster: INT/WIS 14)."""
    from app.services import admin_config

    key = "s2_test_szaman_auto"
    try:
        admin_config.delete_enemy(key, force=True)
    except Exception:
        pass
    row = admin_config.create_enemy(
        key=key, label="Szaman Testowy", hp_base=12, ac_base=11,
        attack_bonus=2, damage_die="d6",
    )
    stats = row.get("stats_json") or {}
    assert stats.get("INT") == 14
    assert stats.get("WIS") == 14
    admin_config.delete_enemy(key, force=True)


def test_create_enemy_explicit_stats_preserved():
    """Jawnie podane staty nie są nadpisywane archetypem."""
    from app.services import admin_config

    key = "s2_test_custom_stats"
    try:
        admin_config.delete_enemy(key, force=True)
    except Exception:
        pass
    row = admin_config.create_enemy(
        key=key, label="Wróg Custom", hp_base=12, ac_base=11,
        attack_bonus=2, damage_die="d6",
        stats_json={"STR": 18, "LCK": 5},
    )
    stats = row.get("stats_json") or {}
    assert stats.get("STR") == 18
    assert stats.get("LCK") == 5
    admin_config.delete_enemy(key, force=True)


# ─── Backward compatibility ─────────────────────────────────────────────────

def test_create_enemy_without_stats_signature_still_works():
    """Stara sygnatura create_enemy (bez stats_json) nadal działa — brak regresji."""
    from app.services import admin_config

    key = "s2_test_backcompat"
    try:
        admin_config.delete_enemy(key, force=True)
    except Exception:
        pass
    row = admin_config.create_enemy(
        key=key, label="Stary Wróg", hp_base=10, ac_base=10,
        attack_bonus=1, damage_die="d4",
    )
    assert row.get("key") == key
    admin_config.delete_enemy(key, force=True)
