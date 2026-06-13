"""TDD: #553 (HF-11) — talk_to_npc beat auto-complete in the LIVE narrative tor.

Root cause: _auto_complete_beats_by_mechanic lives in turn_pipeline.process_v2_turn,
which is never called by the live tor (game_engine.run_narrative_turn → api/turns.py).
So talk_to_npc beats only completed via the LLM [BEAT_COMPLETE] tag.

Fix: campaign_plan_runtime.auto_complete_talk_to_npc detects NPC engagement from the
real live-tor signals (button DIALOGUE key OR free-text scene-NPC keyword match) and
fires auto_complete_beats_by_event('talk_to_npc', engaged_key).
"""
import json
import sqlite3
import sys

sys.path.insert(0, "/app")


def _make_db(plan_dict, campaign_id=1, scene_npcs=None, location_key="brzezino"):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY,
            gm_plan_json TEXT,
            current_act_index INTEGER DEFAULT 0
        );
        CREATE TABLE campaign_turns (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER,
            turn_number INTEGER DEFAULT 0
        );
        CREATE TABLE location_npc_assignments (
            id INTEGER PRIMARY KEY,
            location_key TEXT,
            npc_key TEXT,
            assignment_type TEXT DEFAULT 'resident',
            is_active INTEGER DEFAULT 1
        );
    """)
    conn.execute(
        "INSERT INTO campaigns VALUES (?, ?, 0)", (campaign_id, json.dumps(plan_dict))
    )
    for npc_key in (scene_npcs or []):
        conn.execute(
            "INSERT INTO location_npc_assignments (location_key, npc_key) VALUES (?, ?)",
            (location_key, npc_key),
        )
    conn.commit()
    return conn


def _talk_plan(objective_value=""):
    return {
        "acts": [{
            "act_index": 0,
            "key_beats": [{
                "beat_key": "first_merchant",
                "objective_type": "talk_to_npc",
                "objective_value": objective_value,
            }]
        }]
    }


# ─── Button DIALOGUE path ────────────────────────────────────────────────────

def test_button_dialogue_completes_wildcard_beat():
    """text='DIALOGUE:soltys_brzezino' → dialogue_npc_key carries the key → beat completes."""
    from app.services.campaign_plan_runtime import auto_complete_talk_to_npc, get_plan

    conn = _make_db(_talk_plan(), scene_npcs=["soltys_brzezino"])

    ok = auto_complete_talk_to_npc(
        1, "DIALOGUE:soltys_brzezino", "brzezino", "soltys_brzezino", 3, conn
    )
    assert ok is True
    beat = get_plan(1, conn)["acts"][0]["key_beats"][0]
    assert beat.get("visited") is True


# ─── Free-text path with Polish diacritics ───────────────────────────────────

def test_free_text_polish_diacritics_matches_scene_npc():
    """'rozmawiam z sołtysem' (ł) must match scene NPC key 'soltys_brzezino' (l)."""
    from app.services.campaign_plan_runtime import auto_complete_talk_to_npc, get_plan

    conn = _make_db(
        _talk_plan(),
        scene_npcs=["soltys_brzezino", "kowal_brzezino", "zielarka_brzezino"],
    )

    ok = auto_complete_talk_to_npc(
        1, "Wracam i rozmawiam z sołtysem o nagrodzie.", "brzezino", None, 4, conn
    )
    assert ok is True, "diacritic-normalized 'soltys' token must match"
    beat = get_plan(1, conn)["acts"][0]["key_beats"][0]
    assert beat.get("visited") is True


def test_free_text_no_npc_mention_no_completion():
    """Player text without any scene-NPC token → beat stays unvisited."""
    from app.services.campaign_plan_runtime import auto_complete_talk_to_npc, get_plan

    conn = _make_db(_talk_plan(), scene_npcs=["soltys_brzezino", "kowal_brzezino"])

    ok = auto_complete_talk_to_npc(
        1, "Rozglądam się po lesie i idę dalej.", "brzezino", None, 2, conn
    )
    assert ok is False
    beat = get_plan(1, conn)["acts"][0]["key_beats"][0]
    assert beat.get("visited") is None


# ─── Named objective (non-wildcard) ──────────────────────────────────────────

def test_named_beat_only_matches_correct_npc():
    """objective_value='kowal' → only kowal engagement completes it, not soltys."""
    from app.services.campaign_plan_runtime import auto_complete_talk_to_npc, get_plan

    conn = _make_db(
        _talk_plan(objective_value="kowal"),
        scene_npcs=["soltys_brzezino", "kowal_brzezino"],
    )

    # Wrong NPC — must NOT complete
    auto_complete_talk_to_npc(1, "rozmawiam z sołtysem", "brzezino", None, 2, conn)
    assert get_plan(1, conn)["acts"][0]["key_beats"][0].get("visited") is None

    # Correct NPC — completes
    ok = auto_complete_talk_to_npc(1, "rozmawiam z kowalem", "brzezino", None, 3, conn)
    assert ok is True
    assert get_plan(1, conn)["acts"][0]["key_beats"][0].get("visited") is True


# ─── Idempotency ─────────────────────────────────────────────────────────────

def test_already_visited_beat_no_double_complete():
    """Second engagement on an already-visited beat returns False, no error."""
    from app.services.campaign_plan_runtime import auto_complete_talk_to_npc, get_plan

    conn = _make_db(_talk_plan(), scene_npcs=["soltys_brzezino"])

    assert auto_complete_talk_to_npc(1, None, "brzezino", "soltys_brzezino", 3, conn) is True
    # Second call — already visited
    assert auto_complete_talk_to_npc(1, None, "brzezino", "soltys_brzezino", 4, conn) is False
    beat = get_plan(1, conn)["acts"][0]["key_beats"][0]
    assert beat.get("visited") is True
    assert beat.get("visited_at_turn") == 3  # not overwritten by the second call
