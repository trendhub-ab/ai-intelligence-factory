from __future__ import annotations

from datetime import timedelta

from v2_005_live_proof import build_live_proof
from v2_four_source_live import FourSourceLiveConfig
from tests.test_v2_005_live_proof import (
    FakeResponse,
    NOW,
    _evidence_body,
    _semantic_body_from_request,
    four_source_http_get,
)


SEMANTIC_POOL = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
EVIDENCE_POOL = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
    "gemini-3-flash-preview",
]


def _config() -> FourSourceLiveConfig:
    return FourSourceLiveConfig(hn_limit=1, arxiv_limit=0, max_total_candidates=8)


def test_v2_exposes_the_same_lane_membership_as_v1():
    calls = []

    def http_post(url, **kwargs):
        calls.append(url)
        if "flash-lite" in url:
            return FakeResponse(json_data=_semantic_body_from_request(kwargs))
        return FakeResponse(json_data=_evidence_body())

    report = build_live_proof(
        now=NOW,
        run_id="v2-v1-parity-pools",
        api_key="SECRET_KEY",
        config=_config(),
        http_get=four_source_http_get,
        http_post=http_post,
        provider_health_history=[],
    )

    assert report["observation"]["semantic_model_pool"] == SEMANTIC_POOL
    assert report["observation"]["evidence_model_pool"] == EVIDENCE_POOL
    assert report["observation"]["semantic_request_budget"] == 2
    assert report["observation"]["request_budget"] == 5
    assert report["observation"]["total_model_request_budget"] == 7
    assert len(calls) == 2


def test_semantic_503_falls_back_to_31_lite_then_evidence_continues():
    calls = []

    def http_post(url, **kwargs):
        calls.append(url)
        if "gemini-3.5-flash-lite" in url:
            return FakeResponse(json_data={"error": "hidden"}, status_code=503)
        if "gemini-3.1-flash-lite" in url:
            return FakeResponse(json_data=_semantic_body_from_request(kwargs))
        return FakeResponse(json_data=_evidence_body())

    report = build_live_proof(
        now=NOW,
        run_id="v2-semantic-lite-fallback",
        api_key="SECRET_KEY",
        config=_config(),
        http_get=four_source_http_get,
        http_post=http_post,
        provider_health_history=[],
    )

    assert [url.split("/models/", 1)[1].split(":", 1)[0] for url in calls] == [
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-3.6-flash",
    ]
    assert report["observation"]["semantic_selected_model"] == "gemini-3.1-flash-lite"
    assert report["deep_dive_result_category"] == "sufficient"


def test_evidence_503_falls_back_to_next_full_flash_model():
    calls = []

    def http_post(url, **kwargs):
        calls.append(url)
        if "flash-lite" in url:
            return FakeResponse(json_data=_semantic_body_from_request(kwargs))
        if "gemini-3.6-flash" in url:
            return FakeResponse(json_data={"error": "hidden"}, status_code=503)
        return FakeResponse(json_data=_evidence_body())

    report = build_live_proof(
        now=NOW,
        run_id="v2-evidence-fallback",
        api_key="SECRET_KEY",
        config=_config(),
        http_get=four_source_http_get,
        http_post=http_post,
        provider_health_history=[],
    )

    assert [url.split("/models/", 1)[1].split(":", 1)[0] for url in calls] == [
        "gemini-3.5-flash-lite",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
    ]
    assert report["observation"]["selected_evidence_model"] == "gemini-3.5-flash"
    assert report["deep_dive_result_category"] == "sufficient"


def test_evidence_can_reach_three_flash_preview_as_last_resort():
    calls = []

    def http_post(url, **kwargs):
        calls.append(url)
        if "flash-lite" in url:
            return FakeResponse(json_data=_semantic_body_from_request(kwargs))
        if "gemini-3-flash-preview" in url:
            return FakeResponse(json_data=_evidence_body())
        return FakeResponse(json_data={"error": "hidden"}, status_code=503)

    report = build_live_proof(
        now=NOW,
        run_id="v2-preview-last-resort",
        api_key="SECRET_KEY",
        config=_config(),
        http_get=four_source_http_get,
        http_post=http_post,
        provider_health_history=[],
    )

    attempted_models = [url.split("/models/", 1)[1].split(":", 1)[0] for url in calls]
    assert attempted_models == [SEMANTIC_POOL[0], *EVIDENCE_POOL]
    assert report["observation"]["selected_evidence_model"] == "gemini-3-flash-preview"
    assert report["deep_dive_result_category"] == "sufficient"


def test_provider_health_can_reorder_models_inside_each_lane():
    recent = (NOW - timedelta(minutes=5)).isoformat()
    history = [
        {"timestamp": recent, "model": "gemini-3.5-flash-lite", "kind": "screening", "outcome": "error", "error_type": "503"},
        {"timestamp": recent, "model": "gemini-3.1-flash-lite", "kind": "screening", "outcome": "success", "error_type": ""},
        {"timestamp": recent, "model": "gemini-3.6-flash", "kind": "deep_dive", "outcome": "error", "error_type": "503"},
        {"timestamp": recent, "model": "gemini-3.5-flash", "kind": "deep_dive", "outcome": "success", "error_type": ""},
    ]
    calls = []

    def http_post(url, **kwargs):
        calls.append(url)
        if "flash-lite" in url:
            return FakeResponse(json_data=_semantic_body_from_request(kwargs))
        return FakeResponse(json_data=_evidence_body())

    report = build_live_proof(
        now=NOW,
        run_id="v2-health-ranked-pools",
        api_key="SECRET_KEY",
        config=_config(),
        http_get=four_source_http_get,
        http_post=http_post,
        provider_health_history=history,
    )

    assert report["observation"]["semantic_model_pool"][0] == "gemini-3.1-flash-lite"
    assert report["observation"]["evidence_model_pool"][0] == "gemini-3.5-flash"
    assert "gemini-3.1-flash-lite" in calls[0]
    assert "gemini-3.5-flash" in calls[1]
