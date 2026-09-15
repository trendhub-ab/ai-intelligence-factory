from __future__ import annotations

import logging
from types import SimpleNamespace

import run367_x_daily_discovery as xdaily
from source_normalization import normalize_item


def _fake_pipeline():
    captured = {}

    def round_robin(groups, limit):
        captured["groups"] = groups
        captured["limit"] = limit
        return [item for rows in groups.values() for item in rows][:limit]

    pipeline = SimpleNamespace(
        round_robin_candidates=round_robin,
        normalize_item=normalize_item,
        logger=logging.getLogger("test-run367"),
        SOURCE_ROLE_CONTRACT={"GitHub": "production_discovery"},
        ENGAGEMENT_LABELS={},
    )
    return pipeline, captured


def _x_candidate(url: str):
    return normalize_item(
        "X",
        "primary candidate",
        url,
        "X監視で発見した一次情報候補URL。X投稿自体は根拠に使わない。",
        1,
        primary_url=url,
        source_context="",
        source_details={
            "source_platform": "x",
            "source_role": "discovery_signal",
            "raw_source_not_evidence": True,
            "evidence_status": "discovery_only",
            "is_evidence": False,
            "canonical_primary_url": url,
        },
    )


def test_fixed_watchlist_and_actor_bounds():
    handles = xdaily._load_watchlist()
    payload = xdaily.build_actor_input(handles)

    assert len(handles) == 20
    assert len({item.casefold() for item in handles}) == 20
    assert payload["outputFormat"] == "profile"
    assert payload["maxPosts"] == 5
    assert payload["onlyPostsNewerThan"] == "12 hours"
    assert payload["includeRaw"] is False
    assert payload["isolateProfiles"] is True
    assert xdaily.DEFAULT_MAX_CHARGE_USD == 0.05
    assert xdaily.DEFAULT_MAX_RECORDS == 100


def test_queue_conversion_keeps_raw_x_out_of_evidence_and_context():
    pipeline, _ = _fake_pipeline()
    queue = {
        "queue_type": "x_primary_source_resolution",
        "source_platform": "x",
        "evidence_status": "discovery_only",
        "factory_write": False,
        "items": [
            {
                "canonical_url": "https://example.com/releases/new-model?utm_source=x",
                "mention_count": 2,
                "authors": ["ExampleAI"],
                "x_post_ids": ["123"],
                "x_post_urls": ["https://x.com/ExampleAI/status/123"],
                "source_role": "discovery_signal",
                "resolution_status": "candidate_needs_primary_verification",
                "is_evidence": False,
            }
        ],
    }

    items = xdaily.queue_to_factory_candidates(pipeline, queue)

    assert len(items) == 1
    item = items[0]
    assert item["source"] == "X"
    assert item["url"] == "https://example.com/releases/new-model"
    assert item["primaryUrl"] == "https://example.com/releases/new-model"
    assert item["sourceContext"] == ""
    assert "x.com/ExampleAI/status/123" not in item["description"]
    assert item["sourceDetails"]["raw_source_not_evidence"] is True
    assert item["sourceDetails"]["is_evidence"] is False
    assert item["sourceDetails"]["evidence_status"] == "discovery_only"


def test_full_mode_injects_x_and_dedupes_before_screening(monkeypatch):
    pipeline, captured = _fake_pipeline()
    monkeypatch.setenv("AIIF_X_DISCOVERY_ENABLED", "true")
    monkeypatch.setenv("AIIF_RUN_MODE", "full")
    duplicate = _x_candidate("https://example.com/already?utm_source=x")
    fresh = _x_candidate("https://vendor.example/new-release")
    calls = {"count": 0}

    def fake_acquire(_pipeline):
        calls["count"] += 1
        return [duplicate, fresh]

    monkeypatch.setattr(xdaily, "acquire_x_candidates", fake_acquire)
    xdaily.install(pipeline)

    groups = {
        "GitHub": [normalize_item("GitHub", "existing", "https://example.com/already", "existing", 1)],
        "HackerNews": [],
        "ArXiv": [],
        "ProductHunt": [],
    }
    result = pipeline.round_robin_candidates(groups, 20)

    assert calls["count"] == 1
    assert [item["url"] for item in captured["groups"]["X"]] == ["https://vendor.example/new-release"]
    assert any(item["source"] == "X" for item in result)
    assert pipeline.SOURCE_ROLE_CONTRACT["X"] == "discovery_signal"

    pipeline.round_robin_candidates({"GitHub": [], "HackerNews": [], "ArXiv": [], "ProductHunt": []}, 20)
    assert calls["count"] == 1, "X provider must be called at most once per process"


def test_article_validation_never_calls_x(monkeypatch):
    pipeline, captured = _fake_pipeline()
    monkeypatch.setenv("AIIF_X_DISCOVERY_ENABLED", "true")
    monkeypatch.setenv("AIIF_RUN_MODE", "article_validation")

    def forbidden(_pipeline):
        raise AssertionError("X provider must not be called from article_validation")

    monkeypatch.setattr(xdaily, "acquire_x_candidates", forbidden)
    xdaily.install(pipeline)
    groups = {"GitHub": [], "HackerNews": [], "ArXiv": [], "ProductHunt": []}
    pipeline.round_robin_candidates(groups, 20)

    assert "X" not in captured["groups"]


def test_missing_apify_token_degrades_without_fake_success(monkeypatch, caplog):
    pipeline, _ = _fake_pipeline()
    monkeypatch.setenv("AIIF_X_DISCOVERY_ENABLED", "true")
    monkeypatch.setenv("AIIF_RUN_MODE", "full")
    monkeypatch.delenv("APIFY_TOKEN", raising=False)

    with caplog.at_level(logging.WARNING):
        result = xdaily.acquire_x_candidates(pipeline)

    assert result == []
    assert "APIFY_TOKEN missing" in caplog.text
    assert not hasattr(pipeline, "X_DISCOVERY_LAST_MANIFEST")


def test_provider_failure_isolated_from_existing_sources(monkeypatch, caplog):
    pipeline, _ = _fake_pipeline()
    monkeypatch.setenv("AIIF_X_DISCOVERY_ENABLED", "true")
    monkeypatch.setenv("AIIF_RUN_MODE", "full")
    monkeypatch.setenv("APIFY_TOKEN", "test-token")

    class BrokenProvider:
        def __init__(self, **_kwargs):
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr(xdaily, "ApifyProvider", BrokenProvider)
    with caplog.at_level(logging.WARNING):
        result = xdaily.acquire_x_candidates(pipeline)

    assert result == []
    assert "provider unavailable" in caplog.text
    assert pipeline.X_DISCOVERY_LAST_ERROR == "provider unavailable"


def test_canonical_url_removes_only_tracking_noise():
    value = xdaily.canonical_url("HTTPS://Example.COM/path/?utm_source=x&keep=1#fragment")
    assert value == "https://example.com/path?keep=1"
