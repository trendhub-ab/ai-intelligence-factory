import os
import unittest
from pathlib import Path


class Run146RegressionModelLockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pipeline = Path('pipeline.py').read_text(encoding='utf-8')

    def test_regression_title_filter_env_exists(self):
        self.assertIn('REGEN_TEST_TITLE_CONTAINS', self.pipeline)

    def test_title_filter_is_regen_only_and_casefolded(self):
        self.assertIn('REGEN TEST TITLE FILTER', self.pipeline)
        self.assertIn('REGEN_TEST_TITLE_CONTAINS.casefold()', self.pipeline)

    def test_no_new_gemini_call_site(self):
        self.assertEqual(self.pipeline.count('_generate_via_chat('), 7)
        self.assertEqual(self.pipeline.count('genai.Client('), 1)


if __name__ == '__main__':
    unittest.main()
