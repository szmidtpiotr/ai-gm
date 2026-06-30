"""TDD: Issue #1054 — Atak z zaskoczenia wywołuje Zastraszanie zamiast walki.

Trzy luki:
1. "zaatakowac" (bezokolicznik) brak w _COMBAT_INTENT_VERBS → _player_combat_intent=False
2. _ensure_combat_start_tag nie sprawdza pending_zaskoczony → COMBAT_START nie wstrzykiwane
3. Guard #1046 kasuje pending_zaskoczony przy ruchu zbliżenia do celu
"""
import json
import sqlite3
import sys

sys.path.insert(0, "/app")

# ─── FAZA 1: _player_combat_intent ───────────────────────────────────────────

def test_zaatakowac_infinitive_detected_as_combat_intent():
    """'zaatakowac' (bezokolicznik) musi być wykrywany jako intent walki.

    Repro: gracz pisze 'chce zaatakowac go z zaskoczenia' →
    _player_combat_intent zwracał False bo lista miała tylko 'zaatakuj'/'zaatakuje'.
    """
    from app.api.turns import _player_combat_intent

    assert _player_combat_intent(
        "chce zaatakowac go z zaskoczenia, przylozyc sztylet do szyi i zmusic do mowienia"
    ), "Bezokolicznik 'zaatakowac' musi byc wykrywany jako deklaracja walki"


def test_chce_zaatakowac_simple():
    """Prosty 'chce zaatakować go' musi byc wykryty."""
    from app.api.turns import _player_combat_intent

    assert _player_combat_intent("chce zaatakowac go")


def test_zaatakowal_past_tense_detected():
    """'zaatakowal' (czas przeszły) też wykrywany — scenariusze GM piszą w 3. osobie."""
    from app.api.turns import _player_combat_intent

    assert _player_combat_intent("zaatakowal strażnika")


# ─── FAZA 2: _ensure_combat_start_tag z pending_zaskoczony ───────────────────

def _make_conn_with_pending_surprise(enemy_key: str = "straznik") -> sqlite3.Connection:
    """Minimalny in-memory SQLite z pending_zaskoczony i wrogiem w scenie."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(f"""
        CREATE TABLE game_sessions (
            campaign_id INTEGER PRIMARY KEY,
            session_flags TEXT DEFAULT '{{}}',
            scene_enemies TEXT DEFAULT '[]',
            scene_npcs TEXT DEFAULT '[]',
            current_location_id INTEGER
        );
        INSERT INTO game_sessions (campaign_id, session_flags, scene_enemies, scene_npcs)
        VALUES (
            1,
            '{json.dumps({"pending_zaskoczony": True})}',
            '{json.dumps([{"key": enemy_key, "name": "Straznik", "hp_current": 20}])}',
            '[]'
        );
        CREATE TABLE active_combat (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER,
            status TEXT
        );
        CREATE TABLE game_config_enemies (
            key TEXT PRIMARY KEY,
            label TEXT,
            is_active INTEGER DEFAULT 1,
            min_level INTEGER DEFAULT 1
        );
        INSERT INTO game_config_enemies (key, label, is_active, min_level)
        VALUES ('{enemy_key}', 'Straznik', 1, 1);
        CREATE TABLE campaign_known_npcs (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER,
            npc_name TEXT
        );
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY,
            sheet_json TEXT DEFAULT '{{}}'
        );
        INSERT INTO characters (id, sheet_json) VALUES (1, '{json.dumps({"level": 3})}');
        CREATE TABLE campaign_turns (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER,
            assistant_text TEXT
        );
    """)
    conn.commit()
    return conn


def test_ensure_combat_start_injects_when_pending_surprise_and_weapon():
    """_ensure_combat_start_tag wstrzykuje [COMBAT_START] gdy:
    - pending_zaskoczony=True w session_flags
    - gracz pisze 'z zaskoczenia' + broń (sztylet)
    - LLM nie emitował [COMBAT_START]
    """
    from app.api.turns import _ensure_combat_start_tag

    conn = _make_conn_with_pending_surprise("straznik")
    player_text = "chce zaatakowac go z zaskoczenia, przylozyc sztylet do szyi"
    assistant_text = "Straznik stoi spokojnie przy bramie, nic nie podejrzewa."  # brak COMBAT_START

    result = _ensure_combat_start_tag(conn, 1, player_text, assistant_text, character_id=1)
    conn.close()

    assert "[COMBAT_START:" in result, (
        f"Oczekiwano [COMBAT_START:...] w odpowiedzi gdy pending_zaskoczony+sztylet+z zaskoczenia. "
        f"Otrzymano: {result[:200]}"
    )


def test_ensure_combat_start_not_injected_without_pending():
    """Bez pending_zaskoczony i bez deklaracji ataku — brak wstrzyknięcia."""
    from app.api.turns import _ensure_combat_start_tag

    conn = _make_conn_with_pending_surprise("straznik")
    # Czyścimy pending_zaskoczony
    conn.execute("UPDATE game_sessions SET session_flags='{}' WHERE campaign_id=1")
    conn.commit()

    player_text = "ide dalej, ogladam okolicze"
    assistant_text = "Ulica jest pusta i spokojna."

    result = _ensure_combat_start_tag(conn, 1, player_text, assistant_text, character_id=1)
    conn.close()

    assert "[COMBAT_START:" not in result, "Brak deklaracji ataku = brak wstrzyknięcia"


# ─── FAZA 3: Guard lokalizacji — nie kasuje pending_zaskoczony przy zbliżeniu ─

def _make_conn_for_location_guard(has_enemies: bool) -> sqlite3.Connection:
    """SQLite do testowania _maybe_clear_surprise_on_location_change."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    scene = json.dumps([{"key": "straznik"}]) if has_enemies else "[]"
    conn.executescript(f"""
        CREATE TABLE game_sessions (
            campaign_id INTEGER PRIMARY KEY,
            session_flags TEXT DEFAULT '{{}}',
            scene_enemies TEXT DEFAULT '[]',
            scene_npcs TEXT DEFAULT '[]'
        );
        INSERT INTO game_sessions (campaign_id, session_flags, scene_enemies, scene_npcs)
        VALUES (
            1,
            '{json.dumps({"pending_zaskoczony": True, "state": "NARRATIVE"})}',
            '{scene}',
            '[]'
        );
    """)
    conn.commit()
    return conn


