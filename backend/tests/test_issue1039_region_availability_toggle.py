"""TDD: Issue #1039 — admin przełącza dostępność krainy (coming↔live) + blokada dla gracza.

Dwa poziomy:
  A) ``set_region_status`` — flip statusu krainy zapisuje DB jako trwały
     ``status_override``. Pliki kanonu (``data/regions/region_<key>.json``) są
     git-committed i zamontowane read-only, więc migracja startowa
     ``_align_region_status_to_files`` musi respektować override — inaczej
     restart cofałby decyzję admina.
  B) ``region_block_for_hex`` — blokada travel do krainy coming/locked zwraca
     ustrukturyzowany payload (``error_code``, ``region``, ``region_label``),
     żeby ŻAR mógł pokazać dedykowany modal zamiast milczącego no-opa.

Uruchom w kontenerze:
    docker exec ai-gm-dev-backend-1 pytest tests/test_issue1039_region_availability_toggle.py -v
"""
import json
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, "/app")

from app.services import world_region_service as wrs  # noqa: E402


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _mem_db() -> sqlite3.Connection:
    """Fikcyjna baza z samą tabelą world_regions — NIE dotyka realnej mapy świata."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE world_regions (
            key        TEXT PRIMARY KEY,
            label      TEXT NOT NULL,
            color      TEXT NOT NULL DEFAULT '#888888',
            status     TEXT NOT NULL DEFAULT 'coming'
                       CHECK(status IN ('live', 'coming', 'locked')),
            status_override TEXT DEFAULT NULL,
            entry_q    INTEGER,
            entry_r    INTEGER,
            sort_order INTEGER NOT NULL DEFAULT 0,
            note       TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE world_hexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            q INTEGER, r INTEGER, map_level INTEGER DEFAULT 0,
            hex_type TEXT, label TEXT, region TEXT,
            parent_hex_id INTEGER, is_active INTEGER DEFAULT 1
        )
    """)
    conn.executemany(
        "INSERT INTO world_regions(key,label,status,sort_order) VALUES (?,?,?,?)",
        [("kresy", "Kresy", "live", 1), ("czarnobor", "Czarnobór", "coming", 3)],
    )
    conn.executemany(
        "INSERT INTO world_hexes(q,r,map_level,hex_type,label,region,is_active)"
        " VALUES (?,?,0,?,?,?,1)",
        [(1, 1, "plains", "Polana", "kresy"), (60, 5, "forest", "Bór", "czarnobor")],
    )
    conn.commit()
    return conn


@pytest.fixture()
def conn():
    c = _mem_db()
    yield c
    c.close()


@pytest.fixture()
def regions_dir(tmp_path):
    d = tmp_path / "regions"
    d.mkdir()
    (d / "region_czarnobor.json").write_text(json.dumps({
        "region": "czarnobor", "label": "Czarnobór", "status": "coming",
        "hexes": [{"q": 60, "r": 5, "hex_type": "forest"}],
    }, ensure_ascii=False), encoding="utf-8")
    return str(d)


# ── A) Admin toggle statusu krainy ───────────────────────────────────────────

def test_set_status_flips_db(conn):
    """coming → live zmienia wiersz w world_regions."""
    out = wrs.set_region_status(conn, "czarnobor", "live")
    assert out["status"] == "live" and out["previous_status"] == "coming"
    row = conn.execute("SELECT status FROM world_regions WHERE key='czarnobor'").fetchone()
    assert row["status"] == "live"


def test_set_status_records_override(conn):
    """Decyzja admina zapisuje się jako override — to ona chroni ją przed migracją."""
    wrs.set_region_status(conn, "czarnobor", "live")
    row = conn.execute(
        "SELECT status_override FROM world_regions WHERE key='czarnobor'").fetchone()
    assert row["status_override"] == "live"


def test_set_status_survives_boot_migration(conn, regions_dir):
    """Migracja startowa wyrównuje DB do plików — override admina ma przetrwać restart."""
    from app.migrations_admin import _align_region_status_to_files
    wrs.set_region_status(conn, "czarnobor", "live")
    _align_region_status_to_files(conn, regions_dir=regions_dir)  # plik nadal mówi 'coming'
    row = conn.execute("SELECT status FROM world_regions WHERE key='czarnobor'").fetchone()
    assert row["status"] == "live", "restart cofnął decyzję admina do kanonu pliku"


def test_align_still_applies_without_override(conn, regions_dir):
    """Backward compat R1 (#1241): kraina bez override'u nadal podąża za plikiem."""
    from app.migrations_admin import _align_region_status_to_files
    conn.execute("UPDATE world_regions SET status='live' WHERE key='czarnobor'")
    conn.commit()
    _align_region_status_to_files(conn, regions_dir=regions_dir)  # plik: 'coming'
    row = conn.execute("SELECT status FROM world_regions WHERE key='czarnobor'").fetchone()
    assert row["status"] == "coming"


