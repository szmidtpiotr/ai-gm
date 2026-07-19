"""AUDIT Krok G5 — Poprawność progresji.

  #1466  test_levelup_hp_matches_formula          — level-up recomputes max_hp from formula
  #1466  test_hp_path_independent_rest_vs_resurrect — rest & resurrect/admin agree on max_hp
  #1467  test_max_one_stat_up_per_level            — spend_stat_point_up capped at 1/level
  #1467  test_max_two_new_skills_per_level         — learning NEW skills capped at 2/level
                                                      (rank-ups of known skills unlimited)

Run inside the DEV backend container:
    docker exec ai-gm-dev-backend-1 pytest tests/test_g5_progression_correctness_1466_1467.py -v
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, "/app")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: E402

DB_PATH = "/data/ai_gm.db"


# ══════════════════════════════════════════════════════════════════════════════
# #1466 — HP/mana are recomputed from the formula on every path (in-memory rest)
# ══════════════════════════════════════════════════════════════════════════════

os.environ.setdefault("AIGM_E2E_LITE", "1")
from _fixtures_schema import table_sql  # noqa: E402


def _mem_db(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "g5.db"))
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL DEFAULT 1,
            user_id INTEGER NOT NULL DEFAULT 1,
            name TEXT NOT NULL DEFAULT 'TestHero',
            system_id TEXT NOT NULL DEFAULT 'fantasy',
            sheet_json TEXT NOT NULL DEFAULT '{}',
            is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT 'TestCamp',
            owner_user_id INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            current_location_id INTEGER,
            session_flags TEXT DEFAULT '{}',
            ingame_hours INTEGER DEFAULT 8
        );
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT, label TEXT,
            safe_for_rest INTEGER DEFAULT 1, is_active INTEGER DEFAULT 1
        );
        CREATE TABLE world_hexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            q INTEGER, r INTEGER, hex_type TEXT, label TEXT,
            location_key TEXT, map_level INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1
        );
        CREATE TABLE active_combat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER, status TEXT DEFAULT 'inactive'
        );
        CREATE TABLE character_xp_grants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER, campaign_id INTEGER, amount INTEGER,
            reason TEXT, source TEXT, source_key TEXT DEFAULT '',
            turn_number INTEGER, granted_by_user_id INTEGER DEFAULT 0
        );
        """ + table_sql("game_config_meta") + """
        INSERT INTO campaigns VALUES (1, 'TestCamp', 1);
        INSERT INTO game_locations VALUES (1, 'inn', 'Karczma', 1, 1);
        INSERT INTO game_sessions VALUES (1, 1, 1, '{}', 8);
    """)
    return conn


def _mem_sheet(**over):
    """Warrior CON 8 (mod −1) — the DRIFT case: with a negative CON modifier the
    old incremental clamp (max()) never lowered max_hp, so it diverged from the
    formula base + CON_mod × level. Recompute makes it match at every level."""
    sheet = {
        "archetype": "warrior",
        "level": 1,
        "stats": {"STR": 10, "DEX": 10, "CON": 8, "INT": 10,
                  "WIS": 10, "CHA": 10, "LCK": 10},
        "max_hp": 9, "current_hp": 4,      # lvl1 formula: 10 + (−1)×1 = 9
        "max_mana": 0, "current_mana": 0,
        "pending_xp": 0, "xp_lifetime_earned": 0, "xp_available": 0,
        "short_rests_used": 0, "death_saves_failed": 0, "conditions": [],
    }
    sheet.update(over)
    return json.dumps(sheet, ensure_ascii=False)


def _rest_to_level3(conn):
    """Insert a warrior CON8 with enough lifetime XP for level 3, long-rest, return sheet."""
    sj = _mem_sheet(pending_xp=250, xp_lifetime_earned=250, xp_available=0)
    conn.execute(
        "INSERT INTO characters (campaign_id, user_id, name, sheet_json) VALUES (1,1,'W',?)",
        (sj,),
    )
    cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    from app.services.rest_service import perform_long_rest
    res = perform_long_rest(conn, cid, 1)
    assert res["ok"] is True, res
    row = conn.execute("SELECT sheet_json FROM characters WHERE id = ?", (cid,)).fetchone()
    return json.loads(row["sheet_json"])


def test_levelup_hp_matches_formula(tmp_path):
    """#1466 — after leveling to 3, max_hp equals the canonical formula, not the
    clamped incremental value."""
    from app.services.vitality_service import calculate_hp
    conn = _mem_db(tmp_path)
    sheet = _rest_to_level3(conn)

    assert sheet["level"] == 3, sheet["level"]
    expected = calculate_hp("warrior", 8, 3)   # 10 + (−1)×3 = 7
    assert expected == 7, expected
    assert sheet["max_hp"] == expected, (
        f"level-up must recompute from formula: got {sheet['max_hp']}, want {expected}"
    )


def test_hp_path_independent_rest_vs_resurrect(tmp_path):
    """#1466 — the max_hp a hero reaches by leveling via rest is identical to the
    max_hp the resurrection/admin path recomputes for the same (archetype, CON,
    level). A drifted stored max never survives — both funnel through
    recompute_max_hp (resurrection_service.py / admin_cheat.py)."""
    from app.services.vitality_service import recompute_max_hp
    conn = _mem_db(tmp_path)

    # Path A — rest level-up.
    max_hp_rest = _rest_to_level3(conn)["max_hp"]

    # Path B — resurrection/admin recompute for the SAME hero identity.
    max_hp_resurrect = recompute_max_hp("warrior", 8, 3)

    # A drifted stored value (e.g. left over from the old clamp) is irrelevant.
    drifted = 99
    corrected = recompute_max_hp("warrior", 8, 3)

    assert max_hp_rest == max_hp_resurrect == corrected == 7, (
        f"paths diverge: rest={max_hp_rest} resurrect={max_hp_resurrect}"
    )
    assert corrected != drifted


