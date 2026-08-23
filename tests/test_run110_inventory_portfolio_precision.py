import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import inventory_bootstrap as ib

NOW = datetime(2026, 8, 23, tzinfo=timezone.utc)


def rec(name, source=("GitHub",), url="https://github.com/org/tool", summary="", score=85, category="OTHER", entity=None):
    return ib.TechnologyRecord(
        page_id=name, name=name, canonical_entity_id=entity or f"x:{name}", primary_url=url,
        source=source, category=category, screening_score=score,
        source_summary=summary or name, published_at="2026-08-22T00:00:00Z",
        analyzed_at="2026-08-22T00:00:00Z", next_review=None,
        assessment_state="LEGACY_PENDING", entity_resolution_status="RESOLVED",
        tracking_status="ACTIVE", tracking_eligibility=False, adoption_score=None,
        adoption_status="", evidence_confidence="", production_readiness="",
        main_risk="", best_for="", avoid_for="", short_rationale="",
        primary_evidence_urls="", last_reviewed=None,
    )


class Run110InventoryPortfolioPrecisionTests(unittest.TestCase):
    def test_legacy_other_gets_planning_category_without_mutation(self):
        r = rec("mlflow/mlflow", summary="Open source MLOps platform for experiment tracking, model registry and deployment pipelines")
        category, reasons = ib.infer_planning_category(r)
        self.assertEqual("DEVTOOLS", category)
        self.assertEqual("OTHER", r.category)
        self.assertIn("planning_category:DEVTOOLS", reasons)

    def test_security_paper_is_risk_lane_not_generic_research(self):
        r = rec(
            "When State Becomes an Attack Surface",
            source=("ArXiv",), url="https://arxiv.org/abs/2608.16806",
            summary="State-semantic injection attack against LLM-driven embodied agents and security defenses",
        )
        cat, _ = ib.infer_planning_category(r)
        lane, _ = ib.candidate_lane(r, cat)
        self.assertEqual("SECURITY", cat)
        self.assertEqual("RISK", lane)

    def test_practical_repo_outranks_equally_screened_generic_research_for_launch_queue(self):
        tool = rec(
            "zenml-io/zenml",
            summary="Open source MLOps platform and framework for production AI pipelines, deployment and orchestration",
        )
        paper = rec(
            "Grouping the Stochastic Machine",
            source=("ArXiv",), url="https://arxiv.org/abs/2608.19140",
            summary="Research study and empirical analysis of precision metrics for AI systems and models",
        )
        planned = ib.plan_candidates([paper, tool], limit=2, max_source_share=1.0, now=NOW)
        self.assertEqual("zenml-io/zenml", planned[0].name)
        self.assertGreater(planned[0].product_utility_score, planned[1].product_utility_score)

    def test_source_share_is_prefix_aware_for_first_apply_batch(self):
        rows = []
        for i in range(8):
            rows.append(rec(
                f"Paper{i}", source=("ArXiv",), url=f"https://arxiv.org/abs/2608.{19000+i}",
                summary="Research study of model reasoning and training", score=95-i,
            ))
        for i in range(6):
            rows.append(rec(
                f"tool{i}", source=("GitHub",), url=f"https://github.com/org/tool{i}",
                summary="Open source developer tool SDK platform for production AI workflow and deployment", score=85-i,
            ))
        planned = ib.plan_candidates(rows, limit=10, max_source_share=.60, now=NOW)
        first4 = planned[:4]
        counts = {}
        for x in first4:
            src = x.source[0]
            counts[src] = counts.get(src, 0) + 1
        self.assertLessEqual(max(counts.values()), 3, first4)
        self.assertGreaterEqual(len(counts), 2, first4)

    def test_soft_portfolio_penalty_avoids_single_lane_monoculture_when_close_alternatives_exist(self):
        rows = [
            rec("mlflow/mlflow", summary="MLOps platform SDK experiment tracking model deployment pipeline"),
            rec("huggingface/datasets", summary="Dataset library and data platform for AI model training and workflows"),
            rec("DocsGPT", summary="RAG developer tool for retrieval knowledge base and LLM applications"),
            rec("Security paper", source=("ArXiv",), url="https://arxiv.org/abs/2608.16806", summary="Security attack injection threat for LLM agents"),
            rec("Agent paper", source=("ArXiv",), url="https://arxiv.org/abs/2608.16801", summary="Empirical study measuring coordination in multi-agent AI coding"),
            rec("Vision paper", source=("ArXiv",), url="https://arxiv.org/abs/2608.14530", summary="Research model for image vision rendering geometry"),
        ]
        planned = ib.plan_candidates(rows, limit=4, max_source_share=.60, now=NOW)
        self.assertGreaterEqual(len({x.candidate_lane for x in planned}), 2, planned)
        self.assertGreaterEqual(len({x.planning_category for x in planned}), 2, planned)
        self.assertTrue(any(x.candidate_lane == "PRACTICAL" for x in planned))
        self.assertTrue(any(x.candidate_lane == "RISK" for x in planned))

    def test_planning_category_never_changes_authoritative_assessment_category(self):
        r = rec("vespa-engine/vespa", summary="AI search platform, vector retrieval database and serving engine")
        planned = ib.plan_candidates([r], limit=1, now=NOW)
        self.assertEqual("OTHER", planned[0].category)
        self.assertNotEqual("OTHER", planned[0].planning_category)
        self.assertEqual("OTHER", r.category)

    def test_plan_output_exposes_why_portfolio_order_changed(self):
        r = rec("argilla-io/argilla", summary="Open source data platform and developer tool for AI dataset curation and model workflows")
        p = ib.plan_candidates([r], limit=1, now=NOW)[0]
        self.assertIsInstance(p.product_utility_score, float)
        self.assertIsInstance(p.portfolio_priority, float)
        self.assertTrue(any("planning_category" in reason for reason in p.reasons))
        self.assertTrue(any("lane:" in reason for reason in p.reasons))


if __name__ == "__main__":
    unittest.main()
