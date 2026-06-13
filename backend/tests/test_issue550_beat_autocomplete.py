"""TDD: #550 — beat auto-complete nie odpala przez resolve_attack + DIALOGUE.

Two problems:
1. kill_enemy beat not completed when enemy dies via /combat/resolve-attack
   (bypasses turn_pipeline._auto_complete_beats_by_mechanic).
2. talk_to_npc beat not completed when DIALOGUE action_type but NPC not found in DB
   (context["target_npc"] is None → target="" → guard fails → no event fired).

Fixes:
1. combat_service.resolve_attack() calls auto_complete_beats_by_event when dead=True.
2. turn_pipeline._auto_complete_beats_by_mechanic falls back to result["npc_key"].
"""
import json
import sqlite3
import sys

sys.path.insert(0, "/app")


def _make_plan_db(plan_dict, campaign_id=1):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY,
            gm_plan_json TEXT,
            current_act_index INTEGER DEFAULT 0
        );
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER,
            session_flags TEXT DEFAULT '{}'
        );
        CREATE TABLE campaign_turns (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER,
            turn_number INTEGER DEFAULT 0
        );
    """)
    conn.execute(
        "INSERT INTO campaigns VALUES (?, ?, 0)", (campaign_id, json.dumps(plan_dict))
    )
    conn.execute(
        "INSERT INTO game_sessions VALUES (1, ?, '{}')", (campaign_id,)
    )
    conn.commit()
    return conn


def _kill_enemy_plan():
    return {
        "acts": [{
            "act_index": 0,
            "key_beats": [{
                "beat_key": "first_combat",
                "objective_type": "kill_enemy",
                "objective_value": "",  # wildcard — any enemy kill completes it
            }]
        }]
    }


def _talk_to_npc_plan():
    return {
        "acts": [{
            "act_index": 0,
            "key_beats": [{
                "beat_key": "first_merchant",
                "objective_type": "talk_to_npc",
                "objective_value": "",  # wildcard
            }]
        }]
    }


# ─── Test 1: kill_enemy via auto_complete_beats_by_event ────────────────────

def test_kill_enemy_beat_completes_via_event():
    """auto_complete_beats_by_event fires for kill_enemy beat (wildcard objective_value)."""
    from app.services.campaign_plan_runtime import auto_complete_beats_by_event, get_plan

    conn = _make_plan_db(_kill_enemy_plan())

    result = auto_complete_beats_by_event(1, "kill_enemy", "Goblin", 1, conn)
    assert result is True, "kill_enemy event should complete the wildcard beat"

    plan = get_plan(1, conn)
    beat = plan["acts"][0]["key_beats"][0]
    assert beat.get("visited") is True, "beat.visited must be True after kill_enemy event"


def test_kill_enemy_beat_with_named_enemy():
    """auto_complete_beats_by_event fires when objective_value matches enemy name."""
    from app.services.campaign_plan_runtime import auto_complete_beats_by_event, get_plan

    plan = {
        "acts": [{
            "act_index": 0,
            "key_beats": [{
                "beat_key": "kill_boss",
                "objective_type": "kill_enemy",
                "objective_value": "Szkielet",
            }]
        }]
    }
    conn = _make_plan_db(plan)

    # Wrong enemy — should NOT complete
    result = auto_complete_beats_by_event(1, "kill_enemy", "Goblin", 1, conn)
    plan_after = get_plan(1, conn)
    assert plan_after["acts"][0]["key_beats"][0].get("visited") is None

    # Correct enemy — should complete
    result2 = auto_complete_beats_by_event(1, "kill_enemy", "Szkielet Wojownik", 1, conn)
    assert result2 is True
    plan_after2 = get_plan(1, conn)
    assert plan_after2["acts"][0]["key_beats"][0].get("visited") is True


# ─── Test 2: DIALOGUE fallback to result["npc_key"] ─────────────────────────

def test_dialogue_beat_completes_via_result_npc_key():
    """_auto_complete_beats_by_mechanic uses result['npc_key'] when target_npc is None."""
    from app.services.turn_pipeline import _auto_complete_beats_by_mechanic
    from app.services.campaign_plan_runtime import get_plan

    conn = _make_plan_db(_talk_to_npc_plan())

    # context["target_npc"] is None (NPC not found in DB by key)
    context = {}
    result = {
        "outcome": "SUCCESS",
        "npc_key": "marta_handlarka",  # key from intent parser
        "npc_name": "",  # empty because NPC not in DB
    }

    _auto_complete_beats_by_mechanic("DIALOGUE", result, context, 1, 1, conn)

    plan = get_plan(1, conn)
    beat = plan["acts"][0]["key_beats"][0]
    assert beat.get("visited") is True, (
        "talk_to_npc beat should complete via result['npc_key'] fallback"
    )


def test_dialogue_beat_completes_via_context_target_npc():
    """_auto_complete_beats_by_mechanic uses context['target_npc'] when available (original path)."""
    from app.services.turn_pipeline import _auto_complete_beats_by_mechanic
    from app.services.campaign_plan_runtime import get_plan

    conn = _make_plan_db(_talk_to_npc_plan())

    context = {
        "target_npc": {"label": "Marta Handlarka", "key": "marta_handlarka"},
    }
    result = {
        "outcome": "SUCCESS",
        "npc_key": "marta_handlarka",
        "npc_name": "Marta Handlarka",
    }

    _auto_complete_beats_by_mechanic("DIALOGUE", result, context, 1, 1, conn)

    plan = get_plan(1, conn)
    beat = plan["acts"][0]["key_beats"][0]
    assert beat.get("visited") is True


def test_dialogue_beat_not_double_completed():
    """Already visited beat stays visited, no error on second call."""
    from app.services.turn_pipeline import _auto_complete_beats_by_mechanic
    from app.services.campaign_plan_runtime import get_plan

    plan = {
        "acts": [{
            "act_index": 0,
            "key_beats": [{
                "beat_key": "first_merchant",
                "objective_type": "talk_to_npc",
                "objective_value": "",
                "visited": True,
            }]
        }]
    }
    conn = _make_plan_db(plan)

    context = {}
    result = {"npc_key": "jakis_npc", "npc_name": ""}

    _auto_complete_beats_by_mechanic("DIALOGUE", result, context, 1, 1, conn)
    plan_after = get_plan(1, conn)
    # Still visited, no crash
    assert plan_after["acts"][0]["key_beats"][0].get("visited") is True
