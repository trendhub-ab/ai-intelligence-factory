from __future__ import annotations

import types
import unittest

import run284_reader_recovery_precision
from run352_retry_preservation import (
    RETRY_PRESERVATION_CONTRACT,
    install,
    repair_deterministic_rescue_surface,
    retry_feedback_with_preservation,
)


class Run352RetryPreservationTests(unittest.TestCase):
    def test_contract_is_added_only_to_real_retry(self):
        feedback = "一次情報にない主張だけを削除してください。"
        previous = "読者に届く前回ARTICLE"
        updated = retry_feedback_with_preservation(feedback, previous)
        self.assertIn(feedback, updated)
        self.assertIn(RETRY_PRESERVATION_CONTRACT, updated)
        self.assertEqual("", retry_feedback_with_preservation("", previous))
        self.assertEqual(feedback, retry_feedback_with_preservation(feedback, ""))

    def test_contract_explicitly_forbids_new_business_outcomes(self):
        contract = RETRY_PRESERVATION_CONTRACT
        self.assertIn("ROI", contract)
        self.assertIn("コスト効果", contract)
        self.assertIn("競合比較", contract)
        self.assertIn("全文リライトではありません", contract)
        self.assertIn("見出し", contract)
        self.assertIn("比喩", contract)

    def test_real_run38_ga_ni_corruption_is_repaired_without_restoring_hype(self):
        before = {
            "note_draft": "『おしゃべりだが圧倒的に速く賢い』という特性を踏まえると、小さく試します。",
            "title_text": "比較記事",
            "action_text": "限定検証する",
        }
        rescued = {
            "note_draft": "『おしゃべりだがに速く賢い』という特性を踏まえると、小さく試します。",
            "title_text": "比較記事",
            "action_text": "限定検証する",
            "_rescue_loss": {"removed_sentences": 0, "important_numeric_removed": False, "loss_exceeded": False},
        }
        fixed, changes = repair_deterministic_rescue_surface(before, rescued)
        self.assertIn("おしゃべりだが速く賢い", fixed["note_draft"])
        self.assertNotIn("圧倒的", fixed["note_draft"])
        self.assertNotIn("だがに", fixed["note_draft"])
        self.assertTrue(any("remove_stranded_ni_after_圧倒的" in item for item in changes))
        self.assertEqual(rescued["_rescue_loss"], fixed["_rescue_loss"])

    def test_unrelated_ni_is_never_changed(self):
        before = {"note_draft": "この方式は圧倒的だが、導入には注意が必要です。"}
        rescued = {"note_draft": "この方式はだが、導入には注意が必要です。別の箇所がに注意します。"}
        fixed, changes = repair_deterministic_rescue_surface(before, rescued)
        self.assertEqual(rescued["note_draft"], fixed["note_draft"])
        self.assertEqual([], changes)

    def test_other_base_hype_tokens_with_adverbial_ni_are_repaired(self):
        for token in ("劇的", "革命的"):
            before = {"note_draft": f"以前より{token}に速くなったと主張します。"}
            rescued = {"note_draft": "以前よりに速くなったと主張します。"}
            fixed, changes = repair_deterministic_rescue_surface(before, rescued)
            self.assertEqual("以前より速くなったと主張します。", fixed["note_draft"])
            self.assertTrue(changes)

    def test_install_wraps_existing_retry_without_extra_call(self):
        calls = []

        def build_decision_prompt(name, url, stars, desc, quality_feedback="", source="GitHub",
                                  source_context="", grounding_status_hint=None, evidence_metadata=None,
                                  freshness=None, previous_article="", evidence_result=None):
            calls.append({"quality_feedback": quality_feedback, "previous_article": previous_article})
            return quality_feedback

        def rescue(parsed, reason_rows):
            return ({
                **parsed,
                "note_draft": str(parsed.get("note_draft") or "").replace("圧倒的", ""),
            }, ["remove_hype:圧倒的"])

        module = types.SimpleNamespace(
            build_decision_prompt=build_decision_prompt,
            _apply_deterministic_publication_rescue=rescue,
        )
        install(module)
        install(module)

        result = module.build_decision_prompt(
            "x", "u", 0, "d",
            quality_feedback="該当主張だけ直す",
            previous_article="導入を保った前稿",
        )
        self.assertEqual(1, len(calls))
        self.assertIn(RETRY_PRESERVATION_CONTRACT, result)

        fixed, changes = module._apply_deterministic_publication_rescue(
            {"note_draft": "おしゃべりだが圧倒的に速い"}, []
        )
        self.assertEqual("おしゃべりだが速い", fixed["note_draft"])
        self.assertIn("remove_hype:圧倒的", changes)
        self.assertTrue(any("remove_stranded_ni_after_圧倒的" in item for item in changes))

    def test_run284_production_install_chains_run352_without_authorizing_new_retry(self):
        retry_calls = []

        def base_retry(reason_rows, evidence_result, candidate_origin="new"):
            retry_calls.append((list(reason_rows or []), candidate_origin))
            return False, "reader_value_review_no_retry"

        module = types.SimpleNamespace(
            _JAPANESE_SAFE_FIXES=(),
            should_attempt_dynamic_retry=base_retry,
            GATE_SEVERITY_HARD="HARD",
            EVIDENCE_SUFFICIENT="SUFFICIENT",
        )
        run284_reader_recovery_precision.install(module)

        self.assertTrue(getattr(module, "_run284_reader_recovery_precision_installed", False))
        self.assertTrue(getattr(module, "_run352_retry_preservation_installed", False))
        allowed, reason = module.should_attempt_dynamic_retry([], None, "new")
        self.assertFalse(allowed)
        self.assertEqual("reader_value_review_no_retry", reason)
        self.assertEqual(1, len(retry_calls))


if __name__ == "__main__":
    unittest.main()
