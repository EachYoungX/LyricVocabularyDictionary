import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "processing" / "scripts"))

from build_sqlite import (  # noqa: E402
    PatternCompiler,
    PatternValidator,
    SUPPORTED_SLOT_HINTS,
)


class PatternCompilerTests(unittest.TestCase):
    def compile(self, phrase):
        return PatternCompiler().compile(phrase)[1]

    def slots(self, tokens):
        return [token for token in tokens if token["token_type"] == "SLOT"]

    def test_supported_slot_enum(self):
        self.assertEqual(
            SUPPORTED_SLOT_HINTS,
            {"POSSESSIVE", "REFLEXIVE", "PRONOUN", "GERUND", "PERSON", "THING", "OBJECT", "GENERIC"},
        )

    def test_possessive(self):
        tokens = self.compile("on one's side")
        slot = self.slots(tokens)[0]
        self.assertEqual(slot["slot_hint"], "POSSESSIVE")
        self.assertEqual((slot["min_tokens"], slot["max_tokens"]), (1, 3))

    def test_reflexive_is_exactly_one_token(self):
        slot = self.slots(self.compile("pride oneself on"))[0]
        self.assertEqual(slot["slot_hint"], "REFLEXIVE")
        self.assertEqual((slot["min_tokens"], slot["max_tokens"]), (1, 1))

    def test_person_and_thing(self):
        slots = self.slots(self.compile("remind sb. of sth."))
        self.assertEqual([slot["slot_hint"] for slot in slots], ["PERSON", "THING"])
        self.assertEqual((slots[0]["min_tokens"], slots[0]["max_tokens"]), (1, 4))
        self.assertEqual((slots[1]["min_tokens"], slots[1]["max_tokens"]), (1, 5))

    def test_gerund_and_optional_thing(self):
        slots = self.slots(self.compile("prevent sb. from doing sth."))
        self.assertEqual([slot["slot_hint"] for slot in slots], ["PERSON", "GERUND", "THING"])
        self.assertEqual((slots[1]["min_tokens"], slots[1]["max_tokens"]), (1, 3))
        self.assertEqual((slots[2]["min_tokens"], slots[2]["max_tokens"]), (0, 5))

    def test_gap_is_not_slot(self):
        tokens = self.compile("as…as")
        gaps = [token for token in tokens if token["token_type"] == "GAP"]
        self.assertEqual(len(gaps), 1)
        self.assertIsNone(gaps[0]["slot_hint"])
        self.assertEqual((gaps[0]["min_tokens"], gaps[0]["max_tokens"]), (1, 3))
        self.assertFalse(self.slots(tokens))

    def test_add_ellipsis_has_object_slots(self):
        tokens = self.compile("add…to…")
        self.assertEqual([token["slot_hint"] for token in self.slots(tokens)], ["OBJECT", "GENERIC"])

    def test_lemma_literal_is_preserved(self):
        tokens = self.compile("be all eyes")
        self.assertEqual(tokens[0]["match_type"], "LEMMA")
        self.assertEqual(tokens[2]["match_type"], "NORMALIZED")

    def test_doing_can_be_literal(self):
        tokens = self.compile("up and doing")
        self.assertEqual(tokens[-1]["token_type"], "LITERAL")
        self.assertEqual(tokens[-1]["match_value"], "doing")

    def test_validator_rejects_invalid_tokens(self):
        validator = PatternValidator()
        with self.assertRaises(ValueError):
            validator.validate([{"token_type": "SLOT", "slot_hint": None, "min_tokens": 1, "max_tokens": 1}])
        with self.assertRaises(ValueError):
            validator.validate([
                {"token_type": "LITERAL", "match_value": "on", "slot_hint": "PERSON", "min_tokens": 1, "max_tokens": 1},
            ])
        with self.assertRaises(ValueError):
            validator.validate([
                {"token_type": "LITERAL", "match_value": "", "slot_hint": None, "min_tokens": 1, "max_tokens": 1},
            ])

    def test_phrase_validator_requires_traceability_and_anchor(self):
        validator = PatternValidator()
        compiled = self.compile("on one's side")
        with self.assertRaises(ValueError):
            validator.validate_phrase("", "2ndla:1", "on <POSSESSIVE> side", compiled, [("NORMALIZED", "on")])
        with self.assertRaises(ValueError):
            validator.validate_phrase("on one's side", "2ndla:1", "on <POSSESSIVE> side", compiled, [])
        with self.assertRaises(ValueError):
            validator.validate_phrase("on one's side", "", "on <POSSESSIVE> side", compiled, [("NORMALIZED", "on")])


if __name__ == "__main__":
    unittest.main()
