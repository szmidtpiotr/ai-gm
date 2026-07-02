"""TDD: Issue #1096 (1B) — abandonment scar: porzucone/skasowane kampanie
zostawiają krótką notkę 'niedokończone sprawy' w LEGENDZIE (nie w rozdziałach)."""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


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
            abandonment_note TEXT,
            xp_earned INTEGER NOT NULL DEFAULT 0,
            gold_at_end INTEGER NOT NULL DEFAULT 0,
            turns_count INTEGER NOT NULL DEFAULT 0,
            completed_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    return conn


def _seed_char(conn, cid=1, name="Alaric"):
    conn.execute("INSERT INTO characters (id, name, sheet_json) VALUES (?, ?, '{}')", (cid, name))
    conn.commit()


# ─── Test 1: threshold gate ──────────────────────────────────────────────────


def test_should_generate_abandonment_note_threshold():
    from app.services.chapter_summary_service import (
        should_generate_abandonment_note,
        ABANDON_MIN_TURNS,
    )
    assert should_generate_abandonment_note(0) is False
    assert should_generate_abandonment_note(ABANDON_MIN_TURNS - 1) is False
    assert should_generate_abandonment_note(ABANDON_MIN_TURNS) is True
    assert should_generate_abandonment_note(ABANDON_MIN_TURNS + 10) is True


# ─── Test 2: prompt frames unfinished business ──────────────────────────────


def test_build_abandonment_prompt_frames_unfinished():
    from app.services.chapter_summary_service import _build_abandonment_prompt
    p = _build_abandonment_prompt("Alaric", "Cienie nad Wilczburgiem",
                                  "Gracz: idę do lasu\nGM: mrok gęstnieje")
    low = p.lower()
    assert "alaric" in low
    assert "wilczburg" in low
    # framing must ask about what was left unfinished / who was let down
    assert "niedokończ" in low or "porzuc" in low or "zawiód" in low


# ─── Test 3: generate note via LLM (mock) ───────────────────────────────────


def test_generate_abandonment_note_text(monkeypatch):
    from app.services import chapter_summary_service as svc
    monkeypatch.setattr(svc, "get_user_llm_settings_full", lambda uid: {})
    captured = {}

    def _fake(messages, **kw):
        captured["u"] = " ".join(m["content"] for m in messages)
        return "Alaric porzucił obronę Wilczburga; mieszkańcy zapamiętali jego ucieczkę."

    monkeypatch.setattr(svc, "generate_chat", _fake)
    note = svc._generate_abandonment_note_text(
        "Alaric", "Cienie nad Wilczburgiem", "Gracz: uciekam\nGM: brama pada", user_id=1
    )
    assert "porzucił" in note
    assert "Wilczburg" in captured["u"]


# ─── Test 4: legend fold INCLUDES abandonment as a scar ─────────────────────


def test_refresh_legend_folds_abandonment_note(monkeypatch):
    from app.services import chapter_summary_service as svc
    monkeypatch.setattr(svc, "get_user_llm_settings_full", lambda uid: {})
    captured = {}

    def _fake(messages, **kw):
        captured["u"] = " ".join(m["content"] for m in messages)
        return "LEGENDA Alarica"

    monkeypatch.setattr(svc, "generate_chat", _fake)

    conn = _make_db()
    _seed_char(conn, 1)
    # one victory (chapter), one abandoned (note only)
    conn.execute("""INSERT INTO character_campaign_history
        (character_id, campaign_id, outcome, chapter_summary, completed_at)
        VALUES (1, 10, 'victory', 'Pokonał smoka w Górach Kruka.', datetime('now','-2 days'))""")
    conn.execute("""INSERT INTO character_campaign_history
        (character_id, campaign_id, outcome, abandonment_note, completed_at)
        VALUES (1, 11, 'abandoned', 'Porzucił obronę Wilczburga; miasto go zapamiętało.', datetime('now','-1 days'))""")
    conn.commit()

    digest = svc.refresh_hero_legend(conn, character_id=1, user_id=1)
    assert digest == "LEGENDA Alarica"
    prompt = captured["u"]
    assert "smoka w Górach Kruka" in prompt, "victory chapter must be in legend fold"
    assert "obronę Wilczburga" in prompt, "abandonment note must be in legend fold"
    assert "PORZUC" in prompt.upper(), "abandonment must be framed as a scar"

    # both sources counted → digest_count == 2
    row = conn.execute("SELECT legend_digest_count FROM characters WHERE id=1").fetchone()
    assert row["legend_digest_count"] == 2


