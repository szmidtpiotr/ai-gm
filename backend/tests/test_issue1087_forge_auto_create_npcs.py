"""TDD: Issue #1087 — forge generate-plan auto-creates NPC records in npcs table."""
import sys, os, sqlite3, json, pytest
sys.path.insert(0, "/app")

from app.routers.adventure_forge import _auto_create_forge_npcs, validate_template_publish


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_db() -> sqlite3.Connection:
    """In-memory DB with minimal npcs + campaign_templates schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
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
            gm_plan_json TEXT
        );
    """)
    return conn


SAMPLE_NPCS = [
    {"key": "brunn_zelaznoreki", "name": "Brunn Żelaznoreki", "role": "Kowal protagonist"},
    {"key": "toma_czeladnik",    "name": "Toma Czeladnik",    "role": "Pomocnik kowala"},
]


# ─── Test główny: NPC rows tworzone po generate-plan ─────────────────────────

def test_auto_create_forge_npcs_inserts_rows():
    """_auto_create_forge_npcs() must insert a row per NPC into npcs table with review_status='pending'."""
    conn = _make_db()
    created = _auto_create_forge_npcs(conn, template_id=1, npcs=SAMPLE_NPCS)

    assert len(created) == 2, "Should return 2 created entries"

    rows = conn.execute("SELECT key, label, review_status, is_active FROM npcs ORDER BY key").fetchall()
    keys = [r["key"] for r in rows]
    assert "brunn_zelaznoreki" in keys
    assert "toma_czeladnik" in keys

    for row in rows:
        assert row["review_status"] == "pending", f"{row['key']} must have review_status=pending"
        assert row["is_active"] == 1, f"{row['key']} must be is_active=1"


# ─── Test idempotencji: drugie wywołanie nie duplikuje NPC ───────────────────

def test_auto_create_forge_npcs_idempotent():
    """Calling _auto_create_forge_npcs() twice must not duplicate NPC rows."""
    conn = _make_db()
    _auto_create_forge_npcs(conn, template_id=1, npcs=SAMPLE_NPCS)
    _auto_create_forge_npcs(conn, template_id=1, npcs=SAMPLE_NPCS)

    count = conn.execute("SELECT COUNT(*) FROM npcs").fetchone()[0]
    assert count == 2, f"Expected 2 npcs, got {count} (idempotent check)"


# ─── Test walidacji: validate_template_publish przechodzi po auto-create ─────

def test_validate_publish_passes_after_auto_create_npcs():
    """After _auto_create_forge_npcs(), validate_template_publish must return ok=True (no missing NPCs)."""
    conn = _make_db()
    npc_keys = [n["key"] for n in SAMPLE_NPCS]
    plan = {"acts": [], "endings": [], "key_npcs": SAMPLE_NPCS, "key_enemies": []}

    conn.execute(
        "INSERT INTO campaign_templates (id, required_npc_keys, required_beats, gm_plan_json) VALUES (?,?,?,?)",
        (1, json.dumps(npc_keys), "[]", json.dumps(plan)),
    )
    conn.commit()

    # Before auto-create: should fail
    result_before = validate_template_publish(1, conn)
    assert result_before["missing_npcs"] == npc_keys, "Before auto-create all NPC keys must be missing"

    _auto_create_forge_npcs(conn, template_id=1, npcs=SAMPLE_NPCS)
    conn.commit()

    # After auto-create: must pass
    result_after = validate_template_publish(1, conn)
    assert result_after["ok"] is True, f"After auto-create publish should pass; missing: {result_after['missing_npcs']}"
    assert result_after["missing_npcs"] == [], "No NPCs should be missing after auto-create"


# ─── Backward compat: empty list → no crash ──────────────────────────────────

def test_auto_create_forge_npcs_empty_list():
    """_auto_create_forge_npcs() with empty list must return [] without error."""
    conn = _make_db()
    result = _auto_create_forge_npcs(conn, template_id=1, npcs=[])
    assert result == []
    count = conn.execute("SELECT COUNT(*) FROM npcs").fetchone()[0]
    assert count == 0
