from __future__ import annotations

import inspect

import pytest

from v2_official_vendor_acquisition import acquire_official_vendor_candidates


ITEMS = [
    {
        "id": "release-2",
        "url": "https://openai.com/index/release-2",
        "title": "AI API release adds enterprise deployment controls",
        "description": "Official release details new deployment controls and pricing for enterprise customers.",
        "published_at": "2026-10-15T01:00:00+00:00",
    },
    {
        "id": "release-1",
        "url": "https://openai.com/index/release-1?utm_source=feed",
        "title": "AI model release improves production inference",
        "description": "Official release documents a production inference improvement and availability change.",
        "published_at": "2026-10-14T01:00:00+00:00",
    },
]


def test_official_vendor_requires_explicit_allowlisted_endpoint():
    with pytest.raises(ValueError, match="endpoint"):
        acquire_official_vendor_candidates(
            endpoint_url="https://openai.com/index/unknown-feed",
            allowed_endpoints={"https://openai.com/index/ai-feed.json"},
            provider="OpenAI",
            allowed_domains={"openai.com"},
            items=ITEMS,
        )


def test_official_vendor_normalizes_bounded_candidates_with_provenance():
    result = acquire_official_vendor_candidates(
        endpoint_url="https://openai.com/index/ai-feed.json",
        allowed_endpoints={"https://openai.com/index/ai-feed.json"},
        provider="OpenAI",
        allowed_domains={"openai.com"},
        items=ITEMS,
        max_items=1,
    )

    assert len(result) == 1
    candidate = result[0]
    assert candidate == {
        "primary_url": "https://openai.com/index/release-2",
        "title": "AI API release adds enterprise deployment controls",
        "description": "Official release details new deployment controls and pricing for enterprise customers.",
        "published_at": "2026-10-15T01:00:00+00:00",
        "source_family": "official_vendor",
        "provider": "OpenAI",
        "canonical_url": "https://openai.com/index/release-2",
        "upstream_id": "release-2",
    }


def test_official_vendor_skips_malformed_and_nonallowlisted_domains_fail_closed():
    items = [
        {"id": "missing-url", "title": "AI release"},
        {
            "id": "lookalike",
            "url": "https://openai.com.evil.example/release",
            "title": "AI release",
            "description": "Looks official but is not.",
            "published_at": "2026-10-15T01:00:00+00:00",
        },
        ITEMS[0],
    ]

    result = acquire_official_vendor_candidates(
        endpoint_url="https://openai.com/index/ai-feed.json",
        allowed_endpoints={"https://openai.com/index/ai-feed.json"},
        provider="OpenAI",
        allowed_domains={"openai.com"},
        items=items,
    )

    assert [item["upstream_id"] for item in result] == ["release-2"]


def test_official_vendor_is_deterministic_and_deduplicates_by_canonical_url():
    duplicate = dict(ITEMS[1])
    duplicate["id"] = "release-1-duplicate"
    duplicate["url"] = "https://openai.com/index/release-1?ref=duplicate"

    kwargs = dict(
        endpoint_url="https://openai.com/index/ai-feed.json",
        allowed_endpoints={"https://openai.com/index/ai-feed.json"},
        provider="OpenAI",
        allowed_domains={"openai.com"},
        items=[ITEMS[1], duplicate, ITEMS[0]],
        max_items=10,
    )

    first = acquire_official_vendor_candidates(**kwargs)
    second = acquire_official_vendor_candidates(**kwargs)

    assert first == second
    assert [item["upstream_id"] for item in first] == ["release-1", "release-2"]


def test_official_vendor_adapter_exposes_no_production_or_model_write_surface():
    signature = inspect.signature(acquire_official_vendor_candidates)
    forbidden = {
        "notion",
        "note",
        "publish",
        "ready_state",
        "delivery_ledger",
        "gemini",
        "model",
        "writer",
    }
    assert forbidden.isdisjoint(signature.parameters)
