from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import evidence_context
import pipeline


class Run236EvidenceContextModuleTests(unittest.TestCase):
    def test_module_is_provider_and_persistence_free(self):
        source = inspect.getsource(evidence_context)
        forbidden = (
            "requests.", "genai", "GEMINI_API_KEY", "NOTION_API_KEY",
            "save_to_notion", "github.com/", "api.notion.com",
        )
        for token in forbidden:
            self.assertNotIn(token, source)

    def test_truncate_text_context_exact_parity(self):
        samples = [
            ("", 10),
            ("  alpha\n\n\n\nbeta  ", 100),
            ("abcdef", 3),
            ("abcdef", 0),
            ("abcdef", -5),
        ]
        for text, limit in samples:
            self.assertEqual(
                pipeline._truncate_text_context(text, limit),
                evidence_context.truncate_text_context(text, limit),
            )

    def test_verification_excerpt_exact_parity(self):
        text = "HEAD-" + ("a" * 180) + "\n\n\n\n" + ("z" * 180) + "-TAIL"
        for limit in (0, 32, 64, 65, 120, 1000):
            self.assertEqual(
                pipeline._verification_excerpt(text, limit),
                evidence_context.verification_excerpt(text, limit),
            )

    def test_source_wrapper_uses_live_pipeline_limit(self):
        text = "abcdefghijklmnopqrstuvwxyz"
        with patch.object(pipeline, "SOURCE_CONTEXT_MAX_CHARS", 7):
            self.assertEqual(pipeline._truncate_source_context(text), "abcdefg")

    def test_verification_wrapper_uses_live_pipeline_limit(self):
        text = "abcdefghijklmnopqrstuvwxyz"
        with patch.object(pipeline, "VERIFICATION_CONTEXT_MAX_CHARS", 9):
            self.assertEqual(pipeline._truncate_verification_context(text), "abcdefghi")

    def test_merge_wrapper_preserves_exact_historical_behavior(self):
        old = "OLD-" + ("a" * 100)
        new = "NEW-" + ("b" * 100)
        for limit in (0, 40, 80, 120, 1000):
            with patch.object(pipeline, "VERIFICATION_CONTEXT_MAX_CHARS", limit):
                self.assertEqual(
                    pipeline._merge_verification_context(old, new),
                    evidence_context.merge_verification_context(old, new, limit),
                )

    def test_pipeline_owns_only_thin_limit_binding_wrappers(self):
        source = inspect.getsource(pipeline)
        self.assertIn("from evidence_context import (", source)
        self.assertIn("merge_verification_context as _merge_verification_context_impl", source)
        self.assertNotIn("[...verification context omitted...]", source)
        self.assertNotIn("new_budget = min(len(new), int(payload * 0.60))", source)


if __name__ == "__main__":
    unittest.main()
