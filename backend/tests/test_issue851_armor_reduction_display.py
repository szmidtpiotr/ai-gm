"""TDD: Issue #851 — wyświetlanie redukcji pancerza na karcie obrażeń.

Dwa poziomy testów:
1. Inspekcja kodu JS (RED→GREEN przy fixie): buildDamageStage musi zwracać armorReduction
   i showDmg musi go wyświetlać jako "− N Pancerz" w formule karty obrażeń.
2. Backend kontrakt (GREEN od razu): apply_defense_model zwraca armor_reduction gdy ac_base > 10,
   a równanie rozliczenia zachodzi dla prostego ataku (dokumentuje niezmiennik API).
"""
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.combat_service import (  # noqa: E402
    ARMOR_REDUCTION_OFFSET,
    apply_defense_model,
    _armor_value,
)

# Ścieżka do app.js — testy inspekcji kodu JS.
# W kontenerze: docker cp frontend/front/js/app.js ai-gm-dev-backend-1:/app/tests/app.js
_APP_JS = Path(__file__).resolve().parent / "app.js"


# ─── FAZA RED: inspekcja kodu JS ────────────────────────────────────────────

def test_buildDamageStage_returns_armorReduction():
    """buildDamageStage() musi zwracać armorReduction z data.armor_reduction.

    Bez tego pola frontend nigdy nie dotrze do informacji o pancerzu wroga
    i nie może wyświetlić '− N Pancerz' na karcie obrażeń (#851).
    """
    content = _APP_JS.read_text(encoding="utf-8")
    match = re.search(
        r'function buildDamageStage\(data\)(.*?)(?=^function |\Z)',
        content, re.DOTALL | re.MULTILINE
    )
    assert match, "buildDamageStage nie znaleziona w app.js"
    func_body = match.group(1)
    assert "armorReduction" in func_body, (
        "buildDamageStage nie zawiera 'armorReduction' — fix #851 wymaga dodania "
        "armorReduction: Number(data.armor_reduction ?? 0) do obiektu zwrotnego"
    )


def test_showDmg_displays_pancerz_label():
    """runDamageStage showDmg musi wyświetlać '− N Pancerz' gdy armorReduction > 0.

    Gracz musi widzieć pełne równanie: 🎲 1 + 3 − 1 Pancerz = 3
    zamiast skróconego: 🎲 1 + 3 = 3 (brakuje wyjaśnienia dlaczego suma się nie zgadza).
    """
    content = _APP_JS.read_text(encoding="utf-8")
    # showDmg jest wewnątrz runDamageStage, szukamy 'Pancerz' w tej okolicy (linia z armorReduction)
    assert "armorReduction" in content and (
        "Pancerz" in content.split("runDamageStage")[1].split("runAttackStage")[0]
        if "runDamageStage" in content and "runAttackStage" in content
        else "Pancerz" in content
    ), (
        "app.js nie wyświetla 'Pancerz' w formule obrażeń — "
        "fix #851 wymaga: if (ds.armorReduction) line += ` − ${ds.armorReduction} Pancerz`"
    )


# ─── Backend kontrakt (dokumentacja niezmiennika API) ──────────────────────

def test_armor_reduction_nonzero_when_enemy_has_armor():
    """Wróg z ac_base > 10 → armor_reduction > 0 w odpowiedzi apply_defense_model."""
    ac_base = 12  # armor = max(0, 12 - 10) = 2
    res = apply_defense_model(
        base_damage=8, attack_total=15, defense_stat=ac_base, ignore_armor=False
    )
    expected = _armor_value(ac_base)
    assert expected > 0
    assert res["armor_reduction"] == expected


def test_display_equation_holds_simple_attack():
    """Niezmiennik karty: sum(rolls) + mod_stat − armor_reduction == damage.

    Dla prostego ataku (bez crit, flat_bonus, sneak) równanie musi zachodzić
    żeby frontend mógł pokazać kompletną formułę i gracz mógł ją zweryfikować.
    """
    rolls = [1]   # wynik kości (przykład z issue: kość=1)
    mod = 3       # modyfikator STR
    ac_base = 11  # armor = max(0, 11-10) = 1

    base_dmg = sum(rolls) + mod  # = 4
    res = apply_defense_model(
        base_damage=base_dmg, attack_total=10, defense_stat=ac_base, ignore_armor=False
    )

    api_damage = res["final"]            # = 3 (trafi do out["damage"])
    api_armor_red = res["armor_reduction"]  # = 1 (trafi do out["armor_reduction"])

    assert sum(rolls) + mod - api_armor_red == api_damage, (
        f"Niezmiennik karty nie zachodzi: "
        f"{sum(rolls)} + {mod} − {api_armor_red} ≠ {api_damage}"
    )


def test_no_armor_reduction_when_no_armor():
    """Wróg bez pancerza (ac_base ≤ 10) → armor_reduction=0, karta bez '− N Pancerz'."""
    res = apply_defense_model(
        base_damage=5, attack_total=15, defense_stat=10, ignore_armor=False
    )
    assert res["armor_reduction"] == 0


def test_nat20_produces_no_armor_reduction():
    """Nat 20 pomija pancerz → armor_reduction=0, karta pokazuje czyste ×2 bez odliczenia."""
    res = apply_defense_model(
        base_damage=10, attack_total=20, defense_stat=16, ignore_armor=True
    )
    assert res["armor_reduction"] == 0
