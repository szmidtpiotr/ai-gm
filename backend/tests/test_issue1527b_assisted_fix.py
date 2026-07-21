"""TDD: Issue #1527 (fala 4, runda 2) — NAPRAWA WSPOMAGANA problemów treściowych.

Reguły „decyzja człowieka" (usługa bez gospodarza, duplikat etykiety) z założenia
nie mają guzika jednego kliknięcia — maszyna nie zgaduje treści. Ale to nie znaczy,
że admin ma skakać między zakładkami: Kontrola świata → Lokacje → Świat/NPC → z
powrotem, dla każdego z 20 problemów osobno.

Ta runda daje trzy rzeczy, wszystkie sterowane RĘKĄ CZŁOWIEKA, tylko bez przełączania
zakładek:

1. `host_candidates()` — kto może zostać gospodarzem (NPC bez przydziału),
2. `assign_host()` / `create_host()` — przypisanie albo utworzenie gospodarza w miejscu,
3. `resolve_duplicate()` — rozstrzygnięcie duplikatu (którą kartę zostawić, czy
   przenieść obsadę i sub-lokacje),
4. `lint_flags()` — mapa `klucz lokacji → problemy`, żeby wiersze w zakładkach
   Lokacje / Floating / Do zatwierdzenia mogły nosić znacznik 🩺.

Uruchomienie:
    ./scripts/test_dev.sh tests/test_issue1527b_assisted_fix.py -v
"""
from __future__ import annotations

import sqlite3

import pytest

from app.services.world_lint_service import (
    assign_host,
    create_host,
    duplicate_compare,
    host_candidates,
    host_suggestion_context,
    lint_flags,
    resolve_duplicate,
    run_world_lint,
)

from tests.test_issue1527_world_lint import SCHEMA, _add_location  # noqa: F401


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


def _add_npc(conn: sqlite3.Connection, key: str, label: str | None = None) -> None:
    conn.execute("INSERT INTO npcs (key, label) VALUES (?,?)", (key, label or key.title()))
    conn.commit()


def _assign(conn: sqlite3.Connection, location_key: str, npc_key: str) -> None:
    conn.execute(
        "INSERT INTO location_npc_assignments (location_key, npc_key) VALUES (?,?)",
        (location_key, npc_key),
    )
    conn.commit()


def _rules(report: dict) -> list[str]:
    return [i["rule"] for i in report["issues"]]


# ─── Kandydaci na gospodarza ─────────────────────────────────────────────────

def test_host_candidates_lists_only_unplaced_npcs(conn):
    """Podpowiadamy tych, ktorzy nigdzie nie stoja — nie kradniemy cudzych gospodarzy."""
    _add_location(conn, "karczma", location_subtype="tavern")
    _add_npc(conn, "wolny_kowal", "Wolny Kowal")
    _add_npc(conn, "zajety_karczmarz", "Zajęty Karczmarz")
    _add_location(conn, "inna_karczma", location_subtype="tavern")
    _assign(conn, "inna_karczma", "zajety_karczmarz")

    keys = [c["key"] for c in host_candidates(conn, "karczma")]
    assert keys == ["wolny_kowal"]


def test_host_candidates_skip_inactive_npcs(conn):
    _add_location(conn, "karczma", location_subtype="tavern")
    _add_npc(conn, "duch")
    conn.execute("UPDATE npcs SET is_active = 0 WHERE key = 'duch'")
    conn.commit()

    assert host_candidates(conn, "karczma") == []


def test_host_candidates_carry_label_for_the_picker(conn):
    _add_location(conn, "karczma", location_subtype="tavern")
    _add_npc(conn, "hanka", "Hanka Rogowa")

    candidate = host_candidates(conn, "karczma")[0]
    assert candidate["key"] == "hanka" and candidate["label"] == "Hanka Rogowa"


# ─── Przypisanie istniejącego NPC ────────────────────────────────────────────

def test_assign_host_closes_the_lint_issue(conn):
    _add_location(conn, "karczma", location_subtype="tavern", region="kresy")
    _add_npc(conn, "hanka", "Hanka Rogowa")
    assert "service_without_host" in _rules(run_world_lint(conn))

    result = assign_host(conn, "karczma", "hanka")
    assert result["ok"] is True

    assert "service_without_host" not in _rules(run_world_lint(conn))


def test_assign_host_refuses_unknown_npc(conn):
    _add_location(conn, "karczma", location_subtype="tavern")

    result = assign_host(conn, "karczma", "nie_ma_takiego")
    assert result["ok"] is False


def test_assign_host_refuses_unknown_location(conn):
    _add_npc(conn, "hanka")

    result = assign_host(conn, "nie_ma_lokacji", "hanka")
    assert result["ok"] is False


