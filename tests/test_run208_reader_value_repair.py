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
        pipeline.MAX_QUALITY_RETRIES = 1
        pipeline.should_attempt_dynamic_retry = lambda rows, evidence, origin="new": result
        pipeline.build_decision_prompt = lambda *args, **kwargs: "BASE PROMPT"
        pipeline.build_dynamic_retry_instruction = lambda rows: ("BASE RETRY", ["ARTICLE"])
        return pipeline

    @staticmethod
    def _fresh_safe_evidence():
        return {"state": "SUFFICIENT", "decision_scope_safe": True}

    @staticmethod
    def _reader_rows():
        return [
            {"message": "reader_value_review:multi_axis_reader_weakness", "severity": "REVIEW"},
            {"message": "reader_value_review:non_engineer_access_failure", "severity": "REVIEW"},
        ]

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

    def test_fresh_reader_only_accessibility_failure_gets_exactly_one_reader_repair(self):
        pipeline = self._pipeline()
        run208.install(pipeline)
        rows = self._reader_rows()
        with patch.dict(os.environ, {}, clear=True):
            first_article = pipeline.should_attempt_dynamic_retry(rows, self._fresh_safe_evidence(), "new")
            second_article = pipeline.should_attempt_dynamic_retry(rows, self._fresh_safe_evidence(), "new")
        self.assertEqual(first_article, (True, "run341_production_reader_repair"))
        self.assertEqual(second_article, (False, "run360_reader_repair_already_spent"))

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

    def test_one_base_retry_then_one_reader_only_repair(self):
        calls = {"n": 0}

        def base_retry(rows, evidence, origin="new"):
            calls["n"] += 1
            if any("FACT_" in str(row.get("message")) for row in rows):
                return True, "hard_retry"
            return False, "reader_value_review_no_retry"

        pipeline = self._pipeline()
        pipeline.should_attempt_dynamic_retry = base_retry
        run208.install(pipeline)
        pipeline.build_decision_prompt("n", "u", 1, "d", "", "GitHub", previous_article="")

        mixed = [
            {"message": "FACT_NUMERICAL_MISMATCH", "severity": "HARD"},
            {"message": "reader_value_review:multi_axis_reader_weakness", "severity": "REVIEW"},
        ]
        self.assertEqual(
            pipeline.should_attempt_dynamic_retry(mixed, self._fresh_safe_evidence(), "new"),
            (True, "hard_retry"),
        )
        self.assertEqual(
            pipeline.should_attempt_dynamic_retry(self._reader_rows(), self._fresh_safe_evidence(), "new"),
            (True, "run341_production_reader_repair"),
        )
        self.assertEqual(
            pipeline.should_attempt_dynamic_retry(self._reader_rows(), self._fresh_safe_evidence(), "new"),
            (False, "run360_reader_repair_already_spent"),
        )
        self.assertEqual(pipeline.MAX_QUALITY_RETRIES, 2)

    def test_second_fact_retry_is_blocked(self):
        pipeline = self._pipeline((True, "hard_retry"))
        run208.install(pipeline)
        rows = [{"message": "FACT_NUMERICAL_MISMATCH", "severity": "HARD"}]
        first = pipeline.should_attempt_dynamic_retry(rows, self._fresh_safe_evidence(), "new")
        second = pipeline.should_attempt_dynamic_retry(rows, self._fresh_safe_evidence(), "new")
        self.assertEqual(first, (True, "hard_retry"))
        self.assertEqual(second, (False, "run360_base_quality_retry_already_spent"))

    def test_fresh_prompt_resets_retry_owners_for_next_candidate(self):
        pipeline = self._pipeline((True, "hard_retry"))
        run208.install(pipeline)
        rows = [{"message": "FACT_NUMERICAL_MISMATCH", "severity": "HARD"}]
        pipeline.build_decision_prompt("a", "u", 1, "d", "", "GitHub", previous_article="")
        self.assertTrue(pipeline.should_attempt_dynamic_retry(rows, self._fresh_safe_evidence(), "new")[0])
        self.assertFalse(pipeline.should_attempt_dynamic_retry(rows, self._fresh_safe_evidence(), "new")[0])
        pipeline.build_decision_prompt("b", "u", 1, "d", "", "GitHub", previous_article="")
        self.assertTrue(pipeline.should_attempt_dynamic_retry(rows, self._fresh_safe_evidence(), "new")[0])

    def test_first_pass_prompt_adds_reader_path_without_permission_to_invent(self):
        pipeline = self._pipeline()
        run208.install(pipeline)
        prompt = pipeline.build_decision_prompt()
        self.assertIn("Reader Path Contract", prompt)
        self.assertIn("①何が変わった", prompt)
        self.assertIn("③現時点の暫定判断", prompt)
        self.assertIn("初稿の段階でReader Gateを後工程へ丸投げしない", prompt)
        self.assertIn("問いかけや比喩は、それだけではReader Bridgeとみなさない", prompt)
        self.assertIn("冒頭約600文字", prompt)
        self.assertIn("新事実は足さない", prompt)
        self.assertIn("架空の体験・感情・因果", prompt)
        self.assertIn("固定見出しや定型句は使わず", prompt)

    def test_first_pass_prompt_preserves_plain_language_limitations_and_small_reader_payload(self):
        pipeline = self._pipeline()
        run208.install(pipeline)
        prompt = pipeline.build_decision_prompt()
        self.assertIn("重要な制約・対象範囲・例外・未検証条件", prompt)
        self.assertIn("普通の日本語で1〜2文に圧縮", prompt)
        self.assertIn("制約を脚注扱いで最後へ追いやらない", prompt)
        self.assertIn("中心メッセージは原則3つまで", prompt)
        self.assertIn("Human Appealは問いかけや比喩の数ではなく", prompt)
        self.assertIn("親しみのための前置きは増やさない", prompt)

    def test_reader_only_retry_contract_preserves_fact_evidence_and_decision(self):
        pipeline = self._pipeline()
        run208.install(pipeline)
        instruction, sections = pipeline.build_dynamic_retry_instruction(self._reader_rows())
        self.assertEqual(sections, ["ARTICLE"])
        self.assertIn("BASE RETRY", instruction)
        self.assertIn("Factを固定", instruction)
        self.assertIn("Evidence URL", instruction)
        self.assertIn("Decision/Score/Action", instruction)
        self.assertIn("新しい数値", instruction)
        self.assertIn("冒頭3段落以内へ前倒し", instruction)
        self.assertIn("問いかけ・比喩がDecision到達を遅らせている場合", instruction)
        self.assertIn("Readyにしない", instruction)

    def test_mixed_fact_and_reader_retry_does_not_receive_reader_restructure_contract(self):
        pipeline = self._pipeline()
        run208.install(pipeline)
        rows = [
            {"message": "FACT_NUMERICAL_MISMATCH", "severity": "HARD"},
            {"message": "reader_value_review:non_engineer_access_failure", "severity": "REVIEW"},
        ]
        instruction, _ = pipeline.build_dynamic_retry_instruction(rows)
        self.assertEqual(instruction, "BASE RETRY")
        self.assertNotIn("Reader Repair", instruction)
        self.assertNotIn("RUN359 Reader Repair", instruction)

    def test_reader_retry_keeps_limitations_visible_while_simplifying(self):
        pipeline = self._pipeline()
        run208.install(pipeline)
        instruction, _ = pipeline.build_dynamic_retry_instruction(self._reader_rows())
        self.assertIn("重要な制約・対象範囲・例外・未検証条件", instruction)
        self.assertIn("平易化のために削除してはいけない", instruction)
        self.assertIn("Decisionの直後または同じ判断段落", instruction)
        self.assertIn("①何が変わった ②今どう判断する ③その判断を変えうる重要な制約", instruction)
        self.assertIn("導入を長くしない", instruction)

    def test_reader_contract_does_not_reintroduce_fixed_heading_template(self):
        pipeline = self._pipeline()
        run208.install(pipeline)
        prompt = pipeline.build_decision_prompt()
        for heading in ("## なぜ重要なのか", "## 何が変わるのか", "## 最終判断"):
            self.assertNotIn(heading, prompt)

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
        self.assertTrue(pipeline.RUN342_READER_DECISION_DISTANCE)
        self.assertTrue(pipeline.RUN344_READER_LIMITATION_BRIDGE)
        self.assertTrue(pipeline.RUN360_RETRY_OWNER_ORTHOGONALITY)


if __name__ == "__main__":
    unittest.main()
