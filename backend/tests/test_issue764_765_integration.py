"""TDD: Issue #764/#765 — integracja na realnej bazie DEV.

Sprawdza pełen łańcuch: nadanie amunicji startowej → plecak oznacza ją jako
amunicję (bez akcji „użyj") → odejmowanie przez ammo_service → odzysk wraca do
plecaka. Tworzy własnego, jednorazowego bohatera i sprząta po sobie.
"""
import sys
sys.path.insert(0, "/app")

import json
import pytest


@pytest.fixture()
def temp_char():
    from app.services.loot_service import _conn
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO characters (user_id, name, system_id, sheet_json, status) "
            "VALUES (1, ?, (SELECT system_id FROM characters WHERE system_id IS NOT NULL LIMIT 1), ?, 'idle')",
            ("[AMMO-TEST]", json.dumps({"archetype": "rogue"})),
        )
        cid = int(cur.lastrowid)
        conn.commit()
    yield cid
    with _conn() as conn:
        conn.execute("DELETE FROM character_inventory WHERE character_id = ?", (cid,))
        conn.execute("DELETE FROM characters WHERE id = ?", (cid,))
        conn.commit()


def test_granted_arrows_marked_as_ammo_not_usable(temp_char):
    """Plecak: strzały to amunicja (is_ammo), liczone jako consumable, ale BEZ „użyj"."""
    from app.services.loot_service import grant_loot_to_character, get_character_inventory
    grant_loot_to_character(temp_char, [{"consumable_key": "arrows", "quantity": 20}], source="start")
    inv = get_character_inventory(temp_char)
    ammo = [r for r in inv if r["key"] == "arrows"]
    assert ammo, f"strzały nie pojawiły się w plecaku: {inv}"
    row = ammo[0]
    assert row["quantity"] == 20
    assert row["item_type"] == "consumable"
    assert row["is_ammo"] is True
    assert row["can_use"] is False  # amunicji nie „używa się" jak mikstury
    assert row["label"] == "Strzały"


def test_consume_then_recover_roundtrip(temp_char):
    """Odejmij 5 strzał, potem odzyskaj wszystkie (rng=0.0) — wracają do plecaka."""
    from app.services.loot_service import grant_loot_to_character, _conn
    from app.services import ammo_service
    grant_loot_to_character(temp_char, [{"consumable_key": "arrows", "quantity": 20}], source="start")
    with _conn() as conn:
        for _ in range(5):
            assert ammo_service.consume_ammo(conn, temp_char, "arrows", 1) is True
        assert ammo_service.get_ammo_quantity(conn, temp_char, "arrows") == 15
        got = ammo_service.recover_ammo(conn, temp_char, "arrows", 5, chance=0.40, rng=lambda: 0.0)
        assert got == 5
        assert ammo_service.get_ammo_quantity(conn, temp_char, "arrows") == 20
