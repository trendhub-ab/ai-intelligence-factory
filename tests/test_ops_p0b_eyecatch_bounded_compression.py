import unittest

import run180_eyecatch_semantic_layout as semantic
import ops_ready_eyecatch_finalize as ops


SOURCE_TITLE = "Argo-Bench: Evaluating Data Agents on Enterprise-Scale Workflows：いま何を判断材料にするべきか。"
COMPRESSED_TITLE = "Argo-Bench: Data Agents on Enterprise-Scale Workflows"
SUBHEADLINE = "企業規模のデータエージェント評価を、実務の目線で読み解く。"


class BoundedEnglishEyecatchCompressionTest(unittest.TestCase):
    def test_ops_builds_provider_free_plan_for_actual_runtime_note_title(self):
        plan = ops._bounded_request_layout_plan(None, SOURCE_TITLE, SUBHEADLINE)
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
