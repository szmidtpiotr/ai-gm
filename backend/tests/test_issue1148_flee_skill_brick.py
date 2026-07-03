"""TDD: #1148 — flee from a travel/local encounter must not brick the session.

Root cause (smoke round 3): the narrator answered the player_flee combat-roll
turn with roll_cue "Roll stealth d20". The streaming intercept committed it as
pending_skill_test + state=SKILL_TEST_PENDING, but no dice popup ever reached
the client. Every following movement turn then hit the pending re-surface path,
whose bespoke [SKILL_TEST_PENDING] SSE marker the frontend does not know — so
raw JSON showed up in the chat and the hex froze until a manual DB edit.

Fix under test:
- _skill_test_source_allowed(): combat-roll turns (__AI_GM_COMBAT_ROLL_V1__
  prefix — attack/flee epilogues) never source a NEW skill test from narrator
  roll_cue / [SKILL_TEST] tags;
- the pending re-surface stream emits `[DONE]{"skill_test_pending": ...}` —
  the same meta shape as the working pre-LLM scanner path — instead of the
  frontend-unknown `[SKILL_TEST_PENDING]{...}` marker.
"""
import sys

sys.path.insert(0, "/app")


# ── guard: combat-roll turns never source a skill test ───────────────────────

def test_flee_combat_roll_turn_blocks_skill_test_source():
    from app.api.turns import _skill_test_source_allowed
    from app.core.turn_engine import COMBAT_ROLL_CTX_PREFIX

    flee_turn = (
        COMBAT_ROLL_CTX_PREFIX
        + '\n{"kind":"player_flee","summary_line":"Uciekam z walki z Wilk!",'
        '"character_name":"[TEST] Uczony","enemy_name":"Wilk","success":true}'
    )
    assert _skill_test_source_allowed(flee_turn) is False


def test_attack_combat_roll_turn_blocks_skill_test_source():
    from app.api.turns import _skill_test_source_allowed
    from app.core.turn_engine import COMBAT_ROLL_CTX_PREFIX

    attack_turn = COMBAT_ROLL_CTX_PREFIX + '\n{"kind":"player_attack","hit":true}'
    assert _skill_test_source_allowed(attack_turn) is False


def test_plain_player_prose_still_allows_skill_test():
    from app.api.turns import _skill_test_source_allowed

    assert _skill_test_source_allowed("Zatrzymuję się i wytężam słuch.") is True
    assert _skill_test_source_allowed("Ruszam na północ, ku traktowi.") is True


def test_empty_and_none_text_allow_skill_test():
    from app.api.turns import _skill_test_source_allowed

    assert _skill_test_source_allowed("") is True
    assert _skill_test_source_allowed(None) is True


# ── re-surface stream: [DONE]-meta shape, no bespoke marker ──────────────────

def test_pending_resurface_emits_done_meta_not_bespoke_marker():
    """The re-surface generator lives inline in the streaming endpoint, so
    assert on the source: the pending re-surface must ship its payload behind
    the [DONE] marker (frontend re-opens the dice popup from done-meta) and the
    frontend-unknown `data: [SKILL_TEST_PENDING]{...}` yield must be gone."""
    import inspect
    import app.api.turns as turns_mod

    src = inspect.getsource(turns_mod)
    assert 'yield f"data: [SKILL_TEST_PENDING]{_re_payload}' not in src, (
        "pending re-surface still emits the bespoke [SKILL_TEST_PENDING] marker "
        "the frontend renders as raw JSON (#1148)"
    )
    assert 'yield f"data: [DONE]{_re_payload}' in src, (
        "pending re-surface must emit its payload as [DONE] meta so the client "
        "re-opens the dice popup (#1148)"
    )


# ── stale travel_plan after flee-at-destination must be completed ─────────────