def test_assign_host_mirrors_npc_keys_on_the_card(conn):
    """`npc_keys` to kopia pochodna (#1524) — po przypisaniu musi byc odswiezona."""
    _add_location(conn, "karczma", location_subtype="tavern")
    _add_npc(conn, "hanka")

    assign_host(conn, "karczma", "hanka")

    row = conn.execute("SELECT npc_keys FROM game_locations WHERE key = 'karczma'").fetchone()
    assert "hanka" in (row["npc_keys"] or "")


# ─── Utworzenie nowego gospodarza ────────────────────────────────────────────

def test_create_host_makes_npc_and_places_him(conn):
    _add_location(conn, "kuznia", location_subtype="smithy", region="kresy")

    result = create_host(conn, "kuznia", label="Bolko Kowal", npc_type="merchant",
                         description="Krzepki kowal o przypalonej brodzie.")
    assert result["ok"] is True

    npc = conn.execute("SELECT * FROM npcs WHERE key = ?", (result["npc_key"],)).fetchone()
    assert npc is not None and npc["label"] == "Bolko Kowal"
    assert "service_without_host" not in _rules(run_world_lint(conn))


def test_create_host_key_is_slugified_and_unique(conn):
    _add_location(conn, "kuznia", location_subtype="smithy")
    _add_location(conn, "kuznia2", location_subtype="smithy")

    first = create_host(conn, "kuznia", label="Bolko Kowal")
    second = create_host(conn, "kuznia2", label="Bolko Kowal")

    assert first["npc_key"] == "bolko_kowal"
    assert second["npc_key"] != first["npc_key"], "drugi Bolko nie moze nadpisac pierwszego"


def test_create_host_requires_a_name(conn):
    _add_location(conn, "kuznia", location_subtype="smithy")

    assert create_host(conn, "kuznia", label="   ")["ok"] is False


# ─── Kontekst dla podpowiedzi AI (sam prompt buduje sie deterministycznie) ───

def test_host_suggestion_context_carries_place_region_and_role(conn):
    _add_location(conn, "kamienny_grod_kuznia", label="Kamienny Gród: Kuźnia",
                  location_subtype="smithy", region="siwe_granie")

    ctx = host_suggestion_context(conn, "kamienny_grod_kuznia")
    assert ctx["label"] == "Kamienny Gród: Kuźnia"
    assert ctx["region"] == "siwe_granie"
    assert ctx["subtype"] == "smithy"
    assert ctx["role_pl"] == "kuźnia"


def test_host_suggestion_context_of_unknown_location_is_empty(conn):
    assert host_suggestion_context(conn, "nie_ma") == {}


# ─── Rozstrzygnięcie duplikatu ───────────────────────────────────────────────

def test_resolve_duplicate_deactivates_the_dropped_card(conn):
    _add_location(conn, "trzech_krukow", label="Karczma Pod Trzema Krukami")
    _add_location(conn, "trzech_krukow_2", label="Karczma Pod Trzema Krukami")

    result = resolve_duplicate(conn, keep="trzech_krukow", drop="trzech_krukow_2")
    assert result["ok"] is True

    row = conn.execute(
        "SELECT is_active FROM game_locations WHERE key = 'trzech_krukow_2'"
    ).fetchone()
    assert row["is_active"] == 0
    assert "duplicate_label_in_region" not in _rules(run_world_lint(conn))


def test_resolve_duplicate_can_move_cast_and_children(conn):
    """Kasowanie kopii nie moze gubic obsady ani wnetrz — czlowiek decyduje, my przenosimy."""
    _add_location(conn, "trzech_krukow", label="Karczma Pod Trzema Krukami")
    _add_location(conn, "trzech_krukow_2", label="Karczma Pod Trzema Krukami")
    _add_npc(conn, "marta")
    _assign(conn, "trzech_krukow_2", "marta")
    _add_location(conn, "izba", location_type="sub", parent_key="trzech_krukow_2")

    result = resolve_duplicate(conn, keep="trzech_krukow", drop="trzech_krukow_2",
                               move_assets=True)
    assert result["moved_npcs"] == 1 and result["moved_children"] == 1

    assert conn.execute(
        "SELECT 1 FROM location_npc_assignments WHERE location_key='trzech_krukow' "
        "AND npc_key='marta' AND COALESCE(is_active,1)=1"
    ).fetchone() is not None
    child = conn.execute("SELECT parent_key FROM game_locations WHERE key='izba'").fetchone()
    assert child["parent_key"] == "trzech_krukow"


