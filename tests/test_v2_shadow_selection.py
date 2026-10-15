from datetime import datetime, timezone
import inspect

import pytest

import v2_shadow_selection as shadow_selection
from v2_shadow_selection import (
    ShadowConfig,
    deduplicate_candidates,
    normalize_candidate,
    rank_candidates,
    run_shadow_selection,
    screen_candidate,
)


NOW = datetime(2026, 10, 14, 0, 0, tzinfo=timezone.utc)


def _raw_candidate(url, *, title="Candidate", description=None, published_at="2026-10-13T12:00:00+00:00"):
    return {
        "url": url,
        "title": title,
        "description": description
        if description is not None
        else "Concrete release evidence with enough detail for deterministic shadow screening and comparison.",
        "published_at": published_at,
    }


def test_normalize_candidate_builds_stable_identity_and_contract():
    raw = {
        "primary_url": "https://example.com/item?utm_source=test",
        "title": "Example launch",
        "description": "A concrete product update with enough detail to evaluate.",
        "published_at": "2026-10-13T12:00:00+00:00",
    }

    result = normalize_candidate(raw, provider="official", acquired_at=NOW)

    assert result["candidate_identity"] == "https://example.com/item"
    assert result["provider"] == "official"
    assert result["primary_url"] == "https://example.com/item?utm_source=test"
    assert result["title"] == "Example launch"
    assert result["description"].startswith("A concrete product update")
    assert result["source_timestamp"] == "2026-10-13T12:00:00+00:00"
    assert result["acquired_at"] == NOW.isoformat()


def test_normalize_candidate_rejects_missing_identity_inputs():
    with pytest.raises(ValueError, match="candidate"):
        normalize_candidate(
            {"description": "No title and no URL"},
            provider="broken",
            acquired_at=NOW,
        )


def test_deduplicate_candidates_collapses_tracking_variants_deterministically():
    first = normalize_candidate(
        {
            "url": "https://example.com/item?utm_campaign=a",
            "title": "First",
            "description": "First description with concrete evidence.",
        },
        provider="one",
        acquired_at=NOW,
    )
    second = normalize_candidate(
        {
            "url": "https://example.com/item?ref=feed",
            "title": "Second",
            "description": "Second description with different words.",
        },
        provider="two",
        acquired_at=NOW,
    )

    deduped = deduplicate_candidates([first, second])

    assert len(deduped) == 1
    assert deduped[0]["title"] == "First"
    assert deduped[0]["candidate_identity"] == "https://example.com/item"


def test_screen_candidate_is_deterministic_and_explains_eligibility():
    candidate = normalize_candidate(
        {
            "url": "https://openai.com/index/example",
            "title": "Documented model update",
            "description": (
                "Official release information describing concrete behavior, availability, "
                "and implementation details for decision makers."
            ),
            "published_at": "2026-10-13T12:00:00+00:00",
        },
        provider="OfficialVendor",
        acquired_at=NOW,
    )

    first = screen_candidate(candidate, now=NOW)
    second = screen_candidate(candidate, now=NOW)

    assert first == second
    assert isinstance(first["screening_score"], int)
    assert first["eligible"] is True
    assert first["screening_reasons"]
    assert all(isinstance(reason, str) for reason in first["screening_reasons"])


def test_rank_candidates_breaks_equal_scores_by_identity():
    a = normalize_candidate(
        {
            "url": "https://example.com/a",
            "title": "Same quality A",
            "description": "A description long enough to receive the same completeness score.",
        },
        provider="feed",
        acquired_at=NOW,
    )
    b = normalize_candidate(
        {
            "url": "https://example.com/b",
            "title": "Same quality B",
            "description": "B description long enough to receive the same completeness score.",
        },
        provider="feed",
        acquired_at=NOW,
    )

    ranked = rank_candidates([b, a], now=NOW)

    assert [item["candidate_identity"] for item in ranked] == [
        "https://example.com/a",
        "https://example.com/b",
    ]


