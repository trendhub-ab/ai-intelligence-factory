from __future__ import annotations

import unittest

import run228_reader_rhythm_planning as run228


class Run228ReaderRhythmPlanningTests(unittest.TestCase):
    def test_contract_preserves_evidence_and_reduces_report_stacking(self):
        contract = run228.reader_rhythm_contract()
        self.assertIn("報告書の塊", contract)
        self.assertIn("理解→意味→判断", contract)
        self.assertIn("Evidence上重要な数値・条件・反証・制約は削らない", contract)
        self.assertIn("新しいFact、数字、人物、会話、利用実績、因果、競合情報を作る", contract)

    def test_contract_avoids_style_count_quotas_and_fixed_template(self):
        contract = run228.reader_rhythm_contract()
        forbidden = (
            "問いかけを1回",
            "問いかけを2回",
            "1段落3",
            "箇条書き2",
            "比喩を1回",
            "問題提起→比喩→3点列挙→私なら の順序へ揃える",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, contract)
        self.assertIn("回数ノルマを設けない", contract)
        self.assertIn("全記事を同じ", contract)

    def test_augment_prompt_is_idempotent(self):
        first = run228.augment_prompt("BASE")
        second = run228.augment_prompt(first)
        self.assertEqual(first, second)
        self.assertEqual(second.count(run228.RUN228_MARKER), 1)

    def test_install_adds_no_call_site_and_is_idempotent(self):
        class DummyPipeline:
            calls = 0

            @staticmethod
            def build_decision_prompt(*args, **kwargs):
                DummyPipeline.calls += 1
                return "BASE"

        pipe = DummyPipeline()
        run228.install(pipe)
        first = pipe.build_decision_prompt()
        run228.install(pipe)
        second = pipe.build_decision_prompt()
        self.assertEqual(first, second)
        self.assertEqual(first.count(run228.RUN228_MARKER), 1)
        self.assertEqual(DummyPipeline.calls, 2)


if __name__ == "__main__":
    unittest.main()
