"""TDD: Issue #428 (E13) — generic encounter pool with biome/trigger/level tags."""
import sys, os, json, sqlite3

sys.path.insert(0, "/app")

import pytest

DB_PATH = os.environ.get("DB_PATH", "/data/ai_gm.db")


def _count_generic():
    conn = sqlite3.connect(DB_PATH)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM adventure_hooks WHERE draft_data LIKE '%\"__generic_encounter__\"%'"
        ).fetchone()[0]
    finally:
        conn.close()


def _cleanup():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM adventure_hooks WHERE draft_data LIKE '%\"__generic_encounter__\"%'")
        conn.commit()
    finally:
        conn.close()


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_seed_inserts_tagged_encounters():
    """seed_generic_encounters must insert >=3 encounter hooks, each tagged with
    biomes, trigger_types and level_min/level_max."""
    from app.services.encounter_seed_service import seed_generic_encounters
    _cleanup()
    try:
        n = seed_generic_encounters()
        assert n >= 3, f"expected >=3 generic encounters seeded, got {n}"
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT draft_data, status FROM adventure_hooks WHERE draft_data LIKE '%\"__generic_encounter__\"%'"
            ).fetchall()
        finally:
            conn.close()
        for r in rows:
            assert r["status"] in ("approved", "promoted"), f"generic encounter not approved: {r['status']}"
            enc = json.loads(r["draft_data"])["encounter"]
            assert enc.get("biomes"), f"encounter missing biomes: {enc}"
            assert enc.get("trigger_types"), f"encounter missing trigger_types: {enc}"
            assert "level_min" in enc and "level_max" in enc, f"encounter missing level bounds: {enc}"
    finally:
        _cleanup()


def test_seed_is_idempotent():
    """Running the seed twice must not duplicate the generic encounters."""
    from app.services.encounter_seed_service import seed_generic_encounters
    _cleanup()
    try:
        seed_generic_encounters()
        first = _count_generic()
        seed_generic_encounters()
        second = _count_generic()
        assert first == second, f"seed not idempotent: {first} → {second}"
    finally:
        _cleanup()


def test_seeded_encounters_filter_by_biome_and_level():
    """A seeded encounter must be matchable via encounter_matches by biome+level."""
    from app.services.encounter_seed_service import seed_generic_encounters
    from app.services.encounter_service import encounter_matches
    _cleanup()
    try:
        seed_generic_encounters()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT draft_data FROM adventure_hooks WHERE draft_data LIKE '%\"__generic_encounter__\"%'"
            ).fetchall()
        finally:
            conn.close()
        # At least one seeded encounter must match its own biome at a level inside its band.
        matched_any = False
        for r in rows:
            enc = json.loads(r["draft_data"])["encounter"]
            biome = (enc.get("biomes") or [None])[0]
            lvl = int(enc.get("level_min") or 1)
            trig = (enc.get("trigger_types") or ["hex_enter"])[0]
            if encounter_matches(enc, trigger=trig, hex_type=biome, hero_level=lvl):
                matched_any = True
                break
        assert matched_any, "no seeded encounter matched its own biome/level"
    finally:
        _cleanup()
