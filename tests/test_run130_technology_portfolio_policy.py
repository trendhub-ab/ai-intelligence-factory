from __future__ import annotations

from datetime import datetime, timezone

import inventory_bootstrap as ib
from technology_portfolio_policy import (
    balanced_plan_candidates,
    portfolio_base_priority,
    portfolio_utility_score,
    technology_layer,
)


def rec(
    name: str,
    *,
    source=("GitHub",),
    category="OTHER",
    screening=80,
    summary="",
    url="https://github.com/example/project",
):
    return ib.TechnologyRecord(
        page_id=name,
        name=name,
        canonical_entity_id=f"id:{name}",
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


def test_github_is_not_a_large_automatic_priority_bonus():
    now = datetime(2026, 8, 28, tzinfo=timezone.utc)
    github = rec(
        "generic-template",
        source=("GitHub",),
        category="DEVTOOLS",
        summary="A generic developer template and examples repository for projects.",
    )
    hn = rec(
        "agent-observability",
        source=("HackerNews",),
        category="AGENT",
        summary="Agent observability platform with tracing, evaluation, tool use and security controls.",
        url="https://example.com/agent-observability",
    )
    github_base, _ = portfolio_base_priority(github, now)
    hn_base, _ = portfolio_base_priority(hn, now)
    # Source alone must not create the old ~30 point GitHub advantage.
    assert abs(github_base - hn_base) < 10


def test_generic_repo_is_penalized_but_strategic_repo_is_not():
    generic = rec(
        "awesome-ai-list",
        category="DEVTOOLS",
        summary="An awesome list of tutorials, examples and beginner learning resources.",
    )
    strategic = rec(
        "agent-gateway",
        category="AGENT",
        summary="MCP agent gateway with tool use, tracing, sandbox security and evaluation.",
    )
    g_score, g_reasons = portfolio_utility_score(generic, "DEVTOOLS", "PRACTICAL")
    s_score, s_reasons = portfolio_utility_score(strategic, "AGENT", "PRACTICAL")
    assert s_score > g_score
    assert "generic_github_repo_without_decision_signal:-10" in g_reasons
    assert any("strategic_technology_signals" in r for r in s_reasons)


def test_three_layers_are_available_without_forcing_popular_ai_quota():
    applied = rec(
        "technical-product",
        source=("ProductHunt",),
        category="PRODUCT",
        summary="AI platform with agent orchestration and evaluation.",
        url="https://example.com/product",
    )
    practical = rec(
        "mcp-security",
        category="SECURITY",
        summary="MCP security guardrail for tool use and sandbox policy enforcement.",
    )
    deep = rec(
        "new-reasoning-paper",
        source=("ArXiv",),
        category="MODEL",
        summary="Research paper on a new reasoning method without a released implementation.",
        url="https://arxiv.org/abs/2608.12345",
    )
    assert technology_layer(applied, "PRODUCT", "PRACTICAL")[0] == "APPLIED_AI"
    assert technology_layer(practical, "SECURITY", "RISK")[0] == "PRACTICAL_TECH"
    assert technology_layer(deep, "MODEL", "RESEARCH")[0] == "DEEP_TECH"


def test_balanced_plan_does_not_fill_prefix_with_one_source():
    records = [
        rec(
            f"repo-{i}",
            source=("GitHub",),
            category="DEVTOOLS",
            screening=90 - i,
            summary="Generic developer library and repository.",
        )
        for i in range(8)
    ] + [
        rec(
            "security-risk",
            source=("HackerNews",),
            category="SECURITY",
            screening=82,
            summary="AI agent security threat involving tool use, sandboxing and prompt injection.",
            url="https://example.com/security",
        ),
        rec(
            "research-reasoning",
            source=("ArXiv",),
            category="MODEL",
            screening=81,
            summary="Research study of a new reasoning method and model evaluation benchmark.",
            url="https://arxiv.org/abs/2608.00001",
        ),
        rec(
            "applied-agent",
            source=("ProductHunt",),
            category="PRODUCT",
            screening=80,
            summary="Agent platform with orchestration, tracing and evaluation.",
            url="https://example.com/applied-agent",
        ),
    ]
    planned = balanced_plan_candidates(
        ib,
        records,
        limit=6,
        max_source_share=0.45,
        now=datetime(2026, 8, 28, tzinfo=timezone.utc),
    )
    sources = [p.source[0] for p in planned]
    assert sources.count("GitHub") <= 3
    assert len(set(sources)) >= 3
    assert any(any(r.startswith("technology_layer:") for r in p.reasons) for p in planned)
