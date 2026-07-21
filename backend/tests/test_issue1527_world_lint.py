"""TDD: Issue #1527 — Fala 4 „lampka w panelu zamiast cichej samonaprawy".

Dzis swiat prostuje sie sam, po cichu, przy kazdym starcie backendu
(`reconcile_location_hex_links` + backfille). Rozjazd znika z ekranu, ale
przyczyna zostaje, a Piotr nigdy sie nie dowiaduje, ze cos bylo nie tak.
Do tego zaden lint nie sprawdzal jakosci tresci — 30 lokacji uslugowych bez
gospodarza (#1524) nikt nie zauwazyl przez miesiace.

Fala 4 wprowadza `world_lint_service`:
  * 7 regul lintu swiata (uslugowka bez gospodarza, sieroty obsady, heks
    wskazujacy nieistniejaca lokacje, pin bez pokrycia w kanonie, zepsuty
    rodzic sub-lokacji, flagi spoza legalnego zbioru, duplikaty etykiet),
  * `fix_world_lint_issue()` — deterministyczna naprawa pojedynczego rozjazdu,
  * historia napraw (`world_lint_history`) — reconcile przy starcie DOPISUJE
    co naprawil, zamiast milczec.

Regula „uslugowka bez gospodarza" liczy sie WYLACZNIE dla krain o statusie
`live` (korekta Piotra z 2026-07-21) — Czarnobor i Pustkowia wejda do lintu
automatycznie w dniu otwarcia, bez zmian w kodzie.

Uruchomienie:
    ./scripts/test_dev.sh tests/test_issue1527_world_lint.py -v
"""
from __future__ import annotations

import sqlite3

import pytest

from app.services.world_lint_service import (
    DUPLICATE_SIMILARITY_THRESHOLD,
    LINT_LIST_LIMIT,
    fix_world_lint_issue,
    lint_history,
    lint_issue_count,
    record_reconcile_report,
    record_startup_cleanup,
    run_world_lint,
)


# ─────────────────────────── fixtures ────────────────────────────────────────

SCHEMA = """
CREATE TABLE game_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    parent_id INTEGER,
    parent_key TEXT,
    location_type TEXT DEFAULT 'macro',
    location_subtype TEXT,
    npc_keys TEXT DEFAULT '[]',
    is_active INTEGER DEFAULT 1,
    created_by TEXT DEFAULT 'admin_manual',
    review_status TEXT NOT NULL DEFAULT 'permanent',
    world_hex_q INTEGER,
    world_hex_r INTEGER,
    region TEXT
);

CREATE TABLE world_hexes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    q INTEGER NOT NULL,
    r INTEGER NOT NULL,
    map_level INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    location_key TEXT,
    region TEXT
);

CREATE TABLE world_regions (
    key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'coming',
    status_override TEXT DEFAULT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE npcs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE location_npc_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_key TEXT NOT NULL,
    npc_key TEXT NOT NULL,
    assignment_type TEXT NOT NULL DEFAULT 'resident',
    notes TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    UNIQUE(location_key, npc_key)
);
"""


def _add_location(conn: sqlite3.Connection, key: str, **kw) -> int:
    row = {
        "label": kw.pop("label", key.replace("_", " ").title()),
        "parent_id": kw.pop("parent_id", None),
        "parent_key": kw.pop("parent_key", None),
        "location_type": kw.pop("location_type", "macro"),
        "location_subtype": kw.pop("location_subtype", None),
        "is_active": kw.pop("is_active", 1),
        "created_by": kw.pop("created_by", "seed"),
        "review_status": kw.pop("review_status", "permanent"),
        "world_hex_q": kw.pop("world_hex_q", None),
        "world_hex_r": kw.pop("world_hex_r", None),
        "region": kw.pop("region", "kresy"),
    }
    assert not kw, f"nieznane pola: {sorted(kw)}"
    cur = conn.execute(
        "INSERT INTO game_locations (key, label, parent_id, parent_key, location_type, "
        "location_subtype, is_active, created_by, review_status, world_hex_q, world_hex_r, region) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (key, row["label"], row["parent_id"], row["parent_key"], row["location_type"],
         row["location_subtype"], row["is_active"], row["created_by"], row["review_status"],
         row["world_hex_q"], row["world_hex_r"], row["region"]),
    )
    conn.commit()
    return int(cur.lastrowid)


@pytest.fixture()
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    c.executemany(
        "INSERT INTO world_regions (key, label, status) VALUES (?,?,?)",
        [("kresy", "Kresy", "live"), ("czarnobor", "Czarnobór", "coming")],
    )
    c.commit()
    yield c
    c.close()


