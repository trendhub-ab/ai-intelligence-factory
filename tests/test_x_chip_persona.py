import unittest

from x_intelligence import CHIP_PERSONA, build_x_post, validate_chip_text


class XChipPersonaTests(unittest.TestCase):
    def _item(self):
        return {
            "Name": "AIエージェントの新機能",
            "URL": "https://example.com/release",
            "Screening Score": 75,
            "Decision Score": 80,
            "Source Summary": "AIエージェントの使い方が広がる更新",
        }

    def test_chip_is_the_x_character(self):
        self.assertEqual(CHIP_PERSONA["name"], "チップ")
        self.assertEqual(CHIP_PERSONA["romanized_name"], "Chip")
        self.assertFalse(CHIP_PERSONA["voice"]["dog_endings_enabled"])

    def test_chip_draft_has_no_dog_ending_by_default(self):
        draft = build_x_post(self._item())
        self.assertEqual(draft["character"], "チップ")
        self.assertFalse(draft["dog_endings_enabled"])
        self.assertEqual(draft["dog_flavor_mode"], "metaphor_only_low_frequency")
        self.assertNotIn("ワン", draft["post"])
        self.assertNotIn("でしゅ", draft["post"])

    def test_persona_validator_fails_closed_on_childish_dog_ending(self):
        with self.assertRaisesRegex(ValueError, "forbids dog-like ending"):
            validate_chip_text("これは追っておくワン")

    def test_dog_flavor_is_defined_as_metaphor_not_sentence_ending(self):
        self.assertIn("ちょっと耳が立ちました", CHIP_PERSONA["allowed_dog_metaphors"])
        self.assertIn("犬らしさは語尾ではなく、低頻度の行動・比喩で出す", CHIP_PERSONA["rules"])


if __name__ == "__main__":
    unittest.main()
