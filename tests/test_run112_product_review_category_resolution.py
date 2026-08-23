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
        def __init__(self, *a, **k):
            self.chats = MagicMock()
    class _APIError(Exception):
        def __init__(self, *a, code=None, **k):
            super().__init__(*a)
            self.code = code
    genai_mod.Client = _Client
    errors_mod.APIError = _APIError
    google_pkg.genai = genai_mod
    sys.modules["google"] = google_pkg
    sys.modules["google.genai"] = genai_mod
    sys.modules["google.genai.errors"] = errors_mod

import pipeline


COMPONENTS = {
    "Evidence Quality": 25,
    "Production Maturity": 20,
    "Use-case Utility / Fit": 18,
    "Reliability / Security Risk": 12,
    "Integration / Migration Feasibility": 9,
    "Ecosystem / Support Durability": 5,
}


def review_json(category="DATA"):
    return json.dumps({
        "category": category,
        "adoption_score": sum(COMPONENTS.values()),
        "components": COMPONENTS,
        "adoption_status": "TEST",
        "evidence_confidence": "HIGH",
        "production_readiness": "HIGH",
        "main_risk": "revision未固定では再現性に影響し得る。",
        "best_for": "データセットのロードと前処理。",
        "avoid_for": "外部データ参照を禁止した環境。",
        "short_rationale": "一次情報でデータ処理機能を確認できる。",
        "next_review_days": 30,
    }, ensure_ascii=False)


class Run112ProductReviewCategoryResolutionTests(unittest.TestCase):
    def test_prompt_requests_evidence_grounded_category_without_schema_duplication(self):
        # Run115 supersedes Run112's prompt-level enum/key duplication: the closed set now lives
        # only in response_json_schema, while the prompt keeps evidence-grounded decision semantics.
        prompt = pipeline._product_review_prompt(
            {"nameWithOwner": "huggingface/datasets", "url": "https://github.com/huggingface/datasets"},
            {"context": "Dataset loading and processing library."},
            {"category": "OTHER"},
        )
        self.assertNotIn("keys: category, adoption_score", prompt)
        self.assertNotIn("MODEL/AGENT/DEVTOOLS/INFRA/DATA/SECURITY/MULTIMODAL/PRODUCT/OTHER", prompt)
        self.assertIn("根拠が弱い場合はOTHER", prompt)

    def test_parser_keeps_valid_product_category(self):
        parsed = pipeline._parse_product_review_response(review_json("DATA"))
        self.assertEqual(parsed["category"], "DATA")

    def test_unknown_category_is_structured_failure_not_silent_other(self):
        # Run115 intentionally replaces Run112's silent OTHER coercion so schema violations
        # trigger the one logical Product Review retry instead of hiding provider drift.
        with self.assertRaisesRegex(ValueError, "category invalid"):
            pipeline._parse_product_review_response(review_json("DATABASE"))

    def test_missing_category_is_structured_failure(self):
        payload = json.loads(review_json("DATA"))
        payload.pop("category")
        with self.assertRaisesRegex(ValueError, "missing_fields=category"):
            pipeline._parse_product_review_response(json.dumps(payload, ensure_ascii=False))

    def test_product_review_persists_review_category_not_legacy_other(self):
        state = {
            "canonical_entity_id": "github:huggingface/datasets",
            "technology_name": "huggingface/datasets",
            "primary_url": "https://github.com/huggingface/datasets",
            "sources": ["GitHub"],
            "category": "OTHER",
            "screening_score": 85,
            "screening_reason": "test",
            "source_summary": "legacy",
        }
        response = MagicMock(text=review_json("DATA"))
        captured = {}
        def persist(*args, **kwargs):
            captured.update(kwargs.get("attribution_context") or {})
            return {"saved": True, "page_id": None}
        with patch.object(pipeline, "select_product_review_candidates", return_value=[state]), \
             patch.object(pipeline.PRODUCT_REVIEW_REQUEST_BUDGET, "can_request", return_value=True), \
             patch.object(pipeline.GEMINI_BUDGET, "can_request", return_value=True), \
             patch.object(pipeline, "_model_pool_has_session_candidate", return_value=True), \
             patch.object(pipeline, "prepare_source_context", return_value={"context": "verified", "verification_context": "verified"}), \
             patch.object(pipeline, "assess_evidence_sufficiency", return_value={"state": pipeline.EVIDENCE_SUFFICIENT, "decision_scope_safe": True}), \
             patch.object(pipeline, "_call_product_review_pool", return_value=(response, "gemini-test")), \
             patch.object(pipeline, "persist_decision_intelligence_assessment", side_effect=persist):
            result = pipeline.run_product_reviews()
        self.assertEqual(result["saved"], 1)
        self.assertEqual(captured.get("portfolio_topic"), "DATA")


if __name__ == "__main__":
    unittest.main()