# ─── Test 5: abandonment note NEVER appears in tier-2 verbatim ───────────────


def test_abandonment_not_in_verbatim_tier():
    from app.services.chapter_summary_service import get_hero_chronicle
    conn = _make_db()
    _seed_char(conn, 1)
    conn.execute("""INSERT INTO character_campaign_history
        (character_id, campaign_id, outcome, abandonment_note, completed_at)
        VALUES (1, 11, 'abandoned', 'SEKRETNA-NOTKA-PORZUCENIA', datetime('now'))""")
    conn.execute("UPDATE characters SET legend_digest='Legenda z rysą', legend_digest_count=1 WHERE id=1")
    conn.commit()

    result = get_hero_chronicle(conn, character_id=1, limit=2)
    # tier-1 digest shows
    assert "Legenda z rysą" in result
    # tier-2 verbatim must NOT contain the raw abandonment note
    assert "SEKRETNA-NOTKA-PORZUCENIA" not in result
    assert "OSTATNIE ROZDZIAŁY" not in result  # no verbatim chapters at all


# ─── Test 6: abandonment bumps staleness → triggers regen ───────────────────


def test_abandonment_bumps_legend_staleness(monkeypatch):
    from app.services import chapter_summary_service as svc
    monkeypatch.setattr(svc, "get_user_llm_settings_full", lambda uid: {})
    calls = {"n": 0}
    monkeypatch.setattr(svc, "generate_chat",
                        lambda messages, **kw: (calls.__setitem__("n", calls["n"] + 1) or "NOWA"))

    conn = _make_db()
    _seed_char(conn, 1)
    conn.execute("""INSERT INTO character_campaign_history
        (character_id, campaign_id, outcome, chapter_summary, completed_at)
        VALUES (1, 10, 'victory', 'Rozdział pierwszy.', datetime('now','-2 days'))""")
    conn.execute("UPDATE characters SET legend_digest='Stara', legend_digest_count=1 WHERE id=1")
    conn.commit()

    # add an abandonment → sources now 2 → stale
    conn.execute("""INSERT INTO character_campaign_history
        (character_id, campaign_id, outcome, abandonment_note, completed_at)
        VALUES (1, 11, 'abandoned', 'Porzucił questa.', datetime('now'))""")
    conn.commit()

    digest = svc.refresh_hero_legend(conn, character_id=1, user_id=1)
    assert digest == "NOWA"
    assert calls["n"] == 1
    assert conn.execute("SELECT legend_digest_count FROM characters WHERE id=1").fetchone()[0] == 2


# ─── Test 7: no regression — legend still works without abandonment column ────


def test_legend_still_works_without_abandonment_column(monkeypatch):
    """Older DB schema (no abandonment_note) must not break the legend fold."""
    from app.services import chapter_summary_service as svc
    monkeypatch.setattr(svc, "get_user_llm_settings_full", lambda uid: {})
    monkeypatch.setattr(svc, "generate_chat", lambda messages, **kw: "LEGENDA")

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE characters (id INTEGER PRIMARY KEY, name TEXT, sheet_json TEXT,
        legend_digest TEXT, legend_digest_count INTEGER NOT NULL DEFAULT 0)""")
    conn.execute("""CREATE TABLE character_campaign_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER, campaign_id INTEGER,
        outcome TEXT, chapter_summary TEXT, completed_at TEXT)""")  # NO abandonment_note
    conn.execute("INSERT INTO characters (id, name, sheet_json) VALUES (1,'X','{}')")
    conn.execute("""INSERT INTO character_campaign_history
        (character_id, campaign_id, outcome, chapter_summary, completed_at)
        VALUES (1, 10, 'victory', 'Rozdział.', datetime('now'))""")
    conn.commit()

    digest = svc.refresh_hero_legend(conn, character_id=1, user_id=1)
    assert digest == "LEGENDA"
