"""TDD: Issues #1162 / #1163 / #1164 — migration runner idempotency + single-boot completeness.

#1162 — replay of unconditional UPDATE / INSERT OR REPLACE clobbers admin runtime edits
        (loot weights, rank_ceiling, XP costs, hex terrain) on every backend restart.
#1163 — on a fresh DB the RAW migrations run BEFORE the tables they ALTER exist, the
        "no such table" swallow hides it, so the schema is only complete after a 2nd restart.
#1164 — game_config_meta XP keys seeded twice with divergent values (ceiling 19 vs 20,
        skill costs 100/75/150 vs 50/100/200/400/1200) → value flips between boot 1 and 2.

The fix introduces `run_all_migrations()` — one call = one boot:
  * a `schema_migrations` applied-set so every non-DDL (UPDATE / INSERT) statement runs ONCE,
  * a fix-point loop that re-runs the passes until zero "no such table" remain (cyclic deps),
  * per-file idempotency + per-file try for app/db/migrations/*.sql,
  * a single canonical value (game_mechanics.md) for the XP meta keys.
"""
import importlib
import json
import sqlite3

import pytest


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """Redirect every migration runner at an isolated empty DB file."""
    db_file = str(tmp_path / "ai_gm_test.db")
    import app.main as main_mod
    import app.migrations_admin as adm_mod
    monkeypatch.setattr(main_mod, "DB_PATH", db_file)
    monkeypatch.setattr(adm_mod, "DB_PATH", db_file)
    return db_file, main_mod


def _cols(conn, table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _has_table(conn, table):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


# ─── Test główny — świeża baza kompletna po JEDNYM boocie (#1163) ─────────────

def test_fresh_db_schema_complete_after_single_boot(temp_db):
    """Jeden przebieg run_all_migrations() → wszystkie kolumny z RAW obecne (bez 2. restartu)."""
    db_file, main_mod = temp_db
    main_mod.run_all_migrations()

    conn = sqlite3.connect(db_file)
    try:
        # Kolumny SELECT-owane w kodzie a dodawane przez RAW na tabelach tworzonych
        # przez admin/sql-file (dowód z #1163) — muszą istnieć po PIERWSZYM boocie.
        assert "scene_enemies" in _cols(conn, "game_sessions")
        assert "status" in _cols(conn, "campaign_members")
        assert "character_id" in _cols(conn, "campaign_members")
        assert "boss_defeated" in _cols(conn, "active_combat")
        assert "spawn_weight" in _cols(conn, "hex_type_config")
        assert "location_spawn_chance" in _cols(conn, "hex_type_config")
        # admin ALTER na tabeli tworzonej przez RAW (cykl admin↔RAW)
        assert "complete_push_sent" in _cols(conn, "campaign_rounds")
    finally:
        conn.close()


def test_second_boot_reports_zero_pending(temp_db):
    """Po pełnej migracji drugi boot nie ma już żadnych 'no such table' do dogonienia."""
    db_file, main_mod = temp_db
    main_mod.run_all_migrations()
    # Druga migracja na kompletnej bazie: zero brakujących tabel → zbieżność w 1 przebiegu.
    passes = main_mod.run_all_migrations()
    assert passes == 1, f"kompletna baza powinna zbiec w 1 przebiegu, było {passes}"


# ─── #1162 — edycje admina PRZEŻYWAJĄ replay migracji ────────────────────────

def test_admin_loot_weight_survives_replay(temp_db):
    """Ręcznie zmieniona waga lootu nie jest cofana przez ponowny przebieg migracji."""
    db_file, main_mod = temp_db
    main_mod.run_all_migrations()

    conn = sqlite3.connect(db_file)
    try:
        row = conn.execute(
            "SELECT id, weight FROM game_config_loot_entries LIMIT 1"
        ).fetchone()
        assert row is not None, "brak wierszy loot do przetestowania (seed nie zadziałał)"
        entry_id = row[0]
        conn.execute(
            "UPDATE game_config_loot_entries SET weight = 999 WHERE id = ?", (entry_id,)
        )
        conn.commit()
    finally:
        conn.close()

    main_mod.run_all_migrations()  # replay — nie może cofnąć edycji

    conn = sqlite3.connect(db_file)
    try:
        w = conn.execute(
            "SELECT weight FROM game_config_loot_entries WHERE id = ?", (entry_id,)
        ).fetchone()[0]
        assert w == 999, f"waga lootu cofnięta przez replay (było 999, jest {w})"
    finally:
        conn.close()


def test_admin_rank_ceiling_survives_replay(temp_db):
    """Zmiana rank_ceiling z admina przeżywa replay (nie cofa jej bezwarunkowy UPDATE SET rank_ceiling=3)."""
    db_file, main_mod = temp_db
    main_mod.run_all_migrations()

    conn = sqlite3.connect(db_file)
    try:
        key = conn.execute("SELECT key FROM game_config_skills LIMIT 1").fetchone()[0]
        conn.execute(
            "UPDATE game_config_skills SET rank_ceiling = 5 WHERE key = ?", (key,)
        )
        conn.commit()
    finally:
        conn.close()

    main_mod.run_all_migrations()

    conn = sqlite3.connect(db_file)
    try:
        rc = conn.execute(
            "SELECT rank_ceiling FROM game_config_skills WHERE key = ?", (key,)
        ).fetchone()[0]
        assert rc == 5, f"rank_ceiling cofnięty przez replay (było 5, jest {rc})"
    finally:
        conn.close()


# ─── #1164 — jedno źródło prawdy dla meta XP, wartości ze spec (game_mechanics.md) ──

def test_xp_meta_single_source_of_truth(temp_db):
    """xp_* meta seedowane raz, wartościami ze spec; stałe między boot 1 a 2."""
    db_file, main_mod = temp_db
    main_mod.run_all_migrations()

    def _meta(conn, k):
        r = conn.execute(
            "SELECT value FROM game_config_meta WHERE key = ?", (k,)
        ).fetchone()
        return r[0] if r else None

    conn = sqlite3.connect(db_file)
    try:
        ceiling = _meta(conn, "xp_stat_value_ceiling")
        skill_costs = json.loads(_meta(conn, "xp_skill_rank_costs"))
    finally:
        conn.close()

    # game_mechanics.md: 19+ = Niedostępne; skill 1→2 = 75, 2→3 = 150, nowy = 100
    assert ceiling == "19", f"ceiling powinien być 19 (spec), jest {ceiling}"
    assert skill_costs == {"1": 100, "2": 75, "3": 150}, skill_costs

    # Drugi boot nie może zmienić wartości (brak rozjazdu 19↔20).
    main_mod.run_all_migrations()
    conn = sqlite3.connect(db_file)
    try:
        assert _meta(conn, "xp_stat_value_ceiling") == "19"
        assert json.loads(_meta(conn, "xp_skill_rank_costs")) == {"1": 100, "2": 75, "3": 150}
    finally:
        conn.close()


# ─── Backward compatibility — pojedyncze runnery nadal wołalne ───────────────

def test_individual_runners_still_callable(temp_db):
    """run_raw_migrations / run_app_sql_migrations nadal istnieją i zwracają licznik braków."""
    db_file, main_mod = temp_db
    n1 = main_mod.run_raw_migrations()
    n2 = main_mod.run_app_sql_migrations()
    assert isinstance(n1, int) and isinstance(n2, int)
