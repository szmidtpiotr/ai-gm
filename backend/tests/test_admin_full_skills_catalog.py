"""Inspektor bohatera — GET /admin/characters/{id}/full musi zwracać PEŁNY katalog
skilli (unia game_config_skills + rangi z arkusza), nie tylko podzbiór zapisany
w sheet_json. Bez tego admin nie widzi (i nie może nadać) skilli spoza puli
kreatora — np. arcane_ward / mana_shield (#1324/#1325)."""

from __future__ import annotations
from _fixtures_schema import table_sql

import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import admin_cheat
from app.routers.admin import require_admin_token

CATALOG_KEYS = ["alchemy", "arcane_ward", "dodge", "mana_shield", "trade_craft"]


def _seed_schema(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE characters (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT,
              campaign_id INTEGER,
              user_id INTEGER,
              status TEXT DEFAULT 'idle',
              is_active INTEGER DEFAULT 1,
              sheet_json TEXT,
              gold_gp INTEGER NOT NULL DEFAULT 0
            );

            """ + table_sql("game_config_skills") + """

            INSERT INTO characters(id, name, campaign_id, user_id, sheet_json, gold_gp)
            VALUES (
              1, 'Drundor', NULL, 1,
              '{"current_hp":10,"max_hp":10,"level":1,"stats":{"INT":16},"skills":{"alchemy":1,"trade_craft":5,"dodge":0}}',
              10
            );
            """
        )
        conn.executemany(
            "INSERT INTO game_config_skills(key, label) VALUES (?, ?)",
            [(k, k) for k in CATALOG_KEYS],
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def client_with_auth(tmp_path):
    db_path = str(tmp_path / "test_full_skills.db")
    old_db_path = admin_cheat.DB_PATH
    admin_cheat.DB_PATH = db_path
    _seed_schema(db_path)

    app = FastAPI()
    app.include_router(admin_cheat.router, prefix="/api")
    app.dependency_overrides[require_admin_token] = lambda: None
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        admin_cheat.DB_PATH = old_db_path


def test_full_returns_whole_catalog_with_sheet_ranks(client_with_auth):
    r = client_with_auth.get("/api/admin/characters/1/full")
    assert r.status_code == 200
    skills = r.json()["skills"]
    # Każdy skill z katalogu obecny — brakujące w arkuszu z rangą 0.
    for key in CATALOG_KEYS:
        assert key in skills, f"missing catalog skill: {key}"
    assert skills["arcane_ward"] == 0
    assert skills["mana_shield"] == 0
    # Rangi z arkusza zachowane.
    assert skills["alchemy"] == 1
    assert skills["trade_craft"] == 5
    assert skills["dodge"] == 0


def test_full_keeps_sheet_skill_absent_from_catalog(client_with_auth):
    # Skill w arkuszu spoza katalogu (legacy) nie może zniknąć.
    conn = sqlite3.connect(admin_cheat.DB_PATH)
    conn.execute(
        "UPDATE characters SET sheet_json = json_set(sheet_json, '$.skills.legacy_skill', 2) WHERE id = 1"
    )
    conn.commit()
    conn.close()

    r = client_with_auth.get("/api/admin/characters/1/full")
    assert r.status_code == 200
    assert r.json()["skills"]["legacy_skill"] == 2
