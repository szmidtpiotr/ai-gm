import sqlite3
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.api import campaigns as campaigns_api  # noqa: E402
from app.services import location_context_injector as lci  # noqa: E402
from app.services import location_integrity_config as lic  # noqa: E402
from app.services import location_integrity_service as lis  # noqa: E402
from app.services import location_intent_parser as lip  # noqa: E402
from app.services import location_validator as lv  # noqa: E402


def _setup_db(uri: str) -> sqlite3.Connection:
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE campaigns (id INTEGER PRIMARY KEY, current_location_id INTEGER, session_flags TEXT)")
    conn.execute("CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, name TEXT)")
    conn.execute("CREATE TABLE game_config_meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute(
        """
        CREATE TABLE game_locations (
          id INTEGER PRIMARY KEY,
          key TEXT UNIQUE NOT NULL,
          label TEXT NOT NULL,
          description TEXT,
          parent_id INTEGER,
          location_type TEXT,
          rules TEXT,
          enemy_keys TEXT,
          npc_keys TEXT,
          is_active INTEGER DEFAULT 1
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE location_integrity_log (
          id INTEGER PRIMARY KEY,
          campaign_id INTEGER NOT NULL,
          character_id INTEGER,
          attempted_move TEXT NOT NULL,
          current_location_key TEXT,
          reason_blocked TEXT,
          created_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        "INSERT INTO campaigns (id, current_location_id, session_flags) VALUES (1, 2, '{\"location_integrity_enabled\": 1}')"
    )
    conn.execute(
        "INSERT INTO game_config_meta (key, value) VALUES ('location_parser_json_enabled', '1'), ('location_parser_fallback_enabled', '1')"
    )
    conn.execute(
        "INSERT INTO game_locations (id, key, label, parent_id, location_type, rules, enemy_keys, npc_keys, is_active) VALUES "
        "(1, 'city_varen', 'Miasto Varen', NULL, 'macro', '{}', '[]', '[]', 1),"
        "(2, 'market_square', 'Rynek', 1, 'sub', '{}', '[]', '[]', 1),"
        "(3, 'blacksmith', 'Kuźnia', 1, 'sub', '{}', '[]', '[]', 1),"
        "(4, 'far_city', 'Dalekie Miasto', NULL, 'macro', '{}', '[]', '[]', 1)"
    )
    conn.commit()
    return conn


def test_parser_option_a_json(monkeypatch):
    monkeypatch.setattr(lip, "get_effective_flag", lambda key, campaign_id: True)
    payload = '{"location_intent":{"action":"move","target_label":"Rynek","target_key":"market_square"}}'
    intent = lip.parse_location_intent(payload, campaign_id=1)
    assert intent is not None
    assert intent.action == "move"
    assert intent.target_label == "Rynek"
    assert intent.target_key == "market_square"


def test_parser_option_b_fallback(monkeypatch):
    def _flag(key, campaign_id):
        return True

    monkeypatch.setattr(lip, "get_effective_flag", _flag)
    monkeypatch.setattr(lip, "generate_chat", lambda **kwargs: '{"moved": true, "target_label": "Kuźnia"}')
    intent = lip.parse_location_intent("Zwykła narracja bez JSON", campaign_id=1)
    assert intent is not None
    assert intent.action == "move"
    assert intent.target_label == "Kuźnia"


def test_validator_and_injector(monkeypatch):
    uri = "file:phase8d_loc_services?mode=memory&cache=shared"
    keeper = _setup_db(uri)
    try:
        monkeypatch.setattr(lv, "DB_PATH", uri)
        monkeypatch.setattr(lci, "DB_PATH", uri)
        monkeypatch.setattr(lic, "DB_PATH", uri)
        monkeypatch.setattr(lis, "DB_PATH", uri)

        intent_ok = lip.LocationIntent(action="move", target_label="Kuźnia", target_key=None, parent_key=None, description=None)
        vr_ok = lv.validate_move(1, intent_ok)
        assert vr_ok.allowed is True
        assert vr_ok.resolved_location_id == 3

        intent_block = lip.LocationIntent(
            action="move",
            target_label="Nieznane Miejsce",
            target_key=None,
            parent_key=None,
            description=None,
        )
        monkeypatch.setattr(lv, "_ask_same_location", lambda a, b, llm_config=None: False)
        vr_block = lv.validate_move(1, intent_block)
        assert vr_block.allowed is False
        assert vr_block.block_reason == "unknown_location_without_create"

        ctx = lci.build_location_context(1)
        assert "Aktualna lokalizacja: Rynek" in ctx
        assert "Możliwe sąsiednie lokalizacje:" in ctx
    finally:
        keeper.close()


def test_patch_campaign_location_endpoint(monkeypatch):
    uri = "file:phase8d_loc_patch?mode=memory&cache=shared"
    keeper = _setup_db(uri)
    try:
        monkeypatch.setattr(campaigns_api, "update_campaign_location_by_key", lis.update_campaign_location_by_key)
        monkeypatch.setattr(lis, "DB_PATH", uri)
        app = FastAPI()
        app.include_router(campaigns_api.router, prefix="/api")
        client = TestClient(app)
        resp = client.patch("/api/campaigns/1/location", json={"location_key": "blacksmith"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["campaign_id"] == 1
        assert body["location_key"] == "blacksmith"
    finally:
        keeper.close()
