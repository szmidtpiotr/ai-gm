"""#1327 BL-A1 — enemy metadata: terrain_tags, level bands, world_scope.

Targeted pytest (never the full suite). Verifies the idempotent backfill +
data-pass in migrations_admin._ensure_enemy_terrain_scope_bands against a
minimal in-memory-style DB copy.
"""
import sqlite3

import app.migrations_admin as m


def _make_db(path):
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE game_config_enemies (
            key TEXT PRIMARY KEY,
            tier TEXT NOT NULL DEFAULT 'standard',
            hp_base INTEGER NOT NULL DEFAULT 10,
            min_level INTEGER NOT NULL DEFAULT 1,
            created_by TEXT,
            template_id INTEGER,
            terrain_tags TEXT,
            max_level INTEGER,
            world_scope TEXT NOT NULL DEFAULT 'global'
        )
        """
    )
    rows = [
        # key, tier, hp, created_by, template_id
        ("wolf", "standard", 10, None, None),          # global, 1-2
        ("orc", "standard", 18, None, None),           # global, 3-5 (hp>=16)
        ("kobold", "weak", 6, None, None),             # global, 1-2
        ("troll", "elite", 35, None, None),            # global, 6-9
        ("lich", "boss", 90, None, None),              # global, 10+ (max NULL)
        ("forge_boss", "boss", 60, "forge", None),     # template (created_by)
        ("tmpl_enemy", "standard", 20, None, 42),      # template (template_id)
        ("plan_enemy", "standard", 14, "llm_plan", None),  # campaign
    ]
    for key, tier, hp, cb, tid in rows:
        conn.execute(
            "INSERT INTO game_config_enemies(key,tier,hp_base,min_level,created_by,template_id) "
            "VALUES (?,?,?,?,?,?)",
            (key, tier, hp, 1 if tier in ("weak", "standard") else (6 if tier == "elite" else 10), cb, tid),
        )
    conn.commit()
    return conn


def test_world_scope_backfill(tmp_path):
    p = str(tmp_path / "t.db")
    conn = _make_db(p)
    m._ensure_enemy_terrain_scope_bands(conn)
    scope = dict(
        conn.execute("SELECT key, world_scope FROM game_config_enemies").fetchall()
    )
    assert scope["wolf"] == "global"
    assert scope["forge_boss"] == "template"      # created_by='forge'
    assert scope["tmpl_enemy"] == "template"      # template_id set
    assert scope["plan_enemy"] == "campaign"      # created_by='llm_plan'


def test_level_bands_by_tier(tmp_path):
    p = str(tmp_path / "t.db")
    conn = _make_db(p)
    m._ensure_enemy_terrain_scope_bands(conn)
    band = {
        k: (mn, mx)
        for k, mn, mx in conn.execute(
            "SELECT key, min_level, max_level FROM game_config_enemies"
        ).fetchall()
    }
    assert band["kobold"] == (1, 2)   # weak
    assert band["wolf"] == (1, 2)     # standard hp<16
    assert band["orc"] == (3, 5)      # standard hp>=16
    assert band["troll"] == (6, 9)    # elite
    assert band["lich"] == (10, None)  # boss = 10+ open-ended


def test_every_global_has_terrain_and_band(tmp_path):
    p = str(tmp_path / "t.db")
    conn = _make_db(p)
    m._ensure_enemy_terrain_scope_bands(conn)
    bad = conn.execute(
        "SELECT count(*) FROM game_config_enemies "
        "WHERE world_scope='global' AND (terrain_tags IS NULL OR terrain_tags='' OR min_level IS NULL)"
    ).fetchone()[0]
    assert bad == 0
    # template/campaign enemies are NOT terrain-tagged (selected via templates)
    tmpl_terrain = conn.execute(
        "SELECT terrain_tags FROM game_config_enemies WHERE key='forge_boss'"
    ).fetchone()[0]
    assert tmpl_terrain is None


def test_terrain_values_within_dictionary(tmp_path):
    p = str(tmp_path / "t.db")
    conn = _make_db(p)
    m._ensure_enemy_terrain_scope_bands(conn)
    allowed = {
        "forest", "road", "mountain", "swamp", "city", "dungeon", "plains",
        "ruins", "cave", "river", "hills", "castle", "wilderness",
    }
    for (tags,) in conn.execute(
        "SELECT terrain_tags FROM game_config_enemies WHERE terrain_tags IS NOT NULL"
    ).fetchall():
        for t in tags.split(","):
            assert t in allowed, f"terrain {t!r} not in dictionary"


def test_idempotent_and_preserves_admin_edits(tmp_path):
    p = str(tmp_path / "t.db")
    conn = _make_db(p)
    m._ensure_enemy_terrain_scope_bands(conn)
    # simulate an admin edit in Świat → wrogowie
    conn.execute(
        "UPDATE game_config_enemies SET terrain_tags='castle', min_level=4, max_level=7 WHERE key='wolf'"
    )
    conn.commit()
    # re-run (deploy replay) must NOT clobber the edit
    m._ensure_enemy_terrain_scope_bands(conn)
    row = conn.execute(
        "SELECT terrain_tags, min_level, max_level FROM game_config_enemies WHERE key='wolf'"
    ).fetchone()
    assert row == ("castle", 4, 7)
