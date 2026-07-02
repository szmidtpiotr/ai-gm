"""TDD: Issue #1099 — System reputacji per-region (mechaniczne konsekwencje czynów bohatera).

Reputacja bohatera w regionie (na razie tylko 'kresy') = liczba w tabeli character_reputation.
Wpływa mechanicznie: ceny u kupca, dostęp do questów (helper), postawa NPC, kara anty-farm.
scope_type generyczny ('region' teraz, 'faction' w przyszłości — #1103).
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


# ─── CRUD roundtrip ──────────────────────────────────────────────────────────

def test_get_reputation_defaults_zero(conn):
    """Brak wpisu → reputacja 0 (neutralna)."""
    assert rep.get_reputation(conn, character_id=42, scope_key="kresy") == 0


def test_adjust_reputation_roundtrip(conn):
    """adjust_reputation zapisuje i zwraca nową wartość; get widzi tę samą."""
    new_val = rep.adjust_reputation(conn, character_id=42, scope_key="kresy", delta=20)
    assert new_val == 20
    assert rep.get_reputation(conn, character_id=42, scope_key="kresy") == 20


def test_adjust_reputation_accumulates(conn):
    """Kolejne zmiany się sumują (upsert, nie nadpisanie)."""
    rep.adjust_reputation(conn, 42, "kresy", 20)
    rep.adjust_reputation(conn, 42, "kresy", -5)
    assert rep.get_reputation(conn, 42, "kresy") == 15


def test_reputation_isolated_per_scope(conn):
    """Reputacja w jednym regionie nie miesza się z innym scope."""
    rep.adjust_reputation(conn, 42, "kresy", 30)
    assert rep.get_reputation(conn, 42, "czarnobor") == 0


# ─── scope_type generyczny (forward-compat: per-frakcja #1103) ───────────────

def test_scope_type_faction_independent_from_region(conn):
    """Ten sam scope_key pod różnym scope_type = osobne liczniki (region vs faction)."""
    rep.adjust_reputation(conn, 42, "gildia_kupcow", 10, scope_type="region")
    rep.adjust_reputation(conn, 42, "gildia_kupcow", -40, scope_type="faction")
    assert rep.get_reputation(conn, 42, "gildia_kupcow", scope_type="region") == 10
    assert rep.get_reputation(conn, 42, "gildia_kupcow", scope_type="faction") == -40


# ─── Tier / standing boundaries ──────────────────────────────────────────────

@pytest.mark.parametrize("value,tier", [
    (100, "exalted"),
    (50, "exalted"),
    (49, "friendly"),
    (20, "friendly"),
    (19, "neutral"),
    (0, "neutral"),
    (-19, "neutral"),
    (-20, "disliked"),
    (-49, "disliked"),
    (-50, "hated"),
    (-100, "hated"),
])
def test_reputation_tier_boundaries(value, tier):
    assert rep.reputation_tier(value) == tier


# ─── Efekt 1: ceny u kupca ───────────────────────────────────────────────────

def test_shop_multiplier_neutral_is_one():
    assert rep.shop_price_multiplier(0) == 1.0


def test_shop_multiplier_friendly_gives_discount():
    """Dodatnia reputacja → mnożnik < 1 (taniej)."""
    assert rep.shop_price_multiplier(50) < 1.0


def test_shop_multiplier_hostile_adds_surcharge():
    """Ujemna reputacja → mnożnik > 1 (drożej)."""
    assert rep.shop_price_multiplier(-50) > 1.0


def test_shop_multiplier_clamped():
    """Skrajne wartości nie wychodzą poza rozsądne widełki."""
    assert rep.REP_PRICE_MIN <= rep.shop_price_multiplier(9999) <= rep.REP_PRICE_MAX
    assert rep.REP_PRICE_MIN <= rep.shop_price_multiplier(-9999) <= rep.REP_PRICE_MAX


# ─── Efekt 2: dostęp do questów (helper mechanizmu) ──────────────────────────

def test_quest_access_allowed_when_rep_meets_threshold():
    assert rep.quest_access_allowed(20, min_reputation=20) is True
    assert rep.quest_access_allowed(25, min_reputation=20) is True


def test_quest_access_blocked_when_rep_below_threshold():
    assert rep.quest_access_allowed(19, min_reputation=20) is False


# ─── Efekt 3: postawa NPC z reputacji ────────────────────────────────────────

@pytest.mark.parametrize("value,attitude", [
    (30, "friendly"),
    (0, "neutral"),
    (-30, "hostile"),
])
def test_npc_attitude_from_reputation(value, attitude):
    assert rep.npc_attitude_from_reputation(value) == attitude


# ─── resolve_region (defensywne, region col jeszcze nie istnieje) ────────────

def test_resolve_region_defaults_to_kresy_without_region_data(conn):
    """Brak kolumny/tabel region → fallback do jedynego live regionu 'kresy' (#917)."""
    assert rep.resolve_region(conn, campaign_id=1234) == rep.REGION_DEFAULT
    assert rep.resolve_region(conn, campaign_id=1234) == "kresy"


# ─── Efekt 4 + źródła: apply_campaign_outcome ────────────────────────────────

def test_victory_raises_regional_reputation(conn):
    """Zwycięstwo w kampanii podnosi reputację w regionie."""
    val = rep.apply_campaign_outcome(conn, character_id=7, campaign_id=1, outcome="victory")
    assert val == rep.REP_VICTORY_REWARD
    assert rep.get_reputation(conn, 7, "kresy") == rep.REP_VICTORY_REWARD


def test_abandonment_lowers_regional_reputation(conn):
    """Porzucenie kampanii (farm-and-bail) obniża reputację w regionie — anty-farm."""
    val = rep.apply_campaign_outcome(conn, character_id=7, campaign_id=1, outcome="abandoned")
    assert val == -rep.REP_ABANDON_PENALTY
    assert rep.get_reputation(conn, 7, "kresy") < 0


def test_death_lowers_reputation_slightly(conn):
    val = rep.apply_campaign_outcome(conn, character_id=7, campaign_id=1, outcome="death")
    assert val == -rep.REP_DEATH_PENALTY


def test_apply_campaign_outcome_unknown_outcome_is_noop(conn):
    """Nieznany outcome nie rusza reputacji (bezpieczne wywołanie)."""
    val = rep.apply_campaign_outcome(conn, character_id=7, campaign_id=1, outcome="whatever")
    assert val is None
    assert rep.get_reputation(conn, 7, "kresy") == 0


# ─── Integration: shop_service reputation wiring ─────────────────────────────

def test_shop_buy_multiplier_uses_regional_reputation(conn):
    """buy_item's reputation seam: dodatnia reputacja bohatera → mnożnik ceny < 1."""
    from app.services import shop_service
    conn.execute("CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER)")
    conn.execute("INSERT INTO characters (id, campaign_id) VALUES (7, 1)")
    rep.adjust_reputation(conn, 7, "kresy", 50)
    assert shop_service._reputation_buy_multiplier(conn, 7) < 1.0


def test_shop_buy_multiplier_neutral_without_campaign(conn):
    """Bohater bez kampanii / bez reputacji → mnożnik 1.0 (brak wpływu)."""
    from app.services import shop_service
    conn.execute("CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER)")
    conn.execute("INSERT INTO characters (id, campaign_id) VALUES (8, NULL)")
    assert shop_service._reputation_buy_multiplier(conn, 8) == 1.0
