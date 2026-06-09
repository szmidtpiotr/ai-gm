"""TDD: Issue #439 — E24 Backend trigger kart onboarding przy pierwszym wystąpieniu mechaniki."""
import sys, json, sqlite3
sys.path.insert(0, "/app")
import pytest
from fastapi.testclient import TestClient

DB_PATH = "/data/ai_gm.db"

MECHANIC_KEYS = ["dice_roll", "combat_start", "damage_taken", "xp_gained", "gold_gained", "death_save"]


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


# ─── Service function ─────────────────────────────────────────────────────────

def test_onboarding_service_exists():
    """Moduł app.services.onboarding_service musi istnieć."""
    try:
        from app.services import onboarding_service
    except ImportError:
        pytest.fail(
            "Brak modułu app.services.onboarding_service. "
            "E24 wymaga tego modułu do triggerowania kart onboardingowych."
        )


def test_check_triggers_returns_cards_for_unseen():
    """check_onboarding_triggers zwraca karty dla niewidzianych mechanik."""
    from app.services.onboarding_service import check_onboarding_triggers
    conn = _get_db()
    user_id = 999999
    _cleanup_seen(user_id, "dice_roll")
    try:
        cards = check_onboarding_triggers(user_id=user_id, triggered_keys=["dice_roll"], conn=conn)
        assert isinstance(cards, list), "check_onboarding_triggers musi zwracać listę"
        assert len(cards) == 1, f"Oczekiwano 1 karty dla 'dice_roll', got {len(cards)}"
        card = cards[0]
        assert "mechanic_key" in card, "Karta musi zawierać mechanic_key"
        assert card["mechanic_key"] == "dice_roll"
        assert "title" in card, "Karta musi zawierać title"
        assert "content" in card, "Karta musi zawierać content"
    finally:
        conn.close()
        _cleanup_seen(user_id, "dice_roll")


def test_check_triggers_skips_already_seen():
    """check_onboarding_triggers pomija mechaniki już widziane przez gracza."""
    from app.services.onboarding_service import check_onboarding_triggers
    conn = _get_db()
    user_id = 999998
    _cleanup_seen(user_id, "combat_start")
    _mark_seen(user_id, "combat_start")
    try:
        cards = check_onboarding_triggers(user_id=user_id, triggered_keys=["combat_start"], conn=conn)
        assert len(cards) == 0, f"Już widziana mechanika nie powinna generować karty, got {len(cards)}"
    finally:
        conn.close()
        _cleanup_seen(user_id, "combat_start")


def test_check_triggers_only_unseen_from_mixed():
    """check_onboarding_triggers filtruje tylko nowe z mieszanej listy."""
    from app.services.onboarding_service import check_onboarding_triggers
    conn = _get_db()
    user_id = 999997
    _cleanup_seen(user_id, "dice_roll", "xp_gained")
    _mark_seen(user_id, "dice_roll")  # dice_roll seen, xp_gained not
    try:
        cards = check_onboarding_triggers(
            user_id=user_id, triggered_keys=["dice_roll", "xp_gained"], conn=conn
        )
        keys = [c["mechanic_key"] for c in cards]
        assert "dice_roll" not in keys, "dice_roll jest już widziane — nie powinno być w wynikach"
        assert "xp_gained" in keys, "xp_gained nie jest widziane — powinno być w wynikach"
    finally:
        conn.close()
        _cleanup_seen(user_id, "dice_roll", "xp_gained")


# ─── Turn response zawiera onboarding_cards ───────────────────────────────────

def test_all_mechanic_keys_have_card_content():
    """Każda z 6 mechanik musi mieć zdefiniowaną kartę w onboarding_service."""
    from app.services.onboarding_service import MECHANIC_CARDS
    for key in MECHANIC_KEYS:
        assert key in MECHANIC_CARDS, f"Brak karty dla mechanic_key='{key}' w MECHANIC_CARDS"
        card = MECHANIC_CARDS[key]
        assert card.get("title"), f"Karta '{key}' musi mieć title"
        assert card.get("content"), f"Karta '{key}' musi mieć content"