def test_shadow_config_has_bounded_defaults():
    config = ShadowConfig()

    assert config.max_candidates_per_provider == 10
    assert config.max_deep_dive_attempts == 1
    assert config.min_screening_score == 40


def test_shadow_run_bounds_candidates_and_isolates_provider_failure():
    deep_dive_calls = []

    def broken_provider():
        raise RuntimeError("provider unavailable")

    def good_provider():
        return [
            _raw_candidate("https://example.com/a", title="A"),
            _raw_candidate("https://example.com/b", title="B"),
            _raw_candidate("https://example.com/c", title="C"),
        ]

    def deep_dive(candidate):
        deep_dive_calls.append(candidate["candidate_identity"])
        return {"evidence_sufficient": True}

    report = run_shadow_selection(
        providers={"broken": broken_provider, "good": good_provider},
        deep_dive=deep_dive,
        config=ShadowConfig(max_candidates_per_provider=2),
        now=NOW,
        run_id="v2-001-bounded",
        v1_reference=None,
    )

    assert report["mode"] == "shadow"
    assert report["actual_calls"]["provider"] == 2
    assert report["provider_statuses"]["broken"]["status"] == "failure"
    assert report["provider_statuses"]["good"]["accepted_count"] == 2
    assert report["acquired_candidate_count"] == 2
    assert report["normalized_candidate_count"] == 2
    assert report["deep_dive_attempted_count"] == 1
    assert len(deep_dive_calls) == 1
    assert report["v2_selected_candidate_identity"] == deep_dive_calls[0]
    assert report["comparison_status"] == "unavailable"
    assert report["failure_category"] is None


def test_shadow_run_with_zero_eligible_candidates_skips_deep_dive():
    def provider():
        return [
            _raw_candidate(
                "https://example.com/thin",
                title="Thin",
                description="",
                published_at=None,
            )
        ]

    def should_not_run(_candidate):
        raise AssertionError("deep dive must not run")

    report = run_shadow_selection(
        providers={"feed": provider},
        deep_dive=should_not_run,
        config=ShadowConfig(),
        now=NOW,
        run_id="v2-001-no-eligible",
        v1_reference="https://example.com/v1",
    )

    assert report["deep_dive_attempted_count"] == 0
    assert report["actual_calls"]["deep_dive"] == 0
    assert report["v2_selected_candidate_identity"] is None
    assert report["comparison_status"] == "v2_no_winner"
    assert report["failure_category"] == "insufficient_evidence"


def test_shadow_run_never_falls_back_to_second_candidate_after_insufficient_deep_dive():
    calls = []

    def provider():
        return [
            _raw_candidate("https://example.com/a", title="A"),
            _raw_candidate("https://example.com/b", title="B"),
        ]

    def insufficient(candidate):
        calls.append(candidate["candidate_identity"])
        return {"evidence_sufficient": False}

    report = run_shadow_selection(
        providers={"feed": provider},
        deep_dive=insufficient,
        config=ShadowConfig(),
        now=NOW,
        run_id="v2-001-one-shot",
        v1_reference="https://example.com/a",
    )

    assert calls == ["https://example.com/a"]
    assert report["deep_dive_attempted_count"] == 1
    assert report["actual_calls"]["deep_dive"] == 1
    assert report["deep_dive_result_category"] == "insufficient_evidence"
    assert report["v2_selected_candidate_identity"] is None
    assert report["comparison_status"] == "v2_no_winner"
    assert report["failure_category"] == "insufficient_evidence"


