import contextlib
import types
import unittest
from unittest.mock import MagicMock

import run172_production_reliability as run172
import run260_gemini_model_routing as run260


class FakeAPIError(Exception):
    def __init__(self, code):
        super().__init__(f"HTTP {code}")
        self.code = code


class FakeBudget:
    def can_request(self):
        return True

    def summary(self):
        return "ok"


class Run278QualityRetryBudgetGuardTests(unittest.TestCase):
    def _pipeline(self):
        p = None

        def base_pool(*args, **kwargs):
            raise AssertionError("Run172 should own the live pool caller after install")

        def base_deep_dive(prompt, config=None, kind="deep_dive", request_context="", request_origin="new"):
            return p._call_model_pool(
                prompt,
                config,
                kind,
                0,
                p.DEEP_DIVE_MODEL_POOL,
                deep_dive=True,
                request_context=request_context,
                request_origin=request_origin,
            )

        persistent = types.SimpleNamespace(model_budgets={})
        p = types.SimpleNamespace(
            _call_model_pool=base_pool,
            _call_deep_dive_pool=base_deep_dive,
            DEEP_DIVE_MODEL_POOL=[
                "gemini-3.7-flash",
                "gemini-3.8-flash",
                "gemini-3.6-flash",
                "gemini-3.5-flash",
            ],
            DEEP_DIVE_MODEL_CANDIDATES=[],
            MODEL_DAILY_BUDGETS={
                "gemini-3.7-flash": 18,
                "gemini-3.8-flash": 18,
                "gemini-3.6-flash": 18,
                "gemini-3.5-flash": 18,
            },
            PERSISTENT_GEMINI_COUNTER=persistent,
            build_notion_properties=lambda *a, **k: {},
            prepare_source_context=lambda repo: {
                "context": "generic documentation",
                "verification_context": "generic documentation",
                "primary_url": repo.get("primaryUrl", ""),
                "primary_source_resolved": True,
                "primary_fetch_failed": False,
                "checked_urls": set(),
                "deep_source_urls": [],
                "supplement_candidates": [],
                "evidence_supplement_attempted": False,
            },
            assess_evidence_sufficiency=lambda info: {
                "state": "SUFFICIENT",
                "sufficiency": "SUFFICIENT",
                "decision_scope_safe": True,
                "blocking_missing": [],
            },
            _parse_gemini_response=lambda text: {},
            build_decision_prompt=lambda *a, **k: str(k.get("source_context") or ""),
            build_dynamic_retry_instruction=lambda rows: ("base repair", {"article"}),
            human_appeal_materially_degraded=lambda before, after: False,
            publication_probability_score=lambda item: 50,
            PROP_EYECATCH="アイキャッチ",
            _normalize_decision=lambda x: x.strip().upper(),
            VERIFICATION_CONTEXT_MAX_CHARS=180000,
            EVIDENCE_SUPPLEMENT_REQUIRED="SUPPLEMENT_REQUIRED",
            EVIDENCE_INSUFFICIENT="INSUFFICIENT",
            GH_PAT="",
            requests=types.SimpleNamespace(get=MagicMock()),
            logger=MagicMock(),
            SESSION_EXHAUSTED_MODELS=set(),
            SESSION_UNAVAILABLE_MODELS=set(),
            GEMINI_DEEP_DIVE_CALL_PACING_SECONDS=0,
            GEMINI_DEEP_DIVE_CALL_TIMEOUT_SECONDS=1,
            GEMINI_SCREENING_CALL_TIMEOUT_SECONDS=1,
            _gemini_call_timeout=lambda seconds: contextlib.nullcontext(),
            _generate_via_chat=lambda *a, **k: "ok",
            APIError=FakeAPIError,
            classify_gemini_quota_error=lambda exc: "",
            _mark_model_exhausted=lambda model, why: p.SESSION_EXHAUSTED_MODELS.add(model),
            _mark_model_unavailable=lambda model, why: p.SESSION_UNAVAILABLE_MODELS.add(model),
            _extract_retry_delay=lambda exc, default: 0,
            GeminiBudgetExceededError=type("GeminiBudgetExceededError", (Exception,), {}),
            GeminiCallTimeoutError=type("GeminiCallTimeoutError", (Exception,), {}),
            _is_gemini_transport_timeout=lambda exc: False,
            NoAvailableModelError=type("NoAvailableModelError", (Exception,), {}),
            PRODUCT_REVIEW_REQUEST_BUDGET=FakeBudget(),
            ProductReviewBudgetExceededError=type("ProductReviewBudgetExceededError", (Exception,), {}),
            _PRODUCT_REVIEW_RESPONSE_SCHEMA={"type": "object"},
            SECTION_SPLIT_TOKEN="===NOTE_DRAFT_START===",
        )
        return p

    def _install_live_order(self, p):
        run260.install(p)
        run172.install(p)
        return p

    def test_all_503_quality_retry_stops_after_two_distinct_models_in_live_order(self):
        p = self._install_live_order(self._pipeline())
        calls = []

        def generate(model, prompt, **kwargs):
            calls.append((model, kwargs.get("request_kind")))
            raise FakeAPIError(503)

        p._generate_via_chat = generate
        with self.assertRaises(p.NoAvailableModelError):
            p._call_deep_dive_pool(
                "repair",
                None,
                "quality_retry",
                request_context="run278-live",
                request_origin="new",
            )
        self.assertEqual(
            calls,
            [
                ("gemini-3.8-flash", "quality_retry"),
                ("gemini-3.6-flash", "quality_retry"),
            ],
        )

    def test_second_model_can_rescue_quality_retry(self):
        p = self._install_live_order(self._pipeline())
        calls = []

        def generate(model, prompt, **kwargs):
            calls.append(model)
            if model == "gemini-3.8-flash":
                raise FakeAPIError(503)
            return "repaired"

        p._generate_via_chat = generate
        response, model = p._call_deep_dive_pool("repair", None, "quality_retry")
        self.assertEqual((response, model), ("repaired", "gemini-3.6-flash"))
        self.assertEqual(calls, ["gemini-3.8-flash", "gemini-3.6-flash"])

    def test_fresh_deep_dive_keeps_four_model_failure_tolerance(self):
        p = self._install_live_order(self._pipeline())
        calls = []

        def generate(model, prompt, **kwargs):
            calls.append(model)
            if model != "gemini-3.5-flash":
                raise FakeAPIError(503)
            return "fresh-ok"

        p._generate_via_chat = generate
        response, model = p._call_deep_dive_pool("fresh", None, "deep_dive")
        self.assertEqual((response, model), ("fresh-ok", "gemini-3.5-flash"))
        self.assertEqual(
            calls,
            [
                "gemini-3.7-flash",
                "gemini-3.8-flash",
                "gemini-3.6-flash",
                "gemini-3.5-flash",
            ],
        )

    def test_existing_session_cooldown_is_still_authoritative_inside_bounded_pool(self):
        p = self._install_live_order(self._pipeline())
        p.SESSION_UNAVAILABLE_MODELS.add("gemini-3.8-flash")
        calls = []

        def generate(model, prompt, **kwargs):
            calls.append(model)
            return "ok"

        p._generate_via_chat = generate
        response, model = p._call_deep_dive_pool("repair", None, "quality_retry")
        self.assertEqual((response, model), ("ok", "gemini-3.6-flash"))
        self.assertEqual(calls, ["gemini-3.6-flash"])


if __name__ == "__main__":
    unittest.main()
