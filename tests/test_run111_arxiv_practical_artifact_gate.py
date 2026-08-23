import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import inventory_bootstrap as ib


def rec(name, source=("ArXiv",), url="https://arxiv.org/abs/2608.12345", summary="", evidence=""):
    return ib.TechnologyRecord(
        page_id=name, name=name, canonical_entity_id=f"x:{name}", primary_url=url,
        source=source, category="OTHER", screening_score=95, source_summary=summary,
        published_at="2026-08-22T00:00:00Z", analyzed_at="2026-08-22T00:00:00Z", next_review=None,
        assessment_state="LEGACY_PENDING", entity_resolution_status="RESOLVED", tracking_status="ACTIVE",
        tracking_eligibility=False, adoption_score=None, adoption_status="", evidence_confidence="",
        production_readiness="", main_risk="", best_for="", avoid_for="", short_rationale="",
        primary_evidence_urls=evidence, last_reviewed=None,
    )


class Run111ArxivPracticalArtifactGateTests(unittest.TestCase):
    def test_practical_sounding_arxiv_without_artifact_is_research(self):
        r = rec(
            "Tuning the Stochastic Machine",
            summary="A systems engineer operating model for human-AI engineering with platform workflow deployment and SDK practices",
        )
        cat, _ = ib.infer_planning_category(r)
        lane, reasons = ib.candidate_lane(r, cat)
        self.assertEqual("RESEARCH", lane)
        self.assertIn("lane:RESEARCH_ARXIV_NO_IMPLEMENTATION", reasons)
        self.assertIn("implementation_artifact_missing", reasons)

    def test_arxiv_with_github_evidence_can_be_practical(self):
        r = rec(
            "Deployable Agent System",
            summary="Paper describing an agent SDK and deployment framework",
            evidence="https://github.com/example/deployable-agent",
        )
        cat, _ = ib.infer_planning_category(r)
        lane, reasons = ib.candidate_lane(r, cat)
        self.assertEqual("PRACTICAL", lane)
        self.assertIn("lane:PRACTICAL_ARXIV_IMPLEMENTATION", reasons)
        self.assertTrue(any(x.startswith("implementation_artifact_host:github.com") for x in reasons))

    def test_arxiv_with_huggingface_artifact_can_be_practical(self):
        r = rec(
            "Open Model Toolkit",
            summary="Implementation artifacts: https://huggingface.co/example/toolkit",
        )
        cat, _ = ib.infer_planning_category(r)
        lane, _ = ib.candidate_lane(r, cat)
        self.assertEqual("PRACTICAL", lane)

    def test_security_arxiv_stays_risk_even_without_implementation(self):
        r = rec(
            "When State Becomes an Attack Surface",
            summary="Security attack and vulnerability analysis for LLM agents",
        )
        cat, _ = ib.infer_planning_category(r)
        lane, _ = ib.candidate_lane(r, cat)
        self.assertEqual("RISK", lane)

    def test_github_practical_behavior_is_unchanged(self):
        r = rec(
            "zenml-io/zenml", source=("GitHub",), url="https://github.com/zenml-io/zenml",
            summary="Open source MLOps platform SDK for production AI pipelines",
        )
        cat, _ = ib.infer_planning_category(r)
        lane, reasons = ib.candidate_lane(r, cat)
        self.assertEqual("PRACTICAL", lane)
        self.assertIn("lane:PRACTICAL", reasons)


if __name__ == "__main__":
    unittest.main()
