"""TDD: Issue #422 (E7) — campaign_templates required_npc_keys / required_beats / player_visible."""
import sys, os, json, sqlite3

sys.path.insert(0, "/app")

import pytest

DB_PATH = os.environ.get("DB_PATH", "/data/ai_gm.db")
_NEW_COLS = ("required_npc_keys", "required_beats", "player_visible")


def _migrate():
    from app.migrations_admin import run_admin_migrations
    run_admin_migrations()


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_migration_adds_columns():
    """campaign_templates must gain the 3 new columns after migration."""
    _migrate()
    conn = sqlite3.connect(DB_PATH)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(campaign_templates)").fetchall()}
    finally:
        conn.close()
    for c in _NEW_COLS:
        assert c in cols, f"column {c} missing after migration: {sorted(cols)}"


def test_template_to_dict_includes_new_fields():
    """_template_to_dict must surface the new fields (lists parsed, player_visible bool-ish)."""
    _migrate()
    from app.routers.adventure_forge import _template_to_dict
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "INSERT INTO campaign_templates (title, required_npc_keys, required_beats, player_visible) "
            "VALUES ('E7 test', ?, ?, 0)",
            (json.dumps(["npc_alik"]), json.dumps(["beat_intro"])),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM campaign_templates WHERE id = ?", (cur.lastrowid,)).fetchone()
        d = _template_to_dict(row)
        conn.execute("DELETE FROM campaign_templates WHERE id = ?", (cur.lastrowid,))
        conn.commit()
    finally:
        conn.close()
    assert d["required_npc_keys"] == ["npc_alik"], f"required_npc_keys: {d.get('required_npc_keys')}"
    assert d["required_beats"] == ["beat_intro"], f"required_beats: {d.get('required_beats')}"
    assert d["player_visible"] == 0, f"player_visible: {d.get('player_visible')}"


def test_create_and_patch_template_roundtrip():
    """CreateTemplateReq/PatchTemplateReq must accept + persist the new fields."""
    _migrate()
    from app.routers.adventure_forge import CreateTemplateReq, PatchTemplateReq
    # Models must declare the new fields.
    c = CreateTemplateReq(title="X", required_npc_keys=["a"], required_beats=["b"], player_visible=False)
    assert c.required_npc_keys == ["a"]
    assert c.player_visible is False
    p = PatchTemplateReq(player_visible=True, required_npc_keys=["z"])
    assert p.player_visible is True
    assert p.required_beats is None  # optional, not provided


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_template_to_dict_keeps_core_fields():
    """Existing template dict fields must remain (no regression)."""
    _migrate()
    from app.routers.adventure_forge import _template_to_dict
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute("INSERT INTO campaign_templates (title) VALUES ('core test')")
        conn.commit()
        row = conn.execute("SELECT * FROM campaign_templates WHERE id = ?", (cur.lastrowid,)).fetchone()
        d = _template_to_dict(row)
        conn.execute("DELETE FROM campaign_templates WHERE id = ?", (cur.lastrowid,))
        conn.commit()
    finally:
        conn.close()
    for k in ("id", "title", "difficulty_rating", "status", "hook_ids"):
        assert k in d, f"core field {k} lost: {list(d.keys())}"
