"""TDD: Issue #1202 — content-as-code (A) + DEV↔PROD schema alignment (B).

Part B: _drop_legacy_content_columns_1202 removes 10 dead legacy columns,
        keeps live ones, and is idempotent.
Part A: content_seed_lib snapshot/apply round-trips identically and never
        touches campaign / gameplay rows (Wariant 2) nor player tables.

content_seed_lib.py is docker-cp'd next to this test so the bare `import` works
inside the backend container (scripts/ is not baked into the image).
"""

import json
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fixtures_schema import table_sql

from app.migrations_admin import (  # noqa: E402
    _LEGACY_CONTENT_COLUMNS_1202,
    _drop_legacy_content_columns_1202,
)
import content_seed_lib as csl  # noqa: E402


# ── Part B — schema alignment ────────────────────────────────────────────────

def _build_legacy_db():
    """A DB carrying all 10 dead columns + the kept ones (PROD-shaped)."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        """ + table_sql("game_config_items") + """
        """ + table_sql("game_config_weapons") + """
        """ + table_sql("game_config_loot_entries") + """
        CREATE TABLE game_dungeons (
            key TEXT PRIMARY KEY, label TEXT, difficulty_config_json TEXT);
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY, key TEXT,
            local_hex_q INTEGER, local_hex_r INTEGER, is_generic INTEGER,
            hex_type_key TEXT, image_url TEXT, region TEXT);
        """
    )
    conn.commit()
    return conn


def _cols(conn, table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def test_drop_legacy_columns_removes_all_dead():
    conn = _build_legacy_db()
    _drop_legacy_content_columns_1202(conn)
    for table, dead in _LEGACY_CONTENT_COLUMNS_1202.items():
        present = _cols(conn, table)
        for col in dead:
            assert col not in present, f"{table}.{col} should be dropped"


def test_drop_legacy_keeps_live_columns():
    conn = _build_legacy_db()
    _drop_legacy_content_columns_1202(conn)
    # weapons.durability_base is LIVE (weapon durability) — must survive.
    assert "durability_base" in _cols(conn, "game_config_weapons")
    # items image_url / image_gen_prompt are the live successors — must survive.
    assert {"image_url", "image_gen_prompt"} <= _cols(conn, "game_config_items")


def test_drop_legacy_idempotent():
    conn = _build_legacy_db()
    _drop_legacy_content_columns_1202(conn)
    _drop_legacy_content_columns_1202(conn)  # second run must not raise
    assert "image_prompt" not in _cols(conn, "game_config_items")


def test_drop_legacy_noop_when_columns_absent():
    """DEV-shaped DB (columns already gone) — helper must no-op cleanly."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE game_config_items (key TEXT PRIMARY KEY, label TEXT)")
    conn.commit()
    _drop_legacy_content_columns_1202(conn)  # no such column — silent
    assert _cols(conn, "game_config_items") == {"key", "label"}


# ── Part A — content-as-code round-trip + canon safety ───────────────────────

_SUBSET = ["game_config_stats", "npcs", "game_locations"]


def _build_content_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);
        """ + table_sql("game_config_stats") + """
        CREATE TABLE npcs (
            id INTEGER PRIMARY KEY, key TEXT, label TEXT, review_status TEXT);
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY, key TEXT, label TEXT,
            review_status TEXT, source_campaign_id INTEGER);
        """
    )
    # player row — must never be touched
    conn.execute("INSERT INTO users VALUES (1, 'piotr')")
    # authored content (canon)
    conn.execute("INSERT INTO game_config_stats VALUES ('STR', 'Siła')")
    conn.execute("INSERT INTO game_config_stats VALUES ('DEX', 'Zręczność')")
    conn.execute("INSERT INTO npcs VALUES (1, 'kowal', 'Kowal', 'permanent')")
    conn.execute(
        "INSERT INTO game_locations VALUES (1, 'rynek', 'Rynek', 'permanent', NULL)"
    )
    # campaign / gameplay rows — canon filter must exclude + protect these
    conn.execute("INSERT INTO npcs VALUES (2, 'widmo', 'Widmo', 'pending_review')")
    conn.execute(
        "INSERT INTO game_locations VALUES (2, 'jaskinia', 'Jaskinia', 'pending_review', 42)"
    )
    conn.commit()
    conn.close()


def test_snapshot_excludes_campaign_rows(tmp_path):
    db = str(tmp_path / "src.db")
    _build_content_db(db)
    out = str(tmp_path / "seeds")
    csl.snapshot_all(db, out, tables=_SUBSET)

    npcs = json.load(open(csl.seed_path(out, "npcs")))
    locs = json.load(open(csl.seed_path(out, "game_locations")))
    assert [r["key"] for r in npcs] == ["kowal"]  # 'widmo' (pending_review) excluded
    assert [r["key"] for r in locs] == ["rynek"]  # 'jaskinia' (campaign) excluded


