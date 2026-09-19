from __future__ import annotations

import unittest

import canonical_article_contract as cac
import run228_reader_rhythm_planning as run228


class Run228ReaderRhythmPlanningTests(unittest.TestCase):
    def test_contract_is_only_a_compatibility_layer(self):
        contract = run228.reader_rhythm_contract()
        self.assertIn(run228.RUN228_MARKER, contract)
        self.assertIn("canonical article contract V1", contract)
        self.assertIn("no independent article philosophy", contract)
        self.assertIn("報告書の塊", contract)

    def test_augment_prompt_installs_canonical_writer_and_final_check_once(self):
        first = run228.augment_prompt("BASE")
        second = run228.augment_prompt(first)
        self.assertEqual(first, second)
        self.assertEqual(1, second.count(run228.RUN228_MARKER))
        self.assertEqual(1, second.count(cac.CANONICAL_ARTICLE_CONTRACT_MARKER))
        self.assertEqual(1, second.count(cac.CANONICAL_FINAL_READER_CHECK_MARKER))
        self.assertIn("Evidence・重要数値・条件・反証・Decisionは削らない", second)

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
        self.assertEqual(first.count(cac.CANONICAL_ARTICLE_CONTRACT_MARKER), 1)
        self.assertEqual(first.count(cac.CANONICAL_FINAL_READER_CHECK_MARKER), 1)
        self.assertEqual(DummyPipeline.calls, 2)


if __name__ == "__main__":
    unittest.main()
