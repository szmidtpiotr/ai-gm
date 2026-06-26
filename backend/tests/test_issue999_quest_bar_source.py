"""TDD: Issue #999 — quest-bar must read character_quests (status='active'), not world_state.

Bug: GET /api/campaigns/{id}/quests read active_quests from world_state, which drifted
from character_quests (completed quests never pruned, new ones never added). The HUD bar
showed a stale/completed quest. Fix (Option A): read directly from character_quests.

Helper under test: quest_persist_service.get_active_quests_for_bar(conn, campaign_id).
"""
import sqlite3
import sys

sys.path.insert(0, "/app")


def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE character_quests (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id         INTEGER NOT NULL,
            campaign_id          INTEGER NOT NULL,
            quest_type           TEXT NOT NULL DEFAULT 'main',
            title                TEXT NOT NULL,
            narrative            TEXT NOT NULL DEFAULT '',
            status               TEXT NOT NULL DEFAULT 'active',
            resolution           TEXT DEFAULT NULL,
            resolution_narrative TEXT DEFAULT NULL,
            created_turn         INTEGER,
            completed_turn       INTEGER DEFAULT NULL,
            created_at           TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at           TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    return conn


def _insert(conn, *, campaign_id, title, narrative, status, created_turn, character_id=42):
    conn.execute(
        """INSERT INTO character_quests
               (character_id, campaign_id, quest_type, title, narrative, status, created_turn)
           VALUES (?,?,?,?,?,?,?)""",
        (character_id, campaign_id, "main", title, narrative, status, created_turn),
    )
    conn.commit()


# ── Test główny — belka pokazuje TYLKO aktywne, completed przycięty ───────────

def test_bar_returns_only_active_quests_mapped_for_hud():
    """Returns active quests only; completed pruned; narrative mapped to 'objective'.

    Reproduces 99791 drift: 'Nocna przesyłka' completed, 'Ślad Jednookiego' active.
    """
    from app.services.quest_persist_service import get_active_quests_for_bar

    conn = _make_db()
    _insert(conn, campaign_id=99791, title="Nocna przesyłka",
            narrative="Dostarcz paczkę", status="completed", created_turn=10)
    _insert(conn, campaign_id=99791, title="Ślad Jednookiego",
            narrative="Znajdź Jednookiego", status="active", created_turn=42)

    quests = get_active_quests_for_bar(conn, 99791)

    titles = [q["title"] for q in quests]
    assert titles == ["Ślad Jednookiego"], "only the active quest belongs on the bar"
    assert "Nocna przesyłka" not in titles, "completed quest must be pruned (#999 root cause)"
    # HUD renderQuestBar reads q.objective — narrative must map to it
    assert quests[0]["objective"] == "Znajdź Jednookiego"
    assert "reward" in quests[0], "HUD chip tooltip reads q.reward (may be empty)"


def test_bar_orders_by_created_turn():
    """Multiple active quests come back oldest-first (created_turn order)."""
    from app.services.quest_persist_service import get_active_quests_for_bar

    conn = _make_db()
    _insert(conn, campaign_id=7, title="Drugi", narrative="b", status="active", created_turn=5)
    _insert(conn, campaign_id=7, title="Pierwszy", narrative="a", status="active", created_turn=2)

    quests = get_active_quests_for_bar(conn, 7)

    assert [q["title"] for q in quests] == ["Pierwszy", "Drugi"]


# ── Backward compat / edge ────────────────────────────────────────────────────

def test_bar_empty_when_no_active_quests():
    """No active quests → empty list (bar stays hidden, same as old empty behavior)."""
    from app.services.quest_persist_service import get_active_quests_for_bar

    conn = _make_db()
    _insert(conn, campaign_id=7, title="Skończony", narrative="x", status="completed", created_turn=1)

    assert get_active_quests_for_bar(conn, 7) == []


def test_bar_scopes_to_campaign():
    """Quests from other campaigns must not leak onto this campaign's bar."""
    from app.services.quest_persist_service import get_active_quests_for_bar

    conn = _make_db()
    _insert(conn, campaign_id=1, title="Obcy", narrative="x", status="active", created_turn=1)
    _insert(conn, campaign_id=2, title="Mój", narrative="y", status="active", created_turn=1)

    quests = get_active_quests_for_bar(conn, 2)
    assert [q["title"] for q in quests] == ["Mój"]
