"""TDD: Issue #680 (L11) — dungeon-run endpoint returns v2 graph structure for tile map rendering."""
import json
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_v2_run(entry_node: str = "node_0", extra_nodes: dict | None = None) -> dict:
    """Minimal valid v2 dungeon_run structure as stored in session_flags."""
    nodes = {
        entry_node: {
            "tile_id": 1,
            "position": [0, 0],
            "doors_open": {"E": "node_1"},
            "door_hints": {"E": "Wrogowie za drzwiami"},
            "content": {
                "tile_id": 1,
                "label": "Komnata Wejściowa",
                "image_url": None,
                "room_description": "Zimne mury z kamienia.",
                "doors": ["E"],
                "enemies": [],
                "riddle": None,
                "is_boss_tile": False,
            },
            "visited": True,
            "cleared": False,
            "is_boss": False,
        },
        "node_1": {
            "tile_id": 2,
            "position": [1, 0],
            "doors_open": {"W": entry_node, "N": None},
            "door_hints": {},
            "content": {
                "tile_id": 2,
                "label": "Korytarz Zachodny",
                "image_url": "/static/tiles/corridor.jpg",
                "room_description": "Wąski korytarz.",
                "doors": ["W", "N"],
                "enemies": [{"key": "skeleton", "count": 2}],
                "riddle": None,
                "is_boss_tile": False,
            },
            "visited": False,
            "cleared": False,
            "is_boss": False,
        },
    }
    if extra_nodes:
        nodes.update(extra_nodes)
    return {
        "system": "tiles_v2",
        "dungeon_key": "test_dungeon",
        "dungeon_label": "Testowy Loch",
        "category_key": "krypta",
        "dungeon_difficulty": 3,
        "graph": {
            "entry_node": entry_node,
            "nodes": nodes,
        },
        "positions": {"1": entry_node},
        "cycle": 1,
        "checkpoints": [],
        "at_checkpoint": False,
        "completed": False,
        "failed": False,
        "cooldown_hours": 72,
        "loot_collected": [],
    }


# ─── Test główny: endpoint zwraca graph.nodes dla v2 ─────────────────────────

def test_dungeon_run_endpoint_returns_v2_graph(tmp_path, monkeypatch):
    """GET /campaigns/{id}/dungeon-run must return graph.nodes for v2 runs.

    Weryfikuje że endpoint zwraca graph z nodes (v2), nie stary format rooms[].
    """
    from app.services.dungeon_service import get_active_dungeon_run

    v2_run = _make_v2_run()

    # Patch DB to return v2 run
    import app.services.dungeon_service as ds

    def _fake_get_db():
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE game_sessions (campaign_id INTEGER, session_flags TEXT)")
        conn.execute(
            "INSERT INTO game_sessions VALUES (?, ?)",
            (999, json.dumps({"dungeon_run": v2_run})),
        )
        conn.commit()
        return conn

    monkeypatch.setattr(ds, "_get_db", _fake_get_db)

    result = get_active_dungeon_run(999)

    assert result is not None, "Endpoint zwrócił None zamiast dungeon_run"
    assert result.get("system") == "tiles_v2", "Brak pola system=tiles_v2"
    assert "graph" in result, "Brak klucza 'graph' w dungeon_run"
    graph = result["graph"]
    assert "nodes" in graph, "Brak 'graph.nodes' — renderer nie ma z czego rysować"
    assert "entry_node" in graph, "Brak 'graph.entry_node'"

    nodes = graph["nodes"]
    assert len(nodes) >= 2, "Za mało nodów w grafie"

    # Sprawdź że node_0 ma wymagane pola
    entry = nodes[graph["entry_node"]]
    assert "position" in entry, "Brak 'position' w node"
    assert "visited" in entry, "Brak 'visited' w node"
    assert "doors_open" in entry, "Brak 'doors_open' w node"
    assert "content" in entry, "Brak 'content' w node"
    assert isinstance(entry["position"], list) and len(entry["position"]) == 2, \
        "position musi być listą [col, row]"


