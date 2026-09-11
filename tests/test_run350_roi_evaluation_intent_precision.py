from __future__ import annotations

from types import SimpleNamespace
import unittest

from run350_roi_evaluation_intent_precision import (
    ROI_OUTCOME_FAILURE,
    install,
    roi_sentences_are_evaluation_intent_only,
)


class _Logger:
    def __init__(self):
        self.messages = []

    def info(self, message, *args):
        self.messages.append(message % args if args else str(message))


class Run350RoiEvaluationIntentPrecisionTests(unittest.TestCase):
    def _pipeline(self, extra_failures=None):
        extra_failures = list(extra_failures or [])

        def base_gate(parsed, *args, **kwargs):
            failures = [ROI_OUTCOME_FAILURE, *extra_failures]
            return False, failures

        return SimpleNamespace(validate_fact_gate=base_gate, logger=_Logger())

    def test_real_run38_deepseek_sentence_is_evaluation_intent(self):
        article = (
            "オープンウェイトの強みを活かし、対応APIプロバイダー経由で小さな検証を回すのが安全です。"
            "特性を理解した上で、自社にとって投資対効果が見合うかを見極めていきましょう。"
        )
        self.assertTrue(roi_sentences_are_evaluation_intent_only(article))
        p = self._pipeline()
        install(p)
        ok, failures = p.validate_fact_gate({"note_draft": article, "action_text": "限定検証を行う。"})
        self.assertTrue(ok)
        self.assertEqual([], failures)
        self.assertTrue(any("RUN350 ROI INTENT PRECISION" in row for row in p.logger.messages))

    def test_measure_roi_during_trial_is_allowed(self):
        for sentence in (
            "限定PoCで投資対効果を測定し、継続導入するか判断します。",
            "ROIが見合うかを自社データで確認してから採否を決めます。",
            "実運用前に費用と効果を計測し、投資対効果を評価します。",
            "月間コストを試算したうえでROIを見極めます。",
        ):
            self.assertTrue(roi_sentences_are_evaluation_intent_only(sentence), sentence)

    def test_positive_roi_claims_remain_blocked(self):
        for sentence in (
            "このモデルは投資対効果が高いです。",
            "導入すればROIが改善します。",
            "投資対効果は2倍になります。",
            "この選択は高いROIを保証します。",
            "ROIは十分に見合う。",
        ):
            self.assertFalse(roi_sentences_are_evaluation_intent_only(sentence), sentence)
            p = self._pipeline()
            install(p)
            self.assertEqual(
                (False, [ROI_OUTCOME_FAILURE]),
                p.validate_fact_gate({"note_draft": sentence}),
            )

    def test_unknown_roi_wording_fails_closed(self):
        sentence = "この製品のROIについて説明します。"
        self.assertFalse(roi_sentences_are_evaluation_intent_only(sentence))

    def test_mixed_evaluation_and_positive_claim_remains_blocked(self):
        article = (
            "まず投資対効果を測定します。"
            "そのうえで、このモデルはROIが高いので全社導入します。"
        )
        self.assertFalse(roi_sentences_are_evaluation_intent_only(article))
        p = self._pipeline()
        install(p)
        self.assertEqual((False, [ROI_OUTCOME_FAILURE]), p.validate_fact_gate({"note_draft": article}))

    def test_other_fact_failures_are_never_removed(self):
        article = "限定検証で投資対効果を測定し、採否を判断します。"
        p = self._pipeline(extra_failures=["unsupported numeric claim: 999%"])
        install(p)
        ok, failures = p.validate_fact_gate({"note_draft": article})
        self.assertFalse(ok)
        self.assertEqual(["unsupported numeric claim: 999%"], failures)

    def test_no_roi_sentence_cannot_rescue(self):
        p = self._pipeline()
        install(p)
        self.assertEqual(
            (False, [ROI_OUTCOME_FAILURE]),
            p.validate_fact_gate({"note_draft": "限定検証を行います。"}),
        )

    def test_install_is_idempotent(self):
        p = self._pipeline()
        install(p)
        first = p.validate_fact_gate
        install(p)
        self.assertIs(first, p.validate_fact_gate)


if __name__ == "__main__":
    unittest.main()
