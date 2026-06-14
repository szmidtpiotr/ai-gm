"""TDD: Issue #567 — generyczny placeholder „Wróg" (key='enemy') nie może być wybierany.

Root cause: `_resolve_enemy_key_from_context` dopasowuje etykietę wroga jako podciąg w narracji.
Placeholder z seedu ma label='Wróg' → polskie słowo „wróg" w „atakuję wroga" trafia w niego i
walka startuje z dosłownym „Wróg". Fix: placeholdery (key/label generyczne) są pomijane w
dopasowaniu; gdy nic realnego nie pasuje → 'unknown_attacker', a pending dostaje polską nazwę
„Napastnik" zamiast „Wróg"/„Unknown Attacker".
"""
import sys
sys.path.insert(0, "/app")

import sqlite3
import app.api.turns as turns


def _ctx_conn(enemies):
    """In-memory DB z minimalnym schematem dla _resolve_enemy_key_from_context."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE game_sessions (campaign_id INTEGER, session_flags TEXT)")
    conn.execute("CREATE TABLE campaign_turns (id INTEGER PRIMARY KEY, campaign_id INTEGER, assistant_text TEXT)")
    conn.execute("CREATE TABLE game_config_enemies (key TEXT, label TEXT, is_active INTEGER DEFAULT 1)")
    conn.executemany("INSERT INTO game_config_enemies (key,label,is_active) VALUES (?,?,1)", enemies)
    conn.commit()
    return conn


# ─── Test główny — placeholder „Wróg" NIE jest wybierany ─────────────────────

def test_word_wrog_does_not_match_placeholder():
    """„atakuję wroga" + katalog z samym placeholderem → 'unknown_attacker', nie 'enemy'."""
    conn = _ctx_conn([("enemy", "Wróg")])
    out = turns._resolve_enemy_key_from_context(conn, 1, "Rzucasz się na wroga z furią.")
    assert out != "enemy", "placeholder zlapany przez slowo wrog (#567)"
    assert out == "unknown_attacker"


# ─── Backward compat — realny wróg po nazwie nadal pasuje ────────────────────

def test_real_named_enemy_still_matches():
    """Realny wróg „Goblin" wspomniany w narracji → 'goblin' (placeholder go nie przesłania)."""
    conn = _ctx_conn([("enemy", "Wróg"), ("goblin", "Goblin")])
    out = turns._resolve_enemy_key_from_context(conn, 1, "Goblin warczy i rusza do ataku.")
    assert out == "goblin"


# ─── Pending fallback dostaje polską nazwę ───────────────────────────────────

def test_pending_unknown_attacker_is_polish():
    """_create_pending_combat_enemy('unknown_attacker') → label „Napastnik" (nie „Unknown Attacker")."""
    from app.services import combat_service as cs
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE game_config_enemies
           (key TEXT PRIMARY KEY, label TEXT, tier TEXT, hp_base INT, ac_base INT,
            attack_bonus INT, damage_die TEXT, damage_bonus INT, attacks_per_turn INT,
            xp_award INT, is_active INT, review_status TEXT,
            dex_modifier INT DEFAULT 0, skills_json TEXT,
            loot_table_key TEXT, drop_chance REAL DEFAULT 0)"""
    )
    conn.commit()
    row = cs._create_pending_combat_enemy(conn, "unknown_attacker")
    assert row is not None
    assert row["label"] == "Napastnik"
