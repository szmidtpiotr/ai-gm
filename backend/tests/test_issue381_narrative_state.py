"""TDD: Issue #381 (D6) — Narracja: tagi, parsery, Narrative State.

Per game_mechanics.md CZĘŚĆ Y. LLM emituje tagi:
- [NARRATIVE_EVENT: key=..., note=...]  → kluczowe zdarzenie (do skrótu)
- [NARRATIVE_SEED: key=..., hint=...]   → obietnica/hak do użycia w przyszłości
Backend parsuje, kumuluje w strukturze NarrativeState (events/seeds, dedup by key),
usuwa tagi z narracji gracza.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ─── Parsery tagów ───────────────────────────────────────────────────────────

class TestNarrativeTagParsing(unittest.TestCase):
    def test_parse_narrative_event(self):
        from app.services.narrative_state_service import parse_narrative_event_tags

        text = "Aldric kiwa głową. [NARRATIVE_EVENT: key=met_aldric, note=Gracz spotkał Aldrica, który zaoferował pomoc]"
        pairs = parse_narrative_event_tags(text)
        self.assertEqual(pairs, [("met_aldric", "Gracz spotkał Aldrica, który zaoferował pomoc")])

    def test_parse_narrative_seed(self):
        from app.services.narrative_state_service import parse_narrative_seed_tags

        text = "[NARRATIVE_SEED: key=innkeeper_daughter, hint=Marta wspomniała o zaginionej córce na północy]"
        pairs = parse_narrative_seed_tags(text)
        self.assertEqual(pairs, [("innkeeper_daughter", "Marta wspomniała o zaginionej córce na północy")])

    def test_strip_removes_both_tags(self):
        from app.services.narrative_state_service import strip_narrative_tags

        text = ("Narracja. [NARRATIVE_EVENT: key=a, note=zdarzenie] dalej "
                "[NARRATIVE_SEED: key=b, hint=hak] koniec.")
        out = strip_narrative_tags(text)
        self.assertNotIn("NARRATIVE_EVENT", out)
        self.assertNotIn("NARRATIVE_SEED", out)
        self.assertIn("Narracja.", out)
        self.assertIn("koniec.", out)


# ─── Akumulacja Narrative State ──────────────────────────────────────────────

class TestNarrativeStateAccumulation(unittest.TestCase):
    def test_empty_state_shape(self):
        from app.services.narrative_state_service import empty_narrative_state

        st = empty_narrative_state()
        self.assertEqual(st["events"], [])
        self.assertEqual(st["seeds"], [])
        self.assertIn("current_situation", st)

    def test_apply_events_and_seeds(self):
        from app.services.narrative_state_service import apply_narrative_tags, empty_narrative_state

        st = apply_narrative_tags(
            empty_narrative_state(),
            events=[("met_aldric", "Gracz spotkał Aldrica")],
            seeds=[("daughter", "Marta wspomniała o córce")],
            turn=5,
        )
        self.assertEqual(len(st["events"]), 1)
        self.assertEqual(st["events"][0]["key"], "met_aldric")
        self.assertEqual(st["events"][0]["turn"], 5)
        self.assertEqual(len(st["seeds"]), 1)
        self.assertEqual(st["seeds"][0]["key"], "daughter")
        self.assertEqual(st["seeds"][0]["status"], "active")
        self.assertEqual(st["seeds"][0]["planted_turn"], 5)

    def test_apply_dedups_by_key(self):
        from app.services.narrative_state_service import apply_narrative_tags, empty_narrative_state

        st = apply_narrative_tags(empty_narrative_state(), events=[("e1", "pierwsze")], turn=1)
        st = apply_narrative_tags(st, events=[("e1", "duplikat"), ("e2", "drugie")], turn=2)
        keys = [e["key"] for e in st["events"]]
        self.assertEqual(keys, ["e1", "e2"])  # e1 nie zduplikowany


# ─── Backward compatibility ──────────────────────────────────────────────────

class TestNoTagUnchanged(unittest.TestCase):
    def test_text_without_tags(self):
        from app.services.narrative_state_service import (
            parse_narrative_event_tags, parse_narrative_seed_tags, strip_narrative_tags,
        )
        text = "Zwykła narracja bez tagów."
        self.assertEqual(parse_narrative_event_tags(text), [])
        self.assertEqual(parse_narrative_seed_tags(text), [])
        self.assertEqual(strip_narrative_tags(text), text)


if __name__ == "__main__":
    unittest.main()
