import os
import unittest

# Run157 protects publication quality without adding provider/API calls.
os.environ.setdefault("SYNTHETIC_REGRESSION_MODE", "true")

import pipeline


OBSERVATIONAL_CONTEXT = """
Sophistication in GenAI Use: Field Evidence from a Large Firm.
We document an association between employee seniority and more sophisticated GenAI use.
The pattern is consistent with domain knowledge complementing AI capability and suggests
that expertise may shape how workers use generative AI. This observational field evidence
does not establish causality. The study does not measure return on investment.
"""


class Run157CausalInferenceEvidenceGuardTests(unittest.TestCase):
    def test_actual_false_positive_style_causal_leap_is_blocked(self):
        draft = "シニア社員ほど高度な使い方が見られました。その理由は『ドメイン知識』にあります。"
        failures = pipeline._find_causal_inference_overclaims(draft, OBSERVATIONAL_CONTEXT)
        self.assertIn(
            "causal inference overclaim: observational evidence upgraded to causation",
            failures,
        )

    def test_caveated_interpretation_is_allowed(self):
        draft = "この結果は、業務知識がAI活用を補完している可能性を示しています。因果関係までは断定できません。"
        self.assertEqual([], pipeline._find_causal_inference_overclaims(draft, OBSERVATIONAL_CONTEXT))

    def test_unsupported_roi_conclusion_is_blocked(self):
        draft = "一律研修だけでは、AI投資の成果（ROI）を得るのが難しいことは明白です。"
        failures = pipeline._find_causal_inference_overclaims(draft, OBSERVATIONAL_CONTEXT)
        self.assertIn(
            "unsupported outcome extrapolation: ROI/financial outcome not measured by evidence",
            failures,
        )

    def test_explicit_roi_limitation_is_allowed(self):
        draft = "この研究だけでROIへの影響までは断定できません。利用回数だけを成功指標にする際は注意が必要です。"
        self.assertEqual([], pipeline._find_causal_inference_overclaims(draft, OBSERVATIONAL_CONTEXT))

    def test_measured_roi_evidence_allows_roi_discussion(self):
        context = "The randomized study measured return on investment and reported a 12% improvement in ROI."
        draft = "この実験ではROIが12%改善しました。"
        failures = pipeline._find_causal_inference_overclaims(draft, context)
        self.assertNotIn(
            "unsupported outcome extrapolation: ROI/financial outcome not measured by evidence",
            failures,
        )

    def test_causal_design_does_not_trigger_observational_guard(self):
        context = OBSERVATIONAL_CONTEXT + "\nA randomized controlled trial was used for the intervention."
        draft = "その理由は介入にあります。"
        failures = pipeline._find_causal_inference_overclaims(draft, context)
        self.assertNotIn(
            "causal inference overclaim: observational evidence upgraded to causation",
            failures,
        )

    def test_fact_gate_integrates_guard(self):
        parsed = {
            "note_draft": "企業ログでは相関が確認されました。その理由はドメイン知識にあります。",
            "decision_text": "TRY",
            "score": 80,
            "title_text": "企業AI活用の差はどこから生まれる？",
            "decision_reason_text": "限定的な検証価値がある。",
            "action_text": "自社データで限定検証する。",
            "source_summary_text": "大手企業の利用ログを分析した観察研究。",
        }
        ok, failures = pipeline.validate_fact_gate(
            parsed,
            "Sophistication in GenAI Use",
            source_context=OBSERVATIONAL_CONTEXT,
            evidence_metadata={},
        )
        self.assertFalse(ok)
        self.assertIn(
            "causal inference overclaim: observational evidence upgraded to causation",
            failures,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
