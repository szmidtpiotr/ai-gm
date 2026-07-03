"""TDD: #1146 + #1147 — travel/local combat encounters must actually spawn.

#1146 (overworld):
- empty hex encounter_pool falls back to a terrain-typed default pool instead
  of silently dropping the encounter (_pick_encounter_enemy);
- travel_plan persists the rolled enemy_key so the deterministic
  [COMBAT_START] injection knows whom to spawn;
- _pending_engine_encounter_enemy + _ensure_combat_start_tag append the tag
  when the narrator ignored the ambush.

#1147 (local):
- roll_local_encounter's combat hint carries enemy_key;
- pop_local_travel_hint runs a combat state machine: prompt-the-fight first,
  continue-or-return only after the fight was seen (or fizzle timeout);
- auto_assign_local_hex gives safe sub-locs a non-zero chance (covered in
  test_issue993_local_hex.py).
"""
import json
import sqlite3
import sys

import pytest

sys.path.insert(0, "/app")


# ── #1146: fallback pool ──────────────────────────────────────────────────────

def test_pick_encounter_enemy_empty_pool_uses_terrain_fallback():
    from app.services.hex_travel_service import (
        _pick_encounter_enemy,
        _WORLD_ENCOUNTER_FALLBACK_POOLS,
    )

    enemy = _pick_encounter_enemy({"hex_type": "forest", "encounter_pool": []})
    assert enemy in _WORLD_ENCOUNTER_FALLBACK_POOLS["forest"], \
        f"Empty forest pool must fall back to forest defaults, got {enemy!r}"


def test_pick_encounter_enemy_unknown_terrain_uses_default_fallback():
    from app.services.hex_travel_service import (
        _pick_encounter_enemy,
        _WORLD_ENCOUNTER_FALLBACK_DEFAULT,
    )

    enemy = _pick_encounter_enemy({"hex_type": "plains", "encounter_pool": None})
    assert enemy in _WORLD_ENCOUNTER_FALLBACK_DEFAULT


def test_pick_encounter_enemy_authored_pool_wins():
    from app.services.hex_travel_service import _pick_encounter_enemy

    enemy = _pick_encounter_enemy({"hex_type": "forest", "encounter_pool": ["lich"]})
    assert enemy == "lich", "Authored pool must not be overridden by fallback"


# ── shared fixtures for session_flags-driven tests ────────────────────────────

