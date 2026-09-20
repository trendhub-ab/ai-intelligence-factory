import ast
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import gemini_temporary_exclusion as policy
import run260_gemini_model_routing as routing
import article_revalidation
import ready_rescue_validation
from tests.test_gemini_provider_resilience import make_pipeline, FakeAPIError


class TemporaryExclusionTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {policy.ENV: "2099-09-16T17:00:00+09:00"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_operator_exclusion_blocks_35_without_permanently_removing_other_models(self):
        with patch.dict(os.environ, {policy.EXCLUDED_MODELS_ENV: "gemini-3.5-flash", policy.ENV: ""}):
            pool = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.8-flash"]
            self.assertEqual(policy.allowed_pool(pool), pool[1:])
            self.assertTrue(policy.excluded("models/gemini-3.5-flash"))
            self.assertFalse(policy.excluded("gemini-3.6-flash"))
        with patch.dict(os.environ, {policy.EXCLUDED_MODELS_ENV: "", policy.ENV: ""}):
            self.assertFalse(policy.excluded("gemini-3.5-flash"))

    def test_expiry_boundary_and_no_permanent_exclusion(self):
        deadline = datetime(2026, 9, 16, 8, tzinfo=timezone.utc)
        with patch.dict(os.environ, {policy.ENV: "2026-09-16T17:00:00+09:00"}):
            self.assertTrue(policy.excluded("gemini-3.6-flash", deadline.replace(hour=7)))
            self.assertFalse(policy.excluded("gemini-3.6-flash", deadline))
        with patch.dict(os.environ, {policy.ENV: ""}):
            self.assertFalse(policy.excluded("gemini-3.6-flash"))
        for value in ("broken", "2026-09-16T17:00:00"):
            with patch.dict(os.environ, {policy.ENV: value}), self.assertRaises(RuntimeError):
                policy.allowed_pool([])

    def test_ready_rescue_restores_36_exactly_at_deadline(self):
        deadline = datetime(2026, 9, 16, 8, tzinfo=timezone.utc)
        pool = [
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-3.7-flash",
            "gemini-3.8-flash",
        ]
        with patch.dict(os.environ, {policy.ENV: "2026-09-16T17:00:00+09:00"}):
            before = ready_rescue_validation.validation_pool(pool, now=deadline.replace(hour=7, minute=59))
            at_deadline = ready_rescue_validation.validation_pool(pool, now=deadline)
        self.assertNotIn("gemini-3.6-flash", before)
        self.assertEqual(at_deadline, pool)

