"""TDD: Issue #548 — U32 travel pills z prawdziwych danych + eskalacja anty-stuck w UI."""
import json
import sqlite3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─── Helper: minimal in-memory DB ────────────────────────────────────────────

def _make_db(hexes=None, locations=None, gm_plan=None):
    """Create a minimal in-memory SQLite DB with world_hexes + game_locations."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE world_hexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            q INTEGER NOT NULL, r INTEGER NOT NULL,
            hex_type TEXT NOT NULL DEFAULT 'plains',
            label TEXT,
            atmosphere TEXT,
            encounter_chance REAL NOT NULL DEFAULT 0.15,
            encounter_pool TEXT NOT NULL DEFAULT '[]',
            location_key TEXT,
            discovered_in_campaign_id INTEGER,
            created_by_gm INTEGER NOT NULL DEFAULT 0,
            created_by_campaign_id INTEGER,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            parent_hex_id INTEGER,
            map_level INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            label TEXT,
            description TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            safe_for_rest INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE location_connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_key TEXT, to_key TEXT
        );
        CREATE TABLE location_npc_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_key TEXT, npc_key TEXT, is_active INTEGER DEFAULT 1
        );
        CREATE TABLE game_npcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT, name TEXT
        );
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gm_plan_json TEXT
        );
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER, session_flags TEXT
        );
    """)
    if hexes:
        for h in hexes:
            conn.execute(
                "INSERT INTO world_hexes (q, r, hex_type, label, location_key, is_active) VALUES (?,?,?,?,?,1)",
                (h["q"], h["r"], h.get("hex_type", "plains"), h.get("label"), h.get("location_key")),
            )
    if locations:
        for loc in locations:
            conn.execute(
                "INSERT INTO game_locations (key, label, is_active, safe_for_rest) VALUES (?,?,1,?)",
                (loc["key"], loc["label"], loc.get("safe_for_rest", 0)),
            )
    if gm_plan is not None:
        conn.execute("INSERT INTO campaigns (id, gm_plan_json) VALUES (1, ?)", (json.dumps(gm_plan),))
    else:
        conn.execute("INSERT INTO campaigns (id, gm_plan_json) VALUES (1, NULL)")
    conn.commit()
    return conn


def _plan_with_beat(objective_type, objective_value):
    """Build a minimal gm_plan_json with one beat of given objective_type."""
    return {
        "acts": [{
            "act_number": 1,
            "key_beats": [{
                "id": "b1",
                "title": "Test beat",
                "objective_type": objective_type,
                "objective_value": objective_value,
                "visited": False,
            }]
        }]
    }


# ─── Test 1: travel pills z sąsiednich hexów ─────────────────────────────────

def test_travel_pills_built_from_neighbors():
    """_build_travel_pills zwraca pille dla sąsiednich hexów z world_hexes."""
    from app.services.suggested_actions import _build_travel_pills

    conn = _make_db(
        hexes=[
            {"q": 0, "r": 0, "hex_type": "plains", "label": "Start"},
            {"q": 1, "r": 0, "hex_type": "forest", "label": None, "location_key": "loc_inn"},
            {"q": 0, "r": 1, "hex_type": "plains", "label": "Skały"},
        ],
        locations=[{"key": "loc_inn", "label": "Karczma Pod Bukiem"}],
    )
    session_flags = {"current_hex": {"q": 0, "r": 0}, "turns_at_location": 6}
    pills = _build_travel_pills(conn, campaign_id=1, session_flags=session_flags)

    assert len(pills) >= 1, "powinien być co najmniej 1 pill dla sąsiedniego hexu"
    actions = [p.action for p in pills]
    assert any("TRAVEL:" in a for a in actions), "akcja powinna mieć prefix TRAVEL:"
    labels = [p.label for p in pills]
    assert any("Karczma Pod Bukiem" in lbl for lbl in labels), "etykieta lokacji powinna być widoczna w pilu"


