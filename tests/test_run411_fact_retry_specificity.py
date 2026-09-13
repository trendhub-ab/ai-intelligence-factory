from __future__ import annotations

import types
import unittest

import run411_fact_retry_specificity as run411


class Run411FactRetrySpecificityTests(unittest.TestCase):
    def _pipeline(self):
        def base(rows):
            return "BASE", ["fact"]
        return types.SimpleNamespace(build_dynamic_retry_instruction=base)

    def test_vague_quantified_claim_is_explicitly_removed_or_weakened(self):
        p = self._pipeline()
        run411.install(p)
        instruction, _ = p.build_dynamic_retry_instruction([
            {"message": "unsupported vague quantified claim: 数日"}
        ])
        self.assertIn("『数日』", instruction)
        self.assertIn("数量を含まない事実範囲の表現", instruction)
        self.assertIn("推測で別の期間・件数へ置き換えない", instruction)

    def test_limitation_dropped_requires_one_evidence_backed_limitation(self):
        p = self._pipeline()
        run411.install(p)
        instruction, _ = p.build_dynamic_retry_instruction([
            {"message": "LIMITATION_DROPPED"}
        ])
        self.assertIn("一次Evidenceに実在する制約を1つだけ短く復元", instruction)
        self.assertIn("新しい制約を創作せず", instruction)

    def test_combined_fact_failure_must_be_fixed_in_same_retry(self):
        p = self._pipeline()
        run411.install(p)
        instruction, _ = p.build_dynamic_retry_instruction([
            {"message": "unsupported vague quantified claim: 数日"},
            {"message": "LIMITATION_DROPPED"},
        ])
        self.assertIn("同じ1回のHARD quality retryで両方修正", instruction)
        self.assertIn("Decision・Score", instruction)

    def test_unrelated_retry_is_unchanged(self):
        p = self._pipeline()
        run411.install(p)
        instruction, sections = p.build_dynamic_retry_instruction([
            {"message": "some unrelated reader issue"}
        ])
        self.assertEqual(instruction, "BASE")
        self.assertEqual(sections, ["fact"])

    def test_install_is_idempotent(self):
        p = self._pipeline()
        run411.install(p)
        first = p.build_dynamic_retry_instruction
        run411.install(p)
        self.assertIs(first, p.build_dynamic_retry_instruction)


if __name__ == "__main__":
    unittest.main()
