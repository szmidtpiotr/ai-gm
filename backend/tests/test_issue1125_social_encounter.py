"""TDD: Issue #1125 — PT-D2 Encountery społeczne w sub-lokacjach.

Weryfikacja (z issue):
  - rzut wspólnej puli (PT10 0.20) → przy trafieniu split 50/50 walka vs zdarzenie społeczne
  - split 50/50 deterministyczny
  - kieszonkowiec nalicza gold_event z flagą delayed + licznik tur
  - dymek 💰 pojawia się po N turach (1-3)
  - rozstrzyganie w locie: test umiejętności w tej samej turze; eskalacja do walki TYLKO przy Nat 1
  - backward-compat: istniejący encounter walki (kind='combat') działa jak dotąd
"""
import sys

sys.path.insert(0, "/app")

import pytest

from app.services import social_encounter_service as ses


# ─── Split 50/50 (wspólna pula z PT10) ────────────────────────────────────────

def test_classify_kind_low_roll_is_combat():
    """roll < SPLIT → walka (dolna połowa puli)."""
    assert ses.classify_encounter_kind(0.0) == "combat"
    assert ses.classify_encounter_kind(0.49) == "combat"


def test_classify_kind_high_roll_is_social():
    """roll >= SPLIT → zdarzenie społeczne (górna połowa puli)."""
    assert ses.classify_encounter_kind(0.5) == "social"
    assert ses.classify_encounter_kind(0.99) == "social"


def test_split_is_half():
    """Numbers Policy: split 50/50 (startowy)."""
    assert ses.ENCOUNTER_SOCIAL_SPLIT == 0.5


# ─── Subtypy sub-lokacji ──────────────────────────────────────────────────────

def test_resolve_subtype_alley():
    assert ses.resolve_subtype("zaułek") == "alley"
    assert ses.resolve_subtype("ciemna ulica") == "alley"


def test_resolve_subtype_tavern():
    assert ses.resolve_subtype("karczma") == "tavern"
    assert ses.resolve_subtype("gospoda Pod Kogutem") == "tavern"


def test_resolve_subtype_market():
    assert ses.resolve_subtype("targ") == "market"
    assert ses.resolve_subtype("rynek miejski") == "market"


def test_resolve_subtype_unknown_defaults_to_alley():
    """Nieznany/None subtype → alley (generyczna ulica)."""
    assert ses.resolve_subtype(None) == "alley"
    assert ses.resolve_subtype("cokolwiek") == "alley"


def test_event_pool_per_subtype():
    """Każdy subtyp ma zdefiniowaną pulę zdarzeń (issue: Dla agenta)."""
    assert "pickpocket" in ses.subtype_event_keys("alley")
    assert "drunk_harassment" in ses.subtype_event_keys("alley")
    assert "card_cheat" in ses.subtype_event_keys("tavern")
    assert "quest_rumor" in ses.subtype_event_keys("tavern")
    assert "tout" in ses.subtype_event_keys("market")
    assert "guard_check" in ses.subtype_event_keys("market")


def test_pick_social_event_returns_definition():
    """pick_social_event zwraca definicję z stat/skill/DC do rozstrzygnięcia."""
    ev = ses.pick_social_event("alley", roll=0.0)
    assert ev["key"] in ses.subtype_event_keys("alley")
    assert "stat" in ev and "skill" in ev and "dc" in ev


# ─── Kieszonkowiec: strata złota 10% cap 50 ───────────────────────────────────

def test_pickpocket_loss_ten_percent():
    """10% złota (startowe)."""
    assert ses.pickpocket_loss(100) == 10
    assert ses.pickpocket_loss(250) == 25


def test_pickpocket_loss_cap_50():
    """Cap 50 szt. — bogaty gracz nie traci więcej niż 50."""
    assert ses.pickpocket_loss(1000) == 50
    assert ses.pickpocket_loss(600) == 50


def test_pickpocket_loss_zero_gold():
    """Brak złota → zero straty (nie ujemne)."""
    assert ses.pickpocket_loss(0) == 0


# ─── Rozstrzyganie w locie + eskalacja tylko przy Nat 1 ──────────────────────

def test_skill_check_success_no_escalation():
    """Sukces testu → brak eskalacji do walki (hook, złapany za rękę)."""
    r = ses.resolve_skill_check(d20=18, stat_mod=3, skill_rank=1, dc=12)
    assert r["success"] is True
    assert r["escalate_combat"] is False


