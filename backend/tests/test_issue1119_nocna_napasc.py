"""TDD: Issue #1119 — nocna napaść przy obozie skaluje się z terenem hexa."""
import json
import sqlite3
import sys
import os
import importlib

sys.path.insert(0, "/app")

import pytest

DB_PATH = os.environ.get("DB_PATH", "/data/ai_gm.db")


# ── helpers ──────────────────────────────────────────────────────────────────


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _hex_type_config_boost(conn, hex_type: str) -> float:
    row = conn.execute(
        "SELECT camp_encounter_boost FROM hex_type_config WHERE hex_type = ? AND is_active = 1",
        (hex_type,),
    ).fetchone()
    assert row is not None, f"hex_type_config missing for '{hex_type}'"
    return float(row["camp_encounter_boost"])


# ── FAZA 1: kolumna w hex_type_config ────────────────────────────────────────


def test_hex_type_config_has_camp_encounter_boost_column():
    """hex_type_config musi mieć kolumnę camp_encounter_boost (REAL)."""
    conn = _get_conn()
    try:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(hex_type_config)")}
        assert "camp_encounter_boost" in cols, (
            "Brak kolumny camp_encounter_boost w hex_type_config"
        )
    finally:
        conn.close()


def test_camp_boost_wild_terrain_is_035():
    """Dziki teren (forest) → camp_encounter_boost = 0.35."""
    conn = _get_conn()
    try:
        boost = _hex_type_config_boost(conn, "forest")
        assert boost == pytest.approx(0.35, abs=1e-6), (
            f"Oczekiwano 0.35 dla forest, dostano {boost}"
        )
    finally:
        conn.close()


def test_camp_boost_civilized_terrain_is_020():
    """Teren cywilizowany (plains) → camp_encounter_boost = 0.20."""
    conn = _get_conn()
    try:
        boost = _hex_type_config_boost(conn, "plains")
        assert boost == pytest.approx(0.20, abs=1e-6), (
            f"Oczekiwano 0.20 dla plains, dostano {boost}"
        )
    finally:
        conn.close()


def test_camp_boost_mountains_is_035():
    """Góry → camp_encounter_boost = 0.35."""
    conn = _get_conn()
    try:
        boost = _hex_type_config_boost(conn, "mountains")
        assert boost == pytest.approx(0.35, abs=1e-6), (
            f"Oczekiwano 0.35 dla mountains, dostano {boost}"
        )
    finally:
        conn.close()


def test_camp_boost_swamp_is_035():
    """Bagno → camp_encounter_boost = 0.35."""
    conn = _get_conn()
    try:
        boost = _hex_type_config_boost(conn, "swamp")
        assert boost == pytest.approx(0.35, abs=1e-6), (
            f"Oczekiwano 0.35 dla swamp, dostano {boost}"
        )
    finally:
        conn.close()


# ── helpers do testów perform_long_rest ──────────────────────────────────────


def _setup_camp_rest_test(conn, boost: float, night_march: bool = False, enemy_pool=None):
    """Znajdź aktywną postać, wstaw tymczasowy obóz safe_for_rest=1, ustaw flagi.

    Zwraca (char_id, camp_id) lub (None, None) jeśli brak postaci.
    """
    enemy_pool = enemy_pool or ["wolf", "bandit"]
    char_row = conn.execute(
        "SELECT c.id, c.campaign_id FROM characters c "
        "JOIN game_sessions gs ON gs.campaign_id = c.campaign_id "
        "WHERE c.status = 'in_campaign' LIMIT 1"
    ).fetchone()
    if not char_row:
        return None, None

    char_id = char_row["id"]
    camp_id = char_row["campaign_id"]

    sess_row = conn.execute(
        "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (camp_id,),
    ).fetchone()
    assert sess_row, "Brak sesji"

    flags = json.loads(sess_row["session_flags"] or "{}")

    # Wstaw (lub zastąp) tymczasową safe lokację testową
    test_loc_key = f"__test_camp_1119_{camp_id}__"
    conn.execute(
        "INSERT OR REPLACE INTO game_locations (key, label, safe_for_rest, is_active, created_by) "
        "VALUES (?, 'Obóz testowy', 1, 1, 'seed')",
        (test_loc_key,),
    )
    loc_id = conn.execute(
        "SELECT id FROM game_locations WHERE key = ?", (test_loc_key,)
    ).fetchone()["id"]

    # Ustaw hex encounter_pool
    hex_data = flags.get("current_hex") or {}
    q = hex_data.get("q")
    r = hex_data.get("r")
    if q is not None and r is not None:
        conn.execute(
            "UPDATE world_hexes SET encounter_pool = ? WHERE q = ? AND r = ? AND is_active = 1",
            (json.dumps(enemy_pool), q, r),
        )

    flags["camp_encounter_boost"] = boost
    flags["night_march"] = night_march
    conn.execute(
        "UPDATE game_sessions SET session_flags = ?, current_location_id = ? WHERE id = ?",
        (json.dumps(flags, ensure_ascii=False), loc_id, sess_row["id"]),
    )
    conn.commit()
    return char_id, camp_id


