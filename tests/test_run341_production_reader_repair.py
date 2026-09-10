from __future__ import annotations

import types
import unittest

import run341_production_reader_repair as run341


class Run341ProductionReaderRepairTests(unittest.TestCase):
    def _pipeline(self, *, original_retry=(False, "reader_value_review_no_retry")):
        module = types.SimpleNamespace()
        module.GATE_SEVERITY_HARD = "HARD"
        module.EVIDENCE_SUFFICIENT = "SUFFICIENT"
        module.should_attempt_dynamic_retry = lambda rows, evidence, origin="new": original_retry
        module.build_decision_prompt = lambda *args, **kwargs: "BASE PROMPT"
        module.build_dynamic_retry_instruction = lambda rows: ("BASE RETRY", ["ARTICLE"])
        return module

    @staticmethod
    def _safe_evidence():
        return {"state": "SUFFICIENT", "decision_scope_safe": True}

    @staticmethod
    def _reader_rows(label="multi_axis_reader_weakness"):
        return [{
            "severity": "REVIEW",
            "message": f"reader_value_review:{label}",
        }]

    def test_new_reader_only_failure_gets_exactly_one_existing_retry(self):
        pipeline = self._pipeline()
        run341.install(pipeline)
        first = pipeline.should_attempt_dynamic_retry(
            self._reader_rows("non_engineer_access_failure"), self._safe_evidence(), "new"
        )
        second = pipeline.should_attempt_dynamic_retry(
            self._reader_rows("non_engineer_access_failure"), self._safe_evidence(), "new"
        )
        self.assertEqual(first, (True, "run341_production_reader_repair"))
        self.assertEqual(second, (False, "reader_value_review_no_retry"))

    def test_reader_repair_requires_sufficient_decision_safe_evidence(self):
        for evidence in (
            None,
            {"state": "INSUFFICIENT", "decision_scope_safe": True},
            {"state": "SUFFICIENT", "decision_scope_safe": False},
        ):
            pipeline = self._pipeline()
            run341.install(pipeline)
            self.assertEqual(
                pipeline.should_attempt_dynamic_retry(self._reader_rows(), evidence, "new"),
                (False, "reader_value_review_no_retry"),
            )

    def test_non_reader_or_hard_reason_never_enters_reader_only_lane(self):
        cases = [
            [{"severity": "HARD", "message": "FACT_UNSUPPORTED_CLAIM"}],
            [{"severity": "HARD", "message": "reader_value_review:multi_axis_reader_weakness"}],
            self._reader_rows() + [{"severity": "REVIEW", "message": "other_review"}],
        ]
        for rows in cases:
            pipeline = self._pipeline()
            run341.install(pipeline)
            self.assertEqual(
                pipeline.should_attempt_dynamic_retry(rows, self._safe_evidence(), "new"),
                (False, "reader_value_review_no_retry"),
            )

    def test_existing_hard_retry_decision_remains_authoritative(self):
        pipeline = self._pipeline(original_retry=(True, "hard_local_repair"))
        run341.install(pipeline)
        rows = [
            {"severity": "HARD", "message": "FACT_NUMERICAL_MISMATCH"},
            {"severity": "REVIEW", "message": "reader_value_review:multi_axis_reader_weakness"},
        ]
        self.assertEqual(
            pipeline.should_attempt_dynamic_retry(rows, self._safe_evidence(), "new"),
            (True, "hard_local_repair"),
        )

    def test_pending_and_recovery_origins_keep_their_existing_policies(self):
        for origin in ("pending_retry", "current_policy_ready_recovery"):
            pipeline = self._pipeline()
            run341.install(pipeline)
            self.assertEqual(
                pipeline.should_attempt_dynamic_retry(
                    self._reader_rows(), self._safe_evidence(), origin
                ),
                (False, "reader_value_review_no_retry"),
            )

    def test_first_pass_prompt_has_reader_path_without_new_fact_permission(self):
        pipeline = self._pipeline()
        run341.install(pipeline)
        prompt = pipeline.build_decision_prompt()
        self.assertIn("Reader Path Contract", prompt)
        self.assertIn("何が変わった／なぜ自分に関係する／今どうする", prompt)
        self.assertIn("新事実は足さない", prompt)
        self.assertIn("架空の体験・感情", prompt)

    def test_reader_retry_contract_preserves_fact_evidence_and_decision(self):
        pipeline = self._pipeline()
        run341.install(pipeline)
        instruction, sections = pipeline.build_dynamic_retry_instruction(
            self._reader_rows("final_surface_title_unbalanced_kagi")
        )
        self.assertEqual(sections, ["ARTICLE"])
        self.assertIn("Run341 Reader Repair", instruction)
        self.assertIn("Evidence URL", instruction)
        self.assertIn("Decision/Score/Action", instruction)
        self.assertIn("新しい数値", instruction)
        self.assertIn("Readyにしない", instruction)

    def test_non_reader_retry_does_not_receive_reader_repair_contract(self):
        pipeline = self._pipeline()
        run341.install(pipeline)
        instruction, _ = pipeline.build_dynamic_retry_instruction(
            [{"severity": "HARD", "message": "FACT_UNSUPPORTED_CLAIM"}]
        )
        self.assertEqual(instruction, "BASE RETRY")

    def test_install_is_idempotent(self):
        pipeline = self._pipeline()
        run341.install(pipeline)
        retry = pipeline.should_attempt_dynamic_retry
        prompt = pipeline.build_decision_prompt
        run341.install(pipeline)
        self.assertIs(retry, pipeline.should_attempt_dynamic_retry)
        self.assertIs(prompt, pipeline.build_decision_prompt)


if __name__ == "__main__":
    unittest.main()
