from __future__ import annotations

from datetime import datetime, timezone

import v2_shadow_selection as shadow_selection
from v2_shadow_selection import ShadowConfig, normalize_candidate, run_shadow_selection
from v2_source_portfolio import SourcePortfolioConfig, run_four_source_shadow


NOW = datetime(2026, 10, 15, 3, 0, tzinfo=timezone.utc)


def _candidate(source_family: str, suffix: str = "1") -> dict[str, str]:
    return {
        "url": f"https://example.com/{source_family}/{suffix}",
        "title": "AI API release cuts enterprise deployment cost",
        "description": "New release improves production workflow integration and customer deployment.",
        "published_at": "2026-10-15T01:00:00+00:00",
        "source_family": source_family,
        "canonical_url": f"https://example.com/{source_family}/{suffix}",
        "upstream_id": f"{source_family}-{suffix}",
    }


def test_v2_005b_portfolio_declares_direct_discovery_only_and_retired_families():
    assert shadow_selection.DIRECT_CANDIDATE_SOURCE_FAMILIES == frozenset(
        {"official_vendor", "github", "hacker_news", "arxiv"}
    )
    assert shadow_selection.DISCOVERY_ONLY_SOURCE_FAMILIES == frozenset({"x"})
    assert shadow_selection.RETIRED_SOURCE_FAMILIES == frozenset({"product_hunt"})

    for family in ("official_vendor", "github", "hacker_news", "arxiv"):
        assert shadow_selection.source_family_can_emit_candidate(family) is True
    assert shadow_selection.source_family_can_emit_candidate("x") is False
    assert shadow_selection.source_family_can_emit_candidate("product_hunt") is False
    assert shadow_selection.source_family_can_emit_candidate("unknown") is False


def test_selection_value_is_source_family_neutral_for_identical_content():
    scores = {
        family: shadow_selection.score_selection_value(_candidate(family))
        for family in ("official_vendor", "github", "hacker_news", "arxiv")
    }

    reference = scores["official_vendor"]
    assert all(value == reference for value in scores.values())
    score, reasons = reference
    assert score == 60
    assert reasons == [
        "ai_relevance",
        "decision_value",
        "change_novelty",
        "applied_reader_value",
    ]


def test_normalization_preserves_bounded_source_provenance():
    raw = _candidate("github") | {
        "repository": "openai/openai-python",
        "event_kind": "release",
    }

    normalized = normalize_candidate(raw, provider="GitHub", acquired_at=NOW)

    assert normalized["source_family"] == "github"
    assert normalized["canonical_url"] == "https://example.com/github/1"
    assert normalized["upstream_id"] == "github-1"
    assert normalized["repository"] == "openai/openai-python"
    assert normalized["event_kind"] == "release"


def test_shadow_diagnostics_preserve_source_family_without_production_mutation():
    report = run_shadow_selection(
        providers={"GitHub": lambda: [_candidate("github")]},
        deep_dive=lambda _candidate: {"evidence_sufficient": True},
        config=ShadowConfig(),
        now=NOW,
        run_id="v2-005b-provenance",
    )

    assert report["mode"] == "shadow"
    assert report["screening"][0]["provider"] == "GitHub"
    assert report["screening"][0]["source_family"] == "github"
    assert "notion" not in report
    assert "note" not in report
    assert "publish" not in report


def test_discovery_only_and_retired_sources_fail_closed_when_normalized_directly():
    for family in ("x", "product_hunt"):
        raw = _candidate(family)
        try:
            normalize_candidate(raw, provider=family, acquired_at=NOW)
        except ValueError as exc:
            assert "source family" in str(exc).lower()
        else:
            raise AssertionError(f"{family} must not emit a direct V2 candidate")


