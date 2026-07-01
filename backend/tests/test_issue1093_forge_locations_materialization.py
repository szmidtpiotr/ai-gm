"""TDD: Issue #1093 — Forge: materializacja encji planu GM w DB (NPC + lokacje).

Root cause:
- #1081: tpl.get("atmosphere") / idea.get("tone") crash na sqlite3.Row (brak .get())
- #1092: _auto_create_forge_locations() nie istnieje → key_locations nie trafiają do game_locations
"""
import sys, os, sqlite3, json, pytest
sys.path.insert(0, "/app")

from app.routers.adventure_forge import _auto_create_forge_npcs


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            label TEXT NOT NULL,
            description TEXT,
            location_type TEXT DEFAULT 'macro',
            rules TEXT,
            enemy_keys TEXT DEFAULT '[]',
            npc_keys TEXT DEFAULT '[]',
            is_active INTEGER DEFAULT 1,
            created_at TEXT,
            updated_at TEXT,
            ai_generated INTEGER DEFAULT 0,
            approved INTEGER DEFAULT 1,
            created_by TEXT DEFAULT 'forge',
            canonical INTEGER DEFAULT 0,
            source_campaign_id INTEGER,
            map_x REAL,
            map_y REAL,
            map_icon TEXT NOT NULL DEFAULT 'town',
            visible_before_visit INTEGER NOT NULL DEFAULT 0,
            safe_for_rest INTEGER NOT NULL DEFAULT 0,
            review_status TEXT NOT NULL DEFAULT 'permanent',
            parent_key TEXT,
            location_subtype TEXT,
            biome TEXT,
            tier INTEGER NOT NULL DEFAULT 1,
            usage_count INTEGER NOT NULL DEFAULT 0,
            temporary INTEGER NOT NULL DEFAULT 0,
            world_hex_q INTEGER,
            world_hex_r INTEGER,
            terrain_tags TEXT NOT NULL DEFAULT '[]',
            placement TEXT NOT NULL DEFAULT 'floating',
            region TEXT
        );
        CREATE TABLE npcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL,
            npc_type TEXT NOT NULL DEFAULT 'neutral',
            description TEXT,
            personality_json TEXT NOT NULL DEFAULT '{}',
            is_shop INTEGER NOT NULL DEFAULT 0,
            shop_inventory_json TEXT NOT NULL DEFAULT '[]',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            is_quest_giver INTEGER NOT NULL DEFAULT 0,
            is_ally INTEGER NOT NULL DEFAULT 0,
            personality_prompt TEXT DEFAULT NULL,
            keyword_triggers TEXT NOT NULL DEFAULT '[]',
            review_status TEXT NOT NULL DEFAULT 'permanent',
            is_dead INTEGER DEFAULT 0,
            is_crafter INTEGER NOT NULL DEFAULT 0,
            stats_json TEXT,
            image_url TEXT,
            image_url_raw TEXT,
            image_gen_prompt TEXT
        );
        CREATE TABLE campaign_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            required_npc_keys TEXT,
            required_beats TEXT,
            gm_plan_json TEXT,
            atmosphere TEXT
        );
        CREATE TABLE adventure_ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tone TEXT,
            structured_data TEXT
        );
    """)
    return conn


SAMPLE_LOCATIONS = [
    {"key": "karczma_pod_zolwiem", "name": "Karczma pod Żółwiem",
     "role": "starting point — tavern where the hero begins"},
    {"key": "kopalnia_czarnej_rudy",  "name": "Kopalnia Czarnej Rudy",
     "role": "boss lair"},
]

SAMPLE_NPCS = [
    {"key": "brunn_zelaznoreki", "name": "Brunn Żelaznoreki", "role": "Kowal protagonista"},
]


# ─── #1092 RED: _auto_create_forge_locations inserts rows ───────────────────

def test_auto_create_forge_locations_inserts_rows():
    """_auto_create_forge_locations() must insert game_locations rows with review_status='pending'."""
    from app.routers.adventure_forge import _auto_create_forge_locations

    conn = _make_db()
    created = _auto_create_forge_locations(conn, template_id=1, locations=SAMPLE_LOCATIONS)

    assert len(created) == 2, f"Expected 2 created, got {len(created)}"

    rows = conn.execute(
        "SELECT key, label, review_status, is_active, created_by FROM game_locations ORDER BY key"
    ).fetchall()
    keys = [r["key"] for r in rows]
    assert "karczma_pod_zolwiem" in keys
    assert "kopalnia_czarnej_rudy" in keys

    for row in rows:
        assert row["review_status"] == "pending", f"{row['key']} must have review_status=pending"
        assert row["is_active"] == 1, f"{row['key']} must be is_active=1"
        assert row["created_by"] == "forge", f"{row['key']} must have created_by=forge"


def test_auto_create_forge_locations_idempotent():
    """Calling _auto_create_forge_locations() twice must not duplicate rows."""
    from app.routers.adventure_forge import _auto_create_forge_locations

    conn = _make_db()
    _auto_create_forge_locations(conn, template_id=1, locations=SAMPLE_LOCATIONS)
    _auto_create_forge_locations(conn, template_id=1, locations=SAMPLE_LOCATIONS)

    count = conn.execute("SELECT COUNT(*) FROM game_locations").fetchone()[0]
    assert count == 2, f"Expected 2 locations (idempotent), got {count}"


def test_auto_create_forge_locations_empty_list():
    """_auto_create_forge_locations() with empty list returns [] without error."""
    from app.routers.adventure_forge import _auto_create_forge_locations

    conn = _make_db()
    result = _auto_create_forge_locations(conn, template_id=1, locations=[])
    assert result == []


# ─── #1081 RED: _auto_fill_plan_fields does not crash on sqlite3.Row ─────────

def test_auto_fill_plan_fields_survives_row_with_idea():
    """_auto_fill_plan_fields must not crash when tpl and idea are sqlite3.Row objects.

    Before fix: tpl.get("atmosphere") raises AttributeError on sqlite3.Row.
    After fix: should work and return proper result dict.
    """
    from app.routers.adventure_forge import _auto_fill_plan_fields

    conn = _make_db()
    conn.execute(
        "INSERT INTO campaign_templates (id, required_npc_keys, required_beats, gm_plan_json, atmosphere)"
        " VALUES (1, '[]', '[]', '{}', '')"
    )
    conn.execute(
        "INSERT INTO adventure_ideas (id, tone, structured_data) VALUES (1, '[\"mroczny\"]', '{}')"
    )
    conn.commit()

    tpl_row = conn.execute("SELECT * FROM campaign_templates WHERE id = 1").fetchone()
    idea_row = conn.execute("SELECT * FROM adventure_ideas WHERE id = 1").fetchone()

    plan_public = {
        "key_npcs": [{"key": "brunn", "name": "Brunn"}],
        "acts": [{"key_beats": [{"beat_key": "start", "optional": False}]}],
    }

    # Must not raise AttributeError
    result = _auto_fill_plan_fields(
        conn, tpl_id=1, tpl=tpl_row, idea=idea_row, plan_public=plan_public
    )
    assert "auto_filled_npc_keys" in result
    assert "auto_filled_beat_keys" in result
    assert "auto_filled_atmosphere" in result
    assert result["auto_filled_atmosphere"] == "mroczny"


def test_auto_fill_plan_fields_survives_row_without_idea():
    """_auto_fill_plan_fields must not crash when idea=None (most common path)."""
    from app.routers.adventure_forge import _auto_fill_plan_fields

    conn = _make_db()
    conn.execute(
        "INSERT INTO campaign_templates (id, required_npc_keys, required_beats, gm_plan_json, atmosphere)"
        " VALUES (1, '[]', '[]', '{}', NULL)"
    )
    conn.commit()

    tpl_row = conn.execute("SELECT * FROM campaign_templates WHERE id = 1").fetchone()
    plan_public = {"key_npcs": [], "acts": []}

    result = _auto_fill_plan_fields(conn, tpl_id=1, tpl=tpl_row, idea=None, plan_public=plan_public)
    assert result["auto_filled_atmosphere"] == ""


# ─── #1093 integration: forge_generate_plan calls _auto_create_forge_locations ─

def test_forge_generate_plan_includes_locations_in_return():
    """forge_generate_template_plan must include auto_created_locations in response.

    Uses a unique run_id suffix so each test invocation creates fresh location keys,
    avoiding the idempotency short-circuit (INSERT OR IGNORE) that returns [] when
    keys already exist from a previous test run.
    """
    import unittest.mock as mock
    import time
    from fastapi.testclient import TestClient
    from app.main import app

    run_id = str(int(time.time()))[-6:]
    loc_key_a = f"test_karczma_{run_id}"
    loc_key_b = f"test_kopalnia_{run_id}"

    VALID_PLAN = {
        "title": "Żar w Gasnącej Kuźni",
        "premise": "Bohater musi odnaleźć skradziony miecz.",
        "acts": [
            {
                "number": 1,
                "title": "Wstęp",
                "summary": "Bohater wyrusza",
                "key_beats": [
                    {"beat_key": f"start_beat_{run_id}", "summary": "Zacznij", "optional": False}
                ],
            }
        ],
        "endings": [
            {
                "id": "good_end",
                "title": "Zwycięstwo",
                "type": "primary",
                "description": "Bohater pokonuje antagonistę.",
                "requirements": ["kill_boss"],
            }
        ],
        "key_npcs": [
            {
                "key": f"brunn_{run_id}",
                "name": "Brunn",
                "role": "kowal",
                "importance": "critical",
                "deviation_consequence": "steer",
                "alive": True,
            }
        ],
        "key_locations": [
            {"key": loc_key_a, "name": "Karczma pod Żółwiem",
             "role": "starting point", "visited": False},
            {"key": loc_key_b, "name": "Kopalnia", "role": "boss lair", "visited": False},
        ],
        "key_enemies": [],
        "engine_private": {
            "secret_predisposition_hint": "hint",
            "hidden_twist": "twist",
            "contingency": "cont",
        },
    }

    client = TestClient(app)
    r = client.post("/api/admin/dev-login", json={"username": "demo", "password": "demo"})
    assert r.status_code == 200, f"login failed: {r.text}"
    token = r.json()["token"]

    templates_r = client.get(
        "/api/admin/forge/templates",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert templates_r.status_code == 200
    templates = templates_r.json().get("items", [])
    if not templates:
        # Create a minimal template if none exist
        cr = client.post(
            "/api/admin/forge/templates",
            headers={"Authorization": f"Bearer {token}"},
            json={"title": "Test #1093", "genre": "fantasy", "tone": "heroic", "act_count": 1},
        )
        assert cr.status_code in (200, 201), f"create template failed: {cr.text}"
        template_id = cr.json()["id"]
    else:
        template_id = templates[0]["id"]

    from app.services.llm_service import set_runtime_config
    set_runtime_config("openai", "https://api.openai.com/v1", "gpt-5.4", "test-key")

    with mock.patch(
        "app.services.llm_service.OpenAIDriver.generate_chat",
        return_value=json.dumps(VALID_PLAN),
    ):
        resp = client.post(
            f"/api/admin/forge/templates/{template_id}/generate-plan",
            headers={"Authorization": f"Bearer {token}"},
            json={"suggested_act_count": 1},
        )

    assert resp.status_code == 200, (
        f"Expected 200 got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    assert "auto_created_locations" in body, (
        "Response must include auto_created_locations key (#1092)"
    )
    # Fresh unique keys → should be created in this run
    created_keys = [loc["key"] for loc in body["auto_created_locations"]]
    assert loc_key_a in created_keys, (
        f"Expected {loc_key_a} in auto_created_locations, got {created_keys}"
    )
    assert loc_key_b in created_keys, (
        f"Expected {loc_key_b} in auto_created_locations, got {created_keys}"
    )
