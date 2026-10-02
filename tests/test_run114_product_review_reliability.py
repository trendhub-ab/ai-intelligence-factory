import json
import os
import sys
import unittest
from pathlib import Path
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


class Run114ProductReviewReliabilityTests(unittest.TestCase):
    def test_product_review_call_uses_json_schema(self):
        response = MagicMock(text=json.dumps(review_payload(), ensure_ascii=False))
        with patch.object(pipeline, "DEEP_DIVE_MODEL_POOL", ["gemini-test"]), \
             patch.object(pipeline, "SESSION_EXHAUSTED_MODELS", set()), \
             patch.object(pipeline, "SESSION_UNAVAILABLE_MODELS", set()), \
             patch.object(pipeline.PRODUCT_REVIEW_REQUEST_BUDGET, "can_request", return_value=True), \
             patch.object(pipeline, "_generate_via_chat", return_value=response) as generate:
            pipeline._call_product_review_pool("prompt", "ctx")
        config = generate.call_args.kwargs["config"]
        self.assertEqual("application/json", config["response_mime_type"])
        schema = config["response_json_schema"]
        self.assertEqual("object", schema["type"])
        self.assertIn("category", schema["required"])
        self.assertEqual(set(pipeline.PORTFOLIO_TOPICS), set(schema["properties"]["category"]["enum"]))
        self.assertEqual(
            {label for label, _ in pipeline._ADOPTION_SCORE_COMPONENTS},
            set(schema["properties"]["components"]["required"]),
        )

    def test_schema_uses_only_documented_gemini_json_schema_subset(self):
        allowed = {"type", "additionalProperties", "properties", "required", "enum", "minimum", "maximum"}
        def walk(node):
            if isinstance(node, dict):
                schema_keys = set(node)
                if "type" in node:
                    self.assertTrue(schema_keys <= allowed, schema_keys - allowed)
                for key, value in node.items():
                    if key == "properties":
                        for child in value.values(): walk(child)
                    elif key not in {"required", "enum"}:
                        walk(value)
            elif isinstance(node, list):
                for child in node: walk(child)
        walk(pipeline._PRODUCT_REVIEW_RESPONSE_SCHEMA)

    def test_parser_tolerates_code_fence_and_trailing_transport_text_without_api(self):
        text = "```json\n" + json.dumps(review_payload(), ensure_ascii=False) + "\n```"
        parsed = pipeline._parse_product_review_response(text)
        self.assertEqual(80, parsed["adoption_score"])
        self.assertEqual("DEVTOOLS", parsed["category"])

        trailing = "transport-prefix\n" + json.dumps(review_payload(category="DATA"), ensure_ascii=False) + "\ntransport-tail"
        parsed2 = pipeline._parse_product_review_response(trailing)
        self.assertEqual("DATA", parsed2["category"])

    def test_provider_parsed_object_is_preferred(self):
        response = MagicMock()
        response.parsed = review_payload(category="INFRA")
        response.text = "{broken"
        parsed = pipeline._parse_product_review_model_response(response)
        self.assertEqual("INFRA", parsed["category"])

    def test_malformed_json_gets_exactly_one_logical_retry_inside_existing_budget(self):
        state = {
            "canonical_entity_id": "github:org/tool", "technology_name": "org/tool",
            "primary_url": "https://github.com/org/tool", "sources": ["GitHub"],
            "screening_score": 80, "screening_reason": "test", "source_summary": "legacy",
        }
        bad = MagicMock(text="{not valid json", parsed=None)
        good = MagicMock(text=json.dumps(review_payload(), ensure_ascii=False), parsed=None)
        info = {"context": "verified", "verification_context": "Method implementation limitation", "source": "GitHub"}
        ev = {"state": pipeline.EVIDENCE_SUFFICIENT, "decision_scope_safe": True, "blocking_missing": []}
        with patch.object(pipeline, "PRODUCT_REVIEW_MAX_PER_RUN", 1), \
             patch.object(pipeline, "select_product_review_candidates", return_value=[state]), \
             patch.object(pipeline, "prepare_source_context", return_value=info), \
             patch.object(pipeline, "assess_evidence_sufficiency", return_value=ev), \
             patch.object(pipeline, "_primary_source_authority_failures", return_value=[]), \
             patch.object(pipeline.PRODUCT_REVIEW_REQUEST_BUDGET, "can_request", return_value=True), \
             patch.object(pipeline.GEMINI_BUDGET, "can_request", return_value=True), \
             patch.object(pipeline, "_model_pool_has_session_candidate", return_value=True), \
             patch.object(pipeline, "_call_product_review_pool", side_effect=[(bad, "m"), (good, "m")]) as call, \
             patch.object(pipeline, "persist_decision_intelligence_assessment", return_value={"saved": True, "page_id": None}):
            result = pipeline.run_product_reviews()
        self.assertEqual(2, call.call_count)
        self.assertEqual(1, result["review_slots_used"])
        self.assertEqual(1, result["structured_retries"])
        self.assertEqual(1, result["structured_retry_recovered"])
        self.assertEqual(1, result["saved"])
        self.assertEqual("product_review_retry", call.call_args.kwargs["request_kind_base"])

    def test_source_boundary_name_extraction_is_narrow(self):
        failures = [
            "source-boundary unsupported named fact: MLflow Tracking, Model Registry",
            "Adoption Score total mismatch",
        ]
        self.assertEqual(["MLflow Tracking", "Model Registry"], pipeline._source_boundary_failure_names(failures))

    def test_mlflow_tracking_false_reject_can_be_reconciled_from_explicit_official_docs(self):
        source_info = {
            "source": "GitHub",
            "primary_url": "https://github.com/mlflow/mlflow",
            "source_details": {"homepage": "https://mlflow.org/docs/latest/"},
            "supplement_candidates": [{
                "url": "https://mlflow.org/docs/latest/", "role": "PRIMARY_SOURCE",
                "source_type": "official_docs", "label": "GitHub repository homepage",
            }],
            "verification_context": "MLflow is an open source platform for machine learning lifecycle.",
            "context": "MLflow is an open source platform for machine learning lifecycle.",
            "checked_urls": set(), "evidence_documents": [], "deep_source_urls": [],
            "deep_source_scanned": True,
        }
        failures = ["source-boundary unsupported named fact: MLflow Tracking"]
        seed_links = [("https://mlflow.org/docs/latest/ml/tracking/", "MLflow Tracking")]
        with patch.object(pipeline, "_fetch_boundary_html", side_effect=[
            ("MLflow documentation home", seed_links, "https://mlflow.org/docs/latest/"),
            ("MLflow Tracking provides APIs and UI for logging runs.", [], "https://mlflow.org/docs/latest/ml/tracking/"),
        ]) as fetch:
            result = pipeline.reconcile_product_review_source_boundary({}, source_info, failures)
        self.assertTrue(result["resolved"])
        self.assertEqual(2, fetch.call_count)
        self.assertIn("MLflow Tracking", source_info["verification_context"])
        self.assertIn("https://mlflow.org/docs/latest/ml/tracking/", source_info["deep_source_urls"])

    def test_reconciliation_can_reopen_preflight_checked_official_seed_for_link_discovery(self):
        seed = "https://mlflow.org/docs/latest/"
        source_info = {
            "source": "GitHub", "primary_url": "https://github.com/mlflow/mlflow",
            "source_details": {"homepage": seed},
            "supplement_candidates": [{"url": seed, "role": "PRIMARY_SOURCE"}],
            "verification_context": "MLflow platform docs", "context": "MLflow platform docs",
            "checked_urls": {pipeline._evidence_trace_url_key(seed)},
            "evidence_documents": [], "deep_source_urls": [],
        }
        with patch.object(pipeline, "_fetch_boundary_html", side_effect=[
            ("Docs home", [("https://mlflow.org/docs/latest/ml/tracking/", "MLflow Tracking")], seed),
            ("MLflow Tracking provides run logging.", [], "https://mlflow.org/docs/latest/ml/tracking/"),
        ]) as fetch:
            result = pipeline.reconcile_product_review_source_boundary(
                {}, source_info, ["source-boundary unsupported named fact: MLflow Tracking"]
            )
        self.assertTrue(result["resolved"])
        self.assertEqual(2, fetch.call_count)

    def test_reconciliation_does_not_follow_matching_link_to_unrelated_host(self):
        source_info = {
            "source": "GitHub", "primary_url": "https://github.com/org/tool",
            "source_details": {"homepage": "https://tool.example/docs"},
            "supplement_candidates": [{"url": "https://tool.example/docs", "role": "PRIMARY_SOURCE"}],
            "verification_context": "Tool docs", "context": "Tool docs",
            "checked_urls": set(), "evidence_documents": [], "deep_source_urls": [],
        }
        with patch.object(pipeline, "_fetch_boundary_html", return_value=(
            "Tool docs", [("https://evil.example/mlflow-tracking", "MLflow Tracking")], "https://tool.example/docs"
        )) as fetch:
            result = pipeline.reconcile_product_review_source_boundary(
                {}, source_info, ["source-boundary unsupported named fact: MLflow Tracking"]
            )
        self.assertFalse(result["resolved"])
        self.assertEqual(1, fetch.call_count)
        self.assertEqual([], source_info["deep_source_urls"])

    def test_boundary_reconciliation_revalidates_without_second_gemini(self):
        state = {
            "canonical_entity_id": "github:mlflow/mlflow", "technology_name": "mlflow/mlflow",
            "primary_url": "https://github.com/mlflow/mlflow", "sources": ["GitHub"],
            "screening_score": 85, "screening_reason": "test", "source_summary": "legacy",
        }
        response = MagicMock(text=json.dumps(review_payload(), ensure_ascii=False), parsed=None)
        info = {"context": "verified", "verification_context": "verified", "source": "GitHub"}
        ev = {"state": pipeline.EVIDENCE_SUFFICIENT, "decision_scope_safe": True, "blocking_missing": []}
        first = {"saved": False, "reason": "assessment_invalid", "failures": ["source-boundary unsupported named fact: MLflow Tracking"]}
        second = {"saved": True, "page_id": None}
        with patch.object(pipeline, "PRODUCT_REVIEW_MAX_PER_RUN", 1), \
             patch.object(pipeline, "select_product_review_candidates", return_value=[state]), \
             patch.object(pipeline, "prepare_source_context", return_value=info), \
             patch.object(pipeline, "assess_evidence_sufficiency", return_value=ev), \
             patch.object(pipeline, "_primary_source_authority_failures", return_value=[]), \
             patch.object(pipeline.PRODUCT_REVIEW_REQUEST_BUDGET, "can_request", return_value=True), \
             patch.object(pipeline.GEMINI_BUDGET, "can_request", return_value=True), \
             patch.object(pipeline, "_model_pool_has_session_candidate", return_value=True), \
             patch.object(pipeline, "_call_product_review_pool", return_value=(response, "m")) as gemini, \
             patch.object(pipeline, "reconcile_product_review_source_boundary", return_value={"resolved": True}), \
             patch.object(pipeline, "persist_decision_intelligence_assessment", side_effect=[first, second]) as persist:
            result = pipeline.run_product_reviews()
        self.assertEqual(1, gemini.call_count)
        self.assertEqual(2, persist.call_count)
        self.assertEqual(1, result["boundary_reconciliation_attempted"])
        self.assertEqual(1, result["boundary_reconciled"])
        self.assertEqual(1, result["saved"])

    def test_named_fact_gate_stays_fail_closed_when_reconciliation_cannot_prove_fact(self):
        before = pipeline._find_source_boundary_violations(
            "MLflow Trackingを利用できる。", "MLflow is a platform for machine learning lifecycle."
        )
        self.assertTrue(any("MLflow Tracking" in x for x in before))
        after = pipeline._find_source_boundary_violations(
            "MLflow Trackingを利用できる。", "Official documentation: MLflow Tracking provides APIs for runs."
        )
        self.assertEqual([], after)


if __name__ == "__main__":
    unittest.main()
