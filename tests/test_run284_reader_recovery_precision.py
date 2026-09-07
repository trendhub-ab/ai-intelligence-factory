from __future__ import annotations

import re
import types
import unittest

import run284_reader_recovery_precision as run284


class Run284JapanesePolishTests(unittest.TestCase):
    def _pipeline(self):
        return types.SimpleNamespace(
            _JAPANESE_SAFE_FIXES=(
                (re.compile(r"をな(?=[一-龥ぁ-んァ-ヶA-Za-z])"), "を"),
                (re.compile(r"がを(?=[一-龥ぁ-んァ-ヶA-Za-z])"), "を"),
                (re.compile(r"というという"), "という"),
            ),
            should_attempt_dynamic_retry=lambda rows, evidence, origin="new": (
                False,
                "reader_value_review_no_retry",
            ),
            EVIDENCE_SUFFICIENT="SUFFICIENT",
            GATE_SEVERITY_HARD="HARD",
        )

    def _apply(self, pipeline, value: str) -> str:
        text = value
        for pattern, replacement in pipeline._JAPANESE_SAFE_FIXES:
            text = pattern.sub(replacement, text)
        return text

    def test_production_title_regression_迷子をなくす_is_never_corrupted(self):
        pipeline = self._pipeline()
        before = "AI開発の迷子をなくす『実験カルテ』の作り方とは？"
        self.assertEqual("AI開発の迷子をくす『実験カルテ』の作り方とは？", self._apply(pipeline, before))
        removed = run284.disable_overbroad_japanese_polish(pipeline)
        self.assertEqual(1, removed)
        self.assertEqual(before, self._apply(pipeline, before))

    def test_other_historical_safe_fixes_remain_active(self):
        pipeline = self._pipeline()
        run284.disable_overbroad_japanese_polish(pipeline)
        self.assertEqual("これを改善", self._apply(pipeline, "これがを改善"))
        self.assertEqual("という説明", self._apply(pipeline, "というという説明"))

    def test_valid_をな_verbs_are_preserved(self):
        pipeline = self._pipeline()
        run284.disable_overbroad_japanese_polish(pipeline)
        for value in ("線をなぞる", "問題をなくす", "役割をなす", "表面をなめる"):
            with self.subTest(value=value):
                self.assertEqual(value, self._apply(pipeline, value))


class Run284ReaderRepairTests(unittest.TestCase):
    def _pipeline(self, original=(False, "reader_value_review_no_retry")):
        return types.SimpleNamespace(
            _JAPANESE_SAFE_FIXES=((re.compile(r"をな(?=[一-龥ぁ-んァ-ヶA-Za-z])"), "を"),),
            should_attempt_dynamic_retry=lambda rows, evidence, origin="new": original,
            EVIDENCE_SUFFICIENT="SUFFICIENT",
            GATE_SEVERITY_HARD="HARD",
        )

    def _wandb_rows(self):
        return [
            {
                "message": "reader_value_review:dense_report_cluster (Reader Enjoyment/Narrative Pull/Information Budget/Reader Temperature Rhythm)",
                "severity": "REVIEW",
            },
            {
                "message": "reader_value_review:multi_axis_reader_weakness (accessibility/reader_enjoyment/narrative_pull/jargon_translation/non_engineer_core_clarity/information_budget/reader_temperature_rhythm)",
                "severity": "REVIEW",
            },
            {
                "message": "reader_value_review:non_engineer_access_failure (Accessibility/Jargon Translation/Non-Engineer Core Clarity)",
                "severity": "REVIEW",
            },
            {
                "message": "reader_value_review:final_surface_multi_axis_reader_weakness (accessibility/reader_enjoyment/narrative_pull/jargon_translation/non_engineer_core_clarity/information_budget/reader_temperature_rhythm)",
                "severity": "REVIEW",
            },
            {
                "message": "reader_value_review:final_surface_non_engineer_access_failure (Accessibility/Jargon Translation/Non-Engineer Core Clarity)",
                "severity": "REVIEW",
            },
        ]

    def test_wandb_reader_only_failure_gets_exactly_one_repair(self):
        pipeline = self._pipeline()
        run284.install(pipeline)
        evidence = {"state": "SUFFICIENT", "decision_scope_safe": True}
        first = pipeline.should_attempt_dynamic_retry(
            self._wandb_rows(), evidence, "current_policy_ready_recovery"
        )
        second = pipeline.should_attempt_dynamic_retry(
            self._wandb_rows(), evidence, "current_policy_ready_recovery"
        )
        self.assertEqual(first, (True, "run284_current_policy_reader_repair"))
        self.assertEqual(second, (False, "reader_value_review_no_retry"))

    def test_normal_new_and_pending_retry_policy_are_unchanged(self):
        rows = self._wandb_rows()
        evidence = {"state": "SUFFICIENT", "decision_scope_safe": True}
        for origin in ("new", "pending_retry", "deferred", "article_validation"):
            with self.subTest(origin=origin):
                pipeline = self._pipeline()
                run284.install(pipeline)
                self.assertEqual(
                    pipeline.should_attempt_dynamic_retry(rows, evidence, origin),
                    (False, "reader_value_review_no_retry"),
                )

    def test_insufficient_or_unsafe_evidence_never_spends_repair(self):
        rows = self._wandb_rows()
        for evidence in (
            None,
            {},
            {"state": "SUPPLEMENT_REQUIRED", "decision_scope_safe": True},
            {"state": "SUFFICIENT", "decision_scope_safe": False},
        ):
            with self.subTest(evidence=evidence):
                pipeline = self._pipeline()
                run284.install(pipeline)
                self.assertFalse(
                    pipeline.should_attempt_dynamic_retry(
                        rows, evidence, "current_policy_ready_recovery"
                    )[0]
                )

    def test_non_reader_hard_or_unapproved_reader_reason_is_refused(self):
        evidence = {"state": "SUFFICIENT", "decision_scope_safe": True}
        cases = (
            self._wandb_rows() + [{"message": "FACT_UNSUPPORTED_CLAIM", "severity": "HARD"}],
            [{"message": "reader_value_review:reader_delight_overclaim", "severity": "REVIEW"}],
            [{"message": "reader_value_review:warm_hook_cold_body", "severity": "REVIEW"}],
        )
        for rows in cases:
            with self.subTest(rows=rows):
                pipeline = self._pipeline()
                run284.install(pipeline)
                self.assertFalse(
                    pipeline.should_attempt_dynamic_retry(
                        rows, evidence, "current_policy_ready_recovery"
                    )[0]
                )

    def test_original_true_retry_decision_is_never_overridden(self):
        pipeline = self._pipeline((True, "existing_hard_retry"))
        run284.install(pipeline)
        self.assertEqual(
            pipeline.should_attempt_dynamic_retry([], None, "current_policy_ready_recovery"),
            (True, "existing_hard_retry"),
        )

    def test_install_is_idempotent(self):
        pipeline = self._pipeline()
        run284.install(pipeline)
        wrapped = pipeline.should_attempt_dynamic_retry
        remaining_fixes = pipeline._JAPANESE_SAFE_FIXES
        run284.install(pipeline)
        self.assertIs(wrapped, pipeline.should_attempt_dynamic_retry)
        self.assertEqual(remaining_fixes, pipeline._JAPANESE_SAFE_FIXES)


if __name__ == "__main__":
    unittest.main()
