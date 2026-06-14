"""TDD: Issue #584 (S4) — Testy przeciwne na prawdziwych statach (aktor-agnostycznie).

Decyzja 2 (Piotr 2026-06-12): test przeciwny (OPPOSED) przestaje używać sztywnego
modyfikatora +2 — przeciwnik broni się SWOIMI prawdziwymi statami (7 statów z S2/S3).
counter_key może być statem (WIS) lub skillem (insight → linked_stat). Kondycje
przeciwnika modyfikują jego obronę. Brak rozpoznanego aktora → fallback DC (flat).

Mechanizm testowany deterministycznie: modyfikator przeciwnika = opponent_total - opponent_roll,
niezależny od wylosowanej kości.
"""
import json
import sqlite3

import pytest

from app.services.skill_service import resolve_skill_test


def _conn():
    # in-memory — opposed-with-injected-opponent path nie dotyka DB
    return sqlite3.connect(":memory:")


def _pending_opposed(counter_key, opponent=None, dc=12, mod=0, skill_key="persuasion"):
    counter = {"counter_type": "opposed", "counter_key": counter_key, "dc": dc}
    if opponent is not None:
        counter["opponent"] = opponent
    return {
        "skill_key": skill_key,
        "skill_label": skill_key.title(),
        "counter": counter,
        "modifier_breakdown": {"total": mod},
    }


def _opp_mod(result):
    """Modyfikator przeciwnika wyłuskany z wyniku (deterministyczny, bez kości)."""
    return result["opponent_total"] - result["opponent_roll"]


# ─── Test główny — przeciwnik broni się prawdziwym statem ────────────────────

def test_opponent_rolls_with_real_stat_low_wis():
    """Przeciwnik z WIS 8 → modyfikator obrony (8-10)//2 = -1."""
    r = resolve_skill_test(10, _pending_opposed("WIS", {"stats": {"WIS": 8}}), _conn(), 1, 1)
    assert _opp_mod(r) == -1


def test_opponent_rolls_with_real_stat_high_wis():
    """Przeciwnik z WIS 16 → modyfikator obrony (16-10)//2 = +3."""
    r = resolve_skill_test(10, _pending_opposed("WIS", {"stats": {"WIS": 16}}), _conn(), 1, 1)
    assert _opp_mod(r) == 3


def test_low_wis_opponent_easier_than_high_wis():
    """Perswazja na osiłku (WIS 8) ma niższy próg niż na kapłanie (WIS 16)."""
    osilek = resolve_skill_test(10, _pending_opposed("WIS", {"stats": {"WIS": 8}}), _conn(), 1, 1)
    kaplan = resolve_skill_test(10, _pending_opposed("WIS", {"stats": {"WIS": 16}}), _conn(), 1, 1)
    assert _opp_mod(osilek) < _opp_mod(kaplan)


def test_counter_key_can_be_skill_uses_linked_stat():
    """counter_key 'insight' (skill) → przeciwnik rzuca jego statem rządzącym (WIS)."""
    # insight → WIS (mapa skilli); przeciwnik WIS 14 → mod +2
    r = resolve_skill_test(
        10, _pending_opposed("insight", {"stats": {"WIS": 14}}, skill_key="deception"),
        _conn(), 1, 1,
    )
    assert _opp_mod(r) == 2


def test_opponent_condition_modifies_defense():
    """Kondycja celu (confused: WIS -3) obniża jego obronę: 14→ mod +2, po kondycji -1."""
    opponent = {
        "stats": {"WIS": 14},
        "conditions": [{"effect_json": json.dumps({"stat_mods": {"WIS": -3}})}],
    }
    r = resolve_skill_test(10, _pending_opposed("WIS", opponent), _conn(), 1, 1)
    assert _opp_mod(r) == -1  # +2 (WIS 14) - 3 (confused)


# ─── Fallback — brak rozpoznanego aktora ─────────────────────────────────────

def test_opposed_without_actor_falls_back_to_flat_dc():
    """Brak aktora w opposed → fallback do płaskiego DC (opponent_roll None, próg = dc)."""
    r = resolve_skill_test(10, _pending_opposed("WIS", opponent=None, dc=14), _conn(), 1, 1)
    assert r["opponent_roll"] is None
    assert r["opponent_total"] == 14


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_dc_counter_unchanged():
    """Zwykły test DC (counter_type='dc') bez zmian: próg = dc, brak rzutu przeciwnika."""
    pending = {
        "skill_key": "athletics",
        "skill_label": "Athletics",
        "counter": {"counter_type": "dc", "counter_key": None, "dc": 12},
        "modifier_breakdown": {"total": 0},
    }
    r = resolve_skill_test(10, pending, _conn(), 1, 1)
    assert r["opponent_roll"] is None
    assert r["opponent_total"] == 12


def test_result_keys_preserved():
    """Klucze wyniku bez zmian — kompatybilność konsumentów."""
    r = resolve_skill_test(10, _pending_opposed("WIS", {"stats": {"WIS": 10}}), _conn(), 1, 1)
    for k in ("success", "nat20", "nat1", "player_total", "opponent_total",
              "opponent_roll", "margin", "outcome", "skill_key"):
        assert k in r
