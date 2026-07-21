"""TDD: Issue #1526 — Fala 3 „jedne drzwi tworzenia lokacji".

Lokacje wchodzily do swiata 14 roznymi sciezkami i kazda stemplowala flagi
po swojemu (jedna wpisywala status recenzji, ktorego panel nie zna → limbo;
inna pisala wspolrzedne heksa wprost w INSERT, omijajac kanonicznego writera
→ reconcile odpinal ja przy starcie).

Fala 3 wprowadza JEDNA funkcje `create_location()` w `location_factory.py`:
  * stempluje komplet flag wg zrodla (`LocationSource`),
  * ZAWSZE ustawia `parent_id` I `parent_key` razem,
  * wiaze z heksem WYLACZNIE przez `link_location_to_hex` (kanon #1243),
  * jest idempotentna po kluczu (koniec „dwoch karczm _2"),
  * odrzuca status recenzji spoza 3 legalnych.

Plus test-guard: nowy bezposredni `INSERT INTO game_locations` w kodzie
runtime = fail testu.

Uruchomienie:
    ./scripts/test_dev.sh tests/test_issue1526_one_door_locations.py -v
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

from app.services import hex_location_link as hll
from app.services.hex_location_link import reconcile_location_hex_links
from app.services.location_factory import LocationSource, create_location


APP_DIR = Path(hll.__file__).resolve().parents[1]          # backend/app/
#: `scripts/` lezy inaczej w repo (repo/scripts) niz w obrazie (/app/scripts —
#: tam jest tylko WYCINEK skryptow, wiec guard skryptowy pomija sie sam, zeby
#: nie dawac falszywej zielonej lampki; pelny przebieg leci na checkoucie repo).
SCRIPTS_DIR = next(
    (
        p / "scripts"
        for p in APP_DIR.parents
        if (p / "scripts" / "seed_locations.py").is_file()
    ),
    None,
)
LEGAL_REVIEW_STATUS = {"permanent", "pending_review", "discarded"}


# ─────────────────────────── fixtures ────────────────────────────────────────

SCHEMA = """
CREATE TABLE game_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    parent_id INTEGER REFERENCES game_locations(id),
    location_type TEXT DEFAULT 'macro' CHECK(location_type IN ('macro','sub')),
    rules TEXT,
    enemy_keys TEXT DEFAULT '[]',
    npc_keys TEXT DEFAULT '[]',
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    approved INTEGER DEFAULT 1,
    created_by TEXT DEFAULT 'admin_manual',
    canonical INTEGER DEFAULT 0,
    source_campaign_id INTEGER,
    map_icon TEXT NOT NULL DEFAULT 'town',
    visible_before_visit INTEGER NOT NULL DEFAULT 0,
    safe_for_rest INTEGER NOT NULL DEFAULT 0,
    review_status TEXT NOT NULL DEFAULT 'permanent',
    parent_key TEXT DEFAULT NULL,
    location_subtype TEXT DEFAULT NULL,
    biome TEXT DEFAULT NULL,
    tier INTEGER NOT NULL DEFAULT 1,
    usage_count INTEGER NOT NULL DEFAULT 0,
    temporary INTEGER NOT NULL DEFAULT 0,
    world_hex_q INTEGER,
    world_hex_r INTEGER,
    terrain_tags TEXT NOT NULL DEFAULT '[]',
    region TEXT,
    enrichment_locked INTEGER NOT NULL DEFAULT 0
);
CREATE TRIGGER trg_review_status_insert
    BEFORE INSERT ON game_locations FOR EACH ROW
    WHEN NEW.review_status NOT IN ('permanent','pending_review','discarded')
    BEGIN SELECT RAISE(ABORT, 'review_status must be one of: permanent, pending_review, discarded'); END;
CREATE TABLE world_hexes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    q INTEGER, r INTEGER, map_level INTEGER DEFAULT 0,
    region TEXT, hex_type TEXT DEFAULT 'las',
    label TEXT, location_key TEXT, is_active INTEGER DEFAULT 1
);
INSERT INTO world_hexes (q, r, map_level, region, hex_type)
     VALUES (5, 5, 0, 'kresy', 'las'), (6, 6, 0, 'kresy', 'las'), (7, 7, 0, 'kresy', 'las');
