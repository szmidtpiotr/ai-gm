"""Fallback test runner for resolve_test_name without pytest.

Usage:
  python3 backend/tests/run_resolve_test_name_checks.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.dice import resolve_test_name


def run():
    success_cases = {
        "Athletics": "athletics",
        "Stealth": "stealth",
        "Awareness": "awareness",
        "Survival": "survival",
        "Lore": "lore",
        "Investigation": "investigation",
        "Arcana": "arcana",
        "Medicine": "medicine",
        "Persuasion": "persuasion",
        "Intimidation": "intimidation",
        "Melee Attack": "melee_attack",
        "Ranged Attack": "ranged_attack",
        "Spell Attack": "spell_attack",
        "Fortitude Save": "fortitude_save",
        "Reflex Save": "reflex_save",
        "Willpower Save": "willpower_save",
        "Arcane Save": "arcane_save",
        "Str Save": "fortitude_save",
        "Con Save": "fortitude_save",
        "Dex Save": "reflex_save",
        "Wis Save": "willpower_save",
        "Int Save": "arcane_save",
        "Cha Save": "willpower_save",
        "Perception": "awareness",
        "Attack": "melee_attack",
        "Initiative": "reflex_save",
        "stealth": "stealth",
        "STEALTH": "stealth",
        " Stealth ": "stealth",
    }

    none_cases = [
        "sTrEnGtH SaVe",
        "FlyingKick",
        "Agility",
        "",
        None,
        "SomeMadeUpSkill d20",
    ]

    failures = []

    for raw, expected in success_cases.items():
        got = resolve_test_name(raw)
        if got != expected:
            failures.append(f"FAIL: resolve_test_name({raw!r}) -> {got!r}, expected {expected!r}")

    for raw in none_cases:
        got = resolve_test_name(raw)
        if got is not None:
            failures.append(f"FAIL: resolve_test_name({raw!r}) -> {got!r}, expected None")

    total = len(success_cases) + len(none_cases)
    passed = total - len(failures)

    print(f"Ran {total} checks: {passed} passed, {len(failures)} failed.")
    if failures:
        print("-" * 60)
        for item in failures:
            print(item)
        return 1

    print("All resolve_test_name checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
