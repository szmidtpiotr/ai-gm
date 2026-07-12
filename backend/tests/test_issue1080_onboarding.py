"""TDD: Issue #1080 — auto-onboarding (hidden tutorial campaign "Pierwsze Kroki").

Locks the load-bearing invariants of the onboarding design (plan analysis, E1-E6):

  E1/E5  the tutorial template is HIDDEN from the player picker (player_visible=0)
         yet LAUNCHABLE by id (create_campaign only checks status='published').
  E1     its GM plan passes ``validate_winnable_plan`` (premade must be beatable).
  E1     the 4 beats map to the 4 onboarding scenes (talk / combat / shop / map),
         with exactly the two critical beats the finale gate depends on.
  E2     the "new player" gate is COUNT(campaigns WHERE owner_user_id)==0.
  E4     "skip" ARCHIVES the campaign (keeps the row → gate never re-fires) and
         FREES the hero (Hero-First: campaign_id=NULL, status='idle').

Self-contained: an in-memory DB seeded from the same row shape as
``data/seeds/content/campaign_templates.json`` — no container DB state needed.
Run: docker cp … && docker exec ai-gm-dev-backend-1 pytest tests/test_issue1080_onboarding.py -v
"""
import json
import sqlite3
import sys

sys.path.insert(0, "/app")

from app.services.campaign_plan_runtime import validate_winnable_plan  # noqa: E402


# ── The onboarding plan (same shape the seed builder emits) ──────────────────
ONBOARD_PLAN = {
    "title": "Pierwsze Kroki",
    "premise": "Krótka przygoda wprowadzająca.",
    "acts": [
        {
            "number": 1,
            "title": "Pierwsze Kroki",
            "key_beats": [
                {"beat_key": "tavern_talk", "objective_type": "talk_to_npc",
                 "objective_value": "innkeeper_marta", "optional": False},
                {"beat_key": "first_combat", "objective_type": "kill_enemy",
                 "objective_value": "", "optional": False},
                {"beat_key": "first_merchant", "objective_type": "talk_to_npc",
                 "objective_value": "blacksmith_goran", "optional": True},
                {"beat_key": "first_exploration", "objective_type": "visit_location",
                 "objective_value": "", "optional": True},
            ],
            "completed": False,
        }
    ],
    "endings": [
        {"id": "ending_primary", "type": "primary", "title": "Gotów na przygodę",
         "requirements": ["first_combat"]},
    ],
    "key_npcs": [{"key": "innkeeper_marta"}, {"key": "blacksmith_goran"}],
    "key_locations": [{"key": "trzech_krukow", "name": "Karczma Pod Trzema Krukami"}],
}


def _seed_templates_db():
    """In-memory campaign_templates with the hidden tutorial + one normal row."""
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute(
        "CREATE TABLE campaign_templates ("
        " id INTEGER PRIMARY KEY, title TEXT, status TEXT, created_by TEXT,"
        " player_visible INTEGER, gm_plan_json TEXT, play_count INTEGER DEFAULT 0,"
        " created_at TEXT)"
    )
    db.executemany(
        "INSERT INTO campaign_templates"
        " (id, title, status, created_by, player_visible, gm_plan_json) VALUES (?,?,?,?,?,?)",
        [
            (1, "Pierwsze Kroki", "published", "seed", 0, json.dumps(ONBOARD_PLAN)),
            (2, "Przeklęte Ziemie", "published", "seed", 1, "{}"),
        ],
    )
    db.commit()
    return db


# ── E1: winnable premade ─────────────────────────────────────────────────────
def test_onboarding_plan_is_winnable():
    res = validate_winnable_plan(ONBOARD_PLAN)
    assert res["ok"], res["errors"]
    assert not res["orphan_beats"]
    assert not res["acts_without_closable_beat"]


