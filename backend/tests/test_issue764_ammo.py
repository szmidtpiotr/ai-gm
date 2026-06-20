"""TDD: Issue #764 — System amunicji (strzały dla łuku, bełty dla kuszy).

ammo_service.py: mapuje broń→amunicję, liczy/odejmuje sztuki w plecaku, blokuje
strzał przy 0. Amunicja stackuje w character_inventory (przechowywana jako item_key,
tak jak inne consumable po #557 — patrz grant_loot_to_character else-branch).
"""
import sys
sys.path.insert(0, "/app")

import sqlite3


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _conn(arrows: int | None = None, *, as_consumable_key: bool = False):
    """In-memory DB z bohaterem #1; opcjonalnie stack strzał w plecaku."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE characters (id INTEGER PRIMARY KEY, sheet_json TEXT)")
    c.execute(
        """CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            item_key TEXT, weapon_key TEXT, consumable_key TEXT,
            quantity INTEGER NOT NULL DEFAULT 1,
            equipped INTEGER NOT NULL DEFAULT 0,
            slot TEXT, source TEXT
        )"""
    )
    c.execute("INSERT INTO characters (id, sheet_json) VALUES (1, '{}')")
    if arrows is not None:
        if as_consumable_key:
            c.execute(
                "INSERT INTO character_inventory (character_id, consumable_key, quantity, source) "
                "VALUES (1, 'arrows', ?, 'start')",
                (arrows,),
            )
        else:
            c.execute(
                "INSERT INTO character_inventory (character_id, item_key, quantity, source) "
                "VALUES (1, 'arrows', ?, 'start')",
                (arrows,),
            )
    c.commit()
    return c


# ── Test główny: mapowanie broń → amunicja ────────────────────────────────────

class TestAmmoKeyForWeapon:
    def test_bow_requires_arrows(self):
        from app.services.ammo_service import ammo_key_for_weapon
        assert ammo_key_for_weapon({"weapon_type": "ranged", "ammo_key": "arrows"}) == "arrows"

    def test_crossbow_requires_bolts(self):
        from app.services.ammo_service import ammo_key_for_weapon
        assert ammo_key_for_weapon({"weapon_type": "ranged", "ammo_key": "bolts"}) == "bolts"

    def test_melee_needs_no_ammo(self):
        from app.services.ammo_service import ammo_key_for_weapon
        assert ammo_key_for_weapon({"weapon_type": "melee", "ammo_key": None}) is None

    def test_missing_or_blank_ammo_key_is_none(self):
        from app.services.ammo_service import ammo_key_for_weapon
        assert ammo_key_for_weapon({"weapon_type": "ranged"}) is None
        assert ammo_key_for_weapon({"weapon_type": "ranged", "ammo_key": "  "}) is None
        assert ammo_key_for_weapon(None) is None


# ── Test główny: licznik amunicji w plecaku ───────────────────────────────────

class TestAmmoQuantity:
    def test_counts_item_key_stack(self):
        from app.services.ammo_service import get_ammo_quantity
        assert get_ammo_quantity(_conn(arrows=20), 1, "arrows") == 20

    def test_counts_consumable_key_stack(self):
        """Robustność: amunicja zapisana też pod consumable_key jest liczona."""
        from app.services.ammo_service import get_ammo_quantity
        assert get_ammo_quantity(_conn(arrows=7, as_consumable_key=True), 1, "arrows") == 7

    def test_zero_when_no_ammo(self):
        from app.services.ammo_service import get_ammo_quantity
        assert get_ammo_quantity(_conn(), 1, "arrows") == 0


# ── Test główny: odejmowanie przy strzale + blokada przy 0 ─────────────────────

class TestConsumeAmmo:
    def test_consume_one_decrements_stack(self):
        from app.services.ammo_service import consume_ammo, get_ammo_quantity
        conn = _conn(arrows=20)
        assert consume_ammo(conn, 1, "arrows", 1) is True
        assert get_ammo_quantity(conn, 1, "arrows") == 19

    def test_consume_blocks_when_empty(self):
        """Brak amunicji → False, nic nie odejmujemy (strzał zablokowany)."""
        from app.services.ammo_service import consume_ammo, get_ammo_quantity
        conn = _conn(arrows=0)
        assert consume_ammo(conn, 1, "arrows", 1) is False
        assert get_ammo_quantity(conn, 1, "arrows") == 0

    def test_consume_insufficient_is_atomic(self):
        """Masz 1, chcesz 3 → False i stan bez zmian (brak częściowego odjęcia)."""
        from app.services.ammo_service import consume_ammo, get_ammo_quantity
        conn = _conn(arrows=1)
        assert consume_ammo(conn, 1, "arrows", 3) is False
        assert get_ammo_quantity(conn, 1, "arrows") == 1

    def test_last_arrow_can_be_fired(self):
        from app.services.ammo_service import consume_ammo, get_ammo_quantity
        conn = _conn(arrows=1)
        assert consume_ammo(conn, 1, "arrows", 1) is True
        assert get_ammo_quantity(conn, 1, "arrows") == 0


# ── Test główny: dokładanie amunicji (zwrot do plecaka) ───────────────────────

class TestAddAmmo:
    def test_add_creates_stack_when_none(self):
        from app.services.ammo_service import add_ammo, get_ammo_quantity
        conn = _conn()
        add_ammo(conn, 1, "arrows", 5)
        assert get_ammo_quantity(conn, 1, "arrows") == 5

    def test_add_stacks_onto_existing(self):
        from app.services.ammo_service import add_ammo, get_ammo_quantity
        conn = _conn(arrows=3)
        add_ammo(conn, 1, "arrows", 4)
        assert get_ammo_quantity(conn, 1, "arrows") == 7

    def test_add_zero_is_noop(self):
        from app.services.ammo_service import add_ammo, get_ammo_quantity
        conn = _conn(arrows=3)
        add_ammo(conn, 1, "arrows", 0)
        assert get_ammo_quantity(conn, 1, "arrows") == 3
