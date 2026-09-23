from __future__ import annotations

import contextlib
import types
from datetime import datetime, timezone
import unittest
from unittest.mock import MagicMock, patch

import run172_production_reliability as run172
import run260_gemini_model_routing as run260


class FakeAPIError(Exception):
    def __init__(self, code):
        super().__init__(f"HTTP {code}")
        self.code = code


class Run370ProviderHealthLiveRegressionTests(unittest.TestCase):
    def _pipeline(self):
        p = None
        audit = types.SimpleNamespace(records=[])

        def base_pool(*args, **kwargs):
            raise AssertionError("Run172 should replace the live provider pool")

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

        p = types.SimpleNamespace(
            _call_model_pool=base_pool,
            _call_deep_dive_pool=base_deep_dive,
            DEEP_DIVE_MODEL_POOL=[
                "gemini-3.6-flash",
                "gemini-3.5-flash",
                "gemini-3.7-flash",
                "gemini-3.8-flash",
            ],
            DEEP_DIVE_MODEL_CANDIDATES=[],
            MODEL_DAILY_BUDGETS={model: 18 for model in run260.DEFAULT_DEEP_DIVE_POOL},
            PERSISTENT_GEMINI_COUNTER=types.SimpleNamespace(model_budgets={}),
            PROVIDER_HEALTH_HISTORY_OVERRIDE=[],
            GEMINI_USAGE_AUDIT=audit,
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
            APIError=FakeAPIError,
            classify_gemini_quota_error=lambda exc: "",
            _mark_model_exhausted=lambda model, why: p.SESSION_EXHAUSTED_MODELS.add(model),
            _mark_model_unavailable=lambda model, why: p.SESSION_UNAVAILABLE_MODELS.add(model),
            _extract_retry_delay=lambda exc, default: 0,
            GeminiBudgetExceededError=type("GeminiBudgetExceededError", (Exception,), {}),
            GeminiCallTimeoutError=type("GeminiCallTimeoutError", (Exception,), {}),
            _is_gemini_transport_timeout=lambda exc: False,
            NoAvailableModelError=type("NoAvailableModelError", (Exception,), {}),
            PRODUCT_REVIEW_REQUEST_BUDGET=types.SimpleNamespace(can_request=lambda: True),
            ProductReviewBudgetExceededError=type("ProductReviewBudgetExceededError", (Exception,), {}),
            _PRODUCT_REVIEW_RESPONSE_SCHEMA={"type": "object"},
            SECTION_SPLIT_TOKEN="===NOTE_DRAFT_START===",
        )
        return p

    def test_run172_replacement_still_uses_health_ranked_live_pool(self):
        p = self._pipeline()
        run260.install(p)
        run172.install(p)

        # 3.7 is the healthiest known model; Run172 must not erase that ordering.
        now = datetime.now(timezone.utc).isoformat()
        p._provider_health_history = [
            {
                "timestamp": now,
                "model": "gemini-3.7-flash",
                "kind": "deep_dive",
                "outcome": "success",
                "error_type": "",
            },
            {
                "timestamp": now,
                "model": "gemini-3.6-flash",
                "kind": "deep_dive",
                "outcome": "error",
                "error_type": "ServiceUnavailable",
            },
        ]
        calls = []

        def sender(model, prompt, **kwargs):
            calls.append(model)
            return "ok"

        p._generate_via_chat = sender
        with patch.object(run260, "_persist_provider_health_history"):
            response, model = p._call_deep_dive_pool("prompt", None, "deep_dive")
        self.assertEqual((response, model), ("ok", "gemini-3.7-flash"))
        self.assertEqual(calls, ["gemini-3.7-flash"])

    def test_run57_open_circuits_are_filtered_before_two_model_quality_bound(self):
        p = self._pipeline()
        run260.install(p)
        run172.install(p)
        p._provider_health_history = [
            {
                "timestamp": "2026-09-15T10:00:00+00:00",
                "model": "gemini-3.6-flash",
                "kind": "deep_dive",
                "outcome": "success",
                "error_type": "",
            },
            {
                "timestamp": "2026-09-15T10:00:01+00:00",
                "model": "gemini-3.7-flash",
                "kind": "deep_dive",
                "outcome": "success",
                "error_type": "",
            },
        ]
        p.SESSION_UNAVAILABLE_MODELS.update({"gemini-3.6-flash", "gemini-3.5-flash"})
        calls = []

        def sender(model, prompt, **kwargs):
            calls.append(model)
            return "repair-ok"

        p._generate_via_chat = sender
        with patch.object(run260, "_persist_provider_health_history"):
            response, model = p._call_deep_dive_pool("repair", None, "quality_retry")
        self.assertEqual((response, model), ("repair-ok", "gemini-3.7-flash"))
        self.assertEqual(calls, ["gemini-3.7-flash"])
        self.assertNotIn("gemini-3.6-flash", calls)
        self.assertNotIn("gemini-3.5-flash", calls)


if __name__ == "__main__":
    unittest.main()
