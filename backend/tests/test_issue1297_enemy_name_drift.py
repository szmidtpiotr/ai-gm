"""TDD: Issue #1297 — narrator name-drift: enemy introduced under an invented name.

Wzmacniamy blok WROGOWIE TEJ KAMPANII, żeby narrator używał kanonicznego imienia
wroga z planu (np. „Harl") już przy pierwszym wprowadzeniu do narracji, a nie tylko
przy [COMBAT_START]. Test kontraktowy na treść bloku.
"""
import sqlite3
import json

from app.services.context_injector import build_plan_enemy_keys_block


def _mkdb() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE campaigns (id INTEGER PRIMARY KEY, gm_plan_json TEXT)")
    conn.execute(
        """CREATE TABLE game_config_enemies (
            key TEXT PRIMARY KEY, label TEXT, tier TEXT,
            hp_base INTEGER, ac_base INTEGER, is_active INTEGER DEFAULT 1
        )"""
    )
    return conn


_PLAN = {"key_enemies": [
    {"key": "herszt_wyrostkow_harl", "name": "Harl", "tier": "elite", "alive": True},
]}


def _seed(conn, cid=9998881):
    conn.execute("INSERT INTO campaigns (id, gm_plan_json) VALUES (?, ?)", (cid, json.dumps(_PLAN)))
    conn.execute(
        "INSERT INTO game_config_enemies (key,label,tier,hp_base,ac_base,is_active) VALUES (?,?,?,?,?,1)",
        ("herszt_wyrostkow_harl", "Harl", "elite", 30, 12),
    )
    conn.commit()


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_block_instructs_canonical_name_in_narration():
    """Blok wymusza użycie kanonicznego imienia wroga w NARRACJI, nie tylko klucza."""
    conn = _mkdb()
    _seed(conn)
    block = build_plan_enemy_keys_block(conn, 9998881)
    # nowa dyrektywa o imieniu w narracji (nie tylko o [COMBAT_START] kluczu)
    assert "imieniem" in block.lower() or "imienia" in block.lower()
    assert "narracj" in block.lower()
    # imię wroga nadal obecne
    assert "Harl" in block


def test_block_still_lists_combat_start_key():
    """Backward compat: klucz [COMBAT_START] nadal listowany."""
    conn = _mkdb()
    _seed(conn)
    block = build_plan_enemy_keys_block(conn, 9998881)
    assert "herszt_wyrostkow_harl" in block
    assert "COMBAT_START" in block


def test_block_empty_when_no_live_enemies():
    conn = _mkdb()
    conn.execute("INSERT INTO campaigns (id, gm_plan_json) VALUES (?, ?)", (556, json.dumps({"key_enemies": []})))
    conn.commit()
    assert build_plan_enemy_keys_block(conn, 556) == ""
