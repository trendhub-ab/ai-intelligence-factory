from __future__ import annotations

import unittest
from unittest.mock import patch

import evidence_context
import pipeline


class Run236EvidenceContextIntegrationTests(unittest.TestCase):
    def test_pipeline_aliases_are_exact_extracted_functions(self):
        self.assertIs(pipeline._truncate_text_context, evidence_context.truncate_text_context)
        self.assertIs(pipeline._verification_excerpt, evidence_context.verification_excerpt)

    def test_source_wrapper_uses_live_pipeline_limit(self):
        text = "abcdefghijklmnopqrstuvwxyz"
        with patch.object(pipeline, "SOURCE_CONTEXT_MAX_CHARS", 7):
            self.assertEqual(pipeline._truncate_source_context(text), "abcdefg")
        with patch.object(pipeline, "SOURCE_CONTEXT_MAX_CHARS", 13):
            self.assertEqual(pipeline._truncate_source_context(text), "abcdefghijklm")

    def test_verification_wrapper_uses_live_pipeline_limit(self):
        text = "abcdefghijklmnopqrstuvwxyz"
        with patch.object(pipeline, "VERIFICATION_CONTEXT_MAX_CHARS", 9):
            self.assertEqual(pipeline._truncate_verification_context(text), "abcdefghi")
        with patch.object(pipeline, "VERIFICATION_CONTEXT_MAX_CHARS", 15):
            self.assertEqual(pipeline._truncate_verification_context(text), "abcdefghijklmno")

    def test_merge_wrapper_uses_live_pipeline_limit_and_preserves_behavior(self):
        old = "OLD-" + ("a" * 100)
        new = "NEW-" + ("b" * 100)
        for limit in (0, 40, 80, 120, 1000):
            with patch.object(pipeline, "VERIFICATION_CONTEXT_MAX_CHARS", limit):
                self.assertEqual(
                    pipeline._merge_verification_context(old, new),
                    evidence_context.merge_verification_context(old, new, limit),
                )

    def test_wrapper_limit_changes_do_not_mutate_module_state(self):
        text = "x" * 100
        baseline = evidence_context.truncate_text_context(text, 25)
        with patch.object(pipeline, "SOURCE_CONTEXT_MAX_CHARS", 5):
            self.assertEqual(pipeline._truncate_source_context(text), "xxxxx")
        self.assertEqual(evidence_context.truncate_text_context(text, 25), baseline)


if __name__ == "__main__":
    unittest.main()
