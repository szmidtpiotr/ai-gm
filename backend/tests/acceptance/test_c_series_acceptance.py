"""Acceptance — C-series (FAZA 1) mechanical truth.

Deterministic backend assertions that complement the Playwright LLM-play
suite (ai_test_agent/playwright/ux/acceptance/c_series.spec.js). Runs INSIDE
the backend container: hits the live API on localhost:8100 and reads
/data/ai_gm.db directly (local file in-container, NOT an sshfs mount).

Unimplemented tasks fail here on purpose — this file is an executable backlog.

Run:
  docker exec ai-gm-dev-backend-1 pytest tests/acceptance/test_c_series_acceptance.py -v
"""
import json
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

DB_PATH = "/data/ai_gm.db"
# Inside the backend container uvicorn listens on :8000 (host maps 8100→8000).
BASE = "http://localhost:8000"


# ── helpers ──────────────────────────────────────────────────────────────────

def _req(method: str, path: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}", data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode() or "{}")
        except Exception:
            payload = {}
        return e.code, payload


def _reset():
    status, data = _req("POST", "/api/debug/reset_test_env")
    assert status == 200 and data.get("reset"), f"reset_test_env failed: {status} {data}"
    return data


@pytest.fixture(scope="module")
def env():
    return _reset()


# ── C4 / C5 — wound penalty thresholds (pure unit) ──────────────────────────

def test_c04_wound_penalty_four_thresholds():
    """C4 — wound_penalty(hp_current, hp_max) maps HP% to 0/-1/-2/-4."""
    from app.services.wound_utils import wound_penalty

    assert wound_penalty(100, 100) == 0      # healthy
    assert wound_penalty(60, 100) == -1      # moderate
    assert wound_penalty(30, 100) == -2      # serious
    assert wound_penalty(10, 100) == -4      # critical
    assert wound_penalty(50, 0) == 0         # guard: no max → no penalty


def test_c05_wound_penalty_symmetric_for_enemies():
    """C5 — same HP-only util applies to enemies; combat_service uses it."""
    from app.services.wound_utils import wound_penalty
    import app.services.combat_service as cs
    import inspect

    # An enemy at 20% HP must incur the critical penalty exactly like a player.
    assert wound_penalty(20, 100) == -4
    # And the combat resolver must actually reference wound_penalty (symmetry).
    src = inspect.getsource(cs)
    assert "wound_penalty" in src, "combat_service nie używa wound_penalty (C5 symetria)"


# ── C6 — canonical wound thresholds endpoint ────────────────────────────────

def test_c06_wound_thresholds_endpoint():
    status, body = _req("GET", "/api/config/wound-thresholds")
    assert status == 200, f"/api/config/wound-thresholds → {status}"
    assert {"healthy_pct", "moderate_pct", "critical_pct"} <= set(body), body


# ── C7 / C8 — XP spend endpoints exist and validate ─────────────────────────

def test_c07_spend_xp_skill_endpoint_wired(env):
    status, body = _req(
        "POST", f"/api/characters/{env['character_id']}/spend-xp/skill",
        {"skill_key": "awareness"},
    )
    assert status != 404, "spend-xp/skill nie istnieje (C7)"
    assert status in (200, 400), f"nieoczekiwany status {status}: {body}"


def test_c08_spend_xp_stat_endpoint_wired(env):
    status, body = _req(
        "POST", f"/api/characters/{env['character_id']}/spend-xp/stat",
        {"stat_key": "STR"},
    )
    assert status != 404, "spend-xp/stat nie istnieje (C8)"
    assert status in (200, 400), f"nieoczekiwany status {status}: {body}"


def test_c08_spend_xp_stat_recalcs_hp_on_con(env):
    """C8 — spending XP on CON recomputes hp_max. Snapshot+restore the sheet so
    the seeded hero's stats do not drift across runs."""
    cid = env["character_id"]
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    orig = conn.execute("SELECT sheet_json FROM characters WHERE id=?", (cid,)).fetchone()["sheet_json"]
    try:
        sheet = json.loads(orig or "{}")
        stats = dict(sheet.get("stats") or {})
        con_key = next((k for k in stats if k.upper() == "CON"), "CON")
        # CON 11 → 12 crosses a modifier boundary (mod 0 → +1), so hp_max must rise.
        stats[con_key] = 11
        sheet["stats"] = stats
        sheet["xp_available"] = 1000
        sheet["level"] = int(sheet.get("level") or 1)
        sheet["max_hp"] = int(sheet.get("max_hp") or 10)
        hp_before = int(sheet["max_hp"])
        conn.execute(
            "UPDATE characters SET sheet_json=? WHERE id=?",
            (json.dumps(sheet, ensure_ascii=False), cid),
        )
        conn.commit()

        status, body = _req("POST", f"/api/characters/{cid}/spend-xp/stat", {"stat_key": "CON"})
        assert status == 200, f"spend-xp/stat CON nie powiódł się (C8): {status} {body}"

        row = conn.execute("SELECT sheet_json FROM characters WHERE id=?", (cid,)).fetchone()
        new_sheet = json.loads(row["sheet_json"] or "{}")
        assert int(new_sheet.get("max_hp", 0) or 0) > hp_before, "CON 11→12 nie podniosło hp_max (C8)"
    finally:
        conn.execute("UPDATE characters SET sheet_json=? WHERE id=?", (orig, cid))
        conn.commit()
        conn.close()


