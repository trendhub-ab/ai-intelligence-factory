from candidate_identity import candidate_identity_urls


def _official(revision: str, *, title: str = "Astra update") -> dict:
    return {
        "source": "OfficialVendor",
        "technology_id": "astra",
        "nameWithOwner": title,
        "url": f"https://vendor.example/releases/astra?aif_revision={revision}",
        "primaryUrl": "https://vendor.example/releases/astra",
        "sourceDetails": {"official_url": "https://vendor.example/releases/astra"},
    }


def test_same_event_tracking_variants_share_identity():
    left = {
        "source": "HackerNews",
        "technology_id": "astra",
        "url": "https://example.com/astra-robot-control?utm_source=hn",
        "primaryUrl": "https://example.com/astra-robot-control",
    }
    right = {
        "source": "HackerNews",
        "technology_id": "astra",
        "url": "https://example.com/astra-robot-control?ref=homepage",
        "primaryUrl": "https://example.com/astra-robot-control",
    }

    assert candidate_identity_urls(left) & candidate_identity_urls(right)


def test_same_technology_distinct_official_revisions_are_distinct_events():
    first = _official("2026-10-01-robot-control")
    second = _official("2026-11-05-realtime-latency")

    assert candidate_identity_urls(first).isdisjoint(candidate_identity_urls(second))


def test_same_official_revision_remains_duplicate_even_with_shared_technology():
    first = _official("2026-11-05-realtime-latency")
    same_event = _official("2026-11-05-realtime-latency", title="Astra gets much faster")

    assert candidate_identity_urls(first) == candidate_identity_urls(same_event)


def test_technology_id_alone_never_collapses_distinct_story_urls():
    capability = {
        "source": "HackerNews",
        "technology_id": "astra",
        "url": "https://example.com/astra-robot-control",
    }
    deployment = {
        "source": "HackerNews",
        "technology_id": "astra",
        "url": "https://example.com/astra-commercial-factory-deployment",
    }

    assert candidate_identity_urls(capability).isdisjoint(candidate_identity_urls(deployment))
