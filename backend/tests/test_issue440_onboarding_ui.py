"""TDD: Issue #440 — E25 Frontend onboarding overlay + turn API injection.

Backend: inject_onboarding_to_out helper + hooked into create_turn response.
Frontend: overlay HTML/CSS/JS exists and handles onboarding_cards array.
"""
import sys, json, sqlite3
sys.path.insert(0, "/app")
import pytest
from fastapi.testclient import TestClient

DB_PATH = "/data/ai_gm.db"


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _cleanup_seen(user_id, *keys):
    conn = _get_db()
    try:
        for k in keys:
            conn.execute("DELETE FROM seen_mechanics WHERE user_id=? AND mechanic_key=?", (user_id, k))
        conn.commit()
    finally:
        conn.close()


def _mark_seen(user_id, key):
    conn = _get_db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO seen_mechanics (user_id, mechanic_key) VALUES (?,?)", (user_id, key)
        )
        conn.commit()
    finally:
        conn.close()


# ─── inject_onboarding_to_out helper ────────────────────────────────────────

def test_inject_helper_exists():
    """inject_onboarding_to_out musi istnieć w onboarding_service."""
    try:
        from app.services.onboarding_service import inject_onboarding_to_out
    except ImportError:
        pytest.fail(
            "Brak funkcji inject_onboarding_to_out w onboarding_service. "
            "E25 wymaga tej funkcji do wstrzykiwania kart do odpowiedzi tury."
        )


def test_inject_always_adds_onboarding_cards_field():
    """inject_onboarding_to_out zawsze dodaje klucz onboarding_cards (nawet pusta lista)."""
    from app.services.onboarding_service import inject_onboarding_to_out
    conn = _get_db()
    out = {"route": "narrative", "result": {}}
    try:
        inject_onboarding_to_out(out, user_id=999999, conn=conn)
        assert "onboarding_cards" in out, "Klucz 'onboarding_cards' musi być w out po inject"
        assert isinstance(out["onboarding_cards"], list), "'onboarding_cards' musi być listą"
    finally:
        conn.close()


def test_inject_detects_dice_roll_from_skill_test_pending():
    """inject_onboarding_to_out wykrywa dice_roll gdy skill_test_pending w out."""
    from app.services.onboarding_service import inject_onboarding_to_out
    conn = _get_db()
    user_id = 999998
    _cleanup_seen(user_id, "dice_roll")
    out = {"route": "skill_test", "skill_test_pending": {"skill": "perception"}, "prose": None}
    try:
        inject_onboarding_to_out(out, user_id=user_id, conn=conn)
        keys = [c["mechanic_key"] for c in out["onboarding_cards"]]
        assert "dice_roll" in keys, (
            f"Oczekiwano karty 'dice_roll' gdy skill_test_pending, got: {keys}"
        )
    finally:
        conn.close()
        _cleanup_seen(user_id, "dice_roll")


def test_inject_detects_combat_start():
    """inject_onboarding_to_out wykrywa combat_start gdy combat_state w out."""
    from app.services.onboarding_service import inject_onboarding_to_out
    conn = _get_db()
    user_id = 999997
    _cleanup_seen(user_id, "combat_start")
    out = {"route": "narrative", "combat_state": {"status": "active", "round": 1}, "result": {}}
    try:
        inject_onboarding_to_out(out, user_id=user_id, conn=conn)
        keys = [c["mechanic_key"] for c in out["onboarding_cards"]]
        assert "combat_start" in keys, (
            f"Oczekiwano karty 'combat_start' gdy combat_state w out, got: {keys}"
        )
    finally:
        conn.close()
        _cleanup_seen(user_id, "combat_start")


def test_inject_detects_xp_gained_from_result():
    """inject_onboarding_to_out wykrywa xp_gained gdy xp_granted > 0 w result."""
    from app.services.onboarding_service import inject_onboarding_to_out
    conn = _get_db()
    user_id = 999996
    _cleanup_seen(user_id, "xp_gained")
    out = {"route": "narrative", "result": {"xp_granted": 50, "message": "..."}}
    try:
        inject_onboarding_to_out(out, user_id=user_id, conn=conn)
        keys = [c["mechanic_key"] for c in out["onboarding_cards"]]
        assert "xp_gained" in keys, (
            f"Oczekiwano karty 'xp_gained' gdy xp_granted=50 w result, got: {keys}"
        )
    finally:
        conn.close()
        _cleanup_seen(user_id, "xp_gained")


def test_inject_skips_already_seen_mechanics():
    """inject_onboarding_to_out nie generuje kart dla już widzianych mechanik."""
    from app.services.onboarding_service import inject_onboarding_to_out
    conn = _get_db()
    user_id = 999995
    _cleanup_seen(user_id, "combat_start")
    _mark_seen(user_id, "combat_start")
    out = {"route": "narrative", "combat_state": {"status": "active"}, "result": {}}
    try:
        inject_onboarding_to_out(out, user_id=user_id, conn=conn)
        keys = [c["mechanic_key"] for c in out["onboarding_cards"]]
        assert "combat_start" not in keys, (
            f"combat_start jest już widziana — nie powinna być w kartach, got: {keys}"
        )
    finally:
        conn.close()
        _cleanup_seen(user_id, "combat_start")


def test_inject_detects_gold_gained():
    """inject_onboarding_to_out wykrywa gold_gained gdy gold_drop > 0 w result."""
    from app.services.onboarding_service import inject_onboarding_to_out
    conn = _get_db()
    user_id = 999994
    _cleanup_seen(user_id, "gold_gained")
    out = {"route": "narrative", "result": {"gold_drop": 10}}
    try:
        inject_onboarding_to_out(out, user_id=user_id, conn=conn)
        keys = [c["mechanic_key"] for c in out["onboarding_cards"]]
        assert "gold_gained" in keys, (
            f"Oczekiwano karty 'gold_gained' gdy gold_drop=10 w result, got: {keys}"
        )
    finally:
        conn.close()
        _cleanup_seen(user_id, "gold_gained")
