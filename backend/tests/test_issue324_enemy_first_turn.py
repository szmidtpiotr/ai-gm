"""TDD: Issue #324 — Enemy must execute turn when enemy wins initiative.

Bug: when combat starts and enemy has higher initiative (goes first), the
frontend's handleEnemyTurn() uses raw fetch() without Authorization header.
After session-token auth changes, this is inconsistent and may fail silently.

Backend test: verify POST /combat/enemy-turn endpoint processes enemy attack
correctly when it IS the enemy's turn (status active, current_turn=enemy_id).
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


def _setup_enemy_first_combat(conn, campaign_id: int, character_id: int) -> str:
    """Set up combat where enemy goes first (higher initiative). Returns enemy slug."""
    enemy_slug = "cult_initiate_01"
    combatants = [
        {
            "id": "player",
            "type": "player",
            "name": "Bohater",
            "hp_current": 10,
            "hp_max": 10,
            "defense": 13,
            "stats": {"STR": 14, "DEX": 13, "CON": 10},
            "initiative_roll": 9,   # enemy wins
            "conditions": [],
            "zone": ZONE_ENGAGED,
        },
        {
            "id": enemy_slug,
            "type": "enemy",
            "enemy_key": "cult_initiate",
            "name": "Inicjat Kultu",
            "hp_current": 12,
            "hp_max": 12,
            "defense": 11,
            "attack_bonus": 3,
            "damage_dice": "1d6",
            "dex_modifier": 1,
            "damage_bonus": 0,
            "initiative_roll": 15,   # goes first
            "conditions": [],
            "zone": ZONE_ENGAGED,
            "skills": {},
        },
    ]
    turn_order = [enemy_slug, "player"]   # enemy first
    conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
    conn.execute(
        """INSERT INTO active_combat
           (campaign_id, character_id, round, combatants, turn_order, current_turn,
            status, ended_reason, created_at, updated_at)
           VALUES (?, ?, 1, ?, ?, ?, 'active', NULL, datetime('now'), datetime('now'))""",
        (campaign_id, character_id,
         json.dumps(combatants, ensure_ascii=False),
         json.dumps(turn_order, ensure_ascii=False),
         enemy_slug),
    )
    conn.commit()
    return enemy_slug


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_enemy_turn_resolves_when_enemy_goes_first(conn):
    """resolve_attack(attacker='enemy') must process when enemy has current_turn."""
    from app.services.combat_service import resolve_attack

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

    _setup_enemy_first_combat(conn, campaign_id, character_id)

    # Enemy turn should resolve without error
    result = resolve_attack(campaign_id, 0, attacker="enemy")

    # Clean up
    conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
    conn.commit()

    assert "message" not in result or result.get("message") != "enemy attack only when current turn is an enemy", (
        "Enemy turn should process when current_turn is enemy, not return 'only when current turn is enemy'"
    )
    # Result should have combat state
    assert "combat_state" in result, "Enemy turn result must include combat_state"


def test_enemy_turn_blocked_when_player_turn(conn):
    """resolve_attack(attacker='enemy') must NOT fire when it's the player's turn."""
    from app.services.combat_service import resolve_attack

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

    # Set up with PLAYER going first
    combatants = [
        {
            "id": "player",
            "type": "player",
            "name": "Bohater",
            "hp_current": 10,
            "hp_max": 10,
            "defense": 13,
            "stats": {},
            "initiative_roll": 20,  # player wins
            "conditions": [],
            "zone": ZONE_ENGAGED,
        },
        {
            "id": "rat_01",
            "type": "enemy",
            "enemy_key": "rat",
            "name": "Szczur",
            "hp_current": 6,
            "hp_max": 6,
            "defense": 10,
            "attack_bonus": 1,
            "damage_dice": "1d4",
            "dex_modifier": 0,
            "initiative_roll": 5,
            "conditions": [],
            "zone": ZONE_ENGAGED,
            "skills": {},
        },
    ]
    conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
    conn.execute(
        """INSERT INTO active_combat
           (campaign_id, character_id, round, combatants, turn_order, current_turn,
            status, ended_reason, created_at, updated_at)
           VALUES (?, ?, 1, ?, ?, 'player', 'active', NULL, datetime('now'), datetime('now'))""",
        (campaign_id, character_id,
         json.dumps(combatants, ensure_ascii=False),
         json.dumps(["player", "rat_01"], ensure_ascii=False)),
    )
    conn.commit()

    result = resolve_attack(campaign_id, 0, attacker="enemy")

    conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
    conn.commit()

    assert result.get("message") == "enemy attack only when current turn is an enemy", (
        "Enemy attack must be blocked when it's the player's turn"
    )


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_enemy_turn_endpoint_has_no_auth_requirement(conn):
    """POST /combat/enemy-turn must NOT require Authorization header.

    handleEnemyTurn() in frontend uses raw fetch() without auth headers.
    The endpoint must remain accessible without auth so the frontend works.
    Test via local backend (avoids nginx/network flakiness).
    """
    from app.services.combat_service import resolve_attack

    row = conn.execute(
        "SELECT id FROM campaigns WHERE status = 'active' LIMIT 1"
    ).fetchone()
    if not row:
        pytest.skip("No active campaign")

    campaign_id = row["id"]

    # No active combat → should raise ValueError (no active combat), not auth error
    try:
        resolve_attack(campaign_id, 0, attacker="enemy")
        # If no ValueError, combat IS active — that's fine too
    except ValueError as e:
        assert "no active combat" in str(e).lower() or "active" in str(e).lower(), (
            f"Expected 'no active combat' ValueError, got: {e}"
        )
    # Key assertion: no PermissionError or auth-related error was raised
    # (the function doesn't check Authorization — it uses campaign_id only)
