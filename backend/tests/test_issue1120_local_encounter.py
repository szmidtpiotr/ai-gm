"""TDD: Issue #1120 — PT10 encounter przerywa ruch lokalny w sub-lokacjach."""
import json
import random
import sqlite3
import sys

sys.path.insert(0, "/app")

import pytest


def _db():
    conn = sqlite3.connect("/data/ai_gm.db")
    conn.row_factory = sqlite3.Row
    return conn


def _risky_local_hex(conn):
    row = conn.execute(
        "SELECT * FROM world_hexes WHERE map_level=1 AND encounter_chance > 0 AND is_active=1 LIMIT 1"
    ).fetchone()
    return dict(row) if row else None


def _safe_local_hex(conn):
    row = conn.execute(
        "SELECT * FROM world_hexes WHERE map_level=1 AND encounter_chance = 0 AND is_active=1 LIMIT 1"
    ).fetchone()
    return dict(row) if row else None


# ── Test główny ──────────────────────────────────────────────────────────────

def test_check_local_encounter_risky_hex_forced_roll():
    """Risky hex (chance>0) + wymuszone trafienie → zwraca encounter dict z enemy_key."""
    from app.routers.local_map import _check_local_encounter

    conn = _db()
    try:
        target = _risky_local_hex(conn)
        if not target:
            pytest.skip("No risky local hexes in DB")

        original = random.random
        try:
            random.random = lambda: 0.001  # zawsze < 0.20 → encounter
            result = _check_local_encounter(target, cleared_local_hexes=[])
        finally:
            random.random = original

        assert result is not None, "Risky hex + forced roll must return encounter dict"
        assert "enemy_key" in result, "Encounter dict must include enemy_key"
        assert result["enemy_key"], "enemy_key must not be empty"
    finally:
        conn.close()


def test_check_local_encounter_safe_hex_never():
    """Safe hex (chance=0) → None bez względu na rzut."""
    from app.routers.local_map import _check_local_encounter

    conn = _db()
    try:
        target = _safe_local_hex(conn)
        if not target:
            pytest.skip("No safe local hexes in DB")

        original = random.random
        try:
            random.random = lambda: 0.0  # najgorszy możliwy rzut
            result = _check_local_encounter(target, cleared_local_hexes=[])
        finally:
            random.random = original

        assert result is None, "Safe hex (encounter_chance=0) must never trigger encounter"
    finally:
        conn.close()


def test_check_local_encounter_cleared_hex_no_repeat():
    """Raz wyczyszczony hex → None nawet przy wymuszonym rzucie."""
    from app.routers.local_map import _check_local_encounter

    conn = _db()
    try:
        target = _risky_local_hex(conn)
        if not target:
            pytest.skip("No risky local hexes in DB")

        hex_id = target["id"]

        original = random.random
        try:
            random.random = lambda: 0.001  # force encounter
            result = _check_local_encounter(target, cleared_local_hexes=[hex_id])
        finally:
            random.random = original

        assert result is None, f"Cleared hex {hex_id} must not re-trigger encounter"
    finally:
        conn.close()


# ── Backward compatibility ───────────────────────────────────────────────────

def test_check_local_encounter_zero_chance_is_safe():
    """encounter_chance=0 bez DB lookup → zawsze None (bezpieczeństwo)."""
    from app.routers.local_map import _check_local_encounter

    synthetic = {"id": 99999, "encounter_chance": 0, "encounter_pool": None, "label": "Zajazd"}

    original = random.random
    try:
        random.random = lambda: 0.0
        result = _check_local_encounter(synthetic, cleared_local_hexes=[])
    finally:
        random.random = original

    assert result is None, "encounter_chance=0 must always return None"


def test_check_local_encounter_fallback_pool_when_no_pool():
    """Hex z pustą encounter_pool → encounter używa fallback pool (bandit itp.)."""
    from app.routers.local_map import _check_local_encounter

    # Hex without pool but with chance > 0
    synthetic = {"id": 88888, "encounter_chance": 1.0, "encounter_pool": None, "label": "Ciemny zaułek"}

    original = random.random
    try:
        random.random = lambda: 0.001
        result = _check_local_encounter(synthetic, cleared_local_hexes=[])
    finally:
        random.random = original

    assert result is not None, "Hex with chance=1.0 and no pool must still return encounter"
    assert "enemy_key" in result
    assert result["enemy_key"], "Fallback pool must produce a valid enemy_key"
