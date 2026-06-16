"""TDD: Unified combat-gate guard — #535 / #596 / #534 / #520.

One coherent guard around combat-start covering:
  (a) #535 — negation of attack intent ("nie atakuję" / "nic nie atakuję")
      MUST suppress tag injection.
  (b) #596 — enemy must be present in the current scene/narrative; a bare
      catalog hit (game_config_enemies) is NOT enough.
  (c) #534 — a friendly quest-giver NPC must never become a combat target.
  (d) #520 — combative GM narration without a tag MUST inject the tag
      (reverse direction), but only for a target that is actually present.

All deterministic — no LLM, in-memory SQLite only.
"""
import sys
import os
import sqlite3
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE game_sessions (
            campaign_id    INTEGER PRIMARY KEY,
            session_flags  TEXT NOT NULL DEFAULT '{}',
            scene_enemies  TEXT NOT NULL DEFAULT '[]',
            scene_npcs     TEXT NOT NULL DEFAULT '[]'
        );
        CREATE TABLE game_config_enemies (
            key       TEXT PRIMARY KEY,
            label     TEXT,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE campaign_known_npcs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            npc_name    TEXT NOT NULL
        );
        CREATE TABLE campaign_turns (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id    INTEGER NOT NULL,
            assistant_text TEXT
        );
        CREATE TABLE active_combat (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            status      TEXT DEFAULT 'active'
        );
    """)
    return conn


def _seed_session(conn, campaign_id=1, scene_enemies=None, scene_npcs=None):
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, scene_enemies, scene_npcs) VALUES (?,?,?)",
        (campaign_id,
         json.dumps(scene_enemies or []),
         json.dumps(scene_npcs or [])),
    )
    conn.commit()


# ─────────────────────────────────────────────────────────────────────────────
# (a) #535 — negation suppresses combat intent
# ─────────────────────────────────────────────────────────────────────────────

def test_negation_nic_nie_atakuje_is_not_intent():
    """The exact live-repro phrasing must NOT count as attack intent."""
    from app.api.turns import _player_combat_intent
    txt = ("Nic nie atakuję. Chowam laskę za pas i spokojnie podchodzę do "
           "uratowanego chłopaka, żeby zapytać co się stało.")
    assert _player_combat_intent(txt) is False


def test_negation_nie_walcze_is_not_intent():
    from app.api.turns import _player_combat_intent
    assert _player_combat_intent("Nie walczę z nimi, opuszczam broń.") is False


def test_negation_nie_atakuje_nikogo_is_not_intent():
    from app.api.turns import _player_combat_intent
    assert _player_combat_intent("Nie atakuję nikogo, chcę tylko porozmawiać.") is False


def test_positive_atakuje_goblina_is_intent():
    """Positive control — plain attack still detected."""
    from app.api.turns import _player_combat_intent
    assert _player_combat_intent("Atakuję goblina mieczem!") is True


def test_negation_does_not_swallow_real_attack_after_it():
    """Negation only suppresses the directly-negated verb, not a later attack."""
    from app.api.turns import _player_combat_intent
    # "nie rozmawiam" is negated, but "atakuję" stands → still intent.
    assert _player_combat_intent("Nie rozmawiam z nim — atakuję go toporem!") is True


# ─────────────────────────────────────────────────────────────────────────────
# (b) #596 — enemy presence required; bare catalog hit is NOT enough
# ─────────────────────────────────────────────────────────────────────────────

def test_scene_enemy_is_valid():
    """Regression: enemy in scene_enemies is a valid target."""
    from app.api.turns import _validate_combat_start_target
    conn = _make_db()
    _seed_session(conn, 1, scene_enemies=[{"key": "goblin_scout", "name": "Goblin Scout"}])
    valid, reason = _validate_combat_start_target(conn, 1, "goblin_scout", "")
    assert valid is True and reason == "", (valid, reason)


def test_catalog_enemy_absent_from_scene_is_rejected():
    """#596: enemy exists in catalog but is NOT in scene nor narrative → REJECT."""
    from app.api.turns import _validate_combat_start_target
    conn = _make_db()
    _seed_session(conn, 1)
    conn.execute("INSERT INTO game_config_enemies (key, label) VALUES ('goblin', 'Goblin')")
    conn.commit()
    valid, reason = _validate_combat_start_target(conn, 1, "goblin", "Chłopak dziękuje ci za ratunek.")
    assert valid is False, "catalog-only enemy must not pass"
    assert reason == "combat_target_not_present", reason


def test_catalog_enemy_named_in_narrative_is_valid():
    """GM ambush: enemy newly introduced in THIS turn's narration → present → valid."""
    from app.api.turns import _validate_combat_start_target
    conn = _make_db()
    _seed_session(conn, 1)
    conn.execute("INSERT INTO game_config_enemies (key, label) VALUES ('goblin', 'Goblin')")
    conn.commit()
    narr = "Między pniami miga zgarbiona sylwetka — goblin warczy i rusza na ciebie!"
    valid, reason = _validate_combat_start_target(conn, 1, "goblin", narr)
    assert valid is True and reason == "", (valid, reason)


def test_stale_enemy_from_finished_fight_is_rejected():
    """#535 core: wolf from a finished fight, peaceful current narration → REJECT."""
    from app.api.turns import _validate_combat_start_target
    conn = _make_db()
    _seed_session(conn, 1)
    conn.execute("INSERT INTO game_config_enemies (key, label) VALUES ('wolf', 'Wilk')")
    conn.commit()
    peaceful = "Chłopak dziękuje ci i opowiada o cieniu między sosnami."
    valid, reason = _validate_combat_start_target(conn, 1, "wolf", peaceful)
    assert valid is False, "dead/absent wolf must not pass"
    assert reason == "combat_target_not_present", reason


