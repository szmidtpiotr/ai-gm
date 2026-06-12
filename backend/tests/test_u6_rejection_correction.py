"""U6 (#530): Rejection correction pattern tests.

Tests that:
- REJECTION_CORRECTIONS dict exists in llm_tag_parser with correct entries
- get_rejection_correction() returns text for GRANT_ITEM, None for QUEST_SUGGEST
- save_rejected_tags / get_last_rejected_tags / clear_rejected_tags work on session_flags
- find_unknown_tags correctly identifies unknown vs known tags
- The rejected-tags context block is properly formatted
"""
import json
import sqlite3
import pytest


@pytest.fixture
def mem_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE llm_tag_errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            turn_number INTEGER NOT NULL,
            tag_raw TEXT NOT NULL,
            error_type TEXT NOT NULL,
            ts TEXT NOT NULL
        );
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            session_flags TEXT DEFAULT '{}'
        );
        INSERT INTO game_sessions (campaign_id, session_flags) VALUES (1, '{}');
    """)
    return conn


# ─── REJECTION_CORRECTIONS dict ───────────────────────────────────────────────

def test_rejection_corrections_dict_exists():
    from app.services.llm_tag_parser import REJECTION_CORRECTIONS
    assert "GRANT_ITEM" in REJECTION_CORRECTIONS
    assert REJECTION_CORRECTIONS["GRANT_ITEM"] is not None
    assert "bezwartościowy" in REJECTION_CORRECTIONS["GRANT_ITEM"]
    # Decision 2026-06-12: item DOES reach the inventory — correction must NOT mention plecak
    assert "plecak" not in REJECTION_CORRECTIONS["GRANT_ITEM"]
    assert "QUEST_SUGGEST" in REJECTION_CORRECTIONS
    assert REJECTION_CORRECTIONS["QUEST_SUGGEST"] is None
    assert "SKILL_CHECK" in REJECTION_CORRECTIONS
    assert REJECTION_CORRECTIONS["SKILL_CHECK"] is None


def test_item_create_has_same_correction_as_grant_item():
    from app.services.llm_tag_parser import REJECTION_CORRECTIONS
    assert "ITEM_CREATE" in REJECTION_CORRECTIONS
    assert REJECTION_CORRECTIONS["ITEM_CREATE"] is not None


# ─── get_rejection_correction() ───────────────────────────────────────────────

def test_get_rejection_correction_grant_item():
    from app.services.llm_tag_parser import get_rejection_correction
    corr = get_rejection_correction("GRANT_ITEM")
    assert corr is not None
    assert "bezwartościowy" in corr


def test_get_rejection_correction_case_insensitive():
    from app.services.llm_tag_parser import get_rejection_correction
    assert get_rejection_correction("grant_item") == get_rejection_correction("GRANT_ITEM")


def test_get_rejection_correction_quest_suggest_is_none():
    from app.services.llm_tag_parser import get_rejection_correction
    assert get_rejection_correction("QUEST_SUGGEST") is None


def test_get_rejection_correction_unknown_returns_none():
    from app.services.llm_tag_parser import get_rejection_correction
    assert get_rejection_correction("TOTALLY_UNKNOWN_TAG_XYZ") is None


# ─── session_flags helpers ────────────────────────────────────────────────────

def test_save_and_get_rejected_tags(mem_db):
    from app.services.llm_tag_parser import save_rejected_tags, get_last_rejected_tags
    save_rejected_tags(mem_db, campaign_id=1, tags=["GRANT_ITEM", "UNKNOWN_TAG"])
    result = get_last_rejected_tags(mem_db, campaign_id=1)
    assert result == ["GRANT_ITEM", "UNKNOWN_TAG"]


def test_get_last_rejected_tags_empty_when_none(mem_db):
    from app.services.llm_tag_parser import get_last_rejected_tags
    result = get_last_rejected_tags(mem_db, campaign_id=1)
    assert result == []


def test_clear_rejected_tags(mem_db):
    from app.services.llm_tag_parser import save_rejected_tags, clear_rejected_tags, get_last_rejected_tags
    save_rejected_tags(mem_db, campaign_id=1, tags=["GRANT_ITEM"])
    clear_rejected_tags(mem_db, campaign_id=1)
    result = get_last_rejected_tags(mem_db, campaign_id=1)
    assert result == []


def test_save_empty_tags_does_not_overwrite(mem_db):
    """Saving empty list should not change existing rejected tags."""
    from app.services.llm_tag_parser import save_rejected_tags, get_last_rejected_tags
    save_rejected_tags(mem_db, campaign_id=1, tags=["GRANT_ITEM"])
    save_rejected_tags(mem_db, campaign_id=1, tags=[])  # empty — should be no-op
    result = get_last_rejected_tags(mem_db, campaign_id=1)
    assert result == ["GRANT_ITEM"]


def test_save_rejected_tags_no_crash_missing_session(mem_db):
    """Should not crash when campaign_id has no game_sessions row."""
    from app.services.llm_tag_parser import save_rejected_tags
    save_rejected_tags(mem_db, campaign_id=999, tags=["GRANT_ITEM"])  # no row → silent


# ─── Context block format ─────────────────────────────────────────────────────

def test_rejected_tags_block_format(mem_db):
    """Block injected into LLM context has correct format."""
    from app.services.llm_tag_parser import save_rejected_tags, get_last_rejected_tags
    save_rejected_tags(mem_db, campaign_id=1, tags=["GRANT_ITEM"])
    tags = get_last_rejected_tags(mem_db, campaign_id=1)
    block = "[Odrzucone tagi z poprzedniej tury: " + ", ".join(tags) + "]"
    assert "GRANT_ITEM" in block
    assert "Odrzucone tagi z poprzedniej tury" in block
    assert block.startswith("[")
    assert block.endswith("]")


# ─── find_unknown_tags ────────────────────────────────────────────────────────

def test_find_unknown_tags_detected():
    from app.services.llm_tag_parser import find_unknown_tags
    text = "Walka trwa. [MAGIC_SWORD:shiny] pojawia się w twoich rękach."
    unknown = find_unknown_tags(text)
    assert len(unknown) == 1
    assert "MAGIC_SWORD" in unknown[0]


def test_find_unknown_tags_empty_for_known():
    from app.services.llm_tag_parser import find_unknown_tags
    text = "Zaczynamy walkę! [COMBAT_START:bandit]"
    unknown = find_unknown_tags(text)
    assert unknown == []


def test_find_unknown_tags_multiple():
    from app.services.llm_tag_parser import find_unknown_tags
    text = "[FIRE_SWORD:legendary] i [MAGIC_POTION:rare] w kieszeni."
    unknown = find_unknown_tags(text)
    assert len(unknown) == 2


# ─── Trivial item heuristic (pending_category) ────────────────────────────────

def test_trivial_item_label_detected():
    from app.api.turns import _is_trivial_item_label
    assert _is_trivial_item_label("Sucha gałązka") is True
    assert _is_trivial_item_label("Stary kamień") is True
    assert _is_trivial_item_label("Suchy liść") is True
    assert _is_trivial_item_label("Garść piasku") is True


def test_non_trivial_item_label_not_flagged():
    from app.api.turns import _is_trivial_item_label
    assert _is_trivial_item_label("Miecz ognia Ignis") is False
    assert _is_trivial_item_label("Zwój teleportacji") is False
    assert _is_trivial_item_label("Amulet ochrony") is False