def _rules(report: dict) -> list[str]:
    return [i["rule"] for i in report["issues"]]


def _issue(report: dict, rule: str) -> dict | None:
    return next((i for i in report["issues"] if i["rule"] == rule), None)


# ─── R1: uslugowka bez gospodarza (tylko krainy `live`) ──────────────────────

def test_service_location_without_host_is_reported(conn):
    """Karczma w krainie `live` bez ani jednego NPC = rozjazd na liscie."""
    _add_location(conn, "karczma_pod_rogiem", location_subtype="tavern", region="kresy")

    report = run_world_lint(conn)

    issue = _issue(report, "service_without_host")
    assert issue is not None, "karczma bez gospodarza musi trafic na liste"
    assert "karczma_pod_rogiem" in issue["target"]
    assert issue["fixable"] is False, "dosiew gospodarza to fala tresci, nie auto-fix"


def test_service_location_with_host_is_clean(conn):
    """Ta sama karczma z obsadzona rola gospodarza — cisza."""
    _add_location(conn, "karczma_pod_rogiem", location_subtype="tavern", region="kresy")
    conn.execute("INSERT INTO npcs (key, label) VALUES ('hanka', 'Hanka Rogowa')")
    conn.execute(
        "INSERT INTO location_npc_assignments (location_key, npc_key) VALUES (?,?)",
        ("karczma_pod_rogiem", "hanka"),
    )
    conn.commit()

    assert "service_without_host" not in _rules(run_world_lint(conn))


def test_service_location_in_coming_region_is_not_reported(conn):
    """Kraina `coming` (Czarnobor, Pustkowia) nie generuje falszywych alarmow."""
    _add_location(conn, "goscinne_drzewo", location_subtype="tavern", region="czarnobor")

    assert "service_without_host" not in _rules(run_world_lint(conn))


def test_region_opening_pulls_it_into_lint_without_code_change(conn):
    """Filtr stoi na statusie krainy, nie na liscie nazw — otwarcie = wejscie do lintu."""
    _add_location(conn, "goscinne_drzewo", location_subtype="tavern", region="czarnobor")
    conn.execute("UPDATE world_regions SET status = 'live' WHERE key = 'czarnobor'")
    conn.commit()

    assert "service_without_host" in _rules(run_world_lint(conn))


# ─── R2: sierota obsady (NPC przypisany do nieistniejacej lokacji) ───────────

def test_orphan_npc_assignment_is_reported_and_fixable(conn):
    _add_location(conn, "brzezino")
    conn.execute("INSERT INTO npcs (key, label) VALUES ('bartel', 'Bartel')")
    conn.execute(
        "INSERT INTO location_npc_assignments (location_key, npc_key) VALUES (?,?)",
        ("start_24", "bartel"),
    )
    conn.commit()

    issue = _issue(run_world_lint(conn), "orphan_npc_assignment")
    assert issue is not None and issue["fixable"] is True

    result = fix_world_lint_issue(conn, issue["id"])
    assert result["fixed"] is True

    assert "orphan_npc_assignment" not in _rules(run_world_lint(conn))


# ─── R3: heks wskazuje nieistniejaca lokacje ────────────────────────────────

def test_hex_pointing_at_missing_location_is_reported_and_fixable(conn):
    conn.execute(
        "INSERT INTO world_hexes (q, r, map_level, is_active, location_key) VALUES (?,?,?,?,?)",
        (24, 13, 0, 1, "duch_lokacji"),
    )
    conn.commit()

    issue = _issue(run_world_lint(conn), "hex_points_to_missing_location")
    assert issue is not None and issue["fixable"] is True

    assert fix_world_lint_issue(conn, issue["id"])["fixed"] is True
    row = conn.execute("SELECT location_key FROM world_hexes WHERE q=24 AND r=13").fetchone()
    assert row["location_key"] in (None, "")


# ─── R4: pin lokacji bez pokrycia w kanonie heksow ──────────────────────────

def test_location_pin_not_backed_by_hex_canon_is_reported(conn):
    _add_location(conn, "brzezino", world_hex_q=1, world_hex_r=0)
    conn.execute(
        "INSERT INTO world_hexes (q, r, map_level, is_active, location_key) VALUES (?,?,?,?,?)",
        (39, 9, 0, 1, "brzezino"),
    )
    conn.commit()

    issue = _issue(run_world_lint(conn), "pin_not_backed_by_canon")
    assert issue is not None and issue["fixable"] is True

    assert fix_world_lint_issue(conn, issue["id"])["fixed"] is True
    assert "pin_not_backed_by_canon" not in _rules(run_world_lint(conn))


