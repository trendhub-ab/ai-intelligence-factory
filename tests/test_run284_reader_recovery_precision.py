from __future__ import annotations

from pathlib import Path
import re
import types
import unittest

import run284_reader_recovery_precision as run284

ROOT = Path(__file__).resolve().parents[1]


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


class Run284RetiredRecoveryIsolationTests(unittest.TestCase):
    def _pipeline(self, retry_decision=(False, "reader_value_review_no_retry")):
        def build_decision_prompt(*, quality_feedback="", previous_article=""):
            return quality_feedback

        return types.SimpleNamespace(
            _JAPANESE_SAFE_FIXES=((re.compile(r"をな(?=[一-龥ぁ-んァ-ヶA-Za-z])"), "を"),),
            should_attempt_dynamic_retry=lambda rows, evidence, origin="new": retry_decision,
            build_decision_prompt=build_decision_prompt,
        )

    def test_install_does_not_override_retry_authorization(self):
        pipeline = self._pipeline()
        original_retry_policy = pipeline.should_attempt_dynamic_retry
        run284.install(pipeline)
        self.assertIs(original_retry_policy, pipeline.should_attempt_dynamic_retry)
        for origin in ("new", "pending_retry", "deferred", "article_validation", "current_policy_ready_recovery"):
            with self.subTest(origin=origin):
                self.assertEqual(
                    pipeline.should_attempt_dynamic_retry([], None, origin),
                    (False, "reader_value_review_no_retry"),
                )

    def test_existing_true_retry_decision_is_unchanged(self):
        pipeline = self._pipeline((True, "existing_hard_retry"))
        original_retry_policy = pipeline.should_attempt_dynamic_retry
        run284.install(pipeline)
        self.assertIs(original_retry_policy, pipeline.should_attempt_dynamic_retry)
        self.assertEqual(
            pipeline.should_attempt_dynamic_retry([], None, "new"),
            (True, "existing_hard_retry"),
        )

    def test_install_is_idempotent(self):
        pipeline = self._pipeline()
        original_retry_policy = pipeline.should_attempt_dynamic_retry
        run284.install(pipeline)
        wrapped_prompt = pipeline.build_decision_prompt
        remaining_fixes = pipeline._JAPANESE_SAFE_FIXES
        run284.install(pipeline)
        self.assertIs(original_retry_policy, pipeline.should_attempt_dynamic_retry)
        self.assertIs(wrapped_prompt, pipeline.build_decision_prompt)
        self.assertEqual(remaining_fixes, pipeline._JAPANESE_SAFE_FIXES)


class Run352PreservationTests(unittest.TestCase):
    def test_fact_retry_receives_local_edit_preservation_contract(self):
        feedback = "FACT_UNSUPPORTED_CLAIMを修正してください。"
        result = run284.retry_feedback_with_preservation(feedback, "前回ARTICLE")
        self.assertIn(feedback, result)
        self.assertIn(run284.RETRY_PRESERVATION_CONTRACT, result)

    def test_reader_repair_bypasses_conflicting_paragraph_order_contract(self):
        feedback = "【Reader Repair｜Factを固定した読者導線修正】\n段落を再編してください。"
        self.assertEqual(
            feedback,
            run284.retry_feedback_with_preservation(feedback, "前回ARTICLE"),
        )

    def test_run359_reader_repair_marker_also_bypasses_contract(self):
        feedback = "【RUN359 Reader Repair Execution Contract】\n圧縮してください。"
        self.assertEqual(
            feedback,
            run284.retry_feedback_with_preservation(feedback, "前回ARTICLE"),
        )

    def test_preservation_contract_is_not_duplicated(self):
        feedback = "修正\n\n" + run284.RETRY_PRESERVATION_CONTRACT
        self.assertEqual(
            feedback,
            run284.retry_feedback_with_preservation(feedback, "前回ARTICLE"),
        )

    def test_stranded_adverb_particle_is_repaired_without_restoring_hype(self):
        before = {"note_draft": "Aだが圧倒的に速い。"}
        rescued = {"note_draft": "Aだがに速い。"}
        fixed, changes = run284.repair_deterministic_rescue_surface(before, rescued)
        self.assertEqual("Aだが速い。", fixed["note_draft"])
        self.assertTrue(any("remove_stranded_ni_after_圧倒的" in item for item in changes))
        self.assertNotIn("圧倒的", fixed["note_draft"])


class Run284RepositoryContractTests(unittest.TestCase):
    def test_production_install_and_publication_provenance_track_run284(self):
        production = (ROOT / "production_pipeline.py").read_text(encoding="utf-8")
        contract = (ROOT / "publication_contract.py").read_text(encoding="utf-8")
        ready = (ROOT / ".github/workflows/note-ready-sync.yml").read_text(encoding="utf-8")

        self.assertIn(
            "from run284_reader_recovery_precision import install as install_run284_reader_recovery_precision",
            production,
        )
        self.assertIn("install_run284_reader_recovery_precision(pipeline)", production)
        self.assertIn('"run284_reader_recovery_precision.py"', contract)
        self.assertIn("- 'run284_reader_recovery_precision.py'", ready)
        self.assertIn("python -m unittest tests.test_run284_reader_recovery_precision -v", ready)

    def test_retired_run282_route_is_absent_from_active_production_and_chatops(self):
        production = (ROOT / "production_pipeline.py").read_text(encoding="utf-8")
        chatops = (ROOT / ".github/workflows/chatops-one-shot.yml").read_text(encoding="utf-8")
        controller = (ROOT / "run202_chatops_control.py").read_text(encoding="utf-8")

        self.assertNotIn('mode == "current_policy_ready_recovery"', production)
        self.assertNotIn("run_current_policy_ready_recovery", production)
        self.assertNotIn("/aiif run current_policy_ready_recovery", chatops)
        self.assertNotIn("current-policy-ready-recovery.yml", chatops)
        self.assertNotIn('"/aiif run current_policy_ready_recovery"', controller)


if __name__ == "__main__":
    unittest.main()
