"""TDD: Issue #1111 — Canonical hex directions (fix: zachód ≠ południowy-zachód)."""
import sys
sys.path.insert(0, "/app")


# ─── RED: These fail with the buggy _DIRECTION_KEYWORDS in turn_pipeline ─────

def test_zachod_maps_to_west_not_southwest():
    """'zachód' must map to (-1,0)=west, NOT (-1,1)=południowy-zachód."""
    from app.services.turn_pipeline import _DIRECTION_KEYWORDS
    got = _DIRECTION_KEYWORDS["zachód"]
    assert got == (-1, 0), f"zachód should be (-1,0) but got {got} — that's południowy-zachód!"


def test_zachodni_maps_to_west():
    """'zachodni' (adjective form) must map to (-1,0)."""
    from app.services.turn_pipeline import _DIRECTION_KEYWORDS
    got = _DIRECTION_KEYWORDS["zachodni"]
    assert got == (-1, 0), f"zachodni should be (-1,0) but got {got}"


def test_west_english_maps_to_correct_offset():
    """'west' must map to (-1,0)."""
    from app.services.turn_pipeline import _DIRECTION_KEYWORDS
    got = _DIRECTION_KEYWORDS["west"]
    assert got == (-1, 0), f"west should be (-1,0) but got {got}"


def test_ascii_zachod_maps_to_west():
    """ASCII 'zachod' (no diacritics) must map to (-1,0)."""
    from app.services.turn_pipeline import _DIRECTION_KEYWORDS
    got = _DIRECTION_KEYWORDS["zachod"]
    assert got == (-1, 0), f"zachod should be (-1,0) but got {got}"


def test_direction_keywords_consistent_with_hex_directions():
    """Every primary direction in _HEX_DIRECTIONS must match _DIRECTION_KEYWORDS."""
    from app.services.turn_pipeline import _DIRECTION_KEYWORDS
    from app.services.location_context_injector import _HEX_DIRECTIONS

    mismatches = []
    for dq, dr, name in _HEX_DIRECTIONS:
        if name not in _DIRECTION_KEYWORDS:
            mismatches.append(f"'{name}' missing from _DIRECTION_KEYWORDS")
            continue
        actual = _DIRECTION_KEYWORDS[name]
        if actual != (dq, dr):
            mismatches.append(
                f"'{name}': _HEX_DIRECTIONS=({dq},{dr}) but _DIRECTION_KEYWORDS={actual}"
            )
    assert not mismatches, "Direction table mismatch:\n" + "\n".join(mismatches)


# ─── GREEN: These pass after canonical module created ─────────────────────────

def test_canonical_module_exists():
    """hex_directions.py canonical module must exist and export DIRECTION_KEYWORDS."""
    import importlib
    hd = importlib.import_module("app.services.hex_directions")
    assert hasattr(hd, "DIRECTION_KEYWORDS"), "hex_directions must export DIRECTION_KEYWORDS"
    assert hasattr(hd, "HEX_DIRECTIONS"), "hex_directions must export HEX_DIRECTIONS"


def test_canonical_module_zachod_correct():
    """Canonical module must have zachód → (-1,0)."""
    from app.services.hex_directions import DIRECTION_KEYWORDS
    assert DIRECTION_KEYWORDS["zachód"] == (-1, 0)
    assert DIRECTION_KEYWORDS["zachód"] != (-1, 1), "(-1,1) is południowy-zachód, not zachód"


def test_canonical_six_directions_present():
    """Canonical module must define all 6 flat-top directions."""
    from app.services.hex_directions import HEX_DIRECTIONS
    offsets = {(dq, dr) for dq, dr, _ in HEX_DIRECTIONS}
    expected = {(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)}
    assert offsets == expected, f"Missing or extra directions: {offsets ^ expected}"


# ─── Backward compat: other directions must still be correct ─────────────────

def test_polnoc_still_correct():
    from app.services.turn_pipeline import _DIRECTION_KEYWORDS
    assert _DIRECTION_KEYWORDS["północ"] == (0, -1)


def test_wschod_still_correct():
    from app.services.turn_pipeline import _DIRECTION_KEYWORDS
    assert _DIRECTION_KEYWORDS["wschód"] == (1, 0)


def test_poludniowy_zachod_still_correct():
    from app.services.turn_pipeline import _DIRECTION_KEYWORDS
    assert _DIRECTION_KEYWORDS["południowy-zachód"] == (-1, 1)


def test_polnocny_wschod_still_correct():
    from app.services.turn_pipeline import _DIRECTION_KEYWORDS
    assert _DIRECTION_KEYWORDS["północny-wschód"] == (1, -1)
