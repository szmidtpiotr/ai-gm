"""TDD: Issue #1294 — seed campaign_known_npcs from gm_plan_json.key_npcs.

Warstwa 1: deterministyczny seed rostera NPC z planu kampanii, niezależny od
opcjonalnych tagów LLM ([NPC_MEMORY] / npc_met). Pokrywa nowa/gotowa/MP przez
idempotentne wywołanie funkcji serwisowej.
"""
import sqlite3
import json
import pytest

from app.services.npc_memory_service import (
    seed_known_npcs_from_plan,
    record_npc_met,
)


def _mkdb() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY,
            gm_plan_json TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE campaign_known_npcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            npc_id INTEGER,
            npc_name TEXT,
            role TEXT,
            first_met_location TEXT,
            first_met_turn INTEGER,
            notes TEXT,
            relation_status TEXT,
            created_at TEXT,
            updated_at TEXT,
            purchase_count INTEGER,
            stats_json TEXT,
            UNIQUE(campaign_id, npc_name)
        )"""
    )
    conn.execute(
        """CREATE TABLE npcs (
            id INTEGER PRIMARY KEY,
            key TEXT,
            label TEXT
        )"""
    )
    return conn


_PLAN = {
    "title": "Żar z Gasnącej Kuźni",
    "key_npcs": [
        {"key": "brunn_zelaznoreki", "name": "Brunn Żelaznoręki",
         "role": "Miejscowy kowal", "importance": "critical", "alive": True},
        {"key": "toma_czeladnik", "name": "Toma",
         "role": "Młody czeladnik", "importance": "supporting", "alive": True},
        {"key": "karczmarz_jorek", "name": "Jorek",
         "role": "Karczmarz", "importance": "supporting", "alive": True},
        {"key": "widmowy_bandyta", "name": "Bezimienny zbir",
         "role": "tło", "importance": "minor", "alive": True},
        {"key": "martwy_baron", "name": "Baron Krwawy",
         "role": "poległy", "importance": "critical", "alive": False},
    ],
}


def _seed_campaign(conn, cid=9998881, plan=None):
    conn.execute(
        "INSERT INTO campaigns (id, gm_plan_json) VALUES (?, ?)",
        (cid, json.dumps(plan if plan is not None else _PLAN)),
    )
    conn.commit()


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_seed_creates_rows_for_critical_and_supporting():
    """key_npcs (critical+supporting) trafiają do campaign_known_npcs."""
    conn = _mkdb()
    _seed_campaign(conn)

    result = seed_known_npcs_from_plan(conn, 9998881)

    names = {
        r["npc_name"]
        for r in conn.execute(
            "SELECT npc_name FROM campaign_known_npcs WHERE campaign_id=?", (9998881,)
        )
    }
    assert "Brunn Żelaznoręki" in names
    assert "Toma" in names
    assert "Jorek" in names
    # zwrócona lista raportuje seed
    assert len(result) >= 3


def test_seed_skips_minor_importance():
    """Postać importance=minor NIE jest seedowana."""
    conn = _mkdb()
    _seed_campaign(conn)
    seed_known_npcs_from_plan(conn, 9998881)
    names = {
        r["npc_name"]
        for r in conn.execute(
            "SELECT npc_name FROM campaign_known_npcs WHERE campaign_id=?", (9998881,)
        )
    }
    assert "Bezimienny zbir" not in names


def test_seed_skips_dead_npc():
    """alive=False nie jest wprowadzany jako znajomy."""
    conn = _mkdb()
    _seed_campaign(conn)
    seed_known_npcs_from_plan(conn, 9998881)
    names = {
        r["npc_name"]
        for r in conn.execute(
            "SELECT npc_name FROM campaign_known_npcs WHERE campaign_id=?", (9998881,)
        )
    }
    assert "Baron Krwawy" not in names


def test_seed_is_idempotent():
    """Dwukrotne wywołanie nie tworzy duplikatów."""
    conn = _mkdb()
    _seed_campaign(conn)
    seed_known_npcs_from_plan(conn, 9998881)
    seed_known_npcs_from_plan(conn, 9998881)
    n = conn.execute(
        "SELECT COUNT(*) FROM campaign_known_npcs WHERE campaign_id=?", (9998881,)
    ).fetchone()[0]
    # 3 kwalifikujące się (critical+supporting, alive) — bez duplikatów
    assert n == 3


def test_seed_links_catalog_npc_id_when_label_matches():
    """npc_id linkowany gdy nazwa istnieje w katalogu npcs."""
    conn = _mkdb()
    _seed_campaign(conn)
    conn.execute(
        "INSERT INTO npcs (id, key, label) VALUES (?, ?, ?)",
        (77, "brunn_zelaznoreki", "Brunn Żelaznoręki"),
    )
    conn.commit()
    seed_known_npcs_from_plan(conn, 9998881)
    row = conn.execute(
        "SELECT npc_id FROM campaign_known_npcs WHERE campaign_id=? AND npc_name=?",
        (9998881, "Brunn Żelaznoręki"),
    ).fetchone()
    assert row["npc_id"] == 77


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_record_npc_met_still_works():
    """Istniejący interfejs record_npc_met działa bez zmian."""
    conn = _mkdb()
    _seed_campaign(conn)
    res = record_npc_met(campaign_id=9998881, name="Ktoś Nowy", conn=conn)
    assert res["ok"] is True
    assert res["new"] is True


def test_seed_no_plan_is_noop():
    """Kampania bez planu / bez key_npcs — brak wyjątku, brak wierszy."""
    conn = _mkdb()
    _seed_campaign(conn, cid=555, plan={"title": "puste"})
    result = seed_known_npcs_from_plan(conn, 555)
    assert result == []
    n = conn.execute(
        "SELECT COUNT(*) FROM campaign_known_npcs WHERE campaign_id=?", (555,)
    ).fetchone()[0]
    assert n == 0
