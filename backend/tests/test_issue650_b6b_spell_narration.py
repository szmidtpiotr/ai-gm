"""TDD: Issue #650 (B6b) — narracja ataku czarem ma instruować LLM o MAGII, nie broni.

Przyczyna buga: dla `kind:'player_attack'` funkcja `_user_text_for_llm_context` zwracała
surowy JSON trafienia, bez informacji że to czar → LLM opisywał cios wyposażoną laską.
Fix: payload z `attack_mode:'spell'` → jawna proza-instrukcja narracji magicznej.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.turn_engine import _user_text_for_llm_context, COMBAT_ROLL_CTX_PREFIX


def _combat_line(payload: dict) -> str:
    return f"{COMBAT_ROLL_CTX_PREFIX}\n{json.dumps(payload, ensure_ascii=False)}"


# ─── Test główny: atak czarem → instrukcja magii ─────────────────────────────

def test_spell_attack_produces_magic_narration_instruction():
    """player_attack z attack_mode='spell' → proza z nazwą zaklęcia + 'magia, nie broń'."""
    line = _combat_line({
        "kind": "player_attack",
        "attack_mode": "spell",
        "spell_label": "Ognista Strzała",
        "target_name": "Goblin",
        "hit": True,
        "damage": 7,
    })
    out = _user_text_for_llm_context(line)
    # Nie zwraca surowego JSON-a / prefiksu
    assert COMBAT_ROLL_CTX_PREFIX not in out, f"surowy prefiks wyciekł do LLM: {out!r}"
    assert "{" not in out, f"surowy JSON wyciekł do LLM: {out!r}"
    # Zawiera nazwę zaklęcia i sygnał, że to MAGIA, a nie broń fizyczna
    assert "Ognista Strzała" in out
    low = out.lower()
    assert "magi" in low or "zaklęci" in low or "zaklecie" in low, f"brak sygnału magii: {out!r}"
    assert "broń" in low or "bron" in low, f"brak jawnego zakazu opisu bronią: {out!r}"


def test_spell_attack_miss_mentions_miss_not_damage():
    """Pudło czaru → outcome bez obrażeń, nadal instrukcja magii."""
    line = _combat_line({
        "kind": "player_attack",
        "attack_mode": "spell",
        "spell_label": "Lodowy Grot",
        "target_name": "Szkielet",
        "hit": False,
        "damage": 0,
    })
    out = _user_text_for_llm_context(line)
    assert "Lodowy Grot" in out
    low = out.lower()
    assert "chyb" in low or "pud" in low or "nie traf" in low, f"brak sygnału pudła: {out!r}"


# ─── Backward compatibility: atak bronią bez zmian ───────────────────────────

def test_weapon_attack_unchanged_returns_raw():
    """player_attack BEZ attack_mode (broń) → zachowanie jak przed fixem (zwraca surowy wpis)."""
    payload = {
        "kind": "player_attack",
        "character_name": "Konan",
        "hit": True,
        "damage": 9,
        "target_name": "Goblin",
    }
    line = _combat_line(payload)
    out = _user_text_for_llm_context(line)
    # Stare zachowanie: brak summary_line/intent → zwraca surowy `s`
    assert out == line, f"atak bronią zmienił zachowanie (regresja): {out!r}"


def test_flee_payload_still_handled():
    """player_flee nadal działa (nie złapany przez gałąź spell)."""
    line = _combat_line({"kind": "player_flee", "summary_line": "Uciekasz w mrok."})
    out = _user_text_for_llm_context(line)
    assert "Uciekasz w mrok." in out
    assert COMBAT_ROLL_CTX_PREFIX not in out
