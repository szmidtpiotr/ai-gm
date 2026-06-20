"""TDD: Issue #765 — Odzyskiwanie amunicji (40% szans na sztukę + zwrot do plecaka).

ammo_service.recover_ammo(): rzut per wystrzelona sztuka; odzyskane wracają do
plecaka jako stack. Szansa startowa 40% (Numbers Policy — strojenie w Sandboxie),
rng wstrzykiwany dla determinizmu testu.
"""
import sys
sys.path.insert(0, "/app")

import sqlite3


def _conn(arrows: int = 0):
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
    if arrows:
        c.execute(
            "INSERT INTO character_inventory (character_id, item_key, quantity, source) "
            "VALUES (1, 'arrows', ?, 'start')",
            (arrows,),
        )
    c.commit()
    return c


# ── Numbers Policy: domyślna szansa = 40% ─────────────────────────────────────

def test_default_chance_is_40_percent():
    from app.services.ammo_service import DEFAULT_RECOVER_CHANCE
    assert DEFAULT_RECOVER_CHANCE == 0.40


# ── Test główny: deterministyczny odzysk ──────────────────────────────────────

class TestRecoverAmmo:
    def test_all_recovered_when_rng_always_succeeds(self):
        from app.services.ammo_service import recover_ammo, get_ammo_quantity
        conn = _conn(arrows=0)
        n = recover_ammo(conn, 1, "arrows", shots_fired=7, chance=0.40, rng=lambda: 0.0)
        assert n == 7
        assert get_ammo_quantity(conn, 1, "arrows") == 7  # wróciły do plecaka

    def test_none_recovered_when_rng_always_fails(self):
        from app.services.ammo_service import recover_ammo, get_ammo_quantity
        conn = _conn(arrows=0)
        n = recover_ammo(conn, 1, "arrows", shots_fired=7, chance=0.40, rng=lambda: 1.0)
        assert n == 0
        assert get_ammo_quantity(conn, 1, "arrows") == 0

    def test_recovered_stacks_onto_existing(self):
        from app.services.ammo_service import recover_ammo, get_ammo_quantity
        conn = _conn(arrows=5)
        recover_ammo(conn, 1, "arrows", shots_fired=3, chance=0.40, rng=lambda: 0.0)
        assert get_ammo_quantity(conn, 1, "arrows") == 8

    def test_threshold_is_strict_less_than_chance(self):
        """rng == chance liczone jako pudło (odzysk tylko gdy rng < chance)."""
        from app.services.ammo_service import recover_ammo
        conn = _conn()
        assert recover_ammo(conn, 1, "arrows", 5, chance=0.40, rng=lambda: 0.40) == 0

    def test_zero_shots_recovers_nothing(self):
        from app.services.ammo_service import recover_ammo
        assert recover_ammo(_conn(), 1, "arrows", shots_fired=0, rng=lambda: 0.0) == 0

    def test_configurable_chance(self):
        """100% szansy → wszystko wraca (wartość strojalna)."""
        from app.services.ammo_service import recover_ammo
        conn = _conn()
        assert recover_ammo(conn, 1, "arrows", 4, chance=1.0, rng=lambda: 0.99) == 4
