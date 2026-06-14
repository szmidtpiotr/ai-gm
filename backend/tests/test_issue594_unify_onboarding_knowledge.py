"""TDD: Issue #594 — unify onboarding cards + knowledge_book.

One entry can be shown in BOTH surfaces independently:
  - show_in_onboarding=1 → eligible as a triggered onboarding popup (content from DB)
  - show_in_knowledge=1  → listed in the player Knowledge book (/knowledge-tips)
Onboarding falls back to the hardcoded MECHANIC_CARDS when no DB row exists.

Uses throwaway keys (zz_*) so real seeded onboarding cards are never mutated.
"""
import sqlite3

from app.services.onboarding_service import check_onboarding_triggers, MECHANIC_CARDS

DB = "/data/ai_gm.db"
K1 = "zz_test_594_both"
K2 = "zz_test_594_onbonly"


def _conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def _ensure_cols(c):
    cols = {r[1] for r in c.execute("PRAGMA table_info(knowledge_book)").fetchall()}
    if "kind" not in cols:
        c.execute("ALTER TABLE knowledge_book ADD COLUMN kind TEXT NOT NULL DEFAULT 'knowledge_tip'")
    if "show_in_onboarding" not in cols:
        c.execute("ALTER TABLE knowledge_book ADD COLUMN show_in_onboarding INTEGER NOT NULL DEFAULT 0")
    if "show_in_knowledge" not in cols:
        c.execute("ALTER TABLE knowledge_book ADD COLUMN show_in_knowledge INTEGER NOT NULL DEFAULT 1")
    c.commit()


def _upsert(c, tip_key, body, show_onb, show_kno, title="T"):
    c.execute("DELETE FROM knowledge_book WHERE tip_key = ?", (tip_key,))
    c.execute(
        "INSERT INTO knowledge_book (tip_key, category, title, body, is_active, sort_order, "
        "kind, show_in_onboarding, show_in_knowledge) VALUES (?, 'onboarding', ?, ?, 1, 0, ?, ?, ?)",
        (tip_key, title, body, "onboarding_card" if show_onb else "knowledge_tip", show_onb, show_kno),
    )
    c.commit()


# ─── Test główny — ten sam wpis widoczny w OBU miejscach ─────────────────────

def test_entry_visible_in_both_surfaces():
    """show_in_onboarding=1 AND show_in_knowledge=1 → karta onboardingu I wpis w Księdze."""
    from app.api.knowledge import list_knowledge_tips
    c = _conn()
    _ensure_cols(c)
    custom = "WSPOLNY WPIS #594"
    _upsert(c, K1, custom, show_onb=1, show_kno=1)
    c.execute("DELETE FROM seen_mechanics WHERE user_id = 999999 AND mechanic_key = ?", (K1,))
    c.commit()
    onb = check_onboarding_triggers(user_id=999999, triggered_keys=[K1], conn=c)
    in_knowledge = K1 in [t["tip_key"] for t in list_knowledge_tips()["tips"]]
    c.execute("DELETE FROM knowledge_book WHERE tip_key = ?", (K1,))
    c.commit()
    c.close()
    assert in_knowledge, "wpis z show_in_knowledge=1 musi być w /knowledge-tips"
    assert any(card["mechanic_key"] == K1 and card["content"] == custom for card in onb), \
        "ten sam wpis musi działać jako karta onboardingu z treścią z DB"


def test_onboarding_only_not_in_knowledge():
    """show_in_onboarding=1, show_in_knowledge=0 → onboarding tak, Księga nie."""
    from app.api.knowledge import list_knowledge_tips
    c = _conn()
    _ensure_cols(c)
    _upsert(c, K2, "x", show_onb=1, show_kno=0)
    c.execute("DELETE FROM seen_mechanics WHERE user_id = 999997 AND mechanic_key = ?", (K2,))
    c.commit()
    onb = check_onboarding_triggers(user_id=999997, triggered_keys=[K2], conn=c)
    not_in_knowledge = K2 not in [t["tip_key"] for t in list_knowledge_tips()["tips"]]
    c.execute("DELETE FROM knowledge_book WHERE tip_key = ?", (K2,))
    c.commit()
    c.close()
    assert not_in_knowledge, "wpis z show_in_knowledge=0 nie powinien być w Księdze"
    assert any(card["mechanic_key"] == K2 for card in onb), "onboarding nadal powinien dostać kartę"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_fallback_to_hardcoded_when_no_db_row():
    """No DB row → fall back to MECHANIC_CARDS (no regression). Restores the row after."""
    c = _conn()
    _ensure_cols(c)
    key = "combat_start"
    orig = MECHANIC_CARDS[key]
    c.execute("DELETE FROM knowledge_book WHERE tip_key = ?", (key,))
    c.execute("DELETE FROM seen_mechanics WHERE user_id = 999998 AND mechanic_key = ?", (key,))
    c.commit()
    cards = check_onboarding_triggers(user_id=999998, triggered_keys=[key], conn=c)
    # restore the seeded row so DEV data isn't left polluted
    _upsert(c, key, orig["content"], show_onb=1, show_kno=1, title=orig["title"])
    c.close()
    assert any(
        card["mechanic_key"] == key and card["content"] == orig["content"]
        for card in cards
    ), "must fall back to hardcoded card when no DB row exists"
