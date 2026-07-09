"""TDD: #1300 — finale never opens when plan beats strand on unmaterialized entities.

Symptom: player closed every main quest but got no campaign-completion modal.

Root cause: the finale gate (`maybe_complete_campaign`) requires `is_plan_complete`
(every act flipped `completed`). Acts advance only when objective-typed beats close
via event hooks, but those hooks match plan entity keys (talk_to_npc / visit_location /
find_item) that were never registered as real game entities — same class of gap as
#1284 for enemies. So the act pointer strands, `is_plan_complete` stays False, and a
finished story is locked out of its ending.

Two fixes verified here:
  1. `auto_complete_talk_to_npc` — plan-aware fallback: match player text against the
     talk_to_npc beats' own `objective_value` keys even when the NPC is absent from
     `location_npc_assignments`.
  2. `maybe_complete_campaign` — quest-driven finale fallback: when every main quest is
     resolved AND completed_main >= num_acts, open the finale despite stranded beats.
"""
import json
import sqlite3
import sys

sys.path.insert(0, "/app")

CID = 777001  # high id: keep best-effort write_game_event out of real campaign rows


# ─── Fix 1: plan-aware talk_to_npc fallback ──────────────────────────────────

def _make_talk_db(objective_value, campaign_id=CID):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, gm_plan_json TEXT,
                                current_act_index INTEGER DEFAULT 0);
        CREATE TABLE campaign_turns (id INTEGER PRIMARY KEY, campaign_id INTEGER,
                                     turn_number INTEGER DEFAULT 0);
        CREATE TABLE location_npc_assignments (id INTEGER PRIMARY KEY, location_key TEXT,
                                               npc_key TEXT, is_active INTEGER DEFAULT 1);
        """
    )
    plan = {
        "active_act": 1,
        "acts": [{
            "act_index": 0,
            "key_beats": [{
                "beat_key": "brunn_prosi_o_pomoc",
                "objective_type": "talk_to_npc",
                "objective_value": objective_value,
            }],
        }],
    }
    conn.execute("INSERT INTO campaigns VALUES (?, ?, 0)", (campaign_id, json.dumps(plan)))
    conn.commit()
    return conn


def test_talk_beat_completes_from_plan_key_without_assignment():
    """NPC absent from location_npc_assignments — free text still closes the beat
    by matching the beat's own objective_value key (#1300 fallback)."""
    from app.services.campaign_plan_runtime import auto_complete_talk_to_npc, get_plan

    conn = _make_talk_db("brunn_zelaznoreki")  # NO location_npc_assignments row
    ok = auto_complete_talk_to_npc(
        CID, "Podchodzę do Brunna i pytam, co się stało.", None, None, 5, conn
    )
    assert ok is True, "beat must close from plan objective_value even without assignment"
    assert get_plan(CID, conn)["acts"][0]["key_beats"][0].get("visited") is True


def test_talk_fallback_ignores_unrelated_text():
    """Player text with no NPC-key token → beat stays open (no false completion)."""
    from app.services.campaign_plan_runtime import auto_complete_talk_to_npc, get_plan

    conn = _make_talk_db("brunn_zelaznoreki")
    ok = auto_complete_talk_to_npc(
        CID, "Rozglądam się po izbie i wychodzę na dwór.", None, None, 2, conn
    )
    assert ok is False
    assert get_plan(CID, conn)["acts"][0]["key_beats"][0].get("visited") is None


# ─── Fix 2: quest-driven finale fallback ─────────────────────────────────────

