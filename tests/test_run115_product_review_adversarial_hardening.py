import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMINI_DEEP_DIVE_CALL_PACING_SECONDS", "0")

try:
    import google.genai  # noqa: F401
except Exception:
    import types
    google_pkg = sys.modules.get("google") or types.ModuleType("google")
    google_pkg.__path__ = getattr(google_pkg, "__path__", [])
    genai_mod = types.ModuleType("google.genai")
    errors_mod = types.ModuleType("google.genai.errors")
    class _Client:
        def __init__(self, *a, **k): self.chats = MagicMock()
    class _APIError(Exception):
        def __init__(self, *a, code=None, **k): super().__init__(*a); self.code = code
    genai_mod.Client = _Client
    errors_mod.APIError = _APIError
    google_pkg.genai = genai_mod
    sys.modules["google"] = google_pkg
    sys.modules["google.genai"] = genai_mod
    sys.modules["google.genai.errors"] = errors_mod

import pipeline


def review_payload(**overrides):
    payload = {
        "category": "DEVTOOLS",
        "adoption_score": 80,
        "components": {
            "Evidence Quality": 20,
            "Production Maturity": 20,
            "Use-case Utility / Fit": 16,
            "Reliability / Security Risk": 12,
            "Integration / Migration Feasibility": 8,
            "Ecosystem / Support Durability": 4,
        },
        "adoption_status": "TEST",
        "evidence_confidence": "HIGH",
        "production_readiness": "HIGH",
        "main_risk": "導入前に互換性を検証する必要がある。",
        "best_for": "開発チームの実験環境。",
        "avoid_for": "検証なしの全面移行。",
        "short_rationale": "一次情報で主要機能を確認できる。",
        "next_review_days": 30,
    }
    payload.update(overrides)
    return payload


class _SequenceChat:
    def __init__(self, queue): self.queue = queue
    def send_message(self, _prompt):
        if not self.queue:
            raise AssertionError("unexpected extra provider request")
        return SimpleNamespace(text=self.queue.pop(0), parsed=None, usage_metadata=None)


class _SequenceChats:
    def __init__(self, queue): self.queue = queue
    def create(self, **_kwargs): return _SequenceChat(self.queue)


class _SequenceClient:
    def __init__(self, responses):
        self.queue = list(responses)
        self.chats = _SequenceChats(self.queue)


