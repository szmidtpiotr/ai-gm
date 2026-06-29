"""TDD: Issue #1011 — cap concurrent active quests (anti-spam backstop).

Bug: the narrator emits a fresh [QUEST_SUGGEST] almost every turn; title +
Jaccard-objective dedup misses re-worded near-duplicates. Smoke 999972 spawned 5
variants of "find Iwo" on the bar. Fix: hard cap MAX_ACTIVE_QUESTS — beyond it,
persist_quest_to_character_quests drops new suggestions until one is closed.
"""
import sqlite3
import sys

sys.path.insert(0, "/app")


def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE character_quests (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id  INTEGER NOT NULL,
            campaign_id   INTEGER NOT NULL,
            quest_type    TEXT NOT NULL DEFAULT 'main',
            title         TEXT NOT NULL,
            narrative     TEXT NOT NULL DEFAULT '',
            status        TEXT NOT NULL DEFAULT 'active',
            created_turn  INTEGER,
            completed_turn INTEGER,
            beat_key      TEXT,
            created_at    TEXT DEFAULT (datetime('now')),
            updated_at    TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE campaign_turns (campaign_id INTEGER, turn_number INTEGER);
    """)
    return conn


_OBJECTIVES = [
    "Odnajdź zaginionego kowala przy starym moście",
    "Dostarcz lekarstwo chorej zielarce do wioski",
    "Zbadaj nawiedzoną wieżę na wzgórzu obok jeziora",
    "Upoluj wilki nękające pasterzy z doliny",
    "Wykop skarb ukryty pod ruinami kaplicy",
    "Eskortuj kupca przez bagna do portu",
    "Przekaż wiadomość strażnikom w odległej twierdzy",
    "Zniszcz gniazdo pająków w opuszczonej kopalni",
]


def _q(i):
    # Disjoint titles AND disjoint wording so neither title nor Jaccard dedup fires —
    # isolates the cap behaviour under test.
    return {"title": f"Zadanie {i}: {_OBJECTIVES[i][:12]}",
            "objective": _OBJECTIVES[i]}


def test_count_active_quests_scopes_main_active():
    from app.services.quest_persist_service import count_active_quests
    conn = _make_db()
    conn.executescript(
        "INSERT INTO character_quests (character_id,campaign_id,title,status) VALUES "
        "(1,7,'a','active'),(1,7,'b','active'),(1,7,'c','completed'),(1,9,'d','active');"
    )
    conn.commit()
    assert count_active_quests(conn, 7) == 2
    assert count_active_quests(conn, 7, 1) == 2
    assert count_active_quests(conn, 9) == 1


def test_persist_blocks_beyond_cap():
    """Up to MAX_ACTIVE_QUESTS persist; the next re-worded suggestion is dropped."""
    from app.services import quest_persist_service as qp

    conn = _make_db()
    accepted = [qp.persist_quest_to_character_quests(conn, 1, 7, _q(i), turn_number=i)
                for i in range(qp.MAX_ACTIVE_QUESTS + 3)]

    assert accepted[:qp.MAX_ACTIVE_QUESTS] == [True] * qp.MAX_ACTIVE_QUESTS
    assert all(a is False for a in accepted[qp.MAX_ACTIVE_QUESTS:]), "over-cap suggestions dropped"
    assert qp.count_active_quests(conn, 7) == qp.MAX_ACTIVE_QUESTS


def test_cap_frees_after_completion():
    """Closing a quest frees a slot — a new suggestion is accepted again."""
    from app.services import quest_persist_service as qp

    conn = _make_db()
    for i in range(qp.MAX_ACTIVE_QUESTS):
        assert qp.persist_quest_to_character_quests(conn, 1, 7, _q(i), turn_number=i)
    # At cap — next dropped.
    assert qp.persist_quest_to_character_quests(conn, 1, 7, _q(6), turn_number=6) is False
    # Complete one → slot frees.
    conn.execute("UPDATE character_quests SET status='completed' WHERE id=1")
    conn.commit()
    assert qp.persist_quest_to_character_quests(conn, 1, 7, _q(7), turn_number=7) is True
