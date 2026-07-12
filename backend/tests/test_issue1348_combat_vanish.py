"""TDD: Issue #1348 [WALKA-T4] — walka znika w trakcie, bez wyniku i lootu; fałszywe victory.

Dwie poprawki backend z sekcji T4 specu (docs/FIX_TRAVEL_COMBAT_FLOW.md):

1. `_advance_turn_impl` liczył żywych z `turn_order` zamiast z `combatants`. Wróg żywy
   w `combatants`, ale nieobecny w `turn_order`, dawał FAŁSZYWE victory (living=[player],
   len<=1). Fix: koniec walki liczony z `combatants` (źródło prawdy). Victory tylko gdy
   żaden wróg nie żyje; gdy wróg żyje a padł gracz → `player_dead`.

2. Poll `GET /combat` filtrował `status='active'` → po końcu walki zwracał
   `{active:false, combat:null}` i NIGDY `ended_reason`/`loot_pool`. Fix: zwracaj ostatnią
   walkę kampanii (any status), pole `active` z `status=='active'`. Front sam decyduje
   po `combat_id`, czy stan ended już obsłużył.
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


def _campaign_and_char(conn):
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


def _insert_combat(
    conn, campaign_id, character_id, *, combatants, turn_order,
    status="active", ended_reason=None, loot_pool=None, current_turn="player",
):
    conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
    cols = "campaign_id, character_id, round, combatants, turn_order, current_turn, status, ended_reason, created_at, updated_at"
    vals = [
        campaign_id, character_id,
        json.dumps(combatants, ensure_ascii=False),
        json.dumps(turn_order, ensure_ascii=False),
        current_turn, status, ended_reason,
    ]
    extra_cols, extra_ph, extra_vals = "", "", []
    # loot_pool column may or may not exist depending on migration state
    has_loot = any(r["name"] == "loot_pool" for r in conn.execute("PRAGMA table_info(active_combat)"))
    if loot_pool is not None and has_loot:
        extra_cols, extra_ph = ", loot_pool", ", ?"
        extra_vals = [json.dumps(loot_pool, ensure_ascii=False)]
    conn.execute(
        f"""INSERT INTO active_combat ({cols}{extra_cols})
            VALUES (?, ?, 1, ?, ?, ?, ?, ?, datetime('now'), datetime('now'){extra_ph})""",
        (*vals, *extra_vals),
    )
    conn.commit()


def _player(hp=10):
    return {
        "id": "player", "type": "player", "name": "Bohater",
        "hp_current": hp, "hp_max": 10, "defense": 12, "stats": {},
        "initiative_roll": 15, "conditions": [], "zone": ZONE_ENGAGED,
    }


def _enemy(key="rat", inst="rat_01", hp=6):
    return {
        "id": inst, "type": "enemy", "enemy_key": key, "name": "Szczur",
        "hp_current": hp, "hp_max": 6, "defense": 10, "attack_bonus": 2,
        "damage_dice": "1d4", "initiative_roll": 10, "conditions": [], "zone": ZONE_ENGAGED,
    }


# ─── Test główny #1 — wróg poza turn_order NIE daje fałszywego victory ─────────

def test_alive_enemy_off_turn_order_does_not_end_victory(conn):
    """Wróg żywy w combatants, ale NIEOBECNY w turn_order → walka NIE kończy się victory.

    Bug: `living` liczone z turn_order pomijało wroga → len(living)<=1 → victory z HP>0.
    """
    from app.services.combat_service import _advance_turn_impl

    campaign_id, character_id = _campaign_and_char(conn)
    # Enemy alive (hp=6) but turn_order lists only the player — the #1348 desync.
    _insert_combat(
        conn, campaign_id, character_id,
        combatants=[_player(hp=10), _enemy(hp=6)],
        turn_order=["player"],
    )

    result = _advance_turn_impl(campaign_id)

    row = conn.execute(
        "SELECT status, ended_reason FROM active_combat WHERE campaign_id = ?",
        (campaign_id,),
    ).fetchone()
    conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
    conn.commit()

    assert result != "ended", f"combat must NOT end while an enemy is alive, got result={result!r}"
    assert row["status"] == "active", f"status must stay 'active', got {row['status']!r}"
    assert row["ended_reason"] != "victory", (
        f"false victory with living enemy (bug #1348), ended_reason={row['ended_reason']!r}"
    )


# ─── Test #1b — koniec liczony z combatants: player padł, wróg żyje → player_dead ─

def test_player_dead_when_only_enemy_survives(conn):
    """Gracz padł, wróg żyje (oba w turn_order) → koniec z reason='player_dead', nie 'victory'."""
    from app.services.combat_service import _advance_turn_impl

    campaign_id, character_id = _campaign_and_char(conn)
    _insert_combat(
        conn, campaign_id, character_id,
        combatants=[_player(hp=0), _enemy(hp=4)],
        turn_order=["player", "rat_01"],
    )

    result = _advance_turn_impl(campaign_id)

    row = conn.execute(
        "SELECT ended_reason FROM active_combat WHERE campaign_id = ?",
        (campaign_id,),
    ).fetchone()
    conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
    conn.commit()

    assert result == "ended"
    assert row["ended_reason"] == "player_dead", (
        f"player down + enemy alive must be player_dead, got {row['ended_reason']!r}"
    )


# ─── Backward compat — wszyscy wrogowie martwi nadal daje victory ─────────────

def test_all_enemies_dead_still_victory(conn):
    """Wszyscy wrogowie z HP=0 → nadal 'victory' (bez regresji)."""
    from app.services.combat_service import _advance_turn_impl

    campaign_id, character_id = _campaign_and_char(conn)
    _insert_combat(
        conn, campaign_id, character_id,
        combatants=[_player(hp=10), _enemy(hp=0)],
        turn_order=["player", "rat_01"],
    )

    result = _advance_turn_impl(campaign_id)

    row = conn.execute(
        "SELECT ended_reason FROM active_combat WHERE campaign_id = ?",
        (campaign_id,),
    ).fetchone()
    conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
    conn.commit()

    assert result == "ended"
    assert row["ended_reason"] == "victory", (
        f"all enemies dead must stay victory, got {row['ended_reason']!r}"
    )


# ─── Test główny #2 — poll GET /combat zwraca stan ended + loot_pool ──────────

def test_get_combat_returns_ended_snapshot_with_loot(conn):
    """Po zakończeniu walki `GET /combat` zwraca snapshot z ended_reason + loot_pool.

    Bug: endpoint filtrował status='active' → {active:false, combat:null} po końcu.
    Fix: zwraca ostatnią walkę (any status); active=False, combat niesie ended_reason+loot.
    """
    from app.api.combat import get_combat

    campaign_id, character_id = _campaign_and_char(conn)
    loot = [{"kind": "gold", "amount": 12}, {"item_key": "healing_herb", "qty": 1}]
    _insert_combat(
        conn, campaign_id, character_id,
        combatants=[_player(hp=10), _enemy(hp=0)],
        turn_order=["player", "rat_01"],
        status="ended", ended_reason="victory", loot_pool=loot,
    )

    payload = get_combat(campaign_id)

    conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
    conn.commit()

    assert payload["active"] is False, "ended combat must report active:false"
    assert payload["combat"] is not None, "ended snapshot must NOT be null (bug #1348 silent vanish)"
    assert payload["combat"]["ended_reason"] == "victory", (
        f"ended snapshot must carry ended_reason, got {payload['combat'].get('ended_reason')!r}"
    )
    has_loot_col = any(r["name"] == "loot_pool" for r in conn.execute("PRAGMA table_info(active_combat)"))
    if has_loot_col:
        assert payload["combat"].get("loot_pool"), "ended snapshot must carry loot_pool"


# ─── Backward compat — aktywna walka nadal active:true ────────────────────────

def test_get_combat_active_still_true(conn):
    """Aktywna walka → active:true + snapshot (bez regresji polla)."""
    from app.api.combat import get_combat

    campaign_id, character_id = _campaign_and_char(conn)
    _insert_combat(
        conn, campaign_id, character_id,
        combatants=[_player(hp=10), _enemy(hp=6)],
        turn_order=["player", "rat_01"],
        status="active",
    )

    payload = get_combat(campaign_id)

    conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
    conn.commit()

    assert payload["active"] is True
    assert payload["combat"] is not None
    assert payload["combat"]["status"] == "active"
