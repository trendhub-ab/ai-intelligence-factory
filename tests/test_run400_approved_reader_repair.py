from __future__ import annotations

import types
import unittest

import run400_approved_reader_repair as run400


class Run400ApprovedReaderRepairTests(unittest.TestCase):
    def test_approved_origin_reuses_article_revalidation_policy(self):
        calls = []
        pipeline = types.SimpleNamespace()

        def original(rows, evidence, origin="new"):
            calls.append(origin)
            return (origin == "article_revalidation", "reader_repair" if origin == "article_revalidation" else "no")

        pipeline.should_attempt_dynamic_retry = original
        run400.install(pipeline)
        decision = pipeline.should_attempt_dynamic_retry(
            [{"message": "reader_value_review:multi_axis_reader_weakness", "severity": "REVIEW"}],
            {"state": "SUFFICIENT", "decision_scope_safe": True},
            "approved_article_apply",
        )
        self.assertEqual(decision, (True, "reader_repair"))
        self.assertEqual(calls, ["article_revalidation"])

    def test_other_origins_are_unchanged(self):
        calls = []
        pipeline = types.SimpleNamespace()

        def original(rows, evidence, origin="new"):
            calls.append(origin)
            return (False, "unchanged")

        pipeline.should_attempt_dynamic_retry = original
        run400.install(pipeline)
        self.assertEqual(
            pipeline.should_attempt_dynamic_retry([], {}, "pending_retry"),
            (False, "unchanged"),
        )
        self.assertEqual(calls, ["pending_retry"])

    def test_install_is_idempotent(self):
        pipeline = types.SimpleNamespace(
            should_attempt_dynamic_retry=lambda rows, evidence, origin="new": (False, origin)
        )
        run400.install(pipeline)
        first = pipeline.should_attempt_dynamic_retry
        run400.install(pipeline)
        self.assertIs(first, pipeline.should_attempt_dynamic_retry)

    def test_missing_canonical_retry_policy_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "canonical should_attempt_dynamic_retry"):
            run400.install(types.SimpleNamespace())


if __name__ == "__main__":
    unittest.main()
