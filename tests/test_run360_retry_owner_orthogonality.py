from __future__ import annotations

import types
import unittest

import run284_reader_recovery_precision as run284


class Run360RetryOwnerOrthogonalityTests(unittest.TestCase):
    def test_fact_retry_keeps_run352_local_preservation(self):
        feedback = "FACT_NUMERICAL_MISMATCH: fix the number"
        previous = "before article"
        out = run284.retry_feedback_with_preservation(feedback, previous)
        self.assertIn(run284.RETRY_PRESERVATION_CONTRACT, out)

    def test_reader_only_retry_does_not_receive_paragraph_order_lock(self):
        feedback = (
            "BASE RETRY\n\n"
            "【Reader Repair｜Factを固定した読者導線修正】\n"
            "Fact/Evidenceを固定して段落を再配置する。\n\n"
            "【RUN359 Reader Repair Execution Contract】\n"
            "不要な専門名を削る。"
        )
        out = run284.retry_feedback_with_preservation(feedback, "before article")
        self.assertEqual(out, feedback)
        self.assertNotIn("指摘対象でない見出し、段落順", out)

    def test_prompt_wrapper_preserves_reader_repair_without_run352_conflict(self):
        def base_prompt(*, quality_feedback="", previous_article=""):
            return quality_feedback

        wrapped = run284._wrap_build_decision_prompt(base_prompt)
        feedback = "【Reader Repair｜Factを固定した読者導線修正】\n段落を再配置する。"
        out = wrapped(quality_feedback=feedback, previous_article="old")
        self.assertEqual(out, feedback)
        self.assertNotIn(run284.RETRY_PRESERVATION_CONTRACT, out)


if __name__ == "__main__":
    unittest.main()
