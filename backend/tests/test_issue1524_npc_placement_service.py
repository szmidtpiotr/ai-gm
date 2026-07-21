"""TDD: Issue #1524 — jedno zrodlo prawdy o obsadzie lokacji (`npc_placement_service`).

Fala 1 "Sprzatania lokacji". Silnik ma czytac WYLACZNIE `location_npc_assignments`;
`npc_keys` w `game_locations` jest kopia pochodna odswiezana po kazdym zapisie,
a legacy `npc_locations` przestaje byc czytany (kasacja po weryfikacji na DEV).

Uruchomienie w kontenerze backendu:
    docker exec ai-gm-dev-backend-1 pytest tests/test_issue1524_npc_placement_service.py -v
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

from app.services import npc_placement_service as nps


APP_DIR = Path(nps.__file__).resolve().parents[1]  # app/


@pytest.fixture()
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE game_locations (
            key TEXT PRIMARY KEY,
            label TEXT,
            location_type TEXT,
            parent_key TEXT,
            npc_keys TEXT DEFAULT '[]',
            tier INTEGER DEFAULT 1,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE npcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE,
            label TEXT,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE location_npc_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_key TEXT NOT NULL,
            npc_key TEXT NOT NULL,
            assignment_type TEXT DEFAULT 'resident',
            notes TEXT,
            is_active INTEGER DEFAULT 1,
            UNIQUE(location_key, npc_key)
        );
        CREATE TABLE npc_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            npc_id INTEGER NOT NULL,
            location_key TEXT NOT NULL,
            UNIQUE(npc_id, location_key)
        );
        INSERT INTO game_locations (key, label, location_type, parent_key, npc_keys, tier)
        VALUES ('karczma', 'Karczma', 'macro', NULL, '[]', 2),
               ('karczma_izba', 'Izba', 'sub', 'karczma', '[]', 2),
               ('kuznia', 'Kuznia', 'sub', 'karczma', '[]', 3);
        INSERT INTO npcs (id, key, label) VALUES (1, 'karczmarz', 'Karczmarz'), (2, 'kowal', 'Kowal');
        """
    )
    c.commit()
    return c


# ─── Test glowny: assignments = jedyne zrodlo prawdy ─────────────────────────

def test_odczyt_obsady_lokacji_z_przypisan(conn):
    conn.execute(
        "INSERT INTO location_npc_assignments (location_key, npc_key) VALUES ('karczma_izba','karczmarz')"
    )
    assert nps.npc_keys_for_location(conn, "karczma_izba") == ["karczmarz"]


def test_nieaktywne_przypisanie_nie_liczy_sie(conn):
    conn.execute(
        "INSERT INTO location_npc_assignments (location_key, npc_key, is_active) "
        "VALUES ('karczma_izba','karczmarz',0)"
    )
    assert nps.npc_keys_for_location(conn, "karczma_izba") == []


def test_legacy_npc_locations_nie_jest_czytany(conn):
    """Wiersz TYLKO w legacy nie moze wplynac na wynik — inaczej mamy dwa zrodla prawdy."""
    conn.execute("INSERT INTO npc_locations (npc_id, location_key) VALUES (1, 'karczma_izba')")
    conn.commit()
    assert nps.npc_keys_for_location(conn, "karczma_izba") == []
    assert nps.locations_for_npc_id(conn, 1) == []


def test_zapis_obsady_npc_tworzy_przypisania_i_lustro(conn):
    nps.set_locations_for_npc_id(conn, 1, ["karczma_izba"])
    rows = conn.execute(
        "SELECT location_key, is_active FROM location_npc_assignments WHERE npc_key='karczmarz'"
    ).fetchall()
    assert [(r["location_key"], r["is_active"]) for r in rows] == [("karczma_izba", 1)]
    mirror = conn.execute("SELECT npc_keys FROM game_locations WHERE key='karczma_izba'").fetchone()[0]
    assert mirror == '["karczmarz"]'
    # legacy nie jest dotykany zapisem
    assert conn.execute("SELECT COUNT(*) FROM npc_locations").fetchone()[0] == 0


