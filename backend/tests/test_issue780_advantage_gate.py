"""TDD: Issue #780 — Atak z zaskoczenia + bramka intencji po zdobyciu przewagi.

Pokrywa testowalne kontrakty:
- D2: pierwszy cios w `zaskoczony` = auto-trafienie (first_hit_auto).
- D3: kość sneak skaluje się z poziomem (L1-4 1d6, L5-8 2d6, L9+ 3d6).
- burst: sneak die pali się przy otwarciu (cel `zaskoczony`), nie tylko gdy gracz `hidden`.
- D1 bramka: build_advantage_gate zwraca 3 opcje (atak/zastraszenie/wycofaj).
- komunikat korekty nie kłamie o „nieosiągalności" celu.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if "httpx" not in sys.modules:
    sys.modules["httpx"] = MagicMock()

from app.services import combat_service as cs


# ─── D2 — auto-trafienie zaskoczonego ────────────────────────────────────────

class TestAutoHitZaskoczony(unittest.TestCase):
    def test_zaskoczony_target_gives_first_hit_auto(self):
        """Pierwszy cios w `zaskoczony` = auto-hit (wróg nie zdążył zareagować)."""
        target = {"conditions": [{"key": "zaskoczony"}]}
        fx = cs._apply_attack_bonuses({}, target)
        self.assertTrue(fx.get("first_hit_auto"),
                        "zaskoczony powinien dać first_hit_auto=True")
        # nadal podwaja obrażenia pierwszego ciosu
        self.assertTrue(fx.get("first_hit_doubled"))
        self.assertIn("zaskoczony", fx.get("consumed_keys", []))

    def test_no_zaskoczony_no_auto_hit(self):
        """Backward compat: bez zaskoczony brak auto-hit i brak bonusów."""
        fx = cs._apply_attack_bonuses({}, {"conditions": []})
        self.assertFalse(fx.get("first_hit_auto"))
        self.assertFalse(fx.get("first_hit_doubled"))
        self.assertEqual(fx.get("atk_bonus"), 0)


# ─── D3 — skalowanie kości sneak wg poziomu ──────────────────────────────────

class TestSneakDiceScaling(unittest.TestCase):
    def test_dice_for_level(self):
        self.assertEqual(cs._rogue_sneak_dice_for_level(1), "1d6")
        self.assertEqual(cs._rogue_sneak_dice_for_level(4), "1d6")
        self.assertEqual(cs._rogue_sneak_dice_for_level(5), "2d6")
        self.assertEqual(cs._rogue_sneak_dice_for_level(8), "2d6")
        self.assertEqual(cs._rogue_sneak_dice_for_level(9), "3d6")
        self.assertEqual(cs._rogue_sneak_dice_for_level(15), "3d6")

    def test_rogue_level9_rolls_at_least_3(self):
        """Rogue L9 rzuca 3d6 → min 3."""
        bonus = cs._sneak_attack_bonus({"archetype": "rogue", "level": 9})
        self.assertGreaterEqual(bonus, 3)

    def test_non_rogue_zero(self):
        """Cecha klasy — tylko rogue. Inni → 0 bez rzutu (backward compat)."""
        self.assertEqual(cs._sneak_attack_bonus({"archetype": "warrior", "level": 9}), 0)
        self.assertEqual(cs._sneak_attack_bonus(None), 0)

    def test_rogue_level1_default(self):
        """Rogue L1 (lub brak level) → 1d6, min 1 (backward compat z 1d6)."""
        bonus = cs._sneak_attack_bonus({"archetype": "rogue"})
        self.assertGreaterEqual(bonus, 1)
        self.assertLessEqual(bonus, 6)


# ─── burst — sneak pali się przy otwarciu (zaskoczony), nie tylko hidden ──────

class TestBurstUnification(unittest.TestCase):
    def test_fires_when_player_hidden(self):
        """Klasyczne ukrycie nadal odpala burst."""
        self.assertTrue(cs._should_fire_burst({"conditions": []}, player_hidden=True))

    def test_fires_when_target_zaskoczony_even_without_hidden(self):
        """Otwarcie ze skradania: cel zaskoczony, gracz NIE hidden → burst pali się."""
        target = {"conditions": [{"key": "zaskoczony"}]}
        self.assertTrue(cs._should_fire_burst(target, player_hidden=False))

    def test_no_fire_when_neither(self):
        """Brak hidden i brak zaskoczonego celu → brak burst (backward compat)."""
        self.assertFalse(cs._should_fire_burst({"conditions": []}, player_hidden=False))


# ─── D1 — bramka intencji ────────────────────────────────────────────────────

class TestAdvantageGate(unittest.TestCase):
    def test_gate_has_three_options(self):
        gate = cs.build_advantage_gate("stealth")
        self.assertIsNotNone(gate)
        opts = {o["id"] for o in gate["options"]}
        self.assertEqual(opts, {"strike", "intimidate", "withdraw"})
        for o in gate["options"]:
            self.assertTrue(o.get("label"))
            self.assertTrue(o.get("action"))

    def test_intimidate_option_does_not_start_combat(self):
        """Opcja zastraszenia nie może nieść COMBAT_START (casus Mizela #99791)."""
        gate = cs.build_advantage_gate("stealth")
        intim = next(o for o in gate["options"] if o["id"] == "intimidate")
        self.assertNotIn("COMBAT_START", intim["action"].upper())

    def test_unknown_source_no_gate(self):
        self.assertIsNone(cs.build_advantage_gate(None))
        self.assertIsNone(cs.build_advantage_gate(""))


# ─── komunikat korekty nie kłamie ────────────────────────────────────────────

class TestCorrectionMessageHonest(unittest.TestCase):
    def test_not_present_message_not_lying_about_reachability(self):
        msg = cs.combat_correction_message("combat_target_not_present", "Strażnik")
        self.assertNotIn("nieosiągaln", msg.lower())

    def test_friendly_npc_message_preserved(self):
        msg = cs.combat_correction_message("combat_target_friendly_npc", "Marel")
        self.assertIn("Marel", msg)
        self.assertIn("nie wróg", msg.lower())


if __name__ == "__main__":
    unittest.main()
