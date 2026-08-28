import os
import sys
import types
import unittest
from unittest.mock import patch

os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("GH_PAT", "test-token")
os.environ.setdefault("GEMINI_QUOTA_PROJECT_ID", "test-project")
try:
    from google import genai  # noqa: F401
except (ImportError, AttributeError):
    google_mod = sys.modules.get("google") or types.ModuleType("google")
    genai_mod = types.ModuleType("google.genai")
    errors_mod = types.ModuleType("google.genai.errors")
    class APIError(Exception):
        pass
    class Client:
        def __init__(self, **_kwargs):
            self.chats = types.SimpleNamespace(create=lambda **_kw: None)
    genai_mod.Client = Client
    errors_mod.APIError = APIError
    google_mod.genai = genai_mod
    sys.modules.update({"google": google_mod, "google.genai": genai_mod, "google.genai.errors": errors_mod})

import pipeline


class Run109InventoryBootstrapIntegrationTests(unittest.TestCase):
    def test_bootstrap_main_bypasses_article_pipeline_and_audit_reset(self):
        with patch.object(pipeline, "INVENTORY_BOOTSTRAP_ACTIVE", True), \
             patch.object(pipeline, "initialize_inventory_bootstrap_runtime") as init, \
             patch.object(pipeline, "run_product_reviews", return_value={"attempted": 1, "saved": 1, "skipped": 0}) as reviews, \
             patch.object(pipeline, "run_product_delivery_maintenance", return_value={"subscriber": {"enabled": True}, "monthly": []}) as delivery, \
             patch.object(pipeline, "reset_article_audit_for_production_run") as audit_reset, \
             patch.object(pipeline, "fetch_github_trending") as fetch_github, \
             patch.object(pipeline, "get_existing_repo_urls") as article_dedupe:
            pipeline.main()
        init.assert_called_once()
        reviews.assert_called_once()
        delivery.assert_called_once()
        audit_reset.assert_not_called()
        fetch_github.assert_not_called()
        article_dedupe.assert_not_called()

    def test_bootstrap_candidate_selection_requires_allowlist(self):
        with patch.object(pipeline, "INVENTORY_BOOTSTRAP_ACTIVE", True), \
             patch.object(pipeline, "ENABLE_REVENUE_PRODUCT_PHASE2", True), \
             patch.object(pipeline.decision_intelligence, "ENABLE_DECISION_INTELLIGENCE_DB", True), \
             patch.object(pipeline, "INVENTORY_BOOTSTRAP_ENTITY_IDS", tuple()), \
             patch.object(pipeline.decision_intelligence, "query_technology_records", return_value=[{"id": "x"}]), \
             patch.object(pipeline.decision_intelligence, "technology_page_to_state", return_value={
                 "canonical_entity_id": "github:a/b", "assessment_state": "LEGACY_PENDING",
                 "entity_status": "RESOLVED", "screening_score": 99,
             }):
            self.assertEqual([], pipeline.select_product_review_candidates())

    def test_bootstrap_candidate_selection_respects_plan_order_not_screening_order(self):
        states = [
            {"canonical_entity_id": "github:high/score", "assessment_state": "LEGACY_PENDING", "entity_status": "RESOLVED", "screening_score": 99, "technology_name": "High"},
            {"canonical_entity_id": "github:plan/first", "assessment_state": "LEGACY_PENDING", "entity_status": "RESOLVED", "screening_score": 60, "technology_name": "First"},
            {"canonical_entity_id": "github:plan/second", "assessment_state": "LEGACY_PENDING", "entity_status": "RESOLVED", "screening_score": 95, "technology_name": "Second"},
        ]
        pages = [{"i": i} for i in range(len(states))]
        with patch.object(pipeline, "INVENTORY_BOOTSTRAP_ACTIVE", True), \
             patch.object(pipeline, "ENABLE_REVENUE_PRODUCT_PHASE2", True), \
             patch.object(pipeline.decision_intelligence, "ENABLE_DECISION_INTELLIGENCE_DB", True), \
             patch.object(pipeline, "INVENTORY_BOOTSTRAP_ENTITY_IDS", ("github:plan/first", "github:plan/second", "github:high/score")), \
             patch.object(pipeline, "PRODUCT_REVIEW_MAX_PER_RUN", 2), \
             patch.object(pipeline, "LEGACY_BOOTSTRAP_MAX_PER_RUN", 2), \
             patch.object(pipeline.decision_intelligence, "query_technology_records", return_value=pages), \
             patch.object(pipeline.decision_intelligence, "technology_page_to_state", side_effect=states):
            selected = pipeline.select_product_review_candidates()
        # Run113 bootstrap preflight may inspect beyond max_reviews so evidence-insufficient rows
        # do not consume Gemini review slots. The reviewed Plan order must still be preserved.
        self.assertEqual(["github:plan/first", "github:plan/second"], [x["canonical_entity_id"] for x in selected[:2]])
        self.assertGreaterEqual(len(selected), 2)

    def test_normal_daily_candidate_order_remains_screening_score_based(self):
        states = [
            {"canonical_entity_id": "github:low/score", "assessment_state": "LEGACY_PENDING", "entity_status": "RESOLVED", "screening_score": 60, "technology_name": "Low"},
            {"canonical_entity_id": "github:high/score", "assessment_state": "LEGACY_PENDING", "entity_status": "RESOLVED", "screening_score": 99, "technology_name": "High"},
        ]
        pages = [{"i": i} for i in range(len(states))]
        with patch.object(pipeline, "INVENTORY_BOOTSTRAP_ACTIVE", False), \
             patch.object(pipeline, "ENABLE_REVENUE_PRODUCT_PHASE2", True), \
             patch.object(pipeline.decision_intelligence, "ENABLE_DECISION_INTELLIGENCE_DB", True), \
             patch.object(pipeline, "PRODUCT_REVIEW_MAX_PER_RUN", 2), \
             patch.object(pipeline, "LEGACY_BOOTSTRAP_MAX_PER_RUN", 2), \
             patch.object(pipeline.decision_intelligence, "query_technology_records", return_value=pages), \
             patch.object(pipeline.decision_intelligence, "technology_page_to_state", side_effect=states):
            selected = pipeline.select_product_review_candidates()
        self.assertEqual(["github:high/score", "github:low/score"], [x["canonical_entity_id"] for x in selected])

    def test_bootstrap_runtime_preflight_does_not_require_article_notion_preflight(self):
        with patch.object(pipeline, "GEMINI_API_KEY", "x"), \
             patch.object(pipeline, "GEMINI_PERSISTENT_DAILY_COUNTER", False), \
             patch.object(pipeline, "DEEP_DIVE_MODEL_POOL", ["model-x"]), \
             patch.object(pipeline, "preflight_notion_schema") as article_preflight, \
             patch.object(pipeline.decision_intelligence, "preflight_decision_intelligence_schema") as product_preflight, \
             patch.object(pipeline, "_register_gemini_usage_atexit"):
            pipeline.initialize_inventory_bootstrap_runtime()
        product_preflight.assert_called_once()
        article_preflight.assert_not_called()

    def test_bootstrap_runtime_persistent_counter_fails_early_without_github_identity(self):
        with patch.object(pipeline, "GEMINI_API_KEY", "x"), \
             patch.object(pipeline, "GEMINI_PERSISTENT_DAILY_COUNTER", True), \
             patch.object(pipeline, "GEMINI_COUNTER_SCOPE_ID", "stable-scope"), \
             patch.object(pipeline, "GH_PAT", ""), \
             patch.dict(os.environ, {"GITHUB_REPOSITORY": ""}, clear=False):
            with self.assertRaisesRegex(ValueError, "GH_PAT and GITHUB_REPOSITORY"):
                pipeline.initialize_inventory_bootstrap_runtime()

    def test_bootstrap_workflow_is_manual_only_and_read_permission(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github" / "workflows" / "inventory-bootstrap.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertIn("contents: read", workflow)
        # Run131 removes the hard source-share quota. Diversification is now
        # tolerance-protected so materially weaker candidates are never forced upward.
        self.assertNotIn("max_source_share", workflow)
        self.assertIn("PORTFOLIO_DIVERSITY_TOLERANCE", workflow)


if __name__ == "__main__":
    unittest.main()
