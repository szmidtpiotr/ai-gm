"""TDD: Issue #754 — strukturalny rejestr rzutów kostką (dice_rolls)."""
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import migrations_admin
from app.services import dice_log_service as dls


@pytest.fixture()
def tmp_db(monkeypatch):
    """Świeża baza z tabelą dice_rolls (przez prawdziwą migrację v2)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.row_factory = sqlite3.Row
    # Tabela campaigns potrzebna do testu kasowania kampanii.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS campaigns (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)"
    )
    conn.commit()
    # Uruchom realną migrację — to ona musi stworzyć dice_rolls.
    migrations_admin._ensure_dice_rolls_table(conn)
    conn.commit()
    conn.close()
    monkeypatch.setattr(dls, "DICE_LOG_DB_PATH", tmp.name)
    yield tmp.name
    Path(tmp.name).unlink(missing_ok=True)


# ─── Test główny — migracja tworzy tabelę o oczekiwanym schemacie ──────────────

def test_migration_creates_dice_rolls_table(tmp_db):
    """Migracja v2 tworzy dice_rolls z kompletem kolumn z issue #754."""
    conn = sqlite3.connect(tmp_db)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(dice_rolls)").fetchall()}
    conn.close()
    expected = {
        "id", "campaign_id", "character_id", "turn_number", "combat_id",
        "roll_type", "actor", "notation", "raw_rolls", "modifiers",
        "total", "dc", "outcome", "meta", "created_at",
    }
    assert expected.issubset(cols), f"brakuje kolumn: {expected - cols}"


# ─── Test główny — zapis + odczyt strukturalny ─────────────────────────────────

def test_record_and_query_roundtrip(tmp_db):
    """record_dice_roll zapisuje rzut; query_dice_rolls zwraca go z rozparsowanym JSON."""
    rid = dls.record_dice_roll(
        campaign_id=4242,
        roll_type="skill_test",
        character_id=7,
        turn_number=3.0,
        actor="player",
        notation="1d20",
        raw_rolls=[14],
        modifiers={"stat_mod": 3, "skill_rank": 2, "proficiency": 0},
        total=19,
        dc=12,
        outcome="success",
        meta={"skill_key": "perception"},
    )
    assert rid is not None and rid > 0

    rolls = dls.query_dice_rolls(4242)
    assert len(rolls) == 1
    r = rolls[0]
    assert r["roll_type"] == "skill_test"
    assert r["raw_rolls"] == [14]                       # JSON rozparsowany do listy
    assert r["modifiers"]["skill_rank"] == 2            # JSON rozparsowany do dict
    assert r["total"] == 19 and r["dc"] == 12
    assert r["outcome"] == "success"
    assert r["meta"]["skill_key"] == "perception"


def test_query_filters_by_type_and_turn(tmp_db):
    """Filtr roll_type i zakres tur działają."""
    for t, rt in [(1.0, "attack_player"), (2.0, "dodge"), (3.0, "attack_player")]:
        dls.record_dice_roll(campaign_id=1, roll_type=rt, turn_number=t, total=10)
    assert len(dls.query_dice_rolls(1, roll_type="attack_player")) == 2
    assert len(dls.query_dice_rolls(1, from_turn=2.0)) == 2
    assert len(dls.query_dice_rolls(1, from_turn=2.0, to_turn=2.0)) == 1


# ─── Test główny — rzuty przeżywają wyjście z lochu (DELETE kampanii) ───────────

def test_rolls_survive_campaign_delete(tmp_db):
    """Brak FK CASCADE: po DELETE kampanii rzuty nadal istnieją (loch nie gubi danych)."""
    conn = sqlite3.connect(tmp_db)
    conn.execute("PRAGMA foreign_keys = ON")
    cid = conn.execute("INSERT INTO campaigns (name) VALUES ('loch')").lastrowid
    conn.commit()
    conn.close()

    dls.record_dice_roll(campaign_id=cid, roll_type="attack_enemy", total=15)

    conn = sqlite3.connect(tmp_db)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("DELETE FROM campaigns WHERE id = ?", (cid,))
    conn.commit()
    conn.close()

    rolls = dls.query_dice_rolls(cid)
    assert len(rolls) == 1, "rzut zniknął po usunięciu kampanii (CASCADE) — regresja #754"


# ─── Backward compatibility — błąd logowania nie wywraca rozgrywki ─────────────

def test_record_never_raises_on_bad_db(monkeypatch):
    """record_dice_roll zwraca None (nie rzuca) gdy baza niedostępna — gra gra dalej."""
    monkeypatch.setattr(dls, "DICE_LOG_DB_PATH", "/nonexistent/dir/nope.db")
    result = dls.record_dice_roll(campaign_id=1, roll_type="damage", total=5)
    assert result is None
