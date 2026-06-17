"""TDD L20a #692 — persystencja image_url/image_url_raw/image_gen_prompt na wrogach i NPC."""
from __future__ import annotations

import sqlite3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─── helpers ─────────────────────────────────────────────────────────────────

def _make_enemy_db() -> sqlite3.Connection:
    """In-memory DB z minimalnym schematem game_config_enemies (bez kolumn portretów)."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE game_config_enemies (
            key TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            hp_base INTEGER NOT NULL DEFAULT 10,
            ac_base INTEGER NOT NULL DEFAULT 10,
            attack_bonus INTEGER NOT NULL DEFAULT 0,
            dex_modifier INTEGER NOT NULL DEFAULT 0,
            damage_die TEXT NOT NULL DEFAULT '1d6',
            tier TEXT NOT NULL DEFAULT 'standard',
            attacks_per_turn INTEGER NOT NULL DEFAULT 1,
            damage_bonus INTEGER NOT NULL DEFAULT 0,
            damage_type TEXT NOT NULL DEFAULT 'physical',
            xp_award INTEGER NOT NULL DEFAULT 0,
            conditions_immune TEXT NOT NULL DEFAULT '[]',
            skills_json TEXT NOT NULL DEFAULT '{}',
            stats_json TEXT NOT NULL DEFAULT '{}',
            loot_table_key TEXT,
            drop_chance REAL DEFAULT 1.0,
            note TEXT,
            description TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            loot_tier TEXT,
            locked_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        INSERT INTO game_config_enemies (key, label, hp_base, ac_base, attack_bonus, damage_die)
        VALUES ('test_enemy', 'Test Enemy', 10, 10, 1, '1d6')
    """)
    conn.commit()
    return conn


def _make_npc_db() -> sqlite3.Connection:
    """In-memory DB z minimalnym schematem npcs (bez kolumn portretów)."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE npcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL,
            npc_type TEXT NOT NULL DEFAULT 'neutral',
            description TEXT,
            personality_json TEXT DEFAULT '{}',
            is_shop INTEGER DEFAULT 0,
            shop_inventory_json TEXT DEFAULT '[]',
            is_active INTEGER DEFAULT 1,
            is_dead INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        INSERT INTO npcs (key, label) VALUES ('test_npc', 'Test NPC')
    """)
    conn.commit()
    return conn


# ─── FAZA 1: RED — testy które MUSZĄ failować przed implementacją ───────────

def test_enemy_has_image_url_column():
    """game_config_enemies powinna mieć kolumnę image_url po migracji."""
    from app.migrations_admin import _ensure_portrait_columns
    conn = _make_enemy_db()
    _ensure_portrait_columns(conn)

    cols = {row[1] for row in conn.execute("PRAGMA table_info(game_config_enemies)")}
    assert "image_url" in cols, "Brak kolumny image_url w game_config_enemies"
    assert "image_url_raw" in cols, "Brak kolumny image_url_raw w game_config_enemies"
    assert "image_gen_prompt" in cols, "Brak kolumny image_gen_prompt w game_config_enemies"
    conn.close()


def test_npc_has_image_url_column():
    """npcs powinna mieć kolumnę image_url po migracji."""
    from app.migrations_admin import _ensure_portrait_columns
    conn = _make_npc_db()
    _ensure_portrait_columns(conn)

    cols = {row[1] for row in conn.execute("PRAGMA table_info(npcs)")}
    assert "image_url" in cols, "Brak kolumny image_url w npcs"
    assert "image_url_raw" in cols, "Brak kolumny image_url_raw w npcs"
    assert "image_gen_prompt" in cols, "Brak kolumny image_gen_prompt w npcs"
    conn.close()


def test_ensure_portrait_columns_idempotent():
    """Podwójne wywołanie _ensure_portrait_columns nie rzuca wyjątku."""
    from app.migrations_admin import _ensure_portrait_columns
    conn = _make_enemy_db()
    _ensure_portrait_columns(conn)
    _ensure_portrait_columns(conn)  # drugie wywołanie — musi być ciche
    conn.close()


def test_update_enemy_saves_image_url():
    """update_enemy() powinno zapisywać image_url i zwracać je w dict."""
    from app.services.admin_config import update_enemy

    # musi zwrócić image_url po zapisie
    result = update_enemy(
        "skeleton",
        label=None,
        hp_base=None,
        ac_base=None,
        attack_bonus=None,
        damage_die=None,
        description=None,
        is_active=None,
        force=False,
        image_url="/static/portraits/skeleton.png",
        image_url_raw="/static/portraits/skeleton_raw.png",
        image_gen_prompt="dark fantasy skeleton warrior portrait",
    )
    assert result.get("image_url") == "/static/portraits/skeleton.png", (
        f"update_enemy nie zwróciło image_url. Zwróciło: {result.get('image_url')}"
    )


def test_list_enemies_includes_image_url():
    """list_enemies() powinno zawierać pole image_url w każdym rekordzie."""
    from app.services.admin_config import list_enemies

    enemies = list_enemies()
    assert len(enemies) > 0, "Brak wrogów w DEV DB"
    first = enemies[0]
    assert "image_url" in first, (
        f"list_enemies() nie zwraca image_url. Klucze: {list(first.keys())}"
    )


def test_patch_npc_saves_image_url():
    """PATCH /api/npcs/{id} powinno zapisywać image_url na kolumnie npcs.image_url."""
    import fastapi.testclient
    from app.api.npcs import router as npcs_router
    import fastapi

    app = fastapi.FastAPI()
    app.include_router(npcs_router, prefix="/api")

    client = fastapi.testclient.TestClient(app)

    # Pobierz pierwsze NPC
    resp = client.get("/api/npcs")
    assert resp.status_code == 200
    npcs = resp.json().get("items", [])
    if not npcs:
        # Brak NPC — test nie może się odbyć, ale kolumna powinna istnieć
        import pytest
        pytest.skip("Brak NPC w DB — pomiń test end-to-end")

    npc_id = npcs[0]["id"]

    # PATCH image_url
    resp2 = client.patch(f"/api/npcs/{npc_id}", json={"image_url": "/static/portraits/npc_test.png"})
    assert resp2.status_code == 200, f"PATCH NPC zwróciło {resp2.status_code}: {resp2.text}"

    # Sprawdź czy zapisane
    resp3 = client.get(f"/api/npcs/{npc_id}")
    assert resp3.status_code == 200
    npc = resp3.json()
    assert npc.get("image_url") == "/static/portraits/npc_test.png", (
        f"NPC image_url nie zapisało się. Wartość: {npc.get('image_url')}"
    )
