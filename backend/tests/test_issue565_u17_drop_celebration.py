"""TDD: Issue #565 (U17) — Celebracja dropu afiksowego + porównanie z założonym.

Zakres testów backendu (deterministyczne, bez DB — czysta matematyka diffu):
Mechanika LICZY porównanie dropu z założonym sprzętem (Zasada 1-5: kod liczy, LLM tylko narruje).

Testowane czyste funkcje z loot_service:
- dice_average("1d8+2")        → średnia rzutu, bez RNG (do porównania broni)
- item_combat_metrics(detail)  → broń {damage, attack_bonus} / zbroja {ac}, z bonusami afiksów
- compare_item_metrics(new, eq)→ podpisany diff (dodatni = lepszy drop)
- suggested_slot_for_item      → main_hand / torso / head / l_arm ...
- is_special_drop(rarity,affix)→ czy pokazać kartę celebracji (afiks LUB rarity>=2)
- rarity_label(n)              → common/rare/epic

Pełna ścieżka DB (build_drop_comparison + enrichment claim + przycisk Załóż)
pokryta Playwright spec issue_565_u17_drop_celebration.spec.js na żywej bazie DEV.
"""
import sys
sys.path.insert(0, "/app")

import pytest

from app.services.loot_service import (
    dice_average,
    item_combat_metrics,
    compare_item_metrics,
    suggested_slot_for_item,
    is_special_drop,
    rarity_label,
)


# ─── dice_average — deterministyczna średnia (bez RNG) ───────────────────────

def test_dice_average_simple_die():
    """1d8 → średnia 4.5 (nie losowanie)."""
    assert dice_average("1d8") == 4.5


def test_dice_average_with_bonus():
    """2d6+2 → 2*3.5 + 2 = 9.0."""
    assert dice_average("2d6+2") == 9.0


def test_dice_average_with_negative():
    """1d6-1 → 3.5 - 1 = 2.5."""
    assert dice_average("1d6-1") == 2.5


def test_dice_average_garbage_is_zero():
    """Pusty/zły zapis → 0.0, nigdy wyjątek."""
    assert dice_average("") == 0.0
    assert dice_average(None) == 0.0
    assert dice_average("xyz") == 0.0


# ─── item_combat_metrics — redukcja przedmiotu do liczb porównywalnych ───────

def test_weapon_metrics_include_affix_damage():
    """Broń 1d8 + afiks damage_bonus +2 → damage = 4.5 + 2 = 6.5."""
    detail = {
        "item_type": "weapon",
        "weapon": {"damage_die": "1d8", "attack_bonus": 1},
        "affixes": [{"name": "Ostry", "effects": [{"type": "damage_bonus", "value": 2}]}],
    }
    m = item_combat_metrics(detail)
    assert m["item_type"] == "weapon"
    assert m["damage"] == 6.5
    assert m["attack_bonus"] == 1


def test_weapon_metrics_no_affix():
    """Broń bez afiksów — sama kość."""
    detail = {"item_type": "weapon", "weapon": {"damage_die": "1d6"}, "affixes": []}
    assert item_combat_metrics(detail)["damage"] == 3.5


def test_armor_metrics_include_affix_ac():
    """Zbroja ac_bonus 2 + afiks ac_bonus +1 → ac = 3."""
    detail = {
        "item_type": "armor",
        "armor": {"ac_bonus": 2, "coverage": "torso"},
        "affixes": [{"name": "Wzmocniony", "effects": [{"type": "ac_bonus", "value": 1}]}],
    }
    m = item_combat_metrics(detail)
    assert m["item_type"] == "armor"
    assert m["ac"] == 3


# ─── compare_item_metrics — podpisany diff dropu vs założony ──────────────────

def test_compare_weapon_better_drop():
    """Lepsza broń → dodatni diff damage."""
    new = {"item_type": "weapon", "weapon": {"damage_die": "1d10"}, "affixes": []}   # 5.5
    eq = {"item_type": "weapon", "weapon": {"damage_die": "1d6"}, "affixes": []}     # 3.5
    out = compare_item_metrics(new, eq)
    assert out["diff"]["damage"] == 2.0
    assert out["new"]["damage"] == 5.5
    assert out["equipped"]["damage"] == 3.5


def test_compare_weapon_worse_drop():
    """Gorsza broń → ujemny diff damage."""
    new = {"item_type": "weapon", "weapon": {"damage_die": "1d4"}, "affixes": []}    # 2.5
    eq = {"item_type": "weapon", "weapon": {"damage_die": "1d8"}, "affixes": []}     # 4.5
    out = compare_item_metrics(new, eq)
    assert out["diff"]["damage"] == -2.0


def test_compare_no_equipped_gives_null_diff():
    """Nic nie założone → diff None (frontend pokaże 'brak porównania'), new wciąż policzony."""
    new = {"item_type": "weapon", "weapon": {"damage_die": "1d8"}, "affixes": []}
    out = compare_item_metrics(new, None)
    assert out["equipped"] is None
    assert out["diff"]["damage"] is None
    assert out["new"]["damage"] == 4.5


# ─── suggested_slot_for_item ─────────────────────────────────────────────────

def test_slot_weapon_is_main_hand():
    assert suggested_slot_for_item({"item_type": "weapon", "weapon": {}}) == "main_hand"


def test_slot_armor_by_coverage():
    assert suggested_slot_for_item({"item_type": "armor", "armor": {"coverage": "head"}}) == "head"
    assert suggested_slot_for_item({"item_type": "armor", "armor": {"coverage": "full"}}) == "torso"
    assert suggested_slot_for_item({"item_type": "armor", "armor": {"coverage": "limb_arm"}}) == "l_arm"


def test_slot_consumable_is_none():
    assert suggested_slot_for_item({"item_type": "consumable"}) is None


# ─── is_special_drop — kiedy pokazać kartę celebracji ────────────────────────

def test_special_when_has_affix():
    """Common (rarity 1) ale z afiksem → karta celebracji."""
    assert is_special_drop(1, [{"name": "Ostry", "effects": []}]) is True


def test_special_when_rare_no_affix():
    """Rare (rarity 2) bez afiksu → karta celebracji."""
    assert is_special_drop(2, []) is True


def test_not_special_common_no_affix():
    """Common bez afiksu → BRAK celebracji (zwykły drop, plain popup)."""
    assert is_special_drop(1, []) is False


# ─── rarity_label ────────────────────────────────────────────────────────────

def test_rarity_labels():
    assert rarity_label(1) == "common"
    assert rarity_label(2) == "rare"
    assert rarity_label(3) == "epic"
    assert rarity_label(None) == "common"
