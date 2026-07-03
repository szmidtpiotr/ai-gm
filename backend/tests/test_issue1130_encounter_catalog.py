"""TDD: Issue #1130 (PT-D4a) — kanoniczny katalog encounterów w bazie.

Tabela `game_config_encounters` (combat + social, kolumna `kind`), seed z obecnego
hardcode (GENERIC_ENCOUNTERS + _EVENT_DEFS/_SUBTYPE_EVENTS), serwis losujący wg wag
z fallbackiem (pusty katalog → None) i walidacją FK (enemy_key/skill) na zapisie.

Testy używają in-memory sqlite — nie dotykają /data/ai_gm.db (deterministyczne).
"""
import random
import sqlite3

import pytest

from app.services import encounter_catalog_service as cat


# ── helpers ──────────────────────────────────────────────────────────────────

def _mem_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def _seed_fk_refs(conn: sqlite3.Connection) -> None:
    """Minimalne tabele referencyjne + kilka poprawnych kluczy dla walidacji FK."""
    conn.execute("CREATE TABLE game_config_enemies (key TEXT PRIMARY KEY, label TEXT)")
    conn.execute("CREATE TABLE game_config_skills (key TEXT PRIMARY KEY, label TEXT)")
    for k in ("wolf", "bandit", "goblin", "skeleton", "thug"):
        conn.execute("INSERT INTO game_config_enemies (key, label) VALUES (?, ?)", (k, k))
    for k in ("awareness", "persuasion", "insight", "gossip"):
        conn.execute("INSERT INTO game_config_skills (key, label) VALUES (?, ?)", (k, k))
    conn.commit()


# ── Test główny: schemat ──────────────────────────────────────────────────────

def test_ensure_schema_creates_table_with_expected_columns():
    """Migracja tworzy game_config_encounters wg schematu z epiku."""
    conn = _mem_conn()
    cat.ensure_catalog_schema(conn)
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(game_config_encounters)")}
    expected = {
        "key", "kind", "biome", "subtype", "level_min", "level_max", "weight",
        "trigger_types", "region_tag", "faction_tag", "payload_json",
        "is_active", "source", "quality_rating", "times_used",
    }
    assert expected <= cols, f"brakuje kolumn: {expected - cols}"


def test_ensure_schema_idempotent():
    """Ponowne wywołanie ensure_catalog_schema nie rzuca."""
    conn = _mem_conn()
    cat.ensure_catalog_schema(conn)
    cat.ensure_catalog_schema(conn)  # nie może rzucić


# ── Test główny: seed ─────────────────────────────────────────────────────────

def test_seed_populates_combat_and_social():
    """Seed wgrywa obecne encountery combat (GENERIC) i social (_EVENT_DEFS)."""
    conn = _mem_conn()
    cat.ensure_catalog_schema(conn)
    cat.seed_catalog(conn)

    combat = conn.execute("SELECT COUNT(*) n FROM game_config_encounters WHERE kind='combat'").fetchone()["n"]
    social = conn.execute("SELECT COUNT(*) n FROM game_config_encounters WHERE kind='social'").fetchone()["n"]
    assert combat > 0, "brak wierszy combat"
    assert social > 0, "brak wierszy social"

    # konkretne encountery z hardcode obecne
    keys = {row["key"] for row in conn.execute("SELECT key FROM game_config_encounters")}
    assert any("wolves_forest" in k for k in keys), "brak wolves_forest (combat)"
    assert any("pickpocket" in k for k in keys), "brak pickpocket (social)"

    # marker źródła
    src = {row["source"] for row in conn.execute("SELECT DISTINCT source FROM game_config_encounters")}
    assert "seed" in src


def test_seed_idempotent():
    """Dwukrotny seed → ta sama liczba wierszy (idempotencja)."""
    conn = _mem_conn()
    cat.ensure_catalog_schema(conn)
    cat.seed_catalog(conn)
    n1 = conn.execute("SELECT COUNT(*) n FROM game_config_encounters").fetchone()["n"]
    cat.seed_catalog(conn)
    n2 = conn.execute("SELECT COUNT(*) n FROM game_config_encounters").fetchone()["n"]
    assert n1 == n2, f"seed nieidempotentny: {n1} → {n2}"


def test_seed_combat_biome_matches_generic():
    """Seed combat rozkłada biomy z GENERIC (draw po biomie działa na zaseedowanych)."""
    conn = _mem_conn()
    cat.ensure_catalog_schema(conn)
    cat.seed_catalog(conn)
    rec = cat.draw_combat(conn, biome="forest", level=1, rng=random.Random(0))
    assert rec is not None, "brak trafienia dla forest/level1 po seedzie"
    assert rec["kind"] == "combat"


# ── Test główny: losowanie combat ─────────────────────────────────────────────

def test_draw_combat_filters_biome_and_level():
    conn = _mem_conn()
    cat.ensure_catalog_schema(conn)
    cat.insert_encounter(conn, key="c_forest", kind="combat", biome="forest",
                         level_min=1, level_max=3, weight=10,
                         payload={"enemies": [{"enemy_key": "wolf", "count": 2}]})
    cat.insert_encounter(conn, key="c_city", kind="combat", biome="city",
                         level_min=1, level_max=3, weight=10,
                         payload={"enemies": [{"enemy_key": "thug", "count": 2}]})

    rec = cat.draw_combat(conn, biome="forest", level=2, rng=random.Random(1))
    assert rec is not None and rec["key"] == "c_forest"

    # zły biom → None
    assert cat.draw_combat(conn, biome="swamp", level=2, rng=random.Random(1)) is None
    # poza zakresem poziomu → None
    assert cat.draw_combat(conn, biome="forest", level=9, rng=random.Random(1)) is None