def test_reset_status_drops_override(conn, regions_dir):
    """Reset zdejmuje override → kanon pliku znów rządzi."""
    from app.migrations_admin import _align_region_status_to_files
    wrs.set_region_status(conn, "czarnobor", "live")
    out = wrs.reset_region_status(conn, "czarnobor")
    assert out["overridden"] is False
    _align_region_status_to_files(conn, regions_dir=regions_dir)
    row = conn.execute("SELECT status FROM world_regions WHERE key='czarnobor'").fetchone()
    assert row["status"] == "coming"


def test_set_status_round_trip_back_to_coming(conn):
    """live → coming (ukryj graczom) też działa."""
    wrs.set_region_status(conn, "czarnobor", "live")
    wrs.set_region_status(conn, "czarnobor", "coming")
    row = conn.execute(
        "SELECT status, status_override FROM world_regions WHERE key='czarnobor'").fetchone()
    assert row["status"] == "coming" and row["status_override"] == "coming"


def test_set_status_rejects_invalid_value(conn):
    with pytest.raises(ValueError):
        wrs.set_region_status(conn, "czarnobor", "enabled")


def test_set_status_unknown_region(conn):
    with pytest.raises(LookupError):
        wrs.set_region_status(conn, "atlantyda", "live")


def test_list_region_rows_includes_non_live(conn):
    """Admin preview: lista zwraca wszystkie krainy, nie tylko live."""
    rows = wrs.list_region_rows(conn)
    statuses = {r["key"]: r["status"] for r in rows}
    assert statuses == {"kresy": "live", "czarnobor": "coming"}


def test_admin_route_registered():
    """PATCH /api/admin/regions/{key}/status jest zarejestrowany w routerze admina."""
    from app.routers.admin import router
    paths = {getattr(r, "path", "") for r in router.routes}
    target = "/admin/regions/{key}/status"
    assert target in paths, f"brak trasy {target}; jest: {sorted(p for p in paths if 'region' in p)}"
    route = next(r for r in router.routes if getattr(r, "path", "") == target)
    assert "PATCH" in route.methods


# ── B) Blokada gracza — payload pod modal ────────────────────────────────────

def test_region_block_for_coming_region(conn):
    """Heks w krainie 'coming' → ustrukturyzowana blokada z error_code."""
    block = wrs.region_block_for_hex(conn, 60, 5)
    assert block is not None, "wejście do krainy 'coming' musi być zablokowane"
    assert block["error_code"] == "region_locked"
    assert block["region"] == "czarnobor"
    assert block["region_label"] == "Czarnobór"
    assert block["region_status"] == "coming"


def test_region_block_message_unchanged(conn):
    """Backward compat: treść komunikatu bez zmian (#1039 dokłada pola, nie zmienia tekstu)."""
    block = wrs.region_block_for_hex(conn, 60, 5)
    assert block["error"] == "Kraina niedostępna — Czarnobór jest za zamkniętą granicą."


def test_region_block_for_locked_region(conn):
    conn.execute("UPDATE world_regions SET status='locked' WHERE key='czarnobor'")
    conn.commit()
    block = wrs.region_block_for_hex(conn, 60, 5)
    assert block is not None and block["region_status"] == "locked"


def test_no_block_for_live_region(conn):
    """Backward compat: kraina 'live' jest przechodnia — brak blokady."""
    assert wrs.region_block_for_hex(conn, 1, 1) is None


def test_no_block_after_admin_flips_to_live(conn):
    """Acceptance: flip statusu natychmiast przestaje gatować graczy."""
    assert wrs.region_block_for_hex(conn, 60, 5) is not None
    wrs.set_region_status(conn, "czarnobor", "live")
    assert wrs.region_block_for_hex(conn, 60, 5) is None


def test_block_returns_after_admin_hides_region(conn):
    """Acceptance (odwrotnie): ukrycie krainy natychmiast zamyka ją graczom."""
    wrs.set_region_status(conn, "kresy", "coming")
    block = wrs.region_block_for_hex(conn, 1, 1)
    assert block is not None and block["region"] == "kresy"


def test_no_block_for_unknown_hex(conn):
    """Heks spoza mapy → nie jest blokadą krainy (inne komunikaty travel go obsłużą)."""
    assert wrs.region_block_for_hex(conn, 999, 999) is None


def test_hex_travel_service_uses_shared_block_helper():
    """hex_travel_service nie ma już własnej kopii zapytania blokady."""
    import inspect
    from app.services import hex_travel_service as hts
    src = inspect.getsource(hts)
    assert "region_block_for_hex" in src, "hex_travel_service nie używa wspólnego helpera"
    assert "jest za zamkniętą granicą" not in src, "duplikat komunikatu blokady został w hex_travel_service"
