from __future__ import annotations

import types
import unittest

import reader_value_review_bridge as bridge


class Run405ReaderDensityCompressionTests(unittest.TestCase):
    def _pipeline(self):
        p = types.SimpleNamespace()
        p.REASON_CODE_PUB_SCORE_NARRATIVE_MISMATCH = "score_narrative_mismatch"
        p.REASON_CODE_APPEAL_DECISION_VOICE_LOSS = "decision_voice_missing"
        return p

    def test_density_failure_emits_operational_compression_contract(self):
        rows = [
            {
                "reason_code": "reader_value_review",
                "message": "reader_value_review:dense_report_cluster; reader_value_review:multi_axis_reader_weakness; reader_value_review:non_engineer_access_failure",
            }
        ]
        text = bridge._retry_yield_guardrails(self._pipeline(), rows)
        self.assertIn("Run405 Reader Density Compression", text)
        self.assertIn("1つだけ本文前半", text)
        self.assertIn("原則3点以内", text)
        self.assertIn("Run405 Decision Bridge", text)
        self.assertIn("Run405 Paragraph Budget", text)
        self.assertIn("新規専門概念を2個以上持ち込まない", text)

    def test_score_plus_density_keeps_score_fixed_and_orders_repairs(self):
        rows = [
            {
                "reason_code": "score_narrative_mismatch",
                "message": "score_narrative_mismatch",
            },
            {
                "reason_code": "reader_value_review",
                "message": "reader_value_review:dense_report_cluster",
            },
        ]
        text = bridge._retry_yield_guardrails(self._pipeline(), rows)
        self.assertIn("まずDecision", text)
        self.assertIn("その後で重複説明と情報密度を圧縮", text)
        self.assertIn("Decision Score、Evidence、事実、数値、重要制約は変更しない", text)

    def test_unrelated_reason_does_not_add_run405_guidance(self):
        rows = [{"reason_code": "other", "message": "other failure"}]
        self.assertEqual("", bridge._retry_yield_guardrails(self._pipeline(), rows))


if __name__ == "__main__":
    unittest.main()
