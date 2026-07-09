"""Regression: streaming turn path must fire a dice popup when the narrator emits
a plain-text "Roll <skill> d20" line with no JSON envelope and no [SKILL_TEST] tag.

Bug: GM narration ended with an English "Roll Stealth d20" line (plain prose,
streamed). The streaming path only sourced skill tests from [SKILL_TEST] tags or
the JSON `roll_cue` field, so no dice popup appeared ("brak rzutu"). The
non-streaming path already scanned the plain-text tail (#53 fix 3); this locks the
tail parse + skill resolution the streaming fallback depends on.
"""
import re

from app.services.dice import resolve_test_name

_TAIL_RE = re.compile(r"^Roll\s+.+?\s+d\d+$", re.IGNORECASE)
_CAP_RE = re.compile(r"^Roll (.+?) d\d+$", re.IGNORECASE)


def _last_cue_line(prose: str) -> str:
    """Mirror the streaming plain-text tail scan: inspect only the last non-empty line."""
    for line in reversed((prose or "").rstrip().splitlines()):
        s = line.strip()
        if not s:
            continue
        return s if _TAIL_RE.match(s) else ""
    return ""


def test_plaintext_tail_roll_stealth_resolves_to_stealth():
    prose = (
        "Godziny w kuźni wloką się ciężko...\n"
        "Przy młynie i składach opału znajdziesz odpowiedź albo kłopot.\n"
        "Roll Stealth d20"
    )
    cue = _last_cue_line(prose)
    assert cue == "Roll Stealth d20"
    name = _CAP_RE.match(cue).group(1).strip()
    assert resolve_test_name(name) == "stealth"


def test_non_roll_tail_line_is_ignored():
    prose = "Idziesz ku młynowi.\nCoś porusza się w cieniu."
    assert _last_cue_line(prose) == ""


def test_only_last_line_inspected():
    # A roll cue buried above other prose must NOT trigger — matches streaming scan.
    prose = "Roll Stealth d20\nNarrator dopisał jeszcze jedno zdanie."
    assert _last_cue_line(prose) == ""
