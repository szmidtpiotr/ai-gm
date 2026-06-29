"""TDD: Issue #1021 — minimalna grywalna kampania testowa (2 akty × 1 beat).

Deterministyczny test-bed trylogii #1009–#1020:
  - Akt 1, beat `reach_first_place`: visit_location, objective_value="" (wildcard) →
    auto-complete przy pierwszym ruchu do JAKIEJKOLWIEK lokacji.
  - Akt 2, beat `meet_the_elder`: talk_to_npc, objective_value="" (wildcard) →
    auto-complete przy pierwszej rozmowie z JAKIMKOLWIEK NPC.
  - endings[] z 1 `primary` → overlay zwycięstwa.
  - 0 questów pobocznych, brak orphan-beatów, bez walki.

Po obu beatach: oba akty completed + 0 questów → campaigns.status='completed' + event.
"""
import sys, os, json, sqlite3

sys.path.insert(0, "/app")

import pytest

DB_PATH = os.environ.get("DB_PATH", "/data/ai_gm.db")

TEST_TEMPLATE_TITLE = "[TEST] Przejazd 2-akty — trylogia #1009"


# ─── Test główny — kształt planu wg specyfikacji issue ────────────────────────

def test_plan_shape_matches_spec():
    """Plan ma dokładnie 2 akty × 1 krytyczny beat, wildcardowe cele, endings primary."""
    from app.migrations_admin import build_test_trylogia_2act_plan
    plan = build_test_trylogia_2act_plan()

    acts = plan["acts"]
    assert len(acts) == 2, "spec: dokładnie 2 akty"

    # Akt 1 — reach_first_place / visit_location / wildcard / krytyczny
    b1 = acts[0]["key_beats"]
    assert len(b1) == 1
    assert b1[0]["beat_key"] == "reach_first_place"
    assert b1[0]["objective_type"] == "visit_location"
    assert b1[0]["objective_value"] == ""           # wildcard
    assert b1[0].get("optional") is False

    # Akt 2 — meet_the_elder / talk_to_npc / wildcard / krytyczny
    b2 = acts[1]["key_beats"]
    assert len(b2) == 1
    assert b2[0]["beat_key"] == "meet_the_elder"
    assert b2[0]["objective_type"] == "talk_to_npc"
    assert b2[0]["objective_value"] == ""           # wildcard
    assert b2[0].get("optional") is False

    # endings[] z ≥1 primary
    endings = plan["endings"]
    assert any(e.get("type") == "primary" for e in endings), "spec: 1 ending primary"


def test_plan_is_winnable_and_no_orphans():
    """Plan przechodzi bramkę #1020 (winnable) i nie ma orphan-beatów (#1010)."""
    from app.migrations_admin import build_test_trylogia_2act_plan
    from app.services.campaign_plan_runtime import (
        validate_winnable_plan, find_orphan_beats,
    )
    plan = build_test_trylogia_2act_plan()
    assert find_orphan_beats(plan) == [], "brak orphan-beatów (oba beaty mają objective_type)"
    res = validate_winnable_plan(plan)
    assert res["ok"] is True, res


# ─── Integracja — pełna symulacja zwycięstwa na realnym runtime ───────────────

def _migrate():
    from app.migrations_admin import run_admin_migrations
    run_admin_migrations()