def test_apply_protects_campaign_rows_on_target(tmp_path):
    # snapshot from a clean source (canon only), then apply onto a target that
    # already holds a campaign row — the campaign row must survive.
    src = str(tmp_path / "src.db")
    _build_content_db(src)
    out = str(tmp_path / "seeds")
    csl.snapshot_all(src, out, tables=_SUBSET)

    tgt = str(tmp_path / "tgt.db")
    _build_content_db(tgt)  # target also has its own campaign rows (ids 2)
    res = csl.apply_all(tgt, out, tables=_SUBSET)
    assert res["ok"], res

    conn = sqlite3.connect(tgt)
    # campaign rows untouched
    assert conn.execute(
        "SELECT count(*) FROM npcs WHERE review_status='pending_review'"
    ).fetchone()[0] == 1
    assert conn.execute(
        "SELECT count(*) FROM game_locations WHERE source_campaign_id=42"
    ).fetchone()[0] == 1
    # players untouched
    assert conn.execute("SELECT name FROM users WHERE id=1").fetchone()[0] == "piotr"
    conn.close()


def test_apply_replaces_canon_and_verifies_count(tmp_path):
    src = str(tmp_path / "src.db")
    _build_content_db(src)
    out = str(tmp_path / "seeds")
    csl.snapshot_all(src, out, tables=_SUBSET)

    tgt = str(tmp_path / "tgt.db")
    _build_content_db(tgt)
    # mutate target canon: add a stray stat + rename one — apply must overwrite
    conn = sqlite3.connect(tgt)
    conn.execute("INSERT INTO game_config_stats VALUES ('STALE', 'x')")
    conn.execute("UPDATE game_config_stats SET label='WRONG' WHERE key='STR'")
    conn.commit()
    conn.close()

    assert csl.apply_all(tgt, out, tables=_SUBSET)["ok"]
    conn = sqlite3.connect(tgt)
    rows = dict(conn.execute("SELECT key,label FROM game_config_stats").fetchall())
    assert rows == {"STR": "Siła", "DEX": "Zręczność"}  # STALE gone, STR restored
    conn.close()


def test_roundtrip_snapshot_apply_snapshot_identical(tmp_path):
    src = str(tmp_path / "src.db")
    _build_content_db(src)
    out1 = str(tmp_path / "s1")
    csl.snapshot_all(src, out1, tables=_SUBSET)

    csl.apply_all(src, out1, tables=_SUBSET)  # apply back onto itself
    out2 = str(tmp_path / "s2")
    csl.snapshot_all(src, out2, tables=_SUBSET)

    for t in _SUBSET:
        a = open(csl.seed_path(out1, t), encoding="utf-8").read()
        b = open(csl.seed_path(out2, t), encoding="utf-8").read()
        assert a == b, f"round-trip drift in {t}"


def test_dry_run_writes_nothing(tmp_path):
    src = str(tmp_path / "src.db")
    _build_content_db(src)
    out = str(tmp_path / "seeds")
    csl.snapshot_all(src, out, tables=_SUBSET)

    tgt = str(tmp_path / "tgt.db")
    _build_content_db(tgt)
    conn = sqlite3.connect(tgt)
    conn.execute("INSERT INTO game_config_stats VALUES ('STALE', 'x')")
    conn.commit()
    conn.close()

    res = csl.apply_all(tgt, out, dry_run=True, tables=_SUBSET)
    assert res["ok"] and res["dry_run"]
    conn = sqlite3.connect(tgt)
    # STALE still there — dry-run wrote nothing
    assert conn.execute(
        "SELECT count(*) FROM game_config_stats WHERE key='STALE'"
    ).fetchone()[0] == 1
    conn.close()


# ── Single source of truth for the table list ────────────────────────────────

def test_sync_and_lib_table_lists_match():
    """sync_content_dev_to_prod must not drift from the canonical list."""
    import importlib.util

    sync_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "..", "scripts", "sync_content_dev_to_prod.py",
    )
    if not os.path.exists(sync_path):
        pytest.skip("sync script not present in this image")
    spec = importlib.util.spec_from_file_location("sync_mod", sync_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.CONTENT_TABLES == csl.CONTENT_TABLES


def test_canon_filters_cover_only_dual_tables():
    # #1480 — filtr rozszerzony o tabele przypisań: wskazują lokację kluczem, więc
    # bez filtra przypisanie do lokacji-śmiecia (test_inn_u31) trafiało do gita.
    assert set(csl.CANON_FILTERS) == {
        "npcs",
        "game_locations",
        "location_npc_assignments",
        "location_enemy_assignments",
        "npc_locations",
    }
    for t in csl.CANON_FILTERS:
        assert t in csl.CONTENT_TABLES


def test_canon_filter_excludes_issue_prefixed_junk():
    """#1480 — klucze `issue1105_*` przeciekły do gita mimo filtra na `test_`."""
    import sqlite3

    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE game_locations (key TEXT, source_campaign_id INT, review_status TEXT)")
    conn.executemany(
        "INSERT INTO game_locations VALUES (?,NULL,NULL)",
        [("tundra_mrozu",), ("issue1105_tundra_mrozu_990001105",), ("test_flow_123",),
         ("__test_camp_1__",), ("dup_test_9",)],
    )
    rows = conn.execute(
        f"SELECT key FROM game_locations WHERE {csl.CANON_FILTERS['game_locations']}"
    ).fetchall()
    assert [r[0] for r in rows] == ["tundra_mrozu"]