def test_location_pin_matching_canon_is_clean(conn):
    _add_location(conn, "brzezino", world_hex_q=39, world_hex_r=9)
    conn.execute(
        "INSERT INTO world_hexes (q, r, map_level, is_active, location_key) VALUES (?,?,?,?,?)",
        (39, 9, 0, 1, "brzezino"),
    )
    conn.commit()

    assert "pin_not_backed_by_canon" not in _rules(run_world_lint(conn))


# ─── R5: sub-lokacja bez rodzica / bez kompletu parent_id+parent_key ────────

def test_sublocation_with_dead_parent_is_reported_and_fixable(conn):
    _add_location(conn, "karczma_przy_rozwidleniu", location_type="sub",
                  parent_id=170, parent_key="start_26")

    issue = _issue(run_world_lint(conn), "broken_sublocation_parent")
    assert issue is not None and issue["fixable"] is True

    assert fix_world_lint_issue(conn, issue["id"])["fixed"] is True
    row = conn.execute(
        "SELECT location_type, parent_id, parent_key FROM game_locations WHERE key = ?",
        ("karczma_przy_rozwidleniu",),
    ).fetchone()
    assert row["location_type"] == "macro", "sierota bez rodzica awansuje na makro"
    assert row["parent_id"] is None and row["parent_key"] is None
    assert "broken_sublocation_parent" not in _rules(run_world_lint(conn))


def test_sublocation_with_half_parent_link_is_completed_by_fix(conn):
    hub_id = _add_location(conn, "brzezino")
    _add_location(conn, "brzezino_kram", location_type="sub", parent_key="brzezino")

    issue = _issue(run_world_lint(conn), "broken_sublocation_parent")
    assert issue is not None, "sam parent_key bez parent_id to niekompletne wiazanie"

    assert fix_world_lint_issue(conn, issue["id"])["fixed"] is True
    row = conn.execute(
        "SELECT parent_id, parent_key, location_type FROM game_locations WHERE key = ?",
        ("brzezino_kram",),
    ).fetchone()
    assert row["parent_id"] == hub_id and row["parent_key"] == "brzezino"
    assert row["location_type"] == "sub", "kompletne wiazanie nie degraduje sub do makro"


def test_healthy_sublocation_is_clean(conn):
    hub_id = _add_location(conn, "brzezino")
    _add_location(conn, "brzezino_kram", location_type="sub",
                  parent_id=hub_id, parent_key="brzezino")

    assert "broken_sublocation_parent" not in _rules(run_world_lint(conn))


# ─── R6: flagi spoza legalnego zbioru ───────────────────────────────────────

def test_illegal_created_by_is_reported_and_fixable(conn):
    _add_location(conn, "dziwna_lokacja", created_by="ai_generated")

    issue = _issue(run_world_lint(conn), "illegal_flag_value")
    assert issue is not None and issue["fixable"] is True

    assert fix_world_lint_issue(conn, issue["id"])["fixed"] is True
    assert "illegal_flag_value" not in _rules(run_world_lint(conn))


def test_legal_created_by_values_are_clean(conn):
    for i, src in enumerate(
        ["seed", "admin_manual", "admin_kreator", "forge", "gm_runtime", "auto_generated"]
    ):
        _add_location(conn, f"lokacja_{i}", created_by=src)

    assert "illegal_flag_value" not in _rules(run_world_lint(conn))


# ─── R7: duplikaty po etykiecie w tej samej krainie ─────────────────────────

def test_duplicate_labels_in_same_region_are_reported(conn):
    _add_location(conn, "trzech_krukow", label="Karczma Pod Trzema Krukami", region="kresy")
    _add_location(conn, "trzech_krukow_2", label="Karczma Pod Trzema Krukami", region="kresy")

    issue = _issue(run_world_lint(conn), "duplicate_label_in_region")
    assert issue is not None
    assert issue["fixable"] is False, "wybor ktora kopie zostawic nalezy do czlowieka"


def test_same_label_in_other_region_is_not_a_duplicate(conn):
    _add_location(conn, "kaplica_kresy", label="Opuszczona kaplica", region="kresy")
    _add_location(conn, "kaplica_cb", label="Opuszczona kaplica", region="czarnobor")

    assert "duplicate_label_in_region" not in _rules(run_world_lint(conn))


def test_similarity_threshold_is_a_tunable_starting_value():
    assert DUPLICATE_SIMILARITY_THRESHOLD == pytest.approx(0.85)
    assert LINT_LIST_LIMIT == 200


