"""TDD: Issue #1165 — brak indeksu na campaign_turns.campaign_id (najgorętsza tabela).

`campaign_turns` jest pisana i czytana co turę (57 zapytań `WHERE campaign_id`,
m.in. turns.py:467 last-3-turns oraz turns.py:1693/3112 `MAX(turn_number)`), ale
nie ma żadnego indeksu → każde zapytanie robi pełny skan tabeli. `combat_turns`
i `game_events` mają swoje indeksy — ta tabela została pominięta.

Fix: dodać do ADMIN_MIGRATIONS idempotentne (IF NOT EXISTS) indeksy —
  * idx_campaign_turns_campaign_id (campaign_id)           — last-3-turns / WHERE campaign_id
  * idx_campaign_turns_campaign_turn (campaign_id, turn_number) — MAX(turn_number) staje się pokryty

Wzorzec identyczny jak combat_turns (migrations_admin.py:603-609): czysty DDL
IF NOT EXISTS w liście ADMIN_MIGRATIONS — naturalnie idempotentny, więc nie
wymaga tabeli schema_migrations z #1162 (ta chroni tylko non-DDL UPDATE/INSERT).
"""
import sqlite3

import pytest

import app.migrations_admin as adm


def _campaign_turns_index_ddls():
    """Instrukcje CREATE INDEX z ADMIN_MIGRATIONS dotyczące campaign_turns."""
    out = []
    for sql in adm.ADMIN_MIGRATIONS:
        if not isinstance(sql, str):
            continue
        low = sql.lower()
        if "create index" in low and "campaign_turns" in low:
            out.append(sql)
    return out


@pytest.fixture()
def turns_db():
    """Świeża baza z samą tabelą campaign_turns + zaaplikowanymi indeksami z migracji."""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE campaign_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            character_id INTEGER,
            user_text TEXT NOT NULL,
            route TEXT NOT NULL DEFAULT 'narrative',
            assistant_text TEXT,
            turn_number INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    for ddl in _campaign_turns_index_ddls():
        conn.execute(ddl)
    conn.commit()
    yield conn
    conn.close()


def _index_names(conn):
    return {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='campaign_turns'"
        ).fetchall()
    }


# ─── Test główny — indeks istnieje po migracji ───────────────────────────────

def test_campaign_id_index_present_after_migration(turns_db):
    """Migracja tworzy idx_campaign_turns_campaign_id na campaign_turns(campaign_id)."""
    names = _index_names(turns_db)
    assert "idx_campaign_turns_campaign_id" in names, (
        f"brak indeksu idx_campaign_turns_campaign_id — jest: {sorted(names)}"
    )


def test_last_three_turns_query_uses_index(turns_db):
    """EXPLAIN QUERY PLAN zapytania z turns.py:467 używa indeksu, nie pełnego skanu."""
    plan = turns_db.execute(
        "EXPLAIN QUERY PLAN "
        "SELECT assistant_text FROM campaign_turns "
        "WHERE campaign_id = ? ORDER BY id DESC LIMIT 3",
        (1,),
    ).fetchall()
    detail = " ".join(str(row[-1]) for row in plan)
    assert "idx_campaign_turns_campaign" in detail, (
        f"zapytanie last-3-turns nie używa indeksu campaign_turns — plan: {detail}"
    )
    assert "SCAN campaign_turns" not in detail or "USING INDEX" in detail, (
        f"pełny skan tabeli campaign_turns — plan: {detail}"
    )


def test_max_turn_number_query_uses_index(turns_db):
    """MAX(turn_number) WHERE campaign_id (turns.py:1693/3112) korzysta z indeksu."""
    plan = turns_db.execute(
        "EXPLAIN QUERY PLAN "
        "SELECT COALESCE(MAX(turn_number),0)+1 FROM campaign_turns WHERE campaign_id=?",
        (1,),
    ).fetchall()
    detail = " ".join(str(row[-1]) for row in plan)
    assert "idx_campaign_turns_campaign" in detail, (
        f"zapytanie MAX(turn_number) nie używa indeksu — plan: {detail}"
    )


# ─── Backward compatibility — indeks jest idempotentny ───────────────────────

def test_index_ddl_is_idempotent(turns_db):
    """Ponowne wykonanie DDL indeksu nie rzuca błędem (IF NOT EXISTS)."""
    for ddl in _campaign_turns_index_ddls():
        turns_db.execute(ddl)  # drugie wykonanie — nie może rzucić
    turns_db.commit()
    assert "idx_campaign_turns_campaign_id" in _index_names(turns_db)


def test_migration_defines_at_least_one_campaign_turns_index():
    """ADMIN_MIGRATIONS zawiera przynajmniej jeden indeks campaign_turns."""
    ddls = _campaign_turns_index_ddls()
    assert ddls, "ADMIN_MIGRATIONS nie zawiera żadnego CREATE INDEX na campaign_turns"
