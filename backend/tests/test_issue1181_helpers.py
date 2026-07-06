"""TDD: Issue #1181 — centralizacja helperów stat_modifier / proficiency_bonus + anchor USE_ITEM.

Weryfikuje że shared helpery dają dokładnie te same wartości co stary inline kod,
że wszystkie zmigrowane wrappery delegują do wspólnego źródła, oraz że regex USE_ITEM
nie łapie już "pięścią"/"pięknie".
"""
import pytest


# ─── Test główny: shared helper == legacy inline ─────────────────────────────

def test_stat_modifier_matches_legacy_inline():
    """core.stat_modifier(v) == (v - 10) // 2 dla całego zakresu -5..30."""
    from app.core.mechanics import stat_modifier
    for v in range(-5, 31):
        assert stat_modifier(v) == (int(v) - 10) // 2, f"stat mismatch @ {v}"


def test_proficiency_bonus_matches_legacy_inline():
    """core.proficiency_bonus(r) == (2 if r >= 3 else 0) dla -1..10."""
    from app.core.mechanics import proficiency_bonus
    for r in range(-1, 11):
        assert proficiency_bonus(r) == (2 if r >= 3 else 0), f"prof mismatch @ {r}"


# ─── Wszystkie zmigrowane wrappery delegują do wspólnego źródła ───────────────

def test_all_stat_modifier_wrappers_agree_with_core():
    """Każdy per-moduł wrapper stat_modifier zwraca to samo co core dla -5..30."""
    from app.core.mechanics import stat_modifier as core_sm
    from app.services.vitality_service import stat_modifier as vit_sm
    from app.services.mechanic_resolver import stat_modifier as mr_sm
    from app.services.combat_v2_service import _stat_mod as cv2_sm
    from app.routers.admin_cheat import _stat_modifier as ac_sm
    from app.api.characters import _stat_modifier as ch_sm
    from app.services.weapon_rules import stat_modifier as wr_sm

    for v in range(-5, 31):
        expected = core_sm(v)
        assert vit_sm(v) == expected, f"vitality @ {v}"
        assert mr_sm(v) == expected, f"mechanic_resolver @ {v}"
        assert cv2_sm(v) == expected, f"combat_v2 @ {v}"
        assert ac_sm(v) == expected, f"admin_cheat @ {v}"
        assert ch_sm(v) == expected, f"characters @ {v}"
        # weapon_rules bierze sheet+stat_key
        assert wr_sm({"stats": {"STR": v}}, "STR") == expected, f"weapon_rules @ {v}"


# ─── Backward compat: publiczne API stat_modifier bez zmian ───────────────────

def test_vitality_stat_modifier_public_api_unchanged():
    """vitality_service.stat_modifier(raw_int) — sygnatura i wynik jak przed fixem."""
    from app.services.vitality_service import stat_modifier
    assert stat_modifier(10) == 0
    assert stat_modifier(16) == 3
    assert stat_modifier(7) == -2


def test_weapon_rules_stat_modifier_public_api_unchanged():
    """weapon_rules.stat_modifier(sheet, key) — sygnatura sheet-based bez zmian."""
    from app.services.weapon_rules import stat_modifier
    assert stat_modifier({"stats": {"DEX": 14}}, "DEX") == 2
    assert stat_modifier({"stats": {}}, "DEX") == 0  # default 10 → 0


# ─── intent_service: anchor USE_ITEM ─────────────────────────────────────────

def test_use_item_no_false_positive_on_pieknie():
    """'wyglądam pięknie' NIE może być klasyfikowane jako use_item (#1181)."""
    from app.services.intent_service import parse_intent
    assert parse_intent("wyglądam pięknie").action_type != "use_item"


def test_use_item_still_matches_drink_verbs():
    """Prawdziwe czasowniki picia nadal łapią się na use_item."""
    from app.services.intent_service import parse_intent
    assert parse_intent("piję miksturę leczniczą").action_type == "use_item"
    assert parse_intent("wypiję eliksir").action_type == "use_item"
    assert parse_intent("używam zwoju").action_type == "use_item"