# ─── Historia napraw — koniec cichej samonaprawy ────────────────────────────

def test_startup_reconcile_writes_repair_history(conn):
    """Reconcile przy starcie RAPORTUJE co naprawil — widoczna historia."""
    assert lint_history(conn) == []

    report = {
        "smears": [{"key": "brzezino", "kept": (39, 9), "cleared_hex": (1, 0)}],
        "backfilled": [{"key": "strazyn", "from": (0, 0), "to": (24, 13)}],
        "promoted": [],
        "cleared": [{"key": "obozowisko", "was": (7, 7)}],
        "canonical_pairs": 3,
    }
    written = record_reconcile_report(conn, report)
    assert written == 3

    history = lint_history(conn)
    assert len(history) == 3
    assert all(h["source"] == "startup_reconcile" for h in history)
    assert {h["rule"] for h in history} == {"reconcile_smear", "reconcile_backfill", "reconcile_clear"}


def test_clean_reconcile_writes_nothing(conn):
    empty = {"smears": [], "backfilled": [], "promoted": [], "cleared": [], "canonical_pairs": 12}
    assert record_reconcile_report(conn, empty) == 0
    assert lint_history(conn) == []


def test_startup_migration_cleanup_also_reports(conn):
    """Migracja #1525 tez prostowala swiat po cichu przy kazdym starcie."""
    written = record_startup_cleanup(
        conn, "pin_not_backed_by_canon", ["obozowisko", "temp_camp_1"],
        "pin bez pokrycia w kanonie — zgaszony przez migracje startowa",
    )
    assert written == 2

    history = lint_history(conn)
    assert {h["source"] for h in history} == {"startup_migration"}
    assert {h["target"] for h in history} == {"obozowisko", "temp_camp_1"}


def test_startup_cleanup_without_targets_writes_nothing(conn):
    assert record_startup_cleanup(conn, "pin_not_backed_by_canon", [], "nic") == 0
    assert lint_history(conn) == []


def test_manual_fix_lands_in_history(conn):
    conn.execute(
        "INSERT INTO world_hexes (q, r, map_level, is_active, location_key) VALUES (?,?,?,?,?)",
        (24, 13, 0, 1, "duch_lokacji"),
    )
    conn.commit()
    issue = _issue(run_world_lint(conn), "hex_points_to_missing_location")

    fix_world_lint_issue(conn, issue["id"])

    history = lint_history(conn)
    assert len(history) == 1
    assert history[0]["source"] == "manual_fix"
    assert history[0]["rule"] == "hex_points_to_missing_location"


# ─── Kontrakt raportu + licznik do badge'a ──────────────────────────────────

def test_report_shape_and_counter(conn):
    _add_location(conn, "karczma_pod_rogiem", location_subtype="tavern", region="kresy")
    _add_location(conn, "kuznia", location_subtype="smithy", region="kresy")

    report = run_world_lint(conn)
    assert report["total"] == len(report["issues"]) == 2
    assert report["counts"]["service_without_host"] == 2
    assert report["truncated"] is False
    for issue in report["issues"]:
        assert set(issue) >= {"id", "rule", "severity", "label", "detail", "target", "fixable"}
        assert issue["severity"] in ("error", "warning")

    assert lint_issue_count(conn) == 2


def test_clean_world_reports_nothing(conn):
    _add_location(conn, "brzezino")
    assert run_world_lint(conn) == {
        "issues": [], "counts": {}, "total": 0, "truncated": False, "fixable": 0
    }


def test_fix_of_unknown_issue_id_is_refused(conn):
    result = fix_world_lint_issue(conn, "nie_ma_takiej_reguly:cokolwiek")
    assert result["fixed"] is False


def test_fix_of_unfixable_rule_is_refused(conn):
    _add_location(conn, "karczma_pod_rogiem", location_subtype="tavern", region="kresy")
    issue = _issue(run_world_lint(conn), "service_without_host")

    result = fix_world_lint_issue(conn, issue["id"])
    assert result["fixed"] is False
    assert "service_without_host" in _rules(run_world_lint(conn)), "nic nie zniknelo po cichu"


# ─── Backward compatibility ─────────────────────────────────────────────────

def test_existing_db_lint_still_works():
    """Stary audyt tresci (U12 #559) dziala niezaleznie od nowego lintu swiata."""
    from app.services.db_lint_service import run_lint

    result = run_lint(":memory:")
    assert set(result) >= {"errors", "warnings", "exit_code"}