@pytest.mark.parametrize(
    ("v1_reference", "expected_status"),
    [
        ("https://example.com/a?utm_source=v1", "same"),
        ("https://example.com/other", "different"),
        (None, "unavailable"),
    ],
)
def test_shadow_run_success_comparison_statuses(v1_reference, expected_status):
    report = run_shadow_selection(
        providers={"feed": lambda: [_raw_candidate("https://example.com/a", title="A")]},
        deep_dive=lambda _candidate: {"evidence_sufficient": True},
        config=ShadowConfig(),
        now=NOW,
        run_id="v2-001-compare",
        v1_reference=v1_reference,
    )

    assert report["v2_selected_candidate_identity"] == "https://example.com/a"
    assert report["comparison_status"] == expected_status
    assert report["failure_category"] is None


def test_shadow_report_contract_is_machine_readable_and_has_no_write_callbacks():
    signature = inspect.signature(run_shadow_selection)
    forbidden_params = {
        "persist",
        "writer",
        "notion",
        "note",
        "publish",
        "ready_state",
        "economic_state",
        "delivery_ledger",
    }
    assert forbidden_params.isdisjoint(signature.parameters)

    report = run_shadow_selection(
        providers={"official": lambda: [_raw_candidate("https://example.com/a", title="A")]},
        deep_dive=lambda _candidate: {"evidence_sufficient": True},
        config=ShadowConfig(max_candidates_per_provider=3, max_deep_dive_attempts=1, min_screening_score=40),
        now=NOW,
        run_id="v2-001-report",
    )

    assert report["run_id"] == "v2-001-report"
    assert report["timestamp"] == NOW.isoformat()
    assert report["mode"] == "shadow"
    assert report["provider_statuses"]["official"]["status"] == "success"
    assert report["deduplicated_candidate_count"] == 1
    assert report["screened_candidate_count"] == 1
    assert report["screening"][0]["candidate_identity"] == "https://example.com/a"
    assert report["budgets"] == {
        "max_candidates_per_provider": 3,
        "max_deep_dive_attempts": 1,
        "min_screening_score": 40,
    }
    assert report["actual_calls"] == {"provider": 1, "deep_dive": 1}


def test_selection_value_scores_four_dimensions_once():
    candidate = {
        "title": "AI agent API launch for enterprise automation",
        "description": "New pricing and deployment support improves business workflow integration.",
    }

    score, reasons = shadow_selection.score_selection_value(candidate)

    assert score == 60
    assert reasons == [
        "ai_relevance",
        "decision_value",
        "change_novelty",
        "applied_reader_value",
    ]


def test_selection_value_requires_ai_relevance_for_other_dimensions():
    candidate = {
        "title": "Enterprise pricing launch",
        "description": "New API pricing and deployment workflow for customers.",
    }

    assert shadow_selection.score_selection_value(candidate) == (0, [])


def test_selection_value_uses_word_boundaries_for_ai_token():
    candidate = {
        "title": "Email retail launch pricing",
        "description": "Enterprise availability update for customer workflow.",
    }

    assert shadow_selection.score_selection_value(candidate) == (0, [])


def test_selection_value_does_not_treat_bare_model_as_ai():
    candidate = {
        "title": "New enterprise business model launch",
        "description": "A pricing model update for customer deployment.",
    }

    assert shadow_selection.score_selection_value(candidate) == (0, [])


def test_selection_value_does_not_inflate_repeated_keywords():
    candidate = {
        "title": "AI AI AI API API launch launch automation automation",
        "description": "Enterprise pricing deployment workflow integration release release.",
    }

    score, reasons = shadow_selection.score_selection_value(candidate)

    assert score == 60
    assert reasons == [
        "ai_relevance",
        "decision_value",
        "change_novelty",
        "applied_reader_value",
    ]


def test_selection_value_is_case_insensitive_and_deterministic():
    candidate = {
        "title": "LlM API RELEASE",
        "description": "ENTERPRISE deployment improves CODING workflow.",
    }

    first = shadow_selection.score_selection_value(candidate)
    second = shadow_selection.score_selection_value(candidate)

    assert first == second == (
        60,
        ["ai_relevance", "decision_value", "change_novelty", "applied_reader_value"],
    )


