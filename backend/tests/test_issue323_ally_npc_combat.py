"""TDD: Issue #323 — Ally NPCs must participate in combat turns.

Bug: initiate_combat() only adds player + enemies to combatants/turn_order.
Ally NPCs (story companions) are never added — player fights alone.

Fix:
1. initiate_combat() accepts ally_npc_keys: list[str], adds them with type='ally'
2. execute_ally_auto_attack(campaign_id, ally_id) — ally attacks weakest enemy
3. Allies appear in turn_order after their initiative roll
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.db_runtime import resolve_db_path


@pytest.fixture
def conn():
    c = sqlite3.connect(resolve_db_path())
    c.row_factory = sqlite3.Row
    yield c
    c.close()


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_initiate_combat_accepts_ally_npc_keys():
    """initiate_combat() must accept ally_npc_keys parameter without error."""
    from app.services.combat_service import initiate_combat
    import inspect
    sig = inspect.signature(initiate_combat)
    assert "ally_npc_keys" in sig.parameters, (
        "initiate_combat must accept ally_npc_keys parameter"
    )


def test_initiate_combat_adds_ally_to_combatants(conn):
    """When ally_npc_keys provided, combatants must include ally entry with type='ally'."""
    from app.services.combat_service import initiate_combat

    # Find active campaign with game session and a known enemy
    row = conn.execute(
        """SELECT c.id AS campaign_id, ch.id AS character_id
           FROM campaigns c
           JOIN characters ch ON ch.campaign_id = c.id AND ch.is_active = 1
           JOIN game_sessions gs ON gs.campaign_id = c.id
           WHERE c.status = 'active'
           LIMIT 1"""
    ).fetchone()
    if not row:
        pytest.skip("No active campaign with character and session")

    campaign_id = row["campaign_id"]
    character_id = row["character_id"]

    # Use a synthetic ally key (not real NPC needed — just a name)
    result = initiate_combat(
        campaign_id, character_id, ["giant_rat"],
        ally_npc_keys=["ravan_companion"]
    )

    combatants = result.get("combatants") or []
    ally_ids = [c["id"] for c in combatants if c.get("type") == "ally"]
    assert ally_ids, (
        f"Expected at least one 'ally' type combatant, got: {[c['type'] for c in combatants]}"
    )
    assert any("ravan" in str(a_id).lower() for a_id in ally_ids), (
        f"Expected 'ravan_companion' ally in combatants, got: {ally_ids}"
    )

    # Cleanup
    conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
    conn.commit()


def test_ally_appears_in_turn_order(conn):
    """Ally must be included in turn_order after combat initiation."""
    from app.services.combat_service import initiate_combat, get_active_combat

    row = conn.execute(
        """SELECT c.id AS campaign_id, ch.id AS character_id
           FROM campaigns c
           JOIN characters ch ON ch.campaign_id = c.id AND ch.is_active = 1
           JOIN game_sessions gs ON gs.campaign_id = c.id
           WHERE c.status = 'active'
           LIMIT 1"""
    ).fetchone()
    if not row:
        pytest.skip("No active campaign")

    campaign_id = row["campaign_id"]
    character_id = row["character_id"]

    initiate_combat(
        campaign_id, character_id, ["giant_rat"],
        ally_npc_keys=["lyra_ally"]
    )

    combat = get_active_combat(campaign_id)
    turn_order = combat.get("turn_order") or []
    assert any("lyra" in str(t).lower() for t in turn_order), (
        f"Expected 'lyra_ally' in turn_order, got: {turn_order}"
    )

    conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
    conn.commit()


def test_execute_ally_auto_attack_exists():
    """execute_ally_auto_attack must be importable from combat_service."""
    from app.services.combat_service import execute_ally_auto_attack  # noqa: F401


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_initiate_combat_without_allies_still_works(conn):
    """initiate_combat() without ally_npc_keys must work exactly as before."""
    from app.services.combat_service import initiate_combat

    row = conn.execute(
        """SELECT c.id AS campaign_id, ch.id AS character_id
           FROM campaigns c
           JOIN characters ch ON ch.campaign_id = c.id AND ch.is_active = 1
           JOIN game_sessions gs ON gs.campaign_id = c.id
           WHERE c.status = 'active'
           LIMIT 1"""
    ).fetchone()
    if not row:
        pytest.skip("No active campaign")

    campaign_id = row["campaign_id"]
    character_id = row["character_id"]

    result = initiate_combat(campaign_id, character_id, ["giant_rat"])
    combatants = result.get("combatants") or []
    types = {c.get("type") for c in combatants}
    assert "player" in types, "Player must always be in combatants"
    assert "enemy" in types, "Enemy must always be in combatants"
    assert "ally" not in types, "No ally when ally_npc_keys not provided"

    conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
    conn.commit()