def test_usuniecie_obsady_czysci_lustro(conn):
    nps.set_locations_for_npc_id(conn, 1, ["karczma_izba"])
    nps.set_locations_for_npc_id(conn, 1, [])
    assert nps.npc_keys_for_location(conn, "karczma_izba") == []
    mirror = conn.execute("SELECT npc_keys FROM game_locations WHERE key='karczma_izba'").fetchone()[0]
    assert mirror == "[]"


def test_resync_naprawia_recznie_zepsute_lustro(conn):
    conn.execute(
        "INSERT INTO location_npc_assignments (location_key, npc_key) VALUES ('kuznia','kowal')"
    )
    conn.execute("UPDATE game_locations SET npc_keys='[\"duch\"]' WHERE key='kuznia'")
    changed = nps.resync_npc_keys_mirror(conn)
    assert changed >= 1
    assert nps.npc_keys_for_location(conn, "kuznia") == ["kowal"]
    assert conn.execute("SELECT npc_keys FROM game_locations WHERE key='kuznia'").fetchone()[0] == '["kowal"]'


def test_lokacje_npc_po_kluczu_i_po_id(conn):
    nps.assign_npc(conn, "kuznia", "kowal")
    assert nps.locations_for_npc_key(conn, "kowal") == ["kuznia"]
    assert nps.locations_for_npc_id(conn, 2) == ["kuznia"]


def test_tier_lokacji_npc_liczony_z_przypisan(conn):
    nps.assign_npc(conn, "kuznia", "kowal")
    assert nps.max_tier_for_npc_key(conn, "kowal") == 3
    assert nps.max_tier_for_npc_key(conn, "karczmarz") == 1  # brak przypisan → domyslny tier


def test_npc_at_location_globalny_gdy_brak_przypisan(conn):
    """NPC bez zadnego przypisania jest 'wszedzie' — zachowanie sprzed fixa."""
    assert nps.npc_is_at_location(conn, "kowal", "karczma_izba") is True
    nps.assign_npc(conn, "kuznia", "kowal")
    assert nps.npc_is_at_location(conn, "kowal", "karczma_izba") is False
    assert nps.npc_is_at_location(conn, "kowal", "kuznia") is True


def test_odmowa_przypisania_do_makro_z_sublokacjami(conn):
    """Decyzja 2 (#1524): gospodarz siedzi w subie, makro-hub zostaje puste."""
    with pytest.raises(ValueError):
        nps.assign_npc(conn, "karczma", "karczmarz")


# ─── Invariant kodu: nikt poza migracja nie czyta legacy ─────────────────────

def test_zaden_serwis_ani_router_nie_czyta_npc_locations():
    hits = []
    for path in APP_DIR.rglob("*.py"):
        rel = path.relative_to(APP_DIR).as_posix()
        if rel in {"migrations_admin.py"}:
            continue  # migracja backfilluje i czysci legacy — jedyny dozwolony dostep
        text = path.read_text(encoding="utf-8", errors="ignore")
        # Liczy sie SQL, nie wzmianka w komentarzu ani nazwa funkcji (_set_npc_locations).
        for m in re.finditer(r"(?i)\b(from|into|update|join|table)\s+npc_locations\b", text):
            line = text[: m.start()].count("\n") + 1
            hits.append(f"{rel}:{line}")
    assert hits == [], f"legacy npc_locations wciaz uzywany w kodzie: {hits}"


def test_zaden_serwis_nie_czyta_npc_keys_jako_fallbacku():
    """`npc_keys` to lustro — odczyt obsady idzie przez przypisania."""
    allowed = {
        "services/npc_placement_service.py",  # jedyny wlasciciel lustra
        "migrations_admin.py",
        "routers/locations.py",  # CRUD lokacji: zwraca lustro do panelu admina
        "routers/admin_location.py",
        "services/world_service.py",  # generator lokacji: zapis przez serwis, patrz nizej
    }
    hits = []
    for path in APP_DIR.rglob("*.py"):
        rel = path.relative_to(APP_DIR).as_posix()
        if rel in allowed:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "npc_keys" in text and "FROM game_locations" in text:
            for m in re.finditer(r"npc_keys\s+FROM\s+game_locations", text):
                hits.append(f"{rel}:{text[: m.start()].count(chr(10)) + 1}")
    assert hits == [], f"odczyt npc_keys z game_locations poza dozwolonymi miejscami: {hits}"