import json
import sqlite3


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            session_flags TEXT DEFAULT '{}'
        );
        CREATE TABLE active_combat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
        );
        """
    )
    return conn


def _arrival_stub(**_kw):
    """resolve_chain_travel's from==to early-return shape (hero already at dest)."""
    return {
        "ok": True, "error": None,
        "path": [{"q": 16, "r": 14}],
        "total_hours": 0,
        "arrived_hex": {"q": 16, "r": 14},
        "encounter": None, "encounter_hex": None,
        "hex_data": {"hex_type": "forest"},
        "teleport_used": None, "item_blocked": None,
    }


def test_resume_at_destination_pops_stale_travel_plan(monkeypatch):
    """#1148 layer 2: after fleeing ON the destination hex, 'kontynuuję' resumes
    a zero-length trip. resolve_chain_travel's from==to early-return skips its
    own arrival cleanup, so the resume path must pop the plan itself — otherwise
    every later movement command re-resumes toward the stale destination and the
    hex freezes until the 10-turn TTL."""
    from app.services import hex_travel_service
    from app.services import turn_pipeline

    monkeypatch.setattr(hex_travel_service, "resolve_chain_travel", _arrival_stub)

    conn = _make_conn()
    flags = {
        "current_hex": {"q": 16, "r": 14},
        "travel_plan": {
            "destination_hex": {"q": 16, "r": 14},
            "destination_label": "hex (16,14)",
            "interrupt_reason": "encounter_prompted",
            "enemy_key": "wolf",
            "combat_seen": False,
            "wait_turns": 2,
            "age": 0,
        },
    }
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, session_flags) VALUES (1, ?)",
        (json.dumps(flags),),
    )
    conn.commit()

    res = turn_pipeline.execute_directional_travel(
        conn, 1, 42, {}, "Otrząsam się i kontynuuję marsz na północ."
    )
    assert res["executed"] is True

    row = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = 1"
    ).fetchone()
    left = json.loads(row["session_flags"])
    assert "travel_plan" not in left, (
        "fully-arrived travel_plan must be popped on resume — a stale "
        "encounter_prompted plan hijacks every later movement command (#1148)"
    )


def test_resume_mid_route_keeps_plan_semantics(monkeypatch):
    """Resume that ends in a NEW encounter en route must not pop the plan here —
    resolve_chain_travel owns mid-route plan state (it rewrites it itself)."""
    from app.services import hex_travel_service
    from app.services import turn_pipeline

    def _mid_route_stub(**_kw):
        return {
            "ok": True, "error": None,
            "path": [{"q": 16, "r": 14}, {"q": 16, "r": 13}, {"q": 16, "r": 12}],
            "total_hours": 2.0,
            "arrived_hex": {"q": 16, "r": 13},
            "encounter": {"enemy_key": "goblin"}, "encounter_hex": {"q": 16, "r": 13},
            "hex_data": {"hex_type": "forest"},
            "teleport_used": None, "item_blocked": None,
        }

    monkeypatch.setattr(hex_travel_service, "resolve_chain_travel", _mid_route_stub)
    monkeypatch.setattr(
        "app.services.clock_service.advance_clock", lambda *a, **k: None
    )

    conn = _make_conn()
    flags = {
        "current_hex": {"q": 16, "r": 14},
        "travel_plan": {
            "destination_hex": {"q": 16, "r": 12},
            "destination_label": "hex (16,12)",
            "interrupt_reason": "encounter_prompted",
            "combat_seen": False,
            "age": 0,
        },
    }
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, session_flags) VALUES (1, ?)",
        (json.dumps(flags),),
    )
    conn.commit()

    res = turn_pipeline.execute_directional_travel(
        conn, 1, 42, {}, "Idę dalej."
    )
    assert res["executed"] is True

    row = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = 1"
    ).fetchone()
    left = json.loads(row["session_flags"])
    assert "travel_plan" in left, (
        "mid-route resume (new encounter) must leave plan state to "
        "resolve_chain_travel, not pop it in the resume path"
    )
