"""Fallback checks for Phase 7.4–7.8 without pytest.

Usage:
  python3 backend/tests/run_dice_full_wiring_checks.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.dice import (
    format_roll_result_message,
    parse_character_sheet,
    parse_roll_command,
    resolve_roll,
)


def _assert_equal(name, got, expected, failures):
    if got != expected:
        failures.append(f"{name}: got {got!r}, expected {expected!r}")


def _assert_true(name, cond, failures):
    if not cond:
        failures.append(f"{name}: condition is False")


def _run_dice_checks(failures):
    sheet = {
        "stats": {"STR": 14, "DEX": 12, "CON": 16, "INT": 8, "WIS": 10, "CHA": 11, "LCK": 10},
        "skills": {"athletics": 3, "stealth": 2, "melee_attack": 1},
    }

    # 7.4 + 7.5: skill roll formula + proficiency at rank >= 3
    out = resolve_roll(sheet, "athletics", raw_roll=10)
    _assert_equal("skill.test", out["test"], "athletics", failures)
    _assert_equal("skill.stat_mod", out["stat_mod"], 2, failures)      # STR 14 => +2
    _assert_equal("skill.skill_rank", out["skill_rank"], 3, failures)
    _assert_equal("skill.proficiency", out["proficiency"], 2, failures)  # rank >= 3
    _assert_equal("skill.total", out["total"], 17, failures)            # 10+2+3+2

    out_low = resolve_roll(sheet, "stealth", raw_roll=10)
    _assert_equal("low_rank.proficiency", out_low["proficiency"], 0, failures)
    _assert_equal("low_rank.total", out_low["total"], 13, failures)     # 10+1+2+0

    out_missing = resolve_roll(sheet, "ranged_attack", raw_roll=10)
    _assert_equal("missing_rank.skill_rank", out_missing["skill_rank"], 0, failures)
    _assert_equal("missing_rank.proficiency", out_missing["proficiency"], 0, failures)

    # 7.8: saves use only stat modifier
    out_save = resolve_roll(sheet, "fortitude_save", raw_roll=10)
    _assert_equal("save.test", out_save["test"], "fortitude_save", failures)
    _assert_equal("save.stat_mod", out_save["stat_mod"], 3, failures)   # CON 16 => +3
    _assert_equal("save.skill_rank", out_save["skill_rank"], 0, failures)
    _assert_equal("save.proficiency", out_save["proficiency"], 0, failures)
    _assert_equal("save.total", out_save["total"], 13, failures)        # 10+3

    # 7.7: nat flags
    nat20 = resolve_roll(sheet, "stealth", raw_roll=20)
    _assert_true("nat20 flag", nat20["is_nat20"] is True, failures)
    _assert_true("nat20 nat1 false", nat20["is_nat1"] is False, failures)

    nat1 = resolve_roll(sheet, "stealth", raw_roll=1)
    _assert_true("nat1 flag", nat1["is_nat1"] is True, failures)
    _assert_true("nat1 nat20 false", nat1["is_nat20"] is False, failures)

    # 7.6: parse command compatibility + optional raw_roll override behavior
    parsed = parse_roll_command("/roll Stealth 14")
    _assert_equal("parse /roll raw skill", parsed["skill"], "stealth", failures)
    _assert_equal("parse /roll raw value", parsed["raw_roll"], 14, failures)

    # 7.4 injection string shape
    msg = format_roll_result_message(
        {"test": "stealth", "raw": 14, "stat_mod": 1, "skill_rank": 2, "proficiency": 0, "total": 17}
    )
    _assert_equal(
        "roll result message format",
        msg,
        "[Roll result: stealth — rolled 14 + 3 = 17]",
        failures,
    )

    # parse_character_sheet helper
    parsed_sheet = parse_character_sheet('{"stats":{"STR":12},"skills":{"athletics":1}}')
    _assert_equal("parse_character_sheet.stats", parsed_sheet["stats"]["STR"], 12, failures)


def _run_game_engine_checks(failures):
    try:
        from app.services import game_engine
    except ModuleNotFoundError as exc:
        print(f"Skipping game_engine checks (missing dependency: {exc}).")
        return 0

    # Monkeypatch imports used inside game_engine module.
    original_load_recent = game_engine.loadrecentturns
    original_build_messages = game_engine.buildmessages
    try:
        game_engine.loadrecentturns = lambda conn, campaign_id, limit=8: []
        game_engine.buildmessages = lambda campaign, character, recentturns, usertext: [
            {"role": "system", "content": "BASE SYSTEM"},
            {"role": "user", "content": usertext},
        ]

        # Standard summary injection
        standard = game_engine.build_narrative_messages(
            conn=None,
            campaign={"id": 1},
            character=None,
            user_text="ignored",
            roll_result_message="[Roll result: stealth — rolled 14 + 3 = 17]",
            roll_result_data={
                "test": "stealth",
                "raw": 14,
                "stat_mod": 1,
                "skill_rank": 2,
                "proficiency": 0,
                "total": 17,
                "is_nat20": False,
                "is_nat1": False,
            },
        )
        _assert_true("standard inject marker", "ROLL RESULT: stealth check — rolled 17" in standard[0]["content"], failures)

        # Nat20 injection
        nat20 = game_engine.build_narrative_messages(
            conn=None,
            campaign={"id": 1},
            character=None,
            user_text="ignored",
            roll_result_message="[Roll result: attack — rolled 20 + 4 = 24]",
            roll_result_data={
                "test": "melee_attack",
                "raw": 20,
                "stat_mod": 2,
                "skill_rank": 2,
                "proficiency": 0,
                "total": 24,
                "is_nat20": True,
                "is_nat1": False,
            },
        )
        _assert_true("nat20 inject marker", "CRITICAL SUCCESS (Natural 20)" in nat20[0]["content"], failures)

        # Nat1 injection
        nat1 = game_engine.build_narrative_messages(
            conn=None,
            campaign={"id": 1},
            character=None,
            user_text="ignored",
            roll_result_message="[Roll result: stealth — rolled 1 + 3 = 4]",
            roll_result_data={
                "test": "stealth",
                "raw": 1,
                "stat_mod": 1,
                "skill_rank": 2,
                "proficiency": 0,
                "total": 4,
                "is_nat20": False,
                "is_nat1": True,
            },
        )
        _assert_true("nat1 inject marker", "CRITICAL FAILURE (Natural 1)" in nat1[0]["content"], failures)
    finally:
        game_engine.loadrecentturns = original_load_recent
        game_engine.buildmessages = original_build_messages
    return 3


def main():
    failures = []
    total = 19
    _run_dice_checks(failures)
    total += _run_game_engine_checks(failures)

    passed = total - len(failures)
    print(f"Ran {total} checks: {passed} passed, {len(failures)} failed.")
    if failures:
        print("-" * 70)
        for item in failures:
            print("FAIL:", item)
        return 1
    print("All Phase 7.4–7.8 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
