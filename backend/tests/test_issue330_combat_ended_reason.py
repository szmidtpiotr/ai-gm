"""TDD: Issue #330 — Combat ended_reason must be 'player_dead' when only enemies survive.

Bug in _advance_turn_impl() line 2521: `len(living) <= 1` always ends as 'victory'.
When player HP=0 and enemy HP>0: living=[enemy] → len=1 → "victory" (WRONG).
Expected: "player_dead".

This manifests as: player sees "victory" screen when they died, and on re-login
the last thing shown is the (incorrectly ended) combat events.
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


def _setup_active_combat(conn, campaign_id: int, character_id: int,
                          player_hp: int, enemy_hp: int) -> None:
    """Insert a synthetic active_combat row for testing advance_turn behavior."""
    combatants = [
        {
            "id": "player",
            "type": "player",
            "name": "Bohater",
            "hp_current": player_hp,
            "hp_max": 10,
            "defense": 12,
            "stats": {},
            "initiative_roll": 15,
            "conditions": [],
            "zone": ZONE_ENGAGED,
        },
        {
            "id": "rat_01",
            "type": "enemy",
            "enemy_key": "rat",
            "name": "Szczur",
            "hp_current": enemy_hp,
            "hp_max": 6,
            "defense": 10,
            "attack_bonus": 2,
            "damage_dice": "1d4",
            "initiative_roll": 10,
            "conditions": [],
            "zone": ZONE_ENGAGED,
        },
    ]
    turn_order = ["player", "rat_01"] if player_hp > 0 else ["rat_01"]
    conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
    conn.execute(
        """INSERT INTO active_combat
           (campaign_id, character_id, round, combatants, turn_order, current_turn,
            status, ended_reason, created_at, updated_at)
           VALUES (?, ?, 1, ?, ?, 'player', 'active', NULL, datetime('now'), datetime('now'))""",
        (campaign_id, character_id,
         json.dumps(combatants, ensure_ascii=False),
         json.dumps(turn_order, ensure_ascii=False)),
    )
    conn.commit()


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_advance_turn_sets_player_dead_when_player_hp_zero_enemy_alive(conn):
    """_advance_turn_impl must set ended_reason='player_dead' when player HP=0, enemy HP>0.

    Bug: currently sets 'victory' in this scenario.
    """
    from app.services.combat_service import _advance_turn_impl

    row = conn.execute(
        """SELECT c.id AS campaign_id, ch.id AS character_id
           FROM campaigns c
           JOIN characters ch ON ch.campaign_id = c.id AND ch.is_active = 1
           WHERE c.status = 'active'
           LIMIT 1"""
    ).fetchone()
    if not row:
        pytest.skip("No active campaign with character found")

    campaign_id = row["campaign_id"]
    character_id = row["character_id"]

    # Set up: player HP=0, enemy HP=1 — advance_turn should end as 'player_dead'
    _setup_active_combat(conn, campaign_id, character_id, player_hp=0, enemy_hp=1)

    result = _advance_turn_impl(campaign_id)

    ended_row = conn.execute(
        "SELECT ended_reason FROM active_combat WHERE campaign_id = ?",
        (campaign_id,),
    ).fetchone()
    # Clean up
    conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
    conn.commit()

    assert result == "ended", f"Expected 'ended', got '{result}'"
    assert ended_row["ended_reason"] == "player_dead", (
        f"Expected ended_reason='player_dead' when player dead + enemy alive, "
        f"got '{ended_row['ended_reason']}'"
    )


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_advance_turn_sets_victory_when_all_enemies_dead(conn):
    """_advance_turn_impl must still set ended_reason='victory' when all enemies have HP=0."""
    from app.services.combat_service import _advance_turn_impl

    row = conn.execute(
        """SELECT c.id AS campaign_id, ch.id AS character_id
           FROM campaigns c
           JOIN characters ch ON ch.campaign_id = c.id AND ch.is_active = 1
           WHERE c.status = 'active'
           LIMIT 1"""
    ).fetchone()
    if not row:
        pytest.skip("No active campaign with character found")

    campaign_id = row["campaign_id"]
    character_id = row["character_id"]

    # Set up: player alive, enemy HP=0 → should end as 'victory'
    _setup_active_combat(conn, campaign_id, character_id, player_hp=10, enemy_hp=0)

    result = _advance_turn_impl(campaign_id)

    ended_row = conn.execute(
        "SELECT ended_reason FROM active_combat WHERE campaign_id = ?",
        (campaign_id,),
    ).fetchone()
    conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
    conn.commit()

    assert ended_row["ended_reason"] == "victory", (
        f"Expected 'victory' when all enemies dead, got '{ended_row['ended_reason']}'"
    )
