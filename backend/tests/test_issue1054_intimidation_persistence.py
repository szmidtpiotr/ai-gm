"""TDD: Issue #1054 (część 2) — sukces Zastraszania musi zostawiać trwały stan.

Sandbox repro (kampania 8888911): Skradanie kryt + Zastraszanie sukces →
tura później NPC odmawia oddania broni, bo wynik testu nigdzie nie jest
zapisany i narrator go neguje.

Cztery elementy fixa:
1. Sukces Zastraszania → session_flags.intimidated_enemies (targets + TTL)
2. Reguła narratora: blok ZASTRASZENIE wstrzykiwany dopóki stan aktywny
3. Bonus przewagi z gate skaluje się wg jakości Skradania (+2 sukces / +4 kryt)
4. advantage_bonus widoczny w logu rzutów (dice_rolls.modifiers)
"""
import json
import sqlite3
import sys

sys.path.insert(0, "/app")


def _mem_conn(session_flags: dict | None = None, scene_enemies=None, max_turn: int = 3) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE game_sessions (
            campaign_id INTEGER PRIMARY KEY,
            session_flags TEXT DEFAULT '{}',
            scene_enemies TEXT DEFAULT '[]',
            scene_npcs TEXT DEFAULT '[]'
        );
        CREATE TABLE campaign_turns (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER,
            turn_number REAL
        );
    """)
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, session_flags, scene_enemies) VALUES (1, ?, ?)",
        (json.dumps(session_flags or {}), json.dumps(scene_enemies if scene_enemies is not None else ["bandit"])),
    )
    for i in range(1, max_turn + 1):
        conn.execute("INSERT INTO campaign_turns (campaign_id, turn_number) VALUES (1, ?)", (float(i),))
    conn.commit()
    return conn


# ─── 1. Trwały stan po sukcesie Zastraszania ─────────────────────────────────

def test_intimidation_success_sets_intimidated_enemies_flag():
    """Sukces Zastraszania zapisuje intimidated_enemies z celami sceny i TTL."""
    from app.api.turns import _apply_intimidation_persistence, INTIMIDATION_TTL_TURNS

    conn = _mem_conn(max_turn=3)
    session_flags = {}
    entry = _apply_intimidation_persistence(
        conn, 1, session_flags,
        pending={"skill_key": "intimidation"},
        result={"success": True, "nat1": False, "outcome": "SUCCESS"},
    )
    assert entry is not None, "sukces Zastraszania musi zwrocic wpis stanu"
    flag = session_flags.get("intimidated_enemies")
    assert flag, "session_flags.intimidated_enemies musi byc ustawione"
    assert flag["targets"] == ["bandit"]
    assert flag["expires_at_turn"] == 3 + INTIMIDATION_TTL_TURNS


def test_intimidation_failure_does_not_set_flag():
    """Nieudany test NIE zostawia stanu."""
    from app.api.turns import _apply_intimidation_persistence

    conn = _mem_conn()
    session_flags = {}
    entry = _apply_intimidation_persistence(
        conn, 1, session_flags,
        pending={"skill_key": "intimidation"},
        result={"success": False, "nat1": False, "outcome": "FAILURE"},
    )
    assert entry is None
    assert "intimidated_enemies" not in session_flags


def test_other_skill_success_does_not_set_flag():
    """Backward compat: inne skille nie dotykaja stanu zastraszenia."""
    from app.api.turns import _apply_intimidation_persistence

    conn = _mem_conn()
    session_flags = {}
    entry = _apply_intimidation_persistence(
        conn, 1, session_flags,
        pending={"skill_key": "stealth"},
        result={"success": True, "nat1": False, "outcome": "SUCCESS"},
    )
    assert entry is None
    assert "intimidated_enemies" not in session_flags


def test_scene_enemies_as_dicts_supported():
    """scene_enemies bywa lista dictow ({key,name,...}) — cele wyciagane poprawnie."""
    from app.api.turns import _apply_intimidation_persistence

    conn = _mem_conn(scene_enemies=[{"key": "straznik", "name": "Straznik", "hp_current": 20}])
    session_flags = {}
    _apply_intimidation_persistence(
        conn, 1, session_flags,
        pending={"skill_key": "intimidation"},
        result={"success": True, "nat1": False, "outcome": "SUCCESS"},
    )
    assert session_flags["intimidated_enemies"]["targets"] == ["straznik"]


# ─── 2. Blok narratora ───────────────────────────────────────────────────────

def _messages_stub():
    return [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "oddaj mi swoja bron i sakiewke"},
    ]


def test_inject_intimidated_context_active():
    """Aktywny stan → blok ZASTRASZENIE jako osobna wiadomosc system przed user."""
    from app.services.game_engine import _inject_intimidated_context

    conn = _mem_conn(
        session_flags={"intimidated_enemies": {"targets": ["bandit"], "set_turn": 2, "expires_at_turn": 8, "outcome": "SUCCESS"}},
        max_turn=3,
    )
    messages = _messages_stub()
    _inject_intimidated_context(conn, 1, messages)
    assert len(messages) == 3, "blok musi byc wstawiony jako osobna wiadomosc"
    injected = messages[-2]
    assert injected["role"] == "system"
    assert "ZASTRASZ" in injected["content"].upper()
    assert "bandit" in injected["content"]
    assert "test" in injected["content"].lower(), "regula musi wymagac testu przeciwstawnego dla oporu"


def test_inject_intimidated_context_expired_cleans_flag():
    """Stan po TTL → brak bloku + flaga lazy-usunieta z DB."""
    from app.services.game_engine import _inject_intimidated_context

    conn = _mem_conn(
        session_flags={"intimidated_enemies": {"targets": ["bandit"], "set_turn": 1, "expires_at_turn": 2, "outcome": "SUCCESS"}},
        max_turn=9,
    )
    messages = _messages_stub()
    _inject_intimidated_context(conn, 1, messages)
    assert len(messages) == 2, "wygasly stan nie moze wstrzykiwac bloku"
    sf = json.loads(conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()[0])
    assert "intimidated_enemies" not in sf, "wygasla flaga musi byc usunieta z DB"


def test_inject_intimidated_context_no_flag_noop():
    """Backward compat: brak flagi → messages nietkniete."""
    from app.services.game_engine import _inject_intimidated_context

    conn = _mem_conn(session_flags={})
    messages = _messages_stub()
    _inject_intimidated_context(conn, 1, messages)
    assert len(messages) == 2


# ─── 3. Skalowanie bonusu przewagi ───────────────────────────────────────────

def test_gate_advantage_bonus_default_2():
    from app.api.turns import _gate_advantage_bonus

    assert _gate_advantage_bonus({}) == 2
    assert _gate_advantage_bonus({"pending_zaskoczony_quality": "success"}) == 2


def test_gate_advantage_bonus_critical_4():
    from app.api.turns import _gate_advantage_bonus

    assert _gate_advantage_bonus({"pending_zaskoczony_quality": "critical_success"}) == 4
    assert _gate_advantage_bonus({"pending_zaskoczony_quality": "CRITICAL_SUCCESS"}) == 4


def test_build_advantage_gate_hint_reflects_bonus():
    """Hint przycisku Zastraszenie pokazuje faktyczny bonus (+4 przy krycie)."""
    from app.services.combat_service import build_advantage_gate

    gate = build_advantage_gate("stealth", advantage_bonus=4)
    intim = next(o for o in gate["options"] if o["id"] == "intimidate")
    assert "+4" in intim["hint"]
    # backward compat — bez parametru nadal +2
    gate2 = build_advantage_gate("stealth")
    intim2 = next(o for o in gate2["options"] if o["id"] == "intimidate")
    assert "+2" in intim2["hint"]


# ─── 4. advantage_bonus w logu rzutow ────────────────────────────────────────

def test_advantage_bonus_recorded_in_dice_log(monkeypatch):
    """resolve_skill_test przekazuje advantage_bonus do record_dice_roll."""
    from app.services import dice_log_service
    from app.services.skill_service import resolve_skill_test

    captured = {}

    def _fake_record(*args, **kwargs):
        captured.update(kwargs)
        return 1

    monkeypatch.setattr(dice_log_service, "record_dice_roll", _fake_record)

    conn = _mem_conn()
    resolve_skill_test(
        d20_roll=15,
        pending={
            "skill_key": "intimidation",
            "skill_label": "Zastraszanie",
            "modifier_breakdown": {"total": 3, "stat_mod": 1, "skill_rank": 0, "proficiency": 0, "advantage_bonus": 2},
            "counter": {"counter_type": "dc", "dc": 12},
        },
        conn=conn,
        campaign_id=1,
        character_id=1,
    )
    mods = captured.get("modifiers") or {}
    assert mods.get("advantage_bonus") == 2, "advantage_bonus musi trafic do dice_rolls.modifiers"


# ─── Czyszczenie przy zmianie lokacji ────────────────────────────────────────

def test_location_change_clears_intimidation_even_with_enemies():
    """Zmiana lokacji zawsze kasuje stan zastraszenia (per-scena), ale
    pending_zaskoczony przetrwa gdy scena miala wrogow (zbliżanie #1054)."""
    from app.api.turns import _maybe_clear_surprise_on_location_change

    conn = _mem_conn(
        session_flags={
            "intimidated_enemies": {"targets": ["bandit"], "set_turn": 1, "expires_at_turn": 7},
            "pending_zaskoczony": True,
            "pending_zaskoczony_quality": "critical_success",
        },
        scene_enemies=["bandit"],
    )
    _maybe_clear_surprise_on_location_change(conn, 1)
    sf = json.loads(conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()[0])
    assert "intimidated_enemies" not in sf, "zastraszenie nie podaza za graczem do innej lokacji"
    assert sf.get("pending_zaskoczony") is True, "przewaga zaskoczenia przetrwa ruch przy wrogach w scenie"


def test_location_change_from_empty_scene_clears_surprise_and_quality():
    """Backward compat #1046: pusta scena → pending_zaskoczony + quality kasowane."""
    from app.api.turns import _maybe_clear_surprise_on_location_change

    conn = _mem_conn(
        session_flags={"pending_zaskoczony": True, "pending_zaskoczony_quality": "success"},
        scene_enemies=[],
    )
    _maybe_clear_surprise_on_location_change(conn, 1)
    sf = json.loads(conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()[0])
    assert "pending_zaskoczony" not in sf
    assert "pending_zaskoczony_quality" not in sf
