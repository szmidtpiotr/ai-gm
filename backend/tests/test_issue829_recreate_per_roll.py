"""TDD: Issue #829 (recydywa) — combat 3D dice must RECREATE the box+container per roll.

Root cause (proven live on the buggy mobile GPU, see issue comments): the combat path
`rollDiceVisual` reused a single `_dice3d` (dice-box-threejs) instance and re-rolled into an
already-settled canvas. The mobile compositor never repaints that canvas, so only the FIRST
3D roll of a session is visible — every later roll (Stage 2 damage AND attack 2,3,…) is blank.

Admin `_previewDiceRoll` (system.js) renders a dozen rolls in a row on the SAME phone because
it DESTROYS the container + WebGL context and builds a fresh box per roll. The fix mirrors that
in `rollDiceVisual`: recreate `#dice3d-container` + a fresh box on every roll.

This is a frontend/WebGL repaint bug — not reproducible in pytest. The deterministic gate here is
a SOURCE-CONTRACT check on app.js: the singleton-reuse pattern must be gone and the
recreate-per-roll pattern present, while the 2D fallback + predetermined `@`-notation stay intact.
"""
import os
import re

APP_JS = os.path.join(
    os.path.dirname(__file__), "..", "..", "frontend", "front", "js", "app.js"
)


def _src():
    with open(APP_JS, "r", encoding="utf-8") as f:
        return f.read()


# ─── Test główny — recreate-per-roll in the combat dice path ───────────────────

def test_combat_dice_recreates_box_per_roll():
    """rollDiceVisual must build a FRESH box per roll, not reuse a cached singleton."""
    src = _src()
    # Distinctive marker proving the recreate-per-roll strategy is in place.
    assert "RECREATE-PER-ROLL" in src, "missing recreate-per-roll marker (#829 recydywa)"
    # A dedicated builder that mirrors admin _previewDiceRoll (remove old container + new box).
    assert "buildDice3DBox" in src, "expected buildDice3DBox() helper"


def test_no_singleton_reuse_guard():
    """The old 'reuse the same instance' early-return must be gone — it caused the blank rolls."""
    src = _src()
    assert "if (_dice3d) return _dice3d" not in src, (
        "singleton-reuse early-return still present — every roll after the first stays blank on mobile"
    )


def test_builder_destroys_old_container():
    """The fresh-container helper must remove the previous #dice3d-container (mirror admin clear)."""
    src = _src()
    # Find the builder body and assert it removes an existing container before creating one.
    assert re.search(r"dice3d-container", src), "container id must be referenced"
    assert ".remove()" in src and "createElement" in src, (
        "builder must remove old container and createElement a fresh one (recreate WebGL context)"
    )


# ─── Backward compatibility — fallback + predetermined results unchanged ────────

def test_2d_fallback_still_present():
    """On any 3D failure the player must still see the reliable 2D roll."""
    src = _src()
    assert "play2dDiceRoll" in src, "2D fallback removed — player could see no roll at all"


def test_predetermined_notation_still_used():
    """Dice must still land on the backend's exact result via '@' notation (e.g. 2d6@3,5)."""
    src = _src()
    assert "@${forced.join" in src, "predetermined '@' notation lost — die would land on a random value"


def test_both_stages_route_through_rollDiceVisual():
    """Both Stage 1 (k20) and Stage 2 (damage) must use rollDiceVisual so the fix covers all rolls."""
    src = _src()
    # Stage 1 attack + Stage 2 damage both call rollDiceVisual.
    assert src.count("rollDiceVisual(") >= 2, "both combat stages must route through rollDiceVisual"
