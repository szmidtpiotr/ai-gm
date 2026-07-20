"""#1488 — sprzątanie po przebiegu Playwrighta kasuje TYLKO śmieci z tego przebiegu."""
import sqlite3

import pytest

from app.services import test_cleanup_service as tcs


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / "probe.db"
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE game_locations (id INTEGER PRIMARY KEY, key TEXT);
        CREATE TABLE npcs (id INTEGER PRIMARY KEY, key TEXT);
        CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT);
        CREATE TABLE characters (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE character_inventory (id INTEGER PRIMARY KEY, character_id INTEGER);
        """
    )
    con.commit()
    con.close()
    monkeypatch.setenv("AI_TEST_MODE", "1")
    monkeypatch.setenv("AI_TEST_DB_PATH", str(path))
    return path


def _rows(path, table, col):
    con = sqlite3.connect(path)
    try:
        return sorted(r[0] for r in con.execute(f"SELECT {col} FROM {table}"))
    finally:
        con.close()


def _insert(path, sql, params):
    con = sqlite3.connect(path)
    con.execute(sql, params)
    con.commit()
    con.close()


def test_removes_only_junk_created_during_the_run(db):
    _insert(db, "INSERT INTO game_locations (id,key) VALUES (?,?)", (1, "karczma_pod_debem"))
    _insert(db, "INSERT INTO game_locations (id,key) VALUES (?,?)", (2, "test_loc_pw_stary"))

    before = tcs.snapshot()

    # przebieg testów dokłada swoje
    _insert(db, "INSERT INTO game_locations (id,key) VALUES (?,?)", (3, "test_loc_pw_1783"))
    _insert(db, "INSERT INTO game_locations (id,key) VALUES (?,?)", (4, "plac_targowy"))

    removed = tcs.cleanup_since(before)

    assert removed == {"game_locations": 1}
    # śmieć z przebiegu znika; treść i WCZEŚNIEJSZY śmieć zostają nietknięte
    assert _rows(db, "game_locations", "key") == ["karczma_pod_debem", "plac_targowy", "test_loc_pw_stary"]


def test_character_cleanup_takes_its_child_rows(db):
    before = tcs.snapshot()
    _insert(db, "INSERT INTO characters (id,name) VALUES (?,?)", (77, "TEST1479_1784"))
    _insert(db, "INSERT INTO character_inventory (id,character_id) VALUES (?,?)", (1, 77))
    _insert(db, "INSERT INTO characters (id,name) VALUES (?,?)", (78, "Eldric"))

    removed = tcs.cleanup_since(before)

    assert removed == {"characters": 1}
    assert _rows(db, "characters", "name") == ["Eldric"]
    assert _rows(db, "character_inventory", "id") == []          # brak sieroty po ekwipunku


def test_empty_snapshot_cleans_backlog(db):
    """Ręczne wywołanie z panelu (bez zdjęcia) sprząta zaległości."""
    _insert(db, "INSERT INTO users (id,username) VALUES (?,?)", (5, "test960_h1"))
    _insert(db, "INSERT INTO users (id,username) VALUES (?,?)", (6, "piotrszmidt"))
    _insert(db, "INSERT INTO users (id,username) VALUES (?,?)", (7, "ai_test_player"))

    removed = tcs.cleanup_since({t: set() for t in tcs.WATCHED})

    assert removed == {"users": 1}
    # konto seedowe trybu testowego i realne konto zostają
    assert _rows(db, "users", "username") == ["ai_test_player", "piotrszmidt"]


def test_summary_is_human_readable():
    assert tcs.summarize({}) == "brak śmieci do posprzątania"
    assert tcs.summarize({"users": 2, "game_locations": 1}) == "game_locations 1, users 2"
