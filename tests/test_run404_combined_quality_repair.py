from __future__ import annotations

import types
import unittest

import reader_value_review_bridge as bridge


class Run404CombinedQualityRepairTests(unittest.TestCase):
    def _pipeline(self):
        return types.SimpleNamespace(
            REASON_CODE_PUB_SCORE_NARRATIVE_MISMATCH="PUB_SCORE_NARRATIVE_MISMATCH",
            REASON_CODE_APPEAL_DECISION_VOICE_LOSS="APPEAL_DECISION_VOICE_LOSS",
        )

    def test_score_mismatch_repairs_all_reader_visible_surfaces(self):
        rows = [
            {
                "reason_code": "PUB_SCORE_NARRATIVE_MISMATCH",
                "message": "score_narrative_mismatch",
            }
        ]
        guidance = bridge._retry_yield_guardrails(self._pipeline(), rows)
        self.assertIn("タイトル・導入・本文・結論", guidance)
        self.assertIn("Decision Score、Evidence、事実、数値、重要制約", guidance)
        self.assertNotIn("ARTICLE終盤の判断を同じ行動距離", guidance)

    def test_combined_failure_orders_alignment_before_compression(self):
        rows = [
            {
                "reason_code": "PUB_SCORE_NARRATIVE_MISMATCH",
                "message": "score_narrative_mismatch",
            },
            {
                "reason_code": "",
                "message": "reader_value_review:dense_report_cluster",
            },
            {
                "reason_code": "",
                "message": "reader_value_review:multi_axis_reader_weakness",
            },
        ]
        guidance = bridge._retry_yield_guardrails(self._pipeline(), rows)
        order_pos = guidance.index("まずDecision / Decision Score")
        density_pos = guidance.index("Dense report修正")
        self.assertLess(order_pos, density_pos)
        self.assertIn("1回の修復で両方", guidance)
        self.assertIn("Decision Score、Evidence、事実、数値、重要制約は変更しない", guidance)

    def test_dense_reader_repair_does_not_authorize_new_facts(self):
        rows = [
            {
                "reason_code": "",
                "message": "reader_value_review:dense_report_cluster",
            }
        ]
        guidance = bridge._retry_yield_guardrails(self._pipeline(), rows)
        self.assertIn("Evidence・数値・制約を削らず", guidance)
        self.assertIn("新しい観点を足して長文化せず", guidance)


if __name__ == "__main__":
    unittest.main()
