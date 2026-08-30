import inspect
import unittest

import pipeline
import reader_value_review_bridge as bridge


class Run171ProductionYieldGuardrailsTests(unittest.TestCase):
    def test_contract_covers_run105_failure_classes(self):
        contract = bridge.PRODUCTION_YIELD_CONTRACT
        self.assertIn("Decision / Decision Reason / Decision Score / Action", contract)
        self.assertIn("数年", contract)
        self.assertIn("2分", contract)
        self.assertIn("One Insight, One Home", contract)
        self.assertIn("Decision Voice", contract)
        self.assertIn("注視したい", contract)

    def test_retry_guardrail_repairs_score_voice_and_repetition_locally(self):
        rows = [
            {
                "reason_code": pipeline.REASON_CODE_PUB_SCORE_NARRATIVE_MISMATCH,
                "severity": pipeline.GATE_SEVERITY_HARD,
                "message": "score_narrative_mismatch",
            },
            {
                "reason_code": pipeline.REASON_CODE_APPEAL_DECISION_VOICE_LOSS,
                "severity": pipeline.GATE_SEVERITY_REVIEW,
                "message": "decision_voice_missing",
            },
            {
                "reason_code": "READER_VALUE_REVIEW",
                "severity": pipeline.GATE_SEVERITY_REVIEW,
                "message": bridge.READER_VALUE_MARKER + "repetitive_insight",
            },
        ]
        guidance = bridge._retry_yield_guardrails(pipeline, rows)
        self.assertIn("Decision整合修正", guidance)
        self.assertIn("編集者自身の判断を1文だけ復元", guidance)
        self.assertIn("重複文を削除または1箇所へ統合", guidance)
        self.assertIn("新しい説明や比喩を足さず", guidance)

    def test_reader_only_review_policy_still_avoids_retry_spend(self):
        original_human = pipeline.validate_human_appeal_gate
        original_retry = pipeline.should_attempt_dynamic_retry
        original_prompt = pipeline.build_decision_prompt
        original_instruction = pipeline.build_dynamic_retry_instruction
        had_attr = hasattr(pipeline, bridge._INSTALLED_ATTR)
        old_attr = getattr(pipeline, bridge._INSTALLED_ATTR, None)
        try:
            if had_attr:
                delattr(pipeline, bridge._INSTALLED_ATTR)
            bridge.install(pipeline)
            rows = pipeline.map_gate_reasons(
                "human_appeal",
                [bridge.READER_VALUE_MARKER + "dense_report_cluster"],
            )
            retry, reason = pipeline.should_attempt_dynamic_retry(
                rows, {"sufficiency": "SUFFICIENT"}, "new"
            )
            self.assertFalse(retry)
            self.assertEqual("reader_value_review_no_retry", reason)
        finally:
            pipeline.validate_human_appeal_gate = original_human
            pipeline.should_attempt_dynamic_retry = original_retry
            pipeline.build_decision_prompt = original_prompt
            pipeline.build_dynamic_retry_instruction = original_instruction
            if had_attr:
                setattr(pipeline, bridge._INSTALLED_ATTR, old_attr)
            elif hasattr(pipeline, bridge._INSTALLED_ATTR):
                delattr(pipeline, bridge._INSTALLED_ATTR)

    def test_bridge_still_has_no_new_model_call_site(self):
        src = inspect.getsource(bridge)
        self.assertNotIn("_generate_via_chat(", src)
        self.assertNotIn("genai.Client(", src)


if __name__ == "__main__":
    unittest.main()
