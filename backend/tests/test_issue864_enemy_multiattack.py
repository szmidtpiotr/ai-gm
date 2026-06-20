"""TDD: Issue #864 — ożyw martwe pole attacks_per_turn (wróg z N>1 atakuje N razy/turę).

Silnik walki nigdy nie czytał `game_config_enemies.attacks_per_turn` — wróg zawsze
atakował raz/turę. Ten test wymusza:
  • wróg z attacks_per_turn=2 wykonuje 2 osobno rozliczone ataki w jednej turze,
  • attacks_per_turn=1 → zachowanie bit-identyczne z dziś (zero regresji),
  • pętla przerwana po powaleniu gracza (brak dobijania trupa),
  • jeden advance_turn na koniec tury (ataki NIE zaawansowują tury same).
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.db_runtime import resolve_db_path
from app.services.combat_service import ZONE_ENGAGED


@pytest.fixture
def conn():
    c = sqlite3.connect(resolve_db_path())
    c.row_factory = sqlite3.Row
    yield c
    c.close()


def _active_campaign(conn):
    row = conn.execute(
        """SELECT c.id AS campaign_id, ch.id AS character_id
           FROM campaigns c
           JOIN characters ch ON ch.campaign_id = c.id AND ch.is_active = 1
           WHERE c.status = 'active'
           LIMIT 1"""
    ).fetchone()
    if not row:
        pytest.skip("No active campaign with character found")
    return row["campaign_id"], row["character_id"]


def _setup_combat(conn, campaign_id, character_id, *, attacks_per_turn, player_hp=40):
    """Enemy-turn combat with a single enemy whose attacks_per_turn is set.

    Player gets `reaction_used_round=1` so NO reaction window opens this round —
    the test stays deterministic regardless of the demo character's skills/shield.
    """
    enemy_slug = "mat_enemy_01"
    combatants = [
        {
            "id": "player", "type": "player", "name": "Bohater",
            "hp_current": player_hp, "hp_max": 40, "defense": 11,
            "stats": {"STR": 10, "DEX": 8, "CON": 10},
            "initiative_roll": 5, "conditions": [], "zone": ZONE_ENGAGED,
            "reaction_used_round": 1,  # blokuje okno reakcji w rundzie 1
        },
        {
            "id": enemy_slug, "type": "enemy", "enemy_key": "mat_brute",
            "name": "Brutal", "hp_current": 30, "hp_max": 30, "defense": 11,
            "attack_bonus": 50,  # gwarantowane trafienie (poza nat 1)
            "damage_dice": "1d4", "dex_modifier": 0, "damage_bonus": 0,
            "attacks_per_turn": attacks_per_turn,
            "initiative_roll": 25, "conditions": [], "zone": ZONE_ENGAGED,
            "skills": {},
        },
    ]
    conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
    conn.execute(
        """INSERT INTO active_combat
           (campaign_id, character_id, round, combatants, turn_order, current_turn,
            status, ended_reason, created_at, updated_at)
           VALUES (?, ?, 1, ?, ?, ?, 'active', NULL, datetime('now'), datetime('now'))""",
        (campaign_id, character_id,
         json.dumps(combatants, ensure_ascii=False),
         json.dumps([enemy_slug, "player"], ensure_ascii=False),
         enemy_slug),
    )
    conn.commit()
    return enemy_slug


def _enemy_attack_log_count(conn, campaign_id):
    row = conn.execute(
        """SELECT COUNT(*) AS n FROM combat_turns
           WHERE campaign_id = ? AND actor = 'enemy' AND event_type = 'attack'""",
        (campaign_id,),
    ).fetchone()
    return int(row["n"] or 0)


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_enemy_with_two_attacks_strikes_twice_in_one_turn(conn):
    """attacks_per_turn=2 → dwa osobno rozliczone ataki, tura NIE zaawansowana sama."""
    from app.services.combat_service import (
        resolve_attack, resolve_enemy_followup_attacks,
    )
    campaign_id, character_id = _active_campaign(conn)
    enemy_slug = _setup_combat(conn, campaign_id, character_id, attacks_per_turn=2)

    conn.execute(
        "DELETE FROM combat_turns WHERE campaign_id = ? AND event_type = 'attack'",
        (campaign_id,),
    )
    conn.commit()

    first = resolve_attack(campaign_id, 0, attacker="enemy")
    extras = resolve_enemy_followup_attacks(campaign_id)

    log_count = _enemy_attack_log_count(conn, campaign_id)
    cur = conn.execute(
        "SELECT current_turn FROM active_combat WHERE campaign_id = ?", (campaign_id,)
    ).fetchone()

    conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
    conn.commit()

    assert not first.get("reaction_window"), "reaction window powinno być zablokowane w teście"
    assert len(extras) == 1, f"attacks_per_turn=2 → 1 dodatkowy atak, got {len(extras)}"
    assert log_count == 2, f"oczekiwano 2 wpisów ataku wroga, jest {log_count}"
    assert str(cur["current_turn"]) == enemy_slug, "ataki NIE mogą same zaawansować tury"


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_single_attack_enemy_unchanged(conn):
    """attacks_per_turn=1 → dokładnie jeden atak, brak dodatkowych (bit-identyczne)."""
    from app.services.combat_service import (
        resolve_attack, resolve_enemy_followup_attacks,
    )
    campaign_id, character_id = _active_campaign(conn)
    _setup_combat(conn, campaign_id, character_id, attacks_per_turn=1)

    conn.execute(
        "DELETE FROM combat_turns WHERE campaign_id = ? AND event_type = 'attack'",
        (campaign_id,),
    )
    conn.commit()

    resolve_attack(campaign_id, 0, attacker="enemy")
    extras = resolve_enemy_followup_attacks(campaign_id)
    log_count = _enemy_attack_log_count(conn, campaign_id)

    conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
    conn.commit()

    assert extras == [], "attacks_per_turn=1 nie może wystrzelić dodatkowych ataków"
    assert log_count == 1, f"oczekiwano 1 wpisu ataku wroga, jest {log_count}"


# ─── Przerwanie pętli po powaleniu gracza ────────────────────────────────────

def test_followup_does_not_hit_downed_player(conn):
    """Gracz powalony (hp=0) → pętla dodatkowych ataków nie strzela (brak dobijania)."""
    from app.services.combat_service import resolve_enemy_followup_attacks
    campaign_id, character_id = _active_campaign(conn)
    # gracz już na 0 HP, wróg ma 2 ataki/turę
    _setup_combat(conn, campaign_id, character_id, attacks_per_turn=2, player_hp=0)

    conn.execute(
        "DELETE FROM combat_turns WHERE campaign_id = ? AND event_type = 'attack'",
        (campaign_id,),
    )
    conn.commit()

    extras = resolve_enemy_followup_attacks(campaign_id)
    log_count = _enemy_attack_log_count(conn, campaign_id)

    conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
    conn.commit()

    assert extras == [], "nie wolno atakować powalonego gracza"
    assert log_count == 0, "brak nowych ataków na trupa"
