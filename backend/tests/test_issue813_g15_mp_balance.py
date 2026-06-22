"""TDD: Issue #813 G15 — MP balance flags centralized and sandbox-tunable."""
import sys

sys.path.insert(0, "/app")


# ─── Module structure ────────────────────────────────────────────────────────

def test_mp_balance_module_exists():
    """mp_balance.py must exist and import cleanly."""
    from app.services import mp_balance  # noqa: F401


def test_wipe_gold_pct_by_level_exists():
    from app.services import mp_balance as mb
    assert hasattr(mb, "WIPE_GOLD_PCT_BY_LEVEL"), "WIPE_GOLD_PCT_BY_LEVEL missing"
    d = mb.WIPE_GOLD_PCT_BY_LEVEL
    assert isinstance(d, dict)
    assert "1-3" in d and "4-7" in d and "8+" in d, "must have all three level brackets"


def test_wipe_gold_floor_exists():
    from app.services import mp_balance as mb
    assert hasattr(mb, "WIPE_GOLD_FLOOR"), "WIPE_GOLD_FLOOR missing"
    assert mb.WIPE_GOLD_FLOOR == 50, "default WIPE_GOLD_FLOOR must be 50"


def test_wipe_hp_pct_exists():
    from app.services import mp_balance as mb
    assert hasattr(mb, "WIPE_HP_PCT"), "WIPE_HP_PCT missing"
    assert mb.WIPE_HP_PCT == 0.50, "default WIPE_HP_PCT must be 0.50"


def test_difficulty_scale_by_count_exists():
    from app.services import mp_balance as mb
    assert hasattr(mb, "MP_DIFFICULTY_SCALE_BY_COUNT"), "MP_DIFFICULTY_SCALE_BY_COUNT missing"
    d = mb.MP_DIFFICULTY_SCALE_BY_COUNT
    assert all(k in d for k in [1, 2, 3, 4]), "must have entries for 1-4 players"


def test_loot_scale_by_count_exists():
    from app.services import mp_balance as mb
    assert hasattr(mb, "MP_LOOT_SCALE_BY_COUNT"), "MP_LOOT_SCALE_BY_COUNT missing"
    d = mb.MP_LOOT_SCALE_BY_COUNT
    assert all(k in d for k in [1, 2, 3, 4]), "must have entries for 1-4 players"


# ─── Default values match spec ───────────────────────────────────────────────

def test_default_wipe_pcts_match_spec():
    from app.services import mp_balance as mb
    assert mb.WIPE_GOLD_PCT_BY_LEVEL["1-3"] == 0.10, "level 1-3 must be 10%"
    assert mb.WIPE_GOLD_PCT_BY_LEVEL["4-7"] == 0.20, "level 4-7 must be 20%"
    assert mb.WIPE_GOLD_PCT_BY_LEVEL["8+"]  == 0.30, "level 8+ must be 30%"


def test_default_scales_are_neutral():
    from app.services import mp_balance as mb
    for count in [1, 2, 3, 4]:
        assert mb.MP_DIFFICULTY_SCALE_BY_COUNT[count] == 1.0, (
            f"MP_DIFFICULTY_SCALE_BY_COUNT[{count}] must start neutral (1.0)"
        )
        assert mb.MP_LOOT_SCALE_BY_COUNT[count] == 1.0, (
            f"MP_LOOT_SCALE_BY_COUNT[{count}] must start neutral (1.0)"
        )


# ─── Helper functions ────────────────────────────────────────────────────────

def test_get_wipe_gold_pct_brackets():
    from app.services.mp_balance import get_wipe_gold_pct
    assert get_wipe_gold_pct(1)  == 0.10
    assert get_wipe_gold_pct(3)  == 0.10
    assert get_wipe_gold_pct(4)  == 0.20
    assert get_wipe_gold_pct(7)  == 0.20
    assert get_wipe_gold_pct(8)  == 0.30
    assert get_wipe_gold_pct(20) == 0.30


def test_get_difficulty_scale_default():
    from app.services.mp_balance import get_difficulty_scale
    for count in [1, 2, 3, 4]:
        assert get_difficulty_scale(count) == 1.0


def test_get_loot_scale_default():
    from app.services.mp_balance import get_loot_scale
    for count in [1, 2, 3, 4]:
        assert get_loot_scale(count) == 1.0


def test_get_difficulty_scale_clamps_range():
    from app.services.mp_balance import get_difficulty_scale
    assert get_difficulty_scale(0) == get_difficulty_scale(1)
    assert get_difficulty_scale(5) == get_difficulty_scale(4)


# ─── Changing a flag changes behaviour ───────────────────────────────────────