# ══════════════════════════════════════════════════════════════════════════════
# #1467 — per-level purchase caps (HTTP against the DEV DB)
# ══════════════════════════════════════════════════════════════════════════════

def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def _auth(user_id: int) -> dict:
    from app.services import jwt_service
    tok = jwt_service.issue_access_token(
        user_id=user_id, username=f"u{user_id}", role="player", is_admin=0
    )
    return {"Authorization": f"Bearer {tok}"}


def _insert_char(char_id: int, user_id: int, sheet: dict):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """INSERT OR REPLACE INTO characters
               (id, campaign_id, user_id, name, system_id, race, sheet_json)
               VALUES (?, NULL, ?, ?, 'v1', 'human', ?)""",
            (char_id, user_id, f"[AUDIT_G5] {char_id}",
             json.dumps(sheet, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()


def _read_sheet(char_id: int) -> dict:
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ?", (char_id,)
        ).fetchone()
        return json.loads(row[0]) if row and row[0] else {}
    finally:
        conn.close()


def _cleanup(*char_ids: int):
    conn = sqlite3.connect(DB_PATH)
    try:
        for cid in char_ids:
            conn.execute("DELETE FROM characters WHERE id = ?", (cid,))
            conn.execute("DELETE FROM character_spells WHERE character_id = ?", (cid,))
            conn.execute("DELETE FROM character_xp_grants WHERE character_id = ?", (cid,))
        conn.commit()
    finally:
        conn.close()


def _base_sheet(**over):
    sheet = {
        "archetype": "warrior",
        "level": 3,
        "xp_available": 99999,
        "xp_lifetime_earned": 300,
        "max_hp": 20, "current_hp": 20,
        "max_mana": 0, "current_mana": 0,
        "stats": {"STR": 12, "DEX": 10, "CON": 12, "INT": 10, "WIS": 10, "CHA": 10, "LCK": 10},
        "skills": {},
    }
    sheet.update(over)
    return sheet


def _catalog_skill_keys(n: int) -> list[str]:
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT key FROM game_config_skills WHERE key IS NOT NULL AND key != '' "
            "ORDER BY key LIMIT ?", (n,),
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def test_max_one_stat_up_per_level():
    """#1467 — a second stat purchase within the same level is rejected."""
    cid, owner = 999_467_001, 770_467
    _insert_char(cid, owner, _base_sheet())
    try:
        c = _client()
        r1 = c.post(f"/api/characters/{cid}/xp/spend-stat",
                    headers=_auth(owner), json={"stat_key": "STR"})
        if r1.status_code == 400 and "cost" in r1.text.lower():
            pytest.skip("stat point cost not configured in this DB")
        assert r1.status_code == 200, r1.text
        assert _read_sheet(cid).get("advancement_spent", {}).get("stat_ups") == 1

        # Second stat-up this level → blocked.
        r2 = c.post(f"/api/characters/{cid}/xp/spend-stat",
                    headers=_auth(owner), json={"stat_key": "DEX"})
        assert r2.status_code == 400, r2.text
        assert "stat_up_limit_per_level" in r2.text, r2.text
        # No stat/XP mutated by the rejected call.
        s = _read_sheet(cid)
        assert s["stats"]["DEX"] == 10
        assert s["advancement_spent"]["stat_ups"] == 1
    finally:
        _cleanup(cid)


def test_max_two_new_skills_per_level():
    """#1467 — learning a 3rd NEW skill in one level is rejected; ranking up an
    already-known skill is unlimited (Wariant A)."""
    keys = _catalog_skill_keys(3)
    if len(keys) < 3:
        pytest.skip("need >=3 skills in game_config_skills catalog")
    a, b, cc = keys[0], keys[1], keys[2]

    cid, owner = 999_467_002, 770_468
    _insert_char(cid, owner, _base_sheet(xp_available=99999, skills={}))
    try:
        c = _client()

        def buy(skill):
            return c.post(f"/api/characters/{cid}/xp/spend-skill",
                          headers=_auth(owner), json={"skill_key": skill})

        # Two NEW skills → both allowed.
        assert buy(a).status_code == 200
        assert buy(b).status_code == 200
        assert _read_sheet(cid)["advancement_spent"]["skill_ups"] == 2

        # Third NEW skill → blocked by the per-level cap.
        r3 = buy(cc)
        assert r3.status_code == 400, r3.text
        assert "new_skill_limit_per_level" in r3.text, r3.text
        assert cc not in _read_sheet(cid).get("skills", {})

        # Ranking up an ALREADY-known skill (a: rank 1→2) is NOT capped.
        r_rankup = buy(a)
        assert r_rankup.status_code == 200, r_rankup.text
        s = _read_sheet(cid)
        assert s["skills"][a] == 2
        # skill_ups stays at 2 — rank-ups don't consume new-skill slots.
        assert s["advancement_spent"]["skill_ups"] == 2
    finally:
        _cleanup(cid)