def _make_finale_db(num_acts, completed_main, active_main, plan_complete, campaign_id=CID):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, status TEXT DEFAULT 'active',
                                finale_available INTEGER DEFAULT 0, gm_plan_json TEXT,
                                current_act_index INTEGER DEFAULT 0);
        CREATE TABLE campaign_turns (id INTEGER PRIMARY KEY, campaign_id INTEGER,
                                     turn_number INTEGER DEFAULT 0);
        CREATE TABLE character_quests (id INTEGER PRIMARY KEY, character_id INTEGER,
                                       campaign_id INTEGER, status TEXT,
                                       quest_type TEXT DEFAULT 'main');
        CREATE TABLE game_sessions (id INTEGER PRIMARY KEY, campaign_id INTEGER,
                                    session_flags TEXT DEFAULT '{}');
        """
    )
    acts = [{"act_index": i, "completed": plan_complete,
             "key_beats": [{"beat_key": f"b{i}", "objective_type": "talk_to_npc",
                            "objective_value": f"npc{i}"}]}
            for i in range(num_acts)]
    plan = {"active_act": 1, "acts": acts}
    conn.execute(
        "INSERT INTO campaigns (id, status, finale_available, gm_plan_json) VALUES (?,?,?,?)",
        (campaign_id, "active", 0, json.dumps(plan)),
    )
    conn.execute("INSERT INTO game_sessions (campaign_id, session_flags) VALUES (?, '{}')",
                 (campaign_id,))
    for _ in range(completed_main):
        conn.execute("INSERT INTO character_quests (character_id, campaign_id, status, quest_type)"
                     " VALUES (?,?,?,?)", (99, campaign_id, "completed", "main"))
    for _ in range(active_main):
        conn.execute("INSERT INTO character_quests (character_id, campaign_id, status, quest_type)"
                     " VALUES (?,?,?,?)", (99, campaign_id, "active", "main"))
    conn.commit()
    return conn


def _finale_open(conn, campaign_id=CID):
    return bool(conn.execute("SELECT finale_available FROM campaigns WHERE id=?",
                             (campaign_id,)).fetchone()[0])


def test_finale_opens_when_all_quests_done_but_beats_stranded():
    """Plan incomplete (acts never flipped) but every main quest done and
    completed_main >= num_acts → finale opens (the #1300 core fix)."""
    from app.services.campaign_plan_runtime import maybe_complete_campaign

    conn = _make_finale_db(num_acts=3, completed_main=9, active_main=0, plan_complete=False)
    assert maybe_complete_campaign(CID, 99, 12, conn) is True
    assert _finale_open(conn) is True


def test_finale_stays_closed_early_game_transient_zero_active():
    """0 active main quests but only 1 completed vs 3 acts → NO finale
    (guards against an early-game transient 0-active window)."""
    from app.services.campaign_plan_runtime import maybe_complete_campaign

    conn = _make_finale_db(num_acts=3, completed_main=1, active_main=0, plan_complete=False)
    assert maybe_complete_campaign(CID, 99, 3, conn) is False
    assert _finale_open(conn) is False


def test_finale_blocked_by_active_main_quest():
    """An open main quest still blocks the finale even if beats/acts look done."""
    from app.services.campaign_plan_runtime import maybe_complete_campaign

    conn = _make_finale_db(num_acts=3, completed_main=9, active_main=1, plan_complete=False)
    assert maybe_complete_campaign(CID, 99, 10, conn) is False
    assert _finale_open(conn) is False


def test_finale_opens_normal_path_when_plan_complete():
    """Original path unchanged: all acts completed + 0 active main → finale opens."""
    from app.services.campaign_plan_runtime import maybe_complete_campaign

    conn = _make_finale_db(num_acts=2, completed_main=0, active_main=0, plan_complete=True)
    assert maybe_complete_campaign(CID, 99, 8, conn) is True
    assert _finale_open(conn) is True


def test_planless_campaign_never_auto_wins():
    """num_acts == 0 (no roadmap) → fallback cannot fire regardless of quests."""
    from app.services.campaign_plan_runtime import maybe_complete_campaign

    conn = _make_finale_db(num_acts=0, completed_main=5, active_main=0, plan_complete=False)
    assert maybe_complete_campaign(CID, 99, 5, conn) is False
    assert _finale_open(conn) is False
