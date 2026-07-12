"""BL-A3 (#1329) — pamięć spotkań anti-repeat.

Sygnatury ostatnich spotkań w session_flags, kara wagi ×0.25 dla powtórek,
twarda blokada sygnatury identycznej z ostatnim spotkaniem — w OBU torach
(kompozycja `encounter_composer` + katalog `draw_combat`).
"""
import json
import random
import sqlite3

import pytest

from app.services import encounter_service as es
from app.services import encounter_catalog_service as ecs


# ── Schemat minimalny ─────────────────────────────────────────────────────────

def _enemy_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE game_config_enemies (
            key TEXT PRIMARY KEY, label TEXT, hp_base INTEGER, ac_base INTEGER,
            attack_bonus INTEGER, damage_die TEXT, damage_bonus INTEGER,
            attacks_per_turn INTEGER, tier TEXT, min_level INTEGER, max_level INTEGER,
            terrain_tags TEXT, world_scope TEXT, review_status TEXT, is_active INTEGER
        )"""
    )
    rows = [
        ("wilk", "Wilk", 14, 12, 2, "1d6", 0, 1, "standard", None, None, None, "global", "permanent", 1),
        ("goblin", "Goblin", 10, 11, 1, "1d4", 0, 1, "weak", None, None, None, "global", "permanent", 1),
        ("ogr", "Ogr", 40, 13, 4, "1d10", 2, 1, "elite", None, None, None, "global", "permanent", 1),
    ]
    conn.executemany(
        "INSERT INTO game_config_enemies VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows
    )
    conn.commit()
    return conn


def _catalog_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ecs.ensure_catalog_schema(conn)
    for key, enemies in [
        ("c_wilki", [{"enemy_key": "wilk", "count": 2}]),
        ("c_gobliny", [{"enemy_key": "goblin", "count": 3}]),
        ("c_ogr", [{"enemy_key": "ogr", "count": 1}]),
    ]:
        ecs.insert_encounter(
            conn, key=key, kind="combat", biome="forest", level_min=1, level_max=5,
            weight=100.0, payload={"enemies": enemies, "title": key},
        )
    return conn


# ── Sygnatury i pamięć ────────────────────────────────────────────────────────

def test_signature_sorted_unique():
    assert es.encounter_signature([{"enemy_key": "b"}, {"enemy_key": "a"}, {"enemy_key": "b"}]) == "a+b"
    assert es.encounter_signature([]) == ""
    # fallback do name gdy brak enemy_key
    assert es.encounter_signature([{"name": "Wilk"}]) == "Wilk"


def test_record_trims_to_depth_and_survives_json():
    conn = _enemy_conn()
    sf = {}
    for i in range(8):
        es.record_encounter_signature(conn, sf, [{"enemy_key": f"e{i}"}])
    # głębia domyślna 5, index 0 = najnowsze
    assert sf["recent_encounters"] == ["e7", "e6", "e5", "e4", "e3"]
    # round-trip przez session_flags nie gubi ani nie miesza kampanii
    sf2 = json.loads(json.dumps(sf))
    assert es.recent_signatures(sf2) == sf["recent_encounters"]


def test_record_ignores_empty_signature():
    conn = _enemy_conn()
    sf = {"recent_encounters": ["wilk"]}
    es.record_encounter_signature(conn, sf, [])
    assert sf["recent_encounters"] == ["wilk"]


# ── Tor kompozycji: brak dwóch identycznych z rzędu ──────────────────────────

def test_composer_no_two_identical_in_a_row():
    conn = _enemy_conn()
    rng = random.Random(1234)
    sf = {}
    sigs = []
    for _ in range(10):
        recent = es.recent_signatures(sf)
        composed = es.encounter_composer(conn, level=2, hex_type=None, rng=rng, recent_sigs=recent)
        assert composed is not None
        sig = es.encounter_signature(composed["enemies"])
        sigs.append(sig)
        es.record_encounter_signature(conn, sf, composed["enemies"])
        # symuluj zapis/odczyt session_flags
        sf = json.loads(json.dumps(sf))
    # pula ma >1 możliwą sygnaturę → żadne dwie z rzędu identyczne
    for a, b in zip(sigs, sigs[1:]):
        assert a != b, f"powtórka z rzędu: {sigs}"


def test_composer_single_enemy_pool_allows_repeat():
    """Brak alternatyw (jeden wróg) → blokada ustępuje, spotkanie nadal powstaje."""
    conn = _enemy_conn()
    conn.execute("DELETE FROM game_config_enemies WHERE key != 'wilk'")
    conn.commit()
    rng = random.Random(7)
    sf = {}
    for _ in range(4):
        recent = es.recent_signatures(sf)
        composed = es.encounter_composer(conn, level=1, hex_type=None, rng=rng, recent_sigs=recent)
        assert composed is not None  # nie zwraca None mimo powtórki
        es.record_encounter_signature(conn, sf, composed["enemies"])


# ── Tor katalogu: brak dwóch identycznych z rzędu ────────────────────────────

def test_catalog_draw_no_two_identical_in_a_row():
    conn = _catalog_conn()
    rng = random.Random(99)
    sf = {}
    sigs = []
    for _ in range(10):
        recent = es.recent_signatures(sf)
        row = ecs.draw_combat(conn, "forest", 2, rng=rng, recent_sigs=recent)
        assert row is not None
        enemies = row["payload"].get("enemies") or []
        sig = es.encounter_signature(enemies)
        sigs.append(sig)
        es.record_encounter_signature(conn, sf, enemies)
        sf = json.loads(json.dumps(sf))
    for a, b in zip(sigs, sigs[1:]):
        assert a != b, f"powtórka z rzędu (katalog): {sigs}"


def test_catalog_draw_single_row_allows_repeat():
    conn = _catalog_conn()
    conn.execute("DELETE FROM game_config_encounters WHERE key != 'c_wilki'")
    conn.commit()
    rng = random.Random(3)
    row = ecs.draw_combat(conn, "forest", 2, rng=rng, recent_sigs=["wilk"])
    assert row is not None  # jedyna opcja mimo że == ostatnia sygnatura


def test_catalog_draw_no_recent_backward_compat():
    conn = _catalog_conn()
    row = ecs.draw_combat(conn, "forest", 2, rng=random.Random(1))
    assert row is not None
