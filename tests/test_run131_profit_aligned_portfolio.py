from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import inventory_bootstrap as ib
from daily_portfolio_review import daily_review_bucket, plan_daily_review_allowlist
from technology_portfolio_policy import (
    infer_portfolio_category,
    infer_portfolio_lane,
    portfolio_base_priority,
    rank_portfolio_records,
    technology_layer,
)


NOW = datetime(2026, 8, 28, tzinfo=timezone.utc)


def rec(
    name: str,
    *,
    source=("GitHub",),
    category="OTHER",
    screening=80,
    summary="",
    url="https://github.com/example/project",
    entity_id: str | None = None,
):
    return ib.TechnologyRecord(
        page_id=name,
        name=name,
        canonical_entity_id=entity_id or f"id:{name}",
        primary_url=url,
        source=tuple(source),
        category=category,
        screening_score=screening,
        source_summary=summary,
        published_at="2026-08-20T00:00:00+00:00",
        analyzed_at="2026-08-20T00:00:00+00:00",
        next_review=None,
        assessment_state="LEGACY_PENDING",
        entity_resolution_status="RESOLVED",
        tracking_status="ACTIVE",
        tracking_eligibility=True,
        adoption_score=None,
        adoption_status="",
        evidence_confidence="",
        production_readiness="",
        main_risk="",
        best_for="",
        avoid_for="",
        short_rationale="",
        primary_evidence_urls="",
        last_reviewed=None,
    )


def state(
    entity_id: str,
    *,
    source=("GitHub",),
    category="AGENT",
    screening=80,
    summary="Agent orchestration platform with tracing and evaluation.",
    assessment_state="SCREENED",
    next_review=None,
):
    return {
        "page_id": f"page:{entity_id}",
        "technology_name": entity_id,
        "canonical_entity_id": entity_id,
        "primary_url": "https://github.com/example/project" if "GitHub" in source else "https://arxiv.org/abs/2608.12345",
        "sources": list(source),
        "category": category,
        "screening_score": screening,
        "source_summary": summary,
        "first_seen": "2026-08-20T00:00:00+00:00",
        "last_reviewed": None,
        "next_review": next_review,
        "assessment_state": assessment_state,
        "entity_status": "RESOLVED",
        "tracking_status": "ACTIVE",
        "tracking_eligibility": True,
        "adoption_score": None,
        "adoption_status": "",
        "evidence_confidence": "",
        "production_readiness": "",
        "main_risk": "",
        "best_for": "",
        "avoid_for": "",
        "short_rationale": "",
        "evidence_urls": [],
    }


