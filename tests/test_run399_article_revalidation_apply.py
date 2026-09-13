from __future__ import annotations

import os
import types
import unittest
from unittest.mock import patch

import run399_article_revalidation_apply as run399


class _Budget:
    def __init__(self, budget=4):
        self.budget = budget
        self.used = 0


class Run399ApprovedApplyTests(unittest.TestCase):
    def _pipeline(self):
        pipeline = types.SimpleNamespace()
        pipeline.ARTICLE_STATUS_READY = "Ready"
        pipeline.ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW = "Needs Editorial Review"
        pipeline.CONTENT_STATUS_PENDING_RETRY = "Pending Retry"
        pipeline.CONTENT_STATUS_QUALITY_FAILED = "Quality Failed"
        pipeline.DEEP_DIVE_MODEL_BUDGET = _Budget()
        pipeline.logger = types.SimpleNamespace(warning=lambda *a, **k: None, info=lambda *a, **k: None)
        pipeline.legal_safety_gate = lambda repo: (True, "safe")
        pipeline.should_attempt_dynamic_retry = lambda rows, evidence, origin="new": (False, "test_no_retry")
        pipeline.get_regen_test_items = lambda limit, query: []
        pipeline.get_pending_retry_items = lambda limit: []
        return pipeline

    def _item(self, name=run399.DEFAULT_EXPECTED_NAME, page_id="page-1"):
        return {
            "notion_page_id": page_id,
            "repo": {"nameWithOwner": name},
            "screening_score": 81,
            "screening_reason": "test",
        }

    def _install_rows(self, pipeline, rows, pending_rows=None):
        pipeline.get_regen_test_items = lambda limit, query: list(rows)
        pipeline.get_pending_retry_items = lambda limit: list(pending_rows or [])

    def test_refuses_without_explicit_approval(self):
        pipeline = self._pipeline()
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "approval token"):
                run399.run_approved_article_apply(pipeline)

    def test_exact_target_lookup_never_substitutes_first_other_candidate(self):
        pipeline = self._pipeline()
        self._install_rows(pipeline, [self._item("wrong target")])
        pipeline.generate_intelligence_report = lambda *a, **k: self.fail("must not generate")
        with patch.dict(os.environ, {
            "ARTICLE_REVALIDATION_APPLY_CONFIRM": run399.APPROVAL_TOKEN,
            "ARTICLE_REVALIDATION_EXPECTED_NAME": run399.DEFAULT_EXPECTED_NAME,
        }, clear=True), patch.object(run399.article_revalidation, "_cap_validation_budget", return_value=4):
            with self.assertRaisesRegex(RuntimeError, "exact target count mismatch"):
                run399.run_approved_article_apply(pipeline)

    def test_persists_only_exact_target_and_requires_accepted(self):
        pipeline = self._pipeline()
        self._install_rows(pipeline, [self._item("other"), self._item()])
        calls = []

        def generate(repo, **kwargs):
            calls.append((repo, kwargs))
            return ("published-quality manuscript", "accepted")

        pipeline.generate_intelligence_report = generate
        with patch.dict(os.environ, {
            "ARTICLE_REVALIDATION_APPLY_CONFIRM": run399.APPROVAL_TOKEN,
            "ARTICLE_REVALIDATION_EXPECTED_NAME": run399.DEFAULT_EXPECTED_NAME,
        }, clear=True), patch.object(run399.article_revalidation, "_cap_validation_budget", return_value=4), patch.object(
            run399.article_revalidation,
            "_read_current_statuses",
            return_value=("Needs Editorial Review", "Deep Dive"),
        ):
            result = run399.run_approved_article_apply(pipeline)

        self.assertEqual(result["accepted"], 1)
        self.assertEqual(result["target_source"], "deep_dive")
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0][1]["persist_results"])
        self.assertEqual(calls[0][1]["candidate_origin"], "approved_article_apply")
        self.assertEqual(calls[0][1]["notion_page_id"], "page-1")
        self.assertFalse(result["pending_continuation"])

    def test_exact_owner_approved_pending_retry_can_continue_from_canonical_pending_source(self):
        pipeline = self._pipeline()
        self._install_rows(pipeline, [self._item("other")], pending_rows=[self._item()])
        calls = []
        pipeline.generate_intelligence_report = lambda repo, **kwargs: calls.append((repo, kwargs)) or ("draft", "accepted")
        with patch.dict(os.environ, {
            "ARTICLE_REVALIDATION_APPLY_CONFIRM": run399.APPROVAL_TOKEN,
            "ARTICLE_REVALIDATION_EXPECTED_NAME": run399.DEFAULT_EXPECTED_NAME,
        }, clear=True), patch.object(run399.article_revalidation, "_cap_validation_budget", return_value=5), patch.object(
            run399.article_revalidation,
            "_read_current_statuses",
            return_value=("Needs Editorial Review", "Pending Retry"),
        ):
            result = run399.run_approved_article_apply(pipeline)

        self.assertTrue(result["pending_continuation"])
        self.assertEqual(result["target_source"], "pending_retry")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0]["nameWithOwner"], run399.DEFAULT_EXPECTED_NAME)

    def test_same_page_seen_in_both_sources_is_deduplicated(self):
        pipeline = self._pipeline()
        self._install_rows(pipeline, [self._item()], pending_rows=[self._item()])
        selected = run399._select_exact_approved_target(pipeline, run399.DEFAULT_EXPECTED_NAME)
        self.assertEqual(selected["notion_page_id"], "page-1")
        self.assertEqual(selected["approved_target_source"], "deep_dive")

    def test_duplicate_exact_target_different_pages_fails_closed_before_generation(self):
        pipeline = self._pipeline()
        self._install_rows(pipeline, [self._item(page_id="page-1")], pending_rows=[self._item(page_id="page-2")])
        pipeline.generate_intelligence_report = lambda *a, **k: self.fail("must not generate")
        with patch.dict(os.environ, {
            "ARTICLE_REVALIDATION_APPLY_CONFIRM": run399.APPROVAL_TOKEN,
            "ARTICLE_REVALIDATION_EXPECTED_NAME": run399.DEFAULT_EXPECTED_NAME,
        }, clear=True), patch.object(run399.article_revalidation, "_cap_validation_budget", return_value=5):
            with self.assertRaisesRegex(RuntimeError, "matches=2"):
                run399.run_approved_article_apply(pipeline)

    def test_pending_lifecycle_from_non_pending_source_fails_closed(self):
        pipeline = self._pipeline()
        self._install_rows(pipeline, [self._item()])
        pipeline.generate_intelligence_report = lambda *a, **k: self.fail("must not generate")
        with patch.dict(os.environ, {
            "ARTICLE_REVALIDATION_APPLY_CONFIRM": run399.APPROVAL_TOKEN,
            "ARTICLE_REVALIDATION_EXPECTED_NAME": run399.DEFAULT_EXPECTED_NAME,
        }, clear=True), patch.object(run399.article_revalidation, "_cap_validation_budget", return_value=5), patch.object(
            run399.article_revalidation,
            "_read_current_statuses",
            return_value=("Needs Editorial Review", "Pending Retry"),
        ):
            with self.assertRaisesRegex(RuntimeError, "canonical pending source"):
                run399.run_approved_article_apply(pipeline)

    def test_rejected_regeneration_fails_closed(self):
        pipeline = self._pipeline()
        self._install_rows(pipeline, [self._item()])
        pipeline.generate_intelligence_report = lambda *a, **k: ("draft", "rejected")
        with patch.dict(os.environ, {
            "ARTICLE_REVALIDATION_APPLY_CONFIRM": run399.APPROVAL_TOKEN,
            "ARTICLE_REVALIDATION_EXPECTED_NAME": run399.DEFAULT_EXPECTED_NAME,
        }, clear=True), patch.object(run399.article_revalidation, "_cap_validation_budget", return_value=4), patch.object(
            run399.article_revalidation,
            "_read_current_statuses",
            return_value=("Needs Editorial Review", "Deep Dive"),
        ):
            with self.assertRaisesRegex(RuntimeError, "did not pass"):
                run399.run_approved_article_apply(pipeline)


if __name__ == "__main__":
    unittest.main()
