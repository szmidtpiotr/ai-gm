"""TDD: Issue #1479 — kraina zamknięta ⇒ rasa wyszarzona w kreatorze (z powodem).

Krasnolud ma ojczyznę: Siwe Granie. Gdy kraina nie jest `live`, rasa ma być
NIEDOSTĘPNA w kreatorze — ale widoczna, z czytelnym powodem („te ziemie są
jeszcze zamknięte"), nie ukryta. Człowiek nie ma kotwicy i jest dostępny zawsze.

Tester (#1478) wchodzi do krain `coming`, więc spójnie dostaje też ich rasy.
`locked` zamyka rasę dla wszystkich.

Uruchom w kontenerze:
    docker exec ai-gm-dev-backend-1 pytest tests/test_issue1479_race_region_gate.py -v
"""
import sqlite3
import sys

import pytest

sys.path.insert(0, "/app")

from app.services import world_region_service as wrs  # noqa: E402


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _mem_db(siwe_status: str = "coming") -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE world_regions (
            key TEXT PRIMARY KEY, label TEXT NOT NULL,
            color TEXT NOT NULL DEFAULT '#888888',
            status TEXT NOT NULL DEFAULT 'coming'
                   CHECK(status IN ('live','coming','locked')),
            status_override TEXT DEFAULT NULL,
            entry_q INTEGER, entry_r INTEGER,
            sort_order INTEGER NOT NULL DEFAULT 0, note TEXT
        );
        CREATE TABLE users (
            id INTEGER PRIMARY KEY, username TEXT,
            is_tester INTEGER NOT NULL DEFAULT 0
        );
    """)
    conn.executemany(
        "INSERT INTO world_regions(key,label,status,sort_order) VALUES (?,?,?,?)",
        [("kresy", "Kresy", "live", 1), ("siwe_granie", "Siwe Granie", siwe_status, 4)],
    )
    conn.executemany("INSERT INTO users(id,username,is_tester) VALUES (?,?,?)",
                     [(1, "tester", 1), (2, "gracz", 0)])
    conn.commit()
    return conn


def _avail(conn, **kw) -> dict:
    """{race_key: entry} dla wygodnych asercji."""
    return {r["key"]: r for r in wrs.race_availability(conn, **kw)}


# ── Człowiek: zawsze dostępny ────────────────────────────────────────────────

def test_human_always_available():
    for status in ("live", "coming", "locked"):
        conn = _mem_db(status)
        try:
            human = _avail(conn)["human"]
            assert human["available"] is True
            assert human["reason"] is None
            assert human["home_region"] is None, "człowiek nie ma kotwicy w krainie"
        finally:
            conn.close()


# ── Krasnolud ↔ Siwe Granie ──────────────────────────────────────────────────

def test_dwarf_blocked_when_home_region_coming():
    conn = _mem_db("coming")
    try:
        dwarf = _avail(conn)["dwarf"]
        assert dwarf["available"] is False
        assert dwarf["home_region"] == "siwe_granie"
        assert "Siwe Granie" in (dwarf["reason"] or ""), "powód musi nazywać krainę"
    finally:
        conn.close()


def test_dwarf_available_when_home_region_live():
    conn = _mem_db("live")
    try:
        dwarf = _avail(conn)["dwarf"]
        assert dwarf["available"] is True and dwarf["reason"] is None
    finally:
        conn.close()


def test_dwarf_blocked_when_home_region_locked():
    conn = _mem_db("locked")
    try:
        assert _avail(conn)["dwarf"]["available"] is False
    finally:
        conn.close()


# ── Spójność z bramką testera (#1478) ────────────────────────────────────────

def test_tester_gets_coming_race():
    """Skoro tester może wejść do Siwych Grań, może też nimi grać."""
    conn = _mem_db("coming")
    try:
        assert _avail(conn, include_coming=True)["dwarf"]["available"] is True
    finally:
        conn.close()


def test_tester_still_blocked_on_locked_race():
    conn = _mem_db("locked")
    try:
        assert _avail(conn, include_coming=True)["dwarf"]["available"] is False
    finally:
        conn.close()


def test_user_is_tester_helper():
    conn = _mem_db()
    try:
        assert wrs.user_is_tester(conn, 1) is True
        assert wrs.user_is_tester(conn, 2) is False
        assert wrs.user_is_tester(conn, 999) is False
        assert wrs.user_is_tester(conn, None) is False
    finally:
        conn.close()


# ── Odporność na brak danych ─────────────────────────────────────────────────

def test_unknown_home_region_does_not_block():
    """Brak wiersza krainy (świeży clone) nie może zablokować tworzenia postaci."""
    conn = _mem_db("coming")
    try:
        conn.execute("DELETE FROM world_regions WHERE key='siwe_granie'")
        conn.commit()
        assert _avail(conn)["dwarf"]["available"] is True
    finally:
        conn.close()


def test_missing_table_does_not_block():
    conn = _mem_db()
    try:
        conn.execute("DROP TABLE world_regions")
        conn.commit()
        entries = _avail(conn)
        assert all(e["available"] for e in entries.values())
    finally:
        conn.close()


# ── Bramka po stronie zapisu ─────────────────────────────────────────────────

def test_assert_race_available_raises_for_blocked_race():
    conn = _mem_db("coming")
    try:
        with pytest.raises(wrs.RaceUnavailable) as e:
            wrs.assert_race_available(conn, "dwarf", user_id=2)
        assert "Siwe Granie" in str(e.value)
    finally:
        conn.close()


def test_assert_race_available_passes_for_tester():
    conn = _mem_db("coming")
    try:
        wrs.assert_race_available(conn, "dwarf", user_id=1)  # tester — bez wyjątku
    finally:
        conn.close()


def test_assert_race_available_passes_for_human():
    conn = _mem_db("coming")
    try:
        wrs.assert_race_available(conn, "human", user_id=2)
    finally:
        conn.close()


def test_assert_race_available_ignores_unknown_race():
    """Nieznana rasa to sprawa walidacji rasy, nie bramki krain — tu przechodzi."""
    conn = _mem_db("coming")
    try:
        wrs.assert_race_available(conn, "elf", user_id=2)
    finally:
        conn.close()


# ── Kontrakt endpointu ───────────────────────────────────────────────────────

def test_races_route_registered():
    from app.api.characters import router
    paths = {getattr(r, "path", "") for r in router.routes}
    assert "/creation/races" in paths, f"brak trasy; jest: {sorted(p for p in paths if 'creation' in p or 'race' in p)}"
