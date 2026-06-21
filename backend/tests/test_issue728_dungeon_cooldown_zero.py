"""TDD: Issue #728 — dungeon cooldown=0 must mean "no cooldown", not silently fall to 72h.

Root cause: `int(x or 72)` treats 0 (falsy) as unset → 72h default, and
check_cooldown never re-checked the LIVE cooldown_hours, so a stale cooldown_until
row kept blocking entry after admin set cooldown=0.
"""
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/app")

from app.services import dungeon_service as ds


# ─── Test główny: helper honoruje 0 ──────────────────────────────────────────

def test_resolve_cooldown_hours_honors_explicit_zero():
    """Admin sets cooldown=0 → no cooldown. Must NOT silently become 72h."""
    assert ds._resolve_cooldown_hours({"cooldown_hours": 0}) == 0
    assert ds._resolve_cooldown_hours({"cooldown_hours": "0"}) == 0


# ─── Backward compatibility: unset i normalne wartości ───────────────────────

def test_resolve_cooldown_hours_unset_falls_back_to_72():
    """None / '' / missing key (truly unset) still defaults to 72h."""
    assert ds._resolve_cooldown_hours({"cooldown_hours": None}) == 72
    assert ds._resolve_cooldown_hours({"cooldown_hours": ""}) == 72
    assert ds._resolve_cooldown_hours({}) == 72


def test_resolve_cooldown_hours_normal_values_passthrough():
    """Normal positive values unchanged; junk falls back to 72."""
    assert ds._resolve_cooldown_hours({"cooldown_hours": 72}) == 72
    assert ds._resolve_cooldown_hours({"cooldown_hours": 24}) == 24
    assert ds._resolve_cooldown_hours({"cooldown_hours": "12"}) == 12
    assert ds._resolve_cooldown_hours({"cooldown_hours": "garbage"}) == 72


# ─── Test integracyjny: check_cooldown kasuje zalegający timer gdy live==0 ────

def test_check_cooldown_clears_stale_timer_when_live_cooldown_zero(monkeypatch):
    """Stale cooldown_until (set under old 72h) must be ignored once admin sets 0."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE character_dungeon_runs "
        "(character_id INT, location_key TEXT, cooldown_until TEXT, run_count INT)"
    )
    future = (datetime.now(timezone.utc) + timedelta(hours=20)).isoformat()
    conn.execute(
        "INSERT INTO character_dungeon_runs VALUES (?, ?, ?, ?)",
        (1, "krypta_probna", future, 3),
    )
    conn.commit()

    monkeypatch.setattr(ds, "_get_db", lambda: conn)
    monkeypatch.setattr(ds, "get_dungeon", lambda key: {"cooldown_hours": 0})

    result = ds.check_cooldown(1, "krypta_probna")
    assert result["on_cooldown"] is False
    assert result["run_count"] == 3


def test_check_cooldown_still_blocks_when_live_cooldown_nonzero(monkeypatch):
    """Backward compat: a live non-zero cooldown still blocks a future timer."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE character_dungeon_runs "
        "(character_id INT, location_key TEXT, cooldown_until TEXT, run_count INT)"
    )
    future = (datetime.now(timezone.utc) + timedelta(hours=20)).isoformat()
    conn.execute(
        "INSERT INTO character_dungeon_runs VALUES (?, ?, ?, ?)",
        (1, "krypta_probna", future, 3),
    )
    conn.commit()

    monkeypatch.setattr(ds, "_get_db", lambda: conn)
    monkeypatch.setattr(ds, "get_dungeon", lambda key: {"cooldown_hours": 72})

    result = ds.check_cooldown(1, "krypta_probna")
    assert result["on_cooldown"] is True
    assert result["hours_remaining"] > 0
