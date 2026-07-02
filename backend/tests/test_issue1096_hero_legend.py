"""TDD: Issue #1096 (warstwa 2) — Hero Legend: kumulatywny, spłaszczony digest
całego życia bohatera (lazy-regenerowany przy tworzeniu planu)."""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ─── Helpers ────────────────────────────────────────────────────────────────


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY,
            name TEXT,
            sheet_json TEXT,
            legend_digest TEXT,
            legend_digest_count INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE character_campaign_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            campaign_id INTEGER NOT NULL,
            outcome TEXT NOT NULL DEFAULT 'active',
            chapter_summary TEXT,
            xp_earned INTEGER NOT NULL DEFAULT 0,
            gold_at_end INTEGER NOT NULL DEFAULT 0,
            turns_count INTEGER NOT NULL DEFAULT 0,
            completed_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    return conn


def _seed_char(conn, character_id=1, name="Alaric"):
    conn.execute(
        "INSERT INTO characters (id, name, sheet_json) VALUES (?, ?, '{}')",
        (character_id, name),
    )
    conn.commit()


def _seed_history(conn, character_id=1, n=3):
    for i in range(1, n + 1):
        conn.execute("""
            INSERT INTO character_campaign_history
            (character_id, campaign_id, outcome, chapter_summary, turns_count, completed_at)
            VALUES (?, ?, 'victory', ?, 10, datetime('now', ? || ' days'))
        """, (character_id, 100 + i,
              f"Podsumowanie rozdziału {i}: bohater pokonał smoka nr {i}.",
              str(i - n - 1)))
    conn.commit()


# ─── Test 1: refresh_hero_legend generates + stores digest ───────────────────


def test_refresh_hero_legend_generates_and_stores_digest(monkeypatch):
    """refresh_hero_legend folds ALL chapters into a bounded digest saved on characters."""
    from app.services import chapter_summary_service as svc

    monkeypatch.setattr(svc, "get_user_llm_settings_full", lambda uid: {})
    calls = {"n": 0}

    def _fake_chat(messages, **kw):
        calls["n"] += 1
        # Verify all chapters were provided to the LLM (nr 1..5 all present)
        joined = " ".join(m["content"] for m in messages)
        assert "smoka nr 1" in joined, "oldest chapter must be in digest prompt"
        assert "smoka nr 5" in joined, "newest chapter must be in digest prompt"
        return "LEGENDA: Alaric, pogromca pięciu smoków, znany w całej krainie."

    monkeypatch.setattr(svc, "generate_chat", _fake_chat)

    conn = _make_db()
    _seed_char(conn, 1)
    _seed_history(conn, 1, n=5)

    digest = svc.refresh_hero_legend(conn, character_id=1, user_id=1)

    assert digest, "expected a non-empty digest"
    assert "pogromca" in digest
    assert calls["n"] == 1, "LLM should be called exactly once"

    # persisted
    row = conn.execute(
        "SELECT legend_digest, legend_digest_count FROM characters WHERE id = 1"
    ).fetchone()
    assert row["legend_digest"] == digest
    assert row["legend_digest_count"] == 5, "count should equal folded chapters"


# ─── Test 2: refresh is skipped when digest is fresh ─────────────────────────


def test_refresh_hero_legend_skips_when_fresh(monkeypatch):
    """When legend_digest_count already equals chapter count, no LLM call happens."""
    from app.services import chapter_summary_service as svc

    monkeypatch.setattr(svc, "get_user_llm_settings_full", lambda uid: {})
    calls = {"n": 0}

    def _fake_chat(messages, **kw):
        calls["n"] += 1
        return "SHOULD NOT BE CALLED"

    monkeypatch.setattr(svc, "generate_chat", _fake_chat)

    conn = _make_db()
    _seed_char(conn, 1)
    _seed_history(conn, 1, n=3)
    # pre-store a fresh digest matching count=3
    conn.execute(
        "UPDATE characters SET legend_digest = 'Stara legenda', legend_digest_count = 3 WHERE id = 1"
    )
    conn.commit()

    digest = svc.refresh_hero_legend(conn, character_id=1, user_id=1)

    assert digest == "Stara legenda"
    assert calls["n"] == 0, "LLM must not be called when digest is fresh"


# ─── Test 3: refresh regenerates when a new chapter appears (stale) ──────────


