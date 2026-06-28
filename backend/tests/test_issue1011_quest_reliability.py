"""TDD: Issue #1011 — Quest reliability: auto-domykanie questów + fallback gdy
narrator gubi [QUEST_COMPLETE].

Two mechanisms under test:
  1. auto_complete_quests_by_event() — quest with a condition (kill/visit/talk/find)
     closes itself on the matching game event, WITHOUT relying on the narrator tag.
     Structured objective_type/objective_value when present; keyword fallback on the
     quest narrative/title otherwise.
  2. build_quest_complete_reminder() — when a quest has been active for a long time and
     no tag arrived, inject a directive nudging the narrator to emit [QUEST_COMPLETE].
"""
import json
import sqlite3
import sys

sys.path.insert(0, "/app")


def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY,
            gm_plan_json TEXT
        );
        CREATE TABLE campaign_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            turn_number INTEGER
        );
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER,
            session_flags TEXT DEFAULT '{}'
        );
        CREATE TABLE character_quests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            campaign_id INTEGER NOT NULL,
            quest_type TEXT NOT NULL DEFAULT 'main',
            title TEXT NOT NULL,
            narrative TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active',
            objective_type TEXT,
            objective_value TEXT,
            created_turn INTEGER,
            completed_turn INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    conn.execute("INSERT INTO campaigns (id, gm_plan_json) VALUES (1, '{}')")
    conn.execute("INSERT INTO game_sessions (id, campaign_id, session_flags) VALUES (1, 1, '{}')")
    conn.commit()
    return conn


def _add_quest(conn, title, narrative="", objective_type=None, objective_value=None,
               created_turn=1, character_id=10):
    conn.execute(
        """INSERT INTO character_quests
               (character_id, campaign_id, title, narrative, status,
                objective_type, objective_value, created_turn)
           VALUES (?,1,?,?,'active',?,?,?)""",
        (character_id, title, narrative, objective_type, objective_value, created_turn),
    )
    conn.commit()


def _status(conn, title):
    r = conn.execute("SELECT status FROM character_quests WHERE title=?", (title,)).fetchone()
    return r["status"] if r else None


# ─── 1. Auto-complete by event — structured objective ────────────────────────

def test_auto_complete_kill_quest_structured():
    """Quest with objective_type=kill_enemy closes on matching kill, no tag."""
    from app.services.quest_persist_service import auto_complete_quests_by_event

    conn = _make_db()
    _add_quest(conn, "Zabij Goblina", objective_type="kill_enemy", objective_value="Goblin Wódz")
    done = auto_complete_quests_by_event(conn, 1, "kill_enemy", "Goblin Wódz", 5)
    assert "Zabij Goblina" in done
    assert _status(conn, "Zabij Goblina") == "completed"


def test_auto_complete_wildcard_objective():
    """Empty objective_value = wildcard: any target of the right type matches."""
    from app.services.quest_persist_service import auto_complete_quests_by_event

    conn = _make_db()
    _add_quest(conn, "Pokonaj wroga", objective_type="kill_enemy", objective_value="")
    done = auto_complete_quests_by_event(conn, 1, "kill_enemy", "Jakikolwiek Zbój", 3)
    assert "Pokonaj wroga" in done
    assert _status(conn, "Pokonaj wroga") == "completed"


# ─── 2. Auto-complete by event — keyword fallback on narrative ────────────────

def test_auto_complete_keyword_fallback_on_narrative():
    """Quest with NO structured objective still closes when the event target
    keyword-matches the quest narrative (the 'narrator forgot the tag' case)."""
    from app.services.quest_persist_service import auto_complete_quests_by_event

    conn = _make_db()
    _add_quest(conn, "Sprawa karczmarza",
               narrative="Porozmawiaj z karczmarzem w Wilczburgu o zaginięciu.")
    done = auto_complete_quests_by_event(conn, 1, "talk_to_npc", "karczmarz", 4)
    assert "Sprawa karczmarza" in done
    assert _status(conn, "Sprawa karczmarza") == "completed"


def test_auto_complete_no_false_match():
    """A quest whose objective/narrative does not match the event stays active."""
    from app.services.quest_persist_service import auto_complete_quests_by_event

    conn = _make_db()
    _add_quest(conn, "Zbadaj ruiny", narrative="Odnajdź wejście do starożytnych ruin.")
    done = auto_complete_quests_by_event(conn, 1, "kill_enemy", "Smok", 2)
    assert done == []
    assert _status(conn, "Zbadaj ruiny") == "active"


def test_auto_complete_wrong_event_type_no_match():
    """Structured kill_enemy quest does not close on a talk_to_npc event."""
    from app.services.quest_persist_service import auto_complete_quests_by_event

    conn = _make_db()
    _add_quest(conn, "Zabij bestię", objective_type="kill_enemy", objective_value="Bestia")
    done = auto_complete_quests_by_event(conn, 1, "talk_to_npc", "Bestia", 2)
    assert done == []
    assert _status(conn, "Zabij bestię") == "active"


def test_auto_complete_sets_quest_suggest_needed_when_empty():
    """When the last active quest auto-completes, the #991 quest-dead guard fires."""
    from app.services.quest_persist_service import auto_complete_quests_by_event

    conn = _make_db()
    _add_quest(conn, "Ostatni quest", objective_type="kill_enemy", objective_value="Wróg")
    auto_complete_quests_by_event(conn, 1, "kill_enemy", "Wróg", 6)
    sf = json.loads(conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id=1"
    ).fetchone()["session_flags"])
    assert "quest_suggest_needed" in sf


# ─── 3. Fallback reminder when the tag never arrives ─────────────────────────

def test_reminder_fires_for_stale_quest():
    """A quest active longer than the threshold yields a reminder directive."""
    from app.services.quest_persist_service import build_quest_complete_reminder

    conn = _make_db()
    _add_quest(conn, "Stary quest", narrative="Dawno temu zaczęte zadanie.", created_turn=1)
    directive = build_quest_complete_reminder(conn, 1, current_turn=20)
    assert directive  # non-empty
    assert "Stary quest" in directive
    assert "QUEST_COMPLETE" in directive


def test_reminder_silent_for_fresh_quest():
    """A recently created quest does not trigger the reminder."""
    from app.services.quest_persist_service import build_quest_complete_reminder

    conn = _make_db()
    _add_quest(conn, "Nowy quest", created_turn=19)
    directive = build_quest_complete_reminder(conn, 1, current_turn=20)
    assert directive == ""


# ─── 4. Backward compatibility ───────────────────────────────────────────────

def test_complete_quest_by_tag_still_works():
    """The original tag-driven completion path is unchanged."""
    from app.services.quest_persist_service import complete_quest_in_character_quests

    conn = _make_db()
    _add_quest(conn, "Quest tagowy", character_id=10)
    flipped = complete_quest_in_character_quests(conn, 10, 1, "Quest tagowy", completed_turn=7)
    assert flipped is True
    assert _status(conn, "Quest tagowy") == "completed"
