from candidate_identity import candidate_identity_urls


def test_same_technology_same_event_is_duplicate_by_canonical_identity():
    a = {
        "technology_id": "astra",
        "source": "HackerNews",
        "url": "https://example.com/astra/robotics?utm_source=hn&ref=frontpage",
    }
    b = {
        "technology_id": "astra",
        "source": "ProductHunt",
        "url": "https://example.com/astra/robotics/",
    }

    assert candidate_identity_urls(a) & candidate_identity_urls(b)


def test_same_technology_distinct_official_revision_is_not_duplicate():
    rev1 = {
        "technology_id": "astra",
        "source": "OfficialVendor",
        "url": "https://vendor.example/releases/astra?aif_revision=2026-10-01",
        "primaryUrl": "https://vendor.example/releases/astra",
    }
    rev2 = {
        "technology_id": "astra",
        "source": "OfficialVendor",
        "url": "https://vendor.example/releases/astra?aif_revision=2026-10-10",
        "primaryUrl": "https://vendor.example/releases/astra",
    }

    assert not (candidate_identity_urls(rev1) & candidate_identity_urls(rev2))


def test_same_technology_distinct_material_event_url_is_not_duplicate():
    event_a = {
        "technology_id": "astra",
        "source": "OfficialVendor",
        "url": "https://vendor.example/news/astra-robotics-breakthrough",
    }
    event_b = {
        "technology_id": "astra",
        "source": "OfficialVendor",
        "url": "https://vendor.example/news/astra-api-general-availability",
    }

    assert not (candidate_identity_urls(event_a) & candidate_identity_urls(event_b))


def test_technology_id_is_grouping_metadata_not_article_identity():
    same_event_different_technology_labels = (
        {
            "technology_id": "astra-family",
            "source": "HackerNews",
            "url": "https://example.com/events/launch?gclid=tracking",
        },
        {
            "technology_id": "astra-v2",
            "source": "HackerNews",
            "url": "https://example.com/events/launch",
        },
    )
    distinct_events_same_technology = (
        {
            "technology_id": "astra",
            "source": "HackerNews",
            "url": "https://example.com/events/benchmark",
        },
        {
            "technology_id": "astra",
            "source": "HackerNews",
            "url": "https://example.com/events/commercial-deployment",
        },
    )

    assert candidate_identity_urls(same_event_different_technology_labels[0]) & candidate_identity_urls(
        same_event_different_technology_labels[1]
    )
    assert not (
        candidate_identity_urls(distinct_events_same_technology[0])
        & candidate_identity_urls(distinct_events_same_technology[1])
    )
