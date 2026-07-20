"""SG-6b (#1481) — bramki zasięgu treści krainowej.

Bez nich zawartość Siwych Grań wyciekłaby na całą mapę:
  * `game_config_encounters.region_tag` istniał od PT-D4a, ale ŻADNE zapytanie go nie
    czytało — scena „lawina na grani" trafiłaby na Kresy,
  * wróg regionalny szedł do puli kompozytora wszędzie tam, gdzie zgadzał się teren,
  * autorska pula hexa (`world_hexes.encounter_pool`) była filtrem MIĘKKIM, więc
    unikat w rodzaju zamarzniętych pielgrzymów rozlewał się po całym biomie.
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import encounter_catalog_service as cat
from app.services import encounter_service as enc


# ── Katalog scen ─────────────────────────────────────────────────────────────

def _cat_conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    cat.ensure_catalog_schema(c)
    payload = '{"enemies": [{"enemy_key": "wolf", "name": "wilk", "count": 1}]}'
    rows = [
        ("globalna_scena", None),
        ("scena_gran", "siwe_granie"),
        ("scena_kresy", "kresy"),
    ]
    for key, region in rows:
        c.execute(
            "INSERT INTO game_config_encounters (key, kind, biome, level_min, level_max, "
            "weight, region_tag, payload_json, is_active) "
            "VALUES (?, 'combat', 'grania', 1, 9, 100, ?, ?, 1)",
            (key, region, payload),
        )
    c.commit()
    return c


def _draw_keys(c, region, n=60):
    return {
        (cat.draw_combat(c, "grania", 3, region=region) or {}).get("key")
        for _ in range(n)
    }


def test_region_scene_never_leaks_to_another_region():
    c = _cat_conn()
    keys = _draw_keys(c, "kresy")
    assert "scena_gran" not in keys, keys
    assert "globalna_scena" in keys


def test_region_scene_is_drawn_in_its_own_region():
    c = _cat_conn()
    assert "scena_gran" in _draw_keys(c, "siwe_granie")


def test_unknown_region_gets_only_global_scenes():
    """Treść krainowa jest opt-in — brak regionu nie może jej wpuścić."""
    c = _cat_conn()
    assert _draw_keys(c, None) == {"globalna_scena"}


# ── Pula wrogów kompozytora ──────────────────────────────────────────────────

def _enemy_conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute(
        "CREATE TABLE game_config_enemies (key TEXT PRIMARY KEY, label TEXT, hp_base INT, "
        "ac_base INT, attack_bonus INT, damage_die TEXT, damage_bonus INT, "
        "attacks_per_turn INT, tier TEXT, min_level INT, max_level INT, terrain_tags TEXT, "
        "world_scope TEXT, review_status TEXT, is_active INT, region_tag TEXT)"
    )
    for key, scope, region in (
        ("wilk_globalny", "global", None),
        ("sniezny_wilk", "global", "siwe_granie"),
        ("zamarzniety_pielgrzym", "pool", "siwe_granie"),
    ):
        c.execute(
            "INSERT INTO game_config_enemies VALUES (?,?,12,12,3,'1d6',0,1,'standard',"
            "1,5,'mountain',?,'permanent',1,?)",
            (key, key, scope, region),
        )
    c.commit()
    return c


def _pool_keys(c, **kw):
    return {d["key"] for d in enc.eligible_enemy_pool(c, level=3, hex_type="grania", **kw)}


def test_region_enemy_stays_in_its_region():
    c = _enemy_conn()
    assert _pool_keys(c, region="kresy") == {"wilk_globalny"}


def test_region_enemy_appears_at_home():
    c = _enemy_conn()
    assert _pool_keys(c, region="siwe_granie") == {"wilk_globalny", "sniezny_wilk"}


def test_unknown_region_gets_only_global_enemies():
    c = _enemy_conn()
    assert _pool_keys(c) == {"wilk_globalny"}


def test_pool_only_enemy_needs_an_authored_hex():
    """world_scope='pool' — pielgrzym tylko tam, gdzie autor wpisał go do puli hexa."""
    c = _enemy_conn()
    assert "zamarzniety_pielgrzym" not in _pool_keys(c, region="siwe_granie")
    keys = _pool_keys(c, region="siwe_granie", pool_keys={"zamarzniety_pielgrzym"})
    assert keys == {"zamarzniety_pielgrzym"}, keys


def test_pool_only_enemy_ignores_authored_hex_of_another_region():
    c = _enemy_conn()
    keys = _pool_keys(c, region="kresy", pool_keys={"zamarzniety_pielgrzym"})
    assert "zamarzniety_pielgrzym" not in keys


def test_legacy_db_without_region_column_still_builds_a_pool():
    """Baza sprzed migracji region_tag — kompozytor nie może paść."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute(
        "CREATE TABLE game_config_enemies (key TEXT PRIMARY KEY, label TEXT, hp_base INT, "
        "ac_base INT, attack_bonus INT, damage_die TEXT, damage_bonus INT, "
        "attacks_per_turn INT, tier TEXT, min_level INT, max_level INT, terrain_tags TEXT, "
        "world_scope TEXT, review_status TEXT, is_active INT)"
    )
    c.execute(
        "INSERT INTO game_config_enemies VALUES ('wilk','Wilk',12,12,3,'1d6',0,1,"
        "'standard',1,5,'mountain','global','permanent',1)"
    )
    c.commit()
    assert _pool_keys(c, region="siwe_granie") == {"wilk"}