def test_refresh_hero_legend_regenerates_when_stale(monkeypatch):
    """Adding a new campaign makes the digest stale → LLM is called again."""
    from app.services import chapter_summary_service as svc

    monkeypatch.setattr(svc, "get_user_llm_settings_full", lambda uid: {})
    calls = {"n": 0}
    monkeypatch.setattr(svc, "generate_chat",
                        lambda messages, **kw: (calls.__setitem__("n", calls["n"] + 1) or "NOWA LEGENDA"))

    conn = _make_db()
    _seed_char(conn, 1)
    _seed_history(conn, 1, n=3)
    conn.execute(
        "UPDATE characters SET legend_digest = 'Stara', legend_digest_count = 3 WHERE id = 1"
    )
    conn.commit()

    # 4th campaign completes → stale
    conn.execute("""
        INSERT INTO character_campaign_history
        (character_id, campaign_id, outcome, chapter_summary, turns_count, completed_at)
        VALUES (1, 999, 'death', 'Rozdział 4: bohater poległ.', 5, datetime('now'))
    """)
    conn.commit()

    digest = svc.refresh_hero_legend(conn, character_id=1, user_id=1)
    assert digest == "NOWA LEGENDA"
    assert calls["n"] == 1
    row = conn.execute("SELECT legend_digest_count FROM characters WHERE id = 1").fetchone()
    assert row["legend_digest_count"] == 4


# ─── Test 4: get_hero_chronicle is two-tier (digest + recent verbatim) ───────


def test_get_hero_chronicle_two_tier(monkeypatch):
    """get_hero_chronicle returns cached legend digest PLUS recent verbatim chapters."""
    from app.services.chapter_summary_service import get_hero_chronicle

    conn = _make_db()
    _seed_char(conn, 1)
    _seed_history(conn, 1, n=5)
    conn.execute(
        "UPDATE characters SET legend_digest = 'Alaric pokonał pięć smoków przez lata.', legend_digest_count = 5 WHERE id = 1"
    )
    conn.commit()

    result = get_hero_chronicle(conn, character_id=1, limit=2)
    assert result, "expected non-empty chronicle"
    # tier 1: whole-life digest present
    assert "pięć smoków" in result, "legend digest missing from chronicle"
    assert "LEGENDA" in result.upper()
    # tier 2: recent verbatim (last 2 only)
    assert "smoka nr 5" in result or "smoka nr 4" in result
    assert result.count("smoka nr") <= 3  # digest mentions "pięć", verbatim last 2


# ─── Test 5: get_hero_chronicle read path does NOT call LLM ──────────────────


def test_get_hero_chronicle_read_only_no_llm(monkeypatch):
    """Narrator path (regenerate default False) must never invoke the LLM."""
    from app.services import chapter_summary_service as svc

    def _boom(*a, **k):
        raise AssertionError("get_hero_chronicle must not call the LLM on read")

    monkeypatch.setattr(svc, "generate_chat", _boom)

    conn = _make_db()
    _seed_char(conn, 1)
    _seed_history(conn, 1, n=3)
    conn.execute(
        "UPDATE characters SET legend_digest = 'Cicha legenda', legend_digest_count = 3 WHERE id = 1"
    )
    conn.commit()

    result = svc.get_hero_chronicle(conn, character_id=1, limit=2)
    assert "Cicha legenda" in result


# ─── Test 6: lazy regenerate via get_hero_chronicle(regenerate=True) ─────────


def test_get_hero_chronicle_lazy_regenerate(monkeypatch):
    """With regenerate=True + user_id, get_hero_chronicle refreshes a stale digest first."""
    from app.services import chapter_summary_service as svc

    monkeypatch.setattr(svc, "get_user_llm_settings_full", lambda uid: {})
    monkeypatch.setattr(svc, "generate_chat",
                        lambda messages, **kw: "ODSWIEZONA LEGENDA smoków")

    conn = _make_db()
    _seed_char(conn, 1)
    _seed_history(conn, 1, n=2)
    # no digest yet → stale

    result = svc.get_hero_chronicle(conn, character_id=1, limit=2,
                                    user_id=1, regenerate=True)
    assert "ODSWIEZONA LEGENDA" in result
    # digest persisted
    row = conn.execute("SELECT legend_digest_count FROM characters WHERE id = 1").fetchone()
    assert row["legend_digest_count"] == 2


# ─── Test 7: no regression — new hero, no history, no digest ─────────────────


def test_get_hero_chronicle_empty_for_new_hero():
    """First-campaign hero: no history, no digest → empty string, no error."""
    from app.services.chapter_summary_service import get_hero_chronicle

    conn = _make_db()
    _seed_char(conn, 7, name="Nowy")
    result = get_hero_chronicle(conn, character_id=7, limit=2)
    assert result == ""


def test_refresh_hero_legend_empty_for_new_hero(monkeypatch):
    """refresh on a hero with zero completed chapters returns '' without LLM."""
    from app.services import chapter_summary_service as svc

    monkeypatch.setattr(svc, "get_user_llm_settings_full", lambda uid: {})
    monkeypatch.setattr(svc, "generate_chat",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no LLM for empty")))

    conn = _make_db()
    _seed_char(conn, 7)
    assert svc.refresh_hero_legend(conn, character_id=7, user_id=1) == ""
