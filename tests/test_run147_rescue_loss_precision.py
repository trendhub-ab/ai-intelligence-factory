import unittest
from pathlib import Path

import pipeline


class Run147RescueLossPrecisionTests(unittest.TestCase):
    def _loss(self, removed_sentences, important_numeric_removed):
        # Mirrors the production _rescue_loss payload rule. Keeping the assertion
        # against source text below ensures this test cannot silently diverge.
        return bool(
            removed_sentences >= 3
            or (important_numeric_removed and removed_sentences != 1)
        )

    def test_single_unsupported_numeric_sentence_can_be_safely_rescued(self):
        self.assertFalse(self._loss(1, True))

    def test_multiple_sentence_rescue_with_numeric_loss_stays_blocked(self):
        self.assertTrue(self._loss(2, True))

    def test_three_sentence_rescue_stays_blocked_without_numeric_loss(self):
        self.assertTrue(self._loss(3, False))

    def test_two_non_numeric_sentences_keep_existing_behavior(self):
        self.assertFalse(self._loss(2, False))

    def test_production_rule_is_exactly_narrowed(self):
        source = Path('pipeline.py').read_text(encoding='utf-8')
        expected = '"loss_exceeded": bool(removed_sentences >= 3 or (important_numeric_removed and removed_sentences != 1)),'
        self.assertIn(expected, source)
        self.assertNotIn('"loss_exceeded": bool(important_numeric_removed or removed_sentences >= 3),', source)

    def test_no_new_gemini_call_site(self):
        source = Path('pipeline.py').read_text(encoding='utf-8')
        self.assertEqual(source.count('_generate_via_chat('), 7)
        self.assertEqual(source.count('genai.Client('), 1)


if __name__ == '__main__':
    unittest.main()