def test_draw_combat_respects_weight_zero():
    """Wiersz z weight=0 nigdy nie wylosowany; is_active=0 pomijany."""
    conn = _mem_conn()
    cat.ensure_catalog_schema(conn)
    cat.insert_encounter(conn, key="never", kind="combat", biome="forest",
                         level_min=1, level_max=9, weight=0,
                         payload={"enemies": [{"enemy_key": "wolf", "count": 1}]})
    cat.insert_encounter(conn, key="always", kind="combat", biome="forest",
                         level_min=1, level_max=9, weight=100,
                         payload={"enemies": [{"enemy_key": "bandit", "count": 1}]})
    for seed in range(20):
        rec = cat.draw_combat(conn, biome="forest", level=1, rng=random.Random(seed))
        assert rec["key"] == "always", "weight=0 nie powinien być losowany"


def test_draw_combat_inactive_skipped():
    conn = _mem_conn()
    cat.ensure_catalog_schema(conn)
    cat.insert_encounter(conn, key="off", kind="combat", biome="forest",
                         level_min=1, level_max=9, weight=100, is_active=0,
                         payload={"enemies": [{"enemy_key": "wolf", "count": 1}]})
    assert cat.draw_combat(conn, biome="forest", level=1, rng=random.Random(0)) is None


# ── Test główny: losowanie social ─────────────────────────────────────────────

def test_draw_social_by_subtype():
    conn = _mem_conn()
    cat.ensure_catalog_schema(conn)
    cat.seed_catalog(conn)
    rec = cat.draw_social(conn, subtype="alley", rng=random.Random(0))
    assert rec is not None
    assert rec["kind"] == "social"
    # payload social ma stat/skill/dc
    assert rec["payload"].get("skill")
    assert rec["payload"].get("dc")


def test_draw_social_empty_subtype_returns_none():
    conn = _mem_conn()
    cat.ensure_catalog_schema(conn)
    cat.seed_catalog(conn)
    assert cat.draw_social(conn, subtype="nonexistent_subtype", rng=random.Random(0)) is None


# ── Test główny: pusty katalog → None (fallback) ─────────────────────────────

def test_empty_catalog_returns_none():
    conn = _mem_conn()
    cat.ensure_catalog_schema(conn)
    assert cat.draw_combat(conn, biome="forest", level=1) is None
    assert cat.draw_social(conn, subtype="alley") is None


# ── Test główny: walidacja FK ─────────────────────────────────────────────────

def test_validate_fk_accepts_known_enemy():
    conn = _mem_conn()
    _seed_fk_refs(conn)
    cat.validate_fk(conn, kind="combat",
                    payload={"enemies": [{"enemy_key": "wolf", "count": 2}]})  # nie rzuca


def test_validate_fk_rejects_unknown_enemy():
    conn = _mem_conn()
    _seed_fk_refs(conn)
    with pytest.raises(ValueError):
        cat.validate_fk(conn, kind="combat",
                        payload={"enemies": [{"enemy_key": "dragon_xyz", "count": 1}]})


def test_validate_fk_accepts_known_skill():
    conn = _mem_conn()
    _seed_fk_refs(conn)
    cat.validate_fk(conn, kind="social",
                    payload={"stat": "WIS", "skill": "awareness", "dc": 12})  # nie rzuca


def test_validate_fk_rejects_unknown_skill():
    conn = _mem_conn()
    _seed_fk_refs(conn)
    with pytest.raises(ValueError):
        cat.validate_fk(conn, kind="social",
                        payload={"stat": "WIS", "skill": "made_up_skill", "dc": 12})


def test_insert_validates_fk():
    """insert_encounter odrzuca zły klucz FK na zapisie."""
    conn = _mem_conn()
    cat.ensure_catalog_schema(conn)
    _seed_fk_refs(conn)
    with pytest.raises(ValueError):
        cat.insert_encounter(conn, key="bad", kind="combat", biome="forest",
                             level_min=1, level_max=3, weight=10,
                             payload={"enemies": [{"enemy_key": "nope", "count": 1}]},
                             validate=True)


# ── Backward compatibility ────────────────────────────────────────────────────

def test_social_encounter_service_pure_fns_still_work():
    """Stary czysty serwis social nadal działa bez zmian (pod-task D go przepnie)."""
    from app.services import social_encounter_service as ses
    ev = ses.pick_social_event("alley", roll=0.0)
    assert ev["key"] in ("pickpocket", "drunk_harassment")
    assert ses.classify_encounter_kind(0.0) == "combat"
    assert ses.pickpocket_loss(1000) == 50  # cap


def test_generic_encounters_hardcode_still_present():
    """GENERIC_ENCOUNTERS hardcode zostaje (źródło seeda + fallback pod-task D)."""
    from app.services import encounter_seed_service as ess
    keys = {e["key"] for e in ess.GENERIC_ENCOUNTERS}
    assert "wolves_forest" in keys
    assert "bandits_road" in keys
