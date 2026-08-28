import unittest
from pathlib import Path


class Run148ProductReviewOutputBudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path('pipeline.py').read_text(encoding='utf-8')

    def test_product_review_uses_low_thinking(self):
        marker = '"thinking_config": {"thinking_level": "low"}'
        self.assertIn(marker, self.source)

    def test_product_review_output_budget_is_expanded(self):
        anchor = '"response_json_schema": _PRODUCT_REVIEW_RESPONSE_SCHEMA'
        start = self.source.index(anchor)
        block = self.source[start:start + 1000]
        self.assertIn('"max_output_tokens": 5000', block)
        self.assertNotIn('"max_output_tokens": 2200', block)

    def test_change_is_local_to_product_review_schema_block(self):
        self.assertEqual(self.source.count('"thinking_config": {"thinking_level": "low"}'), 1)
        self.assertEqual(self.source.count('"response_json_schema": _PRODUCT_REVIEW_RESPONSE_SCHEMA'), 1)


if __name__ == '__main__':
    unittest.main()