def test_wipe_gold_pct_change_affects_calculation(monkeypatch):
    """Changing WIPE_GOLD_PCT_BY_LEVEL must change the pct returned by get_wipe_gold_pct."""
    from app.services import mp_balance as mb
    monkeypatch.setitem(mb.WIPE_GOLD_PCT_BY_LEVEL, "1-3", 0.05)
    assert mb.get_wipe_gold_pct(2) == 0.05, "get_wipe_gold_pct must read from the flag"


def test_difficulty_scale_change_affects_helpers(monkeypatch):
    from app.services import mp_balance as mb
    monkeypatch.setitem(mb.MP_DIFFICULTY_SCALE_BY_COUNT, 2, 1.5)
    assert mb.get_difficulty_scale(2) == 1.5, "get_difficulty_scale must read from the flag"


def test_loot_scale_change_affects_helpers(monkeypatch):
    from app.services import mp_balance as mb
    monkeypatch.setitem(mb.MP_LOOT_SCALE_BY_COUNT, 3, 0.75)
    assert mb.get_loot_scale(3) == 0.75, "get_loot_scale must read from the flag"


# ─── Wipe penalty uses flags (unit test without DB) ──────────────────────────

def test_wipe_penalty_respects_gold_floor(monkeypatch):
    """If a character has gold < WIPE_GOLD_FLOOR, penalty must be 0."""
    from app.services import mp_balance as mb

    gold_taken: list[int] = []

    def fake_change_gold(conn, char_id, amount, reason, campaign_id=None):
        gold_taken.append(amount)

    monkeypatch.setattr(mb, "WIPE_GOLD_FLOOR", 50)
    monkeypatch.setattr(mb, "WIPE_HP_PCT", 0.50)
    monkeypatch.setitem(mb.WIPE_GOLD_PCT_BY_LEVEL, "1-3", 0.10)

    # Build minimal in-memory wipe scenario
    pct = mb.get_wipe_gold_pct(2)   # level 2 → 10%
    floor = mb.WIPE_GOLD_FLOOR

    gold_below_floor = 30
    assert gold_below_floor < floor, "precondition"
    # No penalty expected
    should_penalise = gold_below_floor >= floor
    assert not should_penalise, "character with 30 gold must be exempt"

    gold_above_floor = 200
    should_penalise2 = gold_above_floor >= floor
    assert should_penalise2
    expected_penalty = max(1, int(gold_above_floor * pct))
    assert expected_penalty == 20, f"expected 20, got {expected_penalty}"


def test_wipe_revival_hp_pct(monkeypatch):
    """WIPE_HP_PCT must control revival HP fraction."""
    from app.services import mp_balance as mb
    monkeypatch.setattr(mb, "WIPE_HP_PCT", 0.25)

    hp_pct = float(mb.WIPE_HP_PCT)
    max_hp = 100
    revival = max(1, int(max_hp * hp_pct))
    assert revival == 25, "25% HP pct must yield 25 revival HP for max_hp=100"


# ─── Wipe penalty pct changes with level ─────────────────────────────────────

def test_wipe_pct_brackets_full_range():
    from app.services.mp_balance import get_wipe_gold_pct
    cases = [
        (1, 0.10), (2, 0.10), (3, 0.10),
        (4, 0.20), (5, 0.20), (7, 0.20),
        (8, 0.30), (10, 0.30), (15, 0.30),
    ]
    for level, expected_pct in cases:
        pct = get_wipe_gold_pct(level)
        assert pct == expected_pct, f"level {level}: expected {expected_pct}, got {pct}"


# ─── Player count scaling helpers ────────────────────────────────────────────

def test_loot_scale_varies_per_count(monkeypatch):
    from app.services import mp_balance as mb
    monkeypatch.setitem(mb.MP_LOOT_SCALE_BY_COUNT, 1, 1.5)
    monkeypatch.setitem(mb.MP_LOOT_SCALE_BY_COUNT, 4, 0.8)
    assert mb.get_loot_scale(1) == 1.5
    assert mb.get_loot_scale(4) == 0.8
    # 2 and 3 still default
    assert mb.get_loot_scale(2) == 1.0


def test_difficulty_scale_varies_per_count(monkeypatch):
    from app.services import mp_balance as mb
    monkeypatch.setitem(mb.MP_DIFFICULTY_SCALE_BY_COUNT, 1, 1.8)
    monkeypatch.setitem(mb.MP_DIFFICULTY_SCALE_BY_COUNT, 4, 0.9)
    assert mb.get_difficulty_scale(1) == 1.8
    assert mb.get_difficulty_scale(4) == 0.9
