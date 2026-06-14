"""TDD: Issue #594 — unify onboarding cards + knowledge_book via `kind`.

Onboarding card content moves to the knowledge_book table (kind='onboarding_card'),
read by onboarding_service with a fallback to the hardcoded MECHANIC_CARDS. The
player knowledge endpoint must only return kind='knowledge_tip'.
"""
import sqlite3

from app.services.onboarding_service import check_onboarding_triggers, MECHANIC_CARDS

DB = "/data/ai_gm.db"


def _conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def _ensure_kind_col(c):
    cols = {r[1] for r in c.execute("PRAGMA table_info(knowledge_book)").fetchall()}
    if "kind" not in cols:
        c.execute("ALTER TABLE knowledge_book ADD COLUMN kind TEXT NOT NULL DEFAULT 'knowledge_tip'")
        c.commit()


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_onboarding_content_comes_from_db():
    """Editing the knowledge_book onboarding_card row changes the player's card."""
    c = _conn()
    _ensure_kind_col(c)
    key = "dice_roll"
    custom = "ZMIENIONA TRESC TESTOWA #594"
    c.execute("DELETE FROM knowledge_book WHERE tip_key = ?", (key,))
    c.execute(
        "INSERT INTO knowledge_book (tip_key, category, title, body, is_active, sort_order, kind) "
        "VALUES (?, 'onboarding', ?, ?, 1, 0, 'onboarding_card')",
        (key, "Rzut kością", custom),
    )
    c.execute("DELETE FROM seen_mechanics WHERE user_id = 999999 AND mechanic_key = ?", (key,))
    c.commit()
    cards = check_onboarding_triggers(user_id=999999, triggered_keys=[key], conn=c)
    c.close()
    assert any(
        card["mechanic_key"] == key and card["content"] == custom for card in cards
    ), "onboarding card content must come from the DB row, not the hardcoded dict"


def test_knowledge_tips_excludes_onboarding_cards():
    """Player /knowledge-tips must not leak onboarding cards (kind filter)."""
    from app.api.knowledge import list_knowledge_tips
    c = _conn()
    _ensure_kind_col(c)
    key = "dice_roll"
    c.execute("DELETE FROM knowledge_book WHERE tip_key = ?", (key,))
    c.execute(
        "INSERT INTO knowledge_book (tip_key, category, title, body, is_active, sort_order, kind) "
        "VALUES (?, 'onboarding', ?, ?, 1, 0, 'onboarding_card')",
        (key, "Rzut kością", "x"),
    )
    c.commit()
    c.close()
    keys = [t["tip_key"] for t in list_knowledge_tips()["tips"]]
    assert key not in keys, "onboarding_card rows must not appear in player knowledge tips"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_fallback_to_hardcoded_when_no_db_row():
    """No onboarding_card row → fall back to MECHANIC_CARDS (no regression)."""
    c = _conn()
    _ensure_kind_col(c)
    key = "combat_start"
    c.execute("DELETE FROM knowledge_book WHERE tip_key = ?", (key,))
    c.execute("DELETE FROM seen_mechanics WHERE user_id = 999998 AND mechanic_key = ?", (key,))
    c.commit()
    cards = check_onboarding_triggers(user_id=999998, triggered_keys=[key], conn=c)
    c.close()
    assert any(
        card["mechanic_key"] == key and card["content"] == MECHANIC_CARDS[key]["content"]
        for card in cards
    ), "must fall back to hardcoded card when no DB row exists"
