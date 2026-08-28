import unittest
from pathlib import Path


class Run148ProductReviewOutputBudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path("pipeline.py").read_text(encoding="utf-8")

    def test_old_2200_output_cap_never_returns(self):
        anchor = '"response_json_schema": _PRODUCT_REVIEW_RESPONSE_SCHEMA'
        start = self.source.index(anchor)
        block = self.source[start:start + 1200]
        self.assertNotIn('"max_output_tokens": 2200', block)

    def test_product_review_keeps_explicit_thinking_and_output_profile(self):
        anchor = '"response_json_schema": _PRODUCT_REVIEW_RESPONSE_SCHEMA'
        start = self.source.index(anchor)
        block = self.source[start:start + 1200]
        self.assertIn('"thinking_config": {"thinking_level": thinking_level}', block)
        self.assertIn('"max_output_tokens": max_output_tokens', block)


if __name__ == "__main__":
    unittest.main()