def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            session_flags TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE active_combat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
        );
        CREATE TABLE game_config_enemies (
            key TEXT PRIMARY KEY,
            label TEXT,
            is_active INTEGER NOT NULL DEFAULT 1
        );
        INSERT INTO game_config_enemies (key, label) VALUES
            ('goblin', 'Goblin'), ('bandit', 'Bandyta'),
            ('unknown_attacker', 'Nieznany napastnik');
        """
    )
    return conn


def _set_flags(conn, campaign_id, flags):
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, session_flags) VALUES (?, ?)",
        (campaign_id, json.dumps(flags)),
    )
    conn.commit()


# ── #1146: pending-encounter detection + tag injection ────────────────────────

def test_pending_engine_encounter_from_travel_plan():
    from app.api.turns import _pending_engine_encounter_enemy

    conn = _make_conn()
    _set_flags(conn, 1, {"travel_plan": {
        "interrupt_reason": "encounter", "combat_seen": False, "enemy_key": "goblin",
    }})
    assert _pending_engine_encounter_enemy(conn, 1) == "goblin"


def test_pending_engine_encounter_ignores_seen_and_prompted():
    from app.api.turns import _pending_engine_encounter_enemy

    conn = _make_conn()
    _set_flags(conn, 1, {"travel_plan": {
        "interrupt_reason": "encounter", "combat_seen": True, "enemy_key": "goblin",
    }})
    assert _pending_engine_encounter_enemy(conn, 1) is None

    conn2 = _make_conn()
    _set_flags(conn2, 1, {"travel_plan": {
        "interrupt_reason": "encounter_prompted", "enemy_key": "goblin",
    }})
    assert _pending_engine_encounter_enemy(conn2, 1) is None


def test_pending_engine_encounter_from_local_hint():
    from app.api.turns import _pending_engine_encounter_enemy

    conn = _make_conn()
    _set_flags(conn, 1, {"local_travel_hint": {
        "kind": "combat", "enemy_key": "bandit",
    }})
    assert _pending_engine_encounter_enemy(conn, 1) == "bandit"


def test_pending_engine_encounter_ignores_seen_local_hint():
    # Round-5 smoke: combat_seen is now set at combat spawn (consume-at-spawn in
    # _maybe_start_combat_from_gm_tag) — a seen local hint must stop re-injection
    # on the flee-epilogue turn (double-spawn bug).
    from app.api.turns import _pending_engine_encounter_enemy

    conn = _make_conn()
    _set_flags(conn, 1, {"local_travel_hint": {
        "kind": "combat", "enemy_key": "bandit", "combat_seen": True,
    }})
    assert _pending_engine_encounter_enemy(conn, 1) is None


def test_pending_engine_encounter_ignores_social_hint():
    from app.api.turns import _pending_engine_encounter_enemy

    conn = _make_conn()
    _set_flags(conn, 1, {"local_travel_hint": {
        "kind": "social", "social_event": "guard_check",
    }})
    assert _pending_engine_encounter_enemy(conn, 1) is None


def test_ensure_combat_start_tag_injects_for_engine_encounter():
    from app.api.turns import _ensure_combat_start_tag

    conn = _make_conn()
    _set_flags(conn, 1, {"travel_plan": {
        "interrupt_reason": "encounter", "combat_seen": False, "enemy_key": "goblin",
    }})
    peaceful = "Maszerujesz dalej przez las, wiatr szumi w koronach."
    out = _ensure_combat_start_tag(conn, 1, "idę dalej na zachód", peaceful)
    assert "[COMBAT_START:goblin]" in out, \
        "Engine-rolled encounter must inject the tag when the narrator fizzled"


def test_ensure_combat_start_tag_unknown_enemy_falls_back():
    from app.api.turns import _ensure_combat_start_tag

    conn = _make_conn()
    _set_flags(conn, 1, {"travel_plan": {
        "interrupt_reason": "encounter", "combat_seen": False, "enemy_key": "nie_ma_takiego",
    }})
    out = _ensure_combat_start_tag(conn, 1, "idę dalej", "Spokojny marsz.")
    assert "[COMBAT_START:unknown_attacker]" in out


def test_ensure_combat_start_tag_noop_when_tag_present_or_combat_active():
    from app.api.turns import _ensure_combat_start_tag

    conn = _make_conn()
    _set_flags(conn, 1, {"travel_plan": {
        "interrupt_reason": "encounter", "combat_seen": False, "enemy_key": "goblin",
    }})
    tagged = "Gobliny wyskakują!\n[COMBAT_START:goblin]"
    assert _ensure_combat_start_tag(conn, 1, "idę", tagged) == tagged

    conn.execute("INSERT INTO active_combat (campaign_id, status) VALUES (1, 'active')")
    conn.commit()
    peaceful = "Spokojny marsz."
    assert _ensure_combat_start_tag(conn, 1, "idę", peaceful) == peaceful


def test_ensure_combat_start_tag_engine_enemy_wins_over_aggressive_narration():
    # Round-4 smoke regression: prose matching _AGGRESSION_NARRATIVE_RE used to
    # bypass the engine_encounter branch and fall into scene inference, which
    # resolved to unknown_attacker → combat_target_not_present → encounter fizzled.
    from app.api.turns import _ensure_combat_start_tag

    conn = _make_conn()
    _set_flags(conn, 1, {"travel_plan": {
        "interrupt_reason": "encounter", "combat_seen": False, "enemy_key": "goblin",
    }})
    aggressive = "Coś dużego rzuca się na ciebie z paproci, nie widzisz co to jest."
    out = _ensure_combat_start_tag(conn, 1, "idę dalej na południe", aggressive)
    assert "[COMBAT_START:goblin]" in out, \
        "Engine-rolled enemy must win even when narration reads aggressive"


def test_ensure_combat_start_tag_engine_enemy_wins_over_player_intent():
    # Same bypass via _player_combat_intent: an attack-sounding player line must
    # not reroute the engine encounter into scene inference.
    from app.api.turns import _ensure_combat_start_tag

    conn = _make_conn()
    _set_flags(conn, 1, {"travel_plan": {
        "interrupt_reason": "encounter", "combat_seen": False, "enemy_key": "bandit",
    }})
    out = _ensure_combat_start_tag(conn, 1, "atakuję cień między drzewami", "Las milczy.")
    assert "[COMBAT_START:bandit]" in out


def test_directional_move_is_not_combat_intent():
    # Round-5 smoke: bare "ruszam na" matched every directional move and spawned
    # combat vs a stale scene enemy. Directions must not read as attack intent;
    # person-targeted "ruszam na niego" must still count.
    from app.api.turns import _player_combat_intent

    assert _player_combat_intent("Ruszam na północ.") is False
    assert _player_combat_intent("Ruszam na południe, między drzewa.") is False
    assert _player_combat_intent("Ruszam na zachód, ku traktowi.") is False
    assert _player_combat_intent("Ruszam na niego z pięściami!") is True
    assert _player_combat_intent("Ruszam na wroga.") is True


# ── #1147: local combat state machine ─────────────────────────────────────────

def test_pop_local_hint_combat_prompts_fight_first_then_continue():
    from app.services.turn_pipeline import pop_local_travel_hint

    conn = _make_conn()
    _set_flags(conn, 1, {"local_travel_hint": {
        "destination_label": "Gospoda", "kind": "combat", "enemy_key": "bandit",
    }})

    # 1st pop: no combat yet → instruct the narrator to START the fight, keep hint.
    hint1 = pop_local_travel_hint(conn, 1)
    assert hint1 and "COMBAT_START:bandit" in hint1
    flags = json.loads(conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()[0])
    assert flags["local_travel_hint"]["combat_prompted"] is True

    # Combat spawns → pop stays silent and marks combat_seen.
    conn.execute("INSERT INTO active_combat (campaign_id, status) VALUES (1, 'active')")
    conn.commit()
    assert pop_local_travel_hint(conn, 1) is None
    flags = json.loads(conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()[0])
    assert flags["local_travel_hint"]["combat_seen"] is True

    # Combat over → continue-or-return prompt, hint popped.
    conn.execute("UPDATE active_combat SET status='ended'")
    conn.commit()
    hint3 = pop_local_travel_hint(conn, 1)
    assert hint3 and "kontynuuje" in hint3
    flags = json.loads(conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()[0])
    assert "local_travel_hint" not in flags


def test_pop_local_hint_combat_fizzle_falls_through_after_timeout():
    from app.services.turn_pipeline import pop_local_travel_hint, _ENCOUNTER_FIZZLE_TURNS

    conn = _make_conn()
    _set_flags(conn, 1, {"local_travel_hint": {
        "destination_label": "Gospoda", "kind": "combat", "enemy_key": "bandit",
    }})

    assert "COMBAT_START" in (pop_local_travel_hint(conn, 1) or "")
    # combat never spawns → after the fizzle window the continue prompt fires anyway
    got_prompt = None
    for _ in range(_ENCOUNTER_FIZZLE_TURNS + 1):
        got_prompt = pop_local_travel_hint(conn, 1)
        if got_prompt:
            break
    assert got_prompt and "kontynuuje" in got_prompt
    flags = json.loads(conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()[0])
    assert "local_travel_hint" not in flags


def test_pop_local_hint_social_unchanged():
    from app.services.turn_pipeline import pop_local_travel_hint

    conn = _make_conn()
    _set_flags(conn, 1, {"local_travel_hint": {
        "destination_label": "Targ", "kind": "social",
        "social_event": "guard_check", "success": True,
    }})
    hint = pop_local_travel_hint(conn, 1)
    assert hint and "NIE zaczynaj walki" in hint
    flags = json.loads(conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()[0])
    assert "local_travel_hint" not in flags


# ── #1146: travel_plan persists enemy_key (unit-level, via flag shape) ────────

def test_local_roll_hint_carries_enemy_key_for_combat(monkeypatch):
    """roll_local_encounter combat path must persist enemy_key in the hint."""
    from app.routers import local_map as lm

    conn = _make_conn()
    _set_flags(conn, 1, {})

    # Force: encounter triggers, kind=combat.
    monkeypatch.setattr(lm, "_check_local_encounter",
                        lambda target, cleared: {"enemy_key": "bandit", "hex_label": "Zaułek"})
    from app.services import social_encounter_service as ses
    monkeypatch.setattr(ses, "classify_encounter_kind", lambda _r: "combat")

    result = lm.roll_local_encounter(conn, 1, {"id": 5, "label": "Zaułek"}, "osada")
    assert result and result.get("enemy_key") == "bandit"
    flags = json.loads(conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()[0])
    hint = flags.get("local_travel_hint") or {}
    assert hint.get("kind") == "combat"
    assert hint.get("enemy_key") == "bandit", "combat hint must carry enemy_key (#1147)"