class Run115ProductReviewAdversarialHardeningTests(unittest.TestCase):
    def _source_state(self):
        return {
            "canonical_entity_id": "github:org/tool", "technology_name": "org/tool",
            "primary_url": "https://github.com/org/tool", "sources": ["GitHub"],
            "screening_score": 80, "screening_reason": "test", "source_summary": "legacy",
        }

    def _source_info(self):
        return {
            "context": "verified first-party implementation limitation evidence",
            "verification_context": "verified first-party implementation limitation evidence",
            "source": "GitHub", "evidence_documents": [], "checked_urls": set(), "deep_source_urls": [],
        }

    def _evidence(self):
        return {"state": pipeline.EVIDENCE_SUFFICIENT, "decision_scope_safe": True, "blocking_missing": []}

    def test_semantic_schema_rejects_missing_unknown_extra_range_and_sum_errors(self):
        cases = []
        missing = review_payload(); missing.pop("main_risk"); cases.append(("missing", missing, "missing_fields"))
        unknown = review_payload(category="GARBAGE"); cases.append(("unknown category", unknown, "category invalid"))
        extra = review_payload(); extra["invented"] = "x"; cases.append(("extra", extra, "unexpected_fields"))
        missing_component = review_payload(); missing_component["components"] = dict(missing_component["components"]); missing_component["components"].pop("Evidence Quality"); cases.append(("component missing", missing_component, "components_keys"))
        range_error = review_payload(); range_error["components"] = dict(range_error["components"]); range_error["components"]["Evidence Quality"] = 26; cases.append(("component range", range_error, "out_of_range"))
        mismatch = review_payload(adoption_score=79); cases.append(("sum mismatch", mismatch, "sum_mismatch"))
        bool_score = review_payload(adoption_score=True); cases.append(("bool score", bool_score, "must be integer"))
        blank = review_payload(main_risk="   "); cases.append(("blank text", blank, "non-empty string"))
        bad_days = review_payload(next_review_days=61); cases.append(("review range", bad_days, "out_of_range"))
        for label, payload, marker in cases:
            with self.subTest(label=label):
                with self.assertRaisesRegex(ValueError, marker):
                    pipeline._parse_product_review_response(payload)

    def test_invalid_category_is_not_silently_coerced_to_other(self):
        with self.assertRaisesRegex(ValueError, "category invalid"):
            pipeline._parse_product_review_response(review_payload(category="GARBAGE"))

    def test_provider_parsed_semantic_failure_is_rejected_before_text_fallback(self):
        response = SimpleNamespace(parsed=review_payload(category="INVALID"), text=json.dumps(review_payload()))
        with self.assertRaisesRegex(ValueError, "category invalid"):
            pipeline._parse_product_review_model_response(response)

    def test_prompt_does_not_duplicate_json_schema_contract(self):
        prompt = pipeline._product_review_prompt(
            {"nameWithOwner": "org/tool", "url": "https://github.com/org/tool"},
            {"context": "verified"}, {},
        )
        self.assertNotIn("keys:", prompt)
        self.assertNotIn("MODEL/AGENT/DEVTOOLS", prompt)
        self.assertNotIn("WATCH/TEST/ADOPT/AVOID", prompt)
        self.assertNotIn("next_review_daysは7〜60", prompt)
        # Decision semantics that cannot be expressed by JSON Schema must remain.
        self.assertIn("componentsの合計と必ず一致", prompt)
        self.assertIn("ADOPT", prompt)

    def test_redirect_final_url_to_third_party_is_rejected_even_if_body_contains_fact(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/start":
                    self.send_response(302)
                    self.send_header("Location", f"http://localhost:{self.server.server_port}/evil")
                    self.end_headers()
                    return
                if self.path == "/evil":
                    body = b"<html><body>MLflow Tracking provides APIs and UI.</body></html>"
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers(); self.wfile.write(body); return
                self.send_response(404); self.end_headers()
            def log_message(self, *_args): pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            seed = f"http://127.0.0.1:{server.server_port}/start"
            source_info = {
                "source": "GitHub", "primary_url": "https://github.com/org/tool",
                "source_details": {"homepage": seed},
                "supplement_candidates": [{"url": seed, "role": "PRIMARY_SOURCE"}],
                "verification_context": "Tool docs", "context": "Tool docs",
                "checked_urls": set(), "evidence_documents": [], "deep_source_urls": [],
            }
            # The production URL validator correctly blocks loopback; disable only that SSRF guard
            # so this local server can exercise the *separate* first-party redirect invariant.
            with patch.object(pipeline, "_validate_public_http_url", return_value=None):
                result = pipeline.reconcile_product_review_source_boundary(
                    {}, source_info, ["source-boundary unsupported named fact: MLflow Tracking"]
                )
            self.assertFalse(result["resolved"])
            self.assertEqual([], source_info["deep_source_urls"])
            self.assertEqual([], source_info["evidence_documents"])
            rejected = source_info.get("boundary_rejected_urls") or []
            self.assertEqual(1, len(rejected))
            self.assertIn("localhost", rejected[0]["final_url"])
            self.assertEqual("redirect_outside_first_party", rejected[0]["reason"])
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)

    def test_same_host_redirect_result_remains_eligible(self):
        source_info = {
            "source": "GitHub", "primary_url": "https://github.com/org/tool",
            "source_details": {"homepage": "https://tool.example/docs"},
            "supplement_candidates": [{"url": "https://tool.example/docs", "role": "PRIMARY_SOURCE"}],
            "verification_context": "Tool docs", "context": "Tool docs",
            "checked_urls": set(), "evidence_documents": [], "deep_source_urls": [],
        }
        with patch.object(pipeline, "_fetch_boundary_html", return_value=(
            "MLflow Tracking provides APIs.", [], "https://tool.example/docs/tracking"
        )):
            result = pipeline.reconcile_product_review_source_boundary(
                {}, source_info, ["source-boundary unsupported named fact: MLflow Tracking"]
            )
        self.assertTrue(result["resolved"])
        self.assertEqual(["https://tool.example/docs/tracking"], source_info["deep_source_urls"])

    def test_semantic_schema_failure_gets_one_retry_and_real_budget_consumes_two(self):
        bad = review_payload(); bad.pop("main_risk")
        client = _SequenceClient([json.dumps(bad, ensure_ascii=False), json.dumps(review_payload(), ensure_ascii=False)])
        pr_budget = pipeline.ProductReviewRequestBudget(2)
        global_budget = pipeline.GeminiBudget(10, 2, 2)
        with patch.object(pipeline, "PRODUCT_REVIEW_MAX_PER_RUN", 1), \
             patch.object(pipeline, "select_product_review_candidates", return_value=[self._source_state()]), \
             patch.object(pipeline, "prepare_source_context", return_value=self._source_info()), \
             patch.object(pipeline, "assess_evidence_sufficiency", return_value=self._evidence()), \
             patch.object(pipeline, "_primary_source_authority_failures", return_value=[]), \
             patch.object(pipeline, "DEEP_DIVE_MODEL_POOL", ["gemini-test"]), \
             patch.object(pipeline, "SESSION_EXHAUSTED_MODELS", set()), \
             patch.object(pipeline, "SESSION_UNAVAILABLE_MODELS", set()), \
             patch.object(pipeline, "GEMINI_DEEP_DIVE_CALL_PACING_SECONDS", 0), \
             patch.object(pipeline, "client", client), \
             patch.object(pipeline, "PRODUCT_REVIEW_REQUEST_BUDGET", pr_budget), \
             patch.object(pipeline, "GEMINI_BUDGET", global_budget), \
             patch.object(pipeline.PERSISTENT_GEMINI_COUNTER, "reserve", return_value=None), \
             patch.object(pipeline.GEMINI_USAGE_AUDIT, "record_attempt", return_value=1), \
             patch.object(pipeline.GEMINI_USAGE_AUDIT, "record_outcome"), \
             patch.object(pipeline.GEMINI_USAGE_AUDIT, "record_response_usage"), \
             patch.object(pipeline, "persist_decision_intelligence_assessment", return_value={"saved": True, "page_id": None}):
            result = pipeline.run_product_reviews()
        self.assertEqual(1, result["review_slots_used"])
        self.assertEqual(1, result["structured_retries"])
        self.assertEqual(1, result["structured_retry_recovered"])
        self.assertEqual(1, result["saved"])
        self.assertEqual(2, pr_budget.used)
        self.assertEqual({"product_review": 1, "product_review_retry": 1}, pr_budget.by_kind)
        self.assertEqual(2, global_budget.request_count)
        self.assertEqual([], client.queue)

    def test_retry_cannot_exceed_real_product_budget(self):
        bad = review_payload(); bad.pop("main_risk")
        client = _SequenceClient([json.dumps(bad, ensure_ascii=False), json.dumps(review_payload(), ensure_ascii=False)])
        pr_budget = pipeline.ProductReviewRequestBudget(1)
        global_budget = pipeline.GeminiBudget(10, 2, 2)
        with patch.object(pipeline, "PRODUCT_REVIEW_MAX_PER_RUN", 1), \
             patch.object(pipeline, "select_product_review_candidates", return_value=[self._source_state()]), \
             patch.object(pipeline, "prepare_source_context", return_value=self._source_info()), \
             patch.object(pipeline, "assess_evidence_sufficiency", return_value=self._evidence()), \
             patch.object(pipeline, "_primary_source_authority_failures", return_value=[]), \
             patch.object(pipeline, "DEEP_DIVE_MODEL_POOL", ["gemini-test"]), \
             patch.object(pipeline, "SESSION_EXHAUSTED_MODELS", set()), \
             patch.object(pipeline, "SESSION_UNAVAILABLE_MODELS", set()), \
             patch.object(pipeline, "GEMINI_DEEP_DIVE_CALL_PACING_SECONDS", 0), \
             patch.object(pipeline, "client", client), \
             patch.object(pipeline, "PRODUCT_REVIEW_REQUEST_BUDGET", pr_budget), \
             patch.object(pipeline, "GEMINI_BUDGET", global_budget), \
             patch.object(pipeline.PERSISTENT_GEMINI_COUNTER, "reserve", return_value=None), \
             patch.object(pipeline.GEMINI_USAGE_AUDIT, "record_attempt", return_value=1), \
             patch.object(pipeline.GEMINI_USAGE_AUDIT, "record_outcome"), \
             patch.object(pipeline.GEMINI_USAGE_AUDIT, "record_response_usage"), \
             patch.object(pipeline, "persist_decision_intelligence_assessment", return_value={"saved": True, "page_id": None}):
            result = pipeline.run_product_reviews()
        self.assertEqual(1, pr_budget.used)
        self.assertEqual({"product_review": 1}, pr_budget.by_kind)
        self.assertEqual(1, global_budget.request_count)
        self.assertEqual(1, result["review_slots_used"])
        self.assertEqual(0, result["structured_retries"])
        self.assertEqual(0, result["saved"])
        self.assertEqual(1, result["skipped"])
        # The second fake response remains unused, proving the cap blocked provider send #2.
        self.assertEqual(1, len(client.queue))

    def test_valid_payload_still_parses_identically(self):
        parsed = pipeline._parse_product_review_response(review_payload(category="DATA"))
        self.assertEqual("DATA", parsed["category"])
        self.assertEqual(80, parsed["adoption_score"])
        self.assertEqual(30, parsed["next_review_days"])
        self.assertIn("Evidence Quality 20/25", parsed["adoption_score_breakdown_text"])


if __name__ == "__main__":
    unittest.main()
