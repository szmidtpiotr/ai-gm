"""TDD: Issue #1161 — wynik hazardu połknięty gdy brak złota na przegraną.

Cała wypłata hazardu była w szerokim `except Exception` → gdy change_gold rzucał
ValueError("gold_gp would be negative") przy przegranej bez pokrycia, cały wynik
(narracja, outcome) cicho ginął (return None). Fix: niedobór złota = zdefiniowany
wynik — przegrana ograniczona do salda, summary zwrócone.
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.turn import turn_gambling


def _db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        "CREATE TABLE characters (id INTEGER PRIMARY KEY, gold_gp INTEGER DEFAULT 0, campaign_id INTEGER);"
    )
    return conn


def _gold(conn, cid=1):
    return int(conn.execute("SELECT gold_gp FROM characters WHERE id=?", (cid,)).fetchone()[0])


def _run(conn, monkeypatch, *, delta, stake=100, cheat=False):
    """Patchuje gamble_service + world_service, uruchamia funkcję z zadanym delta."""
    from app.services import gamble_service, world_service
    monkeypatch.setattr(
        gamble_service, "apply_gamble_outcome",
        lambda flags, outcome, st, loc: {"delta": delta, "stake": stake, "cheat_accused": cheat},
    )
    monkeypatch.setattr(world_service, "get_current_location_info", lambda c, cid: {"key": "tawerna"})
    return turn_gambling.apply_gamble_outcome_in_skill_resolution(
        conn=conn, campaign_id=1, character_id=1,
        pending={"skill_key": "gamble", "gamble": {"stake": stake}},
        session_flags={}, result={"outcome": "FAILURE"},
    )


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_loss_bigger_than_balance_is_capped_not_swallowed(monkeypatch):
    """Saldo 5, przegrana 100 → wynik NIE ginie; traci 5, saldo 0, delta = -5."""
    conn = _db()
    conn.execute("INSERT INTO characters (id, gold_gp, campaign_id) VALUES (1, 5, 1)")
    conn.commit()

    summary = _run(conn, monkeypatch, delta=-100, stake=100)

    assert summary is not None, "wynik hazardu połknięty (#1161)"
    assert _gold(conn) == 0, "powinien przegrać całe saldo (5), nie zostać przy 5"
    assert summary["delta"] == -5, "delta w summary powinna być ograniczona do salda"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_win_still_credits(monkeypatch):
    conn = _db()
    conn.execute("INSERT INTO characters (id, gold_gp, campaign_id) VALUES (1, 5, 1)")
    conn.commit()
    summary = _run(conn, monkeypatch, delta=50, stake=100)
    assert summary is not None
    assert _gold(conn) == 55
    assert summary["delta"] == 50


def test_loss_within_balance_unchanged(monkeypatch):
    conn = _db()
    conn.execute("INSERT INTO characters (id, gold_gp, campaign_id) VALUES (1, 20, 1)")
    conn.commit()
    summary = _run(conn, monkeypatch, delta=-8, stake=10)
    assert summary is not None
    assert _gold(conn) == 12
    assert summary["delta"] == -8


def test_non_gamble_returns_none(monkeypatch):
    conn = _db()
    out = turn_gambling.apply_gamble_outcome_in_skill_resolution(
        conn=conn, campaign_id=1, character_id=1,
        pending={"skill_key": "persuasion"},
        session_flags={}, result={"outcome": "SUCCESS"},
    )
    assert out is None