def test_travel_pills_action_format():
    """Akcja pilla TRAVEL ma format TRAVEL:{q}:{r} z prawdziwymi współrzędnymi."""
    from app.services.suggested_actions import _build_travel_pills

    conn = _make_db(
        hexes=[
            {"q": 0, "r": 0},
            {"q": -1, "r": 1, "label": "Wzgórze"},
        ],
    )
    session_flags = {"current_hex": {"q": 0, "r": 0}}
    pills = _build_travel_pills(conn, campaign_id=1, session_flags=session_flags)

    for p in pills:
        act = p.action
        assert act.startswith("TRAVEL:"), f"akcja powinna zaczynać się od TRAVEL:, got: {act}"
        parts = act.split(":")
        assert len(parts) == 3, f"format TRAVEL:q:r, got: {act}"
        int(parts[1])  # q musi być int
        int(parts[2])  # r musi być int


def test_travel_pills_type_field():
    """Pille podróży mają type='travel' dla wyróżnienia w UI."""
    from app.services.suggested_actions import _build_travel_pills

    conn = _make_db(
        hexes=[
            {"q": 0, "r": 0},
            {"q": 1, "r": 0, "label": "Las"},
        ],
    )
    session_flags = {"current_hex": {"q": 0, "r": 0}}
    pills = _build_travel_pills(conn, campaign_id=1, session_flags=session_flags)

    for p in pills:
        assert p.type == "travel", f"każdy pill podróży powinien mieć type='travel', got: {p}"


def test_travel_pills_no_current_hex():
    """Jeśli brak current_hex → brak pilli (bezpieczny fallback)."""
    from app.services.suggested_actions import _build_travel_pills

    conn = _make_db(hexes=[{"q": 0, "r": 0}])
    session_flags = {}  # brak current_hex
    pills = _build_travel_pills(conn, campaign_id=1, session_flags=session_flags)

    assert pills == [], "bez current_hex nie powinno być pilli"


# ─── Test 2: pille questowe (visit_location) ─────────────────────────────────

def test_travel_pills_quest_target():
    """Aktywny beat visit_location → pill do celu w zestawie."""
    from app.services.suggested_actions import _build_travel_pills

    conn = _make_db(
        hexes=[
            {"q": 0, "r": 0},
            {"q": 2, "r": 0, "location_key": "wieza_magow"},
        ],
        locations=[{"key": "wieza_magow", "label": "Wieża Magów"}],
        gm_plan=_plan_with_beat("visit_location", "Wieża Magów"),
    )
    session_flags = {"current_hex": {"q": 0, "r": 0}}
    pills = _build_travel_pills(conn, campaign_id=1, session_flags=session_flags)

    labels = [p.label for p in pills]
    assert any("Wieża Magów" in lbl for lbl in labels), (
        f"pill dla quest target 'Wieża Magów' powinien być w zestawie. Got labels: {labels}"
    )


def test_travel_pills_quest_target_no_duplicate():
    """Quest target już w pillach z sąsiedztwa → bez duplikatu."""
    from app.services.suggested_actions import _build_travel_pills

    conn = _make_db(
        hexes=[
            {"q": 0, "r": 0},
            {"q": 1, "r": 0, "location_key": "wieza_magow"},
        ],
        locations=[{"key": "wieza_magow", "label": "Wieża Magów"}],
        gm_plan=_plan_with_beat("visit_location", "Wieża Magów"),
    )
    session_flags = {"current_hex": {"q": 0, "r": 0}}
    pills = _build_travel_pills(conn, campaign_id=1, session_flags=session_flags)

    actions = [p.action for p in pills]
    assert len(actions) == len(set(actions)), "nie powinno być duplikatów akcji TRAVEL"


def test_travel_pills_quest_visited_beat_skipped():
    """Beat już odwiedzony (visited=True) → nie generuje pilla questowego."""
    from app.services.suggested_actions import _build_travel_pills

    plan = _plan_with_beat("visit_location", "Wieża Magów")
    plan["acts"][0]["key_beats"][0]["visited"] = True

    conn = _make_db(
        hexes=[
            {"q": 0, "r": 0},
            {"q": 2, "r": 0, "location_key": "wieza_magow"},
        ],
        locations=[{"key": "wieza_magow", "label": "Wieża Magów"}],
        gm_plan=plan,
    )
    session_flags = {"current_hex": {"q": 0, "r": 0}}
    pills = _build_travel_pills(conn, campaign_id=1, session_flags=session_flags)

    labels = [p.label for p in pills]
    assert not any("Wieża Magów" in lbl for lbl in labels), (
        "odwiedzony beat nie powinien generować pilla"
    )


