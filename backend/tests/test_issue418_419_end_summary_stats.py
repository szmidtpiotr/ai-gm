"""TDD: Issues #418 (E3) + #419 (E4) — campaign stats block in end/death summary."""
import sys, os, json, sqlite3

sys.path.insert(0, "/app")

import pytest

DB_PATH = os.environ.get("DB_PATH", "/data/ai_gm.db")
_CID = 999417   # synthetic campaign id unlikely to collide


def _seed():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM campaign_turns WHERE campaign_id = ?", (_CID,))
        conn.execute("DELETE FROM campaign_known_npcs WHERE campaign_id = ?", (_CID,))
        conn.execute("DELETE FROM character_quests WHERE campaign_id = ?", (_CID,))
        conn.execute("DELETE FROM characters WHERE campaign_id = ?", (_CID,))
        cur = conn.execute(
            "INSERT INTO characters (user_id, campaign_id, name, system_id, sheet_json, gold_gp) "
            "VALUES (1, ?, 'StatHero', 'dnd', '{}', 777)",
            (_CID,),
        )
        char_id = cur.lastrowid
        for i in range(1, 4):  # 3 turns
            conn.execute(
                "INSERT INTO campaign_turns (campaign_id, character_id, user_text, route, turn_number) "
                "VALUES (?, ?, 'x', 'narrative', ?)",
                (_CID, char_id, i),
            )
        for nm in ("Aldric", "Mira"):  # 2 NPCs met
            conn.execute(
                "INSERT INTO campaign_known_npcs (campaign_id, npc_name) VALUES (?, ?)",
                (_CID, nm),
            )
        # 1 completed quest + 1 active
        conn.execute(
            "INSERT INTO character_quests (character_id, campaign_id, title, status, completed_turn) "
            "VALUES (?, ?, 'Done quest', 'completed', 3)",
            (char_id, _CID),
        )
        conn.execute(
            "INSERT INTO character_quests (character_id, campaign_id, title, status) "
            "VALUES (?, ?, 'Open quest', 'active')",
            (char_id, _CID),
        )
        conn.commit()
        return char_id
    finally:
        conn.close()


def _cleanup():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM campaign_turns WHERE campaign_id = ?", (_CID,))
        conn.execute("DELETE FROM campaign_known_npcs WHERE campaign_id = ?", (_CID,))
        conn.execute("DELETE FROM character_quests WHERE campaign_id = ?", (_CID,))
        conn.execute("DELETE FROM characters WHERE campaign_id = ?", (_CID,))
        conn.commit()
    finally:
        conn.close()


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_campaign_run_stats_counts():
    """New campaign_run_stats() must count turns, gold, NPCs met, quests completed."""
    from app.services.solo_death_service import campaign_run_stats
    char_id = _seed()
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            stats = campaign_run_stats(conn, _CID, char_id)
        finally:
            conn.close()
        assert stats["turn_count"] == 3, f"turn_count: {stats}"
        assert stats["gold"] == 777, f"gold: {stats}"
        assert stats["npcs_met"] == 2, f"npcs_met: {stats}"
        assert stats["quests_completed"] == 1, f"quests_completed: {stats}"
    finally:
        _cleanup()


def test_end_summary_payload_includes_stats():
    """end_summary_payload for an ended campaign must carry a 'stats' block."""
    from app.services.solo_death_service import end_summary_payload
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id FROM campaigns WHERE status IN ('ended','completed') LIMIT 1"
        ).fetchone()
        if not row:
            pytest.skip("no ended/completed campaign in DB")
        payload = end_summary_payload(conn, row["id"])
    finally:
        conn.close()
    assert payload is not None, "payload None for ended campaign"
    assert "stats" in payload, f"payload missing 'stats': {list(payload.keys())}"
    for k in ("turn_count", "gold", "npcs_met", "quests_completed"):
        assert k in payload["stats"], f"stats missing {k}: {payload['stats']}"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_end_summary_payload_keeps_core_fields():
    """Existing payload fields (outcome, epitaph, level) must remain (no regression)."""
    from app.services.solo_death_service import end_summary_payload
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id FROM campaigns WHERE status IN ('ended','completed') LIMIT 1"
        ).fetchone()
        if not row:
            pytest.skip("no ended/completed campaign in DB")
        payload = end_summary_payload(conn, row["id"])
    finally:
        conn.close()
    for k in ("outcome", "epitaph", "level", "character_name", "xp_lifetime_earned"):
        assert k in payload, f"core field {k} lost: {list(payload.keys())}"
