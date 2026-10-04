import unittest

import run180_eyecatch_semantic_layout as semantic
import ops_ready_eyecatch_finalize as ops


SOURCE_TITLE = "Argo-Bench: Evaluating Data Agents on Enterprise-Scale Workflows"
COMPRESSED_TITLE = "Argo-Bench: Data Agents on Enterprise-Scale Workflows"
SUBHEADLINE = "企業規模のデータエージェント評価を、実務の目線で読み解く。"


class BoundedEnglishEyecatchCompressionTest(unittest.TestCase):
    def test_generic_gerund_may_be_dropped_while_all_core_source_tokens_remain(self):
        self.assertEqual(
            semantic._validate_eyecatch_title(SOURCE_TITLE, COMPRESSED_TITLE),
            COMPRESSED_TITLE,
        )

    def test_ops_plan_is_provider_free_and_passes_existing_layout_gate(self):
        plan = ops._bounded_deterministic_plan(SOURCE_TITLE, SUBHEADLINE)
        self.assertIsInstance(plan, dict)
        validated = semantic._validate_layout_plan(SOURCE_TITLE, SUBHEADLINE, plan)
        self.assertIsNotNone(validated)
        self.assertEqual(validated["eyecatch_title"], COMPRESSED_TITLE)
        self.assertEqual(
            semantic.r178._canonical_partition_text("".join(validated["subheadline_lines"])),
            semantic.r178._canonical_partition_text(SUBHEADLINE),
        )


if __name__ == "__main__":
    unittest.main()