# ─── Test 3: eskalacja — turns_at_location ───────────────────────────────────

def test_build_suggested_actions_travel_pills_at_5_turns():
    """build_suggested_actions zwraca pille travel przy turns_at_location >= 5."""
    from app.services.suggested_actions import build_suggested_actions

    conn = _make_db(
        hexes=[
            {"q": 0, "r": 0},
            {"q": 1, "r": 0, "label": "Dolina"},
        ],
    )
    session_flags = {
        "current_hex": {"q": 0, "r": 0},
        "turns_at_location": 5,
        "state": "NARRATIVE",
    }
    actions = build_suggested_actions(
        conn=conn, campaign_id=1, character_id=99,
        game_state="NARRATIVE", session_flags=session_flags,
    )

    travel_actions = [a for a in actions if a.get("type") == "travel"]
    assert len(travel_actions) >= 1, (
        f"przy turns_at_location=5 powinny być pille travel. Got: {actions}"
    )


def test_build_suggested_actions_no_travel_pills_below_5_turns():
    """Poniżej 5 tur bez ruchu — brak pilli sąsiednich (quest target może być)."""
    from app.services.suggested_actions import build_suggested_actions

    conn = _make_db(
        hexes=[
            {"q": 0, "r": 0},
            {"q": 1, "r": 0, "label": "Dolina"},
        ],
    )
    session_flags = {
        "current_hex": {"q": 0, "r": 0},
        "turns_at_location": 3,
        "state": "NARRATIVE",
    }
    actions = build_suggested_actions(
        conn=conn, campaign_id=1, character_id=99,
        game_state="NARRATIVE", session_flags=session_flags,
    )

    # Sąsiednie pille NIE powinny się pojawić przy 3 turach (brak quest target)
    neighbor_travel = [
        a for a in actions
        if a.get("type") == "travel" and "Dolina" in a.get("label", "")
    ]
    assert len(neighbor_travel) == 0, (
        f"przy turns_at_location=3 nie powinno być pilli sąsiednich. Got: {actions}"
    )


# ─── Test 4: SuggestedAction.type pole w to_dict() ──────────────────────────

def test_suggested_action_type_field_serialized():
    """SuggestedAction z type='travel' serializuje type do dict."""
    from app.services.suggested_actions import SuggestedAction

    sa = SuggestedAction(label="→ Las (1h)", action="TRAVEL:1:0", type="travel")
    d = sa.to_dict()
    assert d.get("type") == "travel", f"to_dict() powinno zawierać type='travel'. Got: {d}"


def test_suggested_action_without_type_no_type_key():
    """SuggestedAction bez type → to_dict() nie zwraca klucza 'type'."""
    from app.services.suggested_actions import SuggestedAction

    sa = SuggestedAction(label="Atakuj", action="ATTACK")
    d = sa.to_dict()
    assert "type" not in d, f"to_dict() bez type nie powinno mieć klucza 'type'. Got: {d}"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_build_suggested_actions_combat_still_works():
    """Tryb COMBAT nadal zwraca Atakuj/Uciekaj/Użyj — bez regresji."""
    from app.services.suggested_actions import build_suggested_actions

    conn = _make_db()
    session_flags = {"state": "COMBAT"}
    actions = build_suggested_actions(
        conn=conn, campaign_id=1, character_id=99,
        game_state="COMBAT", session_flags=session_flags,
    )

    action_strs = [a["action"] for a in actions]
    assert "ATTACK" in action_strs, "COMBAT mode musi mieć akcję ATTACK"


def test_build_suggested_actions_no_hex_no_travel_pills():
    """Jeśli brak current_hex → brak pilli travel (bezpieczny fallback)."""
    from app.services.suggested_actions import build_suggested_actions

    conn = _make_db()
    session_flags = {
        "turns_at_location": 10,
        "state": "NARRATIVE",
        # brak current_hex
    }
    actions = build_suggested_actions(
        conn=conn, campaign_id=1, character_id=99,
        game_state="NARRATIVE", session_flags=session_flags,
    )

    travel = [a for a in actions if a.get("type") == "travel"]
    assert travel == [], f"bez current_hex brak pilli travel. Got: {travel}"
