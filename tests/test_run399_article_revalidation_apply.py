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


class _Response:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class Run399ApprovedApplyTests(unittest.TestCase):
    def _pipeline(self):
        pipeline = types.SimpleNamespace()
        pipeline.ARTICLE_STATUS_READY = "Ready"
        pipeline.ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW = "Needs Editorial Review"
        pipeline.CONTENT_STATUS_DEEP_DIVE = "Deep Dive"
        pipeline.CONTENT_STATUS_PENDING_RETRY = "Pending Retry"
        pipeline.CONTENT_STATUS_QUALITY_FAILED = "Quality Failed"
        pipeline.PROP_NAME = "記事名"
        pipeline.PROP_URL = "元情報URL"
        pipeline.PROP_SOURCE = "情報源"
        pipeline.PROP_SOURCE_SUMMARY = "元情報要約"
        pipeline.PROP_CONTENT_STATUS = "コンテンツ状態"
        pipeline.PROP_ARTICLE_STATUS = "記事状態"
        pipeline.PROP_EVALUATION_STATUS = "評価状態"
        pipeline.PROP_SCREENING_SCORE = "選別スコア"
        pipeline.PROP_SCREENING_REASON = "選別理由"
        pipeline.PROP_ENGAGEMENT = "注目度"
        pipeline.DEEP_DIVE_MODEL_BUDGET = _Budget()
        pipeline.DEEP_DIVE_MODEL_POOL = [
            "gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash"
        ]
        pipeline.logger = types.SimpleNamespace(warning=lambda *a, **k: None, info=lambda *a, **k: None)
        pipeline.legal_safety_gate = lambda repo: (True, "safe")
        pipeline.should_attempt_dynamic_retry = lambda rows, evidence, origin="new": (False, "test_no_retry")
        pipeline.get_regen_test_items = lambda limit, query: []
        pipeline.get_pending_retry_items = lambda limit: []
        pipeline._call_deep_dive_pool = lambda *a, **k: ("fixture", "gemini-3.8-flash")
        pipeline._call_model_pool = lambda *a, **k: ("fixture", "gemini-3.8-flash")
        pipeline._notion_headers = lambda: {"Authorization": "test"}
        pipeline._notion_plain_text = lambda prop: "".join(
            x.get("plain_text") or x.get("text", {}).get("content", "")
            for x in (prop.get("title") or prop.get("rich_text") or [])
        ).strip()
        pipeline.requests = types.SimpleNamespace(get=lambda *a, **k: _Response({}, 404))
        return pipeline

    def _item(self, name=run399.DEFAULT_EXPECTED_NAME, page_id=run399.DEFAULT_EXPECTED_PAGE_ID):
        return {
            "notion_page_id": page_id,
            "repo": {"nameWithOwner": name},
            "screening_score": 81,
            "screening_reason": "test",
        }

    def _install_rows(self, pipeline, rows, pending_rows=None):
        pipeline.get_regen_test_items = lambda limit, query: list(rows)
        pipeline.get_pending_retry_items = lambda limit: list(pending_rows or [])

    def _quality_failed_payload(
        self,
        *,
        page_id=run399.DEFAULT_EXPECTED_PAGE_ID,
        name=run399.DEFAULT_EXPECTED_NAME,
        article="Not Planned",
        content="Quality Failed",
        evaluation="Deep Dive",
    ):
        def title(value):
            return {"title": [{"plain_text": value}]}

        def rich(value):
            return {"rich_text": [{"plain_text": value}]}

        def select(value):
            return {"select": {"name": value}}

        return {
            "id": page_id,
            "properties": {
                "記事名": title(name),
                "元情報URL": {"url": "https://www.rubyhack.ai/"},
                "情報源": select("HackerNews"),
                "元情報要約": rich("RubyGems incident primary-source summary"),
                "コンテンツ状態": select(content),
                "記事状態": select(article),
                "評価状態": select(evaluation),
                "選別スコア": {"number": 85},
                "選別理由": rich("AI agent supply-chain security incident"),
                "注目度": {"number": 332},
            },
        }

    def _install_quality_failed_page(self, pipeline, **kwargs):
        payload = self._quality_failed_payload(**kwargs)
        pipeline.requests = types.SimpleNamespace(get=lambda *a, **k: _Response(payload, 200))

    def _approved_env(self, **extra):
        env = {
            "ARTICLE_REVALIDATION_APPLY_CONFIRM": run399.APPROVAL_TOKEN,
            "ARTICLE_REVALIDATION_EXPECTED_NAME": run399.DEFAULT_EXPECTED_NAME,
            "ARTICLE_REVALIDATION_EXPECTED_PAGE_ID": run399.DEFAULT_EXPECTED_PAGE_ID,
        }
        env.update(extra)
        return env

    def test_refuses_without_explicit_approval(self):
        pipeline = self._pipeline()
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "approval token"):
                run399.run_approved_article_apply(pipeline)

    def test_exact_target_lookup_never_substitutes_first_other_candidate(self):
        pipeline = self._pipeline()
        self._install_rows(pipeline, [self._item("wrong target")])
        pipeline.generate_intelligence_report = lambda *a, **k: self.fail("must not generate")
        with patch.dict(os.environ, self._approved_env(), clear=True), patch.object(
            run399.article_revalidation, "_cap_validation_budget", return_value=4
        ):
            with self.assertRaisesRegex(RuntimeError, "approved page read failed"):
                run399.run_approved_article_apply(pipeline)

    def test_persists_only_exact_target_and_requires_accepted(self):
        pipeline = self._pipeline()
        self._install_rows(pipeline, [self._item("other"), self._item()])
        calls = []

        def generate(repo, **kwargs):
            calls.append((repo, kwargs))
            return ("published-quality manuscript", "accepted")

        pipeline.generate_intelligence_report = generate
        with patch.dict(os.environ, self._approved_env(), clear=True), patch.object(
            run399.article_revalidation, "_cap_validation_budget", return_value=4
        ), patch.object(
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
        self.assertEqual(calls[0][1]["notion_page_id"], run399.DEFAULT_EXPECTED_PAGE_ID)
        self.assertFalse(result["pending_continuation"])

    def test_exact_owner_approved_pending_retry_can_continue_from_canonical_pending_source(self):
        pipeline = self._pipeline()
        self._install_rows(pipeline, [self._item("other")], pending_rows=[self._item()])
        calls = []
        pipeline.generate_intelligence_report = lambda repo, **kwargs: calls.append((repo, kwargs)) or ("draft", "accepted")
        with patch.dict(os.environ, self._approved_env(), clear=True), patch.object(
            run399.article_revalidation, "_cap_validation_budget", return_value=5
        ), patch.object(
            run399.article_revalidation,
            "_read_current_statuses",
            return_value=("Needs Editorial Review", "Pending Retry"),
        ):
            result = run399.run_approved_article_apply(pipeline)

        self.assertTrue(result["pending_continuation"])
        self.assertEqual(result["target_source"], "pending_retry")
        self.assertEqual(len(calls), 1)

    def test_same_page_seen_in_both_sources_is_deduplicated(self):
        pipeline = self._pipeline()
        self._install_rows(pipeline, [self._item()], pending_rows=[self._item()])
        selected = run399._select_exact_approved_target(
            pipeline, run399.DEFAULT_EXPECTED_NAME, run399.DEFAULT_EXPECTED_PAGE_ID
        )
        self.assertEqual(selected["notion_page_id"], run399.DEFAULT_EXPECTED_PAGE_ID)
        self.assertEqual(selected["approved_target_source"], "deep_dive")

    def test_duplicate_exact_target_different_pages_fails_closed_before_generation(self):
        pipeline = self._pipeline()
        self._install_rows(
            pipeline,
            [self._item(page_id="page-1")],
            pending_rows=[self._item(page_id="page-2")],
        )
        pipeline.generate_intelligence_report = lambda *a, **k: self.fail("must not generate")
        env = self._approved_env(ARTICLE_REVALIDATION_EXPECTED_PAGE_ID="page-1")
        with patch.dict(os.environ, env, clear=True), patch.object(
            run399.article_revalidation, "_cap_validation_budget", return_value=5
        ):
            # page-2 is explicitly outside the approval boundary; page-1 is the only valid target.
            with patch.object(
                run399.article_revalidation,
                "_read_current_statuses",
                return_value=("Needs Editorial Review", "Deep Dive"),
            ):
                pipeline.generate_intelligence_report = lambda *a, **k: ("draft", "accepted")
                result = run399.run_approved_article_apply(pipeline)
        self.assertEqual(result["notion_page_id"], "page-1")

    def test_pending_lifecycle_from_non_pending_source_fails_closed(self):
        pipeline = self._pipeline()
        self._install_rows(pipeline, [self._item()])
        pipeline.generate_intelligence_report = lambda *a, **k: self.fail("must not generate")
        with patch.dict(os.environ, self._approved_env(), clear=True), patch.object(
            run399.article_revalidation, "_cap_validation_budget", return_value=5
        ), patch.object(
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
        with patch.dict(os.environ, self._approved_env(), clear=True), patch.object(
            run399.article_revalidation, "_cap_validation_budget", return_value=4
        ), patch.object(
            run399.article_revalidation,
            "_read_current_statuses",
            return_value=("Needs Editorial Review", "Deep Dive"),
        ):
            with self.assertRaisesRegex(RuntimeError, "did not pass"):
                run399.run_approved_article_apply(pipeline)

    def test_run410_exact_quality_failed_page_is_reconstructed_and_applied(self):
        pipeline = self._pipeline()
        self._install_rows(pipeline, [])
        self._install_quality_failed_page(pipeline)
        calls = []
        pipeline.generate_intelligence_report = lambda repo, **kwargs: calls.append((repo, kwargs)) or ("draft", "accepted")
        with patch.dict(os.environ, self._approved_env(), clear=True), patch.object(
            run399.article_revalidation, "_cap_validation_budget", return_value=5
        ), patch.object(
            run399.article_revalidation,
            "_read_current_statuses",
            return_value=("Not Planned", "Quality Failed"),
        ):
            result = run399.run_approved_article_apply(pipeline)

        self.assertEqual(result["target_source"], "quality_failed_exact")
        self.assertTrue(result["quality_failed_continuation"])
        self.assertEqual(result["notion_page_id"], run399.DEFAULT_EXPECTED_PAGE_ID)
        self.assertEqual(calls[0][0]["html_url"], "https://www.rubyhack.ai/")
        self.assertEqual(calls[0][1]["screening_score"], 85)

    def test_run410_wrong_live_page_id_fails_closed(self):
        pipeline = self._pipeline()
        self._install_rows(pipeline, [])
        self._install_quality_failed_page(pipeline, page_id="different-page")
        with self.assertRaisesRegex(RuntimeError, "page id mismatch"):
            run399._select_exact_approved_target(
                pipeline, run399.DEFAULT_EXPECTED_NAME, run399.DEFAULT_EXPECTED_PAGE_ID
            )

    def test_run410_wrong_live_title_fails_closed(self):
        pipeline = self._pipeline()
        self._install_rows(pipeline, [])
        self._install_quality_failed_page(pipeline, name="different article")
        with self.assertRaisesRegex(RuntimeError, "title mismatch"):
            run399._select_exact_approved_target(
                pipeline, run399.DEFAULT_EXPECTED_NAME, run399.DEFAULT_EXPECTED_PAGE_ID
            )

    def test_run410_ready_page_fails_closed(self):
        pipeline = self._pipeline()
        self._install_rows(pipeline, [])
        self._install_quality_failed_page(pipeline, article="Ready")
        with self.assertRaisesRegex(RuntimeError, "already Ready"):
            run399._select_exact_approved_target(
                pipeline, run399.DEFAULT_EXPECTED_NAME, run399.DEFAULT_EXPECTED_PAGE_ID
            )

    def test_run410_non_quality_failed_exact_page_is_not_substituted(self):
        pipeline = self._pipeline()
        self._install_rows(pipeline, [self._item(run399.DEFAULT_EXPECTED_NAME, "unapproved-page")])
        self._install_quality_failed_page(pipeline, content="Stocked")
        with self.assertRaisesRegex(RuntimeError, "matches=0"):
            run399._select_exact_approved_target(
                pipeline, run399.DEFAULT_EXPECTED_NAME, run399.DEFAULT_EXPECTED_PAGE_ID
            )

    def test_run410_wrong_evaluation_state_fails_closed(self):
        pipeline = self._pipeline()
        self._install_rows(pipeline, [])
        self._install_quality_failed_page(pipeline, evaluation="Screening")
        with self.assertRaisesRegex(RuntimeError, "not Deep Dive"):
            run399._select_exact_approved_target(
                pipeline, run399.DEFAULT_EXPECTED_NAME, run399.DEFAULT_EXPECTED_PAGE_ID
            )


if __name__ == "__main__":
    unittest.main()