def _mk_campaign(plan):
    """Wstrzyknij tymczasową kampanię z planem; zwróć (campaign_id, character_id)."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "INSERT INTO campaigns (title, system_id, model_id, owner_user_id, "
            "status, gm_plan_json) VALUES (?, 'dnd5e', 'stub', 1, 'active', ?)",
            (TEST_TEMPLATE_TITLE + " [sim]", json.dumps(plan, ensure_ascii=False)),
        )
        cid = cur.lastrowid
        conn.commit()
        return cid, 999999  # character_id arbitralny — brak questów = count 0
    finally:
        conn.close()


def _rm_campaign(cid):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM campaigns WHERE id = ?", (cid,))
        try:
            conn.execute("DELETE FROM game_events WHERE campaign_id = ?", (cid,))
        except sqlite3.OperationalError:
            pass
        conn.commit()
    finally:
        conn.close()


def test_full_victory_simulation():
    """Ruch (visit_location) → akt 1 completed; rozmowa (talk_to_npc) → akt 2 completed;
    is_plan_complete → True; maybe_complete_campaign → status='completed' + event."""
    _migrate()
    from app.migrations_admin import build_test_trylogia_2act_plan
    from app.services.campaign_plan_runtime import (
        auto_complete_beats_by_event, is_plan_complete,
        maybe_complete_campaign, get_plan,
    )
    cid, char_id = _mk_campaign(build_test_trylogia_2act_plan())
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # Akt 1 — ruch do JAKIEJKOLWIEK lokacji (wildcard) domyka reach_first_place
        changed1 = auto_complete_beats_by_event(cid, "visit_location", "Brama Wschodnia", 1, conn)
        assert changed1 is True, "wildcard visit_location musi domknąć beat aktu 1"
        plan = get_plan(cid, conn)
        assert plan["acts"][0].get("completed") is True, "akt 1 zamknięty po jedynym krytycznym beacie"
        assert int(plan.get("active_act", 1)) == 2, "wskaźnik aktu przeskoczył na 2"

        # Akt 2 — rozmowa z JAKIMKOLWIEK NPC (wildcard) domyka meet_the_elder
        changed2 = auto_complete_beats_by_event(cid, "talk_to_npc", "Starszy Osady", 2, conn)
        assert changed2 is True, "wildcard talk_to_npc musi domknąć beat aktu 2"
        plan = get_plan(cid, conn)
        assert plan["acts"][1].get("completed") is True, "akt 2 zamknięty"
        assert is_plan_complete(plan) is True, "wszystkie akty completed → plan kompletny"

        # Spinacz #1009 — 0 questów → status='completed' + event campaign_complete
        won = maybe_complete_campaign(cid, char_id, 2, conn)
        assert won is True, "victory spinacz musi odpalić raz"
        status = conn.execute("SELECT status FROM campaigns WHERE id = ?", (cid,)).fetchone()["status"]
        assert status == "completed", f"campaigns.status oczekiwano 'completed', jest '{status}'"
        ev = conn.execute(
            "SELECT COUNT(*) FROM game_events WHERE campaign_id = ? AND event_type = 'campaign_complete'",
            (cid,),
        ).fetchone()[0]
        assert ev >= 1, "event campaign_complete musi zostać zapisany"

        # Idempotencja — drugie wywołanie nie odpala ponownie
        assert maybe_complete_campaign(cid, char_id, 3, conn) is False
    finally:
        conn.close()
        _rm_campaign(cid)


# ─── Seed — opublikowany szablon [TEST] w campaign_templates ──────────────────

def test_seed_template_published_and_winnable():
    """Po migracjach istnieje opublikowany seed-szablon [TEST], winnable, player_visible."""
    _migrate()
    from app.migrations_admin import seed_test_trylogia_template
    from app.services.campaign_plan_runtime import validate_winnable_plan

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        seed_test_trylogia_template(conn)  # idempotentne
        row = conn.execute(
            "SELECT status, created_by, player_visible, gm_plan_json FROM campaign_templates "
            "WHERE title = ?", (TEST_TEMPLATE_TITLE,),
        ).fetchone()
        assert row is not None, "seed-szablon [TEST] musi istnieć po migracjach"
        assert row["status"] == "published"
        assert row["created_by"] == "seed"
        assert int(row["player_visible"]) == 1
        plan = json.loads(row["gm_plan_json"])
        # plan zapisany z `acts` (kanon V2) — winnable bezpośrednio
        assert validate_winnable_plan(plan)["ok"] is True, validate_winnable_plan(plan)
    finally:
        conn.close()


def test_seed_is_idempotent():
    """Dwukrotny seed nie tworzy duplikatu szablonu [TEST]."""
    _migrate()
    from app.migrations_admin import seed_test_trylogia_template
    conn = sqlite3.connect(DB_PATH)
    try:
        seed_test_trylogia_template(conn)
        seed_test_trylogia_template(conn)
        n = conn.execute(
            "SELECT COUNT(*) FROM campaign_templates WHERE title = ?", (TEST_TEMPLATE_TITLE,)
        ).fetchone()[0]
        assert n == 1, f"oczekiwano 1 szablonu [TEST], jest {n}"
    finally:
        conn.close()


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_seed_does_not_touch_other_templates():
    """Seed [TEST] nie modyfikuje istniejących seed-szablonów (planów ani liczby)."""
    _migrate()
    from app.migrations_admin import seed_test_trylogia_template
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        def _snapshot():
            return {
                r["title"]: r["gm_plan_json"]
                for r in conn.execute(
                    "SELECT title, gm_plan_json FROM campaign_templates "
                    "WHERE created_by = 'seed' AND title != ?", (TEST_TEMPLATE_TITLE,),
                ).fetchall()
            }
        before = _snapshot()
        assert before, "bazowe seed-szablony muszą istnieć"
        seed_test_trylogia_template(conn)
        after = _snapshot()
        assert after == before, "seed [TEST] nie może zmienić innych seed-szablonów"
    finally:
        conn.close()