def test_skill_check_normal_fail_no_escalation():
    """Zwykła porażka (nie Nat 1) → miękka konsekwencja, NADAL bez walki."""
    r = ses.resolve_skill_check(d20=5, stat_mod=0, skill_rank=0, dc=16)
    assert r["success"] is False
    assert r["nat1"] is False
    assert r["escalate_combat"] is False


def test_skill_check_nat1_escalates_to_combat():
    """Krytyczna porażka (Nat 1) → JEDYNY przypadek eskalacji do walki."""
    r = ses.resolve_skill_check(d20=1, stat_mod=5, skill_rank=3, dc=8)
    assert r["success"] is False
    assert r["nat1"] is True
    assert r["escalate_combat"] is True


def test_skill_check_proficiency_bonus_rank3():
    """Locked formula: +2 proficiency gdy skill_rank >= 3."""
    # 10 + 0 stat + 3 rank + 2 prof = 15 >= DC 15 → sukces
    r = ses.resolve_skill_check(d20=10, stat_mod=0, skill_rank=3, dc=15)
    assert r["success"] is True


# ─── Opóźniony dymek 💰 (gold_events delayed) ─────────────────────────────────

def test_schedule_gold_notice_adds_pending():
    """Kradzież planuje opóźnione powiadomienie w session_flags."""
    flags = {}
    ses.schedule_gold_notice(flags, amount=10, delay_turns=2, label="sakiewka lżejsza")
    pending = flags["pending_gold_notices"]
    assert len(pending) == 1
    assert pending[0]["amount"] == 10
    assert pending[0]["reveal_in"] == 2


def test_pop_gold_notices_not_due_yet():
    """Przed upływem N tur — nic nie zwraca, licznik maleje."""
    flags = {}
    ses.schedule_gold_notice(flags, amount=10, delay_turns=2, label="x")
    due = ses.pop_due_gold_notices(flags)
    assert due == []
    assert flags["pending_gold_notices"][0]["reveal_in"] == 1


def test_pop_gold_notices_fires_after_n_turns():
    """Po N turach dymek się pojawia i znika z kolejki."""
    flags = {}
    ses.schedule_gold_notice(flags, amount=10, delay_turns=2, label="sakiewka lżejsza")
    ses.pop_due_gold_notices(flags)          # tura 1: reveal_in 2→1, nic
    due = ses.pop_due_gold_notices(flags)     # tura 2: reveal_in 1→0, ODPALA
    assert len(due) == 1
    assert due[0]["amount"] == 10
    assert due[0]["label"] == "sakiewka lżejsza"
    assert flags["pending_gold_notices"] == []


def test_pop_gold_notices_empty_flags_safe():
    """Brak pending → pusta lista, bez błędu."""
    assert ses.pop_due_gold_notices({}) == []


# ─── Koordynator: build_social_outcome ────────────────────────────────────────

def test_build_social_outcome_pickpocket_schedules_notice():
    """Pełny bieg: pickpocket → strata złota policzona + notice zaplanowany."""
    flags = {}
    out = ses.build_social_outcome(
        event_key="pickpocket",
        subtype="alley",
        gold=200,
        skill_check={"success": False, "nat1": False, "escalate_combat": False},
        flags=flags,
        delay_turns=2,
    )
    assert out["gold_loss"] == 20            # 10% z 200
    assert out["escalate_combat"] is False
    assert len(flags["pending_gold_notices"]) == 1
    assert flags["pending_gold_notices"][0]["reveal_in"] == 2


def test_build_social_outcome_pickpocket_success_no_loss():
    """Sukces percepcji łapie kieszonkowca za rękę → brak straty złota."""
    flags = {}
    out = ses.build_social_outcome(
        event_key="pickpocket",
        subtype="alley",
        gold=200,
        skill_check={"success": True, "nat1": False, "escalate_combat": False},
        flags=flags,
        delay_turns=2,
    )
    assert out["gold_loss"] == 0
    assert flags.get("pending_gold_notices", []) == []


# ─── Integration (in-memory DB) ───────────────────────────────────────────────

import json
import sqlite3