def test_dungeon_run_graph_fog_node_not_visited(tmp_path, monkeypatch):
    """Fog node (sąsiad visited) musi mieć visited=False — renderer rysuje go jako zarys."""
    from app.services.dungeon_service import get_active_dungeon_run
    import app.services.dungeon_service as ds

    v2_run = _make_v2_run()

    def _fake_get_db():
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE game_sessions (campaign_id INTEGER, session_flags TEXT)")
        conn.execute(
            "INSERT INTO game_sessions VALUES (?, ?)",
            (998, json.dumps({"dungeon_run": v2_run})),
        )
        conn.commit()
        return conn

    monkeypatch.setattr(ds, "_get_db", _fake_get_db)

    result = get_active_dungeon_run(998)
    nodes = result["graph"]["nodes"]

    entry_id = result["graph"]["entry_node"]
    entry_node = nodes[entry_id]

    # Entry node: visited=True (gracz był)
    assert entry_node["visited"] is True, "Entry node musi być visited=True"

    # node_1 jest sąsiadem przez doors_open, ale nie odwiedzonym
    neighbor_ids = [v for v in entry_node["doors_open"].values() if v]
    assert len(neighbor_ids) >= 1, "Entry node musi mieć co najmniej jednego sąsiada"

    neighbor = nodes[neighbor_ids[0]]
    assert neighbor["visited"] is False, "Sąsiad musi być visited=False (fog)"


def test_dungeon_run_positions_returns_current_node(monkeypatch):
    """run.positions['char_id'] wskazuje aktualny node gracza — renderer używa tego jako marker."""
    from app.services.dungeon_service import get_active_dungeon_run
    import app.services.dungeon_service as ds

    v2_run = _make_v2_run()

    def _fake_get_db():
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE game_sessions (campaign_id INTEGER, session_flags TEXT)")
        conn.execute(
            "INSERT INTO game_sessions VALUES (?, ?)",
            (997, json.dumps({"dungeon_run": v2_run})),
        )
        conn.commit()
        return conn

    monkeypatch.setattr(ds, "_get_db", _fake_get_db)

    result = get_active_dungeon_run(997)

    assert "positions" in result, "Brak 'positions' w dungeon_run"
    pos = result["positions"]
    assert len(pos) >= 1, "positions musi zawierać co najmniej jedną postać"
    char_node = list(pos.values())[0]
    assert char_node in result["graph"]["nodes"], \
        f"positions wskazuje node '{char_node}' który nie istnieje w graph.nodes"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_dungeon_run_returns_none_when_no_run(monkeypatch):
    """Gdy brak dungeon_run w session_flags, endpoint zwraca None (bez regresji)."""
    from app.services.dungeon_service import get_active_dungeon_run
    import app.services.dungeon_service as ds

    def _fake_get_db():
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE game_sessions (campaign_id INTEGER, session_flags TEXT)")
        conn.execute(
            "INSERT INTO game_sessions VALUES (?, ?)",
            (996, json.dumps({"current_hex": {"q": 0, "r": 0}})),
        )
        conn.commit()
        return conn

    monkeypatch.setattr(ds, "_get_db", _fake_get_db)

    result = get_active_dungeon_run(996)
    assert result is None, "Musi zwrócić None gdy brak dungeon_run"


def test_dungeon_run_returns_none_for_missing_campaign(monkeypatch):
    """Kampania bez game_session → None (bez regresji)."""
    from app.services.dungeon_service import get_active_dungeon_run
    import app.services.dungeon_service as ds

    def _fake_get_db():
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE game_sessions (campaign_id INTEGER, session_flags TEXT)")
        conn.commit()
        return conn

    monkeypatch.setattr(ds, "_get_db", _fake_get_db)

    result = get_active_dungeon_run(12345)
    assert result is None, "Musi zwrócić None gdy brak sesji"
