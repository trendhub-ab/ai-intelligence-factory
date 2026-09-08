from __future__ import annotations

import inspect
import unittest

import run301_genrec_summary_restore as r301


class Run301SummaryMetricsTests(unittest.TestCase):
    def test_exact_summary_is_present_once_in_correct_order(self):
        text = f"""## どんな内容？

{r301.EXPECTED_SUMMARY}

**なぜ重要？**
重要です。
"""
        metrics = r301._summary_metrics(text)
        self.assertEqual(metrics["summary_count"], 1)
        self.assertTrue(metrics["summary_present_once"])
        self.assertTrue(metrics["summary_order_valid"])
        self.assertTrue(metrics["what_label_absent"])

    def test_missing_summary_is_detected_without_confusing_removed_label(self):
        text = """## どんな内容？

**なぜ重要？**
重要です。
"""
        metrics = r301._summary_metrics(text)
        self.assertEqual(metrics["summary_count"], 0)
        self.assertFalse(metrics["summary_present_once"])
        self.assertFalse(metrics["summary_order_valid"])
        self.assertTrue(metrics["what_label_absent"])

    def test_duplicate_summary_fails_exactness(self):
        text = f"""## どんな内容？
{r301.EXPECTED_SUMMARY}
{r301.EXPECTED_SUMMARY}
**なぜ重要？**
重要です。
"""
        metrics = r301._summary_metrics(text)
        self.assertEqual(metrics["summary_count"], 2)
        self.assertFalse(metrics["summary_present_once"])

    def test_what_label_must_stay_absent(self):
        text = f"""## どんな内容？
**何が出た？**
{r301.EXPECTED_SUMMARY}
**なぜ重要？**
重要です。
"""
        metrics = r301._summary_metrics(text)
        self.assertFalse(metrics["what_label_absent"])


class Run301SafetyBoundaryTests(unittest.TestCase):
    def test_no_new_draft_or_public_release_surface(self):
        source = inspect.getsource(r301).lower()
        for forbidden in (
            "/new",
            "publish_note",
            "public_release = true",
            "_upload_header_image(",
            "generate_content(",
            "_generate_via_chat(",
        ):
            self.assertNotIn(forbidden, source)

    def test_exact_summary_contract_is_user_approved_text(self):
        self.assertEqual(
            r301.EXPECTED_SUMMARY,
            "Netflixがユーザー行動や文脈をテキスト化し、vLLMのprefill-onlyモードでスコアリングを行う推薦アーキテクチャGenRecを公開した。",
        )


if __name__ == "__main__":
    unittest.main()
