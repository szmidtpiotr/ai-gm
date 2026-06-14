"""TDD: Issue #563 (U15) — jedno źródło prawdy dla tierów ran (label+kolor+kara).

Cel: scalić dwa rozjechane źródła progów (wound_utils 75/50/25 vs
economy_service 76/51/26/11) w jedną tabelę WOUND_TIERS, z której derywują
zarówno kara do rzutu, jak i etykieta + kolor. Kary 0/-1/-2/-4 bez zmian.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.wound_utils import wound_penalty, wound_tier, WOUND_TIERS
from app.services.economy_service import get_wound_label


# ─── Test główny — jedno źródło prawdy: wound_tier() ──────────────────────────

def test_wound_tier_returns_full_payload():
    """wound_tier() zwraca komplet: tier, label, color, penalty, pct."""
    t = wound_tier(40, 100)  # 40% → moderate
    assert t["tier"] == "moderate"
    assert t["label"] == "Ciężko Ranny"
    assert t["color"] == "#ff9800"
    assert t["penalty"] == -2
    assert round(t["pct"]) == 40


def test_wound_tier_full_health_has_no_label():
    """Powyżej 75% — brak etykiety, kara 0, kolor zielony."""
    t = wound_tier(90, 100)
    assert t["tier"] == "healthy"
    assert t["label"] is None
    assert t["penalty"] == 0


def test_wound_tier_ladder_label_and_penalty_agree():
    """Każdy tier wystawia ten sam label i karę z jednej tabeli."""
    cases = [
        (80, "healthy", None, 0),
        (60, "minor", "Ranny", -1),
        (40, "moderate", "Ciężko Ranny", -2),
        (20, "serious", "Poważnie Ranny", -4),
        (5, "near_death", "Na Skraju Śmierci", -4),
    ]
    for hp, tier, label, pen in cases:
        t = wound_tier(hp, 100)
        assert t["tier"] == tier, f"hp={hp}: tier {t['tier']} != {tier}"
        assert t["label"] == label, f"hp={hp}: label {t['label']!r} != {label!r}"
        assert t["penalty"] == pen, f"hp={hp}: penalty {t['penalty']} != {pen}"


def test_wound_tiers_table_is_single_source():
    """WOUND_TIERS to jawna tabela tierów — 5 pozycji z pełnym payloadem."""
    assert len(WOUND_TIERS) == 5
    for row in WOUND_TIERS:
        assert "tier" in row and "color" in row and "penalty" in row
    # kary muszą być dokładnie obecną drabiną (bez zmiany mechaniki)
    penalties = [r["penalty"] for r in WOUND_TIERS]
    assert penalties == [0, -1, -2, -4, -4]


# ─── get_wound_label deleguje do wound_tier (spójność label↔kara) ─────────────

def test_get_wound_label_matches_tier_at_boundaries():
    """get_wound_label musi zwracać label z tej samej tabeli co kara."""
    # 50% — granica: w jednym źródle prawdy label i kara muszą być z tego
    # samego progu. pct=50 NIE jest > 50 → moderate (Ciężko Ranny, -2).
    lbl = get_wound_label(50, 100)
    t = wound_tier(50, 100)
    assert lbl["label"] == t["label"] == "Ciężko Ranny"
    assert t["penalty"] == -2


def test_get_wound_label_healthy_returns_none():
    """Powyżej progu zdrowia — brak etykiety."""
    assert get_wound_label(90, 100)["label"] is None


# ─── Backward compatibility — wound_penalty bez zmian ─────────────────────────

def test_wound_penalty_unchanged():
    """Stara funkcja wound_penalty() zwraca identyczne wartości jak dotąd."""
    assert wound_penalty(100, 100) == 0
    assert wound_penalty(60, 100) == -1
    assert wound_penalty(40, 100) == -2
    assert wound_penalty(10, 100) == -4
    assert wound_penalty(5, 100) == -4
    assert wound_penalty(10, 0) == 0  # max_hp 0 → brak kary


def test_wound_penalty_derives_from_tier():
    """wound_penalty() i wound_tier() zawsze zgodne (jedno źródło)."""
    for hp in (100, 76, 75, 51, 50, 26, 25, 11, 10, 1, 0):
        assert wound_penalty(hp, 100) == wound_tier(hp, 100)["penalty"]
