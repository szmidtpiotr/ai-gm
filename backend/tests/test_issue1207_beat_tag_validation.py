"""TDD: Issue #1207 — walidacja [BEAT_COMPLETE]: LLM nie zamyka beatów mechanicznych.

Kampania 1000021 tura 6: rozmowa z Brunnem, a LLM wyemitował
[BEAT_COMPLETE:ostrozny_karczmarz] (talk_to_npc: karczmarz_jorek). Fix:
- mark_beat_visited(via_llm_tag=True) odrzuca beaty z objective_type,
- prompt-block reklamuje narratorowi tylko beaty domykalne narracyjnie.
"""
import json
import sys
import sqlite3

sys.path.insert(0, "/app")


def _make_db(plan):
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY, gm_plan_json TEXT
        );
    """)
    db.execute(
        "INSERT INTO campaigns (id, gm_plan_json) VALUES (1, ?)",
        (json.dumps(plan, ensure_ascii=False),),
    )
    db.commit()
    return db


def _plan():
    return {
        "title": "T",
        "active_act": 1,
        "acts": [
            {
                "number": 1,
                "key_beats": [
                    {"beat_key": "gadka_z_karczmarzem", "objective_type": "talk_to_npc",
                     "objective_value": "karczmarz_jorek", "optional": True},
                    {"beat_key": "wizyta_w_kuzni", "objective_type": "visit_location",
                     "objective_value": "kuznia", "optional": False},
                    {"beat_key": "szepty", "objective_type": None,
                     "objective_value": None, "optional": False, "narrative_close": True},
                    {"beat_key": "nastroj_wsi", "optional": False},
                ],
            }
        ],
    }


# ─── mark_beat_visited(via_llm_tag=True) ──────────────────────────────────────

def test_llm_tag_rejected_for_objective_beat():
    from app.services.campaign_plan_runtime import mark_beat_visited, get_plan
    db = _make_db(_plan())

    assert mark_beat_visited(1, "gadka_z_karczmarzem", 6, db, via_llm_tag=True) is False
    assert mark_beat_visited(1, "wizyta_w_kuzni", 6, db, via_llm_tag=True) is False

    plan = get_plan(1, db)
    beats = {b["beat_key"]: b for b in plan["acts"][0]["key_beats"]}
    assert not beats["gadka_z_karczmarzem"].get("visited"), \
        "talk_to_npc nie może być zamknięty tagiem LLM"
    assert not beats["wizyta_w_kuzni"].get("visited"), \
        "visit_location nie może być zamknięty tagiem LLM"


def test_llm_tag_allowed_for_narrative_beat():
    from app.services.campaign_plan_runtime import mark_beat_visited, get_plan
    db = _make_db(_plan())

    assert mark_beat_visited(1, "szepty", 6, db, via_llm_tag=True) is True
    plan = get_plan(1, db)
    beats = {b["beat_key"]: b for b in plan["acts"][0]["key_beats"]}
    assert beats["szepty"]["visited"] is True
    assert beats["szepty"]["visited_at_turn"] == 6


def test_llm_tag_allowed_for_beat_without_objective_type_field():
    from app.services.campaign_plan_runtime import mark_beat_visited, get_plan
    db = _make_db(_plan())
    assert mark_beat_visited(1, "nastroj_wsi", 3, db, via_llm_tag=True) is True
    plan = get_plan(1, db)
    beats = {b["beat_key"]: b for b in plan["acts"][0]["key_beats"]}
    assert beats["nastroj_wsi"]["visited"] is True


def test_mechanical_path_still_closes_objective_beats():
    """via_llm_tag=False (domyślne, ścieżki mechaniczne/admin) — bez zmian."""
    from app.services.campaign_plan_runtime import mark_beat_visited, get_plan
    db = _make_db(_plan())
    assert mark_beat_visited(1, "gadka_z_karczmarzem", 6, db) is True
    plan = get_plan(1, db)
    beats = {b["beat_key"]: b for b in plan["acts"][0]["key_beats"]}
    assert beats["gadka_z_karczmarzem"]["visited"] is True


def test_already_visited_returns_false_for_tag():
    from app.services.campaign_plan_runtime import mark_beat_visited
    db = _make_db(_plan())
    assert mark_beat_visited(1, "szepty", 6, db, via_llm_tag=True) is True
    assert mark_beat_visited(1, "szepty", 7, db, via_llm_tag=True) is False, \
        "powtórzony tag = brak ponownego zaliczenia (i brak ponownego XP u callera)"


# ─── prompt block ─────────────────────────────────────────────────────────────

def test_tag_closable_keys_exclude_objective_beats():
    from app.services.campaign_plan_runtime import get_active_act_tag_closable_beat_keys
    keys = get_active_act_tag_closable_beat_keys(_plan())
    assert keys == ["szepty", "nastroj_wsi"]


def test_context_block_advertises_only_narrative_beats():
    from app.services.campaign_plan_runtime import get_beat_completion_context_block
    db = _make_db(_plan())
    block = get_beat_completion_context_block(1, db)
    assert "szepty" in block and "nastroj_wsi" in block
    assert "gadka_z_karczmarzem" not in block, \
        "beat talk_to_npc nie może być reklamowany narratorowi do zamknięcia"
    assert "wizyta_w_kuzni" not in block


def test_context_block_empty_when_only_objective_beats_open():
    from app.services.campaign_plan_runtime import get_beat_completion_context_block
    plan = _plan()
    for b in plan["acts"][0]["key_beats"]:
        if b.get("objective_type") is None and "narrative_close" not in b:
            b["visited"] = True
        if b.get("narrative_close"):
            b["visited"] = True
    db = _make_db(plan)
    assert get_beat_completion_context_block(1, db) == ""
