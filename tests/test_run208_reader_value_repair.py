import os
import types
import unittest
from unittest.mock import patch

import run208_reader_value_repair as run208


class Run208ReaderValueRepairTests(unittest.TestCase):
    def _pipeline(self, result=(False, "reader_value_review_no_retry")):
        pipeline = types.SimpleNamespace()
        pipeline.GATE_SEVERITY_HARD = "HARD"
        pipeline.EVIDENCE_SUFFICIENT = "SUFFICIENT"
        pipeline.should_attempt_dynamic_retry = lambda rows, evidence, origin="new": result
        pipeline.build_decision_prompt = lambda *args, **kwargs: "BASE PROMPT"
        pipeline.build_dynamic_retry_instruction = lambda rows: ("BASE RETRY", ["ARTICLE"])
        return pipeline

    @staticmethod
    def _fresh_safe_evidence():
        return {"state": "SUFFICIENT", "decision_scope_safe": True}

    def test_disabled_pending_repair_outside_fast_lane(self):
        pipeline = self._pipeline()
        run208.install(pipeline)
        rows = [{"message": "reader_value_review:dense_report_cluster", "severity": "REVIEW"}]
        with patch.dict(os.environ, {}, clear=True):
            allowed, reason = pipeline.should_attempt_dynamic_retry(rows, {"ok": True}, "pending_retry")
        self.assertFalse(allowed)
        self.assertEqual(reason, "reader_value_review_no_retry")

    def test_allows_one_repair_for_repairable_reader_only_pending_retry(self):
        pipeline = self._pipeline()
        run208.install(pipeline)
        rows = [
            {"message": "reader_value_review:dense_report_cluster", "severity": "REVIEW"},
            {"message": "reader_value_review:repetitive_insight", "severity": "REVIEW"},
        ]
        with patch.dict(os.environ, {run208.FAST_LANE_ENV: "1"}, clear=True):
            first = pipeline.should_attempt_dynamic_retry(rows, {"evidence": "present"}, "pending_retry")
            second = pipeline.should_attempt_dynamic_retry(rows, {"evidence": "present"}, "pending_retry")
        self.assertEqual(first, (True, "run208_reader_value_fast_lane_repair"))
        self.assertEqual(second, (False, "reader_value_review_no_retry"))

    def test_fresh_reader_only_accessibility_failure_uses_existing_article_retry(self):
        pipeline = self._pipeline()
        run208.install(pipeline)
        rows = [
            {"message": "reader_value_review:multi_axis_reader_weakness", "severity": "REVIEW"},
            {"message": "reader_value_review:non_engineer_access_failure", "severity": "REVIEW"},
        ]
        with patch.dict(os.environ, {}, clear=True):
            first_article = pipeline.should_attempt_dynamic_retry(rows, self._fresh_safe_evidence(), "new")
            second_article = pipeline.should_attempt_dynamic_retry(rows, self._fresh_safe_evidence(), "new")
        self.assertEqual(first_article, (True, "run341_production_reader_repair"))
        self.assertEqual(second_article, (True, "run341_production_reader_repair"))

    def test_fresh_reader_repair_requires_sufficient_decision_safe_evidence(self):
        rows = [{"message": "reader_value_review:non_engineer_access_failure", "severity": "REVIEW"}]
        for evidence in (
            None,
            {"state": "INSUFFICIENT", "decision_scope_safe": True},
            {"state": "SUFFICIENT", "decision_scope_safe": False},
        ):
            pipeline = self._pipeline()
            run208.install(pipeline)
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(
                    pipeline.should_attempt_dynamic_retry(rows, evidence, "new"),
                    (False, "reader_value_review_no_retry"),
                )

    def test_fresh_reader_lane_rejects_hard_or_non_reader_blocker(self):
        cases = [
            [{"message": "reader_value_review:multi_axis_reader_weakness", "severity": "HARD"}],
            [
                {"message": "reader_value_review:multi_axis_reader_weakness", "severity": "REVIEW"},
                {"message": "primary_evidence_insufficient", "severity": "HARD"},
            ],
        ]
        for rows in cases:
            pipeline = self._pipeline()
            run208.install(pipeline)
            self.assertFalse(
                pipeline.should_attempt_dynamic_retry(rows, self._fresh_safe_evidence(), "new")[0]
            )

    def test_pending_fast_lane_refuses_nonrepairable_reader_reason(self):
        pipeline = self._pipeline()
        run208.install(pipeline)
        rows = [{"message": "reader_value_review:reader_delight_overclaim", "severity": "REVIEW"}]
        with patch.dict(os.environ, {run208.FAST_LANE_ENV: "1"}, clear=True):
            allowed, _ = pipeline.should_attempt_dynamic_retry(rows, {"evidence": "present"}, "pending_retry")
        self.assertFalse(allowed)

    def test_preserves_original_true_decision_for_mixed_hard_retry(self):
        pipeline = self._pipeline((True, "hard_retry"))
        run208.install(pipeline)
        rows = [
            {"message": "FACT_NUMERICAL_MISMATCH", "severity": "HARD"},
            {"message": "reader_value_review:multi_axis_reader_weakness", "severity": "REVIEW"},
        ]
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                pipeline.should_attempt_dynamic_retry(rows, self._fresh_safe_evidence(), "new"),
                (True, "hard_retry"),
            )

    def test_first_pass_prompt_adds_reader_path_without_permission_to_invent(self):
        pipeline = self._pipeline()
        run208.install(pipeline)
        prompt = pipeline.build_decision_prompt()
        self.assertIn("Reader Path Contract", prompt)
        self.assertIn("何が変わった／なぜ自分に関係する／今どうする", prompt)
        self.assertIn("新事実は足さない", prompt)
        self.assertIn("架空の体験・感情", prompt)

    def test_reader_retry_contract_preserves_fact_evidence_and_decision(self):
        pipeline = self._pipeline()
        run208.install(pipeline)
        instruction, sections = pipeline.build_dynamic_retry_instruction([
            {"message": "FACT_NUMERICAL_MISMATCH", "severity": "HARD"},
            {"message": "reader_value_review:final_surface_title_unbalanced_kagi", "severity": "REVIEW"},
        ])
        self.assertEqual(sections, ["ARTICLE"])
        self.assertIn("BASE RETRY", instruction)
        self.assertIn("Factを固定", instruction)
        self.assertIn("Evidence URL", instruction)
        self.assertIn("Decision/Score/Action", instruction)
        self.assertIn("新しい数値", instruction)
        self.assertIn("Readyにしない", instruction)

    def test_non_reader_retry_does_not_receive_reader_contract(self):
        pipeline = self._pipeline()
        run208.install(pipeline)
        instruction, _ = pipeline.build_dynamic_retry_instruction(
            [{"message": "FACT_UNSUPPORTED_CLAIM", "severity": "HARD"}]
        )
        self.assertEqual(instruction, "BASE RETRY")

    def test_install_is_idempotent(self):
        pipeline = self._pipeline()
        run208.install(pipeline)
        retry = pipeline.should_attempt_dynamic_retry
        prompt = pipeline.build_decision_prompt
        run208.install(pipeline)
        self.assertIs(retry, pipeline.should_attempt_dynamic_retry)
        self.assertIs(prompt, pipeline.build_decision_prompt)


if __name__ == "__main__":
    unittest.main()
