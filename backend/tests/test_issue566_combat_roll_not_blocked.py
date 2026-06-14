"""TDD: Issue #566 — narracja rzutu walki (__AI_GM_COMBAT_ROLL_V1__) nie może być
blokowana komunikatem „Walka trwa! Użyj interfejsu walki".

Root cause: zwykły (niestrumieniowy) `create_turn` woła `_maybe_handle_blocked_player_combat_turn`
bezwarunkowo i blokuje KAŻDĄ turę przy aktywnej walce. Pakiet narracji rzutu (wysyłany przez
combat UI po `resolve-attack`, gdy tura przeszła już na wroga) trafia na ten blok → „Walka trwa!".
Tor strumieniowy tego nie robi (gwardia current_turn=='player').

Fix: wczesny guard — payload z prefiksem COMBAT_ROLL nigdy nie jest blokowany (to follow-up systemu,
nie wpis gracza). Guard zwraca None ZANIM dotknie bazy → testowalny bez DB.
"""
import sys
sys.path.insert(0, "/app")

import app.api.turns as turns
from app.core.turn_engine import COMBAT_ROLL_CTX_PREFIX


# ─── Test główny — pakiet rzutu walki nie jest blokowany ─────────────────────

def test_combat_roll_payload_not_blocked(monkeypatch):
    """Przy AKTYWNEJ walce: zwykły wpis byłby zablokowany, ale COMBAT_ROLL → None.

    Symulujemy aktywną walkę bez warunku blokującego — bez guardu funkcja zwróciłaby
    dict z „Walka trwa!". Guard musi zwrócić None dla pakietu COMBAT_ROLL.
    """
    from app.services import combat_service as cs
    monkeypatch.setattr(cs, "get_active_combat", lambda _cid: {"status": "active", "current_turn": "enemy_01"})
    monkeypatch.setattr(cs, "evaluate_current_turn_conditions", lambda _cid: {"blocked": False})
    # Strażnicy: gdyby guard NIE zadziałał, te zostałyby wywołane — wysadzamy je,
    # by „brak guardu" był jednoznacznie wykrywalny (wyjątek lub dict, nie None).
    monkeypatch.setattr(turns, "create_turn_log", lambda **_k: (_ for _ in ()).throw(AssertionError("blok wszedł — guard nie zadziałał")))

    payload = COMBAT_ROLL_CTX_PREFIX + '\n{"kind":"player_attack","total":14,"hit":true}'
    out = turns._maybe_handle_blocked_player_combat_turn(
        conn=None,
        campaign_id=999999,
        character_id=1,
        user_text=payload,
        turn_id="t-test",
    )
    assert out is None


# ─── Backward compat — zwykły tekst bez aktywnej walki nadal None ────────────

def test_normal_text_without_active_combat_returns_none(monkeypatch):
    """Zwykły wpis gracza, brak aktywnej walki → None (zachowanie niezmienione)."""
    from app.services import combat_service as cs
    monkeypatch.setattr(cs, "get_active_combat", lambda _cid: None)
    out = turns._maybe_handle_blocked_player_combat_turn(
        conn=None,
        campaign_id=999999,
        character_id=1,
        user_text="rozglądam się po pokoju",
        turn_id="t-test",
    )
    assert out is None