# ── FAZA 2: perform_long_rest zwraca camp_encounter info ─────────────────────


def test_long_rest_camp_encounter_result_key_present():
    """perform_long_rest musi zwracać klucz 'camp_encounter' gdy boost był ustawiony."""
    from app.services.rest_service import perform_long_rest

    conn = _get_conn()
    try:
        char_id, camp_id = _setup_camp_rest_test(conn, boost=1.0, enemy_pool=["wolf", "bandit"])
        if char_id is None:
            pytest.skip("Brak postaci w kampanii do testu")

        result = perform_long_rest(conn, char_id, camp_id)

        assert "camp_encounter" in result, (
            f"Brak klucza 'camp_encounter' w wyniku perform_long_rest. Wynik: {result}"
        )
        enc = result["camp_encounter"]
        assert enc.get("triggered") is True, (
            f"camp_encounter.triggered powinno być True przy boost=1.0, dostano: {enc}"
        )
        assert enc.get("enemy_key") in ("wolf", "bandit"), (
            f"enemy_key poza pulą: {enc.get('enemy_key')}"
        )
    finally:
        conn.close()


def test_long_rest_clears_camp_encounter_boost():
    """Po długim odpoczynku camp_encounter_boost musi być usunięty z session_flags."""
    from app.services.rest_service import perform_long_rest

    conn = _get_conn()
    try:
        char_id, camp_id = _setup_camp_rest_test(conn, boost=0.20)
        if char_id is None:
            pytest.skip("Brak postaci w kampanii")

        perform_long_rest(conn, char_id, camp_id)

        after_row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (camp_id,),
        ).fetchone()
        after_flags = json.loads(after_row["session_flags"] or "{}")
        assert "camp_encounter_boost" not in after_flags, (
            "camp_encounter_boost nie został wyczyszczony po długim odpoczynku"
        )
    finally:
        conn.close()


def test_night_march_adds_010_to_boost():
    """night_march=True → efektywny boost = camp_encounter_boost + 0.10 (1.0 → zawsze trigger)."""
    from app.services.rest_service import perform_long_rest

    conn = _get_conn()
    try:
        char_id, camp_id = _setup_camp_rest_test(conn, boost=0.90, night_march=True, enemy_pool=["orc"])
        if char_id is None:
            pytest.skip("Brak postaci w kampanii")

        # Sprawdź czy current_hex jest ustawiony (potrzebny do encounter_pool)
        sess_row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (camp_id,),
        ).fetchone()
        flags = json.loads(sess_row["session_flags"] or "{}")
        hex_data = flags.get("current_hex") or {}
        if not hex_data.get("q"):
            pytest.skip("Brak current_hex — pool nieosiągalny")

        result = perform_long_rest(conn, char_id, camp_id)
        enc = result.get("camp_encounter", {})
        assert enc.get("triggered") is True, (
            f"Przy boost=0.90 + night_march=True oczekiwano trigger=True, dostano: {enc}"
        )
        assert enc.get("night_march_bonus") is True, (
            f"camp_encounter.night_march_bonus powinno być True, dostano: {enc}"
        )
    finally:
        conn.close()
