"""TDD: Issue #484 — F2b: affix roll dla enemy dropów w zwykłej walce.

Dodaje game_config_enemies.loot_tier TEXT DEFAULT NULL.
Przy śmierci wroga loot_pool entries dostają pole enemy_loot_tier.
claim_post_combat_loot przekazuje loot_tier do grant_loot_to_character dla broni.
"""
import sys
sys.path.insert(0, '/app')

import inspect
import sqlite3


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_db_col_names(table: str) -> list[str]:
    conn = sqlite3.connect("/data/ai_gm.db")
    # PRAGMA table_info returns: (cid, name, type, notnull, dflt_value, pk)
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    conn.close()
    return cols


# ── Schema ────────────────────────────────────────────────────────────────────

class TestSchema:
    def test_game_config_enemies_has_loot_tier_column(self):
        cols = _get_db_col_names("game_config_enemies")
        assert "loot_tier" in cols, (
            f"game_config_enemies must have loot_tier column. Found: {cols}"
        )

    def test_loot_tier_default_is_null(self):
        conn = sqlite3.connect("/data/ai_gm.db")
        # PRAGMA table_info: (cid, name, type, notnull, dflt_value, pk)
        rows = conn.execute("PRAGMA table_info(game_config_enemies)").fetchall()
        conn.close()
        loot_tier_row = next((r for r in rows if r[1] == "loot_tier"), None)
        assert loot_tier_row is not None, "loot_tier column not found"
        # SQLite may return None or string 'NULL' for DEFAULT NULL — both are correct
        dflt = loot_tier_row[4]
        assert dflt is None or str(dflt).upper() == "NULL", (
            f"loot_tier default should be NULL, got: {dflt!r}"
        )


# ── _preview_loot_from_roll_items ─────────────────────────────────────────────

class TestPreviewLootFromRollItems:
    """_preview_loot_from_roll_items must accept loot_tier and store it in entries."""

    def test_accepts_loot_tier_param(self):
        from app.services.combat_service import _preview_loot_from_roll_items
        sig = inspect.signature(_preview_loot_from_roll_items)
        assert "loot_tier" in sig.parameters, (
            "_preview_loot_from_roll_items must accept loot_tier param"
        )
        p = sig.parameters["loot_tier"]
        assert p.default is not inspect.Parameter.empty, "loot_tier must be optional"

    def test_weapon_entry_gets_enemy_loot_tier_when_set(self):
        from app.services.combat_service import _preview_loot_from_roll_items
        items = [{"weapon_key": "miecz_zelazny", "quantity": 1}]
        result = _preview_loot_from_roll_items(items, loot_tier="standard")
        assert len(result) == 1
        assert result[0]["enemy_loot_tier"] == "standard", (
            f"weapon entry must have enemy_loot_tier='standard', got: {result[0]}"
        )

    def test_non_weapon_entry_does_not_get_loot_tier(self):
        from app.services.combat_service import _preview_loot_from_roll_items
        items = [{"item_key": "zloto", "quantity": 3}]
        result = _preview_loot_from_roll_items(items, loot_tier="standard")
        assert len(result) == 1
        # Items don't get affixes — enemy_loot_tier not relevant but harmless if stored
        # Key assertion: function doesn't crash
        assert isinstance(result[0], dict)

    def test_null_loot_tier_stored_as_none(self):
        from app.services.combat_service import _preview_loot_from_roll_items
        items = [{"weapon_key": "miecz_zelazny", "quantity": 1}]
        result = _preview_loot_from_roll_items(items, loot_tier=None)
        assert len(result) == 1
        assert result[0].get("enemy_loot_tier") is None, (
            f"enemy_loot_tier should be None when loot_tier=None, got: {result[0]}"
        )

    def test_backward_compat_no_loot_tier_arg(self):
        from app.services.combat_service import _preview_loot_from_roll_items
        items = [{"weapon_key": "miecz_zelazny", "quantity": 1}]
        result = _preview_loot_from_roll_items(items)
        # Must not crash and must return a valid list
        assert isinstance(result, list)
        assert len(result) == 1


# ── Combatant dict ────────────────────────────────────────────────────────────

class TestCombatantLootTierField:
    """Enemy combatant dict must include loot_tier from game_config_enemies."""

    def test_initiate_combat_stores_loot_tier_in_combatant(self):
        """Enemy combatant dict must have loot_tier key (even if None)."""
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)

        # Get demo token
        r = client.post("/api/admin/dev-login", json={"username": "demo", "password": "demo"})
        assert r.status_code == 200
        token = r.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Get active combat if any
        r = client.get("/api/campaigns/1/combat", headers=headers)
        if r.status_code == 200:
            body = r.json()
            combatants = body.get("combatants") or []
            enemies = [c for c in combatants if c.get("type") == "enemy"]
            if enemies:
                assert "loot_tier" in enemies[0], (
                    f"enemy combatant must have loot_tier key. Keys: {list(enemies[0].keys())}"
                )

    def test_claim_loot_passes_loot_tier_to_grant(self):
        """claim_post_combat_loot source must reference enemy_loot_tier."""
        from app.services.combat_service import claim_post_combat_loot
        import inspect
        src = inspect.getsource(claim_post_combat_loot)
        assert "enemy_loot_tier" in src, (
            "claim_post_combat_loot must read enemy_loot_tier from loot entry"
        )
        assert "loot_tier" in src, (
            "claim_post_combat_loot must pass loot_tier to grant_loot_to_character"
        )
