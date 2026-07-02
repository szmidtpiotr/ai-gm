"""TDD: Issue #1107 — Sekcja reputacji na karcie bohatera: kontrakt endpointu dla frontendu.

Frontend (#1107) zależy od:
  GET /api/characters/{id}/reputation → {character_id, reputation:[{scope_type, scope_key, value, tier}]}
Tier musi być z enum {exalted, friendly, neutral, disliked, hated}.
"""
import sqlite3
import pytest

from app.services import reputation_service as rep


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    rep.ensure_reputation_table(c)
    yield c
    c.close()


# ─── Kontrakt tieru (frontend mapuje tier → PL label + kolor) ────────────────

VALID_TIERS = {"exalted", "friendly", "neutral", "disliked", "hated"}


@pytest.mark.parametrize("value,expected_tier", [
    (50, "exalted"),
    (20, "friendly"),
    (0, "neutral"),
    (-20, "disliked"),
    (-50, "hated"),
])
def test_tier_enum_values_match_frontend_contract(value, expected_tier):
    """Tier z reputation_service musi pasować dokładnie do enum w frontend #1107."""
    actual = rep.reputation_tier(value)
    assert actual == expected_tier, (
        f"Frontend #1107 oczekuje tier='{expected_tier}' dla value={value}, "
        f"dostał '{actual}'"
    )
    assert actual in VALID_TIERS, f"Tier '{actual}' poza dopuszczalnym enum (#1107)"


def test_tier_is_always_valid_enum(conn):
    """get_all_reputations zwraca wyłącznie tiery z enum — backward compat dla #1107 UI."""
    rep.adjust_reputation(conn, character_id=42, scope_key="kresy", delta=-15)
    rows = rep.get_all_reputation(conn, character_id=42)
    for row in rows:
        tier = rep.reputation_tier(row["value"])
        assert tier in VALID_TIERS, f"Niedozwolony tier '{tier}' w #1107 kontrakie"
