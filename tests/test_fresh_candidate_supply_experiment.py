from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import fresh_candidate_supply_experiment as supply


def _repo(name, url):
    return {"nameWithOwner": name, "url": url, "description": name, "stargazerCount": 200,
            "pushedAt": "2026-09-30T00:00:00Z", "licenseInfo": {"spdxId": "MIT"}}


def test_query_protocol_is_frozen_to_three_bounded_30_day_cohorts():
    rows = supply.queries(now=datetime(2026, 9, 30, 12, tzinfo=timezone.utc))
    assert [label for label, _ in rows] == ["baseline", "generative_ai", "large_language_model"]
    assert len(rows) == supply.MAX_GITHUB_QUERY_CALLS == 3
    assert all("stars:>100" in query and "pushed:>2026-08-31" in query for _, query in rows)


def test_interleave_prevents_saturated_baseline_from_consuming_all_50_slots():
    cohorts = []
    for label, _topic in supply.GITHUB_COHORTS:
        cohorts.append((label, [
            {"url": f"https://example.invalid/{label}/{i}", "source": "GitHub"}
            for i in range(50)
        ]))
    chosen, metrics = supply.interleave_unique(
        cohorts, identity=lambda row: {row["url"]}, cap=50
    )
    first = [row["url"].split("/")[-2] for row in chosen[:6]]
    assert first == ["baseline", "generative_ai", "large_language_model"] * 2
    assert len(chosen) == 50
    assert sum(row["unique_presented"] for row in metrics.values()) == 50


def test_interleave_dedupes_cross_cohort_identity_without_increasing_presented_cap():
    shared = {"url": "https://example.invalid/shared"}
    cohorts = [
        ("baseline", [shared, {"url": "https://example.invalid/a"}]),
        ("generative_ai", [shared, {"url": "https://example.invalid/b"}]),
        ("large_language_model", [{"url": "https://example.invalid/c"}]),
    ]
    chosen, metrics = supply.interleave_unique(
        cohorts, identity=lambda row: {row["url"]}, cap=50
    )
    assert [row["url"] for row in chosen].count("https://example.invalid/shared") == 1
    assert len(chosen) == 4
    assert metrics["generative_ai"]["intra_cohort_deduped"] == 1


def test_fetcher_uses_exactly_three_source_queries_and_never_scores():
    requested = []
    datasets = {}
    for idx, (label, query) in enumerate(supply.queries(
        now=datetime(2026, 9, 30, tzinfo=timezone.utc)
    )):
        datasets[query] = [_repo(label, f"https://example.invalid/{idx}")]

    def fetch_page(query, first):
        requested.append((query, first))
        return datasets[query]

    def normalize_item(**kwargs):
        return {
            "source": kwargs["source"],
            "nameWithOwner": kwargs["name"],
            "url": kwargs["url"],
            "description": kwargs["description"],
            "engagement": kwargs["engagement"],
            "licenseInfo": kwargs["license_info"],
            "publishedAt": kwargs["published_at"],
        }

    pipeline = SimpleNamespace(
        normalize_item=normalize_item,
        candidate_identity_urls=lambda row: {row["url"]},
    )
    capture = {}
    fetch = supply.make_fetcher(
        pipeline, capture=capture, fetch_page=fetch_page,
        now=datetime(2026, 9, 30, tzinfo=timezone.utc),
    )
    out = fetch(50)
    assert len(out) == 3
    assert len(requested) == 3
    assert all(first == 50 for _, first in requested)
    assert capture["protocol"] == supply.PROTOCOL_ID
    assert capture["github_graphql_queries"] == 3
    assert capture["github_presented_limit"] == 50
    assert all("score" not in row for row in out)


def test_fetcher_fails_closed_on_unbounded_or_malformed_cohort():
    pipeline = SimpleNamespace(
        normalize_item=lambda **kwargs: kwargs,
        candidate_identity_urls=lambda row: {row["url"]},
    )
    too_many = [_repo(str(i), f"https://example.invalid/{i}") for i in range(51)]
    fetch = supply.make_fetcher(
        pipeline, capture={}, fetch_page=lambda q, first: too_many,
        now=datetime(2026, 9, 30, tzinfo=timezone.utc),
    )
    with pytest.raises(RuntimeError, match="unbounded"):
        fetch(50)
    with pytest.raises(RuntimeError, match="cap exceeded"):
        fetch(51)