    def sender(self):
        # Execute the actual production sender body with a fake SDK and quota ledger.
        tree = ast.parse(Path("pipeline.py").read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_generate_via_chat")
        sdk = Mock()
        ledger = Mock(return_value=1)
        scope = dict(client=sdk, _consume_gemini_request=ledger, GEMINI_USAGE_AUDIT=Mock(),
                     NoAvailableModelError=RuntimeError, DeepDiveRunBudgetExceededError=RuntimeError)
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "pipeline.py", "exec"), scope)
        return scope, sdk, ledger

    def test_real_sender_blocks_aliases_before_reservation_for_every_kind(self):
        scope, sdk, ledger = self.sender()
        for kind in ("deep_dive", "quality_retry", "reader_repair", "ready_rescue", "product_review", "product_review_retry", "ping", "eyecatch_layout"):
            for model in ("gemini-3.6-flash", "models/GEMINI-3.6-FLASH", "gemini-3.6-flash-latest", "gemini-3.6-flash-preview"):
                with self.subTest(kind=kind, model=model), self.assertRaisesRegex(RuntimeError, "temporarily excluded"):
                    scope["_generate_via_chat"](model, "p", request_kind=kind)
        sdk.chats.create.assert_not_called()
        ledger.assert_not_called()
        for model in ("gemini-3.5-flash", "gemini-3.7-flash", "gemini-3.8-flash"):
            scope["_generate_via_chat"](model, "p")
        self.assertEqual(ledger.call_count, 3)

    def test_real_sender_allows_36_after_expiry(self):
        scope, sdk, ledger = self.sender()
        with patch.dict(os.environ, {policy.ENV: "2020-09-16T17:00:00+09:00"}):
            scope["_generate_via_chat"]("gemini-3.6-flash", "p", request_kind="ready_rescue")
        self.assertEqual(ledger.call_count, 1)
        self.assertEqual(sdk.chats.create.call_count, 1)

    def test_rescue_sender_cap_also_blocks_non_deep_dive_repairs(self):
        scope, sdk, ledger = self.sender()
        scope.update(_READY_RESCUE_ACTIVE=True, _READY_RESCUE_PROVIDER_SENDS=0)
        scope["_generate_via_chat"]("gemini-3.5-flash", "p")
        with self.assertRaisesRegex(RuntimeError, "one provider send"):
            scope["_generate_via_chat"]("gemini-3.7-flash", "p", request_kind="eyecatch_layout")
        self.assertEqual(ledger.call_count, 1)
        self.assertEqual(sdk.chats.create.call_count, 1)

    def test_routing_reinjection_quality_and_fallback_exclude_before_limits(self):
        p, calls, *_ = make_pipeline([FakeAPIError("503", code=503), "ok"])
        p._call_deep_dive_pool = Mock()
        p.logger = Mock()
        p.PROVIDER_HEALTH_HISTORY_OVERRIDE = []
        routing.install(p)
        self.assertNotIn("gemini-3.6-flash", p.DEEP_DIVE_MODEL_POOL)
        self.assertNotIn("gemini-3.6-flash", p.DEEP_DIVE_MODEL_CANDIDATES)
        with patch("gemini_provider_resilience.time.sleep"):
            p._call_deep_dive_pool("p", kind="quality_retry")
        self.assertEqual([c[0] for c in calls], ["gemini-3.5-flash", "gemini-3.7-flash"])

    def test_product_review_independent_pool_filters_36(self):
        p, calls, *_ = make_pipeline(["ok"])
        p.DEEP_DIVE_MODEL_POOL = ["models/gemini-3.6-flash-latest", "gemini-3.5-flash"]
        with patch("gemini_provider_resilience.time.sleep"):
            p._call_product_review_pool("p", "test")
        self.assertEqual([c[0] for c in calls], ["gemini-3.5-flash"])

    def test_rescue_503_never_confirms_or_falls_back(self):
        p, calls, *_ = make_pipeline([FakeAPIError("503", code=503), "must not send"])
        p._READY_RESCUE_ACTIVE = True
        with patch("gemini_provider_resilience.time.sleep"), self.assertRaisesRegex(p.NoAvailableModelError, "no retry or fallback"):
            p._call_model_pool("p", None, "deep_dive", 0,
                               ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.7-flash"], deep_dive=True)
        self.assertEqual([c[0] for c in calls], ["gemini-3.5-flash"])

    def test_mixed_quality_failed_and_editorial_status_is_ineligible(self):
        p = SimpleNamespace(get_regen_test_items=lambda *a: [{"notion_page_id": "x"}],
                            ARTICLE_STATUS_READY="Ready", CONTENT_STATUS_PENDING_RETRY="Pending Retry",
                            CONTENT_STATUS_QUALITY_FAILED="Quality Failed",
                            ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW="Needs Editorial Review")
        for status in ("Quality Failed", "Pending Retry"):
            with patch.object(article_revalidation, "_read_current_statuses", return_value=("Needs Editorial Review", status)):
                self.assertEqual(article_revalidation.select_revalidation_items(p, include_quality_failed=False), [])

    def test_pending_retry_fast_lane_still_blocks_36_while_exclusion_is_active(self):
        import pending_retry_validation as fast_lane

        p, calls, *_ = make_pipeline(["must not send"])
        p.logger = Mock()
        p.DEEP_DIVE_MODEL_POOL = ["gemini-3.6-flash", "gemini-3.5-flash"]
        p.DEEP_DIVE_MODEL_CANDIDATES = list(p.DEEP_DIVE_MODEL_POOL)
        p.SCREENING_MODEL_POOL = ["gemini-3.5-flash-lite"]
        p.SESSION_UNAVAILABLE_MODELS = set()
        fast_lane.install_validation_model_exclusions(p)
        self.assertNotIn("gemini-3.6-flash", p.DEEP_DIVE_MODEL_POOL)
        self.assertIn("gemini-3.6-flash", p.SESSION_UNAVAILABLE_MODELS)
        with self.assertRaisesRegex(p.NoAvailableModelError, "temporarily excluded"):
            p._generate_via_chat("gemini-3.6-flash", "p")
        self.assertEqual(calls, [])
    def test_pending_retry_fast_lane_restores_36_after_temporary_exclusion_expiry(self):
        import pending_retry_validation as fast_lane

        p, calls, *_ = make_pipeline(["ok"])
        p.logger = Mock()
        p.DEEP_DIVE_MODEL_POOL = ["gemini-3.6-flash", "gemini-3.5-flash"]
        p.DEEP_DIVE_MODEL_CANDIDATES = list(p.DEEP_DIVE_MODEL_POOL)
        p.SCREENING_MODEL_POOL = ["gemini-3.5-flash-lite"]
        p.SESSION_UNAVAILABLE_MODELS = set()
        with patch.dict(os.environ, {policy.ENV: "2020-09-16T17:00:00+09:00"}):
            fast_lane.install_validation_model_exclusions(p)
            self.assertIn("gemini-3.6-flash", p.DEEP_DIVE_MODEL_POOL)
            self.assertNotIn("gemini-3.6-flash", p.SESSION_UNAVAILABLE_MODELS)
            p._generate_via_chat("gemini-3.6-flash", "p")
        self.assertEqual([c[0] for c in calls], ["gemini-3.6-flash"])

    def test_pending_retry_workflow_does_not_permanently_zero_or_remove_36(self):
        text = Path(".github/workflows/daily-one-shot.yml").read_text()
        start = text.index("      - name: Pending Retry fast laneを1回だけ実行")
        end = text.index("      - name: Portfolio-aware Product Review", start)
        block = text[start:end]
        self.assertIn('GEMINI_36_FLASH_DAILY_BUDGET: "18"', block)
        self.assertIn('GEMINI_DEEP_DIVE_MODEL_CANDIDATES: "gemini-3.8-flash,gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash"', block)
        self.assertNotIn('GEMINI_36_FLASH_DAILY_BUDGET: "0"', block)

    def test_workflow_has_no_expired_gemini36_block_and_rescue_is_explicit(self):
        text = Path(".github/workflows/daily-one-shot.yml").read_text()
        self.assertNotIn("AIIF_GEMINI36_BLOCK_UNTIL", text)
        import run202_chatops_control as chatops
        self.assertEqual(chatops.COMMAND_TO_MODE.get("/aiif run ready_rescue_validation"), "ready_rescue_validation")


if __name__ == "__main__":
    unittest.main()