# ── C12 — SPEND_GOLD deterministic, ignores unknown keys ────────────────────

def test_c12_spend_gold_ignores_unknown_key():
    from app.services.spend_gold_service import parse_spend_gold_tags

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        tags = parse_spend_gold_tags("kupuję [SPEND_GOLD: __nonexistent_service__]", conn)
        assert tags == [], f"Nieznany klucz SPEND_GOLD nie został zignorowany (C12): {tags}"
    finally:
        conn.close()


def test_c12_spend_gold_module_contract():
    """C12 — prices resolve from config table, never from the LLM."""
    import app.services.spend_gold_service as sg

    assert hasattr(sg, "parse_spend_gold_tags")
    assert hasattr(sg, "spend_gold_on_service")


# ── C17 — inventory context injected so LLM won't narrate equipment loss ────

def test_c17_inventory_context_block_mentions_gear(env):
    """C17 — the per-turn inventory block lists the weapon + gold."""
    from app.services.inventory_context_service import build_inventory_block

    cid = env["character_id"]
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    wk = None
    try:
        wk = conn.execute(
            "SELECT key, label FROM game_config_weapons WHERE is_active = 1 LIMIT 1"
        ).fetchone()
        assert wk, "Brak broni w game_config_weapons do testu C17"
        conn.execute("UPDATE characters SET gold_gp = 123 WHERE id = ?", (cid,))
        conn.execute(
            "INSERT INTO character_inventory (character_id, weapon_key, slot, equipped) "
            "VALUES (?, ?, 'main_hand', 1)",
            (cid, wk["key"]),
        )
        conn.commit()

        block = build_inventory_block(conn, cid)
        assert block.strip(), "Pusty inventory block mimo broni i złota (C17)"
        assert "123" in block, "Złoto nie wstrzyknięte do kontekstu (C17)"
        weapon_word = (wk["label"] or wk["key"]).split()[0].lower()
        assert weapon_word in block.lower(), f"Broń '{weapon_word}' nie wymieniona (C17): {block[:200]}"
    finally:
        if wk is not None:
            conn.execute(
                "DELETE FROM character_inventory WHERE character_id = ? AND weapon_key = ?",
                (cid, wk["key"]),
            )
        conn.execute("UPDATE characters SET gold_gp = 0 WHERE id = ?", (cid,))
        conn.commit()
        conn.close()


# ── C18 — campaign starts on an existing/known hex ──────────────────────────

def test_c18_campaign_has_known_start_location(env):
    """C18 — the seeded test campaign must start on a real, non-empty location."""
    status, st = _req("GET", f"/api/debug/player_state?character_id={env['character_id']}")
    assert status == 200, st
    assert (st.get("location") or "").strip(), "Brak startowej lokacji kampanii (C18)"


def test_c18_world_has_start_hexes():
    """C18 — world is seeded and a (0,0) fallback hex exists for fresh heroes."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        try:
            total = conn.execute(
                "SELECT COUNT(*) AS n FROM world_hexes WHERE is_active = 1"
            ).fetchone()["n"]
            origin = conn.execute(
                "SELECT COUNT(*) AS n FROM world_hexes WHERE q = 0 AND r = 0"
            ).fetchone()["n"]
        except sqlite3.OperationalError:
            pytest.fail("Brak tabeli world_hexes (C18)")
        assert total >= 1, "Świat nie ma żadnych hexów (C18)"
        assert origin >= 1, "Brak hexa (0,0) jako fallback startu nowego bohatera (C18)"
    finally:
        conn.close()


# ── C19 — hero starts a campaign at full HP ─────────────────────────────────

def test_c19_full_hp_on_campaign_start(env):
    """C19 — after a fresh start the hero's current HP equals max HP."""
    status, st = _req("GET", f"/api/debug/player_state?character_id={env['character_id']}")
    assert status == 200, st
    assert st["hp"] == st["max_hp"], f"Bohater nie ma pełnego HP na starcie (C19): {st['hp']}/{st['max_hp']}"


# ── C2 — movement onto a non-existent hex is rejected ───────────────────────

def test_c02_invalid_teleport_does_not_change_location(env):
    """C2 — a bogus move must not silently relocate the player."""
    cid = env["character_id"]
    _, before = _req("GET", f"/api/debug/player_state?character_id={cid}")
    _req(
        "POST", f"/api/campaigns/{env['campaign_id']}/turns",
        {"character_id": cid, "text": "teleportuję się na nieistniejący hex 999,999"},
    )
    _, after = _req("GET", f"/api/debug/player_state?character_id={cid}")
    assert after.get("location") == before.get("location"), (
        f"Gracz przeniósł się na nieistniejący hex (C2): {before.get('location')} → {after.get('location')}"
    )
