from __future__ import annotations

import json
from datetime import datetime, timezone

from v2_live_shadow_acquisition import LiveAcquisitionConfig
from v2_005_live_proof import build_live_proof


NOW = datetime(2026, 10, 15, 0, 0, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, *, json_data=None, text="", status_code=200):
        self._json_data = json_data
        self.text = text
        self.content = text.encode("utf-8")
        self.status_code = status_code

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _arxiv_xml(entries: str = "") -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">{entries}</feed>'''


def two_candidate_http_get(url, **kwargs):
    if url.endswith("topstories.json"):
        return FakeResponse(json_data=[101, 102])
    if "/101.json" in url:
        return FakeResponse(
            json_data={
                "id": 101,
                "type": "story",
                "title": "Alpha bounded AI release",
                "url": "https://a.example/releases/alpha",
                "time": 1792020000,
                "score": 180,
                "descendants": 60,
            }
        )
    if "/102.json" in url:
        return FakeResponse(
            json_data={
                "id": 102,
                "type": "story",
                "title": "Beta bounded AI release",
                "url": "https://b.example/releases/beta",
                "time": 1792020000,
                "score": 170,
                "descendants": 55,
            }
        )
    if "export.arxiv.org" in url:
        return FakeResponse(text=_arxiv_xml())
    raise AssertionError(url)


def _provider_body(*, sufficient=True, usage=None):
    evidence = {
        "evidence_sufficient": sufficient,
        "reason_code": "sufficient_source_evidence" if sufficient else "insufficient_source_evidence",
        "evidence_points": ["The supplied metadata contains a bounded factual signal."],
    }
    body = {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps(evidence)}]}}
        ]
    }
    if usage is not None:
        body["usageMetadata"] = usage
    return body


def _build(*, post_response):
    post_calls = []

    def http_post(url, **kwargs):
        post_calls.append((url, kwargs))
        return post_response

    report = build_live_proof(
        now=NOW,
        run_id="v2-005-test",
        api_key="SECRET_KEY",
        config=LiveAcquisitionConfig(hn_limit=2, arxiv_limit=0, total_candidate_limit=2),
        http_get=two_candidate_http_get,
        http_post=http_post,
    )
    return report, post_calls


def test_live_proof_records_safe_rank1_measurement_with_one_provider_request():
    report, post_calls = _build(post_response=FakeResponse(json_data=_provider_body()))

    assert len(post_calls) == 1
    url, kwargs = post_calls[0]
    assert "gemini-3.6-flash:generateContent" in url
    assert kwargs["timeout"] == 120.0
    measurement = report["v2_005_measurement"]
    assert report["v2_selected_candidate_identity"] == measurement["evaluated_candidate"]["candidate_identity"]
    assert measurement["proof_version"] == "V2-005"
    assert measurement["production_mutation_authorized"] is False
    assert measurement["promotion_decision"] == "human_review_required"
    assert set(measurement["evaluated_candidate"]) == {
        "candidate_identity",
        "provider",
        "title",
        "source_timestamp",
        "screening_score",
        "screening_reasons",
    }
    assert measurement["provider_request_count"] == 1


def test_live_proof_records_numeric_provider_usage_when_present():
    report, _ = _build(
        post_response=FakeResponse(
            json_data=_provider_body(
                usage={
                    "promptTokenCount": 123,
                    "candidatesTokenCount": 45,
                    "totalTokenCount": 168,
                }
            )
        )
    )
    assert report["v2_005_measurement"]["provider_usage"] == {
        "prompt_token_count": 123,
        "candidate_token_count": 45,
        "total_token_count": 168,
    }


def test_live_proof_tolerates_missing_usage_metadata():
    report, _ = _build(post_response=FakeResponse(json_data=_provider_body()))
    assert report["deep_dive_result_category"] == "sufficient"
    assert report["v2_005_measurement"]["provider_usage"] is None


def test_live_proof_tolerates_malformed_usage_metadata():
    report, _ = _build(
        post_response=FakeResponse(
            json_data=_provider_body(
                usage={
                    "promptTokenCount": 123,
                    "candidatesTokenCount": "45",
                    "totalTokenCount": 168,
                }
            )
        )
    )
    assert report["deep_dive_result_category"] == "sufficient"
    assert report["v2_005_measurement"]["provider_usage"] is None


def test_live_proof_does_not_persist_description_prompt_key_headers_or_raw_provider_body():
    def secret_http_get(url, **kwargs):
        if url.endswith("topstories.json"):
            return FakeResponse(json_data=[101])
        if "/101.json" in url:
            return FakeResponse(
                json_data={
                    "id": 101,
                    "type": "story",
                    "title": "Alpha bounded AI release",
                    "url": "https://a.example/releases/alpha",
                    "time": 1792020000,
                    "score": 180,
                    "descendants": 60,
                    "text": "SECRET_DESCRIPTION",
                }
            )
        if "export.arxiv.org" in url:
            return FakeResponse(text=_arxiv_xml())
        raise AssertionError(url)

    def http_post(url, **kwargs):
        body = _provider_body()
        body["providerDebug"] = "SECRET_PROVIDER_BODY"
        return FakeResponse(json_data=body)

    report = build_live_proof(
        now=NOW,
        run_id="v2-005-secret-test",
        api_key="SECRET_KEY",
        config=LiveAcquisitionConfig(hn_limit=1, arxiv_limit=0, total_candidate_limit=1),
        http_get=secret_http_get,
        http_post=http_post,
    )
    serialized = json.dumps(report, ensure_ascii=False)
    assert "SECRET_DESCRIPTION" not in serialized
    assert "SECRET_KEY" not in serialized
    assert "SECRET_PROVIDER_BODY" not in serialized
    assert "x-goog-api-key" not in serialized
    assert "Candidate metadata" not in serialized


def test_live_proof_preserves_safe_provider_failure_classification_without_retry():
    post_calls = 0

    def http_post(url, **kwargs):
        nonlocal post_calls
        post_calls += 1
        return FakeResponse(json_data={"error": "SECRET_PROVIDER_BODY"}, status_code=429)

    report = build_live_proof(
        now=NOW,
        run_id="v2-005-429",
        api_key="SECRET_KEY",
        config=LiveAcquisitionConfig(hn_limit=2, arxiv_limit=0, total_candidate_limit=2),
        http_get=two_candidate_http_get,
        http_post=http_post,
    )
    assert post_calls == 1
    assert report["deep_dive_result_category"] == "provider_failure"
    assert report["observation"]["provider_error_category"] == "provider_http_429"
    assert report["v2_selected_candidate_identity"] is None
    assert "SECRET_PROVIDER_BODY" not in json.dumps(report)


def test_live_proof_insufficient_rank1_never_rescues_rank2():
    report, post_calls = _build(
        post_response=FakeResponse(json_data=_provider_body(sufficient=False))
    )
    assert len(post_calls) == 1
    assert report["deep_dive_result_category"] == "insufficient_evidence"
    assert report["v2_selected_candidate_identity"] is None


def test_live_proof_keeps_v1_authority_and_diagnostic_only_boundary():
    report, _ = _build(post_response=FakeResponse(json_data=_provider_body()))
    assert report["observation"]["production_authority"] == "v1"
    assert report["observation"]["diagnostic_only"] is True
    assert report["observation"]["request_budget"] == 1
    assert report["actual_calls"]["deep_dive"] <= 1
    assert report["v2_005_measurement"]["production_mutation_authorized"] is False