# ─────────────────────────────────────────────────────────────────────────────
# (c) #534 — friendly NPC is never a valid target
# ─────────────────────────────────────────────────────────────────────────────

def test_known_npc_is_rejected_as_friendly():
    from app.api.turns import _validate_combat_start_target
    conn = _make_db()
    _seed_session(conn, 1)
    conn.execute("INSERT INTO campaign_known_npcs (campaign_id, npc_name) VALUES (1, 'Starzec')")
    conn.commit()
    valid, reason = _validate_combat_start_target(conn, 1, "Starzec", "Starzec patrzy na ciebie.")
    assert valid is False
    assert reason == "combat_target_friendly_npc", reason


def test_scene_npc_is_rejected_as_friendly():
    from app.api.turns import _validate_combat_start_target
    conn = _make_db()
    _seed_session(conn, 1, scene_npcs=[{"key": "kupiec_jan", "name": "Kupiec Jan"}])
    valid, reason = _validate_combat_start_target(conn, 1, "kupiec_jan", "")
    assert valid is False and reason == "combat_target_friendly_npc", reason


def test_unknown_target_is_rejected():
    from app.api.turns import _validate_combat_start_target
    conn = _make_db()
    _seed_session(conn, 1)
    valid, reason = _validate_combat_start_target(conn, 1, "Xyzzy", "")
    assert valid is False and reason == "combat_target_unknown", reason


# ─────────────────────────────────────────────────────────────────────────────
# (d) injection both ways — _ensure_combat_start_tag
# ─────────────────────────────────────────────────────────────────────────────

def test_injection_suppressed_on_negation():
    """#535 end-to-end: negated intent → NO [COMBAT_START] injected."""
    from app.api.turns import _ensure_combat_start_tag
    conn = _make_db()
    _seed_session(conn, 1)
    conn.execute("INSERT INTO game_config_enemies (key, label) VALUES ('wolf', 'Wilk')")
    # a stale wolf mention sits in a previous turn
    conn.execute("INSERT INTO campaign_turns (campaign_id, assistant_text) VALUES (1, 'Wilk pada martwy.')")
    conn.commit()
    player = "Nic nie atakuję. Chowam laskę za pas i podchodzę do chłopaka."
    out = _ensure_combat_start_tag(conn, 1, player, "Chłopak dziękuje ci za ratunek.")
    assert "[COMBAT_START" not in out, out


def test_injection_suppressed_when_enemy_not_present():
    """#596: player says 'atakuję goblina' but no goblin in scene/narrative → no injection."""
    from app.api.turns import _ensure_combat_start_tag
    conn = _make_db()
    _seed_session(conn, 1)
    conn.execute("INSERT INTO game_config_enemies (key, label) VALUES ('goblin', 'Goblin')")
    conn.commit()
    out = _ensure_combat_start_tag(conn, 1, "Atakuję goblina!", "Stoisz na pustej polanie. Nikogo tu nie ma.")
    assert "[COMBAT_START" not in out, out


def test_injection_fires_on_present_enemy_with_intent():
    """Player intent + enemy present in scene → tag injected."""
    from app.api.turns import _ensure_combat_start_tag
    conn = _make_db()
    _seed_session(conn, 1, scene_enemies=[{"key": "goblin", "name": "Goblin"}])
    conn.execute("INSERT INTO game_config_enemies (key, label) VALUES ('goblin', 'Goblin')")
    conn.commit()
    out = _ensure_combat_start_tag(conn, 1, "Atakuję goblina!", "Goblin sięga po nóż.")
    assert "[COMBAT_START:goblin]" in out, out


def test_injection_fires_on_combative_narration_without_intent():
    """#520 reverse: aggressive GM narration, no player intent, no tag → inject."""
    from app.api.turns import _ensure_combat_start_tag
    conn = _make_db()
    _seed_session(conn, 1)
    conn.execute("INSERT INTO game_config_enemies (key, label) VALUES ('bandyta', 'Bandyta')")
    conn.commit()
    narr = "Zza drzewa wyskakuje bandyta — dobywa noża i rzuca się na ciebie!"
    out = _ensure_combat_start_tag(conn, 1, "Rozglądam się po lesie.", narr)
    assert "[COMBAT_START:bandyta]" in out, out


def test_no_injection_on_peaceful_narration_without_intent():
    """Negative control: calm narration + no intent → no tag."""
    from app.api.turns import _ensure_combat_start_tag
    conn = _make_db()
    _seed_session(conn, 1)
    out = _ensure_combat_start_tag(conn, 1, "Rozglądam się.", "Łąka jest cicha i spokojna.")
    assert "[COMBAT_START" not in out, out


def test_no_injection_when_combat_already_active():
    """Regression: active combat → never re-inject."""
    from app.api.turns import _ensure_combat_start_tag
    conn = _make_db()
    _seed_session(conn, 1, scene_enemies=[{"key": "goblin", "name": "Goblin"}])
    conn.execute("INSERT INTO active_combat (campaign_id, status) VALUES (1, 'active')")
    conn.commit()
    out = _ensure_combat_start_tag(conn, 1, "Atakuję goblina!", "Goblin naciera.")
    assert "[COMBAT_START" not in out, out
