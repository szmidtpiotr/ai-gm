"""TDD: SG-9 #1481/#1193 — wydarzenia regionalne przypisane do krainy.

Problem: `roll_event` losował z WSZYSTKICH aktywnych szablonów, bez względu na
krainę. Szablon charakterystyczny dla Siwych Grań („Głębokie Bicie" — stukanie
w żyle Rdzenia) wypadłby w Kresach, gdzie nie ma żadnego sensu. Dlatego szablon
dostaje `region_scope`: pusty = kraina dowolna, JSON-lista = tylko te krainy.
"""
import json
import sqlite3

import pytest

from app.services import world_event_service as wes


@pytest.fixture()
def conn(tmp_path):
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE game_config_event_templates (
            key TEXT PRIMARY KEY, type TEXT, label TEXT,
            duration_days_min INTEGER, duration_days_max INTEGER,
            modifiers_json TEXT, narrative_tags TEXT,
            weight INTEGER, is_active INTEGER, created_by TEXT,
            region_scope TEXT, created_at TEXT, updated_at TEXT
        );
        CREATE TABLE world_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, region TEXT, template_key TEXT,
            started_at TEXT, ends_at TEXT, state TEXT, source TEXT, created_at TEXT
        );
        """
    )
    db.executemany(
        "INSERT INTO game_config_event_templates (key,type,label,duration_days_min,"
        "duration_days_max,modifiers_json,narrative_tags,weight,is_active,created_by,"
        "region_scope) VALUES (?,?,?,?,?,?,?,?,1,'seed',?)",
        [
            ("jarmark", "jarmark", "Jarmark", 2, 4, "{}", "[]", 10, None),
            ("zima", "zima", "Surowa zima", 4, 8, "{}", "[]", 6, ""),
            ("glebokie_bicie", "glebokie_bicie", "Głębokie Bicie", 3, 6, "{}", "[]", 9,
             json.dumps(["siwe_granie"])),
            ("solna_blokada", "solna_blokada", "Karawana solna nie dotarła", 3, 6, "{}", "[]", 7,
             json.dumps(["siwe_granie"])),
        ],
    )
    db.commit()
    return db


def _keys(rows):
    return {r["key"] for r in rows}


def test_globalny_szablon_widoczny_w_kazdej_krainie(conn):
    """region_scope NULL albo pusty = szablon uniwersalny."""
    assert {"jarmark", "zima"} <= _keys(wes.list_templates(conn, region="kresy"))
    assert {"jarmark", "zima"} <= _keys(wes.list_templates(conn, region="siwe_granie"))


def test_szablon_krainowy_nie_wychodzi_poza_swoja_kraine(conn):
    """§ sedno: Głębokie Bicie to sprawa Siwych Grań, nie Kresów."""
    kresy = _keys(wes.list_templates(conn, region="kresy"))
    assert "glebokie_bicie" not in kresy
    assert "solna_blokada" not in kresy


def test_szablon_krainowy_dostepny_w_swojej_krainie(conn):
    granie = _keys(wes.list_templates(conn, region="siwe_granie"))
    assert {"glebokie_bicie", "solna_blokada"} <= granie


def test_bez_podanej_krainy_lista_jest_pelna(conn):
    """Admin ogląda wszystkie szablony — filtr działa tylko gdy podamy krainę."""
    assert len(wes.list_templates(conn)) == 4


def test_roll_event_w_kresach_nigdy_nie_wylosuje_szablonu_grani(conn):
    for _ in range(40):
        ev = wes.roll_event(conn, "kresy", source="manual")
        assert ev is not None
        assert ev["template_key"] in ("jarmark", "zima")
        conn.execute("UPDATE world_events SET state='ended' WHERE id=?", (ev["id"],))
        conn.commit()


def test_roll_event_w_graniach_potrafi_wylosowac_szablon_krainowy(conn):
    seen = set()
    for _ in range(60):
        ev = wes.roll_event(conn, "siwe_granie", source="manual")
        assert ev is not None
        seen.add(ev["template_key"])
        conn.execute("UPDATE world_events SET state='ended' WHERE id=?", (ev["id"],))
        conn.commit()
    assert seen & {"glebokie_bicie", "solna_blokada"}, "krainowe szablony nigdy nie wypadły"


def test_brak_kolumny_region_scope_nie_wywraca_listy(tmp_path):
    """Stara baza bez kolumny (przed migracją) ma działać — degradacja do 'wszystko globalne'."""
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE game_config_event_templates (
            key TEXT PRIMARY KEY, type TEXT, label TEXT,
            duration_days_min INTEGER, duration_days_max INTEGER,
            modifiers_json TEXT, narrative_tags TEXT,
            weight INTEGER, is_active INTEGER, created_by TEXT
        );
        """
    )
    db.execute(
        "INSERT INTO game_config_event_templates VALUES "
        "('jarmark','jarmark','Jarmark',2,4,'{}','[]',10,1,'seed')"
    )
    db.commit()
    assert _keys(wes.list_templates(db, region="siwe_granie")) == {"jarmark"}
