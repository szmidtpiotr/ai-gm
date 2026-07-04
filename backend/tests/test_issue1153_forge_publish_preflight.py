"""TDD: Issue #1153 — panel „Walidacja planu" w Kuźni pokazywał „Brak błędów",
a Opublikuj blokował 422 (required_beats/NPC sprawdzane tylko w bramce publish).

Nowy endpoint GET /templates/{id}/validate-publish odbija validate_template_publish
+ validate_winnable_plan, więc panel widzi te same bramki co przycisk Opublikuj.
"""
import json
import sys
import sqlite3

sys.path.insert(0, "/app")


def _make_db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE campaign_templates (
            id INTEGER PRIMARY KEY, title TEXT, status TEXT,
            required_npc_keys TEXT, required_beats TEXT, gm_plan_json TEXT
        );
        CREATE TABLE npcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT, is_active INTEGER DEFAULT 1
        );
    """)
    return db


def _plan(beats):
    return json.dumps({
        "acts": [{
            "number": 1,
            "key_beats": [{"beat_key": b, "summary": b, "optional": False} for b in beats],
        }]
    })


def test_stale_placeholder_beat_reported_missing():
    """Scenariusz „Żar z Gasnącej Kuźni": required_beats=['start_beat'],
    plan ma tylko realne beaty → missing_beats=['start_beat']."""
    from app.routers.adventure_forge import validate_template_publish
    db = _make_db()
    db.execute("INSERT INTO npcs (key) VALUES ('brunn')")
    db.execute(
        "INSERT INTO campaign_templates (id,title,status,required_npc_keys,required_beats,gm_plan_json) "
        "VALUES (132,'Żar','review','[\"brunn\"]','[\"start_beat\"]',?)",
        (_plan(["przybycie_do_karczmy", "ponowne_rozpalenie_kuzni"]),),
    )
    db.commit()
    res = validate_template_publish(132, db)
    assert res["ok"] is False
    assert res["missing_beats"] == ["start_beat"]
    assert res["missing_npcs"] == []


def test_matching_required_beats_pass():
    from app.routers.adventure_forge import validate_template_publish
    db = _make_db()
    db.execute("INSERT INTO npcs (key) VALUES ('brunn')")
    db.execute(
        "INSERT INTO campaign_templates (id,title,status,required_npc_keys,required_beats,gm_plan_json) "
        "VALUES (1,'T','review','[\"brunn\"]','[\"przybycie_do_karczmy\"]',?)",
        (_plan(["przybycie_do_karczmy"]),),
    )
    db.commit()
    res = validate_template_publish(1, db)
    assert res["ok"] is True
    assert res["missing_beats"] == []


def test_inactive_npc_reported_missing():
    from app.routers.adventure_forge import validate_template_publish
    db = _make_db()
    db.execute("INSERT INTO npcs (key, is_active) VALUES ('ghost', 0)")
    db.execute(
        "INSERT INTO campaign_templates (id,title,status,required_npc_keys,required_beats,gm_plan_json) "
        "VALUES (2,'T','review','[\"ghost\"]','[]',?)",
        (_plan(["a"]),),
    )
    db.commit()
    res = validate_template_publish(2, db)
    assert res["ok"] is False
    assert res["missing_npcs"] == ["ghost"]


def test_plan_beat_keys_handles_string_beats():
    from app.routers.adventure_forge import _plan_beat_keys
    plan = {"acts": [{"key_beats": ["plain_string_beat", {"beat_key": "dict_beat"}]}]}
    keys = _plan_beat_keys(plan)
    assert "plain_string_beat" in keys and "dict_beat" in keys
