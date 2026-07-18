"""TDD: Issue #981 — Kresy casting (NPCs + horror-place enemies) surfaces to the narrator.

Verifies the live engine read-path: world_service.build_available_content_index()
injects assigned NPCs ("Nearby NPCs") and enemies ("Possible threats") into the
LLM "[AVAILABLE CONTENT]" block from location_npc_assignments /
location_enemy_assignments. The seed (scripts/seed_kresy_obsada.apply) is what
wires Kresy canon places to their characters/threats.
"""
from _fixtures_schema import table_sql
import importlib.util
import os
import sqlite3

import pytest

from app.services.world_service import build_available_content_index

# Load the seed module by path (scripts/ is not a package on PYTHONPATH).
_SEED_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "seed_kresy_obsada.py")
if not os.path.exists(_SEED_PATH):  # container layout: /app/scripts/...
    _SEED_PATH = "/app/scripts/seed_kresy_obsada.py"
_spec = importlib.util.spec_from_file_location("seed_kresy_obsada", _SEED_PATH)
seed = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seed)


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE npcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL, label TEXT, npc_type TEXT DEFAULT 'neutral',
            description TEXT, personality_json TEXT DEFAULT '{}',
            personality_prompt TEXT, is_shop INTEGER DEFAULT 0,
            shop_inventory_json TEXT DEFAULT '[]', is_active INTEGER DEFAULT 1,
            review_status TEXT DEFAULT 'permanent', keyword_triggers TEXT DEFAULT '[]'
        );
        """ + table_sql("game_config_enemies") + """
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL, label TEXT, biome TEXT,
            location_subtype TEXT, tier INTEGER DEFAULT 1, canonical INTEGER DEFAULT 0,
            usage_count INTEGER DEFAULT 0, parent_id INTEGER,
            npc_keys TEXT DEFAULT '[]', enemy_keys TEXT DEFAULT '[]',
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE location_npc_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_key TEXT NOT NULL, npc_key TEXT NOT NULL,
            assignment_type TEXT DEFAULT 'resident', notes TEXT,
            is_active INTEGER DEFAULT 1, UNIQUE(location_key, npc_key)
        );
        CREATE TABLE location_enemy_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_key TEXT NOT NULL, enemy_key TEXT NOT NULL,
            spawn_chance REAL DEFAULT 1.0, max_count INTEGER DEFAULT 3,
            notes TEXT, is_active INTEGER DEFAULT 1, UNIQUE(location_key, enemy_key)
        );
        """
    )
    # Canon locations referenced by the seed (subset).
    for k, label, biome in [
        ("bor_zmarlych", "Bór Zmarłych", "forest"),
        ("zgliszcza", "Zgliszcza", "rural"),
        ("bagienna_knieja", "Bagienna Knieja", "swamp"),
        ("brzezino_tartak", "Brzezino: Tartak", "forest"),
        ("most_komora_celna", "Most: Komora Celna", "rural"),
        ("strazyn_lazaret", "Strażyn: Lazaret", "mountain"),
    ]:
        conn.execute("INSERT INTO game_locations (key, label, biome) VALUES (?,?,?)", (k, label, biome))
    # Pre-existing canon NPCs the seed *reuses* (must already exist).
    for k, label in [
        ("medyk_strazyn", "Felczer Ryszard"), ("celnik_pius", "Pius, celnik"),
    ]:
        conn.execute("INSERT INTO npcs (key, label, npc_type) VALUES (?,?,'neutral')", (k, label))
    # Enemies the seed assigns (must already exist).
    for k, label, tier in [
        ("zombie", "Zombie", "weak"), ("skeleton", "Szkielet", "standard"),
        ("ghoul", "Ghul", "standard"), ("ghost", "Duch", "standard"),
        ("wraith", "Widmo", "standard"), ("cultist", "Kultista", "weak"),
        ("giant_spider", "Olbrzymi Pająk", "standard"), ("slime", "Szlam", "weak"),
        ("dark_mage", "Mroczny Czarodziej", "standard"),
    ]:
        conn.execute("INSERT INTO game_config_enemies (key, label, tier) VALUES (?,?,?)", (k, label, tier))
    conn.commit()
    yield conn
    conn.close()


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_bor_zmarlych_surfaces_npc_and_threats_after_seed(db):
    """After seeding, the narrator context for Bór Zmarłych lists the NPC-hak
    (Wiedźma Jaga) and undead threats (zombie/skeleton)."""
    # Baseline (RED guard): nothing wired yet.
    before = build_available_content_index(db, "bor_zmarlych")
    assert "wiedzma_jaga" not in before
    assert "Possible threats" not in before

    seed.apply(db)

    after = build_available_content_index(db, "bor_zmarlych")
    assert "Nearby NPCs" in after
    assert "wiedzma_jaga" in after          # NPC-hak placed
    assert "Possible threats" in after
    assert "zombie" in after and "skeleton" in after  # Rdzeń-leak undead


def test_sub_location_pin_reuses_existing_npc(db):
    """A sub-location pin surfaces an existing hub NPC (no duplicate created)."""
    seed.apply(db)
    ctx = build_available_content_index(db, "most_komora_celna")
    assert "celnik_pius" in ctx
    # Pius was NOT newly created — still exactly one row.
    assert db.execute("SELECT COUNT(*) FROM npcs WHERE key='celnik_pius'").fetchone()[0] == 1


def test_json_columns_resynced(db):
    """game_locations.npc_keys / enemy_keys JSON re-synced from assignment tables."""
    seed.apply(db)
    row = db.execute("SELECT npc_keys, enemy_keys FROM game_locations WHERE key='bor_zmarlych'").fetchone()
    assert "wiedzma_jaga" in row["npc_keys"]
    assert "zombie" in row["enemy_keys"]


# ─── Idempotency / backward compatibility ────────────────────────────────────

def test_apply_is_idempotent(db):
    """Re-running the seed adds nothing the second time (INSERT OR IGNORE)."""
    first = seed.apply(db)
    assert first["npcs_created"] > 0 and first["npc_assignments"] > 0
    second = seed.apply(db)
    assert second == {"npcs_created": 0, "npc_assignments": 0, "enemy_assignments": 0}


def test_preexisting_assignment_preserved(db):
    """A manual assignment present before the seed is not removed by it."""
    db.execute(
        "INSERT INTO location_npc_assignments (location_key, npc_key) VALUES ('bor_zmarlych','medyk_strazyn')"
    )
    db.commit()
    seed.apply(db)
    ctx = build_available_content_index(db, "bor_zmarlych")
    assert "medyk_strazyn" in ctx and "wiedzma_jaga" in ctx