def test_selection_value_applied_research_can_score_high():
    candidate = {
        "title": "AI inference method reduces deployment cost",
        "description": "New benchmark improvement with practical implementation for production deployment.",
    }

    score, reasons = shadow_selection.score_selection_value(candidate)

    assert score >= 45
    assert "ai_relevance" in reasons
    assert "decision_value" in reasons
    assert "applied_reader_value" in reasons


def test_rank_prefers_shorter_high_value_ai_change_over_long_specialist_abstract():
    specialist = normalize_candidate(
        {
            "url": "https://example.com/a-specialist-research",
            "title": "AI diffusion method for lattice field theory",
            "description": (
                "We derive a diffusion formulation for lattice field theory with mathematical "
                "analysis of sampling operators, asymptotic estimators, and theoretical convergence."
            ),
            "published_at": "2026-10-13T12:00:00+00:00",
        },
        provider="ArXiv",
        acquired_at=NOW,
    )
    product_change = normalize_candidate(
        {
            "url": "https://example.com/z-product-change",
            "title": "AI API launch cuts enterprise pricing",
            "description": "New release adds deployment workflow integration for customers.",
            "published_at": "2026-10-13T12:00:00+00:00",
        },
        provider="HackerNews",
        acquired_at=NOW,
    )

    ranked = rank_candidates([specialist, product_change], now=NOW)

    assert ranked[0]["candidate_identity"] == "https://example.com/z-product-change"


def test_rank_allows_applied_arxiv_research_to_beat_generic_ai_news():
    generic_news = normalize_candidate(
        {
            "url": "https://example.com/a-generic-news",
            "title": "AI update announced",
            "description": "A new AI update was announced with general information about recent developments.",
            "published_at": "2026-10-13T12:00:00+00:00",
        },
        provider="HackerNews",
        acquired_at=NOW,
    )
    applied_research = normalize_candidate(
        {
            "url": "https://example.com/z-applied-research",
            "title": "AI inference benchmark reduces deployment cost",
            "description": "New improvement includes practical implementation for production deployment workflow.",
            "published_at": "2026-10-13T12:00:00+00:00",
        },
        provider="ArXiv",
        acquired_at=NOW,
    )

    ranked = rank_candidates([generic_news, applied_research], now=NOW)

    assert ranked[0]["candidate_identity"] == "https://example.com/z-applied-research"


def test_rank_equal_selection_value_falls_back_to_screening_score():
    stronger_evidence = normalize_candidate(
        {
            "url": "https://example.com/z-stronger-evidence",
            "title": "AI API launch",
            "description": "Enterprise automation workflow integration with deployment availability and pricing details.",
            "published_at": "2026-10-13T12:00:00+00:00",
        },
        provider="feed",
        acquired_at=NOW,
    )
    thinner_evidence = normalize_candidate(
        {
            "url": "https://example.com/a-thinner-evidence",
            "title": "AI API launch",
            "description": "Enterprise automation workflow deployment.",
            "published_at": "2026-10-13T12:00:00+00:00",
        },
        provider="feed",
        acquired_at=NOW,
    )

    ranked = rank_candidates([thinner_evidence, stronger_evidence], now=NOW)

    assert shadow_selection.score_selection_value(stronger_evidence) == shadow_selection.score_selection_value(thinner_evidence)
    assert ranked[0]["candidate_identity"] == "https://example.com/z-stronger-evidence"


def test_existing_screening_score_contract_stays_exactly_90():
    candidate = normalize_candidate(
        {
            "url": "https://openai.com/index/example",
            "title": "Documented model update",
            "description": (
                "Official release information describing concrete behavior, availability, "
                "and implementation details for decision makers."
            ),
            "published_at": "2026-10-13T12:00:00+00:00",
        },
        provider="OfficialVendor",
        acquired_at=NOW,
    )

    result = screen_candidate(candidate, now=NOW)

    assert result["screening_score"] == 90
    assert result["eligible"] is True
