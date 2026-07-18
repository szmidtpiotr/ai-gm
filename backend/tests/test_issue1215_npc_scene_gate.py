"""#1215 — regułowe chipy NPC (Porozmawiaj z…) bramkowane obecnością w scenie.

„Mieszkaniec lokacji" ≠ „obecny tu i teraz": chip dialogu ma się pojawić dopiero,
gdy narrator wprowadzi NPC do ostatniej narracji (po imieniu własnym, nie po tytule).
Bez tego na turze przybycia chip proponował dialog z NPC, którego scena nie pokazała.
"""

import sqlite3

import pytest

from app.services.suggested_actions import _get_npc_actions, _npc_in_scene


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE npcs (key TEXT PRIMARY KEY, label TEXT)")
    c.execute(
        "CREATE TABLE location_npc_assignments (location_key TEXT, npc_key TEXT, is_active INTEGER)"
    )
    c.execute("CREATE TABLE game_locations (key TEXT PRIMARY KEY, npc_keys TEXT)")
    c.executemany(
        "INSERT INTO npcs (key, label) VALUES (?, ?)",
        [("kowal_wolanka", "Grubas Miron"), ("starszy_gornik_wolanka", "Starszy Konrad")],
    )
    c.executemany(
        "INSERT INTO location_npc_assignments (location_key, npc_key, is_active) VALUES (?, ?, 1)",
        [("wolanka", "kowal_wolanka"), ("wolanka", "starszy_gornik_wolanka")],
    )
    c.commit()
    yield c
    c.close()


# ── _npc_in_scene ────────────────────────────────────────────────────────────

def test_matches_proper_name():
    assert _npc_in_scene("Grubas Miron", "kowal_wolanka", "kowal miron kuje przy palenisku")


def test_matches_without_diacritics():
    # narrator/gracz bez ogonków (#1420)
    assert _npc_in_scene("Główny Łucznik Żvalen", "x", "zvalen napina cieciwe")


def test_title_only_no_false_positive():
    # samo "starszy" w opisie ("starszy mężczyzna") nie może wywołać chipu Konrada
    assert _npc_in_scene("Starszy Konrad", "x", "starszy mezczyzna siedzi przy ogniu") is False


def test_matches_konrad_when_named():
    assert _npc_in_scene("Starszy Konrad", "x", "konrad kiwa glowa")


def test_empty_scene_never_matches():
    assert _npc_in_scene("Grubas Miron", "kowal_wolanka", "") is False


# ── _get_npc_actions gating ──────────────────────────────────────────────────

def test_arrival_scene_no_npc_chips(conn):
    # atmosfera bez NPC → brak chipów dialogu (sedno #1215 feedbacku)
    acts = _get_npc_actions(conn, "wolanka", "mgla wisiala nad dachami, cisza osady")
    assert acts == []


def test_named_npc_gets_chip(conn):
    acts = _get_npc_actions(conn, "wolanka", "kowal miron kuje przy palenisku")
    assert [a.label for a in acts] == ["Porozmawiaj z Grubas Miron"]


def test_only_named_npc_not_all_residents(conn):
    # scena nazywa tylko Konrada — Miron (rezydent) się NIE pokazuje
    acts = _get_npc_actions(conn, "wolanka", "konrad opowiada o kopalni")
    labels = [a.label for a in acts]
    assert labels == ["Porozmawiaj z Starszy Konrad"]


def test_no_scene_text_no_chips(conn):
    assert _get_npc_actions(conn, "wolanka", "") == []


def test_npc_keys_fallback_gated(conn):
    # brak assignments → fallback na game_locations.npc_keys, też bramkowany sceną
    conn.execute("DELETE FROM location_npc_assignments")
    conn.execute(
        "INSERT INTO game_locations (key, npc_keys) VALUES (?, ?)",
        ("wolanka", '["kowal_wolanka"]'),
    )
    conn.commit()
    assert _get_npc_actions(conn, "wolanka", "cisza i mgla") == []
    named = _get_npc_actions(conn, "wolanka", "miron unosi mlot")
    assert [a.label for a in named] == ["Porozmawiaj z Grubas Miron"]
