import unittest

import run180_eyecatch_semantic_layout as semantic


SOURCE_TITLE = "Argo-Bench: Evaluating Data Agents on Enterprise-Scale Workflows"
COMPRESSED_TITLE = "Argo-Bench: Data Agents on Enterprise-Scale Workflows"


class BoundedEnglishEyecatchCompressionTest(unittest.TestCase):
    def test_generic_gerund_may_be_dropped_while_all_core_source_tokens_remain(self):
        self.assertEqual(
            semantic._validate_eyecatch_title(SOURCE_TITLE, COMPRESSED_TITLE),
            COMPRESSED_TITLE,
        )


if __name__ == "__main__":
    unittest.main()