def test_resolve_duplicate_without_move_leaves_assets_alone(conn):
    _add_location(conn, "a_kopia", label="Wolanka")
    _add_location(conn, "b_kopia", label="Wolanka")
    _add_npc(conn, "kupiec")
    _assign(conn, "b_kopia", "kupiec")

    result = resolve_duplicate(conn, keep="a_kopia", drop="b_kopia", move_assets=False)
    assert result["moved_npcs"] == 0

    row = conn.execute(
        "SELECT location_key FROM location_npc_assignments WHERE npc_key='kupiec'"
    ).fetchone()
    assert row["location_key"] == "b_kopia"


def test_resolve_duplicate_refuses_to_drop_a_card_standing_on_the_map(conn):
    """Karta osadzona na heksie to kanon mapy — kasowanie jej wymaga najpierw mapy."""
    _add_location(conn, "wolanka", label="Wolanka", world_hex_q=5, world_hex_r=5)
    _add_location(conn, "wolanka_kopia", label="Wolanka")
    conn.execute(
        "INSERT INTO world_hexes (q, r, map_level, is_active, location_key) VALUES (?,?,?,?,?)",
        (5, 5, 0, 1, "wolanka"),
    )
    conn.commit()

    result = resolve_duplicate(conn, keep="wolanka_kopia", drop="wolanka")
    assert result["ok"] is False
    assert "map" in result["reason"] or "mapie" in result["message"].lower()


def test_resolve_duplicate_refuses_same_card(conn):
    _add_location(conn, "wolanka", label="Wolanka")
    assert resolve_duplicate(conn, keep="wolanka", drop="wolanka")["ok"] is False


def test_resolve_duplicate_lands_in_history(conn):
    from app.services.world_lint_service import lint_history

    _add_location(conn, "a_kopia", label="Wolanka")
    _add_location(conn, "b_kopia", label="Wolanka")

    resolve_duplicate(conn, keep="a_kopia", drop="b_kopia")

    history = lint_history(conn)
    assert len(history) == 1
    assert history[0]["source"] == "manual_fix"
    assert history[0]["rule"] == "duplicate_label_in_region"


# ─── Porównanie duplikatów (dane do decyzji człowieka) ───────────────────────

def test_duplicate_compare_gives_both_cards_with_the_deciding_facts(conn):
    """Czlowiek wybiera karte po faktach: obsada, wnetrza, mapa, zrodlo."""
    _add_location(conn, "wolanka", label="Wolanka", created_by="seed", world_hex_q=5, world_hex_r=5)
    _add_location(conn, "wolanka_2", label="Wolanka", created_by="gm_runtime")
    _add_npc(conn, "kupiec")
    _assign(conn, "wolanka", "kupiec")
    _add_location(conn, "izba", location_type="sub", parent_key="wolanka")
    conn.execute(
        "INSERT INTO world_hexes (q, r, map_level, is_active, location_key) VALUES (?,?,?,?,?)",
        (5, 5, 0, 1, "wolanka"),
    )
    conn.commit()

    cmp = duplicate_compare(conn, "wolanka", "wolanka_2")
    a, b = cmp["a"], cmp["b"]
    assert a["key"] == "wolanka" and a["npc_count"] == 1 and a["children_count"] == 1
    assert a["on_map"] == {"q": 5, "r": 5} and a["created_by"] == "seed"
    assert b["npc_count"] == 0 and b["on_map"] is None


def test_duplicate_compare_of_missing_card_is_empty(conn):
    _add_location(conn, "wolanka", label="Wolanka")
    assert duplicate_compare(conn, "wolanka", "nie_ma")["b"] is None


# ─── Znaczniki dla pozostałych zakładek ──────────────────────────────────────

def test_lint_flags_maps_location_key_to_its_problems(conn):
    _add_location(conn, "karczma", location_subtype="tavern", region="kresy")
    _add_location(conn, "sierota", location_type="sub", parent_id=999, parent_key="nie_ma")
    _add_location(conn, "zdrowa")

    flags = lint_flags(conn)
    assert "service_without_host" in [f["rule"] for f in flags["karczma"]]
    assert "broken_sublocation_parent" in [f["rule"] for f in flags["sierota"]]
    assert "zdrowa" not in flags


def test_lint_flags_carry_human_label_for_the_tooltip(conn):
    _add_location(conn, "karczma", location_subtype="tavern", region="kresy")

    flag = lint_flags(conn)["karczma"][0]
    assert flag["label"] and flag["severity"] in ("error", "warning")
    assert flag["fixable"] is False


def test_lint_flags_on_clean_world_is_empty(conn):
    _add_location(conn, "zdrowa")
    assert lint_flags(conn) == {}
