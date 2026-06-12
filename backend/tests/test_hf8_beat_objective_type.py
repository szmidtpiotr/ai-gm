"""TDD: #539 HF-8 — objective_type w key_beats szablonów kampanii.

Problemy:
1. auto_complete_beats_by_event() wymaga niepustej objective_value — pusta = nigdy nie pasuje.
   Spec (U8) mówi objective_value jest OPCJONALNE (puste = match any target).
2. Beaty w seedach kampanii nie mają objective_type → mechanizm U8 martwy w Gotowej Kampanii.
"""
import json
import sqlite3
import sys

sys.path.insert(0, "/app")


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_db(plan_dict):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY,
            gm_plan_json TEXT
        );
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER,
            session_flags TEXT DEFAULT '{}'
        );
    """)
    conn.execute("INSERT INTO campaigns VALUES (1, ?)", (json.dumps(plan_dict),))
    conn.execute("INSERT INTO game_sessions VALUES (1, 1, '{}')")
    conn.commit()
    return conn


def _plan(*beats):
    return {"acts": [{"key_beats": list(beats)}]}


def _beat(key, objective_type=None, objective_value=None, visited=False):
    b = {"beat_key": key, "label": f"Beat {key}", "visited": visited}
    if objective_type is not None:
        b["objective_type"] = objective_type
    if objective_value is not None:
        b["objective_value"] = objective_value
    return b


# ─── FAZA RED: testy które MUSZĄ failować przed naprawą ──────────────────────


def test_beat_objective_type_no_value_matches_any_kill():
    """Beat z objective_type=kill_enemy i BEZ objective_value powinien kompletować na KAŻDYM kill."""
    from app.services.campaign_plan_runtime import auto_complete_beats_by_event

    # Symuluje beat z szablonu po naprawie seeda — jest objective_type, brak objective_value
    beat = _beat("first_combat", objective_type="kill_enemy")  # no objective_value
    conn = _make_db(_plan(beat))

    result = auto_complete_beats_by_event(1, "kill_enemy", "Jakikolwiek Wróg", 3, conn)
    assert result is True, (
        "Beat bez objective_value powinien auto-kompletować na KAŻDYM kill_enemy — "
        "objective_value jest OPCJONALNE (spec U8)"
    )


def test_beat_objective_type_empty_string_value_matches_any():
    """Beat z objective_type i objective_value='' (jawnie puste) pasuje do dowolnego celu."""
    from app.services.campaign_plan_runtime import auto_complete_beats_by_event

    beat = _beat("first_merchant", objective_type="talk_to_npc", objective_value="")
    conn = _make_db(_plan(beat))

    result = auto_complete_beats_by_event(1, "talk_to_npc", "Nieznany Kupiec", 5, conn)
    assert result is True, "Jawnie pusta objective_value = wildcard (match any NPC)"


def test_migration_adds_objective_type_to_seed_templates():
    """Migracja HF-8 dodaje objective_type do beatów w seedowanych szablonach kampanii."""
    from app.migrations_admin import _patch_campaign_template_beat_objectives

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE campaign_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            difficulty_rating INTEGER NOT NULL DEFAULT 3,
            atmosphere TEXT,
            gm_plan_json TEXT NOT NULL DEFAULT '{}',
            hook_ids TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'draft',
            play_count INTEGER NOT NULL DEFAULT 0,
            created_by TEXT NOT NULL DEFAULT 'admin',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            required_npc_keys TEXT NOT NULL DEFAULT '[]',
            required_beats TEXT NOT NULL DEFAULT '[]',
            player_visible INTEGER NOT NULL DEFAULT 1
        );
    """)
    # Wstaw stary template BEZ objective_type (stan przed HF-8)
    old_plan = json.dumps({
        "arcs": [{
            "id": "arc_tutorial",
            "label": "Tutorial",
            "key_beats": [
                {"beat_key": "first_combat", "label": "Pierwsza walka"},
                {"beat_key": "first_merchant", "label": "Pierwszy handel"},
                {"beat_key": "first_exploration", "label": "Pierwsza eksploracja"},
            ],
            "status": "active"
        }]
    })
    conn.execute(
        "INSERT INTO campaign_templates (title, gm_plan_json, status, created_by) VALUES (?,?,?,?)",
        ("Pierwsze Kroki", old_plan, "published", "seed"),
    )
    conn.commit()

    # Uruchom migrację
    _patch_campaign_template_beat_objectives(conn)

    # Sprawdź wynik
    row = conn.execute(
        "SELECT gm_plan_json FROM campaign_templates WHERE title='Pierwsze Kroki'"
    ).fetchone()
    plan = json.loads(row[0])
    beats = plan["arcs"][0]["key_beats"]

    assert beats[0].get("objective_type") == "kill_enemy", (
        "first_combat powinien mieć objective_type=kill_enemy"
    )
    assert beats[1].get("objective_type") == "talk_to_npc", (
        "first_merchant powinien mieć objective_type=talk_to_npc"
    )
    assert beats[2].get("objective_type") == "visit_location", (
        "first_exploration powinien mieć objective_type=visit_location"
    )


# ─── Backward compat: te testy muszą być GREEN przed I po naprawie ───────────


def test_beat_no_objective_type_ignored():
    """Beat BEZ objective_type nadal wymaga tagu BEAT_COMPLETE od LLM — nie zmienia się."""
    from app.services.campaign_plan_runtime import auto_complete_beats_by_event

    beat = _beat("pure_narrative")  # no objective_type, no objective_value
    conn = _make_db(_plan(beat))

    result = auto_complete_beats_by_event(1, "kill_enemy", "Dowolny Wróg", 1, conn)
    assert result is False, "Beat bez objective_type NIE powinien auto-kompletować"

    plan = json.loads(conn.execute("SELECT gm_plan_json FROM campaigns WHERE id=1").fetchone()[0])
    assert plan["acts"][0]["key_beats"][0].get("visited", False) is False


def test_beat_specific_value_matches_correct_target():
    """Beat z konkretną objective_value kompletuje się tylko przy dopasowanym celu."""
    from app.services.campaign_plan_runtime import auto_complete_beats_by_event

    beat = _beat("kill_boss", objective_type="kill_enemy", objective_value="Goblin Szef")
    conn = _make_db(_plan(beat))

    result = auto_complete_beats_by_event(1, "kill_enemy", "Goblin Szef", 8, conn)
    assert result is True


def test_beat_specific_value_no_match_wrong_target():
    """Beat z konkretną objective_value NIE kompletuje się przy złym celu."""
    from app.services.campaign_plan_runtime import auto_complete_beats_by_event

    beat = _beat("kill_boss", objective_type="kill_enemy", objective_value="Goblin Szef")
    conn = _make_db(_plan(beat))

    result = auto_complete_beats_by_event(1, "kill_enemy", "Inny Potwór", 8, conn)
    assert result is False
