"""G8 #1472 — consistency cleanup (Faza AUDIT).

Covers the two mandated tests:
  * test_medicine_uses_wis  — the single fallback map governs medicine on WIS
  * test_skill_test_dc_clamped — [SKILL_TEST:key:DC:n] clamps DC to the 8/12/16/20/24 scale
"""
import sys
import sqlite3
import pytest

sys.path.insert(0, "/app")
from _fixtures_schema import table_sql

import app.services.skill_service as skill_service
from app.services.skill_service import _skill_stat, _skill_label, intercept_skill_test_tag


# ─── test_medicine_uses_wis ──────────────────────────────────────────────────

def test_medicine_uses_wis(monkeypatch):
    """Fallback map (used when the DB catalog is unavailable) governs medicine on WIS,
    not INT. One dictionary is the single source for both stat and label."""
    # Force the DB lookup to miss so the hardcoded fallback is exercised.
    monkeypatch.setattr(skill_service, "_query_skill_from_db", lambda key: None)

    assert _skill_stat("medicine") == "WIS"
    assert _skill_label("medicine") == "Medycyna"
    # Single dict — the tuple carries both stat and label.
    assert skill_service._SKILL_FALLBACK["medicine"] == ("WIS", "Medycyna")
    # Unknown skill still degrades safely.
    assert _skill_stat("nonexistent_skill") == "INT"


# ─── test_skill_test_dc_clamped ──────────────────────────────────────────────

@pytest.fixture()
def mem_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        table_sql("game_config_skills") + """
        INSERT OR IGNORE INTO game_config_skills (key, label, linked_stat, sort_order)
            VALUES ('perception','Percepcja','WIS',0);
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
    """
    )
    yield conn
    conn.close()


@pytest.mark.parametrize(
    "raw_dc,expected",
    [
        (17, 16),   # 17 → nearest 16
        (22, 20),   # 22 → nearest 20
        (9, 8),     # 9 → nearest 8
        (30, 24),   # above scale → 24
        (12, 12),   # already on-scale → unchanged
    ],
)
def test_skill_test_dc_clamped(mem_conn, raw_dc, expected):
    """A [SKILL_TEST:key:DC:n] tag whose DC is off the Easy/Medium/Hard/Extreme/Legendary
    scale (8/12/16/20/24) is clamped to the nearest allowed value before the pending
    dice card is built."""
    prose = f"Rozejrzyj się. [SKILL_TEST:perception:DC:{raw_dc}]"
    cleaned, pending = intercept_skill_test_tag(
        prose, conn=mem_conn, campaign_id=1, character_id=1,
    )
    assert pending is not None
    assert pending["counter"]["dc"] == expected, (
        f"DC {raw_dc} powinno zostać sklamrowane do {expected}, "
        f"dostaliśmy {pending['counter']['dc']}"
    )
    assert "[SKILL_TEST:" not in cleaned
