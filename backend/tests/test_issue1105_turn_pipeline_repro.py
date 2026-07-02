"""TDD: Issue #1105 (deeper repro) — full turn-pipeline reproduction of the
campaign 999989 "gospoda -> tundra" teleport, checked at the state layer:

  Turn 2: GM emits location_intent for a macro location whose target_key
          exactly matches an existing DB row, but whose target_label is
          reworded (region prefix) enough to fail the fuzzy-match threshold.
          A decoy macro location (hex-linked, matching the real prod
          "tundra_mrozu") must never be picked.
  Turn 3: player says "odpoczywam" (rest) — GM response carries NO
          location_intent. The session must stay put: current_location_id
          and current_hex must not drift, and no "first visit" XP fires for
          the decoy.

Covers acceptance criteria 1-4 of #1105 without a live LLM, using the same
_process_location_intent() hook pattern as test_phase8d_location_hook.py.
"""
import json
import sqlite3

from app.api import turns as turns_api
from app.services.xp_sources import grant_first_location_visit

DB_PATH = "/data/ai_gm.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _set_flag(conn, key, value):
    conn.execute(
        "INSERT INTO game_config_meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def _session(conn, campaign_id, current_location_id=None, current_hex=None):
    session_id = f"issue1105-turn-{campaign_id}"
    flags = json.dumps({"current_hex": current_hex} if current_hex else {})
    conn.execute(
        "INSERT OR REPLACE INTO game_sessions (id, campaign_id, current_location_id, session_flags) "
        "VALUES (?, ?, ?, ?)",
        (session_id, campaign_id, current_location_id, flags),
    )
    conn.commit()
    return session_id


def _location(conn, key, label, location_type="macro"):
    conn.execute("DELETE FROM game_locations WHERE key = ?", (key,))
    cur = conn.execute(
        "INSERT INTO game_locations (key, label, location_type, is_active, ai_generated, approved) "
        "VALUES (?, ?, ?, 1, 0, 1)",
        (key, label, location_type),
    )
    conn.commit()
    return int(cur.lastrowid)


def _link_hex(conn, q, r, location_key, hex_type="plains"):
    conn.execute("DELETE FROM world_hexes WHERE q = ? AND r = ?", (q, r))
    conn.execute(
        "INSERT INTO world_hexes (q, r, hex_type, location_key, is_active) VALUES (?, ?, ?, ?, 1)",
        (q, r, hex_type, location_key),
    )
    conn.commit()


def _move_json(label, key):
    return json.dumps(
        {"narrative": f"Docierasz do: {label}.", "location_intent": {"action": "move", "target_label": label, "target_key": key}},
        ensure_ascii=False,
    )


def _rest_json():
    return json.dumps(
        {"narrative": "Spokojnie posilasz się i odpoczywasz.", "location_intent": None},
        ensure_ascii=False,
    )


def _character(conn, campaign_id):
    cur = conn.execute(
        "INSERT INTO characters (name, campaign_id, user_id, system_id, status, visited_location_keys, sheet_json) "
        "VALUES (?, ?, 1, 'fantasy', 'active', '[]', '{}')",
        (f"issue1105-hero-{campaign_id}", campaign_id),
    )
    conn.commit()
    return int(cur.lastrowid)


def test_gospoda_to_tundra_repro_full_pipeline():
    conn = _conn()
    try:
        campaign_id = 990001105
        _set_flag(conn, "location_integrity_enabled", "1")

        origin_hex = (10, 10)
        origin_key = f"issue1105_origin_{campaign_id}"
        origin_id = _location(conn, origin_key, "Miejsce Startowe")
        _link_hex(conn, *origin_hex, origin_key)

        # Target: exact-key match, region-prefixed label the fuzzy matcher
        # scores below FUZZY_MATCH_THRESHOLD=80 against the DB's short label.
        target_key = f"issue1105_gospoda_szlaku_{campaign_id}"
        target_id = _location(conn, target_key, "Gospoda Szlaku")  # no world_hexes row — "bez hexa"

        # Decoy: real prod counterpart (tundra_mrozu) — hex-linked, must never be picked.
        decoy_key = f"issue1105_tundra_mrozu_{campaign_id}"
        decoy_id = _location(conn, decoy_key, "Tundra Wiecznego Mrozu")
        _link_hex(conn, 0, -31, decoy_key, hex_type="tundra")

        # Mirrors prod campaign 999989 turn 2: current_location_id is still NULL
        # (fresh session, LOC-3 graph guard fails open) while session_flags.current_hex
        # already tracks a real world-map position from mechanical hex-travel — the
        # "two conflicting truths" starting state described in #1105.
        session_id = _session(conn, campaign_id, current_location_id=None, current_hex={"q": origin_hex[0], "r": origin_hex[1]})
        char_id = _character(conn, campaign_id)

        # ── Turn 2: GM narrates arrival at "Volhynia: Gospoda Szlaku" ──────────
        out2 = turns_api._process_location_intent(
            conn, campaign_id, _move_json("Volhynia: Gospoda Szlaku", target_key)
        )
        assert "LOCATION_BLOCKED" not in out2, f"move was blocked: {out2}"

        row = conn.execute(
            "SELECT current_location_id, session_flags FROM game_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        # Criterion 1: resolved to the exact-key target, never the decoy.
        assert row["current_location_id"] == target_id, (
            f"expected target {target_id} ({target_key}), got {row['current_location_id']} "
            f"(decoy id={decoy_id})"
        )
        # Criterion 2: current_hex must not be clobbered onto the decoy's hex
        # just because the target has no hex of its own.
        flags = json.loads(row["session_flags"] or "{}")
        cur_hex = flags.get("current_hex") or {}
        assert (cur_hex.get("q"), cur_hex.get("r")) != (0, -31), (
            "current_hex was pulled onto the decoy's (tundra) hex — id/hex desync reproduced"
        )

        # Criterion 4: "first macro visit" XP must credit the actual target, not the decoy.
        loc_row = conn.execute(
            "SELECT gl.key FROM game_sessions gs JOIN game_locations gl ON gl.id = gs.current_location_id "
            "WHERE gs.campaign_id = ?",
            (campaign_id,),
        ).fetchone()
        assert loc_row["key"] == target_key
        xp = grant_first_location_visit(conn, char_id, campaign_id, loc_row["key"], turn_number=2)
        assert xp > 0, "expected first-visit XP for the real target"
        ev = conn.execute(
            "SELECT event_data FROM game_events WHERE campaign_id = ? AND event_type = 'location_new' "
            "ORDER BY id DESC LIMIT 1",
            (campaign_id,),
        ).fetchone()
        ev_data = json.loads(ev["event_data"])
        assert ev_data["location_key"] == target_key, (
            f"XP/discovery event fired for {ev_data['location_key']}, not the visited target {target_key}"
        )

        # ── Turn 3: player rests, GM emits no location_intent ("odpoczywam") ──
        out3 = turns_api._process_location_intent(conn, campaign_id, _rest_json())
        assert out3 == _rest_json()

        row3 = conn.execute(
            "SELECT current_location_id, session_flags FROM game_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        # Criterion 3: narration stays in one place until the player actually travels.
        assert row3["current_location_id"] == target_id
        flags3 = json.loads(row3["session_flags"] or "{}")
        assert flags3.get("current_hex") == flags.get("current_hex"), (
            "current_hex drifted on a no-op rest turn — narrative teleport reproduced"
        )
    finally:
        conn.close()
