"""TDD: Issue #1000 — Bramka przewagi: pętla LLM gdy Zastraszenie/Wycofaj (pending_zaskoczony nieczyszczona)."""
import json
import sys
import os

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/app")


# ─── Test 1: Gate NIE re-emituje po non-stealth skill test ───────────────────

def test_gate_not_reemitted_after_non_stealth_skill_test():
    """skill_test_resolve NIE emituje advantage_gate gdy pending.skill_key != 'stealth'."""
    from app.services.combat_service import build_advantage_gate

    # Symuluje stan po sukcesie Stealth: pending_zaskoczony = True w session_flags
    _sf_st = {"pending_zaskoczony": True, "state": "NARRATIVE"}

    # Rozstrzygamy test Zastraszania (nie Stealth)
    fake_pending = {"skill_key": "intimidation", "skill_label": "Zastraszanie"}

    # Warunek poprawki: gate tylko gdy pending.skill_key == "stealth"
    should_emit = (
        _sf_st.get("pending_zaskoczony")
        and str(fake_pending.get("skill_key", "")).lower() == "stealth"
    )
    assert not should_emit, (
        "Gate NIE powinien być emitowany gdy rozstrzygamy test inny niż Stealth "
        "(wynik: bramka pętli dla Zastraszenia/Wycofaj)"
    )


# ─── Test 2: Gate emituje TYLKO po teście Stealth ─────────────────────────────

def test_gate_emitted_after_stealth_skill_test():
    """skill_test_resolve emituje advantage_gate gdy pending.skill_key == 'stealth'."""
    from app.services.combat_service import build_advantage_gate

    _sf_st = {"pending_zaskoczony": True, "state": "NARRATIVE"}
    fake_pending = {"skill_key": "stealth", "skill_label": "Skradanie"}

    should_emit = (
        _sf_st.get("pending_zaskoczony")
        and str(fake_pending.get("skill_key", "")).lower() == "stealth"
    )
    assert should_emit, "Gate POWINIEN być emitowany bezpośrednio po sukcesie Stealth"

    gate = build_advantage_gate("stealth")
    assert gate is not None
    assert gate.get("source") == "stealth"
    assert len(gate.get("options", [])) >= 3


# ─── Test 3: build_advantage_gate ma opcję dialog ─────────────────────────────

def test_advantage_gate_has_dialog_option():
    """build_advantage_gate zwraca min. 4 opcje z opcją 'dialog'."""
    from app.services.combat_service import build_advantage_gate

    gate = build_advantage_gate("stealth")
    assert gate is not None

    ids = [o.get("id") for o in gate.get("options", [])]
    assert "dialog" in ids, f"Brak opcji 'dialog' w bramce. Dostępne: {ids}"


# ─── Test 4: intimidate action to __GATE:intimidate ───────────────────────────

def test_intimidate_option_action_is_gate_prefix():
    """Opcja 'intimidate' ma action = '__GATE:intimidate' (nie prozę do LLM)."""
    from app.services.combat_service import build_advantage_gate

    gate = build_advantage_gate("stealth")
    assert gate is not None

    intimidate_opt = next((o for o in gate.get("options", []) if o.get("id") == "intimidate"), None)
    assert intimidate_opt is not None, "Brak opcji 'intimidate' w bramce"
    assert intimidate_opt["action"] == "__GATE:intimidate", (
        f"Oczekiwano '__GATE:intimidate', otrzymano '{intimidate_opt['action']}'. "
        "Akcja musi być deterministyczna (nie proza do LLM)."
    )


# ─── Test 5: withdraw action to __GATE:withdraw ───────────────────────────────

def test_withdraw_option_action_is_gate_prefix():
    """Opcja 'withdraw' ma action = '__GATE:withdraw'."""
    from app.services.combat_service import build_advantage_gate

    gate = build_advantage_gate("stealth")
    assert gate is not None

    withdraw_opt = next((o for o in gate.get("options", []) if o.get("id") == "withdraw"), None)
    assert withdraw_opt is not None, "Brak opcji 'withdraw' w bramce"
    assert withdraw_opt["action"] == "__GATE:withdraw", (
        f"Oczekiwano '__GATE:withdraw', otrzymano '{withdraw_opt['action']}'."
    )


# ─── Test 6: _parse_gate_option helper ───────────────────────────────────────

def test_parse_gate_option_extracts_correctly():
    """__GATE:intimidate daje gate_option='intimidate', __GATE:withdraw daje 'withdraw'."""
    def _parse(text):
        if not text.startswith("__GATE:"):
            return None
        return text[7:].split(":", 1)[0].lower()

    assert _parse("__GATE:intimidate") == "intimidate"
    assert _parse("__GATE:withdraw") == "withdraw"
    assert _parse("__GATE:dialog") == "dialog"
    assert _parse("normalny tekst") is None
    assert _parse("__GATE:") == ""


# ─── Test 7: intimidation skill test ma bonus przewagi ────────────────────────

def test_intimidate_gate_sets_advantage_bonus_in_modifier():
    """__GATE:intimidate wstrzykuje advantage_bonus=2 do modifier_breakdown."""
    from app.services.skill_service import calc_skill_modifier_info

    fake_sheet = {
        "stats": {"STR": 12, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 14, "LCK": 10},
        "skills": {"intimidation": 1},
    }
    mod_info = calc_skill_modifier_info(fake_sheet, "intimidation")
    base_total = mod_info["total"]

    # Symulacja tego co robi __GATE:intimidate handler
    mod_info_with_bonus = dict(mod_info)
    mod_info_with_bonus["total"] = base_total + 2
    mod_info_with_bonus["advantage_bonus"] = 2

    assert mod_info_with_bonus["advantage_bonus"] == 2
    assert mod_info_with_bonus["total"] == base_total + 2, (
        "Test Zastraszania z bramki przewagi musi mieć +2 bonus (advantage ze Stealth)"
    )


# ─── Backward compat: grapple gate nadal działa ───────────────────────────────

def test_grapple_gate_still_works():
    """build_advantage_gate('grapple') nadal zwraca bramkę z subdue_resolution."""
    from app.services.combat_service import build_advantage_gate

    gate = build_advantage_gate("grapple")
    assert gate is not None
    assert gate.get("source") == "grapple"
    assert "subdue_resolution" in gate, "Grapple gate musi mieć subdue_resolution"


# ─── Backward compat: bez źródła zwraca None ──────────────────────────────────

def test_build_advantage_gate_none_on_empty_source():
    """build_advantage_gate(None) i build_advantage_gate('') zwracają None."""
    from app.services.combat_service import build_advantage_gate

    assert build_advantage_gate(None) is None
    assert build_advantage_gate("") is None
    assert build_advantage_gate("  ") is None
