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


class Run113CrossSourceEvidenceResolutionTests(unittest.TestCase):
    def test_github_uses_source_native_api_and_never_scrapes_repo_html(self):
        repo = {
            "source": "GitHub", "nameWithOwner": "arc53/DocsGPT",
            "url": "https://github.com/arc53/DocsGPT", "primaryUrl": "https://github.com/arc53/DocsGPT",
            "canonicalEntityId": "github:arc53/docsgpt", "description": "RAG platform",
        }
        readme = "DocsGPT is an open-source RAG platform. [Docs](https://docs.docsgpt.cloud/guide) [Copilot](https://github.com/features/copilot)"
        metadata = "Repository: arc53/DocsGPT\nDescription: RAG platform\nPushed at: 2026-08-23T00:00:00Z"
        with patch.object(pipeline, "fetch_github_readme_context", return_value=readme), \
             patch.object(pipeline, "fetch_github_repository_metadata_context", return_value=(metadata, {"homepage": "https://docsgpt.cloud"})), \
             patch.object(pipeline, "_fetch_html_document") as html:
            info = pipeline.prepare_source_context(repo)
        html.assert_not_called()
        self.assertTrue(info["primary_source_resolved"])
        self.assertTrue(info["freshness_status_available"])
        urls = [x["url"] for x in info["supplement_candidates"]]
        self.assertIn("https://docs.docsgpt.cloud/guide", urls)
        self.assertIn("https://docsgpt.cloud", urls)
        self.assertNotIn("https://github.com/features/copilot", urls)

    def test_github_global_navigation_is_never_evidence(self):
        self.assertTrue(pipeline._is_github_global_navigation_url("https://github.com/features/copilot"))
        self.assertTrue(pipeline._is_github_global_navigation_url("https://github.com/features/ai/github-app"))
        self.assertFalse(pipeline._is_github_global_navigation_url("https://github.com/arc53/DocsGPT/releases"))

    def test_legacy_arxiv_rehydrates_exact_official_metadata(self):
        state = {
            "sources": ["ArXiv"], "technology_name": "Paper", "canonical_entity_id": "arxiv:2608.16806",
            "primary_url": "https://arxiv.org/abs/2608.16806", "source_summary": "legacy summary",
            "evidence_urls": [], "entity_aliases": [],
        }
        repo = pipeline._technology_state_to_repo(state)
        self.assertFalse(repo["sourceContextVerified"])
        with patch.object(pipeline, "fetch_arxiv_api_context", return_value=("Title: Paper\nAbstract: Method architecture", {"authors": ["A"]})), \
             patch.object(pipeline, "_fetch_html_document", return_value=("", [], repo["primaryUrl"])):
            info = pipeline.prepare_source_context(repo)
        self.assertEqual("ArXiv", info["source"])
        self.assertTrue(info["primary_source_resolved"])
        self.assertIn("Official arXiv metadata", info["context"])

    def test_arxiv_pdf_success_resolves_primary_when_landing_failed(self):
        info = {
            "context": "", "verification_context": "", "source": "ArXiv",
            "primary_source_resolved": False, "primary_fetch_failed": True,
            "checked_urls": set(), "evidence_documents": [], "deep_source_urls": [],
            "supplement_candidates": [{
                "url": "https://arxiv.org/pdf/2608.16806.pdf", "role": "PRIMARY_SOURCE",
                "source_type": "arxiv_pdf", "label": "arxiv_pdf",
            }],
            "evidence_supplement_attempted": False, "evidence_supplement_attempts": 0,
        }
        with patch.object(pipeline, "fetch_pdf_context", return_value="Method: attack evaluation. Limitation: lab setting."):
            out = pipeline.supplement_source_evidence(info)
        self.assertTrue(out["primary_source_resolved"])
        self.assertFalse(out["primary_fetch_failed"])

    def test_arxiv_same_paper_doi_does_not_waste_supplement_slot(self):
        repo = {
            "source": "ArXiv", "nameWithOwner": "Paper", "url": "https://arxiv.org/abs/2608.16806",
            "primaryUrl": "https://arxiv.org/abs/2608.16806", "canonicalEntityId": "arxiv:2608.16806",
            "sourceContext": "", "sourceContextVerified": False,
        }
        with patch.object(pipeline, "fetch_arxiv_api_context", return_value=("Abstract: Method architecture", {"official_external_links": ["https://doi.org/10.48550/arXiv.2608.16806"]})), \
             patch.object(pipeline, "_fetch_html_document", return_value=("", [], repo["primaryUrl"])):
            info = pipeline.prepare_source_context(repo)
        urls = [x["url"] for x in info["supplement_candidates"]]
        self.assertIn("https://arxiv.org/pdf/2608.16806.pdf", urls)
        self.assertNotIn("https://doi.org/10.48550/arXiv.2608.16806", urls)

    def test_producthunt_discovery_page_is_not_promoted_to_primary_evidence(self):
        repo = {
            "source": "ProductHunt", "nameWithOwner": "product",
            "url": "https://www.producthunt.com/posts/product", "primaryUrl": "https://www.producthunt.com/posts/product",
            "sourceDetails": {"official_url": "https://vendor.example/docs"},
        }
        with patch.object(pipeline, "fetch_webpage_context", return_value=""), \
             patch.object(pipeline, "_fetch_html_document", return_value=("Product Hunt listing", [], repo["primaryUrl"])):
            info = pipeline.prepare_source_context(repo)
        self.assertFalse(info["primary_source_resolved"])
        self.assertIn("https://vendor.example/docs", [x["url"] for x in info["supplement_candidates"]])

    def test_hn_row_with_github_primary_is_promoted_to_github_evidence(self):
        state = {
            "sources": ["HackerNews"], "technology_name": "Launch HN: Tool", "canonical_entity_id": "github:org/tool",
            "primary_url": "https://github.com/org/tool", "source_summary": "HN discovery summary",
            "evidence_urls": [], "entity_aliases": ["https://news.ycombinator.com/item?id=1"],
        }
        repo = pipeline._technology_state_to_repo(state)
        self.assertEqual("GitHub", repo["source"])
        self.assertEqual("org/tool", repo["nameWithOwner"])
        self.assertEqual(["HackerNews"], repo["sourceDetails"]["discovery_sources"])


    def test_producthunt_official_site_resolves_primary_and_passes_authority(self):
        repo = {
            "source": "ProductHunt", "nameWithOwner": "product",
            "url": "https://www.producthunt.com/posts/product", "primaryUrl": "https://www.producthunt.com/posts/product",
            "sourceDetails": {"official_url": "https://vendor.example/docs"},
        }
        with patch.object(pipeline, "_resolve_producthunt_official_url", return_value=""), \
             patch.object(pipeline, "_fetch_html_document", return_value=("Method architecture and API implementation. Limitation: beta.", [], "https://vendor.example/docs")):
            info = pipeline.prepare_source_context(repo)
        self.assertEqual("https://vendor.example/docs", info["primary_url"])
        self.assertTrue(info["primary_source_resolved"])
        self.assertEqual([], pipeline._primary_source_authority_failures(info))

    def test_hn_external_author_source_can_resolve_primary(self):
        repo = {
            "source": "HackerNews", "nameWithOwner": "Show HN: Tool",
            "url": "https://author.example/tool", "primaryUrl": "https://author.example/tool",
            "sourceContext": "HN discovery", "sourceContextVerified": False, "sourceDetails": {},
        }
        with patch.object(pipeline, "_fetch_html_document", return_value=("Author implementation method. Limitation: prototype.", [], "https://author.example/tool")):
            info = pipeline.prepare_source_context(repo)
        self.assertTrue(info["primary_source_resolved"])
        self.assertEqual([], pipeline._primary_source_authority_failures(info))

    def test_hn_secondary_news_cannot_become_paid_primary_authority(self):
        repo = {
            "source": "HackerNews", "nameWithOwner": "news",
            "url": "https://www.reuters.com/technology/example", "primaryUrl": "https://www.reuters.com/technology/example",
            "sourceContext": "HN discovery", "sourceContextVerified": False, "sourceDetails": {},
        }
        with patch.object(pipeline, "_fetch_html_document", return_value=("Vendor released a product with API implementation.", [], repo["primaryUrl"])):
            info = pipeline.prepare_source_context(repo)
        self.assertTrue(info["primary_source_resolved"])
        failures = pipeline._primary_source_authority_failures(info)
        self.assertTrue(any("secondary news report" in x for x in failures))

    def test_research_current_word_does_not_create_live_freshness_blocker(self):
        info = {
            "verification_context": "This paper presents a current method and architecture for evaluation.",
            "context": "", "source": "ArXiv", "primary_source_resolved": True,
            "freshness_status_available": False, "evidence_metadata": {"coverage": {"method": "FOUND"}},
            "evidence_documents": [], "checked_urls": set(), "supplement_candidates": [],
        }
        result = pipeline.assess_evidence_sufficiency(info)
        self.assertNotIn("freshness_status_available_if_time_sensitive", result["blocking_missing"])
        self.assertEqual(pipeline.EVIDENCE_SUFFICIENT, result["state"])

    def test_evidence_skips_do_not_consume_three_review_slots(self):
        states = [
            {"canonical_entity_id": f"github:o/r{i}", "technology_name": f"o/r{i}", "primary_url": f"https://github.com/o/r{i}",
             "sources": ["GitHub"], "source_summary": "x", "screening_score": 80, "screening_reason": "x"}
            for i in range(5)
        ]
        response = MagicMock(text='''{"category":"DEVTOOLS","adoption_score":80,"components":{"Evidence Quality":20,"Production Maturity":20,"Use-case Utility / Fit":16,"Reliability / Security Risk":12,"Integration / Migration Feasibility":8,"Ecosystem / Support Durability":4},"adoption_status":"TEST","evidence_confidence":"HIGH","production_readiness":"HIGH","main_risk":"risk","best_for":"best use case","avoid_for":"avoid use case","short_rationale":"verified rationale","next_review_days":30}''')
        def prep(repo):
            return {"context": repo["nameWithOwner"], "verification_context": "Method implementation. Limitation: test.", "source": "GitHub"}
        calls = {"n": 0}
        def assess(info):
            calls["n"] += 1
            if calls["n"] <= 2:
                return {"state": pipeline.EVIDENCE_INSUFFICIENT, "decision_scope_safe": False, "blocking_missing": ["technical_claims_available"]}
            return {"state": pipeline.EVIDENCE_SUFFICIENT, "decision_scope_safe": True, "blocking_missing": []}
        with patch.object(pipeline, "PRODUCT_REVIEW_MAX_PER_RUN", 3), \
             patch.object(pipeline, "select_product_review_candidates", return_value=states), \
             patch.object(pipeline, "prepare_source_context", side_effect=prep), \
             patch.object(pipeline, "assess_evidence_sufficiency", side_effect=assess), \
             patch.object(pipeline, "_defer_product_review_candidate"), \
             patch.object(pipeline, "_primary_source_authority_failures", return_value=[]), \
             patch.object(pipeline.PRODUCT_REVIEW_REQUEST_BUDGET, "can_request", return_value=True), \
             patch.object(pipeline.GEMINI_BUDGET, "can_request", return_value=True), \
             patch.object(pipeline, "_model_pool_has_session_candidate", return_value=True), \
             patch.object(pipeline, "_call_product_review_pool", return_value=(response, "gemini-test")) as gemini, \
             patch.object(pipeline, "persist_decision_intelligence_assessment", return_value={"saved": True, "page_id": None}):
            result = pipeline.run_product_reviews()
        self.assertEqual(5, result["inspected"])
        self.assertEqual(2, result["evidence_skipped"])
        self.assertEqual(3, result["review_slots_used"])
        self.assertEqual(3, result["saved"])
        self.assertEqual(3, gemini.call_count)

    def test_transport_primary_failure_gets_short_cooldown(self):
        days = pipeline._product_review_evidence_defer_days(
            {"primary_fetch_failed": True}, {"blocking_missing": ["primary_source_resolved"]}
        )
        self.assertEqual(1, days)
        normal = pipeline._product_review_evidence_defer_days(
            {"primary_fetch_failed": False}, {"blocking_missing": ["technical_claims_available"]}
        )
        self.assertEqual(pipeline.TRACKING_REVIEW_DAYS, normal)


if __name__ == "__main__":
    unittest.main()
