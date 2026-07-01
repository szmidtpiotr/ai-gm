"""TDD: Issue #1085 — generate-plan auto-fills atmosphere/npc/beat fields from plan+idea."""
import json
import sqlite3
import sys

sys.path.insert(0, "/app")


# ─── Helpers shared by multiple tests ────────────────────────────────────────

def _make_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE campaign_ideas (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            premise TEXT,
            tone TEXT DEFAULT '[]',
            themes TEXT DEFAULT '[]',
            difficulty TEXT DEFAULT 'Średnia',
            structured_data TEXT DEFAULT '{}',
            status TEXT DEFAULT 'draft',
            created_by TEXT DEFAULT 'test'
        )
    """)
    conn.execute("""
        CREATE TABLE campaign_templates (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            atmosphere TEXT,
            difficulty_rating INTEGER DEFAULT 3,
            adventure_idea_id INTEGER,
            required_npc_keys TEXT,
            required_beats TEXT,
            gm_plan_json TEXT,
            status TEXT DEFAULT 'draft',
            created_by TEXT DEFAULT 'test'
        )
    """)
    return conn


def _insert_idea(conn, tone=None, title="Idea"):
    tone_json = json.dumps(tone or ["dark", "mystery"], ensure_ascii=False)
    conn.execute(
        "INSERT INTO campaign_ideas (id, title, premise, tone) VALUES (1, ?, 'Premise', ?)",
        (title, tone_json),
    )
    conn.commit()


def _insert_template(conn, atmosphere="", npc_keys=None, beats=None):
    npc_json = json.dumps(npc_keys or [], ensure_ascii=False) if npc_keys is not None else None
    beats_json = json.dumps(beats or [], ensure_ascii=False) if beats is not None else None
    conn.execute(
        "INSERT INTO campaign_templates (id, title, atmosphere, required_npc_keys, required_beats) "
        "VALUES (1, 'Tpl', ?, ?, ?)",
        (atmosphere, npc_json, beats_json),
    )
    conn.commit()


# ─── Test 1: _auto_fill_plan_fields zwraca atmosphere z tone idei ─────────────

def test_auto_fill_atmosphere_from_idea_tone():
    """Gdy template.atmosphere jest puste a idea.tone = ['dark','mystery'], atmosfera = 'dark, mystery'."""
    from app.routers.adventure_forge import _auto_fill_plan_fields

    conn = _make_conn()
    _insert_idea(conn, tone=["dark", "mystery"])
    _insert_template(conn, atmosphere="")

    tpl = dict(conn.execute("SELECT * FROM campaign_templates WHERE id=1").fetchone())
    idea = dict(conn.execute("SELECT * FROM campaign_ideas WHERE id=1").fetchone())
    plan_public = {"key_npcs": [], "acts": []}

    result = _auto_fill_plan_fields(conn, tpl_id=1, tpl=tpl, idea=idea, plan_public=plan_public)

    assert result["auto_filled_atmosphere"] == "dark, mystery", (
        f"Expected 'dark, mystery', got {result['auto_filled_atmosphere']!r}"
    )
    # DB row must be updated too
    row = conn.execute("SELECT atmosphere FROM campaign_templates WHERE id=1").fetchone()
    assert row["atmosphere"] == "dark, mystery"


# ─── Test 2: atmosphere NIE nadpisuje istniejącej wartości ────────────────────

def test_auto_fill_atmosphere_does_not_overwrite_existing():
    """Jeśli template.atmosphere już ustawione, nie nadpisujemy."""
    from app.routers.adventure_forge import _auto_fill_plan_fields

    conn = _make_conn()
    _insert_idea(conn, tone=["horror"])
    _insert_template(conn, atmosphere="Stary klimat")

    tpl = dict(conn.execute("SELECT * FROM campaign_templates WHERE id=1").fetchone())
    idea = dict(conn.execute("SELECT * FROM campaign_ideas WHERE id=1").fetchone())
    plan_public = {"key_npcs": [], "acts": []}

    result = _auto_fill_plan_fields(conn, tpl_id=1, tpl=tpl, idea=idea, plan_public=plan_public)

    assert result["auto_filled_atmosphere"] == "", "Nie powinna nadpisywać istniejącego klimatu"
    row = conn.execute("SELECT atmosphere FROM campaign_templates WHERE id=1").fetchone()
    assert row["atmosphere"] == "Stary klimat"


# ─── Test 3: auto_filled_npc_keys i auto_filled_beat_keys zawsze w response ──

def test_auto_fill_returns_npc_and_beat_keys():
    """auto_filled_npc_keys i auto_filled_beat_keys muszą być w zwróconym dict."""
    from app.routers.adventure_forge import _auto_fill_plan_fields

    conn = _make_conn()
    _insert_idea(conn)
    _insert_template(conn)  # puste npc/beats

    tpl = dict(conn.execute("SELECT * FROM campaign_templates WHERE id=1").fetchone())
    idea = dict(conn.execute("SELECT * FROM campaign_ideas WHERE id=1").fetchone())
    plan_public = {
        "key_npcs": [{"key": "npc_boss", "name": "Szef"}],
        "acts": [
            {"key_beats": [{"beat_key": "beat_start", "optional": False}]}
        ],
    }

    result = _auto_fill_plan_fields(conn, tpl_id=1, tpl=tpl, idea=idea, plan_public=plan_public)

    assert "auto_filled_npc_keys" in result
    assert "auto_filled_beat_keys" in result
    assert "npc_boss" in result["auto_filled_npc_keys"]
    assert "beat_start" in result["auto_filled_beat_keys"]


# ─── Test 4: bez idei → atmosphere pozostaje puste, ale reszta działa ────────

def test_auto_fill_without_idea_no_atmosphere():
    """Bez idea (None) atmosphere nie jest auto-wypełniony."""
    from app.routers.adventure_forge import _auto_fill_plan_fields

    conn = _make_conn()
    _insert_template(conn, atmosphere="")

    tpl = dict(conn.execute("SELECT * FROM campaign_templates WHERE id=1").fetchone())
    plan_public = {"key_npcs": [], "acts": []}

    result = _auto_fill_plan_fields(conn, tpl_id=1, tpl=tpl, idea=None, plan_public=plan_public)

    assert result["auto_filled_atmosphere"] == ""
    assert "auto_filled_npc_keys" in result
    assert "auto_filled_beat_keys" in result
