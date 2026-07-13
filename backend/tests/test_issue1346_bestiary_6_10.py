"""TDD: Issue #1346 — bestiariusz lvl 6-10 wypełnia pasma + generyczni + tereny.

Follow-up contentowy do code-fixa #1345 (siatka poszerzająca pulę). Ten test to
BRAMKA DANYCH kodująca kryteria akceptacji z issue #1346:

  1. lvl 10 ma NATYWNYCH wrogów standard/elite (pula lvl-10 BEZ fallbacku ≥ 8,
     wielotierowa — nie same bossy).
  2. road/plains/river przy lvl 10 → pula ≥ 3 różnych wrogów (brak wymuszonych
     powtórek przez anti-repeat).
  3. Kilku wrogów generycznych (pusty terrain_tags) pokrywa dowolny teren na
     średnich/wysokich poziomach.

Test jedzie na współdzielonej bazie DEV `/data/ai_gm.db` (read-only) i używa
prawdziwych funkcji puli z encounter_service — mierzy realny stan danych, nie mock.
Failuje dopóki content lvl 6-10 nie jest dosiany (seed #1346)."""
import os
import sqlite3

import pytest

from app.services.encounter_service import (
    _filter_by_terrain,
    _query_scoped_enemies,
    eligible_enemy_pool,
)

DB_PATH = os.environ.get("AI_GM_DB_PATH", "/data/ai_gm.db")


@pytest.fixture()
def conn():
    c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    try:
        yield c
    finally:
        c.close()


def _native_pool(conn, level, hex_type=None):
    """Pula BEZ fallbacku (delta=0) — dokładnie okno [level, level]."""
    return _filter_by_terrain(_query_scoped_enemies(conn, level, level), hex_type)


# ─── Test główny 1 — natywna pula lvl 10 wielotierowa ────────────────────────

def test_native_lvl10_pool_is_multitier_and_deep(conn):
    """lvl 10 (cap) ma ≥8 natywnych wrogów, w tym tiery inne niż `boss`."""
    pool = _native_pool(conn, 10)
    tiers = {e.get("tier") for e in pool}
    assert len(pool) >= 8, (
        f"pula lvl-10 (bez fallbacku) = {len(pool)} < 8 — same bossy? "
        f"tiery={tiers}"
    )
    non_boss = tiers - {"boss"}
    assert non_boss, f"lvl 10 ma tylko bossy (tiery={tiers}) — brak standard/elite"


# ─── Test główny 2 — pokrycie terenów przy lvl 10 ────────────────────────────

@pytest.mark.parametrize("hex_type", ["road", "plains", "river"])
def test_terrain_coverage_lvl10(conn, hex_type):
    """road/plains/river przy lvl 10 → ≥3 różnych wrogów (bez wymuszonej powtórki)."""
    pool = _native_pool(conn, 10, hex_type)
    keys = {e["key"] for e in pool}
    assert len(keys) >= 3, (
        f"teren {hex_type} @ lvl 10: pula={len(keys)} różnych ({keys}) < 3 "
        f"— anti-repeat wymusi powtórkę spotkania"
    )


# ─── Test główny 3 — wrogowie generyczni (pusty terrain_tags) ────────────────

def test_generic_high_level_enemies_exist(conn):
    """Kilku wrogów bez terrain_tags pokrywa dowolny teren na lvl ≥6."""
    n = conn.execute(
        """
        SELECT COUNT(*) FROM game_config_enemies
        WHERE world_scope = 'global' AND review_status = 'permanent' AND is_active = 1
          AND (terrain_tags IS NULL OR TRIM(terrain_tags) = '')
          AND (max_level IS NULL OR max_level >= 6)
          AND (min_level IS NULL OR min_level <= 10)
        """
    ).fetchone()[0]
    assert n >= 3, f"generycznych wrogów lvl≥6 = {n} < 3 — cienkie tereny bez łaty"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_low_level_pool_still_populated(conn):
    """Stare zachowanie: pula lvl 1 na trakcie nadal niepusta (nie zepsuliśmy 1-5)."""
    pool = eligible_enemy_pool(conn, level=1, hex_type="road")
    assert len(pool) >= 3, f"pula lvl-1 road spadła do {len(pool)} — regresja pasm 1-2"