def _mk_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE game_sessions (id INTEGER PRIMARY KEY, campaign_id INTEGER, session_flags TEXT);
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, is_active INTEGER DEFAULT 1,
            sheet_json TEXT, gold_gp INTEGER, name TEXT DEFAULT 'Bohater'
        );
        CREATE TABLE game_locations (key TEXT PRIMARY KEY, location_subtype TEXT);
        CREATE TABLE character_gold_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER, delta INTEGER,
            source TEXT, campaign_id INTEGER, meta_json TEXT, game_clock_day INTEGER DEFAULT 0
        );
        CREATE TABLE active_combat (campaign_id INTEGER, status TEXT);
        """
    )
    return conn


def test_pop_gold_notices_integration_fires_after_n_turns():
    """turn_pipeline.pop_gold_notices: dymek 💰 dopiero po dojrzeniu licznika."""
    from app.services.turn_pipeline import pop_gold_notices

    conn = _mk_db()
    flags = {}
    ses.schedule_gold_notice(flags, amount=15, delay_turns=2, label="sakiewka lżejsza")
    conn.execute(
        "INSERT INTO game_sessions (id, campaign_id, session_flags) VALUES (1, 77, ?)",
        (json.dumps(flags),),
    )
    conn.commit()

    assert pop_gold_notices(conn, 77) is None          # tura 1 — jeszcze nie
    hint = pop_gold_notices(conn, 77)                    # tura 2 — ODPALA
    assert hint is not None and "15" in hint and "💰" in hint
    assert pop_gold_notices(conn, 77) is None            # kolejka pusta


def test_resolve_social_encounter_pickpocket_deducts_and_schedules(monkeypatch):
    """_resolve_social_encounter: social + porażka pickpocket → złoto -10%, notice."""
    from app.routers import local_map

    conn = _mk_db()
    conn.execute(
        "INSERT INTO game_sessions (id, campaign_id, session_flags) VALUES (1, 88, '{}')"
    )
    conn.execute(
        "INSERT INTO characters (id, campaign_id, is_active, sheet_json, gold_gp) "
        "VALUES (5, 88, 1, ?, 300)",
        (json.dumps({"stats": {"WIS": 8}, "skills": {}}),),  # WIS 8 → mod -1
    )
    conn.execute(
        "INSERT INTO game_locations (key, location_subtype) VALUES ('zaulek_1', 'zaułek')"
    )
    conn.commit()

    # Force: social branch, pickpocket event, low d20 (fail, not Nat1)
    monkeypatch.setattr(local_map.random, "random", lambda: 0.9)          # → social
    monkeypatch.setattr(local_map.random, "randint", lambda a, b: 5)      # d20=5 fail
    monkeypatch.setattr(ses.random, "choice", lambda seq: seq[0])         # → pickpocket
    monkeypatch.setattr(ses.random, "randint", lambda a, b: 2)            # delay 2 tur

    enc = {"enemy_key": "bandit", "hex_label": "zaułek"}
    hint: dict = {"destination_label": "zaułek"}
    flags: dict = {}
    local_map._resolve_social_encounter(
        conn, 88, {"label": "zaułek"}, "zaulek_1", enc, flags, hint
    )

    # Enemy dropped (soft social, no combat), kind=social
    assert enc["kind"] == "social"
    assert "enemy_key" not in enc
    assert enc["social"]["event"] == "pickpocket"
    assert enc["social"]["gold_loss"] == 30              # 10% z 300

    # Gold actually deducted + logged
    row = conn.execute("SELECT gold_gp FROM characters WHERE id = 5").fetchone()
    assert row["gold_gp"] == 270
    log = conn.execute(
        "SELECT delta, source FROM character_gold_log WHERE character_id = 5"
    ).fetchone()
    assert log["delta"] == -30 and log["source"] == "pickpocket"

    # Delayed notice scheduled in the flags dict (caller persists it to session_flags)
    assert len(flags["pending_gold_notices"]) == 1
    assert flags["pending_gold_notices"][0]["reveal_in"] == 2
    # hint carries social flavor for the narrator
    assert hint["kind"] == "social" and hint["social_event"] == "pickpocket"


def test_resolve_social_encounter_combat_half_unchanged(monkeypatch):
    """Dolna połowa puli → walka nietknięta (backward-compat PT10)."""
    from app.routers import local_map

    conn = _mk_db()
    monkeypatch.setattr(local_map.random, "random", lambda: 0.1)          # → combat
    enc = {"enemy_key": "bandit", "hex_label": "zaułek"}
    hint: dict = {"destination_label": "zaułek"}
    local_map._resolve_social_encounter(
        conn, 99, {"label": "zaułek"}, "zaulek_1", enc, {}, hint
    )
    assert enc["kind"] == "combat"
    assert enc["enemy_key"] == "bandit"    # combat encounter untouched
    assert "social" not in enc


# ── PT-F4 #1138: 💰 gold notice must freeze during combat ─────────────────────

import json as _json
import sqlite3 as _sq


def _mk_notice_db(reveal_in=2, in_combat=False):
    c = _sq.connect(":memory:")
    c.row_factory = _sq.Row
    c.executescript(
        "CREATE TABLE game_sessions (id INTEGER PRIMARY KEY, campaign_id INTEGER, session_flags TEXT);"
        "CREATE TABLE active_combat (campaign_id INTEGER, status TEXT);"
    )
    flags = {"pending_gold_notices": [{"amount": 25, "reveal_in": reveal_in, "label": "sakiewka"}]}
    c.execute("INSERT INTO game_sessions (id, campaign_id, session_flags) VALUES (1, 1, ?)", (_json.dumps(flags),))
    if in_combat:
        c.execute("INSERT INTO active_combat (campaign_id, status) VALUES (1, 'active')")
    c.commit()
    return c


def test_ptf4_gold_notice_frozen_in_combat():
    """PT-F4: while combat is active the 💰 bubble must not fire and the counter must not tick."""
    from app.services.turn_pipeline import pop_gold_notices
    c = _mk_notice_db(reveal_in=2, in_combat=True)
    assert pop_gold_notices(c, 1) is None, "no 💰 bubble mid-combat"
    flags = _json.loads(c.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()[0])
    assert flags["pending_gold_notices"][0]["reveal_in"] == 2, "counter must be frozen (not decremented) during combat"


def test_ptf4_gold_notice_fires_after_combat():
    """PT-F4: with no combat the counter ticks and the bubble fires when it matures."""
    from app.services.turn_pipeline import pop_gold_notices
    c = _mk_notice_db(reveal_in=2, in_combat=False)
    assert pop_gold_notices(c, 1) is None            # reveal_in 2 -> 1, not due
    line = pop_gold_notices(c, 1)                     # 1 -> 0, due
    assert line is not None and "💰" in line, "bubble must fire once the delay elapses"


# ── PT-F4 #1138: soft social marks the local hex cleared (no infinite re-roll) ─

def test_ptf4_social_marks_hex_cleared(monkeypatch):
    """PT-F4: a resolved soft social must add the hex to cleared_local_hexes so a
    repeated pass-through can't re-roll the pickpocket and drain gold forever."""
    from app.services import social_encounter_service as ses
    from app.routers import local_map

    c = _sq.connect(":memory:")
    c.row_factory = _sq.Row
    c.executescript(
        "CREATE TABLE game_sessions (id INTEGER PRIMARY KEY, campaign_id INTEGER, session_flags TEXT);"
        "CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, sheet_json TEXT, gold_gp INTEGER, is_active INTEGER);"
        "CREATE TABLE game_locations (id INTEGER PRIMARY KEY, key TEXT, location_subtype TEXT);"
    )
    c.execute("INSERT INTO game_sessions (id, campaign_id, session_flags) VALUES (1, 1, '{}')")
    c.execute("INSERT INTO characters (id, campaign_id, sheet_json, gold_gp, is_active) VALUES (1, 1, '{}', 100, 1)")
    c.execute("INSERT INTO game_locations (id, key, location_subtype) VALUES (1, 'zaulek', 'zaułek')")
    c.commit()

    # Force a guaranteed encounter and the social half of the 50/50.
    monkeypatch.setattr(local_map.random, "random", lambda: 0.0)  # _check_local_encounter: 0 < 1.0 -> hit
    monkeypatch.setattr(ses, "classify_encounter_kind", lambda _r: "social")

    target = {"id": 42, "label": "Zaułek", "encounter_chance": 1.0, "encounter_pool": []}
    enc = local_map.roll_local_encounter(c, 1, target, "zaulek")

    assert enc is not None and enc.get("kind") == "social"
    flags = _json.loads(c.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()[0])
    assert 42 in (flags.get("cleared_local_hexes") or []), "soft social must clear the hex to stop re-rolls"