def test_four_source_run_has_explicit_total_candidate_budget():
    providers = {
        "official_vendor": lambda: [_candidate("official_vendor", "1"), _candidate("official_vendor", "2")],
        "github": lambda: [_candidate("github", "1"), _candidate("github", "2")],
        "hacker_news": lambda: [_candidate("hacker_news", "1"), _candidate("hacker_news", "2")],
        "arxiv": lambda: [_candidate("arxiv", "1"), _candidate("arxiv", "2")],
    }

    report = run_four_source_shadow(
        providers=providers,
        deep_dive=lambda _candidate: {"evidence_sufficient": True},
        shadow_config=ShadowConfig(max_candidates_per_provider=2),
        portfolio_config=SourcePortfolioConfig(max_total_candidates=3),
        now=NOW,
        run_id="v2-005b-total-budget",
    )

    assert report["budgets"]["max_total_candidates"] == 3
    assert report["budgets"]["source_families"] == [
        "official_vendor",
        "github",
        "hacker_news",
        "arxiv",
    ]
    assert report["acquired_candidate_count"] == 3
    assert report["normalized_candidate_count"] == 3
    assert report["provider_statuses"]["OfficialVendor"]["accepted_count"] == 2
    assert report["provider_statuses"]["GitHub"]["accepted_count"] == 1
    assert report["provider_statuses"]["HackerNews"]["accepted_count"] == 0
    assert report["provider_statuses"]["ArXiv"]["accepted_count"] == 0
    assert report["actual_calls"]["deep_dive"] == 1


def test_source_failure_does_not_consume_other_sources_candidate_budget():
    def fail_official_vendor():
        raise RuntimeError("synthetic source failure")

    providers = {
        "official_vendor": fail_official_vendor,
        "github": lambda: [_candidate("github")],
        "hacker_news": lambda: [_candidate("hacker_news")],
        "arxiv": lambda: [_candidate("arxiv")],
    }

    report = run_four_source_shadow(
        providers=providers,
        deep_dive=lambda _candidate: {"evidence_sufficient": True},
        shadow_config=ShadowConfig(max_candidates_per_provider=1),
        portfolio_config=SourcePortfolioConfig(max_total_candidates=4),
        now=NOW,
        run_id="v2-005b-source-failure-isolation",
    )

    assert report["provider_statuses"]["OfficialVendor"]["status"] == "failure"
    assert report["provider_statuses"]["GitHub"]["normalized_count"] == 1
    assert report["provider_statuses"]["HackerNews"]["normalized_count"] == 1
    assert report["provider_statuses"]["ArXiv"]["normalized_count"] == 1
    assert report["acquired_candidate_count"] == 3
    assert report["normalized_candidate_count"] == 3
    assert report["actual_calls"]["provider"] == 4
    assert report["actual_calls"]["deep_dive"] == 1


def test_four_source_portfolio_rejects_missing_or_unapproved_source_family():
    complete = {
        "official_vendor": lambda: [],
        "github": lambda: [],
        "hacker_news": lambda: [],
        "arxiv": lambda: [],
    }

    missing = dict(complete)
    missing.pop("arxiv")
    try:
        run_four_source_shadow(
            providers=missing,
            deep_dive=lambda _candidate: {"evidence_sufficient": True},
            shadow_config=ShadowConfig(),
            portfolio_config=SourcePortfolioConfig(),
            now=NOW,
            run_id="v2-005b-missing-source",
        )
    except ValueError as exc:
        assert "four-source" in str(exc).lower()
    else:
        raise AssertionError("missing source family must fail closed")

    extra = dict(complete)
    extra["x"] = lambda: []
    try:
        run_four_source_shadow(
            providers=extra,
            deep_dive=lambda _candidate: {"evidence_sufficient": True},
            shadow_config=ShadowConfig(),
            portfolio_config=SourcePortfolioConfig(),
            now=NOW,
            run_id="v2-005b-unapproved-source",
        )
    except ValueError as exc:
        assert "four-source" in str(exc).lower()
    else:
        raise AssertionError("discovery-only source must fail closed")
