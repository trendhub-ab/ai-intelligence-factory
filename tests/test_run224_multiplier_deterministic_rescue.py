from __future__ import annotations

import re
import unittest

import run223_technical_claim_precision as run223
import run224_multiplier_deterministic_rescue as run224


class Run224MultiplierDeterministicRescueTests(unittest.TestCase):
    def setUp(self):
        self.source = (
            "On Mind2Web, the updated Codex harness benchmark delivered 1.9x faster performance "
            "under the reported evaluation conditions."
        )
        self.failure_rows = [{
            "reason_code": "FACT_UNSUPPORTED_CLAIM",
            "message": (
                "performance_multiplier_scope_lost: a source expectation/benchmark multiplier "
                "is presented without preserving attribution/modality and workload-or-condition variability"
            ),
            "severity": "HARD",
        }]

    def test_adds_scope_and_variability_without_changing_multiplier(self):
        article = "Mind2Webでは性能が1.9倍に向上しました。"
        self.assertTrue(run223.multiplier_scope_failures(article, self.source))
        rescued, changes = run224.rescue_multiplier_scope({"note_draft": article}, self.failure_rows)
        fixed = rescued["note_draft"]
        self.assertEqual(run223.multiplier_scope_failures(fixed, self.source), [])
        self.assertIn("一次情報", fixed)
        self.assertIn("実際の改善幅", fixed)
        self.assertIn("処理内容・条件・実行環境によって変わります", fixed)
        self.assertEqual(re.findall(r"\d+(?:\.\d+)?", fixed), ["1.9"])
        self.assertEqual(changes, ["run224_multiplier_scope_qualifier:1"])

    def test_is_idempotent(self):
        article = "Mind2Webでは性能が1.9倍に向上しました。"
        first, _ = run224.rescue_multiplier_scope({"note_draft": article}, self.failure_rows)
        second, changes = run224.rescue_multiplier_scope(first, self.failure_rows)
        self.assertEqual(second["note_draft"], first["note_draft"])
        self.assertEqual(changes, [])

    def test_does_not_activate_without_run223_failure(self):
        article = "Mind2Webでは性能が1.9倍に向上しました。"
        rescued, changes = run224.rescue_multiplier_scope(
            {"note_draft": article},
            [{"reason_code": "OTHER", "message": "other failure", "severity": "HARD"}],
        )
        self.assertEqual(rescued["note_draft"], article)
        self.assertEqual(changes, [])

    def test_fenced_code_and_heading_are_not_edited(self):
        article = "# 1.9倍高速という見出し\n\n```text\nperformance 1.9x faster\n```\n\n本文です。"
        rescued, changes = run224.rescue_multiplier_scope({"note_draft": article}, self.failure_rows)
        self.assertEqual(rescued["note_draft"], article)
        self.assertEqual(changes, [])

    def test_installer_preserves_existing_rescue_and_adds_scope_patch(self):
        class DummyPipeline:
            @staticmethod
            def _apply_deterministic_publication_rescue(parsed, reason_rows):
                result = dict(parsed)
                result["note_draft"] = result["note_draft"].replace("圧倒的", "")
                return result, ["remove_unsupported_hype:圧倒的"]

        pipe = DummyPipeline()
        run224.install(pipe)
        article = "Mind2Webでは圧倒的な性能となり、1.9倍高速です。"
        rescued, changes = pipe._apply_deterministic_publication_rescue(
            {"note_draft": article}, self.failure_rows
        )
        self.assertNotIn("圧倒的", rescued["note_draft"])
        self.assertIn("run224_multiplier_scope_qualifier:1", changes)
        self.assertIn("remove_unsupported_hype:圧倒的", changes)
        self.assertEqual(run223.multiplier_scope_failures(rescued["note_draft"], self.source), [])

    def test_existing_scope_and_variability_need_no_patch(self):
        article = (
            "一次情報のベンチマーク条件では性能が1.9倍でした。"
            "実際の改善幅は処理内容や実行環境によって変わります。"
        )
        rescued, changes = run224.rescue_multiplier_scope({"note_draft": article}, self.failure_rows)
        self.assertEqual(rescued["note_draft"], article)
        self.assertEqual(changes, [])


if __name__ == "__main__":
    unittest.main()
