"""TDD: Issue #853 — Rzuty tab: damage records muszą zawierać armor_reduction w meta.

Dwa poziomy testów:
1. Inspekcja kodu (RED→GREEN przy fixie): combat_service record_dice_roll(damage)
   musi zawierać armor_reduction, nat20_ignored_armor i margin_damage w meta.
2. Frontend: campaigns.js Rzuty tab musi wyświetlać kalkulację zbroi dla wierszy Obrażenia.
3. Backward compat: apply_defense_model API bez zmian.
"""
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.combat_service import apply_defense_model  # noqa: E402

_COMBAT_SVC = Path(__file__).resolve().parents[1] / "app" / "services" / "combat_service.py"

# campaigns.js: docker cp frontend/admin/sections/campaigns.js ai-gm-dev-backend-1:/app/tests/campaigns.js
_CAMPAIGNS_JS = Path(__file__).resolve().parent / "campaigns.js"


# ─── RED: backend meta musi zawierać pola kalkulacji zbroi ──────────────────

def test_damage_record_meta_includes_armor_reduction():
    """record_dice_roll(damage) musi zawierać armor_reduction w meta.

    Bez tego Rzuty tab nigdy nie pokaże '3 - 1 (zbroja) = 2 dmg' (#853).
    """
    content = _COMBAT_SVC.read_text(encoding="utf-8")
    idx = content.find('roll_type="damage"')
    assert idx >= 0, "Nie znaleziono record_dice_roll z roll_type='damage' w combat_service.py"
    # Szukamy meta={ w bloku ok. 700 znaków po roll_type="damage" (meta dict po modifiers)
    block = content[idx: idx + 1000]
    assert "armor_reduction" in block, (
        "meta w record_dice_roll(damage) nie zawiera 'armor_reduction' — "
        "fix #853: dodaj armor_reduction: out.get('armor_reduction', 0) do meta"
    )


def test_damage_record_meta_includes_nat20_flag():
    """record_dice_roll(damage) musi zawierać nat20_ignored_armor w meta."""
    content = _COMBAT_SVC.read_text(encoding="utf-8")
    idx = content.find('roll_type="damage"')
    assert idx >= 0, "Nie znaleziono record_dice_roll z roll_type='damage'"
    block = content[idx: idx + 1000]
    assert "nat20_ignored_armor" in block, (
        "meta nie zawiera 'nat20_ignored_armor' — "
        "fix #853: dodaj nat20_ignored_armor: bool(player_nat20) do meta"
    )


def test_damage_record_meta_includes_margin_damage():
    """record_dice_roll(damage) musi zawierać margin_damage w meta."""
    content = _COMBAT_SVC.read_text(encoding="utf-8")
    idx = content.find('roll_type="damage"')
    assert idx >= 0, "Nie znaleziono record_dice_roll z roll_type='damage'"
    block = content[idx: idx + 1000]
    assert "margin_damage" in block, (
        "meta nie zawiera 'margin_damage' — "
        "fix #853: dodaj margin_damage: out.get('margin_damage_bonus', 0) do meta"
    )


# ─── RED: frontend musi wyświetlać kalkulację dla damage rows ──────────────

def test_frontend_rzuty_shows_armor_calc():
    """campaigns.js Rzuty tab musi wyświetlać kalkulację zbroi dla wierszy Obrażenia (#853).

    Oczekiwane: gdy meta.armor_reduction > 0, kolumna Szczegóły pokazuje
    '{pre} - {arm} (zbroja) = {final} dmg' zamiast tylko metaBits.
    """
    if not _CAMPAIGNS_JS.exists():
        import pytest
        pytest.skip("campaigns.js not found in tests/ — run: docker cp frontend/admin/sections/campaigns.js ai-gm-dev-backend-1:/app/tests/campaigns.js")

    content = _CAMPAIGNS_JS.read_text(encoding="utf-8")
    idx = content.find("tab === 'dice'")
    assert idx >= 0, "Nie znaleziono bloku tab==='dice' w campaigns.js"
    # Szukamy 'armor_reduction' w bloku Rzuty tab (ok. 3000 znaków)
    block = content[idx: idx + 4000]
    assert "armor_reduction" in block, (
        "campaigns.js Rzuty tab nie zawiera 'armor_reduction' — "
        "fix #853: dodaj wyświetlanie kalkulacji zbroi w kolumnie Szczegóły"
    )


# ─── Backward compat: apply_defense_model API niezmieniony ──────────────────

def test_apply_defense_model_returns_all_fields():
    """apply_defense_model nadal zwraca {final, margin_bonus, armor_reduction}."""
    res = apply_defense_model(
        base_damage=5, attack_total=15, defense_stat=12, ignore_armor=False
    )
    assert set(res.keys()) >= {"final", "margin_bonus", "armor_reduction"}
    assert res["armor_reduction"] == 2  # ac_base=12 → armor=max(0,12-10)=2
    assert res["final"] == 3  # 5 - 2 = 3


def test_apply_defense_model_nat20_no_reduction():
    """Nat 20 (ignore_armor=True) → armor_reduction=0 (zbroja ignorowana)."""
    res = apply_defense_model(
        base_damage=10, attack_total=20, defense_stat=16, ignore_armor=True
    )
    assert res["armor_reduction"] == 0
    assert res["final"] == 10


def test_apply_defense_model_no_armor():
    """ac_base <= 10 → armor_reduction=0."""
    res = apply_defense_model(
        base_damage=6, attack_total=12, defense_stat=10, ignore_armor=False
    )
    assert res["armor_reduction"] == 0
    assert res["final"] == 6


def test_apply_defense_model_zero_damage_safe():
    """base_damage=0 → final=0, brak crashu."""
    res = apply_defense_model(base_damage=0, attack_total=20, defense_stat=15, ignore_armor=False)
    assert res["final"] == 0
    assert res["armor_reduction"] == 0