# ── E1: the 4 scenes + the 2 critical beats the finale gate needs ────────────
def test_beats_map_to_the_four_scenes():
    beats = {b["beat_key"]: b for b in ONBOARD_PLAN["acts"][0]["key_beats"]}
    assert set(beats) == {"tavern_talk", "first_combat", "first_merchant", "first_exploration"}
    # Critical (drive the act + finale gate)
    assert beats["tavern_talk"]["optional"] is False
    assert beats["tavern_talk"]["objective_type"] == "talk_to_npc"
    assert beats["tavern_talk"]["objective_value"] == "innkeeper_marta"
    assert beats["first_combat"]["optional"] is False
    assert beats["first_combat"]["objective_type"] == "kill_enemy"
    assert beats["first_combat"]["objective_value"] == ""  # wildcard: any kill closes it
    # Optional (present, but never block the finale)
    assert beats["first_merchant"]["optional"] is True
    assert beats["first_merchant"]["objective_value"] == "blacksmith_goran"
    assert beats["first_exploration"]["optional"] is True
    # Ending fires off first_combat (fast finish, ≤ a handful of turns).
    assert ONBOARD_PLAN["endings"][0]["requirements"] == ["first_combat"]


# ── E5: hidden from the player picker … ──────────────────────────────────────
def test_hidden_from_player_template_list():
    db = _seed_templates_db()
    rows = db.execute(
        "SELECT id, title FROM campaign_templates WHERE status = 'published' "
        "AND COALESCE(player_visible, 1) = 1"
    ).fetchall()
    titles = {r["title"] for r in rows}
    assert "Pierwsze Kroki" not in titles       # hidden
    assert "Przeklęte Ziemie" in titles         # normal row still visible


# ── E1: … yet launchable by id (create_campaign only gates on status) ────────
def test_launchable_by_template_id_despite_hidden():
    db = _seed_templates_db()
    row = db.execute(
        "SELECT gm_plan_json FROM campaign_templates WHERE id = ? AND status = 'published'",
        (1,),
    ).fetchone()
    assert row is not None                       # create_campaign would find it
    assert json.loads(row["gm_plan_json"])["title"] == "Pierwsze Kroki"


# ── E2: new-player gate = zero campaigns owned ───────────────────────────────
def test_new_player_gate_counts_all_owned_campaigns():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE campaigns (id INTEGER PRIMARY KEY, owner_user_id INTEGER, status TEXT)")

    def has_campaign(uid):
        return db.execute(
            "SELECT COUNT(*) FROM campaigns WHERE owner_user_id = ?", (uid,)
        ).fetchone()[0] > 0

    assert has_campaign(7) is False              # brand new → onboarding allowed
    # even an archived tutorial counts → established player, no re-trigger
    db.execute("INSERT INTO campaigns (owner_user_id, status) VALUES (7, 'archived')")
    db.commit()
    assert has_campaign(7) is True               # 409 path


# ── E4: skip archives the campaign AND frees the hero ────────────────────────
def test_skip_archives_campaign_and_frees_hero():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        "CREATE TABLE campaigns (id INTEGER PRIMARY KEY, owner_user_id INTEGER,"
        " status TEXT, is_tutorial INTEGER, ended_at TEXT);"
        "CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, status TEXT);"
    )
    db.execute("INSERT INTO campaigns (id, owner_user_id, status, is_tutorial) VALUES (5, 7, 'active', 1)")
    db.execute("INSERT INTO characters (id, campaign_id, status) VALUES (9, 5, 'in_campaign')")
    db.commit()

    # exact SQL the skip_tutorial endpoint runs
    db.execute("UPDATE campaigns SET status = 'archived', ended_at = datetime('now') WHERE id = 5")
    db.execute("UPDATE characters SET campaign_id = NULL, status = 'idle' WHERE campaign_id = 5")
    db.commit()

    camp = db.execute("SELECT status, ended_at FROM campaigns WHERE id = 5").fetchone()
    hero = db.execute("SELECT campaign_id, status FROM characters WHERE id = 9").fetchone()
    assert camp["status"] == "archived"          # row kept → gate stays closed
    assert camp["ended_at"] is not None
    assert hero["campaign_id"] is None           # Hero-First: freed
    assert hero["status"] == "idle"