"""


@pytest.fixture()
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    c.commit()
    return c


def _row(conn: sqlite3.Connection, key: str) -> sqlite3.Row:
    return conn.execute("SELECT * FROM game_locations WHERE key = ?", (key,)).fetchone()


# ─── Test glowny 1: stempel flag wg zrodla ───────────────────────────────────

@pytest.mark.parametrize(
    "source,expected_status",
    [
        (LocationSource.SEED, "permanent"),
        (LocationSource.ADMIN_MANUAL, "permanent"),
        (LocationSource.ADMIN_KREATOR, "permanent"),
        (LocationSource.AUTO_GENERATED, "permanent"),
        (LocationSource.FORGE, "pending_review"),
        (LocationSource.GM_RUNTIME, "pending_review"),
    ],
)
def test_source_stamps_legal_flag_set(conn, source, expected_status):
    """Kazde z 14 wejsc idzie przez jedno zrodlo → legalny komplet flag."""
    res = create_location(conn, key=f"loc_{source.value}", label="Miejsce", source=source)
    row = _row(conn, f"loc_{source.value}")
    assert row["created_by"] == source.value
    assert row["review_status"] == expected_status
    assert row["review_status"] in LEGAL_REVIEW_STATUS
    assert row["is_active"] == 1
    assert res["created"] is True
    assert res["id"] == row["id"]


def test_seed_macro_is_canonical_sub_is_not(conn):
    """Kanon z gita: makro = kanoniczne, sub = nie (tak jak seed_locations.py)."""
    create_location(conn, key="osada", label="Osada", source=LocationSource.SEED)
    create_location(conn, key="osada_karczma", label="Karczma", source=LocationSource.SEED,
                    parent_key="osada")
    assert _row(conn, "osada")["canonical"] == 1
    assert _row(conn, "osada_karczma")["canonical"] == 0


def test_illegal_review_status_rejected_before_insert(conn):
    """Sciezka 12 wpisywala `approved` — status, ktorego panel nie zna (limbo)."""
    with pytest.raises(ValueError):
        create_location(conn, key="limbo", label="Limbo",
                        source=LocationSource.GM_RUNTIME, review_status="approved")
    assert _row(conn, "limbo") is None


def test_unknown_source_rejected(conn):
    with pytest.raises(ValueError):
        create_location(conn, key="x", label="X", source="jakies_zrodlo")


# ─── Test glowny 2: parent_id I parent_key zawsze razem ──────────────────────

def test_sub_by_parent_key_gets_parent_id_too(conn):
    create_location(conn, key="hub", label="Hub", source=LocationSource.SEED)
    create_location(conn, key="hub_kuznia", label="Kuznia", source=LocationSource.AUTO_GENERATED,
                    parent_key="hub")
    row = _row(conn, "hub_kuznia")
    assert row["parent_key"] == "hub"
    assert row["parent_id"] == _row(conn, "hub")["id"]
    assert row["location_type"] == "sub"


def test_sub_by_parent_id_gets_parent_key_too(conn):
    hub = create_location(conn, key="hub2", label="Hub2", source=LocationSource.SEED)
    create_location(conn, key="hub2_targ", label="Targ", source=LocationSource.FORGE,
                    parent_id=hub["id"])
    row = _row(conn, "hub2_targ")
    assert row["parent_id"] == hub["id"]
    assert row["parent_key"] == "hub2"


# ─── Test glowny 3: heks tylko przez kanonicznego writera ────────────────────

def test_hex_binding_writes_canon_and_survives_reconcile(conn):
    """Sciezka 10 pisala world_hex_q/r wprost w INSERT → reconcile ja odpinal (#1305)."""
    create_location(conn, key="grod", label="Grod", source=LocationSource.AUTO_GENERATED,
                    hex_q=5, hex_r=5)
    hexrow = conn.execute(
        "SELECT location_key FROM world_hexes WHERE q=5 AND r=5 AND map_level=0"
    ).fetchone()
    assert hexrow["location_key"] == "grod", "kanon (world_hexes) musi wskazywac lokacje"
    assert (_row(conn, "grod")["world_hex_q"], _row(conn, "grod")["world_hex_r"]) == (5, 5)

    report = reconcile_location_hex_links(conn)
    assert report["cleared"] == [], "reconcile nie moze odpinac lokacji z jednych drzwi"
    assert _row(conn, "grod")["world_hex_q"] == 5


def test_no_hex_means_no_coordinates(conn):
    create_location(conn, key="floating", label="Floating", source=LocationSource.FORGE)
    row = _row(conn, "floating")
    assert row["world_hex_q"] is None and row["world_hex_r"] is None


# ─── Test glowny 4: idempotencja po kluczu ───────────────────────────────────

def test_second_call_with_same_key_is_noop(conn):
    a = create_location(conn, key="karczma", label="Karczma", source=LocationSource.FORGE)
    b = create_location(conn, key="karczma", label="Karczma", source=LocationSource.FORGE)
    assert a["created"] is True and b["created"] is False
    assert a["id"] == b["id"]
    assert conn.execute(
        "SELECT COUNT(*) c FROM game_locations WHERE key = 'karczma'"
    ).fetchone()["c"] == 1


def test_unique_key_opt_in_suffixes_instead_of_colliding(conn):
    create_location(conn, key="karczma", label="Karczma", source=LocationSource.AUTO_GENERATED)
    second = create_location(conn, key="karczma", label="Karczma", source=LocationSource.AUTO_GENERATED,
                             unique_key=True)
    assert second["key"] == "karczma_2" and second["created"] is True


# ─── Test-guard: jedne drzwi, nie czternascioro ──────────────────────────────

_INSERT_RE = re.compile(r"INSERT\s+(?:OR\s+\w+\s+)?INTO\s+game_locations", re.IGNORECASE)

#: Wolno pisac bezposrednio tylko tutaj (kanoniczne drzwi + przebudowy schematu
#: w migracjach, ktore kopiuja gotowe, juz ostemplowane wiersze).
_ALLOWED = {"services/location_factory.py", "migrations_admin.py"}


def test_no_direct_insert_into_game_locations_outside_factory():
    offenders = []
    for path in APP_DIR.rglob("*.py"):
        rel = str(path.relative_to(APP_DIR))
        if any(rel.endswith(a) for a in _ALLOWED):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for m in _INSERT_RE.finditer(text):
            line = text[: m.start()].count("\n") + 1
            offenders.append(f"{rel}:{line}")
    assert offenders == [], (
        "Bezposredni INSERT INTO game_locations poza location_factory.create_location "
        f"(#1526 — jedne drzwi): {offenders}"
    )


#: Skrypty, ktore ODTWARZAJA gotowe, juz ostemplowane wiersze (a nie tworza
#: nowej lokacji): reseed kanonu z gita i generator SQL-a naprawczego.
_ALLOWED_SCRIPTS = {"seed_content.py", "content_seed_lib.py", "cleanup_test_data.py"}


def test_seed_scripts_also_use_the_single_door():
    if SCRIPTS_DIR is None:
        pytest.skip("katalog scripts/ niedostepny w tym srodowisku")
    offenders = []
    for path in sorted(SCRIPTS_DIR.glob("*.py")):
        if path.name in _ALLOWED_SCRIPTS:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for m in _INSERT_RE.finditer(text):
            offenders.append(f"scripts/{path.name}:{text[: m.start()].count(chr(10)) + 1}")
    assert offenders == [], (
        f"Skrypt seedujacy omija jedne drzwi (#1526): {offenders}"
    )


# ─── Backward compatibility: istniejace sciezki nadal dzialaja ───────────────

def test_gm_tag_path_still_creates_pending_location(conn):
    """Sciezka 7 (znacznik GM) po przepieciu nadal tworzy karte w poczekalni."""
    from app.services.world_service import _get_or_create_location

    out = _get_or_create_location(
        conn, "stara_kuznia",
        {"label": "Stara Kuznia", "type": "sub", "description": "Zimne palenisko."},
        campaign_id=42,
    )
    assert out and out["review_status"] == "pending_review"
    row = _row(conn, "stara_kuznia")
    assert row["created_by"] == "gm_runtime" and row["source_campaign_id"] == 42


def test_settlement_sublocs_path_still_creates_children(conn):
    """Sciezka 11 (sub-lokacje osady) — parent_id + parent_key komplet."""
    from app.services.world_service import generate_sublocs_for_settlement

    create_location(conn, key="wioska", label="Wioska", source=LocationSource.AUTO_GENERATED)
    created = generate_sublocs_for_settlement(conn, "wioska", ["tavern", "smithy"])
    assert len(created) == 2
    for c in created:
        row = _row(conn, c["key"])
        assert row["parent_key"] == "wioska"
        assert row["parent_id"] == _row(conn, "wioska")["id"]
        assert row["review_status"] == "permanent"
        assert row["created_by"] == "auto_generated"
