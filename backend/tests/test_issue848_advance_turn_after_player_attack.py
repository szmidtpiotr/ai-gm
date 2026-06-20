"""TDD: Issue #848 — walka utyka na current_turn=player po ataku gracza.

Root cause: post_resolve_attack nigdy nie woła advance_turn po ataku gracza.
Tura wroga zależy od client-side pollingu — reload (F5) przed odpowiedzią wroga
zostawia walkę na current_turn=player; gracz atakuje ponownie bez tury wroga.

Fix: post_resolve_attack woła advance_turn po ataku gracza (gdy walka active i
attack nie był zablokowany), analogicznie do post_enemy_turn (#633).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ─── Test główny — advance_turn wywoływane po ataku gracza ───────────────────

def test_post_resolve_attack_advances_turn_for_player(monkeypatch):
    """Po ataku gracza API musi deterministycznie wywołać advance_turn.

    Bez fixu: advance_turn NIE jest wołany → current_turn zostaje 'player'.
    Po fixie: advance_turn wołany gdy walka active + attacker='player' + atak nie zablokowany.
    """
    import app.services.combat_service as cs

    advance_turn_called = []

    monkeypatch.setattr(cs, "resolve_attack", lambda cid, roll, **kw: {
        "hit": True, "damage": 4, "enemy_dead": False,
        "combat_state": {"status": "active", "current_turn": "player"},
    })
    monkeypatch.setattr(cs, "load_combat_snapshot", lambda cid: (
        {"status": "active", "current_turn": "undead_champion_01"}
        if advance_turn_called
        else {"status": "active", "current_turn": "player"}
    ))
    monkeypatch.setattr(cs, "advance_turn", lambda cid: (
        advance_turn_called.append(cid) or "undead_champion_01"
    ))

    from app.api.combat import post_resolve_attack, ResolveAttackRequest

    body = ResolveAttackRequest(roll_result=15, attacker="player")
    result = post_resolve_attack(campaign_id=99999, body=body)

    assert advance_turn_called, (
        "advance_turn must be called after player attack — turn stuck on 'player' otherwise (bug #848)"
    )
    assert result.get("advance_turn") == "undead_champion_01", (
        f"Expected advance_turn='undead_champion_01', got {result.get('advance_turn')!r}"
    )
    cs_after = result.get("combat_state") or {}
    assert cs_after.get("current_turn") != "player", (
        f"After player attack, current_turn should not be 'player', got {cs_after.get('current_turn')!r}"
    )


# ─── Test: advance_turn NIE jest wołany gdy walka zakończyła się ──────────────

def test_post_resolve_attack_no_advance_when_combat_ends(monkeypatch):
    """Gdy atak gracza kończy walkę (wróg pokonany), advance_turn NIE powinien być wołany."""
    import app.services.combat_service as cs

    advance_turn_called = []

    monkeypatch.setattr(cs, "resolve_attack", lambda cid, roll, **kw: {
        "hit": True, "damage": 10, "enemy_dead": True,
        "combat_state": {"status": "ended", "ended_reason": "victory"},
    })
    monkeypatch.setattr(cs, "load_combat_snapshot", lambda cid: {
        "status": "ended", "ended_reason": "victory"
    })
    monkeypatch.setattr(cs, "advance_turn", lambda cid: (
        advance_turn_called.append(cid) or "player"
    ))

    from app.api.combat import post_resolve_attack, ResolveAttackRequest

    body = ResolveAttackRequest(roll_result=20, attacker="player")
    result = post_resolve_attack(campaign_id=99999, body=body)

    assert not advance_turn_called, (
        "advance_turn must NOT be called when combat is ended (enemy killed)"
    )
    assert result.get("advance_turn") == "ended"


# ─── Test: advance_turn NIE jest wołany gdy atak zablokowany (out_of_range) ───

def test_post_resolve_attack_no_advance_when_blocked(monkeypatch):
    """Zablokowany atak (out_of_range, mana_insufficient) NIE konsumuje tury → bez advance_turn."""
    import app.services.combat_service as cs

    advance_turn_called = []

    monkeypatch.setattr(cs, "resolve_attack", lambda cid, roll, **kw: {
        "hit": False, "blocked": True, "block_reason": "out_of_range",
        "message": "Cele są poza zasięgiem walki wręcz.",
        "combat_state": {"status": "active", "current_turn": "player"},
    })
    monkeypatch.setattr(cs, "load_combat_snapshot", lambda cid: {
        "status": "active", "current_turn": "player"
    })
    monkeypatch.setattr(cs, "advance_turn", lambda cid: (
        advance_turn_called.append(cid) or "enemy_01"
    ))

    from app.api.combat import post_resolve_attack, ResolveAttackRequest

    body = ResolveAttackRequest(roll_result=15, attacker="player")
    result = post_resolve_attack(campaign_id=99999, body=body)

    assert not advance_turn_called, (
        "advance_turn must NOT be called for blocked attacks (turn not consumed)"
    )


# ─── Backward compat — pola odpowiedzi zachowane ─────────────────────────────

def test_post_resolve_attack_response_shape_preserved(monkeypatch):
    """Oryginalne pola odpowiedzi z resolve_attack są zachowane po fixie."""
    import app.services.combat_service as cs

    monkeypatch.setattr(cs, "resolve_attack", lambda cid, roll, **kw: {
        "hit": True, "damage": 3, "enemy_dead": False,
        "target_hp_remaining": 5,
        "combat_state": {"status": "active", "current_turn": "player"},
    })
    monkeypatch.setattr(cs, "load_combat_snapshot", lambda cid: {
        "status": "active", "current_turn": "enemy_01"
    })
    monkeypatch.setattr(cs, "advance_turn", lambda cid: "enemy_01")

    from app.api.combat import post_resolve_attack, ResolveAttackRequest

    body = ResolveAttackRequest(roll_result=14, attacker="player")
    result = post_resolve_attack(campaign_id=99999, body=body)

    assert result.get("hit") is True, "hit field must be preserved"
    assert result.get("damage") == 3, "damage field must be preserved"
    assert result.get("target_hp_remaining") == 5, "target_hp_remaining must be preserved"
    assert "advance_turn" in result, "advance_turn field must be present after fix"
    assert "combat_state" in result, "combat_state field must be present"
