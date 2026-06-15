"""TDD: Issue #658 (B12) — czary w Kreatorze AI (Smart Entry) — kontrakt backendu.

B12 domyka FRONTEND (wpięcie `game_config_spells` do Kreatora AI + pełny ręczny formularz).
Backend Smart Entry obsługuje czary od B6/B7 — ten plik to REGRESYJNY STRAŻNIK kontraktu,
na którym stoi nowe wpięcie frontendu: gdyby ktoś wyrzucił `game_config_spells` z
`WRITABLE_TABLES` albo okroił schemat pól, Kreator AI dla czarów przestałby działać.

Strażnik (deterministyczny, bez LLM, bez DB):
  • game_config_spells jest zapisywalne (WRITABLE), nie read-only
  • schemat /schema serwuje pełny zestaw pól (spell_type, effect_stat, effect_type,
    effect_duration, target_zone, aoe, rank2_json, rank3_json + wymagane)
  • spell_type ma 5 dozwolonych wartości spójnych z dispatch silnika (attack/attack_aoe/heal/defense/effect)
  • backward-compat: broń (game_config_weapons) nadal w schemacie i zapisywalna
"""
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routers import smart_entry

SPELL_TABLE = "game_config_spells"


# ─── Test główny — Smart Entry zna czary z pełnym schematem ──────────────────

def test_spells_table_is_writable_in_smart_entry():
    """game_config_spells musi być zapisywalne przez Kreator AI (nie read-only)."""
    assert SPELL_TABLE in smart_entry.WRITABLE_TABLES
    assert SPELL_TABLE not in smart_entry.READ_ONLY_TABLES
    # _assert_writable nie może rzucić 403 dla czarów
    smart_entry._assert_writable(SPELL_TABLE)  # nie podnosi wyjątku


def test_spells_schema_exposes_full_field_set():
    """Schemat czaru musi zawierać wszystkie pola, które przyjmuje backend /api/admin/spells."""
    schema = smart_entry.SCHEMA_DESCRIPTORS.get(SPELL_TABLE)
    assert schema is not None, "brak deskryptora schematu dla game_config_spells"

    required = set(schema["required"])
    optional = set(schema.get("optional", []))
    all_fields = required | optional

    # Wymagane (rdzeń czaru)
    assert {"key", "label", "tier", "mana_cost", "spell_type"} <= required

    # Pełny zestaw pól mechaniki czaru (to, czego brakowało w ręcznym formularzu frontendu)
    for f in ("damage_die", "heal_die", "effect_stat", "effect_type",
              "effect_duration", "target_zone", "aoe", "rank2_json", "rank3_json"):
        assert f in all_fields, f"schemat czaru nie zawiera pola '{f}'"


def test_spell_type_options_match_engine_dispatch():
    """spell_type = 5 wartości dispatch silnika (B6/B9/B10): attack/attack_aoe/heal/defense/effect."""
    fields = smart_entry.SCHEMA_DESCRIPTORS[SPELL_TABLE]["fields"]
    opts = {o["label"] for o in fields["spell_type"]["options"]}
    assert opts == {"attack", "attack_aoe", "heal", "defense", "effect"}


def test_schema_endpoint_returns_spell_fields():
    """GET /schema?table=game_config_spells zwraca listę pól dla renderu formularza."""
    result = smart_entry.smart_entry_schema(table=SPELL_TABLE)
    assert result["table"] == SPELL_TABLE
    field_keys = {f["key"] for f in result["fields"]}
    assert {"key", "label", "tier", "mana_cost", "spell_type",
            "effect_stat", "aoe", "rank2_json", "rank3_json"} <= field_keys
    # spell_type renderowany jako single_choice z opcjami
    spell_type_field = next(f for f in result["fields"] if f["key"] == "spell_type")
    assert spell_type_field["type"] == "single_choice"
    assert spell_type_field.get("options")


# ─── Backward compatibility — istniejące tabele nietknięte ───────────────────

def test_weapons_still_writable_and_in_schema():
    """Broń (i pozostałe tabele Kreatora) działa jak wcześniej — zero regresji."""
    smart_entry._assert_writable("game_config_weapons")  # nie podnosi wyjątku
    assert "game_config_weapons" in smart_entry.SCHEMA_DESCRIPTORS
    assert "game_config_items" in smart_entry.WRITABLE_TABLES


def test_read_only_table_still_rejected():
    """Tabela read-only (np. game_config_skills) nadal odrzucana z 403."""
    with pytest.raises(HTTPException) as exc:
        smart_entry._assert_writable("game_config_skills")
    assert exc.value.status_code == 403
