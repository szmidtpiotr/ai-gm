"""TDD: Issue #625 (HI2) — wzbogacony czysty odczyt listy bohaterów dla sekcji „Bohaterowie".

`list_characters_admin()` musi:
  1. pokazywać też bohaterów IDLE (campaign_id NULL) — LEFT JOIN zamiast INNER JOIN (hero-first),
  2. dołączać kolumny: archetype, level, hp, max_hp (z sheet_json), status, owner_name (z users).

Czysty odczyt — zero mutacji. Test samowystarczalny (własny schemat w tmp DB, monkeypatch DB_PATH).
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from app.services import admin_character_recreate as rec


def _seed(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE users (
              id INTEGER PRIMARY KEY,
              username TEXT,
              display_name TEXT
            );
            CREATE TABLE campaigns (
              id INTEGER PRIMARY KEY,
              title TEXT
            );
            CREATE TABLE characters (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              campaign_id INTEGER,
              user_id INTEGER,
              name TEXT,
              sheet_json TEXT,
              status TEXT,
              is_active INTEGER NOT NULL DEFAULT 1,
              gold_gp INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        conn.execute("INSERT INTO users (id, username, display_name) VALUES (1, 'demo', 'Demo')")
        conn.execute("INSERT INTO campaigns (id, title) VALUES (10, 'Wyprawa')")
        sheet_active = json.dumps(
            {"archetype": "warrior", "level": 4, "current_hp": 22, "max_hp": 30}
        )
        sheet_idle = json.dumps(
            {"archetype": "scholar", "level": 2, "current_hp": 10, "max_hp": 14}
        )
        # Bohater w kampanii
        conn.execute(
            "INSERT INTO characters (campaign_id, user_id, name, sheet_json, status) "
            "VALUES (10, 1, 'Konrad', ?, 'in_campaign')",
            (sheet_active,),
        )
        # Bohater IDLE — campaign_id NULL (uwolniony, hero-first)
        conn.execute(
            "INSERT INTO characters (campaign_id, user_id, name, sheet_json, status) "
            "VALUES (NULL, 1, 'Mira', ?, 'idle')",
            (sheet_idle,),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "hi2.db")
    _seed(path)
    monkeypatch.setattr(rec, "DB_PATH", path)
    return path


# ─── Test główny ─────────────────────────────────────────────────────────────


def test_idle_hero_is_listed(db):
    """Bohater IDLE (bez kampanii) MUSI być na liście — LEFT JOIN, nie INNER JOIN."""
    items = rec.list_characters_admin()
    names = {r["name"] for r in items}
    assert "Mira" in names, "idle bohater (campaign_id NULL) zniknął — wciąż INNER JOIN?"
    assert "Konrad" in names
    assert len(items) == 2


def test_enriched_columns_present(db):
    """Lista zwraca komplet kolumn dla sekcji Bohaterowie."""
    items = {r["name"]: r for r in rec.list_characters_admin()}
    konrad = items["Konrad"]
    for col in ("archetype", "level", "hp", "max_hp", "status", "owner_name"):
        assert col in konrad, f"brak kolumny {col} w odczycie listy"
    assert konrad["archetype"] == "warrior"
    assert konrad["level"] == 4
    assert konrad["hp"] == 22
    assert konrad["max_hp"] == 30
    assert konrad["status"] == "in_campaign"
    assert konrad["owner_name"] == "demo"

    mira = items["Mira"]
    assert mira["archetype"] == "scholar"
    assert mira["status"] == "idle"
    assert mira["campaign_title"] is None  # idle — brak kampanii


# ─── Backward compatibility ──────────────────────────────────────────────────


def test_existing_columns_unchanged(db):
    """Stare pola (id, name, campaign_id, user_id, campaign_title) nadal obecne."""
    items = {r["name"]: r for r in rec.list_characters_admin()}
    konrad = items["Konrad"]
    for col in ("id", "name", "campaign_id", "user_id", "campaign_title"):
        assert col in konrad, f"regresja — zniknęła kolumna {col}"
    assert konrad["campaign_id"] == 10
    assert konrad["campaign_title"] == "Wyprawa"
    assert konrad["user_id"] == 1
