"""TDD: Issue #987 — intercept_skill_test_tag must accept user_text kwarg (streaming path)."""
import sys
import sqlite3
import pytest

sys.path.insert(0, "/app")

from app.services.skill_service import intercept_skill_test_tag


@pytest.fixture()
def mem_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS game_config_skills (
            key TEXT PRIMARY KEY,
            label TEXT,
            base_stat TEXT,
            counter INTEGER DEFAULT 0
        );
        INSERT OR IGNORE INTO game_config_skills VALUES ('stealth','Skradanie','DEX',0);
        INSERT OR IGNORE INTO game_config_skills VALUES ('perception','Spostrzegawczość','WIS',0);
        CREATE TABLE IF NOT EXISTS game_sessions (
            campaign_id INTEGER PRIMARY KEY,
            session_flags TEXT DEFAULT '{}'
        );
        INSERT OR IGNORE INTO game_sessions VALUES (1, '{}');
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER,
            sheet_json TEXT DEFAULT '{}'
        );
        INSERT OR IGNORE INTO characters VALUES (1, 1, '{}');
    """)
    yield conn
    conn.close()


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_intercept_accepts_user_text_kwarg(mem_conn):
    """intercept_skill_test_tag must NOT raise TypeError when called with user_text."""
    prose = "Spróbuj się skraść! [SKILL_TEST:stealth:DC:12]"
    # Before fix this raises: TypeError: got an unexpected keyword argument 'user_text'
    try:
        cleaned, pending = intercept_skill_test_tag(
            prose,
            conn=mem_conn,
            campaign_id=1,
            character_id=1,
            user_text="Skradam się po cichu.",
        )
    except TypeError as e:
        pytest.fail(f"intercept_skill_test_tag raised TypeError with user_text kwarg: {e}")
    # Tag should be stripped from cleaned prose
    assert "[SKILL_TEST:" not in cleaned, "Tag powinien być usunięty z narracji"
    # Pending dict should exist
    assert pending is not None, "Powinien powstać pending dict dla testu umiejętności"
    assert pending.get("skill_key") == "stealth"


def test_intercept_roll_cue_not_leaked_to_narrative(mem_conn):
    """Prose must not contain raw [SKILL_TEST:...] tag after intercept."""
    prose = "Narrator asked: [SKILL_TEST:perception:DC:14] whether you notice anything."
    cleaned, pending = intercept_skill_test_tag(
        prose,
        conn=mem_conn,
        campaign_id=1,
        character_id=1,
        user_text="Rozglądam się uważnie.",
    )
    assert "[SKILL_TEST:" not in cleaned, "Tag nie może wyciekać do narracji"
    assert pending is not None
    assert pending.get("skill_key") == "perception"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_intercept_without_user_text_still_works(mem_conn):
    """Calling without user_text (old non-streaming path) must still work."""
    prose = "Spróbuj! [SKILL_TEST:stealth:DC:10]"
    cleaned, pending = intercept_skill_test_tag(
        prose,
        conn=mem_conn,
        campaign_id=1,
        character_id=1,
        # No user_text — old call site
    )
    assert "[SKILL_TEST:" not in cleaned
    assert pending is not None
    assert pending.get("skill_key") == "stealth"


def test_intercept_no_tag_returns_none_pending(mem_conn):
    """Prose without [SKILL_TEST] tag returns (prose, None) — unchanged."""
    prose = "Pogoda jest ładna dziś."
    cleaned, pending = intercept_skill_test_tag(
        prose,
        conn=mem_conn,
        campaign_id=1,
        character_id=1,
        user_text="Obserwuję otoczenie.",
    )
    assert pending is None
    assert cleaned == prose