def test_approach_move_preserves_pending_zaskoczony():
    """Ruch zbliżenia (sub-lokacja z wrogami w scenie) NIE kasuje pending_zaskoczony.

    Repro #1054: gracz podszedł bliżej po sukcesie Skradania → guard #1046 mógł
    skasować flagę przed deklaracją ataku.
    """
    from app.api.turns import _maybe_clear_surprise_on_location_change

    conn = _make_conn_for_location_guard(has_enemies=True)
    _maybe_clear_surprise_on_location_change(conn, campaign_id=1)
    conn.commit()

    row = conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()
    sf = json.loads(row["session_flags"] or "{}")
    conn.close()

    assert sf.get("pending_zaskoczony"), (
        "pending_zaskoczony musi zostac zachowane gdy scena miala wrogów "
        "(gracz zbliżał się do celu ataku)"
    )


def test_normal_location_change_clears_pending_zaskoczony():
    """Ruch do lokacji BEZ wrogów (normalna nawigacja) kasuje pending_zaskoczony."""
    from app.api.turns import _maybe_clear_surprise_on_location_change

    conn = _make_conn_for_location_guard(has_enemies=False)
    _maybe_clear_surprise_on_location_change(conn, campaign_id=1)
    conn.commit()

    row = conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()
    sf = json.loads(row["session_flags"] or "{}")
    conn.close()

    assert not sf.get("pending_zaskoczony"), (
        "pending_zaskoczony musi być skasowane gdy scena była pusta "
        "(gracz wyszedł z obszaru spotkania)"
    )


# ─── Backward compat ──────────────────────────────────────────────────────────

def test_negation_still_suppresses_combat_intent():
    """'nie chce zaatakowac' → False (filtr negacji #535 nadal działa)."""
    from app.api.turns import _player_combat_intent

    assert not _player_combat_intent("nie chce zaatakowac go, chce porozmawiac")


def test_existing_combat_intent_verbs_still_work():
    """Istniejące wzorce (atakuje, uderz, strzelam) nadal wykrywane."""
    from app.api.turns import _player_combat_intent

    assert _player_combat_intent("atakuje orka")
    assert _player_combat_intent("uderz go mieczen")
    assert _player_combat_intent("strzelam z luku")