class Run131ProfitAlignedPortfolioTests(unittest.TestCase):
    def test_materially_weaker_candidate_is_never_force_promoted_for_diversity(self):
        records = [
            rec(
                "strong-agent-a",
                category="AGENT",
                screening=96,
                summary="Agent orchestration platform with MCP, tracing, evaluation and sandbox security.",
            ),
            rec(
                "strong-agent-b",
                category="AGENT",
                screening=94,
                summary="Agent gateway with MCP tool use, observability, evaluation and security controls.",
            ),
            rec(
                "weak-research",
                source=("ArXiv",),
                category="MODEL",
                screening=35,
                summary="Research paper about a speculative model method.",
                url="https://arxiv.org/abs/2608.00001",
            ),
        ]
        ranked = rank_portfolio_records(ib, records, limit=2, tolerance=8, now=NOW)
        self.assertEqual([x.name for x in ranked], ["strong-agent-a", "strong-agent-b"])

    def test_producthunt_source_alone_never_implies_applied_ai(self):
        item = rec(
            "research-notes",
            source=("ProductHunt",),
            category="OTHER",
            summary="A collection of notes about computing systems.",
            url="https://example.com/notes",
        )
        category, _ = infer_portfolio_category(ib, item)
        lane, _ = infer_portfolio_lane(ib, item, category)
        layer, _ = technology_layer(item, category, lane)
        self.assertNotEqual(layer, "APPLIED_AI")

    def test_producthunt_can_be_applied_when_content_is_an_actual_technical_product(self):
        item = rec(
            "agent-product",
            source=("ProductHunt",),
            category="OTHER",
            summary="An agent platform for orchestration, tracing and evaluation.",
            url="https://example.com/agent-product",
        )
        category, _ = infer_portfolio_category(ib, item)
        lane, _ = infer_portfolio_lane(ib, item, category)
        layer, _ = technology_layer(item, category, lane)
        self.assertEqual(layer, "APPLIED_AI")

    def test_token_boundaries_prevent_rag_and_app_false_positives(self):
        item = rec(
            "Ragged Application Fragments",
            source=("ProductHunt",),
            category="OTHER",
            summary="A collection of application fragments for layout experiments.",
            url="https://example.com/fragments",
        )
        category, _ = infer_portfolio_category(ib, item)
        lane, _ = infer_portfolio_lane(ib, item, category)
        layer, _ = technology_layer(item, category, lane)
        self.assertEqual(category, "OTHER")
        self.assertNotEqual(layer, "APPLIED_AI")

    def test_multi_source_order_does_not_change_score_or_layer(self):
        a = rec(
            "multi-a", source=("GitHub", "HackerNews"), category="AGENT",
            summary="Agent gateway with MCP tracing and evaluation.", entity_id="multi-a",
        )
        b = rec(
            "multi-b", source=("HackerNews", "GitHub"), category="AGENT",
            summary="Agent gateway with MCP tracing and evaluation.", entity_id="multi-b",
        )
        score_a, _ = portfolio_base_priority(a, NOW)
        score_b, _ = portfolio_base_priority(b, NOW)
        cat_a, _ = infer_portfolio_category(ib, a)
        cat_b, _ = infer_portfolio_category(ib, b)
        lane_a, _ = infer_portfolio_lane(ib, a, cat_a)
        lane_b, _ = infer_portfolio_lane(ib, b, cat_b)
        self.assertEqual(score_a, score_b)
        self.assertEqual(technology_layer(a, cat_a, lane_a)[0], technology_layer(b, cat_b, lane_b)[0])

    def test_daily_eligibility_preserves_history_recovery_and_cooldown(self):
        history = state("history", assessment_state="HISTORY_PENDING")
        legacy = state("legacy", assessment_state="LEGACY_PENDING")
        future = state(
            "future",
            assessment_state="ASSESSED",
            next_review=(NOW + timedelta(days=2)).isoformat(),
        )
        self.assertEqual(daily_review_bucket(history, NOW), "HISTORY_PENDING")
        self.assertEqual(daily_review_bucket(legacy, NOW), "PORTFOLIO")
        self.assertIsNone(daily_review_bucket(future, NOW))

    def test_daily_allowlist_uses_portfolio_quality_not_source_quota(self):
        states = [
            state(
                "strong-a", screening=96,
                summary="Agent orchestration platform with MCP, tracing, evaluation and sandbox security.",
            ),
            state(
                "strong-b", screening=94,
                summary="Agent gateway with MCP tool use, observability, evaluation and security controls.",
            ),
            state(
                "weak-paper", source=("ArXiv",), category="MODEL", screening=35,
                summary="Research paper about a speculative model method.",
            ),
        ]
        allowlist = plan_daily_review_allowlist(states, scan_limit=2, now=NOW)
        self.assertEqual(allowlist, ["strong-a", "strong-b"])

    def test_daily_workflow_separates_article_and_portfolio_product_review(self):
        text = Path(".github/workflows/daily.yml").read_text(encoding="utf-8")
        self.assertIn('PRODUCT_REVIEW_MAX_PER_RUN: "0"', text)
        self.assertIn("python daily_portfolio_review.py", text)
        self.assertIn('PORTFOLIO_DIVERSITY_TOLERANCE: "8"', text)

    def test_bootstrap_workflow_no_longer_exposes_hard_source_cap(self):
        text = Path(".github/workflows/inventory-bootstrap.yml").read_text(encoding="utf-8")
        self.assertNotIn("max_source_share:", text)
        self.assertNotIn("--max-source-share", text)
        self.assertIn('PORTFOLIO_DIVERSITY_TOLERANCE: "8"', text)

    def test_run131_adds_no_gemini_call_site(self):
        policy = Path("technology_portfolio_policy.py").read_text(encoding="utf-8")
        daily = Path("daily_portfolio_review.py").read_text(encoding="utf-8")
        self.assertNotIn("genai.Client", policy + daily)
        self.assertNotIn("_generate_via_chat", policy + daily)
        self.assertNotIn("generate_content(", policy + daily)


if __name__ == "__main__":
    unittest.main()
