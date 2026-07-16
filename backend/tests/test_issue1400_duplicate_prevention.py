"""TDD: Issue #1400 — prewencja duplikatów przy tworzeniu treści przez LLM/mechanikę.

Acceptance:
- resolve_new_label(conn, table, label, source) — exact po normalizacji → ('reuse', klucz
  istniejącego) + wpis w logu prewencji; fuzzy → ('create_flagged', similar_to);
  różne → ('create')
- reuse pomija klony szablonów (template_id), ukryte, nieaktywne i kampanijne rekordy
- log_flagged_creation → detektor (scan_duplicates) oznacza grupę flagged=True i sortuje
  ją przed innymi fuzzy
- get_prevention_stats — licznik uniknięć widoczny dla admina
- Kuźnia (_promote_hook_to_db) z hookiem o istniejącej nazwie NIE tworzy drugiego rekordu
"""
import sys
sys.path.insert(0, "/app")
from _fixtures_schema import table_sql

import sqlite3
import pytest

from app.services.duplicate_service import (
    resolve_new_label,
    log_flagged_creation,
    get_prevention_stats,
    scan_duplicates,
)


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        table_sql("game_config_items")
        + table_sql("game_config_consumables")
        + table_sql("game_config_weapons")
    )
    yield conn
    conn.close()


def _add_item(conn, key, label, **extra):
    cols = {"key": key, "label": label}
    cols.update(extra)
    names = ", ".join(cols)
    ph = ", ".join("?" for _ in cols)
    conn.execute(f"INSERT INTO game_config_items ({names}) VALUES ({ph})", list(cols.values()))


# ─── resolve: exact → reuse ──────────────────────────────────────────────────

def test_resolve_exact_label_reuses_existing(db):
    _add_item(db, "luneta", "Luneta")
    res = resolve_new_label(db, "items", "  luneta ", source="forge_hook")
    assert res["action"] == "reuse"
    assert res["key"] == "luneta"
    stats = get_prevention_stats(db)
    assert stats["reused"] == 1


def test_resolve_distinct_label_creates(db):
    _add_item(db, "luneta", "Luneta")
    res = resolve_new_label(db, "items", "Czaszka demona", source="forge_hook")
    assert res["action"] == "create"
    assert get_prevention_stats(db)["reused"] == 0


def test_resolve_rejects_bad_table(db):
    with pytest.raises(ValueError):
        resolve_new_label(db, "enemies", "X", source="t")


# ─── reuse pomija klony/ukryte/nieaktywne/kampanijne ─────────────────────────

def test_resolve_skips_template_hidden_inactive_campaign(db):
    _add_item(db, "tpl9_luneta", "Luneta", template_id=9)
    _add_item(db, "luneta_hidden", "Luneta", hidden=1)
    _add_item(db, "luneta_off", "Luneta", is_active=0)
    _add_item(db, "luneta_camp", "Luneta", campaign_id=5)
    res = resolve_new_label(db, "items", "Luneta", source="forge_hook")
    assert res["action"] == "create"


# ─── fuzzy → create_flagged + detektor ───────────────────────────────────────

def test_resolve_fuzzy_flags_creation(db):
    _add_item(db, "mikstura", "Mikstura leczenia")
    res = resolve_new_label(db, "items", "Mikstura leczenia II", source="forge_hook")
    assert res["action"] == "create_flagged"
    assert res["similar_to"] == "mikstura"


def test_flagged_creation_marked_in_scan_and_sorted_first(db):
    _add_item(db, "mikstura", "Mikstura leczenia")
    # dwie zwykłe fuzzy grupy + jedna flagowana — flagowana ma być pierwsza wśród fuzzy
    _add_item(db, "topor_a", "Wielki topór bojowy")
    _add_item(db, "topor_b", "Wielki topór bojowy II")
    _add_item(db, "mikstura2", "Mikstura leczenia II")
    log_flagged_creation(db, "items", "mikstura2", "Mikstura leczenia II", "mikstura", source="forge_hook")

    groups = scan_duplicates(db)["tables"]["items"]
    fuzzy = [g for g in groups if g["match"] == "fuzzy"]
    assert len(fuzzy) == 2
    assert fuzzy[0]["flagged"] is True
    assert any(r["key"] == "mikstura2" for r in fuzzy[0]["records"])
    assert fuzzy[1].get("flagged") is False
    assert get_prevention_stats(db)["flagged"] == 1


# ─── Kuźnia: hook o istniejącej nazwie nie tworzy drugiego rekordu ───────────

def test_forge_hook_reuses_existing_item(db):
    from app.routers.adventure_forge import _promote_hook_to_db
    _add_item(db, "zloty_bozek", "Złoty bożek")
    before = db.execute("SELECT COUNT(*) FROM game_config_items").fetchone()[0]

    table, rec_id = _promote_hook_to_db(db, {
        "hook_type": "item",
        "title": "Złoty bożek",
        "description": "Posążek z zapomnianej świątyni",
        "draft_data": {"label": "złoty bożek"},
    })

    assert table == "game_config_items"
    after = db.execute("SELECT COUNT(*) FROM game_config_items").fetchone()[0]
    assert after == before  # nic nie dopisano
    existing_rowid = db.execute(
        "SELECT rowid FROM game_config_items WHERE key = 'zloty_bozek'"
    ).fetchone()[0]
    assert rec_id == existing_rowid
    assert get_prevention_stats(db)["reused"] == 1


def test_forge_hook_new_label_still_creates(db):
    """Backward compat: nowa nazwa → rekord powstaje jak dotychczas."""
    from app.routers.adventure_forge import _promote_hook_to_db
    table, rec_id = _promote_hook_to_db(db, {
        "hook_type": "item",
        "title": "Roztrzaskany kompas",
        "description": "Wskazuje tylko na burze",
        "draft_data": {"label": "Roztrzaskany kompas"},
    })
    assert table == "game_config_items"
    row = db.execute("SELECT label FROM game_config_items WHERE rowid = ?", (rec_id,)).fetchone()
    assert row["label"] == "Roztrzaskany kompas"
