"""TDD: Issue #464 — F4 [SPEND_GOLD:key] refusal narration + apply helper.

Tests for:
- build_refusal_text(conn, character_id, service_key) → Polish refusal string
- apply_spend_gold_to_narrative(text, conn, character_id) → modified text
  - success: tag removed, gold deducted
  - insufficient: tag replaced with refusal text
"""
import sys
sys.path.insert(0, "/app")
from _fixtures_schema import table_sql

import sqlite3
import pytest
from app.services.spend_gold_service import (
    build_refusal_text,
    apply_spend_gold_to_narrative,
    spend_gold_on_service,
)

# ─── Fixture ─────────────────────────────────────────────────────────────────

@pytest.fixture
def test_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        """ + table_sql("game_config_services") + """
    """)
    conn.execute("""
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY,
            gold_gp INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("INSERT INTO game_config_services VALUES (?, ?, ?, ?)",
                 ("inn_night", "Gospoda: jedna noc", 5, 1))
    conn.execute("INSERT INTO game_config_services VALUES (?, ?, ?, ?)",
                 ("healer_light", "Uzdrowiciel: lekkie rany", 10, 1))
    conn.execute("INSERT INTO characters VALUES (?, ?)", (1, 100))
    conn.commit()
    yield conn
    conn.close()


# ─── build_refusal_text ───────────────────────────────────────────────────────

def test_build_refusal_text_mentions_cost(test_db):
    """Refusal text must mention the service cost so player knows how much is needed."""
    test_db.execute("UPDATE characters SET gold_gp = 3 WHERE id = 1")
    text = build_refusal_text(test_db, 1, "inn_night")
    assert "5" in text  # cost_gp=5 appears in refusal


def test_build_refusal_text_is_nonempty_string(test_db):
    text = build_refusal_text(test_db, 1, "inn_night")
    assert isinstance(text, str)
    assert len(text) > 0


def test_build_refusal_text_unknown_service(test_db):
    """Unknown service key → empty string (nothing to refuse)."""
    text = build_refusal_text(test_db, 1, "nonexistent_key")
    assert text == ""


# ─── apply_spend_gold_to_narrative — success path ────────────────────────────

def test_apply_removes_tag_on_success(test_db):
    """When player can afford: tag removed, rest of text preserved."""
    narrative = "Karczmarz kiwa głową. [SPEND_GOLD:inn_night] Dostaniesz pokój na noc."
    result = apply_spend_gold_to_narrative(narrative, test_db, 1)
    assert "[SPEND_GOLD:" not in result
    assert "Dostaniesz pokój na noc" in result


def test_apply_deducts_gold_on_success(test_db):
    """Gold is actually deducted from character on success."""
    narrative = "Płacisz za nocleg. [SPEND_GOLD:inn_night]"
    apply_spend_gold_to_narrative(narrative, test_db, 1)
    test_db.commit()
    row = test_db.execute("SELECT gold_gp FROM characters WHERE id = 1").fetchone()
    assert row["gold_gp"] == 95  # 100 - 5


def test_apply_no_tags_returns_unchanged(test_db):
    """Narrative without tags returned unchanged."""
    narrative = "Idziesz dalej drogą."
    result = apply_spend_gold_to_narrative(narrative, test_db, 1)
    assert result == narrative


# ─── apply_spend_gold_to_narrative — insufficient gold path ──────────────────

def test_apply_replaces_tag_with_refusal_on_insufficient(test_db):
    """When player cannot afford: tag replaced with refusal text, not just removed."""
    test_db.execute("UPDATE characters SET gold_gp = 3 WHERE id = 1")
    test_db.commit()
    narrative = "Karczmarz czeka na zapłatę. [SPEND_GOLD:inn_night] Pokój gotowy."
    result = apply_spend_gold_to_narrative(narrative, test_db, 1)
    assert "[SPEND_GOLD:" not in result
    # Refusal text contains cost (5 gp) so player knows what they need
    assert "5" in result


def test_apply_does_not_deduct_gold_on_insufficient(test_db):
    """Gold unchanged when player cannot afford."""
    test_db.execute("UPDATE characters SET gold_gp = 3 WHERE id = 1")
    test_db.commit()
    narrative = "Czekasz na nocleg. [SPEND_GOLD:inn_night]"
    apply_spend_gold_to_narrative(narrative, test_db, 1)
    row = test_db.execute("SELECT gold_gp FROM characters WHERE id = 1").fetchone()
    assert row["gold_gp"] == 3  # unchanged


def test_apply_multiple_tags_mixed_result(test_db):
    """Multiple tags: first succeeds (100g - 10 = 90), second fails (90 < 100g healer_heavy)."""
    # Use healer_light (10g) and healer_heavy (not in fixture, add it)
    test_db.execute("INSERT INTO game_config_services VALUES (?, ?, ?, ?)",
                    ("healer_heavy", "Uzdrowiciel: ciężkie rany", 200, 1))
    test_db.commit()
    narrative = "[SPEND_GOLD:healer_light] Leczysz rany. [SPEND_GOLD:healer_heavy] Głęboka rana."
    result = apply_spend_gold_to_narrative(narrative, test_db, 1)
    assert "[SPEND_GOLD:" not in result
    # Second tag was too expensive (200g, have 90 after first)
    assert "200" in result


# ─── Backward compat ─────────────────────────────────────────────────────────

def test_spend_gold_on_service_still_works(test_db):
    """Original spend_gold_on_service function unchanged."""
    success, new_gold = spend_gold_on_service(test_db, 1, "inn_night")
    assert success is True
    assert new_gold == 95
