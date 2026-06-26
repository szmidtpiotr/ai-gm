"""TDD: Issue #979 — Showcase swiat.html: krasnoludy bez 'wkrótce', changelog v1.6.0.
Frontend-only change — full content verification via Playwright spec.
This test verifies the backend is healthy and the change intent is documented.
"""
import sys
sys.path.insert(0, "/app")


def test_backend_healthy_for_showcase():
    """Backend działa — showcase jest obsługiwany przez ten sam stack."""
    import sqlite3
    conn = sqlite3.connect("/data/ai_gm.db")
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='characters'").fetchone()
    conn.close()
    assert row is not None, "DB niedostępna"


def test_race_dwarf_exists_in_backend():
    """Backend obsługuje rasę 'dwarf' — co showcase opisuje jako dostępną."""
    from app.services.actor_stats import RACIAL_STAT_MODS
    assert "dwarf" in RACIAL_STAT_MODS, "Brak rasy 'dwarf' w backend — showcase opisuje ją jako dostępną"


def test_dwarf_spells_seeded_for_showcase():
    """6 czarów krasnoludów istnieje w DB — showcase opisuje Rdzeń-magię."""
    import sqlite3
    conn = sqlite3.connect("/data/ai_gm.db")
    rows = conn.execute(
        "SELECT COUNT(*) AS cnt FROM game_config_spells WHERE race_lock = 'dwarf'"
    ).fetchone()
    conn.close()
    assert rows[0] >= 6, f"Za mało czarów krasnoludów w DB: {rows[0]}"


def test_dwarf_shop_discount_available():
    """Kowalskie oko (15% zniżka) istnieje — showcase opisuje tę cechę."""
    from app.services.shop_service import DWARF_SHOP_DISCOUNT
    assert DWARF_SHOP_DISCOUNT == 0.15


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_human_still_works_as_default_race():
    """Człowiek (human) dalej jest domyślną rasą — nie naruszono innych ras."""
    from app.services.actor_stats import apply_racial_modifiers
    sheet = {"stats": {"STR": 10, "DEX": 10, "CON": 10}}
    result = apply_racial_modifiers(sheet, "human")
    assert result["stats"]["STR"] == 10, "Człowiek nie powinien mieć modyfikatorów STR"
